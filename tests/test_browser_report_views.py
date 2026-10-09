"""Report views have addresses, and Back is real (R7, #237), in playwright's
Chromium on the bakery's books of tests/test_theme_contrast.py:

- a reload on #/reports/profit-loss?start_date=…&end_date=… reproduces the
  P&L on those dates, over the Report Center;
- changing the period inside the report rewrites the address in place
  (replaceState): no history entry per period tried;
- an account's drill-down pushes its own address, with the dates and the
  view it came from; browser Back returns to the report, and the
  drill-down's own "Back to Profit & Loss" button (named, keyboard) goes
  back through history too;
- a source link from the drill-down opens the document; Back returns to
  the drill-down, rebuilt from the address (the account's name comes from
  the server);
- the dashboard's "Full P&L" and "Full Balance Sheet" open the dated
  report; a saved report opens through the same address; a view nobody
  registered leaves the Report Center showing.

Skipped, as one module, where playwright or its Chromium is not installed
(tests/test_report_views.py drives the router in node).
"""

import datetime as dt
import re

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    ORIGIN,
    SERVED,
    _served_by,
    _visit,
    books_fixture,
    browser_fixture,
    company_fixture,
    settle,
)

SEPT = ("2026-09-01", "2026-09-30")
PL_URL = f"#/reports/profit-loss?start_date={SEPT[0]}&end_date={SEPT[1]}"

MODAL_SHOWN = (
    "() => !document.getElementById('modal-overlay').classList.contains('hidden')"
)
TITLE = "() => document.getElementById('modal-title').textContent"
PERIOD = """() => ({
    period: document.getElementById('report-period-select').value,
    start: document.getElementById('report-custom-start').value,
    end: document.getElementById('report-custom-end').value,
})"""


def _open_at(browser, client, page_hash):
    """A fresh document at the address: what a bookmark, a pasted link or a
    reload does."""
    handled = []
    page = browser.new_page(viewport={"width": 1500, "height": 980})
    page.route("**/*", _served_by(client, handled, SERVED))
    page.goto(f"{ORIGIN}/{page_hash}")
    page.wait_for_function("window.App && document.readyState === 'complete'")
    page.evaluate(
        "() => { const s = document.getElementById('splash'); if (s) s.classList.add('hidden'); }"
    )
    settle(page, handled)
    return page, handled


def _hash(page):
    return page.evaluate("location.hash")


def _history(page):
    return page.evaluate("history.length")


def _query(h):
    return dict(p.split("=", 1) for p in h.split("?", 1)[1].split("&"))


def test_a_reload_on_the_address_reproduces_the_report_and_a_period_change_replaces_it(
    browser, company, books
):
    page, handled = _open_at(browser, company, PL_URL)
    try:
        page.wait_for_selector("#report-content table")
        assert page.evaluate(MODAL_SHOWN)
        assert page.evaluate(TITLE) == "Profit & Loss"
        assert page.evaluate(PERIOD) == {
            "period": "custom",
            "start": SEPT[0],
            "end": SEPT[1],
        }
        # the Report Center is the page under it
        assert page.locator("#page-content .card-grid .card").count() > 5
        assert _hash(page) == PL_URL
        # the report is on the dates asked for: the books' September income
        body = page.evaluate(
            "() => document.getElementById('report-content').textContent"
        )
        assert "Sep 1, 2026" in body and "Sep 30, 2026" in body

        # a new period rewrites the address in place
        length = _history(page)
        page.select_option("#report-period-select", "this_year_to_date")
        settle(page, handled)
        page.wait_for_selector("#report-content table")
        h = _hash(page)
        q = _query(h)
        assert h.startswith("#/reports/profit-loss?")
        assert q["period"] == "this_year_to_date"
        assert q["start_date"] == f"{dt.date.today().year}-01-01"
        assert q["end_date"] == dt.date.today().isoformat()
        assert _history(page) == length, "a period change must not pile up history"

        # custom dates, typed: the same
        page.select_option("#report-period-select", "custom")
        page.fill("#report-custom-start", "2026-08-01")
        page.fill("#report-custom-end", "2026-08-31")
        page.dispatch_event("#report-custom-end", "change")
        settle(page, handled)
        assert (
            _hash(page)
            == "#/reports/profit-loss?start_date=2026-08-01&end_date=2026-08-31"
        )
        assert _history(page) == length
    finally:
        page.close()


