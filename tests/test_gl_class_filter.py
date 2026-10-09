"""The General Ledger and the bank register take a class (#236, R6).

- /reports/general-ledger?class_id= keeps only that class's lines (the
  line's own class, else its transaction's, else Uncategorized — the test
  P&L by Class groups by) and computes each balance brought forward under
  the same test, so a running balance is the class's; per P&L account the
  period's net is that class's P&L column; the GL answers class_id and
  class_name; the unexposed account_id still works, alone or with a class;
  the csv and pdf take class_id, and the CSV's columns are unchanged (#179).
- /banking/check-register takes start_date, end_date and class_id: with a
  class the entries and the balance brought forward are the drill-down's
  for the same account, class and dates; `balance` stays the account's.
- The screen: the GL draws the Class column its CSV already had and the
  two pickers; the register page the date and class filters.
"""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.accounting import create_journal_entry
from tests.test_pl_by_class_detail import (
    ledger_fixture,
)  # noqa: F401  (registers the ledger fixture)

JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js"
PERIOD = {"start_date": "2026-07-01", "end_date": "2026-07-31"}
D = Decimal


def _get(client, path, **params):
    r = client.get(path, params=params)
    assert r.status_code == 200, (path, r.status_code, r.text)
    return r.json()


def _gl_account(gl, account_id):
    return next(a for a in gl["accounts"] if a["account_id"] == account_id)


def test_the_ledger_filtered_to_a_class_is_that_class_alone(client, ledger):
    gl = _get(client, "/api/reports/general-ledger", class_id=ledger["side"], **PERIOD)
    assert gl["class_id"] == ledger["side"] and gl["class_name"] == "Side Gig"
    assert gl["account_id"] is None
    accounts = {a["account_id"]: a for a in gl["accounts"]}
    assert set(accounts) == {ledger["income"], ledger["expense"], ledger["cogs"]}
    # every entry is the class's, named
    for a in gl["accounts"]:
        assert all(e["class_name"] == "Side Gig" for e in a["entries"]), a[
            "account_name"
        ]
    # the income account: 300 in the period; 40 brought forward from June,
    # the class's own (the plain GL would bring forward the same 40 here, so
    # the expense account below is the telling one)
    income = accounts[ledger["income"]]
    assert income["opening_balance"] == 40.0
    assert [e["credit"] for e in income["entries"]] == [300.0]
    assert income["closing_balance"] == 340.0
    # the retail entry's one line in Side Gig: the COGS line, not its income
    cogs = accounts[ledger["cogs"]]
    assert [(e["description"], e["debit"]) for e in cogs["entries"]] == [
        ("retail, one line in side gig", 100.0)
    ]
    assert cogs["opening_balance"] == 0.0 and cogs["closing_balance"] == 100.0


def test_the_balance_brought_forward_is_computed_under_the_class_test(
    client, db_session, seed_accounts, ledger
):
    # June, no class: 500 of expense that the plain ledger brings forward
    # and a Side Gig ledger must not
    create_journal_entry(
        db_session,
        date(2026, 6, 25),
        "june, no class",
        [
            {"account_id": ledger["expense"], "debit": D("500"), "credit": D("0")},
            {"account_id": ledger["income"], "debit": D("0"), "credit": D("500")},
        ],
    )
    db_session.commit()
    plain = _get(client, "/api/reports/general-ledger", **PERIOD)
    side = _get(
        client, "/api/reports/general-ledger", class_id=ledger["side"], **PERIOD
    )
    uncat = _get(
        client, "/api/reports/general-ledger", class_id=ledger["uncat"], **PERIOD
    )
    expense_plain = _gl_account(plain, ledger["expense"])
    expense_side = _gl_account(side, ledger["expense"])
    expense_uncat = _gl_account(uncat, ledger["expense"])
    assert expense_plain["opening_balance"] == 540.0  # 500 untagged + 40 Side Gig
    assert expense_side["opening_balance"] == 40.0
    assert expense_uncat["opening_balance"] == 500.0
    assert expense_side["closing_balance"] == 340.0
    assert expense_uncat["closing_balance"] == 550.0
    # the running balance of the last line is the closing balance
    assert expense_side["entries"][-1]["running_balance"] == 340.0
    # the classes' openings add up to the plain one, as their lines do
    assert (
        expense_side["opening_balance"] + expense_uncat["opening_balance"]
        == expense_plain["opening_balance"]
    )


