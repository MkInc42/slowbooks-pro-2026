/**
 * Reports — every report is plain SQL on the backend; this viewer
 * renders the tables, print/PDF is WeasyPrint server-side.
 */
const ReportsPage = {
    // Every report view by its address name: #/reports/<name>?<params>
    // (R7, docs/dev/report-views.md). `open(params)` is what the address
    // runs, with the query as a plain object of strings; `label` names the
    // view on a "Back to …" button (a string, or a function returning the
    // term, where nonprofit vocabulary renames it); `asOf: true` marks a
    // view dated by one as_of_date rather
    // than a range; `keep` lists the drill-down params (beyond the dates)
    // that ride on the way back to the view. A saved report's report_type
    // is the name with underscores (profit_loss ↔ profit-loss), so saving
    // and reopening round-trip through the same address.
    _VIEWS: {
        'profit-loss':          { label: () => T('Profit & Loss'),      open: (p) => ReportsPage.profitLoss(p) },
        'balance-sheet':        { label: () => T('Balance Sheet'),      open: (p) => ReportsPage.balanceSheet(p), asOf: true },
        'profit-loss-by-class': { label: () => T('P&L by Class'),       open: (p) => ReportsPage.profitLossByClass(p) },
        'profit-loss-class':    { label: () => T('Profit & Loss'),      open: (p) => ReportsPage.profitLossOfClass(p.class_id, null, p), keep: ['class_id'] },
        'profit-loss-unclassified': { label: () => `${T('P&L')} Unclassified`, open: (p) => ReportsPage.profitLossUnclassified(p) },
        'account-transactions': { label: 'Drill-down',         open: (p) => ReportsPage.openDrillDown(p.account_id, null, p.start_date, p.end_date, p.class_id || null, null, p.from || null) },
        'ar-aging':             { label: () => T('Accounts Receivable Aging'), open: (p) => ReportsPage.arAging(p), asOf: true },
        'ap-aging':             { label: 'Accounts Payable Aging',    open: (p) => ReportsPage.apAging(p), asOf: true },
        'sales-tax':            { label: 'Sales Tax Report',   open: (p) => ReportsPage.salesTax(p) },
        'general-ledger':       { label: 'General Ledger',     open: (p) => ReportsPage.generalLedger(p) },
        'income-by-customer':   { label: () => T('Income by Customer'), open: (p) => ReportsPage.incomeByCustomer(p) },
        'trial-balance':        { label: 'Trial Balance',      open: (p) => ReportsPage.trialBalance(p) },
        'cash-flow':            { label: 'Cash Flow Statement', open: (p) => ReportsPage.cashFlow(p) },
        'job-profitability':    { label: () => T('Job Profitability'),  open: (p) => ReportsPage.jobProfitability(p) },
        'job-budget-vs-actual': { label: () => T('Job Budget vs Actual'), open: (p) => ReportsPage.jobBudgetVsActual(p) },
        'budget-vs-actual':     { label: 'Budget vs Actual',   open: (p) => { if (/^\d{4}$/.test(p.year || '')) BudgetsPage._year = parseInt(p.year, 10); return BudgetsPage.showVariance(p); } },
        'financial-statements': { label: 'Financial Statements Pack', open: (p) => ReportsPage.financialStatementsPdf(p) },
        'fixed-asset-reconciliation': { label: 'Fixed Asset Reconciliation', open: () => ReportsPage.fixedAssetReconciliation() },
        'customer-statement':   { label: () => T('Customer Statement'), open: () => ReportsPage.customerStatementPicker() },
        '1099-summary':         { label: '1099 Summary',       open: (p) => ReportsPage.report1099(p) },
        'statement-of-financial-position': { label: 'Statement of Financial Position', open: (p) => ReportsPage.statementOfFinancialPosition(p), asOf: true },
        'statement-of-activities':         { label: 'Statement of Activities', open: (p) => ReportsPage.statementOfActivities(p) },
        'fund-balances':        { label: 'Fund Balances',      open: (p) => ReportsPage.fundBalances(p) },
        'functional-expenses':  { label: 'Statement of Functional Expenses', open: (p) => ReportsPage.functionalExpenses(p) },
        'pledges':              { label: 'Pledge Report',      open: (p) => ReportsPage.pledges(p) },
        'giving-statements':    { label: 'Year-End Giving Statements', open: (p) => ReportsPage.givingStatements(p) },
    },

    // The address of a view: '#/reports/<name>?<params>'. Empty values are
    // left out, and so is period=custom — dates alone mean custom, and a
    // preset period (this_month) names what to recompute on a later day.
    viewUrl(name, params) {
        const qs = new URLSearchParams();
        for (const [k, v] of Object.entries(params || {})) {
            if (v === null || v === undefined || v === '') continue;
            if (k === 'period' && v === 'custom') continue;
            qs.set(k, String(v));
        }
        const q = qs.toString();
        return `#/reports/${name}${q ? `?${q}` : ''}`;
    },

    // The registered view of that name, or null. Own names only: a name
    // the registry never had but Object.prototype does ('constructor',
    // '__proto__') opened a drill-down with a "Back to " button going
    // nowhere (R7 review).
    _view(name) {
        return Object.hasOwn(ReportsPage._VIEWS, String(name ?? '')) ? ReportsPage._VIEWS[name] : null;
    },

    // Put the view on the address bar. The same view with other params
    // (the period changed, a filter set) replaces the entry, so Back never
    // walks through every period a user tried; a different view (the
    // Report Center to a report, a report to its drill-down) pushes, so
    // Back returns to it. The pushed entry carries the address it was
    // pushed from in its history.state ({from}), as App.navigate's push
    // does: the entry itself knows where it came from, so Back, Forward,
    // Close and a reload cannot leave a stale note in memory (R7 review),
    // and a replace keeps the state the entry has.
    setAddress(name, params) {
        const url = ReportsPage.viewUrl(name, params);
        const here = location.hash || '#/';
        if (here === url) return;
        if (App.parseHash(here).path === `/reports/${name}`) history.replaceState(history.state, '', url);
        else history.pushState({ from: here }, '', url);
    },

    // Back to a view, as its "Back to …" button does: through the browser's
    // history when this entry was pushed from that view (so Back and the
    // button agree, however deep the chain), otherwise by opening the
    // address. A view reached by its address alone (typed, pasted, a hash
    // set by hand) was pushed from no view, and goes forward.
    backTo(name, params) {
        const from = history.state && history.state.from;
        if (from && App.parseHash(from).path === `/reports/${name}`) {
            history.back();
            return;
        }
        App.navigate(ReportsPage.viewUrl(name, params));
    },

    // `detail` names which one, after the view's label, where the view is
    // a filtered one ("Back to Profit & Loss — Side Gig").
    _backButton(name, params, detail = '') {
        const view = ReportsPage._view(name);
        if (!view) return '';
        const call = escapeHtml(`ReportsPage.backTo(${JSON.stringify(name)}, ${JSON.stringify(params || {})})`);
        return `<button type="button" class="btn btn-secondary" data-back-to="${escapeHtml(name)}" onclick="${call}">${escapeHtml(ReportsPage._backText(name, detail))}</button>`;
    },

    _backText(name, detail) {
        const view = ReportsPage._view(name);
        const label = typeof view.label === 'function' ? view.label() : view.label;
        return `Back to ${label}${detail ? ` — ${detail}` : ''}`;
    },

    // The '/reports/:view' route: the view named in the address, opened
    // over the Report Center from its query. A name nobody registered, or a
    // view that cannot open, leaves the Report Center showing and says so;
    // the address falls back to the Report Center's.
    async openView(name, params) {
        const view = ReportsPage._view(name);
        if (!view) {
            history.replaceState(null, '', '#/reports');
            toast(`There is no report called "${name}"`, 'error');
            return;
        }
        try {
            await view.open(params || {});
        } catch (err) {
            history.replaceState(null, '', '#/reports');
            throw err;
        }
        // Opened nothing (a drill-down with no account, say, which says so
        // in a notice): the address is the Report Center's.
        const overlay = $('#modal-overlay');
        if (overlay && overlay.classList.contains('hidden')) history.replaceState(null, '', '#/reports');
    },

    async render() {
        // Fetch saved reports separately so the page still renders if the
        // call fails (network blip, table missing, etc.).
        let savedHtml = '';
        try {
            const saved = await API.get('/saved-reports');
            if (saved && saved.length) {
                // A list, not a wall of cards: thirty saved reports must not
                // push the Report Center off the screen. Collapsed by default
                // once there are more than a handful; the choice sticks.
                let collapsed = false;
                try { collapsed = localStorage.getItem('sb_saved_reports_collapsed') === '1'; } catch (e) { /* ignore */ }
                if (saved.length > 6 && localStorage.getItem('sb_saved_reports_collapsed') === null) collapsed = true;
                const period = (p) => !p ? '' : (p.as_of_date ? `as of ${escapeHtml(p.as_of_date)}` : (p.start_date ? `${escapeHtml(p.start_date)} → ${escapeHtml(p.end_date || '')}` : (p.period ? escapeHtml(String(p.period).replace(/_/g, ' ')) : '')));
                const rows = saved.slice().sort((a, b) => a.name.localeCompare(b.name)).map(s => `
                    <tr class="saved-report-row">
                        <td><a href="javascript:void(0)" onclick="ReportsPage.openSaved(${s.id})" style="font-weight:600;">${escapeHtml(s.name)}</a></td>
                        <td>${escapeHtml(Terms.text(s.report_type.replace(/_/g, ' ')))}</td>
                        <td style="color:var(--text-muted);">${period(s.parameters)}</td>
                        <td class="actions">
                            <button class="btn btn-sm btn-secondary" onclick="ReportsPage.openSaved(${s.id})">Open</button>
                            <button class="btn btn-sm btn-secondary" aria-label="Delete saved report" onclick="ReportsPage.deleteSaved(${s.id})">Delete</button>
                        </td>
                    </tr>`).join('');
                savedHtml = `
                    <div style="display:flex; align-items:center; gap:10px; margin:0 0 8px;">
                        <button type="button" class="btn btn-sm btn-secondary" id="saved-reports-toggle" aria-expanded="${collapsed ? 'false' : 'true'}" aria-controls="saved-reports-list" onclick="ReportsPage.toggleSaved()">${collapsed ? '▸' : '▾'}</button>
                        <h3 style="font-size:13px; text-transform:uppercase; letter-spacing:0.5px; color:var(--text-muted); margin:0;">Saved Reports (${saved.length})</h3>
                        ${saved.length > 8 ? `<input type="text" id="saved-reports-filter" placeholder="Filter…" style="width:160px;" oninput="ReportsPage.filterSaved(this.value)">` : ''}
                    </div>
                    <div id="saved-reports-list" ${collapsed ? 'hidden' : ''} style="margin-bottom:20px;">
                        <div class="table-container"><table>
                            <thead><tr><th scope="col">Name</th><th scope="col">Report</th><th scope="col">Period</th><th scope="col">Actions</th></tr></thead>
                            <tbody>${rows}</tbody>
                        </table></div>
                    </div>`;
            }
        } catch (e) { /* render anyway */ }

        return `
            <div class="page-header"><h2>Reports</h2></div>
            ${savedHtml}
            <div class="card-grid">
                ${Terms.isNonprofit() ? ReportsPage._nonprofitCards() : `
                <div class="card" style="cursor:pointer" onclick="ReportsPage.profitLoss()">
                    <div class="card-header">${T('Profit & Loss')}</div>
                    <p style="font-size:13px; color:var(--gray-500);">${Terms.text('Income vs expenses for a period')}</p>
                </div>`}
                <div class="card" style="cursor:pointer" onclick="ReportsPage.profitLossByClass()">
                    <div class="card-header">${T('P&L by Class')}</div>
                    <p style="font-size:13px; color:var(--gray-500);">${Terms.text('Income vs expenses split by class')}</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.profitLossUnclassified()">
                    <div class="card-header">${T('P&L')} Unclassified</div>
                    <p style="font-size:13px; color:var(--gray-500);">${Terms.text('Income and expenses with no class yet — the end-of-month cleanup list')}</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.jobBudgetVsActual()">
                    <div class="card-header">${T('Job Budget vs Actual')}</div>
                    <p style="font-size:13px; color:var(--gray-500);">${Terms.text('Budget, committed, actual, projected, variance per job')}</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.jobProfitability()">
                    <div class="card-header">${T('Job Profitability')}</div>
                    <p style="font-size:13px; color:var(--gray-500);">${Terms.text('Income, costs and margin per job')}</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.financialStatementsPdf()">
                    <div class="card-header">Financial Statements Pack (PDF)</div>
                    <p style="font-size:13px; color:var(--gray-500);">${Terms.text('Profit & Loss + Balance Sheet + Trial Balance, one audit-ready PDF')}</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.fixedAssetReconciliation()">
                    <div class="card-header">Fixed Asset Reconciliation</div>
                    <p style="font-size:13px; color:var(--gray-500);">Register totals vs GL by asset type</p>
                </div>
                ${Terms.isNonprofit() ? '' : `
                <div class="card" style="cursor:pointer" onclick="ReportsPage.balanceSheet()">
                    <div class="card-header">${T('Balance Sheet')}</div>
                    <p style="font-size:13px; color:var(--gray-500);">${Terms.text('Assets, liabilities, and equity')}</p>
                </div>`}
                <div class="card" style="cursor:pointer" onclick="ReportsPage.arAging()">
                    <div class="card-header">${T('A/R Aging')}</div>
                    <p style="font-size:13px; color:var(--gray-500);">Outstanding receivables by age</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.apAging()">
                    <div class="card-header">A/P Aging</div>
                    <p style="font-size:13px; color:var(--gray-500);">Outstanding payables by age</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.salesTax()">
                    <div class="card-header">Sales Tax</div>
                    <p style="font-size:13px; color:var(--gray-500);">Tax collected by invoice</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.generalLedger()">
                    <div class="card-header">General Ledger</div>
                    <p style="font-size:13px; color:var(--gray-500);">All journal entries by account</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.incomeByCustomer()">
                    <div class="card-header">${T('Income by Customer')}</div>
                    <p style="font-size:13px; color:var(--gray-500);">${Terms.isNonprofit() ? 'Contribution totals per donor' : 'Sales totals per customer'}</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.customerStatementPicker()">
                    <div class="card-header">${T('Customer Statement')}</div>
                    <p style="font-size:13px; color:var(--gray-500);">${Terms.text('Invoice/payment history PDF')}</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.trialBalance()">
                    <div class="card-header">Trial Balance</div>
                    <p style="font-size:13px; color:var(--gray-500);">Debits and credits by account</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.cashFlow()">
                    <div class="card-header">Cash Flow</div>
                    <p style="font-size:13px; color:var(--gray-500);">Operating, investing, financing</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="ReportsPage.report1099()">
                    <div class="card-header">1099 Summary</div>
                    <p style="font-size:13px; color:var(--gray-500);">Vendor payments for 1099 filing</p>
                </div>
                <div class="card" style="cursor:pointer" onclick="BudgetsPage.showVariance()">
                    <div class="card-header">Budget vs Actual</div>
                    <p style="font-size:13px; color:var(--gray-500);">Monthly budget variance analysis</p>
                </div>
            </div>`;
    },

    // ----- Saved Reports (Phase 11) -----

    toggleSaved() {
        const list = $('#saved-reports-list');
        const btn = $('#saved-reports-toggle');
        if (!list || !btn) return;
        const nowHidden = !list.hidden;
        list.hidden = nowHidden;
        btn.textContent = nowHidden ? '▸' : '▾';
        btn.setAttribute('aria-expanded', nowHidden ? 'false' : 'true');
        try { localStorage.setItem('sb_saved_reports_collapsed', nowHidden ? '1' : '0'); } catch (e) { /* ignore */ }
    },

    filterSaved(q) {
        const needle = (q || '').trim().toLowerCase();
        $$('.saved-report-row').forEach(tr => { tr.hidden = needle !== '' && !tr.textContent.toLowerCase().includes(needle); });
    },

    async openSaved(id) {
        try {
            const all = await API.get('/saved-reports');
            const saved = all.find(s => s.id === id);
            if (!saved) { toast('Saved report not found', 'error'); return; }
            // Through the view's address, as a bookmark would open it: the
            // report is then on the address bar and a step back in history.
            const name = String(saved.report_type).replace(/_/g, '-');
            if (!ReportsPage._view(name)) {
                toast(`No opener registered for "${saved.report_type}"`, 'error');
                return;
            }
            await App.navigate(ReportsPage.viewUrl(name, saved.parameters || {}));
        } catch (err) { toast(err.message || 'Failed to open', 'error'); }
    },

    async saveCurrent(reportType, params) {
        const name = prompt('Name for this saved report:');
        if (!name || !name.trim()) return;
        try {
            await API.post('/saved-reports', {
                name: name.trim(),
                report_type: reportType,
                parameters: params || {},
            });
            toast(`Saved as "${name.trim()}" — it is listed under Saved Reports at the top of the Report Center`);
            // Refresh the page so the new one shows in the Saved section
            App.navigate(location.hash);
        } catch (err) { toast(err.message || 'Save failed', 'error'); }
    },

    async deleteSaved(id) {
        if (!confirm('Delete this saved report?')) return;
        try {
            await API.del(`/saved-reports/${id}`);
            toast('Deleted');
            App.navigate(location.hash);
        } catch (err) { toast(err.message || 'Delete failed', 'error'); }
    },

    // ----- Drill-down (Phase 11) -----
    // Hits /api/reports/account-transactions for one account in the date
    // range and shows the journal entries that rolled up into the row the
    // user clicked. Each entry's source_link routes to the originating
    // invoice / bill / payment / journal entry.
    // With `classId`, only that class's lines (#213). `from` names the view
    // that opened it (a ReportsPage._VIEWS key: 'profit-loss',
    // 'general-ledger' (#224), 'profit-loss-by-class', …): the "Back to …"
    // button returns there for the same dates, and the browser's Back does
    // the same. The view has an address of its own
    // (#/reports/account-transactions?account_id=…&from=…), so it is
    // rebuilt from the address after a reload, or on Back from a source
    // document (R7): the names are then taken from what the server says.
    async openDrillDown(accountId, accountName, startDate, endDate, classId = null, className = null, from = null) {
        accountId = parseInt(accountId, 10);
        if (!accountId) { toast('No account_id on this row', 'error'); return; }
        classId = classId ? parseInt(classId, 10) || null : null;
        if (classId && !from) from = 'profit-loss-by-class';
        const back = ReportsPage._view(from) ? from : null;
        const params = new URLSearchParams();
        params.set('account_id', accountId);
        if (startDate) params.set('start_date', startDate);
        if (endDate) params.set('end_date', endDate);
        if (classId) params.set('class_id', classId);

        ReportsPage.setAddress('account-transactions', {
            account_id: accountId, start_date: startDate, end_date: endDate, class_id: classId, from: back,
        });

        // The way back carries the dates the view was on (one as-of date
        // for a balance sheet) and whatever the view says it keeps. Back to
        // a class's own P&L says which class ("Back to Profit & Loss —
        // Side Gig"): the same words as the company P&L would mislead.
        let backBtn = '';
        const backToClass = back === 'profit-loss-class' && !!classId;
        if (back) {
            const v = ReportsPage._view(back);
            const backParams = v.asOf ? { as_of_date: endDate } : { start_date: startDate, end_date: endDate };
            if ((v.keep || []).includes('class_id') && classId) backParams.class_id = classId;
            backBtn = ReportsPage._backButton(back, backParams, backToClass ? (className || T('Class')) : '');
        }

        const title = (name, cls) => `Drill-down — ${name || `account ${accountId}`}${cls ? ` · ${cls}` : ''}`;
        openModal(title(accountName, className), `
            <div id="drilldown-body" style="font-size:11px; color:var(--gray-500);">Loading…</div>
            <div class="form-actions">
                ${backBtn}
                <button type="button" class="btn btn-secondary" onclick="closeModal()">Close</button>
            </div>
        `);

        try {
            const data = await API.get(`/reports/account-transactions?${params.toString()}`);
            if (!accountName || (classId && !className)) {
                $('#modal-title').textContent = title(accountName || data.account.name, className || data.class_name);
            }
            // Rebuilt from the address, the class's name arrives now
            if (backToClass && !className && data.class_name) {
                const btn = $('#modal-body [data-back-to="profit-loss-class"]');
                if (btn) btn.textContent = ReportsPage._backText(back, data.class_name);
            }
            const rows = (data.entries || []).map(e => {
                const src = e.source_link
                    ? `<a href="${escapeHtml(e.source_link)}" style="color:var(--text-link); text-decoration:none;">${escapeHtml(e.source_type || '')} #${e.source_id}</a>`
                    : escapeHtml(e.source_type || '');
                return `<tr>
                    <td>${formatDate(e.date)}</td>
                    <td>${escapeHtml(e.reference || '')}</td>
                    <td>${escapeHtml(e.description || '')}</td>
                    <td>${src}</td>
                    <td class="amount">${e.debit > 0 ? formatCurrency(e.debit) : ''}</td>
                    <td class="amount">${e.credit > 0 ? formatCurrency(e.credit) : ''}</td>
                    <td class="amount">${formatCurrency(e.running_balance)}</td>
                </tr>`;
            }).join('');

            $('#drilldown-body').innerHTML = `
                <p style="margin-bottom:8px; color:var(--gray-500); font-size:12px;">
                    ${escapeHtml(data.account.number || '')} · ${escapeHtml(data.account.name)}
                    ${data.class_name ? `&middot; ${T('Class')}: <strong>${escapeHtml(data.class_name)}</strong>` : ''}
                    &middot; ${formatDate(data.start_date)} → ${formatDate(data.end_date)}
                    &middot; Net: <strong>${formatCurrency(data.period_net)}</strong>
                </p>
                <div class="table-container"><table>
                    <thead><tr>
                        <th scope="col">Date</th><th scope="col">Ref</th><th scope="col">Description</th><th scope="col">Source</th>
                        <th scope="col" class="amount">Debit</th><th scope="col" class="amount">Credit</th><th scope="col" class="amount">Running</th>
                    </tr></thead>
                    <tbody>${rows || '<tr><td colspan="7" style="text-align:center; color:var(--gray-400);">No entries in range</td></tr>'}</tbody>
                </table></div>`;
        } catch (err) {
            $('#drilldown-body').innerHTML =
                `<div class="empty-state"><p>${escapeHtml(err.message || 'Failed to load drill-down')}</p></div>`;
        }
    },

    periodOptions(selected) {
        const options = [
            ["this_month", "This Month"],
            ["this_quarter", "This Quarter"],
            ["this_year", "This Year"],
            ["this_year_to_date", "This Year to Date"],
            ["last_month", "Last Month"],
            ["last_quarter", "Last Quarter"],
            ["last_year", "Last Year"],
            ["last_year_to_date", "Last Year to Date"],
            ["custom", "Custom Date"],
        ];
        return options.map(([value, label]) =>
            `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`
        ).join("");
    },

    _pad(value) {
        return String(value).padStart(2, "0");
    },

    _isoDate(dateObj) {
        return `${dateObj.getFullYear()}-${ReportsPage._pad(dateObj.getMonth() + 1)}-${ReportsPage._pad(dateObj.getDate())}`;
    },

    _quarterStart(monthIndex) {
        return Math.floor(monthIndex / 3) * 3;
    },

    getDateRange(period, customStart = null, customEnd = null) {
        const today = new Date();
        const year = today.getFullYear();
        const month = today.getMonth();
        const day = today.getDate();
        let start;
        let end;

        switch (period) {
            case "this_month":
                start = new Date(year, month, 1);
                end = new Date(year, month + 1, 0);
                break;
            case "this_quarter": {
                const qStart = ReportsPage._quarterStart(month);
                start = new Date(year, qStart, 1);
                end = new Date(year, qStart + 3, 0);
                break;
            }
            case "this_year":
                start = new Date(year, 0, 1);
                end = new Date(year, 11, 31);
                break;
            case "this_year_to_date":
                start = new Date(year, 0, 1);
                end = today;
                break;
            case "last_month":
                start = new Date(year, month - 1, 1);
                end = new Date(year, month, 0);
                break;
            case "last_quarter": {
                const thisQuarterStart = ReportsPage._quarterStart(month);
                start = new Date(year, thisQuarterStart - 3, 1);
                end = new Date(year, thisQuarterStart, 0);
                break;
            }
            case "last_year":
                start = new Date(year - 1, 0, 1);
                end = new Date(year - 1, 11, 31);
                break;
            case "last_year_to_date":
                start = new Date(year - 1, 0, 1);
                end = new Date(year - 1, month, Math.min(day, new Date(year - 1, month + 1, 0).getDate()));
                break;
            case "custom":
                return {
                    start: customStart || ReportsPage._isoDate(new Date(year, 0, 1)),
                    end: customEnd || ReportsPage._isoDate(today),
                };
            default:
                start = new Date(year, 0, 1);
                end = today;
                break;
        }

        return {
            start: ReportsPage._isoDate(start),
            end: ReportsPage._isoDate(end),
        };
    },

    getAsOfDate(period, customEnd = null) {
        if (period === "custom") return customEnd || todayISO();
        return ReportsPage.getDateRange(period).end;
    },

    customRangeHtml(initialStart, initialEnd) {
        return `
            <div id="report-custom-range" style="display:none; margin:4px 0 12px 0; font-size:11px; align-items:center; gap:8px;">
                <label for="report-custom-start">From:</label>
                <input id="report-custom-start" type="date" value="${initialStart}">
                <label for="report-custom-end">To:</label>
                <input id="report-custom-end" type="date" value="${initialEnd}">
            </div>`;
    },

    toggleCustomRange() {
        const select = $("#report-period-select");
        const row = $("#report-custom-range");
        if (!select || !row) return;
        row.style.display = select.value === "custom" ? "flex" : "none";
    },

    async openPeriodModal(title, initialPeriod, loadContent, label = "Dates", useAsOfOnly = false, opts = {}) {
        // opts.reportType (string) — when set, adds an "Add to Saved Reports" button
        // that captures the current period/range as parameters.
        // opts.prefill ({period?, start_date?, end_date?, as_of_date?}) —
        // used when reopening a saved report or a view's address; overrides
        // initialPeriod and pre-populates the date inputs. Dates with no
        // period mean a custom range; a period nobody knows is ignored.
        // opts.view (string) — the view's address name (ReportsPage._VIEWS):
        // each render puts the period and dates on the address bar, with
        // opts.params (an object: class_id, account_id, …) ahead of them.
        // opts.params is kept by reference and read on every render: a
        // control in the toolbar changes it through ReportsPage.setParam
        // and the view redraws on the new address. It rides into a saved
        // report's parameters too, so a class, a job or a column choice
        // reopens with the dates.
        // opts.toolbar (html) — controls drawn once, beside the period
        // select, that stay as the report redraws (a class picker, Prev /
        // Next, a column chooser); the report's own body is redrawn by
        // loadContent(period, range, params) on every change.
        // opts.wide — the wide dialog (openModal's), for a grid with a
        // column per class or job.
        const reportType = opts.reportType || null;
        const prefill = opts.prefill || {};
        const view = opts.view || null;
        const params = opts.params || {};

        const currentYear = new Date().getFullYear();
        const defaultCustomStart = prefill.start_date || `${currentYear}-01-01`;
        const defaultCustomEnd = prefill.end_date || prefill.as_of_date || todayISO();
        const known = ReportsPage.periodOptions('').includes(`value="${prefill.period}"`);
        const dated = !!(prefill.start_date || prefill.end_date || prefill.as_of_date);
        const startingPeriod = (prefill.period && known) ? prefill.period : (dated ? 'custom' : initialPeriod);

        const saveBtn = reportType
            ? `<button class="btn btn-secondary" id="report-save-btn" data-write>Add to Saved Reports…</button>`
            : '';

        openModal(title, `
            <div class="form-grid report-toolbar" style="margin-bottom:4px;">
                <div class="form-group">
                    <label for="report-period-select">${label}</label>
                    <select id="report-period-select">${ReportsPage.periodOptions(startingPeriod)}</select>
                </div>
                ${opts.toolbar || ''}
            </div>
            ${ReportsPage.customRangeHtml(defaultCustomStart, defaultCustomEnd)}
            <div id="report-content">
                <div style="font-size:11px; color:var(--gray-500);">Loading report...</div>
            </div>
            <div class="form-actions">
                ${saveBtn}
                <button class="btn btn-secondary" onclick="closeModal()">Close</button>
            </div>`, { wide: !!opts.wide });

        const select = $("#report-period-select");
        const startInput = $("#report-custom-start");
        const endInput = $("#report-custom-end");
        const content = $("#report-content");

        // A pasted address with a date that is not one: the date input
        // refuses it and the default stands. Said, rather than other dates
        // quietly shown (R7 review); the address is then rewritten to the
        // dates in use.
        const asOfKey = prefill.end_date ? 'end_date' : 'as_of_date';
        const dates = useAsOfOnly ? [[asOfKey, endInput]] : [['start_date', startInput], ['end_date', endInput]];
        for (const [key, input] of dates) {
            if (prefill[key] && input.value !== prefill[key]) toast(`${key} in the address is not a date (${prefill[key]}) — ignored`, 'error');
        }
        if (prefill.period && !known) toast(`period in the address is not one of the choices (${prefill.period}) — ignored`, 'error');

        // Track current params so the Save button captures fresh values.
        let currentParams = {};

        const render = async () => {
            ReportsPage.toggleCustomRange();
            content.innerHTML = `<div style="font-size:11px; color:var(--gray-500);">Loading report...</div>`;
            try {
                if (useAsOfOnly) {
                    const asOfDate = ReportsPage.getAsOfDate(select.value, endInput.value || todayISO());
                    currentParams = { period: select.value, as_of_date: asOfDate };
                    if (view) ReportsPage.setAddress(view, { ...params, ...currentParams });
                    content.innerHTML = await loadContent(select.value, { as_of_date: asOfDate }, params);
                } else {
                    const range = ReportsPage.getDateRange(select.value, startInput.value, endInput.value);
                    currentParams = { period: select.value, start_date: range.start, end_date: range.end };
                    if (view) ReportsPage.setAddress(view, { ...params, ...currentParams });
                    content.innerHTML = await loadContent(select.value, range, params);
                }
            } catch (err) {
                content.innerHTML = `<div class="empty-state"><p>${escapeHtml(err.message)}</p></div>`;
            }
        };
        // The open report, for its toolbar's controls (ReportsPage.setParam,
        // ReportsPage.refresh): one period dialog is open at a time.
        ReportsPage._live = { view, params, render, select };

        select.addEventListener("change", render);
        startInput.addEventListener("change", () => { if (select.value === "custom" && !useAsOfOnly) render(); });
        endInput.addEventListener("change", () => { if (select.value === "custom") render(); });

        if (reportType) {
            const sb = $("#report-save-btn");
            if (sb) sb.addEventListener("click", () => {
                ReportsPage.saveCurrent(reportType, { ...params, ...currentParams });
            });
        }

        await render();
    },

    // Redraw the open report on its current period and params: what a
    // toolbar control does after changing something.
    refresh() {
        if (ReportsPage._live) ReportsPage._live.render();
    },

    // Set one of the open report's params (a class, a job, a column
    // choice) and redraw; an empty value removes it from the address.
    setParam(key, value, redraw = true) {
        const live = ReportsPage._live;
        if (!live) return;
        if (value === null || value === undefined || value === '') delete live.params[key];
        else live.params[key] = value;
        if (redraw) live.render();
    },

    async profitLoss(prefill) {
        // A P&L saved or addressed with a class is that class's own (#235):
        // the address is replaced by the class view's, so Back is not a
        // loop through the redirect.
        if (prefill && parseInt(prefill.class_id, 10)) {
            if (App.parseHash(location.hash || '#/').path === '/reports/profit-loss') {
                history.replaceState(history.state, '', ReportsPage.viewUrl('profit-loss-class', prefill));
            }
            await ReportsPage.profitLossOfClass(prefill.class_id, null, prefill);
            return;
        }
        await ReportsPage.openPeriodModal(T("Profit & Loss"), "this_year_to_date", async (_period, range) => {
            const data = await API.get(`/reports/profit-loss?start_date=${range.start}&end_date=${range.end}`);
            const pdfBtn = ReportsPage._exportButtons('profit-loss', `start_date=${range.start}&end_date=${range.end}`);
            // Build the onclick payload outside the template so we can
            // HTML-escape the embedded double quotes from JSON.stringify().
            // Otherwise the inner " breaks the outer onclick="…" attribute.
            const drillCall = (i) => escapeHtml(
                `ReportsPage.openDrillDown(${i.account_id},${JSON.stringify(i.account_name)},${JSON.stringify(range.start)},${JSON.stringify(range.end)},null,null,'profit-loss')`
            );
            const section = (items) => {
                if (!items.length) return `<tr><td colspan="2" style="color:var(--gray-400);">None</td></tr>`;
                return items.map(i =>
                    `<tr><td style="padding-left:24px;">
                        <a href="javascript:void(0)" style="color:var(--text-link); text-decoration:none;"
                           onclick="${drillCall(i)}">${escapeHtml(i.account_name)}</a>
                        </td><td class="amount">${formatCurrency(i.amount)}</td></tr>`
                ).join("");
            };
            return `${pdfBtn}
                <p style="margin-bottom:12px; color:var(--gray-500);">${formatDate(data.start_date)} &mdash; ${formatDate(data.end_date)}</p>
                <div class="table-container"><table>
                    <thead><tr><th scope="col">Account</th><th scope="col" class="amount">Amount</th></tr></thead>
                    <tbody>
                        <tr><td><strong>${T('Income')}</strong></td><td></td></tr>
                        ${section(data.income)}
                        <tr style="font-weight:600; background:var(--gray-50);"><td>${T('Total Income')}</td><td class="amount">${formatCurrency(data.total_income)}</td></tr>
                        <tr><td><strong>Cost of Goods Sold</strong></td><td></td></tr>
                        ${section(data.cogs)}
                        <tr style="font-weight:600; background:var(--gray-50);"><td>Gross Profit</td><td class="amount">${formatCurrency(data.gross_profit)}</td></tr>
                        <tr><td><strong>Expenses</strong></td><td></td></tr>
                        ${section(data.expenses)}
                        <tr style="font-weight:600; background:var(--gray-50);"><td>Total Expenses</td><td class="amount">${formatCurrency(data.total_expenses)}</td></tr>
                        <tr style="font-weight:700; font-size:15px; background:var(--primary-light);"><td>${T('Net Income')}</td><td class="amount">${formatCurrency(data.net_income)}</td></tr>
                    </tbody>
                </table></div>`;
        }, "Dates", false, { reportType: 'profit_loss', view: 'profit-loss', prefill });
    },

    async balanceSheet(prefill) {
        await ReportsPage.openPeriodModal(T("Balance Sheet"), "this_year_to_date", async (_period, params) => {
            const data = await API.get(`/reports/balance-sheet?as_of_date=${params.as_of_date}`);
            const pdfBtn = ReportsPage._exportButtons('balance-sheet', `as_of_date=${params.as_of_date}`);
            const drillCall = (i) => escapeHtml(
                `ReportsPage.openDrillDown(${i.account_id},${JSON.stringify(i.account_name)},null,${JSON.stringify(params.as_of_date)},null,null,'balance-sheet')`
            );
            const section = (items) => items.map(i =>
                `<tr><td style="padding-left:24px;">
                    <a href="javascript:void(0)" style="color:var(--text-link); text-decoration:none;"
                       onclick="${drillCall(i)}">${escapeHtml(i.account_name)}</a>
                    </td><td class="amount">${formatCurrency(i.amount)}</td></tr>`
            ).join("") || `<tr><td colspan="2" style="color:var(--gray-400);">None</td></tr>`;
            return `${pdfBtn}
                <p style="margin-bottom:12px; color:var(--gray-500);">As of ${formatDate(data.as_of_date)}</p>
                <div class="table-container"><table>
                    <thead><tr><th scope="col">Account</th><th scope="col" class="amount">Amount</th></tr></thead>
                    <tbody>
                        <tr><td><strong>Assets</strong></td><td></td></tr>
                        ${section(data.assets)}
                        <tr style="font-weight:600; background:var(--gray-50);"><td>Total Assets</td><td class="amount">${formatCurrency(data.total_assets)}</td></tr>
                        <tr><td><strong>Liabilities</strong></td><td></td></tr>
                        ${section(data.liabilities)}
                        <tr style="font-weight:600; background:var(--gray-50);"><td>Total Liabilities</td><td class="amount">${formatCurrency(data.total_liabilities)}</td></tr>
                        <tr><td><strong>${T('Equity')}</strong></td><td></td></tr>
                        ${section(data.equity)}
                        <tr style="font-weight:600; background:var(--gray-50);"><td>${T('Total Equity')}</td><td class="amount">${formatCurrency(data.total_equity)}</td></tr>
                    </tbody>
                </table></div>`;
        }, "As Of", true, { reportType: 'balance_sheet', view: 'balance-sheet', prefill });
    },

    async salesTax(prefill) {
        await ReportsPage.openPeriodModal("Sales Tax Report", "this_year_to_date", async (_period, range) => {
            const data = await API.get(`/reports/sales-tax?start_date=${range.start}&end_date=${range.end}`);
            // Credit memos come back as negative rows; a document with
            // nothing taxable shows no rate rather than "8.25%, $0.00".
            const rows = data.items.map(i =>
                `<tr>
                    <td>${formatDate(i.date)}</td>
                    <td>${escapeHtml(i.number)}${i.type === 'credit_memo' ? ` <span class="badge" style="font-size:9px">Credit Memo</span>` : ''}</td>
                    <td>${escapeHtml(i.customer_name)}</td>
                    <td class="amount">${formatCurrency(i.subtotal)}</td>
                    <td class="amount">${formatCurrency(i.taxable)}</td>
                    <td class="amount">${i.tax_rate == null ? '—' : SalesLines.taxPercent(i.tax_rate) + '%'}</td>
                    <td class="amount">${formatCurrency(i.tax_amount)}</td>
                </tr>`
            ).join("");
            const ledger = data.ledger;
            const agrees = ledger && Math.abs(ledger.difference) < 0.005;
            const reconcile = ledger ? `
                    <div style="font-size:12px; margin-top:8px; border-top:1px solid var(--gray-200); padding-top:6px;">
                        ${escapeHtml(ledger.account_number)} ${escapeHtml(ledger.account_name)}: tax posted this period <strong>${formatCurrency(ledger.tax_posted)}</strong>
                        ${agrees
                            ? '— agrees with this report.'
                            : `— <span style="color:var(--danger); font-weight:700;">differs from this report by ${formatCurrency(ledger.difference)}</span>. Something other than a sale or credit memo posted to the account in these dates (tax on a bill, a journal entry, a void of an earlier sale).`}
                        <div>Paid this period: ${formatCurrency(ledger.payments)} · Owed at ${formatDate(data.end_date)}: <strong>${formatCurrency(ledger.balance)}</strong></div>
                        ${Math.abs(ledger.purchase_tax_to_date || 0) >= 0.005 ? `<div style="margin-top:6px;">
                            Sales tax paid to suppliers on bills entered before SlowBooks Pro 2.18 was posted to ${escapeHtml(ledger.account_name)}, lowering that balance by <strong>${formatCurrency(ledger.purchase_tax)}</strong> this period; since 2.18 that tax is part of what the purchase cost. To correct it, post one journal entry: debit the expense or cost-of-goods account those purchases used, and credit ${escapeHtml(ledger.account_number)} ${escapeHtml(ledger.account_name)} <strong>${formatCurrency(ledger.purchase_tax_to_date)}</strong> (the total to ${formatDate(data.end_date)}).</div>` : ''}
                    </div>` : '';
            return `
                <p style="margin-bottom:12px; color:var(--gray-500);">${formatDate(data.start_date)} &mdash; ${formatDate(data.end_date)}</p>
                <div class="table-container"><table>
                    <thead><tr><th scope="col">Date</th><th scope="col">${T('Invoice')} / Credit Memo</th><th scope="col">${T('Customer')}</th><th scope="col" class="amount">Sales</th><th scope="col" class="amount">Taxable</th><th scope="col" class="amount">Rate</th><th scope="col" class="amount">Tax</th></tr></thead>
                    <tbody>${rows || '<tr><td colspan="7" style="text-align:center; color:var(--gray-400);">No taxable sales</td></tr>'}</tbody>
                </table></div>
                <div style="margin-top:12px; padding:8px; background:var(--gray-50); border:1px solid var(--gray-200);">
                    <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:4px;">
                        <span>Total Sales: <strong>${formatCurrency(data.total_sales)}</strong></span>
                        <span>Taxable: <strong>${formatCurrency(data.total_taxable)}</strong></span>
                        <span>Non-Taxable: <strong>${formatCurrency(data.total_non_taxable)}</strong></span>
                    </div>
                    <div style="font-size:12px;">Tax on sales ${formatCurrency(data.tax_on_sales)} less tax on credit memos ${formatCurrency(data.tax_credited)}</div>
                    <div style="font-size:14px; font-weight:700; color:var(--qb-navy);">Tax Collected: ${formatCurrency(data.total_tax)}</div>
                    ${reconcile}
                </div>`;
        }, "Dates", false, { reportType: 'sales_tax', view: 'sales-tax', prefill });
    },

    async generalLedger(prefill) {
        await ReportsPage.openPeriodModal("General Ledger", "this_year_to_date", async (_period, range) => {
            const data = await API.get(`/reports/general-ledger?start_date=${range.start}&end_date=${range.end}`);
            let html = `${ReportsPage._exportButtons('general-ledger', `start_date=${range.start}&end_date=${range.end}`)}
                <p style="margin-bottom:12px; color:var(--gray-500);">${formatDate(data.start_date)} &mdash; ${formatDate(data.end_date)}</p>`;
            if (data.accounts.length === 0) {
                html += `<div class="empty-state"><p>No journal entries found</p></div>`;
            } else {
                // An account's name opens its register for these dates, as the
                // P&L's and Balance Sheet's do (#224). The onclick payload is
                // built outside the template and HTML-escaped, as profitLoss
                // does, so JSON.stringify's quotes can't break the attribute.
                const drillCall = (acct) => escapeHtml(
                    `ReportsPage.openDrillDown(${acct.account_id},${JSON.stringify(acct.account_name)},${JSON.stringify(range.start)},${JSON.stringify(range.end)},null,null,'general-ledger')`
                );
                for (const acct of data.accounts) {
                    const name = acct.account_id
                        ? `<a href="javascript:void(0)" style="color:var(--text-link); text-decoration:none;" onclick="${drillCall(acct)}">${escapeHtml(acct.account_name)}</a>`
                        : escapeHtml(acct.account_name);
                    html += `<h3 style="margin:12px 0 4px; font-size:12px; color:var(--qb-navy);">${escapeHtml(acct.account_number)} &mdash; ${name}</h3>`;
                    html += `<div class="table-container"><table>
                        <thead><tr><th scope="col">Date</th><th scope="col">Description</th><th scope="col">Reference</th><th scope="col">Source</th><th scope="col" class="amount">Debit</th><th scope="col" class="amount">Credit</th><th scope="col" class="amount">Balance</th></tr></thead><tbody>`;
                    html += `<tr style="color:var(--gray-500);"><td></td><td colspan="5">Balance brought forward</td><td class="amount">${formatCurrency(acct.opening_balance)}</td></tr>`;
                    for (const e of acct.entries) {
                        html += `<tr>
                            <td>${formatDate(e.date)}</td>
                            <td>${escapeHtml(e.description)}</td>
                            <td>${escapeHtml(e.reference)}</td>
                            <td style="font-size:10px; color:var(--gray-500);">${escapeHtml(e.source_type)}</td>
                            <td class="amount">${e.debit > 0 ? formatCurrency(e.debit) : ""}</td>
                            <td class="amount">${e.credit > 0 ? formatCurrency(e.credit) : ""}</td>
                            <td class="amount">${formatCurrency(e.running_balance)}</td>
                        </tr>`;
                    }
                    html += `<tr style="font-weight:600; background:var(--gray-50);">
                        <td colspan="4">Period total</td>
                        <td class="amount">${formatCurrency(acct.total_debit)}</td>
                        <td class="amount">${formatCurrency(acct.total_credit)}</td>
                        <td class="amount">${formatCurrency(acct.closing_balance)}</td>
                    </tr></tbody></table></div>`;
                }
            }
            return html;
        }, "Dates", false, { reportType: 'general_ledger', view: 'general-ledger', prefill });
    },

    async incomeByCustomer(prefill) {
        await ReportsPage.openPeriodModal(T("Income by Customer"), "this_year_to_date", async (_period, range) => {
            const data = await API.get(`/reports/income-by-customer?start_date=${range.start}&end_date=${range.end}`);
            // Sales before tax, the tax beside it; Paid includes money not
            // yet applied to an invoice, and Balance is net of it.
            let rows = data.items.map(i =>
                `<tr>
                    <td>${escapeHtml(i.customer_name)}</td>
                    <td class="amount">${i.invoice_count}</td>
                    <td class="amount">${formatCurrency(i.total_sales)}</td>
                    <td class="amount">${formatCurrency(i.total_tax || 0)}</td>
                    <td class="amount">${formatCurrency(i.total_paid)}</td>
                    <td class="amount">${formatCurrency(i.total_balance)}</td>
                </tr>`
            ).join("");
            rows += `<tr style="font-weight:700; background:var(--gray-50);">
                <td>TOTAL</td>
                <td class="amount">${data.items.reduce((sum, item) => sum + item.invoice_count, 0)}</td>
                <td class="amount">${formatCurrency(data.total_sales)}</td>
                <td class="amount">${formatCurrency(data.total_tax || 0)}</td>
                <td class="amount">${formatCurrency(data.total_paid)}</td>
                <td class="amount">${formatCurrency(data.total_balance)}</td>
            </tr>`;
            return `
                <p style="margin-bottom:12px; color:var(--gray-500);">${formatDate(data.start_date)} &mdash; ${formatDate(data.end_date)}</p>
                <div class="table-container"><table>
                    <thead><tr><th scope="col">${T('Customer')}</th><th scope="col" class="amount">${T('Invoices')}</th><th scope="col" class="amount">Sales</th><th scope="col" class="amount">Sales Tax</th><th scope="col" class="amount">Paid</th><th scope="col" class="amount">Balance</th></tr></thead>
                    <tbody>${rows || '<tr><td colspan="6" style="text-align:center; color:var(--gray-400);">No sales data</td></tr>'}</tbody>
                </table></div>`;
        }, "Dates", false, { reportType: 'income_by_customer', view: 'income-by-customer', prefill });
    },

    async customerStatementPicker() {
        ReportsPage.setAddress('customer-statement', {});
        const customers = await API.get("/customers?active_only=true");
        const custOpts = customers.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join("");
        openModal(T("Customer Statement"), `
            <form onsubmit="ReportsPage.openStatement(event)" data-readonly-ok>
                <!-- minmax(0, …) and width:100%: a select sizes itself to its
                     longest option, and a 120-character customer name pushed
                     As of past the dialog's edge (macbase1, F22). The picked
                     name still shows in full in the open list. -->
                <div class="form-grid" style="grid-template-columns:minmax(0, 2fr) minmax(0, 1fr);">
                    <div class="form-group" style="min-width:0;"><label>${T('Customer')} *</label>
                        <select name="customer_id" required style="width:100%; min-width:0; max-width:100%;"><option value="">Select...</option>${custOpts}</select></div>
                    <div class="form-group"><label>As of Date</label>
                        <input name="as_of_date" type="date" value="${todayISO()}"></div>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">Generate PDF</button>
                </div>
            </form>`);
    },

    openStatement(e) {
        e.preventDefault();
        const form = e.target;
        const cid = form.customer_id.value;
        const asOf = form.as_of_date.value || todayISO();
        window.open(`/api/reports/customer-statement/${cid}/pdf?as_of_date=${asOf}`, "_blank");
        closeModal();
    },

    async arAging(prefill) {
        await ReportsPage.openPeriodModal(T("Accounts Receivable Aging"), "this_year_to_date", async (_period, params) => {
            const data = await API.get(`/reports/ar-aging?as_of_date=${params.as_of_date}`);
            // The API nets a customer's credits (unapplied payments and
            // credit memos) into Current; show Current gross and the
            // credits on their own, so the row still adds up to Total and
            // Total is what account 1100 says.
            const credit = (r) => r.unapplied_credits || 0;
            const agingRow = (r, name, style = '') => `<tr style="${style}">
                    <td>${name}</td>
                    <td class="amount">${formatCurrency(r.current + credit(r))}</td>
                    <td class="amount">${formatCurrency(r.over_30)}</td>
                    <td class="amount">${formatCurrency(r.over_60)}</td>
                    <td class="amount">${formatCurrency(r.over_90)}</td>
                    <td class="amount">${credit(r) ? formatCurrency(-credit(r)) : ''}</td>
                    <td class="amount" style="font-weight:600;">${formatCurrency(r.total)}</td>
                </tr>`;
            let rows = data.items.map(i => agingRow(i, escapeHtml(i.customer_name))).join("");
            const t = data.totals;
            rows += agingRow(t, 'TOTAL', 'font-weight:700; background:var(--gray-50);');
            return `
                <p style="margin-bottom:12px; color:var(--gray-500);">As of ${formatDate(data.as_of_date)}</p>
                <div style="margin-bottom:12px; display:flex; gap:8px;" data-write>
                    <button class="btn btn-sm btn-secondary" onclick="ReportsPage.applyLateFees()">Apply Late Fees</button>
                    <button class="btn btn-sm btn-secondary" onclick="ReportsPage.batchEmailStatements()">Email All Overdue</button>
                    <select id="collection-letter-type" aria-label="Collection letter" style="font-size:11px; padding:2px 6px;">
                        <option value="30">30-Day Letter</option>
                        <option value="60">60-Day Letter</option>
                        <option value="90">90-Day Letter</option>
                    </select>
                    <button class="btn btn-sm btn-secondary" onclick="ReportsPage.sendCollectionLetters()">Send Collection Letters</button>
                </div>
                <div class="table-container"><table>
                    <thead><tr>
                        <th scope="col">${T('Customer')}</th><th scope="col" class="amount">Current</th><th scope="col" class="amount">1-30</th>
                        <th scope="col" class="amount">31-60</th><th scope="col" class="amount">61-90+</th><th scope="col" class="amount">Credits</th><th scope="col" class="amount">Total</th>
                    </tr></thead>
                    <tbody>${rows || '<tr><td colspan="7" style="text-align:center; color:var(--gray-400);">No outstanding receivables</td></tr>'}</tbody>
                </table></div>`;
        }, "As Of", true, { reportType: 'ar_aging', view: 'ar-aging', prefill });
    },

    async apAging(prefill) {
        await ReportsPage.openPeriodModal("Accounts Payable Aging", "this_year_to_date", async (_period, params) => {
            const data = await API.get(`/reports/ap-aging?as_of_date=${params.as_of_date}`);
            let rows = data.items.map(i =>
                `<tr>
                    <td>${escapeHtml(i.vendor_name)}</td>
                    <td class="amount">${formatCurrency(i.current)}</td>
                    <td class="amount">${formatCurrency(i.over_30)}</td>
                    <td class="amount">${formatCurrency(i.over_60)}</td>
                    <td class="amount">${formatCurrency(i.over_90)}</td>
                    <td class="amount" style="font-weight:600;">${formatCurrency(i.total)}</td>
                </tr>`
            ).join("");
            const t = data.totals;
            rows += `<tr style="font-weight:700; background:var(--gray-50);">
                <td>TOTAL</td>
                <td class="amount">${formatCurrency(t.current)}</td>
                <td class="amount">${formatCurrency(t.over_30)}</td>
                <td class="amount">${formatCurrency(t.over_60)}</td>
                <td class="amount">${formatCurrency(t.over_90)}</td>
                <td class="amount">${formatCurrency(t.total)}</td>
            </tr>`;
            return `
                <p style="margin-bottom:12px; color:var(--gray-500);">As of ${formatDate(data.as_of_date)}</p>
                <div class="table-container"><table>
                    <thead><tr>
                        <th scope="col">Vendor</th><th scope="col" class="amount">Current</th><th scope="col" class="amount">1-30</th>
                        <th scope="col" class="amount">31-60</th><th scope="col" class="amount">61-90+</th><th scope="col" class="amount">Total</th>
                    </tr></thead>
                    <tbody>${rows || '<tr><td colspan="6" style="text-align:center; color:var(--gray-400);">No outstanding payables</td></tr>'}</tbody>
                </table></div>`;
        }, "As Of", true, { reportType: 'ap_aging', view: 'ap-aging', prefill });
    },

    async trialBalance(prefill) {
        await ReportsPage.openPeriodModal("Trial Balance", "this_year_to_date", async (_period, range) => {
            const data = await API.get(`/reports/trial-balance?start_date=${range.start}&end_date=${range.end}`);
            let rows = data.items.map(i =>
                `<tr>
                    <td>${escapeHtml(i.account_number)}</td>
                    <td>${escapeHtml(i.account_name)}</td>
                    <td style="font-size:10px; color:var(--gray-400);">${i.account_type}</td>
                    <td class="amount">${i.total_debit > 0 ? formatCurrency(i.total_debit) : ''}</td>
                    <td class="amount">${i.total_credit > 0 ? formatCurrency(i.total_credit) : ''}</td>
                    <td class="amount">${formatCurrency(i.net_balance)}</td>
                </tr>`
            ).join('');
            const diffColor = Math.abs(data.difference) < 0.01 ? 'var(--text-success)' : 'var(--text-danger)';
            rows += `<tr style="font-weight:700; background:var(--gray-50);">
                <td colspan="3">TOTALS</td>
                <td class="amount">${formatCurrency(data.total_debit)}</td>
                <td class="amount">${formatCurrency(data.total_credit)}</td>
                <td class="amount" style="color:${diffColor}">${formatCurrency(data.difference)}</td>
            </tr>`;
            return `${ReportsPage._exportButtons('trial-balance', `start_date=${range.start}&end_date=${range.end}`)}
                <p style="margin-bottom:12px; color:var(--gray-500);">${formatDate(data.start_date)} &mdash; ${formatDate(data.end_date)}</p>
                <div class="table-container"><table>
                    <thead><tr><th scope="col">Number</th><th scope="col">Account</th><th scope="col">Type</th><th scope="col" class="amount">Debit</th><th scope="col" class="amount">Credit</th><th scope="col" class="amount">Net</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table></div>`;
        }, "Dates", false, { view: 'trial-balance', prefill });
    },

    async cashFlow(prefill) {
        await ReportsPage.openPeriodModal("Cash Flow Statement", "this_year_to_date", async (_period, range) => {
            const data = await API.get(`/reports/cash-flow?start_date=${range.start}&end_date=${range.end}`);
            // Indirect method (banking, exploratory 2.17.3 W-M6/F18): net
            // income, what moved no cash, the change in working capital;
            // then investing and financing; the net change is the bank's.
            const rows = (items, indent) => items.length
                ? items.map(i => `<tr><td style="padding-left:${indent}px;">${escapeHtml(i.account_name)}</td><td class="amount">${formatCurrency(i.amount)}</td></tr>`).join('')
                : `<tr><td style="padding-left:${indent}px; color:var(--gray-400);">None</td><td></td></tr>`;
            const head = (title, indent = 0) => `<tr><td style="padding-left:${indent}px;"><strong>${title}</strong></td><td></td></tr>`;
            const total = (title, amount) => `<tr style="font-weight:600; background:var(--gray-50);"><td>Total ${title}</td><td class="amount">${formatCurrency(amount)}</td></tr>`;
            const adjustments = data.adjustments || [];
            const workingCapital = data.working_capital || [];
            const operating = `${head('Operating Activities')}
                <tr><td style="padding-left:24px;">${T('Net Income')}</td><td class="amount">${formatCurrency(data.net_income)}</td></tr>
                ${adjustments.length ? head('Adjustments for non-cash items', 24) + rows(adjustments, 48) : ''}
                ${workingCapital.length ? head('Changes in working capital', 24) + rows(workingCapital, 48) : ''}
                ${total('Operating Activities', data.total_operating)}`;
            return `
                <p style="margin-bottom:12px; color:var(--gray-500);">${formatDate(data.start_date)} &mdash; ${formatDate(data.end_date)}</p>
                <div class="table-container"><table>
                    <thead><tr><th scope="col">Account</th><th scope="col" class="amount">Amount</th></tr></thead>
                    <tbody>
                        ${operating}
                        ${head('Investing Activities')}${rows(data.investing, 24)}${total('Investing Activities', data.total_investing)}
                        ${head('Financing Activities')}${rows(data.financing, 24)}${total('Financing Activities', data.total_financing)}
                        <tr style="font-weight:700; font-size:15px; background:var(--primary-light);">
                            <td>Net Change in Cash</td><td class="amount">${formatCurrency(data.net_change)}</td>
                        </tr>
                        <tr><td>Cash at beginning of period</td><td class="amount">${formatCurrency(data.beginning_cash)}</td></tr>
                        <tr style="font-weight:700;"><td>Cash at end of period</td><td class="amount">${formatCurrency(data.ending_cash)}</td></tr>
                    </tbody>
                </table></div>`;
        }, "Dates", false, { reportType: 'cash_flow', view: 'cash-flow', prefill });
    },

    // #/reports/1099-summary?year=2025 opens the year's summary straight
    // away (R7); the address takes the year when Generate is clicked.
    async report1099(prefill) {
        const currentYear = new Date().getFullYear();
        const year = /^\d{4}$/.test((prefill || {}).year || '') ? prefill.year : null;
        ReportsPage.setAddress('1099-summary', { year });
        openModal('1099 Summary', `
            <div class="form-grid" style="margin-bottom:12px;">
                <div class="form-group"><label for="report-1099-year">Year</label>
                    <input id="report-1099-year" type="number" value="${year || currentYear}" style="width:100px;"></div>
                <div class="form-group" style="align-self:end;">
                    <button type="button" class="btn btn-primary" onclick="ReportsPage.load1099()">Generate</button></div>
            </div>
            <div id="report-1099-content"><div style="font-size:11px; color:var(--gray-500);">Select year and click Generate</div></div>
            <div class="form-actions"><button type="button" class="btn btn-secondary" onclick="closeModal()">Close</button></div>`);
        if (year) await ReportsPage.load1099();
    },

    async load1099() {
        const year = $('#report-1099-year').value;
        ReportsPage.setAddress('1099-summary', { year });
        const content = $('#report-1099-content');
        content.innerHTML = '<div style="font-size:11px; color:var(--gray-500);">Loading...</div>';
        try {
            const data = await API.get(`/reports/1099-summary?year=${year}`);
            if (data.items.length === 0) {
                content.innerHTML = '<div class="empty-state"><p>No 1099 vendors found. Flag vendors as 1099 in the Vendors page.</p></div>';
                return;
            }
            let rows = data.items.map(i =>
                `<tr${i.above_threshold ? ' style="background:var(--primary-light);"' : ''}>
                    <td>${escapeHtml(i.vendor_name)}</td>
                    <td>${escapeHtml(i.tax_id)}</td>
                    <td>${escapeHtml(i.vendor_1099_type)}</td>
                    <td class="amount">${formatCurrency(i.total_paid)}</td>
                    <td>${i.above_threshold ? '<span style="color:var(--danger); font-weight:700;">REPORT</span>' : ''}</td>
                </tr>`
            ).join('');
            rows += `<tr style="font-weight:700; background:var(--gray-50);">
                <td colspan="3">TOTAL</td><td class="amount">${formatCurrency(data.total)}</td>
                <td>${data.vendors_above_threshold} vendor(s) above $${data.threshold}</td></tr>`;
            content.innerHTML = `
                <div class="table-container"><table>
                    <thead><tr><th scope="col">Vendor</th><th scope="col">Tax ID</th><th scope="col">Type</th><th scope="col" class="amount">Total Paid</th><th scope="col">Status</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table></div>`;
        } catch (err) { content.innerHTML = `<div style="color:var(--danger);">${escapeHtml(err.message)}</div>`; }
    },

    async applyLateFees() {
        if (!confirm('Apply late fees to all overdue invoices past the grace period?')) return;
        try {
            const result = await API.post('/invoices/apply-late-fees');
            toast(`Late fees applied to ${result.applied} of ${result.total_overdue} overdue invoices`);
        } catch (err) { toast(err.message, 'error'); }
    },

    async batchEmailStatements() {
        if (!confirm('Email statements to all customers with overdue invoices?')) return;
        try {
            const result = await API.post('/reports/batch-email-statements');
            if (!result.sent && !result.failed) {
                toast(Terms.text('No customer has an overdue invoice, so there was nothing to send.'));
                return;
            }
            // Only what actually went out is "sent"; a customer who didn't
            // get one is named, with the reason (explore 2.17.3, W-H7).
            ReportsPage._sendResult('Statements',
                `Sent ${result.sent} statement${result.sent === 1 ? '' : 's'}.`, result.errors || []);
        } catch (err) { toast(err.message, 'error'); }
    },

    _sendResult(title, headline, errors) {
        if (!errors.length) { toast(headline); return; }
        openModal(title, `
            <p>${escapeHtml(headline)} ${errors.length} could not be sent:</p>
            <ul style="margin:8px 0 12px 20px;">${errors.map(e => `<li>${escapeHtml(e)}</li>`).join('')}</ul>
            <div class="form-actions"><button type="button" class="btn btn-secondary" onclick="closeModal()">Close</button></div>`);
    },

    async sendCollectionLetters() {
        const letterType = $('#collection-letter-type')?.value || '30';
        if (!confirm(`Send ${letterType}-day collection letters to all qualifying customers?`)) return;
        try {
            const result = await API.post('/reports/collection-letters', {
                letter_type: letterType,
                send_email: true,
            });
            ReportsPage._sendResult('Collection Letters',
                `Generated ${result.generated} letter${result.generated === 1 ? '' : 's'}, emailed ${result.emailed}.`, result.errors || []);
        } catch (err) { toast(err.message, 'error'); }
    },
};