def test_a_drill_down_pushes_and_back_returns_to_the_report(browser, company, books):
    page, handled = _open_at(browser, company, PL_URL)
    try:
        page.wait_for_selector("#report-content table")
        length = _history(page)
        link = page.locator("#report-content tbody a").first
        account = link.text_content().strip()
        link.click()
        page.wait_for_selector("#drilldown-body table")
        h = _hash(page)
        q = _query(h)
        assert h.startswith("#/reports/account-transactions?")
        assert re.fullmatch(r"\d+", q["account_id"])
        assert (q["start_date"], q["end_date"]) == SEPT
        assert q["from"] == "profit-loss"
        assert _history(page) == length + 1, "a hop pushes"
        assert page.evaluate(TITLE) == f"Drill-down — {account}"
        back = page.get_by_role("button", name="Back to Profit & Loss")
        assert back.count() == 1

        # the browser's Back: the report, on the same dates
        page.go_back()
        page.wait_for_selector("#report-content table")
        assert page.evaluate(TITLE) == "Profit & Loss"
        assert page.evaluate(PERIOD) == {
            "period": "custom",
            "start": SEPT[0],
            "end": SEPT[1],
        }
        assert _hash(page) == PL_URL

        # the drill-down's own button, by keyboard, goes back through history
        page.locator("#report-content tbody a").first.click()
        page.wait_for_selector("#drilldown-body table")
        assert _history(page) == length + 1
        page.get_by_role("button", name="Back to Profit & Loss").focus()
        page.keyboard.press("Enter")
        page.wait_for_selector("#report-content table")
        assert page.evaluate(TITLE) == "Profit & Loss"
        assert _hash(page) == PL_URL
        assert (
            _history(page) == length + 1
        ), "the button went back, not forward onto a copy"
    finally:
        page.close()


def test_back_from_a_document_returns_to_the_drill_down(browser, company, books):
    # the income account the September invoices posted to
    pl = company.get(
        "/api/reports/profit-loss", params={"start_date": SEPT[0], "end_date": SEPT[1]}
    ).json()
    row = pl["income"][0]
    url = (
        f"#/reports/account-transactions?account_id={row['account_id']}"
        f"&start_date={SEPT[0]}&end_date={SEPT[1]}&from=profit-loss"
    )
    page, handled = _open_at(browser, company, url)
    try:
        # rebuilt from the address alone: the name is the server's
        page.wait_for_selector("#drilldown-body table")
        assert page.evaluate(TITLE) == f"Drill-down — {row['account_name']}"
        assert page.get_by_role("button", name="Back to Profit & Loss").count() == 1
        rows = page.locator("#drilldown-body tbody tr").count()
        assert rows >= 2

        source = page.locator('#drilldown-body a[href^="/#/invoices/"]').first
        number = source.text_content().strip()
        source.click()
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Invoice #')"
        )
        assert _hash(page).startswith("#/invoices/")
        assert page.locator("#drilldown-body").count() == 0

        page.go_back()
        page.wait_for_selector("#drilldown-body table")
        assert _hash(page) == url
        assert page.evaluate(TITLE) == f"Drill-down — {row['account_name']}"
        assert page.locator("#drilldown-body tbody tr").count() == rows
        assert number in page.evaluate(
            "() => document.getElementById('drilldown-body').textContent"
        )

        # Back to the report from a drill-down reached by its address: the
        # report opens on the drill-down's dates
        page.get_by_role("button", name="Back to Profit & Loss").click()
        page.wait_for_selector("#report-content table")
        assert page.evaluate(TITLE) == "Profit & Loss"
        assert page.evaluate(PERIOD) == {
            "period": "custom",
            "start": SEPT[0],
            "end": SEPT[1],
        }
        assert _hash(page) == PL_URL
    finally:
        page.close()


