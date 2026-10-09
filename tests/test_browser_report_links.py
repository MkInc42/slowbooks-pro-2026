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

import datetime as dt
import re

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
from tests.test_readonly_browser import _reader, _signed_in  # noqa: E402
from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    _open,
    _visit,
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
        assert _hash(page) == f"#/customers/{books['customer']}"
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
        assert _hash(page) == f"#/vendors/{books['vendor']}"
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
        assert _hash(page) == f"#/customers/{books['customer']}"
        page.go_back()
        _report(page)
        assert _hash(page) == url
        assert page.evaluate(FOCUSED_KEY) == f"customer:{books['customer']}"

        # the row: the job's own address, one entry, and Back returns here
        page.locator("#report-content tbody tr", has_text="Waterfront Gala").locator(
            "td"
        ).nth(1).click()
        page.wait_for_selector("#job-tab-body")
        # on the report's dates, with the way back (A's review of #242)
        assert _hash(page).startswith(f"#/jobs/{books['job']}?")
        assert "start_date=" in _hash(page) and "from=job-profitability" in _hash(page)
        assert page.locator("#page-content button", has_text="Back to").count() >= 1
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


# ── R8: entity pages open their reports pre-filtered ─────────────────────


def _home(browser, client, role=None):
    """The app at #/, the splash out of the way (as _open_at leaves it)."""
    page, handled = (
        _signed_in(browser, client, role) if role else _open(browser, client)
    )
    page.evaluate(
        "() => { const s = document.getElementById('splash'); if (s) s.classList.add('hidden'); }"
    )
    return page, handled


def _open_customer(page, handled, customer_id):
    _visit(page, handled, "#/customers")
    page.evaluate("(id) => CustomersPage.showDetails(id)", customer_id)
    page.wait_for_function(
        "() => document.getElementById('modal-title').textContent.startsWith('Customer — ')"
    )
    settle(page, handled)


def _open_vendor(page, handled, vendor_id):
    _visit(page, handled, "#/vendors")
    page.evaluate("(id) => VendorsPage.showDetails(id)", vendor_id)
    page.wait_for_function(
        "() => document.getElementById('modal-title').textContent.startsWith('Vendor — ')"
    )
    settle(page, handled)


def _hrefs(page, group):
    return page.evaluate(
        '(g) => [...document.querySelectorAll(`[role=group][aria-label="${g}"] a`)]'
        ".map(a => [a.textContent.trim(), a.getAttribute('href')])",
        group,
    )


