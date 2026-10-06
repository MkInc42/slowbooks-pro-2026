"""#179: the trial balance and general ledger save as a spreadsheet and a
printable file; P&L and balance sheet gain the spreadsheet. The figures in
the files are the figures on the screen, and the general ledger ties to the
trial balance account by account."""

from decimal import Decimal

import pytest

from app.services.ledger_exports import rows_of

PERIOD = "start_date=2026-01-01&end_date=2026-12-31"


def _je(client, accts, when, dr, cr, amount, ref):
    r = client.post(
        "/api/journal",
        json={
            "date": when,
            "description": f"entry {ref}",
            "reference": ref,
            "lines": [
                {"account_id": accts[dr].id, "debit": amount},
                {"account_id": accts[cr].id, "credit": amount},
            ],
        },
    )
    assert r.status_code == 201, r.text


@pytest.fixture
def books(client, seed_accounts):
    # one entry before the period (a balance brought forward), three inside it
    _je(client, seed_accounts, "2025-12-15", "1000", "4000", "500.00", "PRIOR-1")
    _je(client, seed_accounts, "2026-02-01", "1000", "4000", "1200.00", "JE-1")
    _je(client, seed_accounts, "2026-03-05", "6000", "1000", "300.00", "JE-2")
    _je(client, seed_accounts, "2026-03-05", "6000", "1000", "45.50", "JE-3")
    return seed_accounts