// ---------------------------------------------------------------------------
// The wide grid: P&L accounts down the side, one column per class (or job)
// across, a Total column (R1, #231; R13, #242). The Account column and the
// header row stay put while the rest scrolls sideways inside its container,
// so the Total column is reachable however many columns there are. Above
// the table: a "Go to" picker (the type-ahead attaches to it), ‹ Prev /
// Next ›, and a status line a screen reader hears ("Column 4 of 12: Site
// Prep"). With the grid or the picker focused, ←/→ move one column, Home
// and End go to the first and last, Enter opens the column's own report.
// Nothing of the jump state reaches the address, a saved report or an
// export: it is a place in the table, not a filter.
// ---------------------------------------------------------------------------
ReportsPage._grid = { current: -1, count: 0, names: [] };

// spec: { title, noun (lowercase, T()'d), kind ('class' | 'job': the
// picker's name, so the type-ahead knows it lists them), columns
// [{id, name, income, cogs, gross_profit, expenses, net_income}], accounts
// {income, cogs, expenses} with amounts[] aligned to columns, totals
// {income, cogs, gross_profit, expenses, net_income}, drill(account, col)
// → call for an amount, head(col) → call for a heading, sum(col, key) →
// call for a subtotal cell (or null), note (html above the table),
// totalLabel }
ReportsPage._pivotGrid = function (spec) {
    const cols = spec.columns;
    const n = cols.length;
    const totals = spec.totals;
    const link = (call, text) => `<a href="javascript:void(0)" class="grid-link" style="color:var(--text-link); text-decoration:none;" onclick="${escapeHtml(call)}">${text}</a>`;
    const empties = cols.map((_, i) => `<td data-col="${i}"></td>`).join('') + '<td></td>';
    const label = a => `${a.account_number ? escapeHtml(a.account_number) + ' - ' : ''}${escapeHtml(a.account_name)}`;
    const cell = (a, i) => {
        const amount = a.amounts[i];
        if (!amount) return `<td class="amount" data-col="${i}"></td>`;
        return `<td class="amount" data-col="${i}">${link(spec.drill(a, cols[i]), formatCurrency(amount))}</td>`;
    };
    const section = (title, rows) => `<tr class="grid-section"><th scope="row">${title}</th>${empties}</tr>`
        + (rows.length
            ? rows.map(a => `<tr><th scope="row" style="padding-left:24px;">${label(a)}</th>${cols.map((_, i) => cell(a, i)).join('')}<td class="amount">${formatCurrency(a.total)}</td></tr>`).join('')
            : `<tr><td style="padding-left:24px; color:var(--gray-400);">None</td>${empties}</tr>`);
    const sum = (title, key, style) => `<tr style="${style}"><th scope="row">${title}</th>${cols.map((c, i) => {
        const text = formatCurrency(c[key]);
        const call = spec.sum ? spec.sum(c, key) : null;
        return `<td class="amount" data-col="${i}">${call ? link(call, text) : text}</td>`;
    }).join('')}<td class="amount">${formatCurrency(totals[key])}</td></tr>`;
    const subtotal = 'font-weight:600; background:var(--gray-50);';
    const heads = cols.map((c, i) => {
        const call = spec.head ? spec.head(c) : null;
        return `<th scope="col" class="amount" data-col="${i}">${call ? link(call, escapeHtml(c.name)) : escapeHtml(c.name)}</th>`;
    }).join('');
    const jumpOpts = cols.map((c, i) => `<option value="${i}">${escapeHtml(c.name)}</option>`).join('');
    ReportsPage._grid = { current: -1, count: n, names: cols.map(c => c.name) };
    return `
        <div class="grid-toolbar" id="grid-toolbar" onkeydown="ReportsPage.gridKey(event)">
            <label for="grid-jump">Go to ${escapeHtml(spec.noun)}</label>
            <select id="grid-jump" name="${spec.kind}_jump" onchange="if (this.value !== '') ReportsPage.gridGo(parseInt(this.value, 10))"><option value="">Type a ${escapeHtml(spec.noun)}…</option>${jumpOpts}</select>
            <button type="button" class="btn btn-sm btn-secondary" aria-label="Previous ${escapeHtml(spec.noun)}" onclick="ReportsPage.gridStep(-1)">&lsaquo; Prev</button>
            <button type="button" class="btn btn-sm btn-secondary" aria-label="Next ${escapeHtml(spec.noun)}" onclick="ReportsPage.gridStep(1)">Next &rsaquo;</button>
            <span id="grid-live" class="grid-live" role="status" aria-live="polite"></span>
        </div>
        ${spec.note || ''}
        <div class="table-container table-container--scroll grid-scroll" id="grid-scroll" tabindex="0" role="region" aria-label="${escapeHtml(spec.title)}" onkeydown="ReportsPage.gridKey(event)">
            <table class="pivot-grid">
                <thead><tr><th scope="col">Account</th>${heads}<th scope="col" class="amount">${escapeHtml(spec.totalLabel || 'Total')}</th></tr></thead>
                <tbody>
                    ${section(T('Income'), spec.accounts.income)}
                    ${sum(T('Total Income'), 'income', subtotal)}
                    ${section('Cost of Goods Sold', spec.accounts.cogs)}
                    ${sum('Gross Profit', 'gross_profit', subtotal)}
                    ${section('Expenses', spec.accounts.expenses)}
                    ${sum('Total Expenses', 'expenses', subtotal)}
                    ${sum(T('Net Income'), 'net_income', 'font-weight:700; background:var(--primary-light);')}
                </tbody>
            </table>
        </div>`;
};