def test_the_customer_page_invoice_rows_open_the_invoice_and_its_reports_open_for_the_customer(
    browser, company, books
):
    cid = books["customer"]
    page, handled = _home(browser, company)
    try:
        _open_customer(page, handled, cid)
        # an invoice row opens the invoice, not the Invoices list
        page.locator("#modal-body h4", has_text="Recent invoices").wait_for()
        page.locator("#modal-body h4", has_text="Recent invoices").locator(
            "xpath=following-sibling::table//tbody/tr[1]"
        ).click()
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Invoice #')"
        )
        assert re.fullmatch(r"#/invoices/\d+", _hash(page))

        # the Reports row: each report through its address, on a period
        page.go_back()
        _open_customer(page, handled, cid)
        links = dict(_hrefs(page, "Reports for this customer"))
        assert links == {
            "Income by Customer": f"#/reports/income-by-customer?customer_id={cid}&period=this_year_to_date",
            "A/R Aging": f"#/reports/ar-aging?customer_id={cid}&period=this_year_to_date",
            "Job Profitability": f"#/reports/job-profitability?customer_id={cid}&period=this_year_to_date",
        }
        statement = page.get_by_role("button", name="Statement (PDF)")
        assert statement.count() == 1
        assert (
            f"/api/reports/customer-statement/{cid}/pdf?as_of_date="
            in statement.get_attribute("onclick")
        )

        # A/R Aging: the whole report, this customer's row picked out and focused
        page.get_by_role("link", name="A/R Aging").click()
        _report(page)
        assert page.evaluate(TITLE) == "Accounts Receivable Aging"
        q = _query(_hash(page))
        assert q["customer_id"] == str(cid) and q["period"] == "this_year_to_date"
        assert q["as_of_date"] == dt.date.today().isoformat()
        current = page.locator('#report-content tr[aria-current="true"]')
        assert current.count() == 1 and "Salt & Pine" in current.text_content()
        assert page.evaluate(FOCUSED_KEY) == f"customer:{cid}"
        assert "TOTAL" in page.evaluate(
            "() => document.getElementById('report-content').textContent"
        )
        # a new period keeps the customer in the address
        page.select_option("#report-period-select", "last_month")
        settle(page, handled)
        _report(page)
        assert _query(_hash(page))["customer_id"] == str(cid)
        assert page.locator('#report-content tr[aria-current="true"]').count() == 1

        # Job Profitability: filtered to the customer's jobs, and says so
        page.go_back()
        _open_customer(page, handled, cid)
        page.get_by_role("link", name="Job Profitability").click()
        _report(page)
        body = page.evaluate(
            "() => document.getElementById('report-content').textContent"
        )
        assert "Salt & Pine Catering Co. only" in body
        assert "Total — Salt & Pine Catering Co." in body
        # the rows are the server's filter: none is "current" (R8 review)
        assert page.locator('#report-content tr[aria-current="true"]').count() == 0
        assert "No job" not in body
        assert "Waterfront Gala" in body
        length = _history(page)
        # the whole report, in place: the address loses the filter, no push
        page.get_by_role("link", name="Show all jobs").click()
        page.wait_for_function(
            "() => !document.querySelector('#report-content [data-filtered]')"
        )
        _report(page)
        assert "customer_id" not in _query(_hash(page))
        assert _history(page) == length
        body = page.evaluate(
            "() => document.getElementById('report-content').textContent"
        )
        assert "No job" in body and "Total — " not in body
    finally:
        page.close()


def test_the_vendor_page_reports_open_for_the_vendor(browser, company, books):
    accounts = company.get("/api/accounts").json()
    [cogs] = [a for a in accounts if a["account_number"] == "5000"]
    r = company.put(
        f"/api/vendors/{books['vendor']}",
        json={"default_expense_account_id": cogs["id"]},
    )
    assert r.status_code == 200, r.text
    vid, vid1099 = books["vendor"], books["vendor2"]
    page, handled = _home(browser, company)
    try:
        _open_vendor(page, handled, vid)
        links = dict(_hrefs(page, "Reports for this vendor"))
        assert links == {
            "A/P Aging": f"#/reports/ap-aging?vendor_id={vid}&period=this_year_to_date",
            f"{cogs['name']} register": f"#/reports/account-transactions?account_id={cogs['id']}&period=this_year_to_date",
        }
        page.get_by_role("link", name="A/P Aging").click()
        _report(page)
        assert page.evaluate(TITLE) == "Accounts Payable Aging"
        current = page.locator('#report-content tr[aria-current="true"]')
        assert current.count() == 1 and "Cascade Flour Mill" in current.text_content()
        assert page.evaluate(FOCUSED_KEY) == f"vendor:{vid}"

        page.go_back()
        _open_vendor(page, handled, vid)
        page.get_by_role("link", name=f"{cogs['name']} register").click()
        page.wait_for_selector("#drilldown-body table")
        assert page.evaluate(TITLE) == f"Drill-down — {cogs['name']}"
        assert _query(_hash(page))["account_id"] == str(cogs["id"])

        # a 1099 vendor: the summary for this year, its row picked out
        _open_vendor(page, handled, vid1099)
        links = dict(_hrefs(page, "Reports for this vendor"))
        year = dt.date.today().year
        assert (
            links["1099 Summary"]
            == f"#/reports/1099-summary?year={year}&vendor_id={vid1099}"
        )
        page.get_by_role("link", name="1099 Summary").click()
        page.wait_for_selector("#report-1099-content table")
        current = page.locator('#report-1099-content tr[aria-current="true"]')
        assert current.count() == 1 and "Blue Heron Installs" in current.text_content()
    finally:
        page.close()


