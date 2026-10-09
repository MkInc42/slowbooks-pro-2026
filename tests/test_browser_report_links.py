"""Every report row goes somewhere, and you can get back (2.22.0 theme C:
#239 R9, #238 R8, #241 R11), in playwright's Chromium on the bakery's books
of tests/test_theme_contrast.py:

- A/R Aging and Income by Customer rows open the customer's page; A/P
  Aging and 1099 rows open the vendor's page; browser Back returns to the
  report on its dates, with the keyboard back on the row it left from;
- Trial Balance and Cash Flow account rows open the drill-down for the
  report's dates with "Back to Trial Balance" / "Back to Cash Flow
  Statement"; a row the Cash Flow makes up (Net Income) stays text; the
  Back button works by keyboard and focus returns to the row;
- the Job Profitability customer cell opens the customer without taking the
  row's click; the row opens the job's own address, one entry;
- a class's P&L opened from Fund Balances says "Back to Fund Balances"; the
  Back label follows nonprofit vocabulary;
- the customer page's invoice rows open the invoice; its Reports row opens
  the Statement PDF, Income by Customer, A/R Aging and Job Profitability
  for that customer, each with a period in the address; the vendor page's
  opens A/P Aging, the 1099 Summary and the default account's register; a
  read-only sign-in keeps every one of them;
- a report opened for one customer highlights that customer's row and says
  so; Job Profitability filtered to a customer says so and labels its
  total as the customer's, with a way to the whole report that replaces
  the address;
- the drill-down is on the period shell: a new period re-renders in place
  and replaces the address; the class and account selects re-scope it;
  Previous/Next step through the report's accounts; Payee, the cleared
  mark, the void mark and the opening-balance line are shown; a job-cost
  line links to its entry; a saved drill-down reopens with its account.

Skipped, as one module, where playwright or its Chromium is not installed.
"""

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_browser_report_views import (  # noqa: E402
    SEPT,
    TITLE,
    _hash,
    _history,
    _open_at,
    _query,
)
from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    books_fixture,
    browser_fixture,
    company_fixture,
    settle,
)

YEAR = ("2026-01-01", "2026-09-30")
FOCUSED_KEY = "() => document.activeElement && document.activeElement.getAttribute('data-row-key')"


def _report(page):
    page.wait_for_selector("#report-content table")


def _modal_text(page):
    return page.evaluate("() => document.getElementById('modal-body').textContent")


# ── R9: rows become links, and Back returns to the row ───────────────────


def test_ar_aging_and_income_by_customer_rows_open_the_customer_and_back_returns_to_the_row(
    browser, company, books
):
    url = f"#/reports/ar-aging?as_of_date={SEPT[1]}"
    page, handled = _open_at(browser, company, url)
    try:
        _report(page)
        link = page.locator(
            f'#report-content a[data-row-key="customer:{books["customer"]}"]'
        )
        assert link.count() == 1
        assert link.text_content().strip() == "Salt & Pine Catering Co."
        length = _history(page)
        link.click()
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Customer — ')"
        )
        assert page.evaluate(TITLE) == "Customer — Salt & Pine Catering Co."
        assert _hash(page) == "#/customers"
        assert _history(page) == length + 1

        # Back: the report on its date, and the keyboard on the row it left
        page.go_back()
        _report(page)
        assert _hash(page) == url
        assert page.evaluate(TITLE) == "Accounts Receivable Aging"
        assert page.evaluate(FOCUSED_KEY) == f"customer:{books['customer']}"
    finally:
        page.close()

    url = f"#/reports/income-by-customer?start_date={YEAR[0]}&end_date={YEAR[1]}"
    page, handled = _open_at(browser, company, url)
    try:
        _report(page)
        link = page.locator(
            f'#report-content a[data-row-key="customer:{books["customer"]}"]'
        )
        assert link.count() == 1
        link.focus()
        page.keyboard.press("Enter")
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Customer — ')"
        )
        page.go_back()
        _report(page)
        assert _hash(page) == url
        assert page.evaluate(FOCUSED_KEY) == f"customer:{books['customer']}"
    finally:
        page.close()


def test_ap_aging_and_1099_rows_open_the_vendor(browser, company, books):
    url = f"#/reports/ap-aging?as_of_date={SEPT[1]}"
    page, handled = _open_at(browser, company, url)
    try:
        _report(page)
        link = page.locator(
            f'#report-content a[data-row-key="vendor:{books["vendor"]}"]'
        )
        assert link.count() == 1
        assert link.text_content().strip() == "Cascade Flour Mill"
        link.click()
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Vendor — ')"
        )
        assert page.evaluate(TITLE) == "Vendor — Cascade Flour Mill"
        assert _hash(page) == "#/vendors"
        page.go_back()
        _report(page)
        assert _hash(page) == url
        assert page.evaluate(FOCUSED_KEY) == f"vendor:{books['vendor']}"
    finally:
        page.close()

    page, handled = _open_at(browser, company, "#/reports/1099-summary?year=2026")
    try:
        page.wait_for_selector("#report-1099-content table")
        link = page.locator(
            f'#report-1099-content a[data-row-key="vendor:{books["vendor2"]}"]'
        )
        assert link.count() == 1
        assert link.text_content().strip() == "Blue Heron Installs"
        link.click()
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Vendor — ')"
        )
        assert page.evaluate(TITLE) == "Vendor — Blue Heron Installs"
        page.go_back()
        page.wait_for_selector("#report-1099-content table")
        assert _hash(page) == "#/reports/1099-summary?year=2026"
    finally:
        page.close()


