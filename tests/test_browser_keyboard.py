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
    NONPROFIT_PAGES,
    PEOPLE,
    PURCHASES,
    REPORTS,
    SALES,
    SETTINGS,
    nonprofit,
)
from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    _open,
    _theme,
    _visit,
    browser_fixture,
    company_fixture,
    contrast,
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
CLOSE_X = (
    "() => `button#${document.getElementById('modal-close-btn').dataset.tabProbe}`"
)
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
    assert len(native) >= 3, native
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
        assert (
            page.evaluate(
                "() => document.getElementById('report-custom-start').checkVisibility()"
            )
            is False
        )
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
        assert (
            page.evaluate("() => document.activeElement.textContent.trim()") == "Close"
        )
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


# ── NEW-30: Back, within the app ──────────────────────────────────────────

BACK = """() => { const b = document.getElementById('back-btn');
    return { disabled: b.disabled, name: b.getAttribute('aria-label'), title: b.title,
             keys: b.getAttribute('aria-keyshortcuts') }; }"""
AT = "(h) => location.hash === h"


def _no_splash(page):
    page.evaluate(
        "() => { const s = document.getElementById('splash'); if (s) s.classList.add('hidden'); }"
    )


def _sidebar(page, handled, href):
    page.click(f'#sidebar a[href="{href}"]')
    page.wait_for_function(AT, arg=href)
    settle(page, handled)


def test_back_goes_back_within_the_app_while_there_is_somewhere_to_go(
    browser, company, books
):
    page, handled = _open(browser, company)
    try:
        _no_splash(page)
        # the session's first page: named, with its shortcut, nowhere to go
        assert page.evaluate(BACK) == {
            "disabled": True,
            "name": "Back",
            "title": "Back (Alt+←)",
            "keys": "Alt+ArrowLeft",
        }
        page.keyboard.press("Alt+ArrowLeft")
        page.wait_for_timeout(100)
        assert page.evaluate("location.hash") == "#/"
        # a sidebar link: an entry the browser made, which Back knows about
        _sidebar(page, handled, "#/customers")
        assert page.evaluate(BACK)["disabled"] is False
        page.keyboard.press("Alt+ArrowLeft")
        page.wait_for_function(AT, arg="#/")
        settle(page, handled)
        assert page.evaluate(BACK)["disabled"] is True
        # the button, and Forward's entry still ahead
        _sidebar(page, handled, "#/vendors")
        page.click("#back-btn")
        page.wait_for_function(AT, arg="#/")
        settle(page, handled)
        assert page.evaluate(BACK)["disabled"] is True
        # a report pushed from the Report Center: Back closes it and returns
        _sidebar(page, handled, "#/reports")
        page.evaluate(
            """() => document.querySelector('#page-content .card[onclick="ReportsPage.profitLoss()"]').click()"""
        )
        page.wait_for_selector("#report-content table")
        settle(page, handled)
        assert page.evaluate("location.hash").startswith("#/reports/profit-loss?")
        assert page.evaluate(BACK)["disabled"] is False
        page.click("#back-btn")
        page.wait_for_function(AT, arg="#/reports")
        page.wait_for_function(f"!({MODAL_SHOWN})()")
        settle(page, handled)
        assert page.evaluate(BACK)["disabled"] is False  # the dashboard is behind
        # a reload keeps the entry's Back
        page.reload()
        page.wait_for_function("window.App && document.readyState === 'complete'")
        _no_splash(page)
        settle(page, handled)
        assert page.evaluate(BACK)["disabled"] is False
        page.keyboard.press("Alt+ArrowLeft")
        page.wait_for_function(AT, arg="#/")
        settle(page, handled)
        assert page.evaluate(BACK)["disabled"] is True
        # on a Mac: ⌘[, said on the button; Alt+← is the Mac's word-left
        page.evaluate("""() => { Object.defineProperty(Navigator.prototype, 'platform',
                { get: () => 'MacIntel', configurable: true }); App.labelBack(); }""")
        assert page.evaluate(BACK)["title"] == "Back (⌘[)"
        assert page.evaluate(BACK)["keys"] == "Meta+["
        _sidebar(page, handled, "#/customers")
        page.keyboard.press("Alt+ArrowLeft")
        page.wait_for_timeout(100)
        assert page.evaluate("location.hash") == "#/customers"
        page.keyboard.press("Meta+BracketLeft")
        page.wait_for_function(AT, arg="#/")
    finally:
        page.close()


# ── NEW-32: no dialog opens on Void or Delete ────────────────────────────

# What has focus: its tag, its words, and whether it undoes something
FOCUSED = """() => { const a = document.activeElement;
    return { id: a.id || '', tag: a.tagName.toLowerCase(), text: a.textContent.trim().slice(0, 40),
             destructive: a.hasAttribute('data-destructive') }; }"""
DESTRUCTIVE = re.compile(r"^(void|delete|remove)\b", re.I)


def _opens_safely(page, handled, books, groups):
    """Every dialog of `groups` opened as the app opens it: the control
    focused is never one that undoes. Returns what was focused per dialog."""
    focused, offenders, unopened = {}, [], []
    for route, openers in groups:
        _visit(page, handled, route.format(**books))
        for opener in openers:
            call = opener.format(**books)
            page.evaluate("() => closeModal()")
            try:
                page.evaluate(f"async () => {{ await {call}; }}")
                page.wait_for_function(MODAL_SHOWN, timeout=5000)
            except (
                Exception
            ) as exc:  # the contrast sweep reports a dialog that won't open
                unopened.append((call, str(exc)[:120]))
                continue
            settle(page, handled)
            at = page.evaluate(FOCUSED)
            focused[call] = at
            if at["destructive"] or DESTRUCTIVE.match(at["text"]):
                offenders.append((call, at))
        page.evaluate("() => closeModal()")
    assert not offenders, offenders
    return focused, unopened