def test_a_read_only_sign_in_keeps_the_reports_rows(
    browser, company, books, db_session
):
    reader = _reader(company, db_session)
    page, handled = _home(browser, reader, "readonly")
    try:
        _open_customer(page, handled, books["customer"])
        assert sorted(t for t, _ in _hrefs(page, "Reports for this customer")) == [
            "A/R Aging",
            "Income by Customer",
            "Job Profitability",
        ]
        assert page.get_by_role("button", name="Statement (PDF)").count() == 1
        _open_vendor(page, handled, books["vendor2"])
        assert sorted(t for t, _ in _hrefs(page, "Reports for this vendor")) == [
            "1099 Summary",
            "A/P Aging",
        ]
    finally:
        page.close()


ACTIVE_ID = "() => document.activeElement && document.activeElement.id"


def test_a_period_change_from_the_keyboard_keeps_focus_on_the_period_select(
    browser, company, books
):
    """The spotlighted row takes focus on the view's first render only: a
    period change used to throw a keyboard user off the select onto the
    row, so every next period needed Shift+Tab first (R8 review)."""
    cid = books["customer"]
    url = f"#/reports/ar-aging?customer_id={cid}&period=this_year_to_date"
    page, handled = _open_at(browser, company, url)
    try:
        _report(page)
        assert page.evaluate(FOCUSED_KEY) == f"customer:{cid}"
        page.focus("#report-period-select")
        page.keyboard.press("ArrowDown")
        settle(page, handled)
        _report(page)
        q = _query(_hash(page))
        assert q["period"] != "this_year_to_date" and q["customer_id"] == str(cid)
        assert page.evaluate(ACTIVE_ID) == "report-period-select"
        # the row is still picked out, just not focused
        assert page.locator('#report-content tr[aria-current="true"]').count() == 1
        page.keyboard.press("ArrowDown")
        settle(page, handled)
        _report(page)
        assert _query(_hash(page))["period"] != q["period"]
        assert page.evaluate(ACTIVE_ID) == "report-period-select"
        page.select_option("#report-period-select", "last_month")
        settle(page, handled)
        _report(page)
        assert page.evaluate(ACTIVE_ID) == "report-period-select"
    finally:
        page.close()

    # the 1099 summary: Generate from the keyboard keeps focus on Generate
    vid = books["vendor2"]
    page, handled = _open_at(
        browser, company, f"#/reports/1099-summary?year=2026&vendor_id={vid}"
    )
    try:
        page.wait_for_selector("#report-1099-content table")
        assert page.evaluate(FOCUSED_KEY) == f"vendor:{vid}"
        generate = page.get_by_role("button", name="Generate")
        generate.focus()
        page.keyboard.press("Enter")
        settle(page, handled)
        page.wait_for_selector("#report-1099-content table")
        assert page.evaluate("() => document.activeElement.textContent") == "Generate"
        assert page.locator('#report-1099-content tr[aria-current="true"]').count() == 1
    finally:
        page.close()


