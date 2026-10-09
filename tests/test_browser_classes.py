"""A class is an entity of its own (#234, R4), in playwright's Chromium on
the bakery's books of tests/test_theme_contrast.py with two classes added
and a bill split across them:

- #/classes lists every class with its income, cost of goods, expenses and
  net for the period, Active / Archived / All, the total of the rows shown
  and what every class together nets (the Profit & Loss); a period change
  rewrites the address in place; a class opens from its row by keyboard;
- #/classes/<id> is the class's page: Overview with the by-account figures
  and the company's net beside the class's, Transactions with every posted
  line across every account, each opening its document; the tab and the
  period ride in the address (replaced, not pushed), so Back from a
  document returns to the page on the tab it was left on;
- the Overview's links carry the page's dates into the class's P&L and the
  by-class report, and an account into its drill-down for this class;
- the Uncategorized page and an archived class's page open; the global
  search finds a class and opens its page; nonprofit vocabulary (Fund).

Skipped, as one module, where playwright or its Chromium is not installed
(tests/test_class_entity.py checks the API and the sources).
"""

import datetime as dt

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_browser_report_views import (
    _hash,
    _history,
    _open_at,
    _query,
)  # noqa: E402
from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    _visit,
    browser_fixture,
    company_fixture,
    settle,
)

SEPT = ("2026-09-01", "2026-09-30")
MODAL_SHOWN = (
    "() => !document.getElementById('modal-overlay').classList.contains('hidden')"
)
TITLE = "() => document.getElementById('modal-title').textContent"
ROWS = "() => [...document.querySelectorAll('#page-content tbody tr')].map(r => r.textContent.replace(/\\s+/g, ' ').trim())"


def _ok(r):
    assert r.status_code in (200, 201), (str(r.request.url), r.status_code, r.text)
    return r.json()


@pytest.fixture
def classed(company, books):
    """Two classes and a bill split across them, in September: Site Prep
    (active) with one line, Old Crew (archived) with the other."""
    site = _ok(company.post("/api/classes", json={"name": "Site Prep"}))
    crew = _ok(company.post("/api/classes", json={"name": "Old Crew"}))
    accounts = {a["account_number"]: a for a in _ok(company.get("/api/accounts"))}
    bill = _ok(
        company.post(
            "/api/bills",
            json={
                "vendor_id": books["vendor"],
                "date": "2026-09-14",
                "terms": "Net 30",
                "bill_number": "SPLIT-1",
                "lines": [
                    {
                        "account_id": accounts["6000"]["id"],
                        "description": "Grading",
                        "quantity": 1,
                        "rate": 120,
                        "class_id": site["id"],
                    },
                    {
                        "account_id": accounts["6000"]["id"],
                        "description": "Old crew hours",
                        "quantity": 1,
                        "rate": 80,
                        "class_id": crew["id"],
                    },
                ],
            },
        )
    )
    _ok(company.put(f"/api/classes/{crew['id']}", json={"is_archived": True}))
    uncat = next(c for c in _ok(company.get("/api/classes")) if c["is_system_default"])
    return {"site": site, "crew": crew, "bill": bill, "uncat": uncat}


def _list_url(start, end, **more):
    qs = "&".join(
        f"{k}={v}" for k, v in {"start_date": start, "end_date": end, **more}.items()
    )
    return f"#/classes?{qs}"


