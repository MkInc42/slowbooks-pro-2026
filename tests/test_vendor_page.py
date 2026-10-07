"""A vendor's own page, like a customer's (#223).

Clicking a vendor in the Vendors list did nothing: a vendor row had no
click at all, only Edit, while a customer row opened the customer's page.
Now a vendor row opens the vendor's page: contact, address, terms, the
default account, 1099, notes, what's owed, the last ten bills and payments,
and credits not yet applied. The page reads only what already exists
(`/api/vendors/{id}`, `/api/bills?vendor_id=`, `/api/bill-payments?vendor_id=`,
`/api/vendor-credits?vendor_id=`): no new route, no schema change.

The page's source is pinned here; the browser tests at the end open it on
the shared books (tests/test_theme_contrast.py) and skip where playwright or
its Chromium is not installed.
"""

import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.contacts import Vendor

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app" / "static" / "js"
VENDORS = (JS / "vendors.js").read_text(encoding="utf-8")


def _method(js, signature):
    body = js[js.index(f"\n    {signature} {{") :]
    return body[: body.index("\n    },")]


# ── the page's source, as the customer's is pinned ────────────────────────


def test_a_vendor_row_opens_the_page_and_its_buttons_keep_to_themselves():
    page = _method(VENDORS, "async render()")
    row = re.search(r"<tr class=\"clickable vendor-row[^\n]*", page).group(0)
    assert 'onclick="VendorsPage.showDetails(${v.id})"' in row
    # the row's Edit used to be the only way in; it still edits, and the
    # click doesn't fall through to the row
    assert "event.stopPropagation(); VendorsPage.showForm(${v.id})" in page
    # #210's Make Inactive / Make Active stops propagation in its own markup
    assert "ActiveLists.buttonHtml('vendors', v)" in page


def test_the_page_reads_what_exists_and_shows_the_whole_vendor():
    details = _method(VENDORS, "async showDetails(id)")
    for call in (
        "API.get(`/vendors/${id}`)",
        "fetchAllPages(`/bills?vendor_id=${id}`)",
        "API.get(`/bill-payments?vendor_id=${id}`)",
        "API.get(`/vendor-credits?vendor_id=${id}`)",
    ):
        assert call in details, call
    for shown in (
        "vendor.terms",
        "vendor.is_1099_vendor",
        "vendor.tax_id",
        "vendor.default_expense_account_id",
        "vendor.is_active === false",
        "vendor.balance",
        "b.balance_due",
        "BillsPage.view(${b.id})",
        "BillsPage.viewPayment(${p.id})",
        "VendorCreditsPage.view(${c.id})",
        'onclick="VendorsPage.showForm(${id})">Edit',
    ):
        assert shown in details, shown
    # what a read-only sign-in can't do is marked, as on the customer page
    assert 'data-write onclick="closeModal();BillsPage.showForm()"' in details
    assert 'data-write onclick="closeModal();BillsPage.showPayForm()"' in details
    assert 'data-write aria-label="Notes"' in details
    # the notes save the way the customer's do
    notes = _method(VENDORS, "async _saveNotes(id, value)")
    assert "API.put(`/vendors/${id}`, { notes: value })" in notes


# ── the API the page reads: the balance it shows is the list's ────────────