// Column i of the open grid: scrolled into view (the frozen Account
// column allowed for), highlighted, named in the picker and said aloud.
ReportsPage.gridGo = function (i) {
    const g = ReportsPage._grid;
    if (!g.count) return;
    i = Math.max(0, Math.min(g.count - 1, i));
    g.current = i;
    $$('#report-content .pivot-grid .is-current').forEach(el => el.classList.remove('is-current'));
    $$(`#report-content .pivot-grid [data-col="${i}"]`).forEach(el => el.classList.add('is-current'));
    const th = $(`#report-content .pivot-grid thead th[data-col="${i}"]`);
    const box = $('#grid-scroll');
    if (th && box) {
        // the last column brings the Total column beside it into view
        const fixed = box.querySelector('thead th:first-child');
        const edgeCell = i === g.count - 1 ? box.querySelector('thead th:last-child') : th;
        const b = box.getBoundingClientRect();
        const edge = b.left + (fixed ? fixed.getBoundingClientRect().width : 0);
        const right = edgeCell.getBoundingClientRect().right;
        if (right > b.right) box.scrollLeft += right - b.right;
        const left = th.getBoundingClientRect().left;
        if (left < edge) box.scrollLeft += left - edge;
    }
    const sel = $('#grid-jump');
    if (sel && sel.value !== String(i)) {
        sel.value = String(i);
        if (sel._cbx) sel._cbx.sync();
    }
    const live = $('#grid-live');
    if (live) live.textContent = `Column ${i + 1} of ${g.count}: ${g.names[i]}`;
};

