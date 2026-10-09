"""Type-ahead in the pickers (combobox.js): a list of customers, vendors,
items, accounts, employees, jobs or classes, and any long list, is a box you
type into, as in QuickBooks. "harb" finds Harbor District Events, "6500"
finds 6500 - Rent or Lease, and Enter, Tab or a click takes it.

The <select> stays the answer. These drive the box with the keyboard and the
mouse, as a person would, on the bakery's books of tests/test_theme_contrast.py,
and read the select: its value, and whether its change handler ran.

Skipped, as one module, where playwright or its Chromium is not installed.
"""

import time

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_dialog_contrast import OPEN, nonprofit  # noqa: E402,F401
from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    _open,
    _theme,
    _visit,
    below_threshold,
    browser_fixture,
    company_fixture,
    settle,
    sweep_of,
)

POPUP_SWEEP = sweep_of("document.querySelector('.cbx-popup')", cap=5000)

SHOWN = """() => [...document.querySelectorAll('#cbx-listbox [role=option]')]
    .map(li => li.textContent)"""
ACTIVE = """() => { const b = document.activeElement;
    const id = b && b.getAttribute('aria-activedescendant');
    const li = id && document.getElementById(id);
    return li ? [li.textContent, li.getAttribute('aria-selected')] : null; }"""
NOTE = "() => document.querySelector('.cbx-note').textContent"


def _dialog(page, handled, route, call):
    _visit(page, handled, route)
    # the start-up splash sits over the page until it's dismissed
    page.evaluate(
        "() => { const s = document.getElementById('splash'); if (s) s.classList.add('hidden'); }"
    )
    page.evaluate(f"async () => {{ await {call}; }}")
    page.wait_for_function(OPEN, timeout=5000)
    settle(page, handled)


def _chosen(page, sel_id):
    """[the selected option's words, what the box says] for a select."""
    return page.evaluate(
        """(id) => { const s = document.getElementById(id);
            const box = s.closest('.cbx').querySelector('.cbx-input');
            return [s.selectedIndex >= 0 ? s.options[s.selectedIndex].textContent : null, box.value]; }""",
        sel_id,
    )


def test_type_a_customer_and_take_it_with_enter(browser, company, books):
    page, handled = _open(browser, company)
    try:
        _dialog(page, handled, "#/invoices", "InvoicesPage.showForm()")
        page.evaluate(
            """() => { window.__changes = [];
                document.getElementById('inv-customer-select')
                    .addEventListener('change', e => window.__changes.push(e.target.value)); }"""
        )
        # the label (#198) names the box, the "*" read as required
        box = page.get_by_role("combobox", name="Customer", exact=True)
        assert box.count() == 1
        assert (
            page.evaluate("() => document.activeElement.id")
            == "inv-customer-select-box"
        ), "the dialog opens in the box"
        page.keyboard.type("harb")
        shown = page.evaluate(SHOWN)
        active = page.evaluate(ACTIVE)
        expanded = box.get_attribute("aria-expanded")
        page.keyboard.press("Enter")
        chosen = _chosen(page, "inv-customer-select")
        changes = page.evaluate("() => window.__changes.length")
        after = box.get_attribute("aria-expanded")
    finally:
        page.close()
    assert shown == ["Harbor District Events", "+ New Customer"]
    assert active == ["Harbor District Events", "true"] and expanded == "true"
    assert chosen == ["Harbor District Events", "Harbor District Events"]
    assert changes == 1 and after == "false"


def test_a_bill_line_finds_its_account_by_number(browser, company, books):
    page, handled = _open(browser, company)
    try:
        _dialog(page, handled, "#/bills", "BillsPage.showForm()")
        box = page.get_by_role("combobox", name="Account, line 1", exact=True)
        box.click()
        page.keyboard.type("6500")
        # each match with the group it's in: the account lists are grouped,
        # cost of goods apart from expenses (#214)
        shown = page.evaluate(
            """() => [...document.querySelectorAll('#cbx-listbox [role=option]')].map(li => {
                const c = li.cloneNode(true), g = c.querySelector('.cbx-in');
                if (g) g.remove();
                return [c.textContent.trim(), g ? g.textContent.trim() : ''];
            })"""
        )
        # the list hangs from the window: the table's overflow doesn't clip it
        reachable = page.evaluate(
            """() => { const li = document.querySelector('#cbx-listbox [role=option]');
                const r = li.getBoundingClientRect();
                return li.contains(document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2))
                    && li.closest('.cbx-popup').parentElement === document.body; }"""
        )
        page.keyboard.press("Tab")  # Tab takes it too, and moves on
        chosen = page.evaluate(
            """() => { const s = document.querySelector('#modal tbody tr select.line-account');
                return [s.options[s.selectedIndex].textContent,
                        s.closest('.cbx').querySelector('.cbx-input').value,
                        document.activeElement.classList.contains('line-desc')]; }"""
        )
    finally:
        page.close()
    assert shown == [["6500 - Rent or Lease", "Expenses"]] and reachable
    assert chosen == ["6500 - Rent or Lease", "6500 - Rent or Lease", True]


