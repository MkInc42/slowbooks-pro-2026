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
    # `from` names the view that opened the drill-down (R7): 'general-ledger'
    # is a registered view, so the button is "Back to General Ledger" and
    # it goes back to the ledger on the drill-down's dates
    drill = _method(
        "async openDrillDown(accountId, accountName, startDate, endDate, "
        "classId = null, className = null, from = null)"
    )
    assert "const back = ReportsPage._VIEWS[from] ? from : null;" in drill
    assert "backBtn = ReportsPage._backButton(back, backParams);" in drill
    assert "{ start_date: startDate, end_date: endDate }" in drill
    assert "'general-ledger':       { label: 'General Ledger'" in JS
    button = JS[JS.index("\n    _backButton(name, params) {") :]
    button = button[: button.index("\n    },")]
    assert "ReportsPage.backTo(" in button
    assert "typeof view.label === 'function' ? view.label() : view.label" in button
    assert "Back to ${escapeHtml(label)}" in button
    # the older helper still answers by name, through the same button
    back = JS[JS.index("ReportsPage._backToGeneralLedger = function") :]
    back = back[: back.index("\n};")]
    assert (
        "ReportsPage._backButton('general-ledger', { start_date: startDate, end_date: endDate })"
        in back
    )