def test_trial_balance_csv_matches_the_screen_to_the_cent(client, books):
    screen = client.get(f"/api/reports/trial-balance?{PERIOD}").json()
    r = client.get(f"/api/reports/trial-balance/csv?{PERIOD}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    head = r.text.splitlines()[:3]
    assert (
        head[1].startswith("Report,Trial Balance")
        and "2026-01-01 to 2026-12-31" in head[2]
    )
    rows = rows_of(r.text)
    assert rows[0] == [
        "Account number",
        "Account name",
        "Type",
        "Debit",
        "Credit",
        "Net",
    ]
    body, total = rows[1:-1], rows[-1]
    assert len(body) == len(screen["items"])
    by_num = {row[0]: row for row in body}
    for item in screen["items"]:
        row = by_num[item["account_number"]]
        assert Decimal(row[3]) == Decimal(str(item["total_debit"])).quantize(
            Decimal("0.01")
        )
        assert Decimal(row[5]) == Decimal(str(item["net_balance"])).quantize(
            Decimal("0.01")
        )
    assert total[1] == "Total" and total[3] == total[4]  # debit equals credit
    assert Decimal(total[3]) == Decimal("1545.50")


def test_general_ledger_carries_every_line_and_ties_to_the_trial_balance(client, books):
    gl = client.get(f"/api/reports/general-ledger?{PERIOD}").json()
    tb = client.get(f"/api/reports/trial-balance?{PERIOD}").json()
    tb_net = {i["account_number"]: Decimal(str(i["net_balance"])) for i in tb["items"]}
    cash = next(a for a in gl["accounts"] if a["account_number"] == "1000")
    # balance brought forward from 2025, running balance after each line
    assert Decimal(str(cash["opening_balance"])) == Decimal("500.00")
    assert [e["running_balance"] for e in cash["entries"]] == [1700.0, 1400.0, 1354.5]
    assert all(e["source_type"] for e in cash["entries"])
    # a credit-normal account reads in its own sign, as the balance sheet and
    # the overview show it: income of 500 brought forward, 1,700 after JE-1
    sales = next(a for a in gl["accounts"] if a["account_number"] == "4000")
    assert sales["normal_balance"] == "credit" and cash["normal_balance"] == "debit"
    assert Decimal(str(sales["opening_balance"])) == Decimal("500.00")
    assert [e["running_balance"] for e in sales["entries"]] == [1700.0]
    assert sales["closing_balance"] == 1700.0

    rows = rows_of(client.get(f"/api/reports/general-ledger/csv?{PERIOD}").text)
    assert rows[0][:3] == ["Date", "Reference", "Description"] and rows[0][-3:] == [
        "Running balance",
        "Source type",
        "Class",  # last, so a sheet reading by position still lines up (#213)
    ]
    kind = rows[0].index("Source type")
    lines = [r for r in rows[1:] if r[kind] not in ("opening", "total")]
    assert (
        len(lines) == 6
    )  # three in-period entries, two lines each; PRIOR-1 is not in the period
    assert all(r[-1] == "Uncategorized" for r in lines)  # nothing here has a class
    for r in (r for r in rows[1:] if r[kind] == "total"):
        num, dr, cr = r[3], Decimal(r[5]), Decimal(r[6])
        assert dr - cr == tb_net[num], num  # the period net equals the TB's Net
    opening = {r[3]: Decimal(r[7]) for r in rows[1:] if r[kind] == "opening"}
    closing = {r[3]: Decimal(r[7]) for r in rows[1:] if r[kind] == "total"}
    sign = {
        a["account_number"]: 1 if a["normal_balance"] == "debit" else -1
        for a in gl["accounts"]
    }
    for num in closing:
        assert closing[num] == opening[num] + sign[num] * tb_net[num], num
    assert closing["4000"] == Decimal("1700.00")  # positive: income earned, not -1,700


def test_profit_loss_and_balance_sheet_save_as_spreadsheets(client, books):
    pl = rows_of(client.get(f"/api/reports/profit-loss/csv?{PERIOD}").text)
    assert pl[0] == ["Section", "Account number", "Account name", "Amount"]
    net = next(r for r in pl if r[2] in ("Net Income", "Change in Net Assets"))
    screen = client.get(f"/api/reports/profit-loss?{PERIOD}").json()
    assert Decimal(net[3]) == Decimal(str(screen["net_income"])).quantize(
        Decimal("0.01")
    )
    bs = rows_of(
        client.get("/api/reports/balance-sheet/csv?as_of_date=2026-12-31").text
    )
    assert bs[0] == ["Section", "Account number", "Account name", "Amount"]
    assert any(r[2] == "Total Assets" for r in bs)


def test_the_desktop_shell_gets_the_file_inline(client, books):
    r = client.get(
        f"/api/reports/trial-balance/csv?{PERIOD}", headers={"X-Slowbooks-Desktop": "1"}
    )
    assert r.headers["content-disposition"].startswith("inline")
    r = client.get(f"/api/reports/trial-balance/csv?{PERIOD}")
    assert r.headers["content-disposition"].startswith("attachment")


def test_negative_amounts_stay_numbers_and_text_stays_guarded(
    client, books, db_session
):
    # A formula-shaped account name is neutralised; a negative amount is not
    # (an apostrophe would turn it into text and break every sum in the sheet).
    books["6000"].name = "=HYPERLINK(1)"
    db_session.commit()
    text = client.get(f"/api/reports/general-ledger/csv?{PERIOD}").text
    assert "'=HYPERLINK(1)" in text
    assert "'-" not in text
    running = [r[7] for r in rows_of(text) if r[1] == "JE-3"]
    assert running and all(Decimal(v) for v in running)
    net = {
        r[1]: r[5]
        for r in rows_of(client.get(f"/api/reports/trial-balance/csv?{PERIOD}").text)
    }
    assert any(v.startswith("-") for v in net.values())


def test_exporting_writes_nothing(client, books, db_session):
    from app.models.transactions import Transaction

    before = db_session.query(Transaction).count()
    for path in ("trial-balance/csv", "general-ledger/csv", "profit-loss/csv"):
        assert client.get(f"/api/reports/{path}?{PERIOD}").status_code == 200
    db_session.expire_all()
    assert db_session.query(Transaction).count() == before


def test_printable_trial_balance_and_ledger(client, books):
    pytest.importorskip("weasyprint")
    for path in ("trial-balance/pdf", "general-ledger/pdf"):
        r = client.get(f"/api/reports/{path}?{PERIOD}")
        assert r.status_code == 200, path
        assert r.content[:4] == b"%PDF", path


def test_the_report_page_offers_both_buttons_on_all_four():
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "app/static/js/reports.js").read_text(
        encoding="utf-8"
    )
    for path in ("trial-balance", "general-ledger", "profit-loss", "balance-sheet"):
        assert f"ReportsPage._exportButtons('{path}'" in js, path