def test_a_name_not_in_the_list_opens_the_quick_add_with_it(browser, company, books):
    page, handled = _open(browser, company)
    try:
        _dialog(page, handled, "#/invoices", "InvoicesPage.showForm()")
        page.keyboard.type("Zed Newco")
        shown, active, note = (
            page.evaluate(SHOWN),
            page.evaluate(ACTIVE),
            page.evaluate(NOTE),
        )
        page.keyboard.press("Enter")
        quick = page.evaluate(
            """() => { const n = document.getElementById('inv-new-cust-name');
                return [document.getElementById('inv-new-customer-form').style.display,
                        n.value, document.activeElement === n]; }"""
        )
    finally:
        page.close()
    assert shown == ["+ New Customer"] and active == ["+ New Customer", "true"]
    assert note == "No match"
    assert quick == ["block", "Zed Newco", True]


def test_what_sets_the_select_shows_in_the_box(browser, company, books):
    page, handled = _open(browser, company)
    try:
        _dialog(page, handled, "#/invoices", "InvoicesPage.showForm()")
        page.evaluate(
            """() => { const s = document.getElementById('inv-customer-select');
                s.value = [...s.options].find(o => o.textContent === 'Salt & Pine Catering Co.').value; }"""
        )
        by_value = _chosen(page, "inv-customer-select")
        # a quick add appends the new customer, selected, without setting value
        page.evaluate(
            """() => { const s = document.getElementById('inv-customer-select');
                const o = document.createElement('option');
                o.value = '9999'; o.textContent = 'Brand New Co'; o.selected = true;
                s.appendChild(o); }"""
        )
        page.wait_for_function(
            "() => document.getElementById('inv-customer-select-box').value === 'Brand New Co'"
        )
        # Cancel on a quick add puts the select back to nothing
        page.evaluate(
            "() => { document.getElementById('inv-customer-select').value = ''; }"
        )
        cleared = page.evaluate(
            """() => { const b = document.getElementById('inv-customer-select-box');
                return [b.value, b.placeholder]; }"""
        )
        # a form reset puts each select back without a word; the box follows
        page.evaluate(
            """() => { const s = document.getElementById('inv-customer-select');
                s.selectedIndex = 2; document.getElementById('invoice-form').reset(); }"""
        )
        page.wait_for_function(
            "() => document.getElementById('inv-customer-select-box').value === ''"
        )
        # a test tool that picks an option the usual way still can: the
        # select is out of sight, not out of reach
        page.select_option("#inv-customer-select", label="Harbor District Events")
        picked = _chosen(page, "inv-customer-select")
    finally:
        page.close()
    assert by_value == ["Salt & Pine Catering Co.", "Salt & Pine Catering Co."]
    assert cleared == ["", "Select..."]
    assert picked == ["Harbor District Events", "Harbor District Events"]


def test_the_keys_and_leaving_the_box(browser, company, books):
    page, handled = _open(browser, company)
    try:
        _dialog(page, handled, "#/invoices", "InvoicesPage.showForm()")
        # Escape closes the list and puts the words back; the dialog stays
        page.keyboard.type("salt")
        page.keyboard.press("Escape")
        escaped = page.evaluate(
            """() => [!document.getElementById('modal-overlay').classList.contains('hidden'),
                      document.querySelector('.cbx-popup').hidden,
                      document.getElementById('inv-customer-select-box').value,
                      document.getElementById('inv-customer-select').value]"""
        )
        # a name typed in full is taken when you leave the box
        page.keyboard.type("salt & pine catering co.")
        page.click("#modal-title")
        full = _chosen(page, "inv-customer-select")
        # anything else goes back to what was chosen
        page.focus("#inv-customer-select-box")
        page.keyboard.type("xyz")
        page.click("#modal-title")
        partial = _chosen(page, "inv-customer-select")
        # the arrows: the whole list open on the choice, then up and down it
        page.focus("#inv-customer-select-box")
        page.keyboard.press("ArrowDown")
        opened = page.evaluate(ACTIVE)
        page.keyboard.press("ArrowUp")
        page.keyboard.press("ArrowDown")
        page.keyboard.press("ArrowUp")
        moved = page.evaluate(ACTIVE)
        page.keyboard.press("Enter")
        arrowed = _chosen(page, "inv-customer-select")
        # a click opens it, a click on a name takes it
        page.click("#modal-title")
        page.click("#inv-customer-select-box")
        page.click("#cbx-listbox [role=option]:has-text('Salt & Pine Catering Co.')")
        clicked = _chosen(page, "inv-customer-select")
        # Escape with the list closed still closes the dialog
        page.focus("#inv-customer-select-box")
        page.keyboard.press("Escape")
        closed = page.evaluate(
            "() => document.getElementById('modal-overlay').classList.contains('hidden')"
        )
    finally:
        page.close()
    assert escaped == [True, True, "", ""]
    assert full == ["Salt & Pine Catering Co.", "Salt & Pine Catering Co."]
    assert partial == full
    assert opened == ["Salt & Pine Catering Co.", "true"]
    assert moved == ["Harbor District Events", "true"]
    assert arrowed == ["Harbor District Events", "Harbor District Events"]
    assert clicked == ["Salt & Pine Catering Co.", "Salt & Pine Catering Co."]
    assert closed