def test_no_dialog_opens_with_focus_on_void_or_delete(browser, company, books):
    groups = [
        ("#/invoices", SALES),
        ("#/bills", PURCHASES),
        ("#/banking/{checking}", BANKING),
        ("#/reports", REPORTS),
        ("#/employees", PEOPLE),
        ("#/settings", SETTINGS),
    ]
    page, handled = _open(browser, company)
    confirms = []
    page.on("dialog", lambda d: (confirms.append(d.message), d.dismiss()))
    try:
        # the three the gate named open on Void: the dialog itself takes
        # focus, named by its title, and Return there does nothing
        _visit(page, handled, "#/journal")
        for call in (
            f"JournalPage.view({books['journal']})",
            f"DepositsPage.view({books['deposit']})",
            f"JobCostsPage.view({books['job_cost']})",
        ):
            page.evaluate("() => closeModal()")
            page.evaluate(f"async () => {{ await {call}; }}")
            page.wait_for_function(MODAL_SHOWN)
            settle(page, handled)
            assert page.evaluate(FOCUSED)["id"] == "modal", (
                call,
                page.evaluate(FOCUSED),
            )
            assert (
                page.evaluate(
                    "() => document.activeElement.getAttribute('aria-labelledby')"
                )
                == "modal-title"
            )
            assert page.locator("#modal-body [data-destructive]").count() == 1
            page.keyboard.press("Enter")
            page.wait_for_timeout(100)
            assert page.evaluate(MODAL_SHOWN) and not confirms
            # Tab from there: the dialog's Close ×, then Void, then Close
            page.keyboard.press("Tab")
            assert page.evaluate("() => document.activeElement.id") == "modal-close-btn"
        # a dialog whose first control is harmless keeps it
        page.evaluate("() => closeModal()")
        page.evaluate("async () => { await InvoicesPage.showForm(); }")
        page.wait_for_function(MODAL_SHOWN)
        settle(page, handled)
        assert page.evaluate(FOCUSED)["id"] != "modal"
        # and every dialog the app opens (the last of them as a read-only
        # sign-in sees it, which is how the sweep leaves the page)
        focused, unopened = _opens_safely(page, handled, books, groups)
        assert len(focused) >= 100, (len(focused), unopened)
    finally:
        page.close()


def test_a_nonprofits_dialogs_open_safely_too(
    browser, client, nonprofit  # noqa: F811  (the fixture, imported above)
):
    page, handled = _open(browser, client)
    try:
        for route in NONPROFIT_PAGES:  # the pages load what their dialogs need
            _visit(page, handled, route.format(**nonprofit))
        focused, unopened = _opens_safely(
            page, handled, nonprofit, [("#/invoices", NONPROFIT_DIALOGS)]
        )
        assert len(focused) == len(NONPROFIT_DIALOGS), unopened
        views = [
            c
            for c in focused
            if re.search(r"(Releases|Allocations|InKind)Page\.view\(", c)
        ]
        assert len(views) == 3, views
        assert all(focused[c]["id"] == "modal" for c in views), {
            c: focused[c] for c in views
        }
    finally:
        page.close()


# ── NEW-38: the customer page's invoice rows are links ───────────────────


def test_the_customer_pages_invoice_rows_open_from_the_keyboard(
    browser, company, books
):
    page, handled = _open_at(browser, company, f"#/customers/{books['customer']}")
    try:
        page.wait_for_function(MODAL_SHOWN)
        settle(page, handled)
        links = page.evaluate(
            """() => [...document.querySelectorAll('#modal a[href^="#/invoices/"]')]
                .map(a => [a.getAttribute('href'), a.textContent.trim()])"""
        )
        assert len(links) >= 3, links
        href, text = links[0]
        inv = company.get(f"/api/invoices/{href.rsplit('/', 1)[1]}").json()
        assert text == inv["invoice_number"]  # named by the number
        # Enter on the link opens the invoice at its address; Back returns
        page.focus(f'#modal a[href="{href}"]')
        page.keyboard.press("Enter")
        page.wait_for_function(AT, arg=href)
        page.wait_for_function(
            f"() => document.getElementById('modal-title').textContent.includes('#{inv['invoice_number']}')"
        )
        settle(page, handled)
        page.go_back()
        page.wait_for_function(AT, arg=f"#/customers/{books['customer']}")
        page.wait_for_function(MODAL_SHOWN)
        settle(page, handled)
        assert page.locator(f'#modal a[href="{href}"]').count() == 1
        # and the link left has the focus back (review: as a report's row)
        assert (
            page.evaluate("() => document.activeElement.dataset.rowKey")
            == f"invoice:{inv['id']}"
        )
        # the row's own click still opens it
        page.click(
            f'#modal a[href="{href}"] >> xpath=ancestor::tr',
            position={"x": 300, "y": 8},
        )
        page.wait_for_function(AT, arg=href)
        page.go_back()
        page.wait_for_function(MODAL_SHOWN)
        settle(page, handled)
        # a payment row the same: its date is the link, and opens the payment
        # at its own address; Back returns to the page, focus on the link
        pay = page.locator('#modal a[href^="#/payments/"]').first
        assert pay.count() == 1 and pay.text_content().strip()
        pay_href = pay.get_attribute("href")
        pay.focus()
        page.keyboard.press("Enter")
        page.wait_for_function(AT, arg=pay_href)
        page.wait_for_function(f"() => {TITLE.split('=> ')[1]} === 'Payment Details'")
        settle(page, handled)
        page.go_back()
        page.wait_for_function(AT, arg=f"#/customers/{books['customer']}")
        page.wait_for_function(MODAL_SHOWN)
        settle(page, handled)
        assert (
            page.evaluate("() => document.activeElement.getAttribute('href')")
            == pay_href
        )
    finally:
        page.close()