def test_trial_balance_and_cash_flow_rows_open_the_drill_down_with_the_way_back(
    browser, company, books
):
    url = f"#/reports/trial-balance?start_date={SEPT[0]}&end_date={SEPT[1]}"
    page, handled = _open_at(browser, company, url)
    try:
        _report(page)
        link = page.locator('#report-content a[data-row-key^="drill:"]').first
        name = link.text_content().strip()
        key = link.get_attribute("data-row-key")
        length = _history(page)
        link.click()
        page.wait_for_selector("#drilldown-body table")
        q = _query(_hash(page))
        assert q["account_id"] == key.split(":")[1]
        assert (q["start_date"], q["end_date"]) == SEPT
        assert q["from"] == "trial-balance"
        assert _history(page) == length + 1
        assert page.evaluate(TITLE) == f"Drill-down — {name}"

        # the way back, by keyboard: the report as it was, the row focused
        back = page.get_by_role("button", name="Back to Trial Balance")
        assert back.count() == 1
        back.focus()
        page.keyboard.press("Enter")
        _report(page)
        assert page.evaluate(TITLE) == "Trial Balance"
        assert _hash(page) == url
        assert _history(page) == length + 1, "went back, not forward onto a copy"
        assert page.evaluate(FOCUSED_KEY) == key
    finally:
        page.close()

    url = f"#/reports/cash-flow?start_date={YEAR[0]}&end_date={YEAR[1]}"
    page, handled = _open_at(browser, company, url)
    try:
        _report(page)
        links = page.locator('#report-content a[data-row-key^="drill:"]')
        assert links.count() >= 1
        # a row the statement makes up is not a link
        net = page.locator("#report-content tbody tr", has_text="Net Income").first
        assert net.locator("a").count() == 0
        links.first.click()
        page.wait_for_selector("#drilldown-body table")
        q = _query(_hash(page))
        assert (q["start_date"], q["end_date"]) == YEAR
        assert q["from"] == "cash-flow"
        assert (
            page.get_by_role("button", name="Back to Cash Flow Statement").count() == 1
        )
        page.get_by_role("button", name="Back to Cash Flow Statement").click()
        _report(page)
        assert page.evaluate(TITLE) == "Cash Flow Statement"
        assert _hash(page) == url
    finally:
        page.close()


def test_job_profitability_customer_cell_opens_the_customer_and_the_row_the_job(
    browser, company, books
):
    url = f"#/reports/job-profitability?start_date={SEPT[0]}&end_date={SEPT[1]}"
    page, handled = _open_at(browser, company, url)
    try:
        _report(page)
        row = page.locator("#report-content tbody tr", has_text="Waterfront Gala")
        assert row.count() == 1
        link = row.locator(f'a[data-row-key="customer:{books["customer"]}"]')
        assert link.count() == 1
        length = _history(page)
        link.click()
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Customer — ')"
        )
        # the cell's click did not also open the job
        assert _hash(page) == "#/customers"
        page.go_back()
        _report(page)
        assert _hash(page) == url
        assert page.evaluate(FOCUSED_KEY) == f"customer:{books['customer']}"

        # the row: the job's own address, one entry, and Back returns here
        page.locator("#report-content tbody tr", has_text="Waterfront Gala").locator(
            "td"
        ).nth(1).click()
        page.wait_for_selector("#job-tab-body")
        assert _hash(page) == f"#/jobs/{books['job']}"
        assert _history(page) == length + 1
        page.go_back()
        _report(page)
        assert _hash(page) == url
    finally:
        page.close()


def test_a_class_pl_opened_from_fund_balances_goes_back_there_and_the_label_follows_the_vocabulary(
    browser, company, books
):
    [uncat] = [
        c for c in company.get("/api/classes").json() if c.get("is_system_default")
    ] or [company.get("/api/classes").json()[0]]
    url = (
        f"#/reports/profit-loss-class?class_id={uncat['id']}"
        f"&start_date={SEPT[0]}&end_date={SEPT[1]}&from=fund-balances"
    )
    page, handled = _open_at(browser, company, url)
    try:
        page.wait_for_selector("#class-pl-body table")
        back = page.get_by_role("button", name="Back to Fund Balances")
        assert back.count() == 1
        assert page.get_by_role("button", name="Back to P&L by Class").count() == 0
        # reached by its address alone: Back goes forward to the report
        back.click()
        page.wait_for_function(
            "() => location.hash.startsWith('#/reports/fund-balances?')"
        )
        q = _query(_hash(page))
        assert (q["start_date"], q["end_date"]) == SEPT
    finally:
        page.close()

    # a drill-down's Back names the report in the company's words
    r = company.put("/api/settings", json={"company_type": "nonprofit"})
    assert r.status_code == 200, r.text
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
        page.wait_for_selector("#drilldown-body table")
        assert (
            page.get_by_role("button", name="Back to Statement of Activities").count()
            == 1
        )
        assert page.get_by_role("button", name="Back to Profit & Loss").count() == 0
    finally:
        page.close()
        company.put("/api/settings", json={"company_type": "business"})
