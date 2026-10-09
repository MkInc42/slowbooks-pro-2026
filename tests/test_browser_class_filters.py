"""Class on the General Ledger and the register, the Chart of Accounts'
links and filter box, and line-level class with the warn-when-blank
setting (#236, #240, #243), in playwright's Chromium on the bakery's
books of tests/test_theme_contrast.py with the classes and the split bill
of tests/test_browser_classes.py:

- the General Ledger shows a Class column; its Account and Class pickers
  (named, keyboard) re-run the report, ride on its address (replaced, not
  pushed), its export links and its drill-down; a class-filtered ledger
  says so;
- the bank register's From / To / Class filters ride on its address and
  show the balance brought forward; a class-filtered register says the
  account's whole balance beside it;
- the Chart of Accounts: an account's name opens its register (the bank
  register for a bank account, the drill-down for this year for the rest),
  the filter box narrows the rows and keeps the type headings, and the
  global search finds an account and opens its register;
- the line Class cell on the bill, journal and invoice forms in business
  mode, and the setting that warns when a document is saved without a
  class: with it on the header picker starts blank and Save asks first
  (Cancel keeps the form open, OK saves to Uncategorized); with it off the
  picker starts on Uncategorized and nothing asks.

Skipped, as one module, where playwright or its Chromium is not installed
(tests/test_gl_class_filter.py and tests/test_class_warn_setting.py check
the API and the sources).
"""

import datetime as dt

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_browser_classes import classed as _classed  # noqa: E402,F401
from tests.test_browser_report_views import (
    _hash,
    _history,
    _open_at,
    _query,
)  # noqa: E402
from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    _visit,
    books_fixture,
    browser_fixture,
    company_fixture,
    settle,
)

SEPT = ("2026-09-01", "2026-09-30")
MODAL_SHOWN = (
    "() => !document.getElementById('modal-overlay').classList.contains('hidden')"
)
TITLE = "() => document.getElementById('modal-title').textContent"
# the register's own rows: the table headed Payee (the To-review panel has one too)
REG_ROWS = """() => { const t = [...document.querySelectorAll('#page-content table')]
    .find(t => t.tHead && /Payee/.test(t.tHead.textContent));
    return t ? [...t.tBodies[0].rows].map(r => r.textContent.replace(/\\s+/g, ' ').trim()) : []; }"""


def _ok(r):
    assert r.status_code in (200, 201), (str(r.request.url), r.status_code, r.text)
    return r.json()


@pytest.fixture(name="classed")
def classed_fixture(_classed):  # noqa: F811  (the fixture, by its name)
    """Site Prep, Old Crew (archived) and the bill split across them."""
    return _classed


# ── #236: the General Ledger ──────────────────────────────────────────────