def test_a_required_picker_stops_the_save_and_says_why(browser, company, books):
    page, handled = _open(browser, company)
    try:
        _dialog(page, handled, "#/invoices", "InvoicesPage.showForm()")
        page.evaluate(
            """() => { window.__saves = 0;
                InvoicesPage.save = (e) => { e.preventDefault(); window.__saves++; }; }"""
        )
        page.click("#modal-title")
        page.evaluate("() => document.getElementById('invoice-form').requestSubmit()")
        blocked = page.evaluate(
            """() => { const b = document.getElementById('inv-customer-select-box');
                return [window.__saves, b.validationMessage, document.activeElement === b,
                        b.required]; }"""
        )
        page.keyboard.type("harb")
        page.keyboard.press("Enter")
        page.evaluate("() => document.getElementById('invoice-form').requestSubmit()")
        saves = page.evaluate("() => window.__saves")
    finally:
        page.close()
    assert blocked == [0, "Choose one from the list.", True, True]
    assert saves == 1


def test_a_read_only_sign_in_gets_the_box_locked(browser, company, books):
    page, handled = _open(browser, company)
    try:
        page.evaluate("() => App.setRole('readonly')")
        _dialog(page, handled, "#/invoices", "InvoicesPage.showForm()")
        locked = page.evaluate(
            """() => [...document.querySelectorAll('#modal .cbx-input')]
                .map(b => [b.id, b.disabled])"""
        )
        page.evaluate(
            "() => document.getElementById('inv-customer-select-box').dispatchEvent("
            "new MouseEvent('mousedown', {bubbles: true}))"
        )
        opened = page.evaluate(
            "() => !!document.querySelector('.cbx-popup') && !document.querySelector('.cbx-popup').hidden"
        )
    finally:
        page.close()
    assert locked and all(disabled for _, disabled in locked), locked
    assert not opened


def test_a_nonprofits_donor_picker(browser, client, nonprofit):  # noqa: F811
    page, handled = _open(browser, client)
    try:
        _dialog(page, handled, "#/invoices", "InvoicesPage.showForm()")
        box = page.get_by_role("combobox", name="Donor", exact=True)
        named = box.count()
        page.keyboard.type("salt")
        page.keyboard.press("Enter")
        chosen = _chosen(page, "inv-customer-select")
    finally:
        page.close()
    assert named == 1
    assert chosen == ["Salt & Pine Catering Co.", "Salt & Pine Catering Co."]