def test_back_from_a_report_opened_on_the_customer_or_vendor_page_returns_to_the_page(
    browser, company, books
):
    """The page has an address of its own (#/customers/12): Back from the
    report comes back to the page, not the list, and a reload keeps it."""
    cid, vid = books["customer"], books["vendor"]
    page, handled = _home(browser, company)
    try:
        _open_customer(page, handled, cid)
        assert _hash(page) == f"#/customers/{cid}"
        page.get_by_role("link", name="Income by Customer").click()
        _report(page)
        assert page.evaluate(TITLE) == "Income by Customer"
        page.go_back()
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Customer — ')"
        )
        settle(page, handled)
        assert _hash(page) == f"#/customers/{cid}"
        assert page.evaluate(TITLE) == "Customer — Salt & Pine Catering Co."
        # Back again: the list, the page gone
        page.go_back()
        page.wait_for_function(
            "() => document.getElementById('modal-overlay').classList.contains('hidden')"
        )
        assert _hash(page) == "#/customers"

        _open_vendor(page, handled, vid)
        assert _hash(page) == f"#/vendors/{vid}"
        page.get_by_role("link", name="A/P Aging").click()
        _report(page)
        page.go_back()
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Vendor — ')"
        )
        settle(page, handled)
        assert _hash(page) == f"#/vendors/{vid}"
        assert page.evaluate(TITLE) == "Vendor — Cascade Flour Mill"
    finally:
        page.close()

    # a reload on the address: the page over its list
    page, handled = _open_at(browser, company, f"#/customers/{cid}")
    try:
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Customer — ')"
        )
        assert page.locator("#customer-tbody").count() == 1
        assert page.evaluate(TITLE) == "Customer — Salt & Pine Catering Co."
    finally:
        page.close()
    page, handled = _open_at(browser, company, f"#/vendors/{vid}")
    try:
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Vendor — ')"
        )
        assert page.evaluate(TITLE) == "Vendor — Cascade Flour Mill"
    finally:
        page.close()


# ── R11: the drill-down re-dates and re-scopes in place ──────────────────


def _account(company, number):
    [a] = [
        x for x in company.get("/api/accounts").json() if x["account_number"] == number
    ]
    return a


def _drill(page):
    page.wait_for_selector("#drilldown-body table")


def test_the_drill_down_re_dates_in_place_and_its_selects_re_scope_it(
    browser, company, books
):
    cogs = _account(company, "5000")
    url = (
        f"#/reports/account-transactions?account_id={cogs['id']}"
        f"&start_date={SEPT[0]}&end_date={SEPT[1]}&from=profit-loss"
    )
    page, handled = _open_at(browser, company, url)
    try:
        _drill(page)
        assert page.evaluate(TITLE) == f"Drill-down — {cogs['name']}"
        assert _hash(page) == url
        assert page.input_value("#report-period-select") == "custom"
        assert page.input_value("#report-custom-start") == SEPT[0]
        # the toolbar: named selects, Previous/Next, where in the report
        assert page.get_by_label("Class", exact=True).count() == 1
        assert page.get_by_label("Account", exact=True).count() == 1
        assert page.get_by_role("button", name="Previous account").count() == 1
        assert page.get_by_role("button", name="Next account").count() == 1
        assert re.fullmatch(r"\d+ of \d+", page.text_content("#drill-position").strip())
        accounts = page.eval_on_selector_all(
            "#drill-account option", "os => os.map(o => [o.value, o.textContent])"
        )
        assert len(accounts) > 1 and page.input_value("#drill-account") == str(
            cogs["id"]
        )
        length = _history(page)

        # a new period: the same view, re-rendered, the address replaced
        page.select_option("#report-period-select", "this_year_to_date")
        settle(page, handled)
        _drill(page)
        q = _query(_hash(page))
        assert q["account_id"] == str(cogs["id"]) and q["from"] == "profit-loss"
        assert q["period"] == "this_year_to_date"
        assert q["start_date"] == f"{dt.date.today().year}-01-01"
        assert _history(page) == length
        assert "Jan 1, " in page.text_content("#drilldown-body p")

        # Next: the report's next account, in place
        page.get_by_role("button", name="Next account").click()
        settle(page, handled)
        _drill(page)
        i = [v for v, _ in accounts].index(str(cogs["id"]))
        following = accounts[i + 1]
        assert _query(_hash(page))["account_id"] == following[0]
        assert (
            page.evaluate(TITLE) == f"Drill-down — {following[1].split(' - ', 1)[-1]}"
        )
        assert _history(page) == length
        page.get_by_role("button", name="Previous account").click()
        settle(page, handled)
        _drill(page)
        assert _query(_hash(page))["account_id"] == str(cogs["id"])
        # the ends are disabled
        page.select_option("#drill-account", accounts[-1][0])
        settle(page, handled)
        _drill(page)
        assert page.get_by_role("button", name="Next account").is_disabled()
        assert not page.get_by_role("button", name="Previous account").is_disabled()

        # the class: the same account, that class's lines, named in the title
        [uncat] = [
            c for c in company.get("/api/classes").json() if c["is_system_default"]
        ]
        page.select_option("#drill-account", str(cogs["id"]))
        settle(page, handled)
        page.select_option("#drill-class", str(uncat["id"]))
        settle(page, handled)
        _drill(page)
        assert _query(_hash(page))["class_id"] == str(uncat["id"])
        assert page.evaluate(TITLE) == f"Drill-down — {cogs['name']} · {uncat['name']}"
        assert _history(page) == length
        page.select_option("#drill-class", "")
        settle(page, handled)
        _drill(page)
        assert "class_id" not in _query(_hash(page))

        # the way back is still the report it came from, on its own dates
        page.get_by_role("button", name="Back to Profit & Loss").click()
        _report(page)
        assert page.evaluate(TITLE) == "Profit & Loss"
        q = _query(_hash(page))
        assert (q["start_date"], q["end_date"]) == SEPT
    finally:
        page.close()


