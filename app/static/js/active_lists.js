/**
 * Active / Inactive / All on the list pages, and Make Inactive / Make Active
 * on each row (#210, asked for by Ryan of Cimarron Site Services). The
 * Chart of Accounts already worked this way (#139); customers, vendors,
 * items, employees and jobs do too now. An inactive record keeps its
 * history and leaves the pickers; it can be made active again.
 *
 * Each list remembers its Show choice. Only the record's id goes into a
 * row's onclick; its name and balance are looked up from the rows the page
 * last drew.
 */
const ActiveLists = {
    KINDS: {
        customers: {
            api: '/customers', route: '#/customers', noun: () => T('customer'), money: true,
            name: r => r.name,
        },
        vendors: {
            api: '/vendors', route: '#/vendors', noun: () => 'vendor', money: true,
            name: r => r.name,
        },
        items: {
            api: '/items', route: '#/items', noun: () => 'item',
            name: r => r.name,
        },
        // Staff records are the administrator's to change (the server's
        // /api/employees writes are admin-only), so the buttons are too.
        employees: {
            api: '/employees', route: '#/employees', noun: () => 'employee', admin: true, payroll: true,
            name: r => `${r.first_name || ''} ${r.last_name || ''}`.trim(),
        },
        // The Jobs page has every job already; a new view only redraws.
        jobs: {
            api: '/jobs', route: '#/jobs', noun: () => T('job'),
            name: r => r.name,
            redraw: () => JobsPage.setFilter('show', ActiveLists.show('jobs')),
        },
    },
    CHOICES: ['active', 'inactive', 'all'],
    _rows: {},

    _key(kind) { return `slowbooks-show-${kind}`; },

    // What the list shows: active records unless the person chose otherwise.
    show(kind) {
        try {
            const v = localStorage.getItem(this._key(kind));
            if (this.CHOICES.includes(v)) return v;
        } catch (e) { /* storage blocked: the default */ }
        return 'active';
    },

    // The list endpoint's filter for the current choice.
    query(kind) {
        const s = this.show(kind);
        return s === 'active' ? '?active_only=true' : s === 'inactive' ? '?inactive_only=true' : '';
    },

    // Whether a record belongs in the current view (the Jobs page filters
    // the list it already has).
    shows(kind, record) {
        const s = this.show(kind);
        const active = record.is_active !== false;
        return s === 'all' || (s === 'active') === active;
    },

    pickerHtml(kind) {
        const cur = this.show(kind);
        const opt = (v, label) => `<option value="${v}"${cur === v ? ' selected' : ''}>${label}</option>`;
        return `<label for="list-show" class="list-show-label">Show</label>
            <select id="list-show" data-no-search onchange="ActiveLists.choose('${kind}', this.value)">
                ${opt('active', 'Active')}${opt('inactive', 'Inactive')}${opt('all', 'All')}
            </select>`;
    },

    choose(kind, value) {
        if (!this.CHOICES.includes(value)) return;
        try { localStorage.setItem(this._key(kind), value); } catch (e) { /* this view only */ }
        const k = this.KINDS[kind];
        if (k.redraw) k.redraw();
        else App.navigate(k.route);
    },

    // The rows a page drew, so a button needs only the id.
    remember(kind, rows) {
        this._rows[kind] = new Map(rows.map(r => [r.id, r]));
    },

    // The sentence for an empty Inactive view; the other views use the
    // page's own "nothing yet" one.
    emptyText(kind) {
        return this.show(kind) === 'inactive' ? `No inactive ${this.KINDS[kind].noun()}s.` : null;
    },

    buttonHtml(kind, record) {
        const k = this.KINDS[kind];
        const active = record.is_active !== false;
        const label = active ? 'Make Inactive' : 'Make Active';
        const said = `${active ? 'Make inactive' : 'Make active'}: ${k.name(record)}`;
        return `<button type="button" class="btn btn-sm btn-secondary" data-write${k.admin ? ' data-admin' : ''}
            aria-label="${escapeHtml(said)}"
            onclick="event.stopPropagation(); ActiveLists.set('${kind}', ${Number(record.id)}, ${!active})">${label}</button>`;
    },

    // One click, with a question first where hiding a record could hide
    // money: an open balance, or an employee's next pay run.
    async set(kind, id, active) {
        const k = this.KINDS[kind];
        const record = (this._rows[kind] && this._rows[kind].get(id)) || { id };
        const name = k.name(record) || `This ${k.noun()}`;
        if (!active) {
            const open = Number(record.balance || 0);
            if (k.money && Math.abs(open) >= 0.005
                && !confirm(`${name} has ${formatCurrency(open)} open. Make this ${k.noun()} inactive anyway? `
                    + 'Its documents stay as they are; it only leaves the pickers.')) return;
            if (k.payroll && !confirm(`Make ${name} inactive? An inactive employee isn't included in new pay runs.`)) return;
        }
        try {
            await API.put(`${k.api}/${id}`, { is_active: active });
            toast(active ? `${name} is active again` : `${name} is inactive: kept on file, out of the pickers`);
            App.navigate(k.route);
        } catch (err) {
            toast(err.message, 'error');
        }
    },
};
