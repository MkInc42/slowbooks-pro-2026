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
    assert "if (escapeLeavesPicker(e)) return;\n        e.preventDefault(); closeModal(); return;" in utils
    app = _src("app.js")
    assert "if (e.key === 'Escape' && !escapeLeavesPicker(e)) { closeModal(); }" in app


# ── NEW-41 ────────────────────────────────────────────────────────────────


def test_the_alt_shortcuts_compare_the_keys_position_and_cmd_k_finds():
    app = _src("app.js")
    keys = app[app.index("// Keyboard shortcuts.") :]
    keys = keys[: keys.index("// Close search dropdown")]
    assert "const alt = e.altKey && !e.ctrlKey && !e.metaKey;" in keys
    for code in ("KeyN", "KeyP", "KeyQ", "KeyH", "KeyD"):
        assert f"if (alt && e.code === '{code}')" in keys, code
    assert "['KeyN', 'KeyP', 'KeyQ'].includes(e.code) && App.isReadOnly()" in keys
    assert not re.search(r"(?<!!)e\.altKey && e\.key === '[a-z]'", keys)
    assert "((e.ctrlKey || e.metaKey) && !e.altKey && e.key === 'k')" in keys
