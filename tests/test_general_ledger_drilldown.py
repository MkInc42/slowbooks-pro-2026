"""An account in the General Ledger opens its register (#224).

The GL rendered each account as a plain heading while the P&L and Balance
Sheet made their account names links into the account's register
(ReportsPage.openDrillDown). A user reported clicking an account in the GL
and nothing happening. Pinned by reading reports.js, as
test_reconciliation_report.py pins banking.js; the click itself is in
tests/test_browser_ui.py.
"""

import re
from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "app/static/js/reports.js").read_text(
    encoding="utf-8"
)


def _method(signature):
    body = JS[JS.index(f"\n    {signature} {{") :]
    return body[: body.index("\n    },")]


def test_the_general_ledger_heading_links_into_the_account_register():
    gl = _method("async generalLedger(prefill)")
    # the P&L's way: the onclick payload built outside the template and escaped
    assert "const drillCall = (acct) => escapeHtml(" in gl
    assert "ReportsPage.openDrillDown(${acct.account_id}" in gl
    assert "${JSON.stringify(range.start)},${JSON.stringify(range.end)}" in gl
    assert "'general-ledger'" in gl
    # the link sits in the heading, in the link colour, and only with an id
    assert re.search(
        r"<h3 [^>]*>\$\{escapeHtml\(acct\.account_number\)\} &mdash; \$\{name\}</h3>",
        gl,
    )
    assert (
        'acct.account_id\n                        ? `<a href="javascript:void(0)"' in gl
    )
    assert "color:var(--text-link); text-decoration:none;" in gl


def test_the_drill_down_offers_the_way_back_to_the_ledger():
    drill = _method(
        "async openDrillDown(accountId, accountName, startDate, endDate, "
        "classId = null, className = null, from = null)"
    )
    assert (
        "from === 'general-ledger' ? ReportsPage._backToGeneralLedger(startDate, endDate)"
        in drill
    )
    back = JS[JS.index("ReportsPage._backToGeneralLedger = function") :]
    back = back[: back.index("\n};")]
    assert "ReportsPage.generalLedger({period: 'custom', start_date:" in back
    assert "Back to General Ledger" in back