def test_the_classes_list_shows_each_class_for_the_period_and_says_what_it_totals(
    browser, company, books, classed
):
    page, handled = _open_at(browser, company, _list_url(*SEPT))
    try:
        page.wait_for_selector("#classes-table tbody tr")
        rows = page.evaluate(ROWS)
        names = [r.split(" ")[0] for r in rows]
        assert any(r.startswith("Uncategorized") for r in rows)
        assert any("Site Prep Active" in r for r in rows), rows
        assert not any("Old Crew" in r for r in rows), "archived classes start hidden"
        site_row = next(r for r in rows if "Site Prep" in r)
        assert "$120.00" in site_row and "-$120.00" in site_row, site_row
        # the total is of the rows shown, and the note says what everything nets
        foot = page.inner_text("#classes-table tfoot")
        assert "Total of the" in foot and "shown" in foot
        note = page.inner_text("#classes-total-note")
        assert "Showing 2 of 3" in note
        by_class = _ok(
            company.get(
                "/api/reports/profit-loss-by-class",
                params={"start_date": SEPT[0], "end_date": SEPT[1]},
            )
        )
        pl = _ok(
            company.get(
                "/api/reports/profit-loss",
                params={"start_date": SEPT[0], "end_date": SEPT[1]},
            )
        )
        assert by_class["total_net_income"] == pl["net_income"]
        net = f"{pl['net_income']:,.2f}".replace("-", "-$")
        if not net.startswith("-"):
            net = "$" + net
        assert net in note, (net, note)
        assert names

        # the Show picker, by its name: All adds the archived class, dimmed
        page.get_by_label("Show").select_option("all")
        settle(page, handled)
        rows = page.evaluate(ROWS)
        assert any("Old Crew Archived" in r for r in rows), rows
        assert "Every class is shown" in page.inner_text("#classes-total-note")
        assert page.locator("#classes-table tbody tr.row--dim").count() == 1
        assert _query(_hash(page))["show"] == "all"

        # a period change rewrites the address in place
        length = _history(page)
        page.get_by_label("Period").select_option("this_year_to_date")
        settle(page, handled)
        q = _query(_hash(page))
        assert q["period"] == "this_year_to_date"
        assert q["start_date"] == f"{dt.date.today().year}-01-01"
        assert _history(page) == length, "a period change must not pile up history"

        # the class opens from its row, by keyboard, carrying the dates
        link = page.locator("#classes-table a", has_text="Site Prep")
        link.focus()
        page.keyboard.press("Enter")
        page.wait_for_selector("#class-tab-body #class-stats")
        h = _hash(page)
        assert h.startswith(f"#/classes/{classed['site']['id']}?")
        assert _query(h)["period"] == "this_year_to_date"
        assert _history(page) == length + 1, "opening a class pushes"
        page.go_back()
        page.wait_for_selector("#classes-table tbody tr")
        assert _query(_hash(page))["show"] == "all"
    finally:
        page.close()


def test_the_class_page_ties_to_the_report_and_back_returns_to_the_tab_it_left(
    browser, company, books, classed
):
    site = classed["site"]
    url = f"#/classes/{site['id']}?start_date={SEPT[0]}&end_date={SEPT[1]}"
    page, handled = _open_at(browser, company, url)
    try:
        page.wait_for_selector("#class-stats")
        assert page.locator("#page-content h2", has_text="Site Prep").count() == 1
        stats = page.inner_text("#class-stats")
        assert "-$120.00" in stats and "$120.00" in stats
        # the net is the class's P&L column for the same dates
        pl = _ok(
            company.get(
                "/api/reports/profit-loss",
                params={
                    "start_date": SEPT[0],
                    "end_date": SEPT[1],
                    "class_id": site["id"],
                },
            )
        )
        assert pl["net_income"] == -120.0
        note = page.inner_text("#class-net-note")
        assert "-$120.00" in note and "of the company" in note
        # the report links carry the page's dates
        hrefs = page.evaluate(
            "() => [...document.querySelectorAll('#page-content .page-header a')].map(a => a.getAttribute('href'))"
        )
        assert (
            f"#/reports/profit-loss-class?class_id={site['id']}&start_date={SEPT[0]}&end_date={SEPT[1]}"
            in hrefs
        )
        assert any(
            h.startswith("#/reports/profit-loss-by-class?")
            and f"start_date={SEPT[0]}" in h
            for h in hrefs
        )
        assert "#/settings" in hrefs
        # an account opens its drill-down for this class
        acct = page.locator("#class-tab-body tbody a", has_text="Advertising")
        assert acct.count() == 1
        q = _query(acct.get_attribute("href"))
        assert q["class_id"] == str(site["id"]) and q["from"] == "classes"
        assert (q["start_date"], q["end_date"]) == SEPT
        # … and its "Back to <class>" returns to the page as it was left,
        # through history (the hop pushed one entry; Back takes it back)
        left = _hash(page)
        length = _history(page)
        acct.click()
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Drill-down')"
        )
        page.wait_for_selector("#drilldown-body table")
        assert _hash(page).startswith("#/reports/account-transactions?")
        assert _query(_hash(page))["from"] == "classes"
        assert _history(page) == length + 1
        back = page.get_by_role("button", name="Back to Site Prep")
        assert back.count() == 1
        back.click()
        page.wait_for_selector("#class-stats")
        assert _hash(page) == left
        assert _history(page) == length + 1  # back through history, no new entry
        assert not page.evaluate(MODAL_SHOWN)
        # the keyboard reaches the account link and the way back alike
        acct = page.locator("#class-tab-body tbody a", has_text="Advertising")
        acct.focus()
        page.keyboard.press("Enter")
        page.wait_for_selector("#drilldown-body table")
        page.get_by_role("button", name="Back to Site Prep").focus()
        page.keyboard.press("Enter")
        page.wait_for_selector("#class-stats")
        assert _hash(page) == left
        assert not page.evaluate(MODAL_SHOWN)

        # Transactions: the tab is pressed, the address replaced
        length = _history(page)
        page.get_by_role("button", name="Transactions").click()
        page.wait_for_selector("#class-transactions")
        assert _query(_hash(page))["tab"] == "transactions"
        assert _history(page) == length
        assert (
            page.get_by_role("button", name="Transactions").get_attribute(
                "aria-pressed"
            )
            == "true"
        )
        rows = page.evaluate(ROWS)
        assert len(rows) == 1 and "Grading" in rows[0] and "$120.00" in rows[0], rows
        assert "-$120.00" in page.inner_text("#class-transactions-note")

        # a line opens its document; Back returns to the page on Transactions
        link = page.locator("#class-transactions tbody a").first
        assert link.get_attribute("href") == f"/#/bills/{classed['bill']['id']}"
        link.click()
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Bill')"
        )
        assert _hash(page).startswith("#/bills/")
        page.go_back()
        page.wait_for_selector("#class-transactions")
        assert _query(_hash(page))["tab"] == "transactions"
        assert (
            _query(_hash(page))["start_date"],
            _query(_hash(page))["end_date"],
        ) == SEPT
        assert not page.evaluate(MODAL_SHOWN)

        # the period select on the page: a custom range, replaced in place
        page.get_by_label("Period").select_option("custom")
        page.fill("#class-start", "2026-08-01")
        page.fill("#class-end", "2026-08-31")
        page.dispatch_event("#class-end", "change")
        settle(page, handled)
        assert (
            _hash(page)
            == f"#/classes/{site['id']}?tab=transactions&start_date=2026-08-01&end_date=2026-08-31"
        )
        assert "Nothing posted" in page.inner_text("#class-tab-body")
    finally:
        page.close()


