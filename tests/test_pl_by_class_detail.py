"""P&L by Class, account by account, and the transactions behind it (#213).

A user could see each class's totals but not what made them up: the P&L by
Class was one row per class, and neither the P&L nor its drill-down took a
class. Now the report lists every account with a column per class, a
class has its own P&L, and the drill-down and the General Ledger carry the
class. A line belongs to its own class, else its transaction's, else
Uncategorized, the rule P&L by Class has always grouped by.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.services.accounting import create_journal_entry
from app.services.classes_service import uncategorized_class_id

D = Decimal
PERIOD = "start_date=2026-07-01&end_date=2026-07-31"


# Named, so another module can import it without shadowing the name its
# tests ask for (tests/test_pl_grid_exports.py).
@pytest.fixture(name="ledger")
def ledger_fixture(client, db_session, seed_accounts):
    """Two classes and the postings the tests read:
    - Side Gig (header): 300 income, 300 expense
    - Retail (header) with one line of its own in Side Gig: 100 income in
      Retail, 100 COGS in Side Gig
    - no class at all: 50 income, 50 expense (Uncategorized)
    - before the period, Side Gig: 40 income (the drill-down's opening)
    """
    side = client.post("/api/classes", json={"name": "Side Gig"}).json()
    retail = client.post("/api/classes", json={"name": "Retail"}).json()
    income, expense, cogs = (seed_accounts[n] for n in ("4000", "6000", "5300"))

    def je(day, what, lines, class_id=None):
        create_journal_entry(db_session, day, what, lines, class_id=class_id)

    je(
        date(2026, 7, 10),
        "side gig",
        [
            {"account_id": expense.id, "debit": D("300"), "credit": D("0")},
            {"account_id": income.id, "debit": D("0"), "credit": D("300")},
        ],
        class_id=side["id"],
    )
    je(
        date(2026, 7, 12),
        "retail, one line in side gig",
        [
            {
                "account_id": cogs.id,
                "debit": D("100"),
                "credit": D("0"),
                "class_id": side["id"],
            },
            {"account_id": income.id, "debit": D("0"), "credit": D("100")},
        ],
        class_id=retail["id"],
    )
    je(
        date(2026, 7, 14),
        "no class",
        [
            {"account_id": expense.id, "debit": D("50"), "credit": D("0")},
            {"account_id": income.id, "debit": D("0"), "credit": D("50")},
        ],
    )
    je(
        date(2026, 6, 20),
        "side gig, last month",
        [
            {"account_id": expense.id, "debit": D("40"), "credit": D("0")},
            {"account_id": income.id, "debit": D("0"), "credit": D("40")},
        ],
        class_id=side["id"],
    )
    uncat = uncategorized_class_id(db_session)  # made on first use, as the app does
    db_session.commit()
    return {
        "side": side["id"],
        "retail": retail["id"],
        "uncat": uncat,
        "income": income.id,
        "expense": expense.id,
        "cogs": cogs.id,
    }


def _row(section, account_id):
    return next(r for r in section if r["account_id"] == account_id)


def test_the_report_lists_each_account_with_a_column_per_class(client, ledger):
    data = client.get(f"/api/reports/profit-loss-by-class?{PERIOD}").json()
    order = [c["class_name"] for c in data["classes"]]
    at = {name: i for i, name in enumerate(order)}
    assert set(order) == {"Uncategorized", "Retail", "Side Gig"}

    income = _row(data["accounts"]["income"], ledger["income"])
    assert income["amounts"][at["Side Gig"]] == 300.0
    assert income["amounts"][at["Retail"]] == 100.0
    assert income["amounts"][at["Uncategorized"]] == 50.0
    assert income["total"] == 450.0
    # the line's own class wins over its transaction's
    cogs = _row(data["accounts"]["cogs"], ledger["cogs"])
    assert cogs["amounts"][at["Side Gig"]] == 100.0 and cogs["total"] == 100.0
    expense = _row(data["accounts"]["expenses"], ledger["expense"])
    assert expense["amounts"][at["Side Gig"]] == 300.0
    assert expense["amounts"][at["Uncategorized"]] == 50.0

    # it ties to the plain P&L, account by account and in total
    plain = client.get(f"/api/reports/profit-loss?{PERIOD}").json()
    for key in ("income", "cogs", "expenses"):
        mine = {r["account_id"]: r["total"] for r in data["accounts"][key]}
        theirs = {r["account_id"]: r["amount"] for r in plain[key] if r["amount"]}
        assert mine == theirs, key
    assert data["total_income"] == plain["total_income"]
    assert data["total_cogs"] == plain["total_cogs"]
    assert data["total_gross_profit"] == plain["gross_profit"]
    assert data["total_net_income"] == plain["net_income"]


def test_a_class_has_its_own_profit_and_loss(client, ledger):
    side = client.get(f"/api/reports/profit-loss?{PERIOD}&class_id={ledger['side']}")
    assert side.status_code == 200
    side = side.json()
    assert side["class_name"] == "Side Gig"
    assert side["total_income"] == 300.0
    assert side["total_cogs"] == 100.0
    assert side["total_expenses"] == 300.0
    assert side["net_income"] == -100.0

    retail = client.get(
        f"/api/reports/profit-loss?{PERIOD}&class_id={ledger['retail']}"
    ).json()
    assert (retail["total_income"], retail["total_cogs"]) == (100.0, 0)

    uncat = client.get(
        f"/api/reports/profit-loss?{PERIOD}&class_id={ledger['uncat']}"
    ).json()
    assert (uncat["total_income"], uncat["total_expenses"]) == (50.0, 50.0)

    everything = client.get(f"/api/reports/profit-loss?{PERIOD}").json()
    assert everything["class_id"] is None and everything["total_income"] == 450.0


def test_the_drill_down_shows_one_class_s_lines(client, ledger):
    base = f"/api/reports/account-transactions?account_id={ledger['income']}&{PERIOD}"
    side = client.get(f"{base}&class_id={ledger['side']}").json()
    assert side["class_name"] == "Side Gig"
    assert [e["description"] for e in side["entries"]] == ["side gig"]
    assert side["period_net"] == 300.0
    # what came before the period, in that class only
    assert side["opening_balance"] == 40.0

    retail = client.get(f"{base}&class_id={ledger['retail']}").json()
    assert [e["description"] for e in retail["entries"]] == [
        "retail, one line in side gig"
    ]
    assert retail["opening_balance"] == 0.0

    everything = client.get(base).json()
    assert everything["period_net"] == 450.0 and everything["opening_balance"] == 40.0
    assert everything["class_id"] is None


def test_an_unknown_class_is_a_404(client, ledger):
    assert (
        client.get(f"/api/reports/profit-loss?{PERIOD}&class_id=99999").status_code
        == 404
    )
    r = client.get(
        f"/api/reports/account-transactions?account_id={ledger['income']}&{PERIOD}&class_id=99999"
    )
    assert r.status_code == 404


def test_the_general_ledger_carries_the_class(client, ledger):
    gl = client.get(f"/api/reports/general-ledger?{PERIOD}").json()
    classes = {
        (a["account_id"], e["description"]): e["class_name"]
        for a in gl["accounts"]
        for e in a["entries"]
    }
    assert classes[(ledger["income"], "side gig")] == "Side Gig"
    assert classes[(ledger["cogs"], "retail, one line in side gig")] == "Side Gig"
    assert classes[(ledger["income"], "retail, one line in side gig")] == "Retail"
    assert classes[(ledger["income"], "no class")] == "Uncategorized"

    csv = client.get(f"/api/reports/general-ledger/csv?{PERIOD}").text
    header = next(line for line in csv.splitlines() if line.startswith("Date,"))
    assert header.rstrip().endswith(",Class")
    assert any(
        "side gig" in line and line.rstrip().endswith(",Side Gig")
        for line in csv.splitlines()
    )
