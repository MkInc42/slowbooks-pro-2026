"""Every posting in a register or drill-down links to its document (#241,
R11), and the drill-down is a report view of its own.

app/services/bank_register.py's _LINKS maps a posting's source_type to the
page that shows it; the drill-down and the bank register send that link
with each line. A job cost, a pay run, a credit memo, an in-kind gift, a
release or an allocation each had a viewer but no address, so their lines
were bare text; a posting that is its own document (a PTO accrual, a
sales-tax payment, an inventory adjustment, depreciation) opens its
journal entry. The SPA falls back to the journal entry for the rest.

The drill-down (ReportsPage.openDrillDown) sits on the period shell
(openPeriodModal): dates, a class and an account select, Previous/Next
through the report it came from, and a saved account_transactions report
that reopens. What that looks like in Chromium is
tests/test_browser_report_links.py.
"""

import re
from pathlib import Path

from app.services import bank_register

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app" / "static" / "js"


# ── the link map ─────────────────────────────────────────────────────────


def _py_sources():
    for folder in ("app/services", "app/routes"):
        for path in (ROOT / folder).rglob("*.py"):
            yield path.read_text(encoding="utf-8")


# The void postings that are not written as source_type="…" literals:
# the house void takes its type as an argument (void_document(db, txn,
# "deposit_void")), two routes keep it in a constant (VOID_SOURCE_TYPE),
# and the journal's void and the QBO import's reversals derive it from
# the voided posting's own type (f"{txn.source_type}_void"). The review
# of R11 found these had slipped past a literal-only grep, so an
# expense_void line fell back to the void posting itself.
DERIVED_VOID_BASES = ("qbo_ledger", "qbo_journal")


def _posted_source_types():
    found = set()
    derived_sites = 0
    for text in _py_sources():
        found |= set(re.findall(r'source_type\s*=\s*"([a-z_]+)"', text))
        found |= set(re.findall(r'void_document\([^)]*?"([a-z_]+)"\s*\)', text))
        found |= set(re.findall(r'VOID_SOURCE_TYPE\s*=\s*"([a-z_]+)"', text))
        derived_sites += text.count('f"{txn.source_type}_void"')
    # the derived form is still in use (journal void, QBO reversals) — if it
    # went away, so should DERIVED_VOID_BASES
    assert derived_sites >= 3, derived_sites
    found |= {f"{base}_void" for base in DERIVED_VOID_BASES}
    return found


# Every void posting links to the document it voided (its source_id is
# that posting's id); none is left to the SPA's journal-entry fallback.
NO_DOCUMENT = set()


def test_every_source_type_the_app_posts_has_a_link():
    posted = _posted_source_types()
    assert "job_cost" in posted and "restriction_release" in posted
    # the ones a literal-only grep missed (R11 review)
    assert {
        "expense_void",
        "deposit_void",
        "cc_charge_void",
        "bank_entry_void",
        "transfer_void",
        "qbo_ledger_void",
        "qbo_journal_void",
    } <= posted
    unmapped = {t for t in posted if t not in bank_register._LINKS}
    assert unmapped == NO_DOCUMENT, sorted(unmapped)


def test_the_pages_with_a_viewer_link_by_document_id_and_the_rest_by_journal():
    by_id = {k: v for k, v in bank_register._LINKS.items() if "{id}" in v}
    by_txn = {k: v for k, v in bank_register._LINKS.items() if "{txn}" in v}
    assert by_id["job_cost"] == "/#/job-costs/{id}"
    assert by_id["job_cost_void"] == "/#/job-costs/{id}"
    assert by_id["payroll"] == "/#/payroll/{id}"
    assert by_id["credit_memo"] == "/#/credit-memos/{id}"
    assert by_id["in_kind_gift"] == "/#/in-kind-gifts/{id}"
    assert by_id["restriction_release"] == "/#/releases/{id}"
    assert by_id["functional_allocation"] == "/#/functional-allocations/{id}"
    # a void links to the document it voided
    assert by_id["invoice_void"] == by_id["invoice"]
    assert by_id["bill_void"] == by_id["bill"]
    # a document addressed by its transaction id: its void (keyed by that
    # id) links to the same page
    for doc in ("expense", "deposit", "cc_charge", "transfer", "bank_entry"):
        assert by_id[f"{doc}_void"] == by_txn[doc].replace("{txn}", "{id}"), doc
    assert by_id["manual_void"] == "/#/journal/{id}"
    assert by_id["payment_apply_void"] == "/#/journal/{id}"
    for kind in (
        "pto",
        "check",
        "adjustment",
        "sales_tax_payment",
        "iif_import",
        "depreciation",
    ):
        assert by_txn[kind] == "/#/journal/{txn}", kind
    # every by-id page has a document route
    app_js = (JS / "app.js").read_text(encoding="utf-8")
    for pattern in set(by_id.values()):
        route = pattern.removeprefix("/#").replace("{id}", ":id")
        assert f"'{route}':" in app_js, route