def test_the_ledger_shows_the_class_column_and_its_pickers_filter_it(
    browser, company, books, classed
):
    site = classed["site"]
    accounts = {a["account_number"]: a for a in _ok(company.get("/api/accounts"))}
    url = f"#/reports/general-ledger?start_date={SEPT[0]}&end_date={SEPT[1]}"
    page, handled = _open_at(browser, company, url)
    try:
        page.wait_for_selector("#report-content table")
        heads = page.evaluate(
            "() => [...document.querySelector('#report-content table thead').querySelectorAll('th')].map(t => t.textContent.trim())"
        )
        assert heads == [
            "Date",
            "Description",
            "Reference",
            "Source",
            "Class",
            "Debit",
            "Credit",
            "Balance",
        ]
        body = page.inner_text("#report-content")
        assert "Site Prep" in body and "Uncategorized" in body
        length = _history(page)

        # the class picker, by its name: the ledger is that class's alone
        page.get_by_label("Class").select_option(str(site["id"]))
        settle(page, handled)
        page.wait_for_function(
            "() => document.getElementById('gl-class-note') !== null"
        )
        q = _query(_hash(page))
        assert (
            q["class_id"] == str(site["id"])
            and (q["start_date"], q["end_date"]) == SEPT
        )
        assert _history(page) == length, "a filter change replaces the address"
        classes = page.evaluate(
            "() => [...document.querySelectorAll('#report-content tbody tr')].map(r => r.children[4] && r.children[4].textContent.trim()).filter(Boolean)"
        )
        assert classes and set(classes) == {"Site Prep"}, classes
        assert "this class's lines only" in page.inner_text("#report-content")
        exports = page.evaluate(
            "() => [...document.querySelectorAll('#report-content button')].filter(b => /Save (PDF|CSV)/.test(b.textContent)).map(b => b.getAttribute('onclick'))"
        )
        assert len(exports) == 2 and all(f"class_id={site['id']}" in e for e in exports)

        # the account picker too; both on the address
        page.get_by_label("Account").select_option(str(accounts["6000"]["id"]))
        settle(page, handled)
        page.wait_for_function(
            "() => document.querySelectorAll('#report-content h3').length === 1"
        )
        q = _query(_hash(page))
        assert q["account_id"] == str(accounts["6000"]["id"]) and q["class_id"] == str(
            site["id"]
        )
        assert (
            page.locator("#report-content h3")
            .inner_text()
            .endswith(accounts["6000"]["name"])
        )
        assert "$120.00" in page.inner_text("#report-content tbody")

        # a reload reproduces the filtered ledger, pickers set
        page.reload()
        page.wait_for_function("window.App && document.readyState === 'complete'")
        page.evaluate(
            "() => { const s = document.getElementById('splash'); if (s) s.classList.add('hidden'); }"
        )
        page.wait_for_selector("#report-content table")
        settle(page, handled)
        assert page.evaluate("() => document.getElementById('gl-class').value") == str(
            site["id"]
        )
        assert page.evaluate(
            "() => document.getElementById('gl-account').value"
        ) == str(accounts["6000"]["id"])

        # the drill-down from a class-filtered ledger carries the class, and
        # Back to General Ledger returns to the filtered ledger
        page.locator("#report-content h3 a").first.click()
        page.wait_for_selector("#drilldown-body table")
        q = _query(_hash(page))
        assert q["class_id"] == str(site["id"]) and q["from"] == "general-ledger"
        assert "Site Prep" in page.evaluate(TITLE)
        page.get_by_role("button", name="Back to General Ledger").click()
        page.wait_for_selector("#report-content table")
        page.wait_for_function("() => document.getElementById('gl-class') !== null")
        assert page.evaluate("() => document.getElementById('gl-class').value") == str(
            site["id"]
        )
        assert _query(_hash(page))["class_id"] == str(site["id"])

        # a saved report keeps the filters
        page.on("dialog", lambda d: d.accept("Site Prep ledger"))
        page.get_by_role("button", name="Add to Saved Reports…").click()
        settle(page, handled)
        saved = _ok(company.get("/api/saved-reports"))
        mine = next(s for s in saved if s["name"] == "Site Prep ledger")
        assert mine["parameters"]["class_id"] == str(site["id"])
        assert mine["parameters"]["account_id"] == str(accounts["6000"]["id"])
    finally:
        page.close()


def test_the_register_filters_by_dates_and_class(browser, company, books, classed):
    site = classed["site"]
    accounts = {a["account_number"]: a for a in _ok(company.get("/api/accounts"))}
    bank = accounts["1000"]["id"]
    # a classed register entry in September, so the class filter has a line
    _ok(
        company.post(
            "/api/banking/transactions",
            json={
                "account_id": bank,
                "date": "2026-09-16",
                "amount": -45,
                "payee": "Site Prep fuel",
                "category_account_id": accounts["6000"]["id"],
                "class_id": site["id"],
            },
        )
    )
    page, handled = _open_at(browser, company, f"#/banking/{bank}")
    try:
        page.wait_for_selector("#page-content tbody tr")
        all_rows = len(page.evaluate(REG_ROWS))
        assert all_rows > 5
        assert page.locator("#reg-opening").count() == 0
        length = _history(page)

        page.get_by_label("From").fill(SEPT[0])
        page.dispatch_event("#reg-start", "change")
        settle(page, handled)
        page.wait_for_selector("#reg-opening")
        assert _query(_hash(page)) == {"start_date": SEPT[0]}
        assert _history(page) == length, "a filter change replaces the address"
        opening = page.inner_text("#reg-opening")
        assert "Balance brought forward" in opening
        assert (
            len(page.evaluate(REG_ROWS)) == all_rows
        ), "January's opening goes, the balance brought forward comes"

        page.get_by_label("Class").select_option(str(site["id"]))
        settle(page, handled)
        page.wait_for_function(
            "() => document.getElementById('reg-filter-note') && /Site Prep/.test(document.getElementById('reg-filter-note').textContent)"
        )
        q = _query(_hash(page))
        assert q["class_id"] == str(site["id"]) and q["start_date"] == SEPT[0]
        rows = page.evaluate(REG_ROWS)
        assert (
            len(rows) == 2
            and "Site Prep fuel" in rows[0]
            and "Balance brought forward (Site Prep)" in rows[1]
        ), rows
        note = page.inner_text("#reg-filter-note")
        assert "the account's whole balance is" in note
        reg = _ok(
            company.get(
                "/api/banking/check-register",
                params={
                    "account_id": bank,
                    "start_date": SEPT[0],
                    "class_id": site["id"],
                },
            )
        )
        assert f"${reg['balance']:,.2f}" in note.replace("-$", "$")

        # a reload reproduces the filtered register; Clear empties it
        page.reload()
        page.wait_for_function("window.App && document.readyState === 'complete'")
        page.evaluate(
            "() => { const s = document.getElementById('splash'); if (s) s.classList.add('hidden'); }"
        )
        page.wait_for_selector("#reg-filter-note")
        assert page.evaluate("() => document.getElementById('reg-class').value") == str(
            site["id"]
        )
        assert (
            page.evaluate("() => document.getElementById('reg-start').value") == SEPT[0]
        )
        page.get_by_role("button", name="Clear").click()
        settle(page, handled)
        page.wait_for_function(f"(n) => ({REG_ROWS})().length === n", arg=all_rows)
        assert _hash(page) == f"#/banking/{bank}"
    finally:
        page.close()


