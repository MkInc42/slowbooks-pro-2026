"""The keyboard in dialogs and on the page, in playwright's Chromium on the
bakery's books of tests/test_theme_contrast.py (2.22.0 gate, round 2):

- NEW-25: inside a dialog, Tab and Shift+Tab are moved in script through
  every control, wrapping at the ends, so WebKit's Tab (which, under
  macOS's default keyboard setting, skips buttons and links and leaves the
  dialog) reaches "Back to …", Prev/Next and a report's links. The walk is
  checked against the browser's own: the sequence Chromium's native Tab
  takes with the handler removed is the sequence the handler takes, on
  the New Invoice form (date fields and their segments, type-ahead boxes,
  checkboxes, a line table), a drill-down (links in every row, Prev/Next,
  Back to …) and the P&L by Class grid (the focusable scroll region, the
  column picker, a link per cell). A dialog with no date field is walked
  by synthetic Tab events alone, which move no focus by themselves: the
  WebKit case.
- NEW-33: Escape in a date field leaves the field rather than closing the
  dialog; the next Escape closes it.
- NEW-41: the Alt shortcuts go by the key's position (e.code), so a Mac's
  Option-D ("∂") still toggles the theme; ⌘K finds like Ctrl+K; Ctrl+Alt
  (AltGr) is left alone.
- NEW-30: the toolbar's Back, enabled only while an app page is behind,
  with Alt+← (⌘[ on a Mac); a reload keeps it.
- NEW-32: no dialog opens with focus on Void or Delete; a dialog whose
  first control is one takes focus itself.
- NEW-38: the customer page's invoice rows carry a real link, reachable
  by the keyboard.
- NEW-37: a line's Class cell is named for its line ("Class, line 2").
- NEW-39: the drill-down's "n of m" is a status, read with the account.

Skipped, as one module, where playwright or its Chromium is not installed.
"""

import re

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_browser_classes import classed as _classed  # noqa: E402,F401
from tests.test_browser_grid import (  # noqa: E402,F401  (eleven classes)
    BY_CLASS_URL,
    divisions_fixture,
)
from tests.test_browser_report_views import SEPT, _open_at  # noqa: E402
from tests.test_dialog_contrast import (  # noqa: E402,F401  (the dialogs)
    BANKING,
    NONPROFIT_DIALOGS,
    PEOPLE,
    PURCHASES,
    REPORTS,
    SALES,
    SETTINGS,
    nonprofit,
)
from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    _open,
    _visit,
    books_fixture,
    browser_fixture,
    company_fixture,
    settle,
)


@pytest.fixture(name="classed")
def classed_fixture(_classed):  # noqa: F811  (the fixture, by its name)
    return _classed


MODAL_SHOWN = (
    "() => !document.getElementById('modal-overlay').classList.contains('hidden')"
)
TITLE = "() => document.getElementById('modal-title').textContent"

# Every element of the dialog numbered, so a focus can be named exactly.
NUMBER = """() => { const m = document.getElementById('modal');
    [...m.querySelectorAll('*')].forEach((el, i) => { el.dataset.tabProbe = String(i); }); }"""
# Where focus is, as "tag#number", or null once it has left the dialog.
WHERE = """() => { const a = document.activeElement, m = document.getElementById('modal');
    return a && a !== m && m.contains(a) ? `${a.tagName.toLowerCase()}#${a.dataset.tabProbe}` : null; }"""
# The first and the last control of the dialog's body take focus
FIRST = "() => { _tabStops(document.getElementById('modal-body'), null)[0].focus(); }"
LAST = "() => { _tabStops(document.getElementById('modal-body'), null).pop().focus(); }"
CLOSE_X = "() => `button#${document.getElementById('modal-close-btn').dataset.tabProbe}`"
HANDLER_OFF = "() => document.removeEventListener('keydown', modalKeydown)"
HANDLER_ON = "() => document.addEventListener('keydown', modalKeydown)"
SYNTHETIC_TAB = """(shift) => document.activeElement.dispatchEvent(new KeyboardEvent('keydown',
    { key: 'Tab', code: 'Tab', shiftKey: !!shift, bubbles: true, cancelable: true }))"""


def _account(company, number):
    [a] = [
        x for x in company.get("/api/accounts").json() if x["account_number"] == number
    ]
    return a