ReportsPage.gridStep = function (delta) {
    const g = ReportsPage._grid;
    if (!g.count) return;
    if (g.current < 0) ReportsPage.gridGo(delta < 0 ? g.count - 1 : 0);
    else ReportsPage.gridGo(g.current + delta);
};

// ←/→ one column, Home/End the first and last, Enter the column's own
// report. In the picker's box the arrows are the caret's while its list
// is open; closed, they move the column.
ReportsPage.gridKey = function (e) {
    const g = ReportsPage._grid;
    if (!g.count) return;
    const t = e.target;
    if (t && t.getAttribute && t.getAttribute('aria-expanded') === 'true') return;
    const inText = t && t.tagName === 'INPUT' && t.getAttribute('role') !== 'combobox';
    if (inText) return;
    switch (e.key) {
        case 'ArrowLeft': e.preventDefault(); ReportsPage.gridStep(-1); return;
        case 'ArrowRight': e.preventDefault(); ReportsPage.gridStep(1); return;
        case 'Home': e.preventDefault(); ReportsPage.gridGo(0); return;
        case 'End': e.preventDefault(); ReportsPage.gridGo(g.count - 1); return;
        case 'Enter': {
            if (t && t.getAttribute && t.getAttribute('role') === 'combobox') return;
            if (t && (t.tagName === 'BUTTON' || t.tagName === 'A')) return;
            if (g.current < 0) return;
            const a = $(`#report-content .pivot-grid thead th[data-col="${g.current}"] a`);
            if (a) { e.preventDefault(); a.click(); }
            return;
        }
        default:
    }
};