def test_which_pickers_get_type_ahead(browser, company, books):
    page, handled = _open(browser, company)
    try:
        _dialog(page, handled, "#/invoices", "InvoicesPage.showForm()")
        on_the_form = page.evaluate(
            """() => [...document.querySelectorAll('#modal select')]
                .map(s => [s.name || s.className, !!s._cbx])"""
        )
        rule = page.evaluate("""() => {
                const mk = (attrs, n) => {
                    const s = document.createElement('select');
                    for (const [k, v] of Object.entries(attrs)) s.setAttribute(k, v);
                    for (let i = 0; i < n; i++) s.add(new Option('option ' + i, String(i)));
                    return s;
                };
                return {
                    customer: Combobox.wants(mk({name: 'customer_id'}, 2)),
                    lineItem: Combobox.wants(mk({class: 'line-item'}, 1)),
                    account: Combobox.wants(mk({name: 'deposit_to_account_id'}, 3)),
                    employee: Combobox.wants(mk({id: 'w2-employee'}, 2)),
                    accountType: Combobox.wants(mk({name: 'account_type'}, 5)),
                    terms: Combobox.wants(mk({id: 'invoice-terms', name: 'terms'}, 5)),
                    yesNo: Combobox.wants(mk({name: 'is_1099_vendor'}, 2)),
                    shortList: Combobox.wants(mk({name: 'pay_frequency'}, 4)),
                    longList: Combobox.wants(mk({name: 'country'}, 250)),
                    optOut: Combobox.wants(mk({name: 'vendor_id', 'data-no-search': ''}, 3)),
                    optIn: Combobox.wants(mk({name: 'basis', 'data-search': ''}, 2)),
                    multiple: Combobox.wants(mk({name: 'customer_id', multiple: ''}, 3)),
                };
            }""")
    finally:
        page.close()
    picked = dict(on_the_form)
    wanted = ("customer_id", "terms", "class_id", "job_id", "currency")
    assert {k: picked.get(k) for k in wanted} == {
        "customer_id": True,
        "terms": False,
        "class_id": True,
        "job_id": True,
        "currency": False,
    }, on_the_form
    assert picked.get("line-item cbx-select") is True, on_the_form
    assert rule == {
        "customer": True,
        "lineItem": True,
        "account": True,
        "employee": True,
        "accountType": False,
        "terms": False,
        "yesNo": False,
        "shortList": False,
        "longList": True,
        "optOut": False,
        "optIn": True,
        "multiple": False,
    }


def test_a_thousand_names_draw_fifty_and_say_keep_typing(browser, company, books):
    page, handled = _open(browser, company)
    try:
        _visit(page, handled, "#/invoices")
        page.evaluate("""() => { const g = document.createElement('div');
                g.className = 'form-group';
                g.innerHTML = '<label for="big">Customer</label><select id="big" name="customer_id">'
                    + '<option value="">Select...</option>'
                    + Array.from({length: 1000}, (_, i) =>
                        `<option value="${i}">Customer ${String(i).padStart(4, '0')} Co</option>`).join('')
                    + '</select>';
                document.getElementById('page-content').prepend(g); }""")
        page.wait_for_function("() => !!document.getElementById('big-box')")
        page.focus("#big-box")
        started = time.perf_counter()
        page.keyboard.type("co")
        typed = time.perf_counter() - started
        many = [len(page.evaluate(SHOWN)), page.evaluate(NOTE)]
        page.keyboard.type(" 09")
        fewer = [len(page.evaluate(SHOWN)), page.evaluate(NOTE)]
        drawn = page.evaluate("""() => { const box = document.getElementById('big-box');
                const t = performance.now();
                box.value = 'customer 0';
                box.dispatchEvent(new Event('input'));
                return performance.now() - t; }""")
    finally:
        page.close()
    # " 09" finds 0900-0999, 0090-0099 and 0x09
    found = sum(1 for i in range(1000) if "09" in f"{i:04d}")
    assert many == [50, "950 more — keep typing"]
    assert fewer == [50, f"{found - 50} more — keep typing"]
    assert drawn < 150, drawn  # a keystroke's filter and draw, in milliseconds
    assert typed < 5, typed


def test_the_open_list_reads_in_both_themes(browser, company, books):
    """The list's names, the highlighted one, a match in bold, "+ New
    Customer" and the note under it meet AA in the light and dark themes."""
    page, handled = _open(browser, company)
    sweeps = {}
    try:
        for theme in ("light", "dark"):
            _theme(page, theme)
            _dialog(page, handled, "#/invoices", "InvoicesPage.showForm()")
            page.keyboard.press("ArrowDown")  # the whole list
            sweeps[(theme, "open")] = page.evaluate(POPUP_SWEEP)
            page.keyboard.type("a")  # matches, in bold, and the action
            sweeps[(theme, "typing")] = page.evaluate(POPUP_SWEEP)
            page.keyboard.type("zzz")  # no match: the note
            sweeps[(theme, "nothing")] = page.evaluate(POPUP_SWEEP)
            page.keyboard.press("Escape")
            page.evaluate("() => closeModal()")
            # a job cost's "who" lists Employees and Equipment under headings
            _dialog(page, handled, "#/job-costs", "JobCostsPage.showForm()")
            who = page.evaluate(
                "() => document.querySelector('#modal tbody tr select.jc-who')"
                ".closest('.cbx').querySelector('.cbx-input').id"
            )
            page.focus(f"#{who}")
            page.keyboard.press("ArrowDown")
            sweeps[(theme, "grouped")] = page.evaluate(POPUP_SWEEP)
            page.keyboard.press("Escape")
            page.evaluate("() => closeModal()")
    finally:
        page.close()
    assert all(sweeps.values()), {k: len(v) for k, v in sweeps.items()}
    assert below_threshold(sweeps) == []