def test_the_page_s_sources_agree_on_what_is_owed(client, db_session, seed_accounts):
    v = Vendor(name="Cascade Flour Mill", is_active=True)
    db_session.add(v)
    db_session.commit()
    expense = seed_accounts["6000"].id

    def bill(number, amount):
        r = client.post(
            "/api/bills",
            json={
                "vendor_id": v.id,
                "bill_number": number,
                "date": "2026-09-01",
                "lines": [{"account_id": expense, "description": "x", "rate": amount}],
            },
        )
        assert r.status_code == 201, r.text
        return r.json()

    bill("B-1", 500)
    b2 = bill("B-2", 90)
    r = client.post(
        "/api/bill-payments",
        json={
            "vendor_id": v.id,
            "date": "2026-09-05",
            "amount": 60,
            "pay_from_account_id": seed_accounts["1000"].id,
            "allocations": [{"bill_id": b2["id"], "amount": 40}],
        },
    )
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/vendor-credits",
        json={
            "vendor_id": v.id,
            "date": "2026-09-06",
            "lines": [{"account_id": expense, "description": "short", "rate": 10}],
        },
    )
    assert r.status_code == 201, r.text

    # the four calls the page makes, with the vendor filter each one takes
    page = client.get(f"/api/vendors/{v.id}").json()
    bills = client.get(f"/api/bills?vendor_id={v.id}&skip=0&limit=1000").json()
    payments = client.get(f"/api/bill-payments?vendor_id={v.id}").json()
    credits = client.get(f"/api/vendor-credits?vendor_id={v.id}").json()
    assert {b["bill_number"] for b in bills} == {"B-1", "B-2"}
    assert [p["amount"] for p in payments] == [60.0] or [
        Decimal(str(p["amount"])) for p in payments
    ] == [Decimal("60")]
    assert len(credits) == 1 and Decimal(
        str(credits[0]["balance_remaining"])
    ) == Decimal("10")
    # 500 + 50 − 20 unapplied − 10 credit: the list's figure and the page's
    listed = {x["id"]: x for x in client.get("/api/vendors").json()}[v.id]
    assert (
        Decimal(str(page["balance"]))
        == Decimal("520")
        == Decimal(str(listed["balance"]))
    )
    # and the notes the page saves inline land on the vendor
    assert (
        client.put(f"/api/vendors/{v.id}", json={"notes": "Pays late."}).status_code
        == 200
    )
    assert client.get(f"/api/vendors/{v.id}").json()["notes"] == "Pays late."


# ── in a browser, on the shared books ──────────────────────────────────────

sync_api = pytest.importorskip("playwright.sync_api")

from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    _open,
    _visit,
    books_fixture,
    browser_fixture,
    company_fixture,
    settle,
)

OPEN = "() => !document.getElementById('modal-overlay').classList.contains('hidden')"


def _start(browser, company):
    page, handled = _open(browser, company)
    # the start-up splash sits over the page until it's dismissed
    page.evaluate(
        "() => { const s = document.getElementById('splash'); if (s) s.classList.add('hidden'); }"
    )
    return page, handled


def test_clicking_a_vendor_row_opens_its_page(browser, company, books):
    page, handled = _start(browser, company)
    try:
        _visit(page, handled, "#/vendors")
        row = page.locator("#page-content tr.vendor-row", has_text="Cascade Flour Mill")
        listed = row.locator("td.amount").first.inner_text()
        row.locator("td").first.click()
        page.wait_for_function(OPEN, timeout=5000)
        settle(page, handled)
        title = page.inner_text("#modal-title")
        assert title == "Vendor — Cascade Flour Mill", title
        # headings are drawn in capitals (text-transform), so compare folded
        body = page.inner_text("#modal-body")
        folded = body.casefold()
        # the balance the page shows is the one the list shows
        assert listed in body, (listed, body[:300])
        # the books' bill, and the credit not yet applied to it: the balance
        # owed is the bill less that credit, as the list shows it
        assert "CFM-0918" in body and "recent bills (1)" in folded
        assert "credits not applied yet ($38.50)" in folded
        # View on a bill opens the bill, from the page
        page.click("#modal-body tr:has-text('CFM-0918')")
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent.includes('CFM-0918')",
            timeout=5000,
        )
        page.evaluate("() => closeModal()")
        # the row's Edit still edits, without opening the page
        _visit(page, handled, "#/vendors")
        row.locator("button", has_text="Edit").click()
        page.wait_for_function(OPEN, timeout=5000)
        assert page.inner_text("#modal-title") == "Edit Vendor"
        page.evaluate("() => closeModal()")
    finally:
        page.close()


def test_the_page_s_edit_opens_the_form_and_the_notes_save(browser, company, books):
    page, handled = _start(browser, company)
    try:
        _visit(page, handled, "#/vendors")
        page.evaluate(
            f"async () => {{ await VendorsPage.showDetails({books['vendor']}); }}"
        )
        page.wait_for_function(OPEN, timeout=5000)
        settle(page, handled)
        notes = page.locator(f"#vend-notes-{books['vendor']}")
        notes.fill("Delivers Tuesdays.")
        notes.evaluate("el => el.blur()")
        settle(page, handled)
        assert (
            page.inner_text(f"#vend-note-status-{books['vendor']}").strip() == "✓ saved"
        )
        page.click("#modal-body button:has-text('Edit')")
        page.wait_for_function(
            "() => document.getElementById('modal-title').textContent === 'Edit Vendor'",
            timeout=5000,
        )
        assert page.input_value("#vendor-form [name=notes]") == "Delivers Tuesdays."
    finally:
        page.close()