def test_per_account_the_class_ledger_nets_to_its_p_and_l_column(client, ledger):
    by_class = _get(client, "/api/reports/profit-loss-by-class", **PERIOD)
    for col in by_class["classes"]:
        gl = _get(
            client, "/api/reports/general-ledger", class_id=col["class_id"], **PERIOD
        )
        for section in ("income", "cogs", "expenses"):
            for row in by_class["accounts"][section]:
                amount = row["amounts"][by_class["classes"].index(col)]
                acct = next(
                    (a for a in gl["accounts"] if a["account_id"] == row["account_id"]),
                    None,
                )
                if amount == 0:
                    assert acct is None or acct["total_debit"] == acct["total_credit"]
                    continue
                net = D(str(acct["total_debit"])) - D(str(acct["total_credit"]))
                natural = -net if section == "income" else net
                assert float(natural) == amount, (
                    col["class_name"],
                    row["account_name"],
                )


def test_account_and_class_together_and_an_unknown_class(client, ledger):
    gl = _get(
        client,
        "/api/reports/general-ledger",
        account_id=ledger["income"],
        class_id=ledger["retail"],
        **PERIOD,
    )
    assert gl["account_id"] == ledger["income"] and gl["class_name"] == "Retail"
    assert [a["account_id"] for a in gl["accounts"]] == [ledger["income"]]
    assert [e["credit"] for e in gl["accounts"][0]["entries"]] == [100.0]
    r = client.get("/api/reports/general-ledger", params={"class_id": 999999, **PERIOD})
    assert r.status_code == 404


def test_the_exports_take_the_class_and_keep_their_columns(client, ledger):
    r = client.get(
        "/api/reports/general-ledger/csv",
        params={"class_id": ledger["side"], **PERIOD},
    )
    assert r.status_code == 200, r.text
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    header = next(ln for ln in lines if ln.startswith("Date,"))
    assert header.split(",") == [
        "Date",
        "Reference",
        "Description",
        "Account number",
        "Account name",
        "Debit",
        "Credit",
        "Running balance",
        "Source type",
        "Class",
    ]
    body = [ln for ln in lines[lines.index(header) + 1 :]]
    classes = {
        ln.rsplit(",", 1)[1]
        for ln in body
        if "Balance brought forward" not in ln and "Period total" not in ln
    }
    assert classes == {"Side Gig"}
    assert "retail, one line in side gig" in r.text
    assert "no class" not in r.text
    pdf = client.get(
        "/api/reports/general-ledger/pdf",
        params={"class_id": ledger["side"], **PERIOD},
    )
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")