# ── NEW-37: a line's Class cell is named for its line ────────────────────

NAMES = "(sel) => [...document.querySelectorAll(sel)].map(el => el.getAttribute('aria-label'))"


def test_a_lines_class_cell_says_its_line(browser, company, books, classed):
    page, handled = _open(browser, company)
    try:
        _visit(page, handled, "#/bills")
        _open_dialog(page, handled, "BillsPage.showForm()", "#bill-lines tr")
        assert page.evaluate(NAMES, "#bill-lines .line-function-fund") == [
            "Class, line 1"
        ]
        page.evaluate("() => BillsPage.addLine()")
        settle(page, handled)
        assert page.evaluate(NAMES, "#bill-lines .line-function-fund") == [
            "Class, line 1",
            "Class, line 2",
        ]
        # as a screen reader finds them: one each
        assert page.get_by_label("Class, line 2").count() == 1
        page.evaluate("() => closeModal()")
        _visit(page, handled, "#/invoices")
        _open_dialog(page, handled, "InvoicesPage.showForm()", "#inv-lines tr")
        page.evaluate("() => InvoicesPage.addLine()")
        settle(page, handled)
        assert page.evaluate(NAMES, "#inv-lines .line-class-fund") == [
            "Class, line 1",
            "Class, line 2",
        ]
        page.evaluate("() => closeModal()")
        _visit(page, handled, "#/journal")
        _open_dialog(page, handled, "JournalPage.showForm()", "#je-lines tr")
        assert page.evaluate(NAMES, "#je-lines .je-function-fund") == [
            "Class, line 1",
            "Class, line 2",
        ]
    finally:
        page.close()


def test_a_nonprofits_fund_and_function_cells_say_their_line(
    browser, client, nonprofit  # noqa: F811  (the fixture, imported above)
):
    page, handled = _open(browser, client)
    try:
        _visit(page, handled, "#/journal")
        _open_dialog(page, handled, "JournalPage.showForm()", "#je-lines tr")
        heads = page.evaluate(
            "() => [...document.querySelectorAll('#modal .line-items-table thead th')].map(t => t.textContent.trim())"
        )
        fund = heads[
            heads.index("Function") - 1
        ]  # the class column, by the nonprofit's word
        assert page.evaluate(NAMES, "#je-lines .je-function-fund") == [
            f"{fund}, line 1",
            f"{fund}, line 2",
        ]
        assert page.evaluate(NAMES, "#je-lines select.je-function") == [
            "Function, line 1",
            "Function, line 2",
        ]
    finally:
        page.close()


# ── NEW-39: the drill-down's "n of m" is a status ────────────────────────


def test_the_drill_downs_position_is_a_status_that_names_the_account(
    browser, company, books
):
    checking = _account(company, "1000")
    url = (
        f"#/reports/account-transactions?account_id={checking['id']}"
        f"&start_date={SEPT[0]}&end_date={SEPT[1]}&from=trial-balance"
    )
    page, handled = _open_at(browser, company, url)
    try:
        page.wait_for_selector("#drilldown-body table")
        pos = page.locator("#drill-position")
        assert pos.get_attribute("role") == "status"
        assert pos.get_attribute("aria-live") == "polite"
        where = pos.text_content().strip()
        m = re.fullmatch(r"(\d+) of (\d+): (.+)", where)
        assert m and m.group(3).endswith(checking["name"]), where
        n, total = int(m.group(1)), int(m.group(2))
        assert total > 3

        def step(button):
            was = pos.text_content()
            page.focus(button)
            page.keyboard.press("Enter")
            page.wait_for_function(
                "(was) => document.getElementById('drill-position').textContent !== was",
                arg=was,
            )
            settle(page, handled)
            return pos.text_content().strip()

        # Next, by keyboard: focus stays on Next, the status says where
        after = step("#drill-next")
        m2 = re.fullmatch(r"(\d+) of (\d+): (.+)", after)
        assert m2 and int(m2.group(1)) == n + 1 and int(m2.group(2)) == total, after
        assert page.evaluate("() => document.activeElement.id") == "drill-next"
        assert m2.group(3).split(" - ", 1)[-1] in page.evaluate(TITLE)  # its name
        assert page.get_by_role("status").filter(has_text=after).count() == 1
        # at the last account Next is disabled: Prev takes the focus, so
        # the keyboard keeps its place (and Next again from the first)
        page.select_option(
            "#drill-account",
            page.eval_on_selector_all(
                "#drill-account option", "os => os[os.length - 2].value"
            ),
        )
        settle(page, handled)
        last = step("#drill-next")
        assert last.startswith(f"{total} of {total}: "), last
        assert page.evaluate("() => document.activeElement.id") == "drill-prev"
        assert page.locator("#drill-next").is_disabled()
    finally:
        page.close()


# ── Review, round 2: the Alt letters inside a field ──────────────────────

KEY_AT = """([sel, key, code, mods]) => document.querySelector(sel).dispatchEvent(new KeyboardEvent('keydown',
    { key, code, bubbles: true, cancelable: true, ...mods }))"""