def _open_dialog(page, handled, call, ready):
    page.evaluate(f"async () => {{ await {call}; }}")
    page.wait_for_function(MODAL_SHOWN, timeout=5000)
    page.wait_for_selector(ready)
    settle(page, handled)


def _press(page, shift=False, synthetic=False):
    """One Tab: a real key (the browser's Tab and the handler together, as
    on Chromium) or a synthetic keydown alone, which moves no focus by
    itself, so the handler is doing all of it (WebKit's case)."""
    if synthetic:
        page.evaluate(SYNTHETIC_TAB, shift)
        page.wait_for_timeout(5)  # a date field's check runs a tick later
    else:
        page.keyboard.press("Shift+Tab" if shift else "Tab")


def _native_walk(page, start, shift=False, cap=600):
    """The sequence the browser's own Tab takes from `start`, with the
    app's handler out of the way, until it leaves the dialog."""
    page.evaluate(HANDLER_OFF)
    try:
        page.evaluate(start)
        seq = [page.evaluate(WHERE)]
        for _ in range(cap):
            page.keyboard.press("Shift+Tab" if shift else "Tab")
            at = page.evaluate(WHERE)
            if at is None:
                break
            seq.append(at)
        else:
            raise AssertionError("the native walk never left the dialog")
    finally:
        page.evaluate(HANDLER_ON)
    return seq


def _walk(page, start, steps, shift=False, synthetic=False):
    """The sequence the handler takes from `start`, `steps` presses on."""
    page.evaluate(start)
    seq = [page.evaluate(WHERE)]
    for _ in range(steps):
        _press(page, shift, synthetic)
        seq.append(page.evaluate(WHERE))
    return seq


DESCRIBE = """(seq) => seq.map(s => { if (!s) return s;
    const el = document.querySelector(`[data-tab-probe="${s.split('#')[1]}"]`);
    return `${s} ${el.type || ''} .${el.className} tabindex=${el.tabIndex} "${(el.getAttribute('aria-label') || el.textContent).trim().slice(0, 30)}"`; })"""


def _same(page, mine, native):
    """The two sequences, element for element, said in full where not."""
    if mine == native:
        return
    i = next(k for k, (a, b) in enumerate(zip(mine, native)) if a != b)
    raise AssertionError(
        f"at {i}: the handler's walk {page.evaluate(DESCRIBE, mine[max(0, i - 2) : i + 3])}"
        f" vs the browser's {page.evaluate(DESCRIBE, native[max(0, i - 2) : i + 3])}"
    )


def _check_walk(page, handled, reverse=True, synthetic=False):
    """Forward from the body's first control, the handler's sequence is
    the browser's own, then wraps to the dialog's Close ×; backward from
    the body's last control, the same, then wraps from the × to the last."""
    page.evaluate(NUMBER)
    native = _native_walk(page, FIRST)
    assert len(native) > 3, native
    _same(page, _walk(page, FIRST, len(native) - 1, synthetic=synthetic), native)
    close = page.evaluate(CLOSE_X)
    _press(page, synthetic=synthetic)
    assert page.evaluate(WHERE) == close
    if not reverse:
        return native
    back_native = _native_walk(page, LAST, shift=True)
    assert back_native[-1] == close, back_native
    _same(
        page,
        _walk(page, LAST, len(back_native) - 1, shift=True, synthetic=synthetic),
        back_native,
    )
    _press(page, shift=True, synthetic=synthetic)
    assert page.evaluate(WHERE) == back_native[0]
    return native


# ── NEW-25: Tab inside a dialog ───────────────────────────────────────────


def test_tab_walks_the_new_invoice_form_as_the_browser_does(browser, company, books):
    page, handled = _open(browser, company)
    try:
        _visit(page, handled, "#/invoices")
        _open_dialog(page, handled, "InvoicesPage.showForm()", "#inv-lines tr")
        native = _check_walk(page, handled)
        kinds = page.evaluate(
            """() => [...document.querySelectorAll('#modal [data-tab-probe]')]
                .filter(el => el.matches('input[type=date], input[type=checkbox], [role=combobox], textarea, select:not(.cbx-select)'))
                .map(el => `${el.tagName.toLowerCase()}#${el.dataset.tabProbe}`)"""
        )
        # the walk took in the date fields (their segments, so each more
        # than once), the type-ahead boxes, a checkbox, the plain selects,
        # the notes; not the selects the type-ahead boxes stand in for
        assert all(k in native for k in kinds), [k for k in kinds if k not in native]
        hidden = page.evaluate(
            "() => [...document.querySelectorAll('#modal select.cbx-select')].map(el => `select#${el.dataset.tabProbe}`)"
        )
        assert hidden and not any(h in native for h in hidden)
        dates = page.evaluate(
            "() => [...document.querySelectorAll('#modal input[type=date]')].map(el => `input#${el.dataset.tabProbe}`)"
        )
        assert dates and all(native.count(d) >= 3 for d in dates), [
            (d, native.count(d)) for d in dates
        ]
    finally:
        page.close()