def test_a_job_cost_a_credit_memo_and_a_void_link_to_their_pages(client, books):
    accounts = {a["account_number"]: a for a in client.get("/api/accounts").json()}
    drill = client.get(
        "/api/reports/account-transactions",
        params={
            "account_id": accounts["5000"]["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
        },
    ).json()
    [cost] = [e for e in drill["entries"] if e["source_type"] == "job_cost"]
    assert cost["source_link"] == f"/#/job-costs/{books['job_cost']}"
    ar = client.get(
        "/api/reports/account-transactions",
        params={
            "account_id": accounts["1100"]["id"],
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
    ).json()
    [memo] = [e for e in ar["entries"] if e["source_type"] == "credit_memo"]
    assert memo["source_link"] == f"/#/credit-memos/{books['memo']}"
    [void] = [e for e in ar["entries"] if e["source_type"] == "invoice_void"]
    assert void["source_link"] == f"/#/invoices/{books['void']}" and void["voided"]
    # the voided expense (entered twice, 2026-09-03): its void line opens the
    # expense, not the void posting (R11 review)
    cash = client.get(
        "/api/reports/account-transactions",
        params={
            "account_id": accounts["1000"]["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
        },
    ).json()
    [expense_void] = [e for e in cash["entries"] if e["source_type"] == "expense_void"]
    [expense] = [
        e
        for e in cash["entries"]
        if e["source_type"] == "expense"
        and e["transaction_id"] == expense_void["source_id"]
    ]
    assert expense["voided"]
    assert expense["source_link"] == f"/#/expenses/{expense['transaction_id']}"
    assert expense_void["source_link"] == expense["source_link"]
    # the register sends the same fields the drill-down now shows
    assert {"payee", "cleared", "reconciliation_id", "voided"} <= set(cost)
    assert "opening_balance" in drill and "period_debit" in drill


# ── the drill-down is a view on the period shell ─────────────────────────


def _method(src, signature):
    body = src[src.index(f"\n    {signature} {{") :]
    return body[: body.index("\n    },")]


def test_the_drill_down_opens_through_the_period_shell_and_can_be_saved():
    src = (JS / "reports.js").read_text(encoding="utf-8")
    drill = _method(
        src,
        "async openDrillDown(accountId, accountName, startDate, endDate, "
        "classId = null, className = null, from = null, extra = {})",
    )
    assert "ReportsPage.openPeriodModal(" in drill
    assert "reportType: 'account_transactions', view: 'account-transactions'" in drill
    assert "params, toolbar, actions: backBtn, wide: true" in drill
    assert "prefill: { period, start_date: startDate, end_date: endDate }" in drill
    # the address: account, dates, class, the way back — the period preset
    # rides through the registry
    assert "p.from || null, { job_id: p.job_id, period: p.period || null })" in src
    # what the register sends is on the screen
    for shown in (
        "e.payee",
        "e.cleared",
        "e.voided",
        "e.reconciliation_id",
        "data.opening_balance",
        "Balance brought forward",
    ):
        assert shown in drill, shown
    # a line with no document opens its journal entry, as the register does
    assert "`/#/journal/${e.transaction_id}`" in drill
    # the selects and the steps
    assert 'id="drill-class"' in drill and 'id="drill-account"' in drill
    assert (
        'aria-label="Previous account"' in drill
        and 'aria-label="Next account"' in drill
    )
    assert "ReportsPage._drillStep(" in drill


def test_the_shell_takes_a_toolbar_and_actions_and_saves_the_params():
    src = (JS / "reports.js").read_text(encoding="utf-8")
    shell = _method(
        src,
        'async openPeriodModal(title, initialPeriod, loadContent, label = "Dates", useAsOfOnly = false, opts = {})',
    )
    assert "${opts.toolbar || ''}" in shell
    assert "${opts.actions || ''}" in shell
    assert "{ wide: !!opts.wide }" in shell
    assert (
        "ReportsPage.saveCurrent(reportType, { ...params(), ...currentParams })"
        in shell
    )


def test_a_saved_drill_down_is_an_allowed_type():
    from app.routes.saved_reports import _ALLOWED_TYPES

    assert "account_transactions" in _ALLOWED_TYPES
