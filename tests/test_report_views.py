"""Report views have addresses (R7, #237): the router takes a query string
apart instead of swallowing it into the :id parameter, '#/reports/<view>'
opens the view over the Report Center from its query, and every report the
Report Center offers is registered under a view name, so a bookmark, a
pasted link, a reload or Back reproduces it.

The router is driven in node (tests/js/report_views_probe.js) on stub
pages; the registry is read from the page sources. What the views do in a
browser — reload, period change, drill-down, Back — is
tests/test_browser_report_views.py.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app" / "static" / "js"

needs_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed"
)


def _probe(*hashes):
    out = subprocess.run(
        [
            "node",
            str(ROOT / "tests" / "js" / "report_views_probe.js"),
            json.dumps(hashes),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# ── the router ───────────────────────────────────────────────────────────


@needs_node
def test_parse_hash_splits_the_path_from_the_query():
    shown = _probe(
        "#/reports/profit-loss?start_date=2026-07-01&end_date=2026-09-30",
        "#/reports/account-transactions?account_id=5120&class_id=3&start_date=2026-07-01&end_date=2026-09-30&from=general-ledger",
        "#/jobs/12?tab=costs",
        "#/",
        "",
        "#/reports?",
        "#/reports/profit-loss?name=Salt%20%26%20Pine&empty=",
    )
    assert shown["#/reports/profit-loss?start_date=2026-07-01&end_date=2026-09-30"][
        "parsed"
    ] == {
        "path": "/reports/profit-loss",
        "query": {"start_date": "2026-07-01", "end_date": "2026-09-30"},
    }
    drill = shown[
        "#/reports/account-transactions?account_id=5120&class_id=3&start_date=2026-07-01&end_date=2026-09-30&from=general-ledger"
    ]["parsed"]
    assert drill["path"] == "/reports/account-transactions"
    assert drill["query"] == {
        "account_id": "5120",
        "class_id": "3",
        "start_date": "2026-07-01",
        "end_date": "2026-09-30",
        "from": "general-ledger",
    }
    assert shown["#/jobs/12?tab=costs"]["parsed"] == {
        "path": "/jobs/12",
        "query": {"tab": "costs"},
    }
    assert shown["#/"]["parsed"] == {"path": "/", "query": {}}
    assert shown[""]["parsed"] == {"path": "/", "query": {}}
    assert shown["#/reports?"]["parsed"] == {"path": "/reports", "query": {}}
    # percent-encoding is undone; an empty value is still a key
    assert shown["#/reports/profit-loss?name=Salt%20%26%20Pine&empty="]["parsed"][
        "query"
    ] == {
        "name": "Salt & Pine",
        "empty": "",
    }


@needs_node
def test_a_report_view_opens_over_the_report_center_from_its_query():
    url = "#/reports/profit-loss?start_date=2026-07-01&end_date=2026-09-30"
    shown = _probe(
        url, "#/reports/account-transactions?account_id=5120&from=profit-loss"
    )
    pl = shown[url]
    assert pl["page"] == "<ReportsPage>"
    assert pl["calls"] == [
        ["ReportsPage.render"],
        [
            "ReportsPage.openView",
            "profit-loss",
            {"start_date": "2026-07-01", "end_date": "2026-09-30"},
        ],
    ]
    # the whole address, query included, is what the router put on the bar
    assert pl["hash"] == url and pl["pushes"] == 1
    drill = shown["#/reports/account-transactions?account_id=5120&from=profit-loss"]
    assert drill["calls"][1] == [
        "ReportsPage.openView",
        "account-transactions",
        {"account_id": "5120", "from": "profit-loss"},
    ]


@needs_node
def test_every_route_still_works_and_a_query_no_longer_reaches_the_id():
    shown = _probe(
        "#/reports",
        "#/invoices/12",
        "#/jobs/12?tab=costs",
        "#/banking/transfers/9",
        "#/customers?x=1",
        "#/nothing-here",
    )
    assert shown["#/reports"]["calls"] == [["ReportsPage.render"]]
    assert shown["#/invoices/12"]["calls"] == [
        ["InvoicesPage.render"],
        ["InvoicesPage.view", "12"],
    ]
    # the id is the segment alone; the query is the route's to forward
    # (as '/reports/:view' does, and the job page since #242: its period
    # and the report it was opened from), and a route that takes none
    # ignores it
    assert shown["#/jobs/12?tab=costs"]["calls"] == [
        ["JobsPage.renderDetail", "12", {"tab": "costs"}]
    ]
    assert shown["#/banking/transfers/9"]["calls"] == [
        ["BankingPage.render"],
        ["JournalPage.view", "9"],
    ]
    assert shown["#/customers?x=1"]["calls"] == [["CustomersPage.render"]]
    assert shown["#/customers?x=1"]["hash"] == "#/customers?x=1"
    assert shown["#/nothing-here"]["page"] == "<p>Page not found</p>"


# ── the registry ─────────────────────────────────────────────────────────


def _views_block():
    src = (JS / "reports.js").read_text(encoding="utf-8")
    m = re.search(r"_VIEWS:\s*\{(.*?)\n    \},", src, re.S)
    assert m, "ReportsPage._VIEWS is the registry"
    return src, m.group(1)


def test_every_report_the_report_center_offers_has_a_view_name():
    src, block = _views_block()
    names = re.findall(r"^\s*'([a-z0-9-]+)':\s*\{", block, re.M)
    assert names and all(
        re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", n) for n in names
    ), names
    assert len(names) == len(set(names))
    # every card on the Report Center (business and nonprofit) is a link
    # to a view the registry names (ReportsPage._card), so the keyboard
    # reaches it and its report has an address; and no card is a click
    # alone any more
    cards = re.findall(r"\bcard\('([a-z0-9-]+)', ", src)
    assert len(cards) >= 24 and len(cards) == len(set(cards)), cards
    for view in cards:
        assert view in names, f"the card for {view} has no view"
    assert 'class="card" style="cursor:pointer" onclick=' not in src
    card = src[src.index("    _card(view, title, text) {") :]
    card = card[: card.index("\n    },")]
    assert (
        '<a class="card report-card" href="${ReportsPage.viewUrl(view, {})}"'
        ' data-row-key="report:${view}"' in card
    )
    assert 'aria-label="${escapeHtml(title)}" aria-describedby="${id}-text"' in card
    assert (
        'onclick="ReportsPage._leaveFrom(this)" onkeydown="ReportsPage._cardKey(event)"'
        in card
    )
    # the drill-down and a class's own P&L, opened from inside a report
    for inner in ("openDrillDown(", "profitLossOfClass("):
        assert inner in block, inner


def test_every_period_report_puts_its_view_on_the_address():
    # openPeriodModal writes the address on each render when told the
    # view; every call tells it. The call's closer is the first line at
    # the call's own indentation that ends it: "}, "Dates", false, {…});"
    for name in ("reports.js", "budgets.js"):
        src = (JS / name).read_text(encoding="utf-8")
        lines = src.splitlines()
        calls = [
            i for i, line in enumerate(lines) if "ReportsPage.openPeriodModal(" in line
        ]
        assert calls, name
        for i in calls:
            indent = re.match(r"\s*", lines[i]).group(0)
            closer = next(
                (
                    line
                    for line in lines[i + 1 :]
                    if re.match(rf"{indent}\}}.*\);$", line)
                ),
                None,
            )
            assert closer, f"{name}:{i + 1} openPeriodModal has no closer"
            assert re.search(
                r"\bview: '[a-z0-9-]+'", closer
            ), f"{name}:{i + 1} openPeriodModal names no view: {closer.strip()}"


def test_saved_report_types_are_view_names_with_underscores():
    from app.routes.saved_reports import _ALLOWED_TYPES

    _, block = _views_block()
    names = set(re.findall(r"^\s*'([a-z0-9-]+)':\s*\{", block, re.M))
    # every type a saved report can carry opens through its view's address;
    # analytics_dashboard is the Analytics page, not a report view
    for t in _ALLOWED_TYPES - {"analytics_dashboard"}:
        assert t.replace("_", "-") in names, t


def test_the_dashboard_cards_link_to_the_dated_report():
    src = (JS / "dashboard.js").read_text(encoding="utf-8")
    assert (
        'href="#/reports"' not in src
    ), "a card links to its report, not the Report Center"
    assert src.count("DashboardPage._reportLink(") == 3
    assert "ReportsPage.viewUrl(" in src


def test_the_dev_note_is_short_and_says_how_to_register_a_view():
    note = (ROOT / "docs" / "dev" / "report-views.md").read_text(encoding="utf-8")
    assert len(note.strip().splitlines()) <= 40
    for word in ("_VIEWS", "setAddress", "replaceState", "push", "Back"):
        assert word in note, word
