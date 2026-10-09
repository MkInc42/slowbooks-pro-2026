"""P&L by Class saves as CSV and PDF, is a saved-report type, and the P&L
exports honour class_id (R2, #232); the grid chooses its columns (R3,
#233); P&L by Job is the same grid by job, with a job_id on the drill-down
(R13, #242). v2.22.0.

The ledger is tests/test_pl_by_class_detail.py's: Side Gig (300 income,
300 expense, 100 COGS on a line), Retail (100 income), untagged (50 and
50), and 40 of Side Gig income the month before.
"""

from datetime import date
from decimal import Decimal

from app.services.accounting import create_journal_entry
from app.services.ledger_exports import rows_of
from tests.test_pl_by_class_detail import PERIOD, ledger_fixture  # noqa: F401

D = Decimal


def _by_class(client, extra=""):
    r = client.get(f"/api/reports/profit-loss-by-class?{PERIOD}{extra}")
    assert r.status_code == 200, r.text
    return r.json()


def _csv_rows(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    return rows_of(r.text.lstrip("﻿")), r


# ── R2: the by-class grid saves as a spreadsheet and a PDF ───────────────


def test_the_by_class_csv_is_the_grid_and_its_columns_tie_to_the_plain_p_and_l(
    client, ledger
):
    data = _by_class(client)
    rows, r = _csv_rows(client, f"/api/reports/profit-loss-by-class/csv?{PERIOD}")
    assert r.headers["content-disposition"].endswith(
        "p-l-by-class_2026-07-01_2026-07-31.csv"
    )
    header = rows[0]
    classes = [c["class_name"] for c in data["classes"]]
    assert header == ["Section", "Account number", "Account name"] + classes + ["Total"]
    assert classes[0] == "Uncategorized"

    by_name = {r[2]: r for r in rows[1:]}
    # an account row: one amount per class, and the account's total
    income = by_name["Service Income"]
    at = {name: 3 + i for i, name in enumerate(classes)}
    assert income[0] == "Income"
    assert income[at["Side Gig"]] == "300.00"
    assert income[at["Retail"]] == "100.00"
    assert income[at["Uncategorized"]] == "50.00"
    assert income[-1] == "450.00"
    # an empty cell stays empty, not 0.00
    cogs = by_name["Subcontractor Costs"]
    assert cogs[at["Retail"]] == "" and cogs[at["Side Gig"]] == "100.00"
    # the subtotal rows, section named so a filter keeps them
    assert by_name["Total Income"][0] == "Income"
    assert by_name["Gross Profit"][0] == "Cost of Goods Sold"
    assert by_name["Total Expenses"][0] == "Expenses"
    net = by_name["Net Income"]
    # 450 income, 100 COGS, 350 expenses: nothing left
    assert net[0] == "" and net[-1] == "0.00"
    assert net[at["Side Gig"]] == "-100.00" and net[at["Retail"]] == "100.00"

    # the Net Income row's columns sum to the plain P&L
    plain = client.get(f"/api/reports/profit-loss?{PERIOD}").json()
    assert sum(D(x) for x in net[3:-1]) == D(net[-1]) == D(str(plain["net_income"]))
    assert sum(D(x) for x in by_name["Total Income"][3:-1]) == D(
        str(plain["total_income"])
    )


def test_the_long_layout_is_one_row_per_account_and_class(client, ledger):
    rows, _ = _csv_rows(
        client, f"/api/reports/profit-loss-by-class/csv?{PERIOD}&layout=long"
    )
    assert rows[0] == ["Section", "Account number", "Account name", "Class", "Amount"]
    cells = {(r[2], r[3]): r[4] for r in rows[1:]}
    assert cells[("Service Income", "Side Gig")] == "300.00"
    assert cells[("Service Income", "Retail")] == "100.00"
    assert cells[("Subcontractor Costs", "Side Gig")] == "100.00"
    assert ("Subcontractor Costs", "Retail") not in cells, "no row for nothing"
    assert cells[("Net Income", "Side Gig")] == "-100.00"
    assert cells[("Net Income", "Total")] == "0.00"
    # every amount in the long form adds up to the plain P&L's net income
    accounts = [r for r in rows[1:] if r[2] != "Net Income"]
    signed = sum((D(r[4]) if r[0] == "Income" else -D(r[4])) for r in accounts)
    assert signed == D("0.00")


def test_the_by_class_pdf_is_landscape_and_pages_past_eight_classes(
    client, ledger, db_session, seed_accounts
):
    from app.routes.reports.financial import GRID_COLUMNS_PER_PAGE, _grid_sections
    from app.services.terminology import Terms

    r = client.get(f"/api/reports/profit-loss-by-class/pdf?{PERIOD}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert "p-l-by-class_2026-07-01_2026-07-31.pdf" in r.headers["content-disposition"]

    # three classes: one page, every column and the Total
    data = _by_class(client)
    columns = [dict(c, name=c["class_name"]) for c in data["classes"]]
    sections = _grid_sections(data, "P&L by Class", columns, Terms())
    assert len(sections) == 1
    assert sections[0]["columns"] == ["Account"] + [
        c["class_name"] for c in data["classes"]
    ] + ["Total"]
    net = next(r for r in sections[0]["rows"] if r["cells"][0] == "Net Income")
    assert net["cells"][-1] == "$0.00" and net["style"] == "grand-total"

    # twelve classes: two pages, each with Account and the same Total
    income, expense = seed_accounts["4000"], seed_accounts["6000"]
    for n in range(9):
        cls = client.post("/api/classes", json={"name": f"Division {n:02d}"}).json()
        create_journal_entry(
            db_session,
            date(2026, 7, 20),
            f"division {n}",
            [
                {"account_id": expense.id, "debit": D("10"), "credit": D("0")},
                {"account_id": income.id, "debit": D("0"), "credit": D("10")},
            ],
            class_id=cls["id"],
        )
    db_session.commit()
    data = _by_class(client)
    assert len(data["classes"]) == 12
    columns = [dict(c, name=c["class_name"]) for c in data["classes"]]
    sections = _grid_sections(data, "P&L by Class", columns, Terms())
    assert len(sections) == 2
    assert len(sections[0]["columns"]) == GRID_COLUMNS_PER_PAGE + 2
    assert len(sections[1]["columns"]) == 12 - GRID_COLUMNS_PER_PAGE + 2
    assert "columns 1–8 of 12" in sections[0]["period"]
    assert "columns 9–12 of 12" in sections[1]["period"]
    nets = [
        next(r for r in s["rows"] if r["cells"][0] == "Net Income")["cells"][-1]
        for s in sections
    ]
    assert nets == ["$0.00", "$0.00"], "the Total column is the same on each page"
    # and it renders, on both paper sizes
    from app.services.settings_service import set_setting

    for size in ("letter", "a4"):
        set_setting(db_session, "pdf_paper_size", size)
        db_session.commit()
        r = client.get(f"/api/reports/profit-loss-by-class/pdf?{PERIOD}")
        assert r.status_code == 200 and r.content[:5] == b"%PDF-"


def test_the_landscape_flag_turns_the_page(client, ledger, db_session):
    from app.services.pdf_service import _render

    for landscape in (False, True):
        html = _render(
            "report_pdf.html",
            {"company_name": "Bakery"},
            sections=[],
            paper_size="letter",
            landscape=landscape,
            generated_on="2026-07-31",
        )
        assert ("size: letter landscape;" in html) is landscape
        assert ("size: letter;" in html) is not landscape


def test_the_p_and_l_exports_honour_class_id(client, ledger):
    side = ledger["side"]
    rows, r = _csv_rows(
        client, f"/api/reports/profit-loss/csv?{PERIOD}&class_id={side}"
    )
    assert r.headers["content-disposition"].endswith(
        "profit-loss_side-gig_2026-07-01_2026-07-31.csv"
    )
    by_name = {row[2]: row for row in rows[1:]}
    assert by_name["Service Income"][3] == "300.00", "this class only"
    assert by_name["Net Income"][3] == "-100.00"
    # the preamble says which class
    whole = client.get(f"/api/reports/profit-loss/csv?{PERIOD}&class_id={side}").text
    assert "Profit & Loss — Class: Side Gig" in whole

    r = client.get(f"/api/reports/profit-loss/pdf?{PERIOD}&class_id={side}")
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    assert "profit-loss_side-gig_" in r.headers["content-disposition"]

    # without it, the company's, as before
    rows, r = _csv_rows(client, f"/api/reports/profit-loss/csv?{PERIOD}")
    assert {row[2]: row for row in rows[1:]}["Net Income"][3] == "0.00"
    assert r.headers["content-disposition"].endswith(
        "profit-loss_2026-07-01_2026-07-31.csv"
    )
    # an unknown class is a 404 on the exports too
    assert (
        client.get(f"/api/reports/profit-loss/csv?{PERIOD}&class_id=9999").status_code
        == 404
    )
    assert (
        client.get(f"/api/reports/profit-loss/pdf?{PERIOD}&class_id=9999").status_code
        == 404
    )


def test_the_by_class_grid_and_a_class_p_and_l_are_saved_report_types(client, ledger):
    for report_type, params in (
        (
            "profit_loss_by_class",
            {"period": "custom", "start_date": "2026-07-01", "end_date": "2026-07-31"},
        ),
        (
            "profit_loss_class",
            {
                "class_id": ledger["side"],
                "period": "last_month",
                "start_date": "2026-07-01",
                "end_date": "2026-07-31",
            },
        ),
    ):
        r = client.post(
            "/api/saved-reports",
            json={
                "name": f"Division {report_type}",
                "report_type": report_type,
                "parameters": params,
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["parameters"] == params


def test_the_report_page_offers_export_and_save_on_the_grid():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "app/static/js/reports.js").read_text(
        encoding="utf-8"
    )
    assert "_exportButtons('profit-loss-by-class'" in src
    assert "reportType: 'profit_loss_by_class'" in src
    assert "reportType: 'profit_loss_class'" in src
    assert (
        "_exportButtons('profit-loss', qs)" in src
    ), "the class P&L exports with its class_id"


# ── R3: choose the columns ───────────────────────────────────────────────


def test_a_subset_of_classes_is_filtered_and_its_total_is_the_columns_shown(
    client, ledger
):
    whole = _by_class(client)
    assert whole["filtered"] is False
    assert whole["columns_total"] == 3
    assert whole["unfiltered"]["net_income"] == whole["total_net_income"]

    side, retail = ledger["side"], ledger["retail"]
    part = _by_class(client, f"&class_ids={side},{retail}")
    assert [c["class_name"] for c in part["classes"]] == ["Retail", "Side Gig"]
    assert part["filtered"] is True
    assert part["columns_total"] == 3, "three classes have activity"
    # the filtered total is the sum of the columns shown, not the company's
    assert part["total_net_income"] == sum(c["net_income"] for c in part["classes"])
    assert part["total_net_income"] == -100.0 + 100.0
    assert part["total_income"] == 400.0
    # and the company's figure rides along so the view can say so
    assert part["unfiltered"]["net_income"] == whole["total_net_income"] == 0.0
    assert part["unfiltered"]["income"] == 450.0
    assert part["filter"] == {
        "show": "all",
        "class_ids": sorted([side, retail]),
        "include_empty": False,
    }
    # an account with nothing in the columns shown is left out: the
    # untagged-only accounts stay, as Side Gig and Retail use them too
    assert {r["account_name"] for r in part["accounts"]["income"]} == {"Service Income"}
    # the repeated form means the same
    again = _by_class(client, f"&class_ids={side}&class_ids={retail}")
    assert again["classes"] == part["classes"]
    # one chosen class is one column, with zeros for what it has none of
    one = _by_class(client, f"&class_ids={retail}")
    assert [c["class_name"] for c in one["classes"]] == ["Retail"]
    assert one["accounts"]["cogs"] == [] and one["total_cogs"] == 0.0
    assert one["total_net_income"] == 100.0 and one["filtered"] is True

    # the exports carry the choice
    rows, _ = _csv_rows(
        client,
        f"/api/reports/profit-loss-by-class/csv?{PERIOD}&class_ids={side},{retail}",
    )
    assert rows[0] == [
        "Section",
        "Account number",
        "Account name",
        "Retail",
        "Side Gig",
        "Total (shown)",
    ]
    assert {r[2]: r for r in rows[1:]}["Net Income"][-1] == "0.00"
    text = client.get(
        f"/api/reports/profit-loss-by-class/csv?{PERIOD}&class_ids={side},{retail}"
    ).text
    assert "filtered: 2 of 3 shown; totals are for the columns shown" in text
    r = client.get(
        f"/api/reports/profit-loss-by-class/pdf?{PERIOD}&class_ids={side},{retail}"
    )
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"

    # nonsense is refused, not quietly dropped
    assert (
        client.get(
            f"/api/reports/profit-loss-by-class?{PERIOD}&class_ids=x"
        ).status_code
        == 400
    )
    assert (
        client.get(f"/api/reports/profit-loss-by-class?{PERIOD}&show=some").status_code
        == 400
    )


def test_an_archived_class_with_history_shows_under_all_and_hides_under_active(
    client, ledger
):
    retail = ledger["retail"]
    assert (
        client.put(f"/api/classes/{retail}", json={"is_archived": True}).status_code
        == 200
    )
    everything = _by_class(client)
    names = {c["class_name"]: c for c in everything["classes"]}
    assert "Retail" in names and names["Retail"]["archived"] is True
    assert everything["filtered"] is False
    assert everything["total_net_income"] == 0.0, "still the plain P&L"

    active = _by_class(client, "&show=active")
    assert "Retail" not in {c["class_name"] for c in active["classes"]}
    assert active["filtered"] is True
    assert active["total_net_income"] == -100.0
    assert active["unfiltered"]["net_income"] == 0.0
    # chosen by id, an archived class still gets its column
    chosen = _by_class(client, f"&show=active&class_ids={retail}")
    assert [c["class_name"] for c in chosen["classes"]] == ["Retail"]


def test_an_empty_class_gets_a_zero_column_when_asked(client, ledger):
    empty = client.post("/api/classes", json={"name": "Dormant"}).json()
    plain = _by_class(client)
    assert "Dormant" not in {c["class_name"] for c in plain["classes"]}

    full = _by_class(client, "&include_empty=true")
    names = [c["class_name"] for c in full["classes"]]
    assert names == ["Uncategorized", "Dormant", "Retail", "Side Gig"]
    dormant = next(c for c in full["classes"] if c["class_name"] == "Dormant")
    assert dormant["net_income"] == 0.0 and dormant["income"] == 0.0
    assert full["filtered"] is False, "nothing with activity is left out"
    assert full["total_net_income"] == plain["total_net_income"]
    at = names.index("Dormant")
    for section in full["accounts"].values():
        for row in section:
            assert row["amounts"][at] == 0.0
    # the grid's CSV has the empty column too
    rows, _ = _csv_rows(
        client, f"/api/reports/profit-loss-by-class/csv?{PERIOD}&include_empty=true"
    )
    assert rows[0][3:] == names + ["Total"]
    # archived and empty: only under All
    assert (
        client.put(
            f"/api/classes/{empty['id']}", json={"is_archived": True}
        ).status_code
        == 200
    )
    assert "Dormant" not in [
        c["class_name"]
        for c in _by_class(client, "&include_empty=true&show=active")["classes"]
    ]
    assert "Dormant" in [
        c["class_name"] for c in _by_class(client, "&include_empty=true")["classes"]
    ]


def test_a_saved_by_class_report_carries_the_column_choice(client, ledger):
    params = {
        "period": "last_month",
        "start_date": "2026-07-01",
        "end_date": "2026-07-31",
        "show": "active",
        "include_empty": "true",
        "class_ids": f"{ledger['side']},{ledger['retail']}",
    }
    r = client.post(
        "/api/saved-reports",
        json={
            "name": "Divisions",
            "report_type": "profit_loss_by_class",
            "parameters": params,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["parameters"] == params