// Class tracking: Profit & Loss split by the class dimension.
ReportsPage.profitLossByClass = async function (prefill) {
    await ReportsPage.openPeriodModal(T("P&L by Class"), "this_year_to_date", async (period, range) => {
        const qs = `start_date=${range.start}&end_date=${range.end}`;
        const data = await API.get(`/reports/profit-loss-by-class?${qs}`);
        const classes = data.classes;
        if (!classes.length) {
            return `<div class="empty-state"><p>No activity in this period</p></div>`;
        }
        // Accounts down the side and a column per class, as QuickBooks
        // lays it out; an amount opens the transactions behind it, and a
        // class's heading opens its own P&L (#213), on the report's period.
        const args = (...xs) => xs.map(x => JSON.stringify(x)).join(',');
        const dates = { period, start_date: range.start, end_date: range.end };
        return `${ReportsPage._exportButtons('profit-loss-by-class', qs)}
            <div style="font-size:11px; color:var(--gray-500); margin-bottom:8px;">
                ${escapeHtml(data.start_date)} — ${escapeHtml(data.end_date)}. Click an amount for the transactions behind it, or a heading for that column's own report.
            </div>
            ${ReportsPage._pivotGrid({
                title: T('P&L by Class'),
                noun: T('class'),
                kind: 'class',
                columns: classes.map(c => ({ ...c, id: c.class_id, name: c.class_name })),
                accounts: data.accounts,
                totals: { income: data.total_income, cogs: data.total_cogs, gross_profit: data.total_gross_profit, expenses: data.total_expenses, net_income: data.total_net_income },
                drill: (a, c) => `ReportsPage.openDrillDown(${args(a.account_id, a.account_name, range.start, range.end, c.class_id, c.class_name, 'profit-loss-by-class')})`,
                head: (c) => `ReportsPage.profitLossOfClass(${args(c.class_id, c.class_name, dates)})`,
                sum: (c) => `ReportsPage.profitLossOfClass(${args(c.class_id, c.class_name, dates)})`,
            })}`;
    }, "Dates", false, { reportType: 'profit_loss_by_class', view: 'profit-loss-by-class', prefill, wide: true });
};