def test_the_default_and_an_archived_class_open_and_the_search_finds_a_class(
    browser, company, books, classed
):
    page, handled = _open_at(
        browser,
        company,
        f"#/classes/{classed['uncat']['id']}?start_date={SEPT[0]}&end_date={SEPT[1]}",
    )
    try:
        page.wait_for_selector("#class-stats")
        assert page.locator("#page-content h2", has_text="Uncategorized").count() == 1
        assert page.locator("#page-content .badge", has_text="default").count() == 1
        # the cleanup list: everything untagged in September
        page.get_by_role("button", name="Transactions").click()
        page.wait_for_selector("#class-transactions")
        assert page.locator("#class-transactions tbody tr").count() > 5

        _visit(
            page,
            handled,
            f"#/classes/{classed['crew']['id']}?start_date={SEPT[0]}&end_date={SEPT[1]}",
        )
        page.wait_for_selector("#class-stats")
        assert page.locator("#page-content .badge", has_text="Archived").count() == 1
        assert "-$80.00" in page.inner_text("#class-stats")

        # the global search: a class, escaped, opening its page
        _ok(company.post("/api/classes", json={"name": "Tom & <Jerry>"}))
        _visit(page, handled, "#/")
        page.fill("#global-search", "Tom &")
        page.wait_for_selector("#search-results .search-item", timeout=5000)
        settle(page, handled)
        items = page.evaluate(
            "() => [...document.querySelectorAll('#search-results .search-item')].map(e => e.textContent)"
        )
        assert "Tom & <Jerry>" in items, items
        assert (
            page.locator("#search-results .search-section", has_text="Classes").count()
            == 1
        )
        page.locator("#search-results .search-item", has_text="Tom & <Jerry>").click()
        page.wait_for_selector("#class-stats")
        assert page.locator("#page-content h2", has_text="Tom & <Jerry>").count() == 1
        assert _hash(page).startswith("#/classes/")
    finally:
        page.close()


def test_a_nonprofit_sees_funds(browser, company, books, classed):
    _ok(company.put("/api/settings", json={"company_type": "nonprofit"}))
    try:
        page, handled = _open_at(browser, company, _list_url(*SEPT))
        try:
            page.wait_for_selector("#classes-table tbody tr")
            assert page.locator("#page-content h2", has_text="Funds").count() == 1
            assert (
                page.locator("#sidebar a[href='#/classes']")
                .inner_text()
                .strip()
                .endswith("Funds")
            )
            assert "FUND" in page.inner_text("#classes-table thead").upper()
            page.locator("#classes-table a", has_text="Site Prep").click()
            page.wait_for_selector("#class-fund")
            assert "Without donor restrictions" in page.inner_text("#class-fund")
            assert (
                page.locator(
                    "#page-content .page-header a", has_text="Activities by Fund"
                ).count()
                == 1
            )
        finally:
            page.close()
    finally:
        _ok(company.put("/api/settings", json={"company_type": "business"}))
