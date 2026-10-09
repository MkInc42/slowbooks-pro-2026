"""The Job picker lists the customer's jobs, in playwright's Chromium on the
bakery's books of tests/test_theme_contrast.py with a second job added
(2.22.0 gate, NEW-36).

JobPicker.sync (utils.js) hid other customers' jobs when the hidden
<select> got focus, which the type-ahead box in front of it (combobox.js,
2.19) never gives it, so the list was never narrowed: Customer "Kootenai
Auto Group", Job "Rose" offered Rose City Diner's job, and the API took it.
Now the customer's choice narrows the list the moment it is made, reaching
the box does too, a chosen job of another customer is cleared when the
customer changes, and the server refuses what slips past the form — on
the invoice form, and on the estimate and sales receipt forms, which share
the picker. And books from before the rule: a note saved from the form
over an invoice carrying another customer's job (header and line) goes
through, the line's foreign job dropped, and the job is then put right.

Skipped, as one module, where playwright or its Chromium is not installed.
"""

import pytest

pytest.importorskip("playwright.sync_api")

from app.models.invoices import Invoice  # noqa: E402
from tests.test_browser_grid import _open_at  # noqa: E402
from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    books_fixture,
    browser_fixture,
    company_fixture,
    settle,
)

MODAL_SHOWN = (
    "() => !document.getElementById('modal-overlay').classList.contains('hidden')"
)
LIST_OPEN = "() => !document.querySelector('.cbx-popup').hidden"
SHOWN = """() => [...document.querySelectorAll('#cbx-listbox [role=option]')]
    .map(li => li.textContent.trim())"""
NOTE = "() => document.querySelector('.cbx-note').textContent"
JOB = """() => { const s = document.querySelector('#modal select[name=job_id]');
    return [s.value, s.closest('.cbx').querySelector('.cbx-input').value]; }"""
TOASTS = """() => [...document.querySelectorAll('#toast-container *')]
    .map(t => t.textContent.trim()).filter(Boolean)"""

SALT = "Salt & Pine Catering Co."
HARBOR = "Harbor District Events"
GALA = f"{SALT}: Waterfront Gala"
FESTIVAL = f"{HARBOR}: Harbor Lights Festival"
NO_JOB = "— No job —"


def _ok(resp):
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


@pytest.fixture(name="jobs")
def jobs_fixture(company, books):
    """Each customer with a job of its own: Salt & Pine's Waterfront Gala
    (the books') and Harbor District Events' Harbor Lights Festival."""
    festival = _ok(
        company.post(
            "/api/jobs",
            json={"customer_id": books["customer2"], "name": "Harbor Lights Festival"},
        )
    )
    return {"gala": books["job"], "festival": festival["id"]}


def _form(browser, company, route, call):
    page, handled = _open_at(browser, company, route)
    page.evaluate(f"async () => {{ await {call}; }}")
    page.wait_for_function(MODAL_SHOWN, timeout=5000)
    settle(page, handled)
    return page, handled


def _pick(page, box, typed, name):
    """Type into a type-ahead box and take its match with Enter: the wait
    is for the match to be the top of the list and highlighted, which is
    what Enter takes (a customer list also carries "+ New Customer")."""
    box.click()
    page.keyboard.type(typed)
    page.wait_for_function(
        "(name) => { const l = document.querySelectorAll('#cbx-listbox [role=option]');"
        " return l.length > 0 && l[0].textContent.trim() === name"
        " && l[0].getAttribute('aria-selected') === 'true'; }",
        arg=name,
    )
    page.keyboard.press("Enter")


def _listed(page, box):
    """What a click on the box offers: the whole list, narrowed."""
    box.click()
    page.wait_for_function(LIST_OPEN, timeout=5000)
    shown = page.evaluate(SHOWN)
    page.keyboard.press("Escape")
    return shown