def test_the_register_takes_dates_and_a_class_and_agrees_with_the_drill_down(
    client, db_session, seed_accounts, ledger
):
    bank = seed_accounts["1000"]
    equity = seed_accounts["3000"]

    def je(day, what, lines, class_id=None):
        create_journal_entry(db_session, day, what, lines, class_id=class_id)

    je(
        date(2026, 6, 15),
        "side gig deposit, june",
        [
            {"account_id": bank.id, "debit": D("1000"), "credit": D("0")},
            {"account_id": equity.id, "debit": D("0"), "credit": D("1000")},
        ],
        class_id=ledger["side"],
    )
    je(
        date(2026, 6, 16),
        "untagged deposit, june",
        [
            {"account_id": bank.id, "debit": D("70"), "credit": D("0")},
            {"account_id": equity.id, "debit": D("0"), "credit": D("70")},
        ],
    )
    je(
        date(2026, 7, 5),
        "side gig spend",
        [
            {"account_id": ledger["expense"], "debit": D("200"), "credit": D("0")},
            {"account_id": bank.id, "debit": D("0"), "credit": D("200")},
        ],
        class_id=ledger["side"],
    )
    je(
        date(2026, 7, 6),
        "untagged spend",
        [
            {"account_id": ledger["expense"], "debit": D("30"), "credit": D("0")},
            {"account_id": bank.id, "debit": D("0"), "credit": D("30")},
        ],
    )
    db_session.commit()

    whole = _get(client, "/api/banking/check-register", account_id=bank.id)
    assert whole["class_id"] is None and whole["start_date"] is None
    assert len(whole["entries"]) == 4 and whole["balance"] == 840.0

    reg = _get(
        client,
        "/api/banking/check-register",
        account_id=bank.id,
        class_id=ledger["side"],
        **PERIOD,
    )
    assert reg["class_id"] == ledger["side"] and reg["class_name"] == "Side Gig"
    assert (reg["start_date"], reg["end_date"]) == (
        PERIOD["start_date"],
        PERIOD["end_date"],
    )
    assert reg["opening_balance"] == 1000.0  # the class's June deposit alone
    assert [(e["date"], e["payment"], e["balance"]) for e in reg["entries"]] == [
        ("2026-07-05", 200.0, 800.0)
    ]
    assert reg["balance"] == 840.0, "the account's whole balance, said as such"

    drill = _get(
        client,
        "/api/reports/account-transactions",
        account_id=bank.id,
        class_id=ledger["side"],
        **PERIOD,
    )
    assert drill["opening_balance"] == reg["opening_balance"]
    assert [(e["line_id"], e["running_balance"]) for e in drill["entries"]] == [
        (e["line_id"], e["balance"]) for e in reg["entries"]
    ]

    # dates alone
    dated = _get(client, "/api/banking/check-register", account_id=bank.id, **PERIOD)
    assert dated["opening_balance"] == 1070.0
    assert [e["date"] for e in dated["entries"]] == ["2026-07-05", "2026-07-06"]
    assert (
        client.get(
            "/api/banking/check-register",
            params={"account_id": bank.id, "class_id": 999999},
        ).status_code
        == 404
    )


# ── the screen ────────────────────────────────────────────────────────────


def test_the_ledger_screen_draws_the_class_column_and_the_pickers():
    js = (JS / "reports.js").read_text(encoding="utf-8")
    gl = js[js.index("\n    async generalLedger(prefill) {") :]
    gl = gl[: gl.index("\n    },")]
    assert "<th scope=\"col\">${T('Class')}</th>" in gl
    assert "${escapeHtml(e.class_name || '')}" in gl
    assert 'id="gl-account"' in gl and 'id="gl-class"' in gl
    assert '<label for="gl-account"' in gl and '<label for="gl-class"' in gl
    # the filters ride the address, the exports and a saved report
    assert "params: () => ReportsPage._gl" in gl
    assert "&class_id=${f.class_id}" in gl and "&account_id=${f.account_id}" in gl
    assert "ReportsPage._exportButtons('general-ledger', qs)" in gl
    # the drill-down from a class-filtered ledger carries the class
    assert (
        "${data.class_id || null},${JSON.stringify(cls || null)},'general-ledger'" in gl
    )
    assert re.search(r"'general-ledger':\s*\{[^\n]*keep: \['class_id'\]", js)
    # openPeriodModal reads a function's params on every render
    assert "typeof opts.params === 'function' ? null : (opts.params || {})" in js
    assert "paramsObj ? paramsObj : opts.params()" in js


def test_the_register_screen_has_date_and_class_filters():
    js = (JS / "banking.js").read_text(encoding="utf-8")
    reg = js[js.index("    async renderRegister(accountId, query) {") :]
    reg = reg[: reg.index("\n    },")]
    for ident in ("reg-start", "reg-end", "reg-class"):
        assert f'id="{ident}"' in reg and f'<label for="{ident}"' in reg, ident
    assert "/banking/check-register?account_id=${id}${filterQs}" in reg
    assert "Balance brought forward" in reg
    # the filter is replaced in place on the address, never pushed
    assert "history.replaceState(history.state, '', url)" in js
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert "render: (id, query) => BankingPage.renderRegister(id, query)" in app