// One class's own P&L (#213): the P&L by Class column, account by account,
// each opening its transactions for that class. A report in its own right
// since R5 (#235): the period shell, a class picker with ‹ Prev / Next ›
// through the classes, Save and export. Its address is
// #/reports/profit-loss-class?class_id=…&start_date=…&end_date=… (R7):
// opened from it, the class's name comes from the server. `prefill` is the
// query (period, start_date, end_date) the view starts on.
ReportsPage.profitLossOfClass = async function (classId, className, prefill) {
    classId = parseInt(classId, 10);
    if (!classId) { toast(`No ${T('class')} on this column`, 'error'); return; }
    prefill = prefill || {};
    // The picker lists every active class, and this one if it is archived
    // (history keeps it); the type-ahead attaches to it by its name.
    let classes = [];
    try { classes = await API.get('/classes?include_archived=true'); } catch (e) { classes = []; }
    const listed = classes.filter(c => !c.is_archived || c.id === classId);
    if (!listed.some(c => c.id === classId)) listed.unshift({ id: classId, name: className || `${T('Class')} ${classId}` });
    const pickOpts = listed.map(c =>
        `<option value="${c.id}" ${c.id === classId ? 'selected' : ''}>${escapeHtml(c.name)}${c.is_archived ? ' (archived)' : ''}</option>`
    ).join('');
    const noun = T('class');
    const toolbar = `
        <div class="form-group">
            <label for="class-pl-pick">${T('Class')}</label>
            <select id="class-pl-pick" name="class_id" onchange="ReportsPage.setParam('class_id', parseInt(this.value, 10))">${pickOpts}</select>
        </div>
        <div class="form-group grid-step full-width">
            <span class="grid-step__buttons">
                <button type="button" class="btn btn-sm btn-secondary" aria-label="Previous ${escapeHtml(noun)}" onclick="ReportsPage.stepClass(-1)">&lsaquo; Prev ${escapeHtml(noun)}</button>
                <button type="button" class="btn btn-sm btn-secondary" aria-label="Next ${escapeHtml(noun)}" onclick="ReportsPage.stepClass(1)">Next ${escapeHtml(noun)} &rsaquo;</button>
                <span id="class-pl-where" class="grid-live" role="status" aria-live="polite"></span>
            </span>
        </div>`;
    const params = { class_id: classId };
    await ReportsPage.openPeriodModal(`${T('Profit & Loss')} — ${className || T('Class')}`, "this_year_to_date", async (period, range, p) => {
        const id = parseInt(p.class_id, 10) || classId;
        const qs = `start_date=${range.start}&end_date=${range.end}&class_id=${id}`;
        const data = await API.get(`/reports/profit-loss?${qs}`);
        $('#modal-title').textContent = `${T('Profit & Loss')} — ${data.class_name}`;
        const pick = $('#class-pl-pick');
        if (pick && pick.value !== String(id)) { pick.value = String(id); if (pick._cbx) pick._cbx.sync(); }
        const at = listed.findIndex(c => c.id === id);
        const where = $('#class-pl-where');
        if (where) where.textContent = at >= 0 ? `${data.class_name}: ${at + 1} of ${listed.length}` : '';
        const args = (...xs) => xs.map(x => JSON.stringify(x)).join(',');
        const section = items => items.length
            ? items.map(i => {
                const call = escapeHtml(`ReportsPage.openDrillDown(${args(i.account_id, i.account_name, range.start, range.end, id, data.class_name, 'profit-loss-class')})`);
                return `<tr><td style="padding-left:24px;"><a href="javascript:void(0)" style="color:var(--text-link); text-decoration:none;" onclick="${call}">${escapeHtml(i.account_name)}</a></td><td class="amount">${formatCurrency(i.amount)}</td></tr>`;
            }).join('')
            : '<tr><td colspan="2" style="color:var(--gray-400);">None</td></tr>';
        const subtotal = (title, amount) => `<tr style="font-weight:600; background:var(--gray-50);"><td>${title}</td><td class="amount">${formatCurrency(amount)}</td></tr>`;
        return `<div id="class-pl-body">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
                ${ReportsPage._backButton('profit-loss-by-class', { period, start_date: range.start, end_date: range.end })}
                ${ReportsPage._exportButtons('profit-loss', qs)}
            </div>
            <p style="margin-bottom:12px; color:var(--gray-500); font-size:12px;">${T('Class')}: <strong>${escapeHtml(data.class_name)}</strong> &middot; ${formatDate(data.start_date)} &mdash; ${formatDate(data.end_date)} &middot; this ${escapeHtml(noun)} only, not the company total</p>
            <div class="table-container"><table>
                <thead><tr><th scope="col">Account</th><th scope="col" class="amount">Amount</th></tr></thead>
                <tbody>
                    <tr><td><strong>${T('Income')}</strong></td><td></td></tr>
                    ${section(data.income)}
                    ${subtotal(T('Total Income'), data.total_income)}
                    <tr><td><strong>Cost of Goods Sold</strong></td><td></td></tr>
                    ${section(data.cogs)}
                    ${subtotal('Gross Profit', data.gross_profit)}
                    <tr><td><strong>Expenses</strong></td><td></td></tr>
                    ${section(data.expenses)}
                    ${subtotal('Total Expenses', data.total_expenses)}
                    <tr style="font-weight:700; font-size:15px; background:var(--primary-light);"><td>${T('Net Income')}</td><td class="amount">${formatCurrency(data.net_income)}</td></tr>
                </tbody>
            </table></div></div>`;
    }, "Dates", false, { reportType: 'profit_loss_class', view: 'profit-loss-class', params, prefill, toolbar });
};

// P&L Unclassified (#235): the class P&L pointed at the system-default
// class, the end-of-month cleanup list. Its card's address stands in for
// the class view's (replaced, not pushed, so Back is one step).
ReportsPage.profitLossUnclassified = async function (prefill) {
    let classes = [];
    try { classes = await API.get('/classes'); } catch (err) { toast(err.message || `Could not load the ${T('classes')}`, 'error'); return; }
    const uncat = classes.find(c => c.is_system_default);
    if (!uncat) { toast(`There is no default ${T('class')} to report on`, 'error'); return; }
    if (App.parseHash(location.hash || '#/').path === '/reports/profit-loss-unclassified') {
        history.replaceState(history.state, '', ReportsPage.viewUrl('profit-loss-class', { class_id: uncat.id, ...(prefill || {}) }));
    }
    await ReportsPage.profitLossOfClass(uncat.id, uncat.name, prefill);
};

// ‹ Prev / Next › through the class picker's list.
ReportsPage.stepClass = function (delta) {
    const pick = $('#class-pl-pick');
    if (!pick || !pick.options.length) return;
    const i = Math.max(0, Math.min(pick.options.length - 1, pick.selectedIndex + delta));
    if (i === pick.selectedIndex) return;
    pick.selectedIndex = i;
    if (pick._cbx) pick._cbx.sync();
    ReportsPage.setParam('class_id', parseInt(pick.value, 10));
};