MAC = """(on) => { Object.defineProperty(Navigator.prototype, 'platform',
    { get: () => on ? 'MacIntel' : 'Linux x86_64', configurable: true }); App.labelBack(); }"""


def test_inside_a_field_an_alt_letter_is_the_plain_letter_alone(
    browser, company, books
):
    """A Mac's Option types a character in a field ("∂", or a dead key for
    Option-N's tilde): it goes through, and no shortcut fires. The plain
    letter with Alt (Windows, Linux) fires as before; outside a field the
    key's position is enough; Shift makes it another shortcut."""
    page, handled = _open(browser, company)
    try:
        _no_splash(page)
        _visit(page, handled, "#/invoices")
        _open_dialog(page, handled, "InvoicesPage.showForm()", "#inv-lines tr")
        page.fill("#modal textarea", "a note being typed")
        page.focus("#modal textarea")
        was = page.evaluate(THEME)
        # Option-N in the Notes: the tilde's dead key, not a new invoice
        page.evaluate(KEY_AT, ["#modal textarea", "Dead", "KeyN", {"altKey": True}])
        page.wait_for_timeout(100)
        assert page.input_value("#modal textarea") == "a note being typed"
        assert page.evaluate("() => document.activeElement.tagName") == "TEXTAREA"
        # Option-D in the Notes types "∂": no theme change
        page.evaluate(KEY_AT, ["#modal textarea", "∂", "KeyD", {"altKey": True}])
        assert page.evaluate(THEME) == was
        # Shift+Alt+D anywhere is not the shortcut either
        page.evaluate(KEY, ["D", "KeyD", {"altKey": True, "shiftKey": True}])
        assert page.evaluate(THEME) == was
        # the plain letter with Alt, as Windows and Linux send it, fires
        # from a field: the form is opened afresh (its default note back)
        page.evaluate(KEY_AT, ["#modal textarea", "n", "KeyN", {"altKey": True}])
        page.wait_for_function(
            "() => document.querySelector('#modal textarea').value !== 'a note being typed'"
        )
        settle(page, handled)
        assert page.evaluate(TITLE).startswith("New Invoice")
        page.evaluate("() => closeModal()")
        # outside a field the key's position is enough, dead key or not
        page.evaluate("() => document.body.focus()")
        page.evaluate(KEY, ["Dead", "KeyN", {"altKey": True}])
        page.wait_for_function(MODAL_SHOWN)
        assert page.evaluate(TITLE).startswith("New Invoice")
        page.evaluate("() => closeModal()")
        # on a Mac, ⌘⌥[ is not Back; ⌘[ is
        _sidebar(page, handled, "#/customers")
        page.evaluate(MAC, True)
        page.evaluate(KEY, ["[", "BracketLeft", {"metaKey": True, "altKey": True}])
        page.wait_for_timeout(100)
        assert page.evaluate("location.hash") == "#/customers"
        page.evaluate(KEY, ["[", "BracketLeft", {"metaKey": True}])
        page.wait_for_function(AT, arg="#/invoices")  # the page before Customers
        page.evaluate(MAC, False)
    finally:
        page.close()


# ── Review, round 2: Tab into a textarea keeps the caret ─────────────────

BEFORE = """(sel) => { const m = document.getElementById('modal'), el = document.querySelector(sel);
    const stops = _tabStops(m, null); stops[stops.indexOf(el) - 1].focus(); }"""
SELECTION = "(sel) => { const el = document.querySelector(sel); return [el.selectionStart, el.selectionEnd, el.value.length]; }"


def test_tab_into_a_textarea_keeps_the_caret_and_into_a_text_box_selects(
    browser, company, books
):
    page, handled = _open(browser, company)
    try:
        _visit(page, handled, "#/invoices")
        _open_dialog(page, handled, "InvoicesPage.showForm()", "#inv-lines tr")
        page.fill("#modal textarea", "two lines\nof notes")
        page.fill("#modal .line-desc", "Rounding probe")
        # the handler's Tab into the notes: no selection (the browser's own
        # Tab selects nothing in a textarea, and a note must not vanish)
        page.evaluate(BEFORE, "#modal textarea")
        page.evaluate(SYNTHETIC_TAB, False)
        assert page.evaluate("() => document.activeElement.tagName") == "TEXTAREA"
        start, end, _ = page.evaluate(SELECTION, "#modal textarea")
        assert start == end
        # into a text box, its words selected, as the browser's Tab has it
        page.evaluate(BEFORE, "#modal .line-desc")
        page.evaluate(SYNTHETIC_TAB, False)
        assert page.evaluate("() => document.activeElement.className") == "line-desc"
        assert page.evaluate(SELECTION, "#modal .line-desc") == [0, 14, 14]
    finally:
        page.close()


# ── Review, round 2: Back is inert over a form ───────────────────────────

AT_POINT = """() => { const b = document.getElementById('back-btn'), r = b.getBoundingClientRect();
    return document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === b; }"""