def test_the_dashboard_cards_open_the_dated_report(browser, company, books):
    r = company.put(
        "/api/preferences/dashboard",
        json={"value": {"order": ["pnl_month", "pnl_ytd", "balance_sheet_trend"]}},
    )
    assert r.status_code == 200, r.text
    page, handled = _open_at(browser, company, "#/")
    today = dt.date.today()
    try:
        page.wait_for_selector("#page-content a:has-text('Full P&L')")
        hrefs = page.evaluate(
            "() => [...document.querySelectorAll('#page-content a')]"
            ".filter(a => /^Full /.test(a.textContent)).map(a => [a.textContent, a.getAttribute('href')])"
        )
        assert [t for t, _ in hrefs] == ["Full P&L", "Full P&L", "Full Balance Sheet"]
        month = _query(hrefs[0][1])
        assert hrefs[0][1].startswith("#/reports/profit-loss?")
        assert month["period"] == "this_month"
        assert month["start_date"] == today.replace(day=1).isoformat()
        assert month["end_date"].startswith(today.strftime("%Y-%m-"))
        ytd = _query(hrefs[1][1])
        assert (
            ytd["period"] == "this_year_to_date"
            and ytd["start_date"] == f"{today.year}-01-01"
        )
        assert hrefs[2][1] == f"#/reports/balance-sheet?as_of_date={today.isoformat()}"

        page.click("#page-content a:has-text('Full Balance Sheet')")
        page.wait_for_selector("#report-content table")
        assert page.evaluate(TITLE) == "Balance Sheet"
        assert page.evaluate(PERIOD)["period"] == "custom"
        assert page.evaluate(PERIOD)["end"] == today.isoformat()
        # and Back is the dashboard
        page.go_back()
        page.wait_for_selector("#page-content a:has-text('Full P&L')")
        assert _hash(page) == "#/"
    finally:
        page.close()


def test_a_saved_report_opens_through_its_address_and_an_unknown_view_does_not_crash(
    browser, company, books
):
    r = company.post(
        "/api/saved-reports",
        json={
            "name": "September P&L",
            "report_type": "profit_loss",
            "parameters": {
                "period": "custom",
                "start_date": SEPT[0],
                "end_date": SEPT[1],
            },
        },
    )
    assert r.status_code in (200, 201), r.text
    page, handled = _open_at(browser, company, "#/reports")
    try:
        page.get_by_role("button", name="Open").first.click()
        page.wait_for_selector("#report-content table")
        assert _hash(page) == PL_URL
        assert page.evaluate(TITLE) == "Profit & Loss"
        assert page.evaluate(PERIOD) == {
            "period": "custom",
            "start": SEPT[0],
            "end": SEPT[1],
        }
    finally:
        page.close()

    page, handled = _open_at(
        browser, company, "#/reports/no-such-report?start_date=2026-01-01"
    )
    try:
        page.wait_for_selector("#page-content .card-grid")
        page.wait_for_function("() => location.hash === '#/reports'")
        assert not page.evaluate(MODAL_SHOWN)
        toast = page.evaluate(
            "() => [...document.querySelectorAll('#toast-container .toast')].map(t => t.textContent).join(' | ')"
        )
        assert 'no report called "no-such-report"' in toast
        # and a drill-down with no account falls back the same way
        _visit(page, handled, "#/reports/account-transactions?start_date=2026-01-01")
        page.wait_for_function("() => location.hash === '#/reports'")
        assert not page.evaluate(MODAL_SHOWN)
    finally:
        page.close()