def test_the_invoice_form_offers_the_customers_jobs_and_follows_a_change(
    browser, company, books, jobs
):
    page, handled = _form(browser, company, "#/invoices", "InvoicesPage.showForm()")
    try:
        customer = page.get_by_role("combobox", name="Customer", exact=True)
        job = page.get_by_role("combobox", name="Job", exact=True)
        # no customer yet: every job
        before = _listed(page, job)
        _pick(page, customer, "harbor", HARBOR)
        # Harbor's job only, and the other customer's is not found by name
        harbor_list = _listed(page, job)
        job.click()
        page.keyboard.type("water")
        page.wait_for_function(f"({NOTE})() === 'No match'", timeout=5000)
        water = page.evaluate(SHOWN)
        page.keyboard.press("Escape")
        _pick(page, job, "lights", FESTIVAL)
        chosen = page.evaluate(JOB)
        # the customer changes: the job clears, and the list follows
        _pick(page, customer, "salt", SALT)
        page.wait_for_function(f"({JOB})()[0] === ''", timeout=5000)
        cleared = page.evaluate(JOB)
        salt_list = _listed(page, job)
        # the keyboard reaches it too: focus in the box, Down opens the
        # narrowed list
        job.focus()
        page.keyboard.press("ArrowDown")
        page.wait_for_function(LIST_OPEN, timeout=5000)
        by_keys = page.evaluate(SHOWN)
        page.keyboard.press("Escape")
        _pick(page, job, "gala", GALA)
        page.fill("#inv-lines tr .line-desc", "Tent and tables")
        page.fill("#inv-lines tr .line-rate", "250")
        page.click("#invoice-form button[type=submit]")
        page.wait_for_function(f"!({MODAL_SHOWN})()", timeout=5000)
        settle(page, handled)
    finally:
        page.close()
    assert before == [NO_JOB, FESTIVAL, GALA]  # the jobs list's own order
    assert harbor_list == [NO_JOB, FESTIVAL]
    assert water == []
    assert chosen == [str(jobs["festival"]), FESTIVAL]
    assert cleared == ["", ""]
    assert salt_list == [NO_JOB, GALA] and by_keys == [NO_JOB, GALA]
    saved = _ok(company.get(f"/api/invoices?customer_id={books['customer']}"))
    newest = max(saved, key=lambda i: i["id"])
    assert newest["job_id"] == jobs["gala"]
    assert newest["lines"][0]["description"] == "Tent and tables"


def test_the_servers_refusal_reaches_the_form(browser, company, books, jobs):
    page, handled = _form(browser, company, "#/invoices", "InvoicesPage.showForm()")
    try:
        customer = page.get_by_role("combobox", name="Customer", exact=True)
        _pick(page, customer, "harbor", HARBOR)
        # the other customer's job, set on the select behind the filter's back
        page.evaluate(
            "(id) => { document.querySelector('#modal select[name=job_id]').value = String(id); }",
            jobs["gala"],
        )
        forced = page.evaluate(JOB)
        page.fill("#inv-lines tr .line-desc", "Lanterns")
        page.fill("#inv-lines tr .line-rate", "40")
        count = len(_ok(company.get(f"/api/invoices?customer_id={books['customer2']}")))
        page.click("#invoice-form button[type=submit]")
        page.wait_for_function(f"({TOASTS})().length > 0", timeout=5000)
        toasts = page.evaluate(TOASTS)
        still_open = page.evaluate(MODAL_SHOWN)
    finally:
        page.close()
    assert forced == [str(jobs["gala"]), GALA]
    assert any(
        t == "Job Waterfront Gala belongs to a different customer than this invoice"
        " — clear the Job field or pick one of this customer's."
        for t in toasts
    ), toasts
    assert still_open, "the form stays, with what was typed"
    after = _ok(company.get(f"/api/invoices?customer_id={books['customer2']}"))
    assert len(after) == count, "nothing was saved"