# ── #240: the Chart of Accounts opens the register; accounts in search ──


def test_chart_rows_open_the_register_and_the_filter_box_keeps_the_grouping(
    browser, company, books
):
    accounts = {a["account_number"]: a for a in _ok(company.get("/api/accounts"))}
    year = dt.date.today().year
    page, handled = _open_at(browser, company, "#/accounts")
    try:
        page.wait_for_selector("#page-content tbody tr")
        checking = page.locator("#page-content tbody a", has_text="Checking").first
        assert checking.get_attribute("href") == f"#/banking/{accounts['1000']['id']}"
        rent = page.locator(
            "#page-content tbody a", has_text=accounts["6000"]["name"]
        ).first
        q = _query(rent.get_attribute("href"))
        assert rent.get_attribute("href").startswith("#/reports/account-transactions?")
        assert q["account_id"] == str(accounts["6000"]["id"])
        assert q["period"] == "this_year"
        assert (q["start_date"], q["end_date"]) == (f"{year}-01-01", f"{year}-12-31")

        # the filter box, by keyboard: typing narrows the rows, the type
        # headings of the rows left stay, the others go
        box = page.get_by_label("Filter accounts")
        box.focus()
        page.keyboard.type("6000")
        page.wait_for_function(
            "() => [...document.querySelectorAll('#page-content tbody tr')].filter(r => r.offsetParent !== null).length < 6"
        )
        shown = page.evaluate(
            "() => [...document.querySelectorAll('#page-content tbody tr')].filter(r => r.offsetParent !== null).map(r => r.textContent.replace(/\\s+/g, ' ').trim())"
        )
        assert any("6000" in r for r in shown) and any(
            r == "Expenses" for r in shown
        ), shown
        assert not any(r == "Assets" for r in shown), shown
        page.keyboard.press("Control+A")
        page.keyboard.type("checking")
        page.wait_for_function(
            "() => [...document.querySelectorAll('#page-content tbody tr')].filter(r => r.offsetParent !== null).some(r => /Assets/.test(r.textContent))"
        )

        # the expense account's link opens the drill-down for this year
        box.fill("")
        rent = page.locator(
            "#page-content tbody a", has_text=accounts["6000"]["name"]
        ).first
        rent.focus()
        page.keyboard.press("Enter")
        page.wait_for_selector("#drilldown-body table")
        assert page.evaluate(TITLE) == f"Drill-down — {accounts['6000']['name']}"
        page.go_back()
        page.wait_for_selector("#page-content tbody tr")
        assert _hash(page) == "#/accounts"
        assert not page.evaluate(MODAL_SHOWN)

        # the bank account's link is the bank register
        page.locator("#page-content tbody a", has_text="Checking").first.click()
        page.wait_for_selector("#page-content .page-header h2")
        assert _hash(page) == f"#/banking/{accounts['1000']['id']}"

        # the search: an account by number, opening its register
        _visit(page, handled, "#/")
        page.fill("#global-search", "6000")
        page.wait_for_selector(
            "#search-results .search-section:has-text('Accounts')", timeout=5000
        )
        settle(page, handled)
        page.locator(
            "#search-results .search-item", has_text=accounts["6000"]["name"]
        ).first.click()
        page.wait_for_selector("#drilldown-body table")
        assert _query(_hash(page))["account_id"] == str(accounts["6000"]["id"])
    finally:
        page.close()