// Back to P&L by Class / the General Ledger, on the dates each was opened
// with (#213, #224): now ReportsPage._backButton, through the view's
// address and the browser's history (R7). Kept by name for callers.
ReportsPage._backToByClass = function (startDate, endDate) {
    return ReportsPage._backButton('profit-loss-by-class', { start_date: startDate, end_date: endDate });
};
ReportsPage._backToGeneralLedger = function (startDate, endDate) {
    return ReportsPage._backButton('general-ledger', { start_date: startDate, end_date: endDate });
};

// Fixed assets: register totals per type for GL reconciliation.
ReportsPage.fixedAssetReconciliation = async function () {
    ReportsPage.setAddress('fixed-asset-reconciliation', {});
    const data = await API.get('/fixed-assets/reports/reconciliation');
    const rows = data.types.map(t => `<tr>
        <td>${escapeHtml(t.asset_type)}</td>
        <td class="amount">${t.asset_count}</td>
        <td class="amount">${formatCurrency(t.cost)}</td>
        <td class="amount">${formatCurrency(t.accumulated_depreciation)}</td>
        <td class="amount">${formatCurrency(t.book_value)}</td>
    </tr>`).join('');
    openModal('Fixed Asset Reconciliation', `
        <div class="table-container"><table>
            <thead><tr><th scope="col">Asset Type</th><th scope="col" class="amount">Assets</th><th scope="col" class="amount">Cost</th>
            <th scope="col" class="amount">Accum. Depr.</th><th scope="col" class="amount">Book Value</th></tr></thead>
            <tbody>${rows.length ? rows : '<tr><td colspan="5">No registered assets</td></tr>'}</tbody>
            <tfoot><tr style="font-weight:700; background:var(--gray-50);">
                <td>Total</td><td></td>
                <td class="amount">${formatCurrency(data.total_cost)}</td>
                <td class="amount">${formatCurrency(data.total_accumulated)}</td>
                <td class="amount">${formatCurrency(data.total_book_value)}</td>
            </tr></tfoot>
        </table></div>
        <div style="font-size:11px; color:var(--gray-500); margin-top:8px;">
            Compare against the mapped fixed-asset and accumulated-depreciation
            GL accounts — differences mean unposted acquisitions or manual GL edits.
        </div>`);
};

// Financial statements pack — one PDF with P&L, Balance Sheet, Trial Balance.
ReportsPage.financialStatementsPdf = async function (prefill) {
    await ReportsPage.openPeriodModal("Financial Statements Pack", "this_year_to_date", async (_period, range) => {
        window.open(`/api/reports/financial-statements/pdf?start_date=${range.start}&end_date=${range.end}`, '_blank');
        // Said for both: a browser opens a tab, the desktop app saves the PDF,
        // opens it in a window of its own and says where it saved it (F24).
        return `<div style="font-size:12px;">The statements pack has opened as a PDF —
            ${T('P&L')} and Trial Balance for ${escapeHtml(range.start)} — ${escapeHtml(range.end)},
            ${T('Balance Sheet')} as of ${escapeHtml(range.end)}. Paper size follows
            Settings → Report PDF Paper Size.</div>`;
    }, "Dates", false, { view: 'financial-statements', prefill });
};

ReportsPage.jobProfitability = async function (prefill) {
    await ReportsPage.openPeriodModal(T("Job Profitability"), "this_year_to_date", async (_period, range) => {
        const data = await API.get(`/reports/job-profitability?start_date=${range.start}&end_date=${range.end}`);
        const pct = v => v === null || v === undefined ? '—' : `${v.toFixed(1)}%`;
        const rows = data.jobs.map(j => `<tr ${j.job_id ? `style="cursor:pointer" onclick="closeModal();App.navigate('#/jobs');JobsPage.showDetails(${j.job_id})"` : ''}>
            <td>${escapeHtml(j.customer_name || '')}</td>
            <td>${escapeHtml(j.job_name)}</td>
            <td class="amount">${j.contract_amount !== null && j.contract_amount !== undefined ? formatCurrency(j.contract_amount) : ''}</td>
            <td class="amount">${formatCurrency(j.income)}</td>
            <td class="amount">${formatCurrency(j.total_costs)}</td>
            <td class="amount" style="font-weight:700;">${formatCurrency(j.net_income)}</td>
            <td class="amount">${pct(j.margin_pct)}</td>
        </tr>`).join('');
        return `
            <div style="font-size:11px; color:var(--gray-500); margin-bottom:8px;">
                ${escapeHtml(data.start_date)} — ${escapeHtml(data.end_date)} · ${Terms.text('"No job" holds untagged activity')} <em>and</em> ${Terms.text('the applied-cost credits behind Job Cost Entries (labor, equipment, overhead applied to jobs), so its costs can be negative and the totals still match the P&L')}
            </div>
            <div class="table-container"><table>
                <thead><tr><th scope="col">${T('Customer')}</th><th scope="col">${T('Job')}</th><th scope="col" class="amount">Contract</th><th scope="col" class="amount">${T('Income')}</th>
                <th scope="col" class="amount">Costs</th><th scope="col" class="amount">Net</th><th scope="col" class="amount">Margin</th></tr></thead>
                <tbody>${rows.length ? rows : '<tr><td colspan="7">No activity in this period</td></tr>'}</tbody>
                <tfoot><tr style="font-weight:700; background:var(--gray-50);">
                    <td colspan="3">Total</td>
                    <td class="amount">${formatCurrency(data.total_income)}</td>
                    <td class="amount">${formatCurrency(data.total_costs)}</td>
                    <td class="amount">${formatCurrency(data.total_net_income)}</td>
                    <td></td>
                </tr></tfoot>
            </table></div>`;
    }, "Dates", false, { view: 'job-profitability', prefill });
};

ReportsPage.jobBudgetVsActual = async function (prefill) {
    await ReportsPage.openPeriodModal(T("Job Budget vs Actual"), "this_year_to_date", async (_period, range) => {
        const data = await API.get(`/jobs/budget-vs-actual?start_date=${range.start}&end_date=${range.end}`);
        const pct = v => v === null || v === undefined ? '—' : `${v.toFixed(1)}%`;
        const t = { revised: 0, committed: 0, actual: 0, projected: 0, variance: 0, act_revenue: 0 };
        const rows = data.map(j => {
            for (const k of Object.keys(t)) t[k] += j[k] || 0;
            return `<tr style="cursor:pointer" onclick="closeModal();App.navigate('#/jobs/${j.job_id}')">
            <td>${escapeHtml(j.customer_name || '')}</td>
            <td>${escapeHtml(j.job_name)}</td>
            <td class="amount">${formatCurrency(j.revised)}</td>
            <td class="amount">${formatCurrency(j.committed)}</td>
            <td class="amount">${formatCurrency(j.actual)}</td>
            <td class="amount">${formatCurrency(j.projected)}</td>
            <td class="amount" style="font-weight:700;color:${j.revised && j.variance < 0 ? 'var(--text-danger)' : 'inherit'}">${formatCurrency(j.variance)}</td>
            <td class="amount">${pct(j.pct_used)}</td>
            <td class="amount">${formatCurrency(j.act_revenue)}</td>
        </tr>`; }).join('');
        return `
            <div style="font-size:11px; color:var(--gray-500); margin-bottom:8px;">
                Actuals for ${escapeHtml(range.start)} — ${escapeHtml(range.end)}; budgets and committed cost are job-to-date. Click a job to drill down.
            </div>
            <div class="table-container"><table>
                <thead><tr><th scope="col">${T('Customer')}</th><th scope="col">${T('Job')}</th><th scope="col" class="amount">Budget</th><th scope="col" class="amount">Committed</th>
                <th scope="col" class="amount">Actual</th><th scope="col" class="amount">Projected</th><th scope="col" class="amount">Variance</th><th scope="col" class="amount">% Used</th><th scope="col" class="amount">Revenue</th></tr></thead>
                <tbody>${rows.length ? rows : '<tr><td colspan="9">No jobs</td></tr>'}</tbody>
                <tfoot><tr style="font-weight:700; background:var(--gray-50);">
                    <td colspan="2">Total</td>
                    <td class="amount">${formatCurrency(t.revised)}</td><td class="amount">${formatCurrency(t.committed)}</td>
                    <td class="amount">${formatCurrency(t.actual)}</td><td class="amount">${formatCurrency(t.projected)}</td>
                    <td class="amount">${formatCurrency(t.variance)}</td><td></td><td class="amount">${formatCurrency(t.act_revenue)}</td>
                </tr></tfoot>
            </table></div>`;
    }, "Dates", false, { view: 'job-budget-vs-actual', prefill });
};



// ---------------------------------------------------------------------------
// Nonprofit statements — shown in place of the P&L and Balance Sheet cards
// when Settings -> Company Type is nonprofit. Each reconciles to the plain
// P&L / balance sheet (the server computes both from the same lines).
// ---------------------------------------------------------------------------
ReportsPage._nonprofitCards = function () {
    return `
        <div class="card" style="cursor:pointer" onclick="ReportsPage.statementOfActivities()">
            <div class="card-header">Statement of Activities</div>
            <p style="font-size:13px; color:var(--gray-500);">Revenue, releases and expenses, with and without donor restrictions</p>
        </div>
        <div class="card" style="cursor:pointer" onclick="ReportsPage.statementOfFinancialPosition()">
            <div class="card-header">Statement of Financial Position</div>
            <p style="font-size:13px; color:var(--gray-500);">Assets, liabilities, and net assets by restriction</p>
        </div>
        <div class="card" style="cursor:pointer" onclick="ReportsPage.fundBalances()">
            <div class="card-header">Fund Balances</div>
            <p style="font-size:13px; color:var(--gray-500);">Each restricted fund: beginning, contributions, spent, released, ending</p>
        </div>
        <div class="card" style="cursor:pointer" onclick="ReportsPage.functionalExpenses()">
            <div class="card-header">Statement of Functional Expenses</div>
            <p style="font-size:13px; color:var(--gray-500);">Program / management / fundraising by expense account (Form 990 Part IX)</p>
        </div>
        <div class="card" style="cursor:pointer" onclick="ReportsPage.pledges()">
            <div class="card-header">Pledge Report</div>
            <p style="font-size:13px; color:var(--gray-500);">Promised, received, written off and outstanding by donor and campaign</p>
        </div>
        <div class="card" style="cursor:pointer" onclick="ReportsPage.givingStatements()">
            <div class="card-header">Year-End Giving Statements</div>
            <p style="font-size:13px; color:var(--gray-500);">One statement per donor for the tax year — print the stack or email them all</p>
        </div>`;
};

ReportsPage.givingStatements = function (prefill) {
    const y = new Date().getFullYear();
    const picked = parseInt((prefill || {}).year, 10);
    const chosen = [y, y - 1, y - 2].includes(picked) ? picked : y - 1;
    ReportsPage.setAddress('giving-statements', { year: chosen });
    const opts = [y, y - 1, y - 2].map(v => `<option value="${v}" ${v === chosen ? 'selected' : ''}>${v}</option>`).join('');
    openModal('Year-End Giving Statements', `
        <div class="form-grid">
            <div class="form-group"><label for="gs-year">Tax year</label><select id="gs-year" onchange="ReportsPage.setAddress('giving-statements', { year: this.value })">${opts}</select></div>
        </div>
        <p style="font-size:12px;color:var(--gray-500);margin:8px 0;">Every ${T('customer')} with a gift in the year gets a statement: cash contributions with the deductible portion, non-cash gifts described without a value. ${T('Customers')} who opted out in their record are skipped when emailing.</p>
        <div id="gs-result" style="font-size:12px;margin:8px 0;"></div>
        <div class="form-actions">
            <button class="btn btn-secondary" onclick="window.open('/api/donors/giving-statements/pdf?year=' + $('#gs-year').value, '_blank')">Download all (PDF)</button>
            <button class="btn btn-primary" onclick="ReportsPage.emailGivingStatements()">Email all</button>
            <button class="btn btn-secondary" onclick="closeModal()">Close</button>
        </div>`);
};

ReportsPage.emailGivingStatements = async function () {
    const year = parseInt($('#gs-year').value);
    if (!confirm(`Email ${year} giving statements to every ${T('customer')} with a gift that year?`)) return;
    const box = $('#gs-result');
    box.textContent = 'Sending…';
    try {
        const r = await API.post('/donors/giving-statements/batch-email', { year });
        box.innerHTML = `Sent ${r.sent}, failed ${r.failed}, skipped ${r.skipped}.` + (r.errors.length ? `<ul>${r.errors.map(e => `<li>${escapeHtml(e)}</li>`).join('')}</ul>` : '');
    } catch (err) { box.textContent = err.message; }
};