def test_back_is_inert_over_a_form_but_live_over_an_addressed_dialog(
    browser, company, books
):
    page, handled = _open(browser, company)
    try:
        _no_splash(page)
        _sidebar(page, handled, "#/invoices")
        assert page.evaluate(AT_POINT) and page.evaluate("() => App.backAllowed()")
        # a plain form over the page: the button is under the overlay, the
        # chord does nothing, and the note typed stays
        _open_dialog(page, handled, "InvoicesPage.showForm()", "#inv-lines tr")
        page.fill("#modal textarea", "half typed")
        assert not page.evaluate(AT_POINT)
        assert page.evaluate("() => App.editingDialog() && !App.backAllowed()")
        assert not page.evaluate(BACK)["disabled"]  # somewhere to go, still
        page.keyboard.press("Alt+ArrowLeft")
        page.wait_for_timeout(150)
        assert page.evaluate("location.hash") == "#/invoices"
        assert page.evaluate(MODAL_SHOWN)
        assert page.input_value("#modal textarea") == "half typed"
        page.evaluate(MAC, True)
        page.keyboard.press("Meta+BracketLeft")
        page.wait_for_timeout(150)
        assert page.evaluate("location.hash") == "#/invoices" and page.evaluate(
            MODAL_SHOWN
        )
        page.evaluate(MAC, False)
        # the form closed, Back is back
        page.evaluate("() => closeModal()")
        assert page.evaluate(AT_POINT) and page.evaluate("() => App.backAllowed()")
        # a report view has its own address: the button is above the
        # overlay and takes the report back to the Report Center
        _sidebar(page, handled, "#/reports")
        page.evaluate(
            """() => document.querySelector('#page-content .card[onclick="ReportsPage.profitLoss()"]').click()"""
        )
        page.wait_for_selector("#report-content table")
        settle(page, handled)
        assert page.evaluate(AT_POINT) and not page.evaluate(
            "() => App.editingDialog()"
        )
        page.click("#back-btn")
        page.wait_for_function(AT, arg="#/reports")
        page.wait_for_function(f"!({MODAL_SHOWN})()")
        # a customer's page has one too; a form opened over it has none
        _visit(page, handled, f"#/customers/{books['customer']}")
        page.wait_for_function(MODAL_SHOWN)
        assert page.evaluate(AT_POINT)
        _open_dialog(
            page, handled, f"CustomersPage.showForm({books['customer']})", "#modal form"
        )
        assert not page.evaluate(AT_POINT) and page.evaluate(
            "() => App.editingDialog()"
        )
        page.keyboard.press("Alt+ArrowLeft")
        page.wait_for_timeout(150)
        assert page.evaluate("location.hash") == f"#/customers/{books['customer']}"
        assert page.evaluate(MODAL_SHOWN)
        page.evaluate("() => closeModal()")
        # dismissing the form dismissed the page it stood in for (one modal):
        # the list's address is on the bar (NEW-23); the page again, then a
        # document at its address: live, and Back returns to the page before
        assert page.evaluate("location.hash") == "#/customers"
        _visit(page, handled, f"#/customers/{books['customer']}")
        page.wait_for_function(MODAL_SHOWN)
        _visit(page, handled, f"#/invoices/{books['sent']}")
        page.wait_for_function(MODAL_SHOWN)
        settle(page, handled)
        assert page.evaluate(AT_POINT) and page.evaluate("() => App.backAllowed()")
        page.keyboard.press("Alt+ArrowLeft")
        page.wait_for_function(AT, arg=f"#/customers/{books['customer']}")
    finally:
        page.close()


# ── Review, round 2: the button is never lit with nowhere to go ──────────

CONSISTENT = "() => document.getElementById('back-btn').disabled === !App.canGoBack()"


def test_a_replaced_address_keeps_the_entrys_state_and_back_follows(
    browser, company, books
):
    page, handled = _open(browser, company)
    page.on("dialog", lambda d: d.dismiss())
    try:
        _no_splash(page)
        _sidebar(page, handled, "#/reports")
        # a report nobody registered: the address falls back to the Report
        # Center's, and the entry keeps where it was pushed from
        _visit(page, handled, "#/reports/nonsense")
        page.wait_for_function(AT, arg="#/reports")
        assert page.evaluate("() => history.state.from") == "#/reports"
        assert page.evaluate("() => App.canGoBack()") and page.evaluate(CONSISTENT)
        # the Settings leave guard, declined: the address put back keeps the
        # entry's state, and the button follows what is behind
        _sidebar(page, handled, "#/settings")
        assert page.evaluate(CONSISTENT)
        dirty = page.evaluate(
            """() => { const i = document.querySelector('#page-content input[type=text], #page-content input:not([type])');
                i.value += ' x'; i.dispatchEvent(new Event('input', { bubbles: true })); return SettingsPage.isDirty(); }"""
        )
        assert dirty
        page.click('#sidebar a[href="#/customers"]')  # the confirm is declined
        page.wait_for_function(AT, arg="#/settings")
        settle(page, handled)
        assert page.evaluate("() => SettingsPage.isDirty()")
        assert page.evaluate(CONSISTENT)
    finally:
        page.close()


def test_the_first_page_at_a_report_that_cannot_open_has_nowhere_to_go(
    browser, company, books
):
    page, handled = _open_at(browser, company, "#/reports/nonsense")
    try:
        page.wait_for_function(AT, arg="#/reports")
        settle(page, handled)
        assert page.evaluate("() => history.state.from") is None
        assert not page.evaluate("() => App.canGoBack()") and page.evaluate(CONSISTENT)
    finally:
        page.close()


# ── Review, round 2: a radio group is one stop, as the browser has it ────

RADIOS = """(checked) => { const body = document.getElementById('modal-body');
    body.insertAdjacentHTML('afterbegin', `<fieldset id="rg"><legend>Choice</legend>
        <label><input type="radio" name="rg" value="a"> a</label>
        <label><input type="radio" name="rg" value="b"> b</label>
        <label><input type="radio" name="rg" value="c"> c</label></fieldset>`);
    if (checked) body.querySelector(`#rg input[value="${checked}"]`).checked = true; }"""