def test_the_estimate_and_sales_receipt_forms_follow_the_customer_too(
    browser, company, books, jobs
):
    page, handled = _form(browser, company, "#/estimates", "EstimatesPage.showForm()")
    try:
        customer = page.get_by_role("combobox", name="Customer", exact=True)
        job = page.get_by_role("combobox", name="Job", exact=True)
        _pick(page, customer, "harbor", HARBOR)
        est_harbor = _listed(page, job)
        _pick(page, job, "lights", FESTIVAL)
        _pick(page, customer, "salt", SALT)
        page.wait_for_function(f"({JOB})()[0] === ''", timeout=5000)
        est_cleared = page.evaluate(JOB)
        est_salt = _listed(page, job)
    finally:
        page.close()
    assert est_harbor == [NO_JOB, FESTIVAL]
    assert est_cleared == ["", ""]
    assert est_salt == [NO_JOB, GALA]

    page, handled = _form(
        browser, company, "#/sales-receipts", "SalesReceiptsPage.showForm()"
    )
    try:
        customer = page.get_by_role("combobox", name="Customer", exact=True)
        job = page.get_by_role("combobox", name="Job", exact=True)
        # a blank customer is the walk-in customer, who has no jobs
        walk_in = _listed(page, job)
        _pick(page, customer, "salt", SALT)
        sr_salt = _listed(page, job)
    finally:
        page.close()
    assert walk_in == [NO_JOB]
    assert sr_salt == [NO_JOB, GALA]


def _by_job_income(company):
    r = company.get(
        "/api/reports/profit-loss-by-job?start_date=2026-09-01&end_date=2026-09-30"
        "&include_empty=true"
    )
    assert r.status_code == 200, r.text
    return {j["job_id"]: float(j["income"]) for j in r.json()["jobs"]}


def test_a_note_saves_over_an_old_mismatch_and_the_job_is_put_right(
    browser, company, books, jobs, db_session
):
    """The skeptic's case: an invoice carrying another customer's job on
    its header and on a line (the old fixture's doing). A note saved from
    the form goes through — the form sends every field, and the server
    judges only what changed, while the form drops the line's foreign job;
    then the user picks one of the customer's own jobs, and P&L by Job
    counts the invoice there."""
    inv = _ok(
        company.post(
            "/api/invoices",
            json={
                "customer_id": books["customer"],
                "date": "2026-09-20",
                "lines": [{"description": "Lanterns", "quantity": 1, "rate": 120}],
            },
        )
    )
    row = db_session.get(Invoice, inv["id"])
    row.job_id = jobs["festival"]
    row.lines[0].job_id = jobs["festival"]
    db_session.commit()
    before = _by_job_income(company)

    page, handled = _form(
        browser, company, "#/invoices", f"InvoicesPage.showForm({inv['id']})"
    )
    try:
        # a note, nothing else touched
        page.fill("#invoice-form textarea[name=notes]", "Deliver by Friday")
        page.click("#invoice-form button[type=submit]")
        page.wait_for_function(f"!({MODAL_SHOWN})()", timeout=5000)
        settle(page, handled)
        toasts_after_note = page.evaluate(TOASTS)
        saved = _ok(company.get(f"/api/invoices/{inv['id']}"))

        # then the job put right: the picker clears the foreign one on the
        # way in and offers the customer's own
        page.evaluate(f"async () => {{ await InvoicesPage.showForm({inv['id']}); }}")
        page.wait_for_function(MODAL_SHOWN, timeout=5000)
        settle(page, handled)
        job = page.get_by_role("combobox", name="Job", exact=True)
        _pick(page, job, "gala", GALA)
        page.click("#invoice-form button[type=submit]")
        page.wait_for_function(f"!({MODAL_SHOWN})()", timeout=5000)
        settle(page, handled)
        fixed = _ok(company.get(f"/api/invoices/{inv['id']}"))
    finally:
        page.close()
    assert not any(
        "belongs to a different" in t for t in toasts_after_note
    ), toasts_after_note
    assert saved["notes"] == "Deliver by Friday"
    assert saved["job_id"] == jobs["festival"], "the header's job, untouched, stays"
    assert saved["lines"][0]["job_id"] is None, "the line's foreign job is dropped"
    assert fixed["job_id"] == jobs["gala"] and fixed["lines"][0]["job_id"] is None
    after = _by_job_income(company)
    assert after[jobs["gala"]] == before.get(jobs["gala"], 0) + 120
    assert after.get(jobs["festival"], 0) == before.get(jobs["festival"], 0)