def test_tab_walks_a_drill_down_and_its_links_as_the_browser_does(
    browser, company, books
):
    cogs = _account(company, "5000")
    url = (
        f"#/reports/account-transactions?account_id={cogs['id']}"
        f"&start_date={SEPT[0]}&end_date={SEPT[1]}&from=trial-balance"
    )
    page, handled = _open_at(browser, company, url)
    try:
        page.wait_for_selector("#drilldown-body table")
        native = _check_walk(page, handled)
        named = page.evaluate(
            """() => [...document.querySelectorAll('#modal [data-tab-probe]')]
                .filter(el => el.matches('#drill-prev, #drill-next, [data-back-to], #report-save-btn, #drilldown-body a[href], #report-custom-start'))
                .map(el => `${el.tagName.toLowerCase()}#${el.dataset.tabProbe}`)"""
        )
        assert len(named) > 5 and all(n in native for n in named), [
            n for n in named if n not in native
        ]
    finally:
        page.close()


def test_tab_walks_the_grid_and_its_cells_as_the_browser_does(
    browser, company, books, divisions
):
    page, handled = _open_at(browser, company, BY_CLASS_URL)
    try:
        page.wait_for_selector("#report-content .pivot-grid")
        native = _check_walk(page, handled, reverse=False)
        named = page.evaluate(
            """() => [...document.querySelectorAll('#modal [data-tab-probe]')]
                .filter(el => el.matches('#grid-scroll, #grid-toolbar [role=combobox], #grid-toolbar button, .pivot-grid a[href], #grid-choose-btn, #grid-empty'))
                .map(el => `${el.tagName.toLowerCase()}#${el.dataset.tabProbe}`)"""
        )
        assert len(named) > 20 and all(n in native for n in named), [
            n for n in named if n not in native
        ]
        # the folded chooser's boxes are not stops; opened, they are
        folded = page.evaluate(
            "() => [...document.querySelectorAll('#grid-chooser input')].map(el => `input#${el.dataset.tabProbe}`)"
        )
        assert folded and not any(f in native for f in folded)
        page.evaluate("() => ReportsPage.toggleChooser()")
        page.wait_for_timeout(50)
        page.evaluate(NUMBER)
        opened = _native_walk(page, FIRST)
        assert _walk(page, FIRST, len(opened) - 1) == opened
        folded = page.evaluate(
            "() => [...document.querySelectorAll('#grid-chooser input')].map(el => `input#${el.dataset.tabProbe}`)"
        )
        assert all(f in opened for f in folded)
    finally:
        page.close()


def test_synthetic_tabs_alone_walk_a_dialog_the_webkit_way(browser, company, books):
    """A keydown the browser does nothing with (WebKit's, under the Mac's
    default setting, for a button or a link) still moves focus along the
    same sequence: the handler does it."""
    cogs = _account(company, "5000")
    page, handled = _open_at(
        browser,
        company,
        f"#/reports/account-transactions?account_id={cogs['id']}&from=trial-balance",
    )
    try:
        page.wait_for_selector("#drilldown-body table")
        assert page.evaluate("() => document.getElementById('report-custom-start').checkVisibility()") is False
        _check_walk(page, handled, synthetic=True)
        # a Tab a control has claimed is left to it
        page.evaluate(FIRST)
        at = page.evaluate(WHERE)
        page.evaluate(
            """() => { const stop = (e) => { if (e.key === 'Tab') e.preventDefault(); };
                document.activeElement.addEventListener('keydown', stop, { once: true }); }"""
        )
        page.evaluate(SYNTHETIC_TAB, False)
        assert page.evaluate(WHERE) == at
        # from the dialog itself (focused by script) Tab goes to its first
        # control, Shift+Tab to its last
        page.evaluate("() => document.getElementById('modal').focus()")
        page.evaluate(SYNTHETIC_TAB, False)
        assert page.evaluate("() => document.activeElement.id") == "modal-close-btn"
        page.evaluate("() => document.getElementById('modal').focus()")
        page.evaluate(SYNTHETIC_TAB, True)
        assert page.evaluate(
            "() => document.activeElement.textContent.trim()"
        ) == "Close"
    finally:
        page.close()