def test_a_radio_group_is_one_stop_as_the_browser_has_it(browser, company, books):
    """None checked: Tab and Shift+Tab land on the group's first radio, and
    leave the group from any of its own; one checked: that one alone. The
    walk is checked against Chromium's native Tab, as the other dialogs."""
    page, handled = _open(browser, company)
    try:
        _visit(page, handled, "#/journal")
        _open_dialog(
            page, handled, f"JournalPage.view({books['journal']})", "#modal-body"
        )
        page.evaluate(RADIOS, None)
        native = _check_walk(page, handled)
        radios = page.evaluate(
            "() => [...document.querySelectorAll('#rg input')].map(el => `input#${el.dataset.tabProbe}`)"
        )
        assert radios[0] in native and not any(r in native for r in radios[1:]), native
        # from the group's second radio (a click lands there) Tab leaves the group
        page.evaluate("() => document.querySelector('#rg input[value=\"b\"]').focus()")
        page.evaluate(SYNTHETIC_TAB, False)
        assert page.evaluate(WHERE) not in radios
        # one checked: that one is the stop
        page.evaluate("() => closeModal()")
        _open_dialog(
            page, handled, f"JournalPage.view({books['journal']})", "#modal-body"
        )
        page.evaluate(RADIOS, "b")
        native = _check_walk(page, handled)
        radios = page.evaluate(
            "() => [...document.querySelectorAll('#rg input')].map(el => `input#${el.dataset.tabProbe}`)"
        )
        assert (
            radios[1] in native and radios[0] not in native and radios[2] not in native
        )
    finally:
        page.close()


# ── Review, round 3: Back is live over every report view ─────────────────

VIEW_STATE = """() => ({ shown: !document.getElementById('modal-overlay').classList.contains('hidden'),
    mark: document.getElementById('modal').dataset.address || null, hash: location.hash,
    allowed: App.backAllowed(), editing: App.editingDialog() })"""


def _views_live(page, handled):
    """Every registered view opened by its own call, as its Report Center
    card does: each that shows a dialog has its address as the dialog's
    mark, and Back live over it. Returns the views shown, and the silent."""
    live, silent = [], []
    for name in page.evaluate("() => Object.keys(ReportsPage._VIEWS)"):
        page.evaluate("() => closeModal()")
        err = page.evaluate(
            "async (n) => { try { await ReportsPage._VIEWS[n].open({}); return null; } catch (e) { return String(e); } }",
            name,
        )
        settle(page, handled)
        state = page.evaluate(VIEW_STATE)
        if not state["shown"]:
            silent.append((name, err))
            continue
        assert state["mark"] == state["hash"], (name, state, err)
        assert state["allowed"] and not state["editing"], (name, state, err)
        live.append(name)
    page.evaluate("() => closeModal()")
    return live, silent


def test_back_is_live_over_every_report_view_the_company_has(browser, company, books):
    """Including the views that put their address on the bar before they
    open (the statement picker, the 1099 summary, the fixed-asset
    reconciliation), where openModal used to clear the mark."""
    page, handled = _open(browser, company)
    try:
        _no_splash(page)
        _sidebar(page, handled, "#/reports")
        live, silent = _views_live(page, handled)
        for name in (
            "profit-loss",
            "customer-statement",
            "1099-summary",
            "fixed-asset-reconciliation",
            "profit-loss-by-class",
            "general-ledger",
        ):
            assert name in live, (name, silent)
        assert len(live) > 10, (live, silent)
    finally:
        page.close()


def test_back_is_live_over_a_nonprofits_report_views_too(
    browser, client, nonprofit  # noqa: F811  (the fixture, imported above)
):
    page, handled = _open(browser, client)
    try:
        _no_splash(page)
        _sidebar(page, handled, "#/reports")
        live, silent = _views_live(page, handled)
        assert "giving-statements" in live, (live, silent)
    finally:
        page.close()


# ── Review, round 3: a declined leave from Settings ──────────────────────

EDIT = """() => { const i = document.querySelector('#page-content input[type=text], #page-content input:not([type])');
    i.value += ' x'; i.dispatchEvent(new Event('input', { bubbles: true })); return i.value; }"""
VALUE = "() => document.querySelector('#page-content input[type=text], #page-content input:not([type])').value"


def test_a_declined_leave_from_settings_stays_on_its_entry_and_back_goes_behind(
    browser, company, books
):
    page, handled = _open(browser, company)
    answer, confirms = {"accept": False}, []
    page.on(
        "dialog",
        lambda d: (
            confirms.append(d.message),
            d.accept() if answer["accept"] else d.dismiss(),
        ),
    )

    def declined(n):
        for _ in range(100):
            if len(confirms) >= n:
                break
            page.wait_for_timeout(50)
        assert len(confirms) == n, confirms
        page.wait_for_function("() => location.hash === '#/settings' && !App._stay")
        settle(page, handled)

    try:
        _no_splash(page)
        _sidebar(page, handled, "#/reports")
        _sidebar(page, handled, "#/settings")
        edited = page.evaluate(EDIT)
        assert page.evaluate("() => SettingsPage.isDirty()")
        # a sidebar link, declined: the Settings entry itself again, the
        # edits untouched (no re-render), Back lit, the Report Center behind
        page.click('#sidebar a[href="#/customers"]')
        declined(1)
        assert (
            page.evaluate("() => SettingsPage.isDirty()")
            and page.evaluate(VALUE) == edited
        )
        assert page.evaluate("() => history.state.from") == "#/reports"
        assert (
            page.evaluate("() => App.canGoBack()")
            and not page.evaluate(BACK)["disabled"]
        )
        # a Back declined: the move went behind, so the way back is forward
        page.click("#back-btn")
        declined(2)
        assert (
            page.evaluate("() => SettingsPage.isDirty()")
            and page.evaluate(VALUE) == edited
        )
        assert page.evaluate("() => history.state.from") == "#/reports"
        assert (
            page.evaluate("() => App.canGoBack()")
            and not page.evaluate(BACK)["disabled"]
        )
        # Back then goes to the page that was behind, the leave confirmed
        answer["accept"] = True
        page.click("#back-btn")
        page.wait_for_function(AT, arg="#/reports")
        settle(page, handled)
        assert len(confirms) == 3
        assert page.locator("#page-content .card-grid .card").count() > 5
    finally:
        page.close()