def test_the_drill_down_shows_what_the_register_sends_and_links_a_job_cost(
    browser, company, books
):
    ar = _account(company, "1100")
    page, handled = _open_at(
        browser,
        company,
        f"#/reports/account-transactions?account_id={ar['id']}&start_date={SEPT[0]}&end_date={SEPT[1]}",
    )
    try:
        _drill(page)
        heads = page.eval_on_selector_all(
            "#drilldown-body thead th",
            "els => els.map(e => e.getAttribute('aria-label') || e.textContent.trim())",
        )
        assert heads == [
            "Date",
            "Payee",
            "Ref",
            "Description",
            "Source",
            "Debit",
            "Credit",
            "Running",
            "Cleared",
        ]
        body = page.text_content("#drilldown-body")
        assert "Balance brought forward" in body and "Period total" in body
        assert "Opening:" in page.text_content("#drilldown-body p")
        assert "Salt & Pine Catering Co." in body  # the payee
        # the voided invoice: struck through, badged, still linked
        void = page.locator("#drilldown-body tr.row--void")
        assert void.count() >= 1
        assert void.first.locator(".badge-void").text_content().strip() == "void"
        assert void.first.locator('a[href^="/#/invoices/"]').count() == 1
        # a credit memo links to its own page
        assert (
            page.locator(
                f'#drilldown-body a[href="/#/credit-memos/{books["memo"]}"]'
            ).count()
            >= 1
        )
    finally:
        page.close()

    # the reconciled January statement: R on the bank's lines
    bank = _account(company, "1000")
    page, handled = _open_at(
        browser,
        company,
        f"#/reports/account-transactions?account_id={bank['id']}&start_date=2026-01-01&end_date=2026-01-31",
    )
    try:
        _drill(page)
        marks = page.eval_on_selector_all(
            "#drilldown-body tbody tr td:last-child",
            "els => els.map(e => e.textContent.trim())",
        )
        assert "R" in marks
    finally:
        page.close()

    # a job cost line opens the entry at its own address; Back returns
    cogs = _account(company, "5000")
    url = f"#/reports/account-transactions?account_id={cogs['id']}&start_date={SEPT[0]}&end_date={SEPT[1]}"
    page, handled = _open_at(browser, company, url)
    try:
        _drill(page)
        link = page.locator(
            f'#drilldown-body a[href="/#/job-costs/{books["job_cost"]}"]'
        )
        assert link.count() == 1
        assert link.text_content().strip() == f"Job cost #{books['job_cost']}"
        link.click()
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.startsWith('Job Cost ')"
        )
        assert _hash(page) == f"#/job-costs/{books['job_cost']}"
        page.go_back()
        _drill(page)
        assert _hash(page) == url
    finally:
        page.close()