# ── NEW-33: Escape in a date field ────────────────────────────────────────


def test_escape_in_a_date_field_leaves_the_field_and_the_next_closes_the_dialog(
    browser, company, books
):
    page, handled = _open(browser, company)
    try:
        _visit(page, handled, "#/invoices")
        _open_dialog(page, handled, "InvoicesPage.showForm()", "#inv-lines tr")
        page.fill("#modal textarea", "a note worth keeping")
        page.focus("#modal input[type=date]")
        # the key WebKit sends on after closing the calendar (a real one
        # here, with no calendar open, reaches the page the same way)
        page.keyboard.press("Escape")
        assert page.evaluate(MODAL_SHOWN)
        assert page.evaluate("() => document.activeElement.id") == "modal"
        assert page.input_value("#modal textarea") == "a note worth keeping"
        # as a synthetic key at the field (WebKit's, after its calendar)
        page.focus("#modal input[type=date]")
        page.evaluate(
            """() => document.activeElement.dispatchEvent(new KeyboardEvent('keydown',
                { key: 'Escape', code: 'Escape', bubbles: true, cancelable: true }))"""
        )
        assert page.evaluate(MODAL_SHOWN)
        assert page.evaluate("() => document.activeElement.id") == "modal"
        # the next Escape closes the dialog
        page.keyboard.press("Escape")
        page.wait_for_function(f"!({MODAL_SHOWN})()")
        # any other field: one Escape closes it, as before
        _open_dialog(page, handled, "InvoicesPage.showForm()", "#inv-lines tr")
        page.focus("#modal textarea")
        page.keyboard.press("Escape")
        page.wait_for_function(f"!({MODAL_SHOWN})()")
    finally:
        page.close()


# ── NEW-41: the shortcuts by key position; ⌘K ────────────────────────────

KEY = """([key, code, mods]) => document.body.dispatchEvent(new KeyboardEvent('keydown',
    { key, code, bubbles: true, cancelable: true, ...mods }))"""
THEME = "() => document.documentElement.getAttribute('data-theme') || 'light'"


def test_the_alt_shortcuts_go_by_the_keys_position_and_cmd_k_finds(
    browser, company, books
):
    page, handled = _open(browser, company)
    try:
        _visit(page, handled, "#/customers")
        was = page.evaluate(THEME)
        # Option-D on a Mac: the character is "∂", the key is still KeyD
        page.evaluate(KEY, ["∂", "KeyD", {"altKey": True}])
        assert page.evaluate(THEME) != was
        page.evaluate(KEY, ["∂", "KeyD", {"altKey": True}])
        assert page.evaluate(THEME) == was
        # a real Alt+D too
        page.keyboard.press("Alt+KeyD")
        assert page.evaluate(THEME) != was
        page.keyboard.press("Alt+KeyD")
        assert page.evaluate(THEME) == was
        # Ctrl+Alt (AltGr on some layouts) types a character, and is left alone
        page.evaluate(KEY, ["đ", "KeyD", {"altKey": True, "ctrlKey": True}])
        assert page.evaluate(THEME) == was
        # Option-H ("˙") goes home
        page.evaluate(KEY, ["˙", "KeyH", {"altKey": True}])
        page.wait_for_function("() => location.hash === '#/'")
        settle(page, handled)
        # Option-N ("˜") opens a new invoice
        page.evaluate(KEY, ["˜", "KeyN", {"altKey": True}])
        page.wait_for_function(MODAL_SHOWN)
        assert page.evaluate(TITLE).startswith("New Invoice")
        page.evaluate("() => closeModal()")
        # ⌘K finds, as Ctrl+K does
        page.evaluate("() => document.body.focus()")
        page.evaluate(KEY, ["k", "KeyK", {"metaKey": True}])
        assert page.evaluate("() => document.activeElement.id") == "global-search"
        page.evaluate("() => document.body.focus()")
        page.keyboard.press("Control+KeyK")
        assert page.evaluate("() => document.activeElement.id") == "global-search"
    finally:
        page.close()