# ── Round 3, NEW-42: Back is a bordered gold button that reads "← Back" ──

# The button as drawn: its words, and the computed colour, ground, border
# and opacity the sweep would read.
LOOKS = """() => { const b = document.getElementById('back-btn'), cs = getComputedStyle(b);
    return { text: b.textContent.trim(), disabled: b.disabled, color: cs.color,
             background: cs.backgroundColor, opacity: cs.opacity,
             border: [cs.borderTopWidth, cs.borderTopStyle, cs.borderTopColor].join(' ') }; }"""
# the brand's gold, each theme's own (--qb-gold)
GOLD = {"light": "rgb(204, 153, 51)", "dark": "rgb(224, 168, 64)"}
NONE = "rgba(0, 0, 0, 0)"  # a transparent border or ground, as computed


def test_back_is_a_bordered_gold_button_that_is_never_grey_while_it_works(
    browser, company, books
):
    """The ← was a bare grey glyph that got its border on hover alone, and
    disabled it was the same glyph dimmed; with a card open the owner read
    it as unusable, an arrow pointing at the brand (macOS gate, round 2).
    Lit, it is a bordered gold button reading "← Back" in both themes, its
    words AA against its own ground and the border gold under the pointer
    too; with nowhere to go it is muted and borderless, and still named."""
    page, handled = _open(browser, company)
    try:
        _no_splash(page)
        rest = page.evaluate(LOOKS)
        assert rest["text"] == "← Back" and rest["disabled"]
        assert rest["border"].endswith(NONE) and rest["background"] == NONE
        assert float(rest["opacity"]) < 1
        assert page.evaluate(BACK)["name"] == "Back"
        _sidebar(page, handled, "#/customers")
        for theme in ("light", "dark"):
            _theme(page, theme)
            lit = page.evaluate(LOOKS)
            assert lit["text"] == "← Back" and not lit["disabled"]
            assert lit["border"] == f"2px solid {GOLD[theme]}", (theme, lit)
            assert lit["opacity"] == "1" and lit["background"] != NONE
            assert contrast(lit["color"], lit["background"]) >= 4.5, (theme, lit)
            # not the bar's grey: the navy on a pale gold tint, or the gold
            assert (
                lit["color"]
                == {"light": "rgb(0, 51, 102)", "dark": GOLD["dark"]}[theme]
            ), (theme, lit)
            page.hover("#back-btn")
            hovered = page.evaluate(LOOKS)
            assert hovered["border"] not in (
                "1px solid rgb(176, 184, 200)",  # .tb-btn:hover, light
                "2px solid rgb(176, 184, 200)",
                "2px solid rgb(74, 78, 88)",  # .tb-btn:hover, dark
            ), (theme, hovered)
            assert hovered["border"].startswith("2px solid ")
            assert contrast(hovered["color"], hovered["background"]) >= 4.5, hovered
            page.mouse.move(0, 0)
        _theme(page, "light")
        # over a plain form it sits under the overlay, as before
        _open_dialog(page, handled, "CustomersPage.showForm()", "#modal form")
        assert not page.evaluate(AT_POINT)
        page.evaluate("() => closeModal()")
        assert page.evaluate(AT_POINT)
        # Back: nowhere to go, and the muted, borderless look is back
        page.keyboard.press("Alt+ArrowLeft")
        page.wait_for_function(AT, arg="#/")
        settle(page, handled)
        rest = page.evaluate(LOOKS)
        assert rest["disabled"] and rest["border"].endswith(NONE)
        assert rest["background"] == NONE and float(rest["opacity"]) < 1
    finally:
        page.close()


# ── Round 3, NEW-43: the keyboard's place is visible on links and buttons ──

# Where focus is, and the ring drawn there: the computed outline, and
# whether the browser counts this focus as the keyboard's.
RING = """() => { const a = document.activeElement, cs = getComputedStyle(a);
    return { at: a.dataset.rowKey || a.id || a.getAttribute('href') || a.tagName.toLowerCase(),
             tag: a.tagName.toLowerCase(), offset: cs.outlineOffset,
             outline: [cs.outlineWidth, cs.outlineStyle, cs.outlineColor].join(' '),
             keyboard: a.matches(':focus-visible') }; }"""
# a button's colours fade (transition: all 0.1s): the ring is read settled
SETTLED = "() => document.getAnimations().forEach(a => a.finish())"


def _tab_until(page, test, cap=40, shift=False):
    for _ in range(cap):
        page.keyboard.press("Shift+Tab" if shift else "Tab")
        if page.evaluate(test):
            page.evaluate(SETTLED)
            return page.evaluate(RING)
    raise AssertionError(f"Tab never reached {test}")


