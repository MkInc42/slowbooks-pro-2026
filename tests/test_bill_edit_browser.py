"""Editing a bill from the screen (#225): Edit on the row opens the form
filled from the bill, and Save Changes puts the new total in the list.

Reuses the contrast sweep's books and harness (tests/test_theme_contrast.py).
Skipped, as one module, where playwright or its Chromium is not installed.
"""

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_dialog_contrast import OPEN  # noqa: E402
from tests.test_readonly_browser import _reader, _signed_in  # noqa: E402
from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    _open,
    _visit,
    books_fixture,
    browser_fixture,
    company_fixture,
    settle,
)


def test_edit_opens_the_bill_filled_in_and_save_changes_the_total(
    browser, company, books, client
):
    bill = client.get(f"/api/bills/{books['bill']}").json()
    page, handled = _open(browser, company)
    try:
        _visit(page, handled, "#/bills")
        row = page.locator(
            f"#page-content tbody tr:has-text('{bill['bill_number']}')"
        ).first
        assert row.locator("button:has-text('Edit')").count() == 1
        page.evaluate(f"async () => {{ await BillsPage.showForm({bill['id']}); }}")
        page.wait_for_function(OPEN, timeout=5000)
        settle(page, handled)
        filled = page.evaluate("""() => ({
                title: document.getElementById('modal-title').textContent,
                vendor: document.getElementById('bill-vendor').value,
                number: document.querySelector('#bill-form [name=bill_number]').value,
                date: document.querySelector('#bill-form [name=date]').value,
                lines: [...document.querySelectorAll('#bill-lines tr')].map(r => [
                    r.querySelector('.line-desc').value,
                    r.querySelector('.line-account').value,
                    r.querySelector('.line-qty').value,
                    r.querySelector('.line-rate').value,
                ]),
                total: document.getElementById('bill-total').textContent,
                button: document.querySelector('#bill-form button[type=submit]').textContent,
            })""")
        assert filled["title"] == f"Edit Bill {bill['bill_number']}"
        assert filled["vendor"] == str(bill["vendor_id"])
        assert (
            filled["number"] == bill["bill_number"] and filled["date"] == bill["date"]
        )
        assert len(filled["lines"]) == len(bill["lines"])
        for shown, stored in zip(filled["lines"], bill["lines"]):
            assert shown[0] == (stored["description"] or "")
            assert shown[1] == str(stored["account_id"] or "")
            assert float(shown[2]) == float(stored["quantity"])
            assert float(shown[3]) == float(stored["rate"])
        assert filled["button"] == "Save Changes"

        # change the first line's rate and save
        page.fill("#bill-lines tr .line-rate", "999")
        page.evaluate("() => BillsPage.recalc()")
        # the start-up splash sits over the page in this harness, so submit
        # the form as the button would (the dialog tests do the same)
        page.evaluate("() => document.getElementById('bill-form').requestSubmit()")
        settle(page, handled)
        page.wait_for_function(f"() => !({OPEN})()", timeout=5000)
        settle(page, handled)
        after = client.get(f"/api/bills/{bill['id']}").json()
        assert float(after["lines"][0]["rate"]) == 999.0
        assert after["total"] != bill["total"]
        shown_total = (
            page.locator(f"#page-content tbody tr:has-text('{bill['bill_number']}') td")
            .nth(5)
            .inner_text()
        )
        assert (
            shown_total.replace("$", "").replace(",", "")
            == f"{float(after['total']):.2f}"
        )
    finally:
        page.close()


def test_a_read_only_sign_in_sees_no_edit_on_a_bill(
    browser, company, db_session, books
):
    # a real read-only user, signed in on a client of its own, as the
    # read-only sweep does it: the role arrives with /api/auth/status
    reader = _reader(company, db_session)
    page, handled = _signed_in(browser, reader, "readonly")
    try:
        _visit(page, handled, "#/bills")
        shown = page.evaluate(
            """() => [...document.querySelectorAll('#page-content tbody tr button')]
                .filter(b => b.offsetParent !== null).map(b => b.textContent.trim())"""
        )
        assert "Edit" not in shown and "View" in shown, shown
    finally:
        page.close()