def test_a_saved_drill_down_reopens_with_its_account_and_period(
    browser, company, books
):
    cogs = _account(company, "5000")
    url = f"#/reports/account-transactions?account_id={cogs['id']}&period=last_month&from=trial-balance"
    page, handled = _open_at(browser, company, url)
    try:
        _drill(page)
        assert page.input_value("#report-period-select") == "last_month"
        page.once("dialog", lambda d: d.accept("COGS, last month"))
        page.get_by_role("button", name="Add to Saved Reports…").click()
        page.wait_for_function(
            "() => [...document.querySelectorAll('#page-content .saved-report-row')].some(r => r.textContent.includes('COGS, last month'))"
        )
        [saved] = [
            s
            for s in company.get("/api/saved-reports").json()
            if s["name"] == "COGS, last month"
        ]
        assert saved["report_type"] == "account_transactions"
        p = saved["parameters"]
        assert (p["account_id"], p["from"], p["period"]) == (
            cogs["id"],
            "trial-balance",
            "last_month",
        )
        assert p["start_date"] and p["end_date"]

        _visit(page, handled, "#/reports")
        page.locator(".saved-report-row", has_text="COGS, last month").get_by_role(
            "button", name="Open"
        ).click()
        _drill(page)
        assert page.evaluate(TITLE) == f"Drill-down — {cogs['name']}"
        q = _query(_hash(page))
        assert q["account_id"] == str(cogs["id"]) and q["period"] == "last_month"
        assert page.input_value("#report-period-select") == "last_month"
        assert page.get_by_role("button", name="Back to Trial Balance").count() == 1
    finally:
        page.close()


def test_a_drill_down_line_is_named_in_the_apps_words_and_numbered_by_its_document(
    browser, company, books
):
    """A line's label was `source_type #source_id`, and an expense's
    source_id is its vendor, so two expenses read "expense #6"; a bill
    payment, a card charge or a manual journal read as a raw key (NEW-40).
    The label now carries the app's word and the number of the document
    the link opens; the links themselves are unchanged."""
    cash = _account(company, "1000")
    accounts = {
        a["account_number"]: a["id"] for a in company.get("/api/accounts").json()
    }
    r = company.post(
        "/api/journal",
        json={
            "date": "2026-09-16",
            "description": "till float",
            "lines": [
                {"account_id": accounts["1000"], "debit": "40", "credit": "0"},
                {"account_id": accounts["4000"], "debit": "0", "credit": "40"},
            ],
        },
    )
    assert r.status_code in (200, 201), r.text
    page, handled = _open_at(
        browser,
        company,
        f"#/reports/account-transactions?account_id={cash['id']}&start_date={SEPT[0]}&end_date={SEPT[1]}",
    )
    try:
        _drill(page)
        labels = page.eval_on_selector_all(
            "#drilldown-body tbody a",
            "els => els.map(a => [a.textContent.trim(), a.getAttribute('href')])",
        )
        assert labels
        for text, href in labels:
            n = href.rsplit("/", 1)[1]
            assert text.endswith(f" #{n}"), (text, href)
            word = text[: -len(f" #{n}")]
            assert word[0].isupper() and "_" not in word, text
        expenses = [(t, h) for t, h in labels if h.startswith("/#/expenses/")]
        assert len(expenses) >= 2
        assert len({t for t, _ in expenses}) == len(
            expenses
        ), "each expense is numbered by its own document, not its vendor"
        assert any(t.startswith("Expense #") for t, _ in expenses)
        assert any(t.startswith("Expense void #") for t, _ in expenses)
        assert any(
            t.startswith("Journal entry #") and h.startswith("/#/journal/")
            for t, h in labels
        )
    finally:
        page.close()