def test_tab_shows_where_it_is_on_a_report_row_and_a_mouse_click_draws_no_ring(
    browser, company, books
):
    """style.css had no focus style for links or buttons, and WebKit draws
    no ring on a link with the Mac's keyboard navigation off: the owner
    tabbed through A/R Aging and never saw the customer names take focus
    (macOS gate, round 2). Now every control draws the skip link's ring,
    2px of the brand's gold with an offset, in both themes — on keyboard
    focus only."""
    page, handled = _open_at(
        browser, company, "#/reports/ar-aging?as_of_date=2026-09-30"
    )
    try:
        page.wait_for_function(MODAL_SHOWN)
        page.wait_for_selector('#modal a[data-row-key^="customer:"]')
        settle(page, handled)
        page.evaluate(FIRST)
        row = _tab_until(
            page,
            "() => (document.activeElement.dataset.rowKey || '').startsWith('customer:')",
        )
        assert row["tag"] == "a" and row["keyboard"], row
        for theme in ("light", "dark"):
            _theme(page, theme)
            on = page.evaluate(RING)
            assert on["outline"] == f"2px solid {GOLD[theme]}", (theme, on)
            assert on["offset"] == "2px", (theme, on)
        # a button before the table the same: Apply Late Fees, Email All
        # Overdue, Send Collection Letters
        button = _tab_until(
            page, "() => document.activeElement.tagName === 'BUTTON'", shift=True
        )
        assert button["keyboard"] and button["outline"] == f"2px solid {GOLD['dark']}"
        _theme(page, "light")
        page.evaluate(SETTLED)
        assert page.evaluate(RING)["outline"] == f"2px solid {GOLD['light']}"
        # the dialog closed from the keyboard; a mouse click on a button:
        # focus, and no ring
        page.keyboard.press("Escape")
        page.wait_for_function(f"!({MODAL_SHOWN})()")
        page.click("#theme-toggle")
        page.evaluate(SETTLED)
        clicked = page.evaluate(RING)
        assert clicked["at"] == "theme-toggle" and not clicked["keyboard"], clicked
        assert "none" in clicked["outline"], clicked
        page.click("#theme-toggle")  # light again
        # a link clicked: the same; the next Tab from it draws the ring
        page.click('#sidebar a[href="#/customers"]')
        page.wait_for_function(AT, arg="#/customers")
        settle(page, handled)
        page.evaluate(SETTLED)
        link = page.evaluate(RING)
        assert link["at"] == "#/customers" and not link["keyboard"], link
        assert "none" in link["outline"], link
        page.keyboard.press("Tab")
        page.evaluate(SETTLED)
        after = page.evaluate(RING)
        assert after["keyboard"] and after["outline"] == f"2px solid {GOLD['light']}"
    finally:
        page.close()


# ── Round 3, NEW-44: leaving a page's Notes box as it was writes nothing ─


@pytest.mark.parametrize(
    ("kind", "box"), [("customers", "cust-notes"), ("vendors", "vend-notes")]
)
def test_a_tab_through_a_page_writes_no_note_and_a_change_saves_once(
    browser, company, books, kind, box
):
    """The customer page's Notes box saved on every blur, changed or not,
    and so did the vendor page's: now that Tab walks every control in a
    dialog, a Tab through the page wrote the company file and an audit
    entry each time, and turned a note never written (null) into ""
    (macOS gate, round 2). Only a change is saved, empty and none alike."""
    rid = books["customer" if kind == "customers" else "vendor"]
    api = f"/api/{kind}/{rid}"
    audit = f"/api/audit?table_name={kind}&record_id={rid}"
    status = f"#{box.replace('notes', 'note-status')}-{rid}"
    assert company.get(api).json()["notes"] is None  # never written
    before = len(company.get(audit).json())
    page, handled = _open_at(browser, company, f"#/{kind}/{rid}")
    puts = []
    page.on("request", lambda r: puts.append(r.url) if r.method == "PUT" else None)
    try:
        page.wait_for_function(MODAL_SHOWN)
        page.wait_for_selector(f"#{box}-{rid}")
        settle(page, handled)
        # Tab through the whole page, the box included, and in and out of
        # the box itself
        stops = page.evaluate(
            "() => _tabStops(document.getElementById('modal-body'), null).length"
        )
        page.evaluate(FIRST)
        for _ in range(stops + 1):
            page.keyboard.press("Tab")
        page.focus(f"#{box}-{rid}")
        for keys in ("Tab", "Shift+Tab", "Tab"):
            page.keyboard.press(keys)
        settle(page, handled)
        assert puts == []
        assert page.inner_text(status).strip() == ""
        assert company.get(api).json()["notes"] is None  # not turned into ""
        assert len(company.get(audit).json()) == before
        # a change saves, once, and says so
        page.fill(f"#{box}-{rid}", "Prefers email.")
        page.keyboard.press("Tab")
        page.wait_for_function(
            "(s) => document.querySelector(s).textContent === '✓ saved'", arg=status
        )
        settle(page, handled)
        assert len(puts) == 1 and puts[0].endswith(api), puts
        assert company.get(api).json()["notes"] == "Prefers email."
        assert len(company.get(audit).json()) == before + 1
        # left as saved: nothing more
        page.focus(f"#{box}-{rid}")
        page.keyboard.press("Tab")
        settle(page, handled)
        assert len(puts) == 1
        # cleared: a change again, saved as empty; then nothing more
        page.fill(f"#{box}-{rid}", "")
        page.keyboard.press("Tab")
        settle(page, handled)
        assert len(puts) == 2
        assert (company.get(api).json()["notes"] or "") == ""
        page.focus(f"#{box}-{rid}")
        page.keyboard.press("Tab")
        settle(page, handled)
        assert len(puts) == 2
    finally:
        page.close()