ReportsPage.pledges = async function (prefill) {
    await ReportsPage.openPeriodModal("Pledge Report", "this_year_to_date", async (_period, range) => {
        const qs = `start_date=${range.start}&end_date=${range.end}`;
        const d = await API.get(`/reports/pledges?${qs}`);
        const cols = ['pledged', 'invoiced', 'not_yet_invoiced', 'received', 'written_off', 'outstanding'];
        const cells = (r) => cols.map(c => `<td class="amount">${formatCurrency(r[c])}</td>`).join('');
        const donors = d.by_donor.map(g => `<tr style="font-weight:600; background:var(--gray-50);"><td>${escapeHtml(g.customer_name)}</td>${cells(g)}</tr>`
            + g.pledges.map(p => `<tr><td style="padding-left:24px;">${escapeHtml(p.label)} <span style="color:var(--gray-500)">· ${escapeHtml(p.class_name)}</span></td>${cells(p)}</tr>`).join('')).join('');
        const classes = d.by_class.map(g => `<tr><td>${escapeHtml(g.class_name)}</td>${cells(g)}</tr>`).join('');
        const head = `<thead><tr><th scope="col"></th><th scope="col" class="amount">Pledged</th><th scope="col" class="amount">Invoiced</th><th scope="col" class="amount">Not yet invoiced</th><th scope="col" class="amount">Received</th><th scope="col" class="amount">Written off</th><th scope="col" class="amount">Outstanding</th></tr></thead>`;
        const foot = `<tfoot><tr style="font-weight:700; background:var(--gray-50);"><td>Total</td>${cells(d.totals)}</tr></tfoot>`;
        return `${ReportsPage._exportButtons('pledges', qs)}
            <p style="margin-bottom:12px; color:var(--gray-500);">${formatDate(d.start_date)} &mdash; ${formatDate(d.end_date)}</p>
            <h4 style="margin:8px 0 4px;font-size:12px;">By ${T('customer')}</h4>
            <div class="table-container"><table>${head}<tbody>${donors || `<tr><td colspan="7" style="color:var(--gray-400);">No pledges in this period</td></tr>`}</tbody>${foot}</table></div>
            <h4 style="margin:12px 0 4px;font-size:12px;">By campaign (${T('class')})</h4>
            <div class="table-container"><table>${head}<tbody>${classes || `<tr><td colspan="7" style="color:var(--gray-400);">—</td></tr>`}</tbody></table></div>`;
    }, "Dates", false, { reportType: 'pledges', view: 'pledges', prefill });
};

ReportsPage._exportButtons = function (path, qs) {
    return `<div style="text-align:right; margin-bottom:6px; margin-left:auto;">
        <button class="btn btn-sm btn-secondary" onclick="window.open('/api/reports/${path}/pdf?${qs}','_blank')">Save PDF</button>
        <button class="btn btn-sm btn-secondary" onclick="window.open('/api/reports/${path}/csv?${qs}','_blank')">Save CSV</button>
    </div>`;
};

// Prior-year comparison for the two statements a treasurer reads side by
// side. The choice is remembered for the session and rides on the export
// links, so the PDF and CSV carry the same columns as the screen.
ReportsPage._compare = { statement_of_activities: false, functional_expenses: false };
ReportsPage.compareToggleHtml = function (key) {
    return `<label style="font-weight:normal; font-size:12px; margin-right:auto;"><input type="checkbox" ${ReportsPage._compare[key] ? 'checked' : ''} onchange="ReportsPage._compare['${key}']=this.checked; $('#report-period-select').dispatchEvent(new Event('change'))"> Compare to prior year</label>`;
};

ReportsPage.statementOfActivities = async function (prefill) {
    await ReportsPage.openPeriodModal("Statement of Activities", "this_year_to_date", async (_period, range) => {
        const cmp = ReportsPage._compare.statement_of_activities;
        const qs = `start_date=${range.start}&end_date=${range.end}${cmp ? '&compare=prior_year' : ''}`;
        const d = await API.get(`/reports/statement-of-activities?${qs}`);
        const t = d.totals;
        const pt = cmp && d.prior ? d.prior.totals : {};
        const cols = cmp ? 6 : 4;
        const line = (label, w, r, tot, prior, style = '') => `<tr style="${style}"><td>${label}</td><td class="amount">${formatCurrency(w)}</td><td class="amount">${formatCurrency(r)}</td><td class="amount">${formatCurrency(tot)}</td>${cmp ? `<td class="amount">${formatCurrency(prior || 0)}</td><td class="amount">${formatCurrency((tot || 0) - (prior || 0))}</td>` : ''}</tr>`;
        const rows = (items) => items.length ? items.map(i => line(`<span style="padding-left:24px">${escapeHtml(i.account_name)}</span>`, i.without, i.with, i.total, i.prior_total)).join('') : `<tr><td colspan="${cols}" style="color:var(--gray-400);">None</td></tr>`;
        const head = (label) => `<tr><td><strong>${label}</strong></td>${'<td></td>'.repeat(cols - 1)}</tr>`;
        return `<div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">${ReportsPage.compareToggleHtml('statement_of_activities')}${ReportsPage._exportButtons('statement-of-activities', qs)}</div>
            <p style="margin-bottom:12px; color:var(--gray-500);">${formatDate(d.start_date)} &mdash; ${formatDate(d.end_date)}${cmp && d.prior ? ` · prior year ${formatDate(d.prior.start_date)} &mdash; ${formatDate(d.prior.end_date)}` : ''}</p>
            <div class="table-container"><table>
                <thead><tr><th scope="col"></th><th scope="col" class="amount">Without Donor Restrictions</th><th scope="col" class="amount">With Donor Restrictions</th><th scope="col" class="amount">Total</th>${cmp ? '<th scope="col" class="amount">Prior year</th><th scope="col" class="amount">Change</th>' : ''}</tr></thead>
                <tbody>
                    ${head('Revenue &amp; Support')}
                    ${rows(d.revenue)}
                    ${line('Total Revenue &amp; Support', t.revenue_without, t.revenue_with, t.revenue, pt.revenue, 'font-weight:600; background:var(--gray-50);')}
                    ${line('Net assets released from restrictions', d.releases.without, d.releases.with, 0, 0)}
                    ${head('Expenses')}
                    ${rows(d.expenses)}
                    ${line('Total Expenses', t.expenses, 0, t.expenses, pt.expenses, 'font-weight:600; background:var(--gray-50);')}
                    ${line('Change in Net Assets', t.change_without, t.change_with, t.change_total, pt.change_total, 'font-weight:700; font-size:15px; background:var(--primary-light);')}
                </tbody>
            </table></div>`;
    }, "Dates", false, { reportType: 'statement_of_activities', view: 'statement-of-activities', prefill });
};

ReportsPage.statementOfFinancialPosition = async function (prefill) {
    await ReportsPage.openPeriodModal("Statement of Financial Position", "this_year_to_date", async (_period, params) => {
        const qs = `as_of_date=${params.as_of_date}`;
        const d = await API.get(`/reports/statement-of-financial-position?${qs}`);
        const drillCall = (i) => escapeHtml(`ReportsPage.openDrillDown(${i.account_id},${JSON.stringify(i.account_name)},null,${JSON.stringify(params.as_of_date)},null,null,'statement-of-financial-position')`);
        const section = (items) => items.map(i => `<tr><td style="padding-left:24px;">
                ${i.account_id ? `<a href="javascript:void(0)" style="color:var(--text-link); text-decoration:none;" onclick="${drillCall(i)}">${escapeHtml(i.account_name)}</a>` : escapeHtml(i.account_name)}
                </td><td class="amount">${formatCurrency(i.amount)}</td></tr>`).join('') || `<tr><td colspan="2" style="color:var(--gray-400);">None</td></tr>`;
        const sub = (label, v) => `<tr style="font-weight:600; background:var(--gray-50);"><td>${label}</td><td class="amount">${formatCurrency(v)}</td></tr>`;
        return `${ReportsPage._exportButtons('statement-of-financial-position', qs)}
            <p style="margin-bottom:12px; color:var(--gray-500);">As of ${formatDate(d.as_of_date)}</p>
            <div class="table-container"><table>
                <thead><tr><th scope="col">Account</th><th scope="col" class="amount">Amount</th></tr></thead>
                <tbody>
                    <tr><td><strong>Assets</strong></td><td></td></tr>${section(d.assets)}${sub('Total Assets', d.total_assets)}
                    <tr><td><strong>Liabilities</strong></td><td></td></tr>${section(d.liabilities)}${sub('Total Liabilities', d.total_liabilities)}
                    <tr><td><strong>Net Assets</strong></td><td></td></tr>${section(d.net_assets)}
                    ${sub('Net Assets Without Donor Restrictions', d.net_assets_without)}
                    ${sub('Net Assets With Donor Restrictions', d.net_assets_with)}
                    ${sub('Total Net Assets', d.total_net_assets)}
                    <tr style="font-weight:700; font-size:15px; background:var(--primary-light);"><td>Liabilities + Net Assets</td><td class="amount">${formatCurrency(d.total_liabilities_and_net_assets)}</td></tr>
                </tbody>
            </table></div>`;
    }, "As of", true, { reportType: 'statement_of_financial_position', view: 'statement-of-financial-position', prefill });
};

ReportsPage.fundBalances = async function (prefill) {
    await ReportsPage.openPeriodModal("Fund Balances", "this_year_to_date", async (_period, range) => {
        const qs = `start_date=${range.start}&end_date=${range.end}`;
        const d = await API.get(`/reports/fund-balances?${qs}`);
        const keys = ['beginning', 'contributions', 'expenses', 'releases', 'ending', 'unreleased'];
        const row = (f, style = '') => `<tr style="${style}"><td>${escapeHtml(f.class_name)}${f.donor_name ? `<div style="font-size:10px;color:var(--gray-500)">${escapeHtml(f.donor_name)}</div>` : ''}</td>${keys.map(k => `<td class="amount">${formatCurrency(f[k])}</td>`).join('')}</tr>`;
        const rows = d.funds.map(f => row(f)).join('') + (d.unassigned ? row(d.unassigned, 'font-style:italic') : '');
        return `${ReportsPage._exportButtons('fund-balances', qs)}
            <p style="margin-bottom:12px; color:var(--gray-500);">${formatDate(d.start_date)} &mdash; ${formatDate(d.end_date)} · restricted ${T('classes')} only</p>
            <div class="table-container"><table>
                <thead><tr><th scope="col">${T('Class')}</th><th scope="col" class="amount">Beginning</th><th scope="col" class="amount">Contributions</th><th scope="col" class="amount">Spent</th><th scope="col" class="amount">Released</th><th scope="col" class="amount">Ending</th><th scope="col" class="amount" title="Spent but not yet released">Unreleased</th></tr></thead>
                <tbody>${rows || `<tr><td colspan="7" style="color:var(--gray-400);">No restricted ${T('classes')} yet</td></tr>`}</tbody>
                <tfoot>${row({ class_name: 'Total', ...d.totals }, 'font-weight:700; background:var(--gray-50);')}</tfoot>
            </table></div>`;
    }, "Dates", false, { reportType: 'fund_balances', view: 'fund-balances', prefill });
};

ReportsPage.functionalExpenses = async function (prefill) {
    await ReportsPage.openPeriodModal("Statement of Functional Expenses", "this_year_to_date", async (_period, range) => {
        const cmp = ReportsPage._compare.functional_expenses;
        const qs = `start_date=${range.start}&end_date=${range.end}${cmp ? '&compare=prior_year' : ''}`;
        const d = await API.get(`/reports/functional-expenses?${qs}`);
        const keys = ['total', 'program', 'management', 'fundraising', 'unassigned'];
        const pt = cmp && d.prior ? d.prior.totals : {};
        const row = (label, r, style = '', prior = null) => { const pv = prior != null ? prior : (r.prior_total || 0); return `<tr style="${style}"><td>${label}</td>${keys.map(k => `<td class="amount">${formatCurrency(r[k])}</td>`).join('')}${cmp ? `<td class="amount">${formatCurrency(pv)}</td><td class="amount">${formatCurrency(r.total - pv)}</td>` : ''}</tr>`; };
        const rows = d.rows.map(r => row(escapeHtml(`${r.account_number || ''} ${r.account_name}`.trim()), r)).join('');
        const programs = d.programs.length ? `<h4 style="margin:12px 0 4px;font-size:12px;">Program services by program</h4>
            <div class="table-container"><table><thead><tr><th scope="col">Program</th><th scope="col" class="amount">Amount</th></tr></thead>
            <tbody>${d.programs.map(p => `<tr><td>${escapeHtml(p.class_name)}</td><td class="amount">${formatCurrency(p.amount)}</td></tr>`).join('')}</tbody></table></div>` : '';
        return `<div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">${ReportsPage.compareToggleHtml('functional_expenses')}${ReportsPage._exportButtons('functional-expenses', qs)}</div>
            <p style="margin-bottom:12px; color:var(--gray-500);">${formatDate(d.start_date)} &mdash; ${formatDate(d.end_date)}${cmp && d.prior ? ` · prior year ${formatDate(d.prior.start_date)} &mdash; ${formatDate(d.prior.end_date)}` : ''}${d.totals.unassigned ? ` · <span style="color:var(--danger)">${formatCurrency(d.totals.unassigned)} still unassigned — run an allocation rule</span>` : ''}</p>
            <div class="table-container"><table>
                <thead><tr><th scope="col">Expense</th><th scope="col" class="amount">Total</th><th scope="col" class="amount">Program</th><th scope="col" class="amount">Management</th><th scope="col" class="amount">Fundraising</th><th scope="col" class="amount">Unassigned</th>${cmp ? '<th scope="col" class="amount">Prior year</th><th scope="col" class="amount">Change</th>' : ''}</tr></thead>
                <tbody>${rows || `<tr><td colspan="${cmp ? 8 : 6}" style="color:var(--gray-400);">No expenses in this period</td></tr>`}</tbody>
                <tfoot>${row('Total', d.totals, 'font-weight:700; background:var(--gray-50);', pt.total || 0)}</tfoot>
            </table></div>${programs}`;
    }, "Dates", false, { reportType: 'functional_expenses', view: 'functional-expenses', prefill });
};
