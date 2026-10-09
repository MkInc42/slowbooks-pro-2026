"""The keyboard fixes of the 2.22.0 gate's second round, pinned in the
sources, so they hold where playwright's Chromium is not installed (the
Windows and macOS suites); what they do in a browser is
tests/test_browser_keyboard.py.

- NEW-25: the dialog's Tab is walked in script (utils.js modalKeydown)
  through every control the browser's own Tab would reach.
- NEW-33: an Escape at a date or time field leaves the field and does not
  close the dialog, in both Escape handlers.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app" / "static" / "js"


def _src(name):
    return (JS / name).read_text(encoding="utf-8")


# ── NEW-25 ────────────────────────────────────────────────────────────────


def test_the_dialogs_tab_is_walked_in_script_in_the_browsers_order():
    utils = _src("utils.js")
    walk = utils[utils.index("function modalKeydown(e)") :]
    walk = walk[: walk.index("document.addEventListener('keydown', modalKeydown)")]
    assert "if (e.key !== 'Tab' || e.defaultPrevented) return;" in walk
    assert "const stops = _tabStops(modal, active);" in walk
    # wraps at the ends, and from the dialog itself goes to its first or last
    assert "stops[(i + (back ? -1 : 1) + stops.length) % stops.length]" in walk
    assert "next = back ? stops[stops.length - 1] : stops[0];" in walk
    # a date field's segments are the browser's; a wrong landing is put right
    assert "_hasSegments(active) || _hasSegments(next)" in walk
    assert "active.addEventListener('focusout', left, { once: true });" in walk
    assert "e.preventDefault();\n    _tabTo(next);" in walk
    stops = utils[utils.index("function _tabStops(root, from)") :]
    stops = stops[: stops.index("\n}\n")]
    # the browser's rules: enabled, tabbable, drawn; tabindex above 0 first
    assert "el.tabIndex >= 0 && !el.matches(':disabled') && _drawn(el)" in stops
    assert ".sort((a, b) => a.tabIndex - b.tabIndex)" in stops
    assert "return ahead.concat(stops.filter(el => el.tabIndex === 0));" in stops
    assert re.search(
        r"const _TAB_SEL = 'a\[href\], area\[href\], button, input, select, textarea, summary, iframe, \[tabindex\]",
        utils,
    )
    # the dialog's first control is found the same way
    assert "_tabStops($('#modal-body'), null)[0]" in utils
    # a text box's words are selected on the way in, a textarea's are not
    tab_to = utils[utils.index("function _tabTo(el)") :]
    tab_to = tab_to[: tab_to.index("\n}\n")]
    assert (
        "el.tagName === 'INPUT' && /^(text|search|url|tel|password|email|number)$/.test(el.type)"
        in tab_to
    )
    assert "TEXTAREA" not in tab_to


# ── NEW-33 ────────────────────────────────────────────────────────────────


def test_an_escape_at_a_date_field_leaves_the_field_in_both_handlers():
    utils = _src("utils.js")
    leaves = utils[utils.index("function escapeLeavesPicker(e)") :]
    leaves = leaves[: leaves.index("\n}\n")]
    assert "if (!_hasSegments(e.target)) return false;" in leaves
    assert "modal.contains(e.target)) modal.focus();" in leaves
    assert "return true;" in leaves
    assert re.search(
        r"/\^\(date\|time\|datetime-local\|month\|week\)\$/\.test\(el\.type\)", utils
    )
    assert (
        "if (escapeLeavesPicker(e)) return;\n        e.preventDefault(); closeModal(); return;"
        in utils
    )
    app = _src("app.js")
    assert "if (e.key === 'Escape' && !escapeLeavesPicker(e)) { closeModal(); }" in app


# ── NEW-41 ────────────────────────────────────────────────────────────────


def test_the_alt_shortcuts_compare_the_keys_position_and_cmd_k_finds():
    app = _src("app.js")
    keys = app[app.index("// Keyboard shortcuts.") :]
    keys = keys[: keys.index("// Close search dropdown")]
    assert "const alt = e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey;" in keys
    # inside a field the plain letter alone (a Mac's Option types a
    # character, or a dead key, that must go through); outside, the key
    assert (
        "e.target.closest('input, textarea, select, [contenteditable]:not([contenteditable=\"false\"])')"
        in keys
    )
    assert (
        "const letter = (code, key) => alt && e.code === code && (!editing || String(e.key).toLowerCase() === key);"
        in keys
    )
    for code, key in (
        ("KeyN", "n"),
        ("KeyP", "p"),
        ("KeyQ", "q"),
        ("KeyH", "h"),
        ("KeyD", "d"),
    ):
        assert f"if (letter('{code}', '{key}'))" in keys, code
    assert (
        "const entry = letter('KeyN', 'n') || letter('KeyP', 'p') || letter('KeyQ', 'q');"
        in keys
    )
    assert "if (entry && App.isReadOnly())" in keys
    # ⌘⌥[ is not Back
    assert (
        "e.metaKey && !e.ctrlKey && !e.altKey && !e.shiftKey && (e.code === 'BracketLeft' || e.key === '[')"
        in app
    )
    assert not re.search(r"(?<!!)e\.altKey && e\.key === '[a-z]'", keys)
    assert "((e.ctrlKey || e.metaKey) && !e.altKey && e.key === 'k')" in keys


# ── NEW-30 ────────────────────────────────────────────────────────────────


def test_the_toolbar_has_a_back_that_knows_whether_there_is_somewhere_to_go():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    btn = re.search(r'<button[^>]*id="back-btn"[^>]*>', html).group(0)
    assert 'aria-label="Back"' in btn and "disabled" in btn and 'type="button"' in btn
    assert "App.goBack && App.goBack()" in _src("bootstrap.js")
    app = _src("app.js")
    assert "canGoBack() { return !!(history.state && history.state.from); }" in app
    assert "goBack() { if (App.backAllowed()) history.back(); }" in app
    assert "history.length" not in re.sub(r"//.*", "", app)  # not in the code
    # a link's entry is stamped when first seen; the first entry at start
    assert (
        "else if (!history.state) history.replaceState(App.entryState(App._here), '', here);"
        in app
    )
    assert (
        "if (!history.state) history.replaceState({ from: null, n: 0 }, '', location.hash || '#/');"
        in app
    )
    # the button follows every push, stamp and history move
    assert app.count("App.addressShown();") >= 3
    assert "closeModal({ keepAddress: true });\n            App.syncBack();" in app
    assert "App.dialogAddressed();  // the view's own address" in _src("reports.js")
    # the shortcut: ⌘[ on a Mac, Alt+← elsewhere, by key position
    assert (
        "if (App.isBackKey(e) && App.backAllowed()) { e.preventDefault(); App.goBack(); return; }"
        in app
    )
    assert (
        "!e.altKey && !e.shiftKey && (e.code === 'BracketLeft' || e.key === '[')" in app
    )
    assert (
        "e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey && e.code === 'ArrowLeft'"
        in app
    )
    assert "btn.title = mac ? 'Back (⌘[)' : 'Back (Alt+←)';" in app
    css = (ROOT / "app/static/css/style.css").read_text(encoding="utf-8")
    assert ".tb-btn:disabled {" in css
    docs = (ROOT / "docs/accessibility.md").read_text(encoding="utf-8")
    assert "⌘[" in docs and "Alt+←" in docs


# ── NEW-32 ────────────────────────────────────────────────────────────────

# Every button that says Void or Delete carries the marker openModal reads,
# in a dialog or a list (the rule is one rule); the three the gate named
# are among them
DESTRUCTIVE = [
    ("journal.js", "JournalPage.void(${entry.id})"),
    ("deposits.js", "DepositsPage.voidDeposit(${d.id})"),
    ("job_costs.js", "JobCostsPage.voidEntry(${jc.id})"),
]


def test_every_void_or_delete_is_marked_and_never_focused_first():
    """A button that says Void or Delete, or is named so (an icon button's
    aria-label, "Delete attachment"), carries the marker."""
    unmarked = []
    for p in sorted(JS.glob("*.js")):
        src = p.read_text(encoding="utf-8")
        for m in re.finditer(r"<button([^>]*)>", src):
            attrs = m.group(1)
            says = re.match(r"\s*(Void|Delete)\b", src[m.end() : m.end() + 40])
            named = re.search(r'aria-label="(Void|Delete)\b', attrs)
            if (says or named) and "data-destructive" not in attrs:
                unmarked.append(f"{p.name}: {m.group(0)[:80]}")
    assert not unmarked, unmarked
    assert (
        sum(
            _src(n).count('data-destructive aria-label="Delete attachment"')
            for n in ("bills.js", "expenses.js", "invoices.js")
        )
        == 3
    )
    for name, call in DESTRUCTIVE:
        assert f'onclick="{call}"' in _src(name), (name, call)


# ── NEW-38 ────────────────────────────────────────────────────────────────


def test_the_customer_pages_invoice_and_payment_rows_carry_links():
    src = _src("customers.js")
    assert (
        "rowLink(`#/invoices/${i.id}`, `invoice:${i.id}`, i.invoice_number || `#${i.id}`)"
        in src
    )
    assert (
        "rowLink(`#/payments/${p.id}`, `payment:${p.id}`, p.date || `#${p.id}`)" in src
    )
    assert 'onclick="event.preventDefault()">${escapeHtml(text)}</a>' in src
    # the row's click still opens the document, through the router (a
    # history entry, Back returns), noting the link left for the focus
    assert (
        "const hop = (href) => `ReportsPage._leaveFrom();closeModal({ keepAddress: true });App.navigate('${href}')`;"
        in src
    )
    assert 'onclick="${hop(`#/invoices/${i.id}`)}"' in src
    assert 'onclick="${hop(`#/payments/${p.id}`)}"' in src
    assert "PaymentsPage.view(${p.id})" not in src
    # and the page's render puts the focus back on it
    assert (
        "if (history.state && history.state.focus) setTimeout(() => ReportsPage._refocusRow($('#modal-body')), 0);"
        in _src("app.js")
    )


# ── NEW-37 ────────────────────────────────────────────────────────────────


def test_the_line_class_and_function_cells_leave_their_names_to_the_grid_rule():
    utils = _src("utils.js")
    assert "for this line" not in utils
    assert (
        '<select class="${cls}-fund" data-no-search><option value="">Same as header</option>'
        in utils
    )
    assert '<select class="${cls}">${Nonprofit.optionsHtml(selected' in utils
    # the rule that names them: the column heading and "line N"
    assert "rowName = `line ${row.sectionRowIndex + 1}`;" in utils
    assert "return [heading, rowName].filter(Boolean).join(', ');" in utils


# ── NEW-39 ────────────────────────────────────────────────────────────────


def test_the_drill_downs_position_is_a_live_status_with_the_account():
    src = _src("reports.js")
    assert (
        '<span id="drill-position" class="grid-live" role="status" aria-live="polite"'
        in src
    )
    assert (
        "pos.textContent = list.length > 1 && i >= 0 ? `${i + 1} of ${list.length}: ${list[i].label}` : '';"
        in src
    )


# ── Review, round 2: Back is inert over a form ───────────────────────────


def test_back_is_inert_over_a_dialog_with_no_address_of_its_own():
    app = _src("app.js")
    assert "backAllowed() { return App.canGoBack() && !App.editingDialog(); }" in app
    assert "return (m.dataset.address || '') !== (location.hash || '#/');" in app
    # the three ways the router gives a dialog its address mark it
    assert "App.dialogAddressed();  // the open dialog's own" in app  # documentAddress
    assert (
        "App.dialogAddressed();\n                    if (history.state && history.state.focus)"
        in app
    )  # withDocument
    assert "App.dialogAddressed();  // the view's own address" in _src(
        "reports.js"
    )  # setAddress
    # a plain form clears the mark, and the button follows; a mark the
    # opener itself set (its address first, then openModal) stays
    utils = _src("utils.js")
    assert "const wasOpen = !$('#modal-overlay').classList.contains('hidden');" in utils
    assert (
        "const own = modal.dataset.address === (location.hash || '#/') && (!wasOpen || !!(window.App && window.App._marking));"
        in utils
    )
    assert utils.count("if (!own) delete modal.dataset.address;") == 1  # openModal
    assert (
        "App._marking = true;\n        setTimeout(() => { App._marking = false; }, 0);"
        in app
    )
    assert utils.count("delete $('#modal').dataset.address;") == 1  # closeModal
    assert utils.count("window.App.syncBack();") == 2
    assert "btn.classList.toggle('tb-back--under', App.editingDialog());" in app
    css = (ROOT / "app/static/css/style.css").read_text(encoding="utf-8")
    assert ".tb-back.tb-back--under {\n    z-index: auto;\n}" in css
    # a customer's or vendor's page opens the dialog, then gives it its address
    for name, call in (
        ("customers.js", "App.documentAddress(`#/customers/${customer.id}`)"),
        ("vendors.js", "App.documentAddress(`#/vendors/${vendor.id}`)"),
    ):
        src = _src(name)
        at = src.index(call)
        assert "openModal(" in src[at - 200 : at], name


# ── Review, round 2: a replaced address keeps the entry's state ──────────


def test_a_replaced_address_keeps_the_entrys_state_and_the_button_follows():
    """Never lit with canGoBack() false: every replaceState of the app's
    carries history.state along and re-syncs the button."""
    for name in (
        "app.js",
        "reports.js",
        "settings.js",
        "utils.js",
        "customers.js",
        "vendors.js",
    ):
        assert "replaceState(null" not in _src(name), name
    reports = _src("reports.js")
    assert reports.count("ReportsPage._addressReportCenter();") == 3
    assert (
        "history.replaceState(history.state, '', '#/reports');\n        App.addressShown();"
        in reports
    )
    assert "if (location.hash !== '#/settings') App.stayPut();" in _src("settings.js")


# ── Review, round 2: the nits ────────────────────────────────────────────


def test_an_unchecked_radio_group_is_one_stop_its_first_radio():
    utils = _src("utils.js")
    stops = utils[utils.index("function _tabStops(root, from)") :]
    stops = stops[: stops.index("\n}\n")]
    assert "if (picked.has(g)) return el.checked;" in stops
    assert (
        "if (seen.has(g)) return false;\n        seen.add(g);\n        return true;"
        in stops
    )


def test_the_shortcut_list_follows_the_screen_reader_bullets():
    docs = (ROOT / "docs/accessibility.md").read_text(encoding="utf-8")
    bullets_end = docs.index("State is never conveyed by colour alone")
    assert docs.index("### Keyboard shortcuts") > bullets_end
    assert docs.index("### Keyboard shortcuts") < docs.index(
        "## What we know is still open"
    )
    assert docs.index("### Keyboard shortcuts") > docs.index(
        "### Screen readers and keyboards"
    )


# ── Review, round 3: a declined leave goes back to its entry ─────────────


def test_a_declined_leave_goes_back_to_the_entry_it_left():
    app = _src("app.js")
    assert "entryState(from) { return { from, n: App._nShown + 1 }; }" in app
    assert (
        "if (typeof n === 'number' && n < App._nShown) history.forward(); else history.back();"
        in app
    )
    assert (
        "if (App._stay) { App._stay = false; App.addressShown(); return; }" in app
    )  # navigate
    assert "if (App._stay) { App.syncBack(); return; }" in app  # popstate
    # every entry the app makes carries its place
    assert app.count("App.entryState(") == 3
    assert "history.pushState(App.entryState(here), '', url);" in _src("reports.js")
    assert "if (location.hash !== '#/settings') App.stayPut();" in _src("settings.js")
