# Report views and their addresses

Every report view has an address: `#/reports/<view>?<params>` — `#/reports/profit-loss-by-class?start_date=2026-07-01&end_date=2026-09-30`,
`#/reports/account-transactions?account_id=5120&class_id=3&start_date=…&end_date=…&from=general-ledger`.
The route `/reports/:view` (`app/static/js/app.js`) renders the Report Center and opens the view over it with
`ReportsPage.openView(view, query)`; `App.parseHash(hash)` splits the path from the query and the router hands the
query to the route's render as its second argument (a plain object of strings — `class_id` is `"3"`, parse it).

## The three rules

1. **A reload reproduces the view.** Everything the view needs is in the address; nothing is kept in memory. Names (an account's, a class's) are taken from the server's answer when the address has only an id.
2. **A change inside the view replaces the address** (`history.replaceState`): a new period, a filter, a year. Back never walks through every period a user tried.
3. **A hop pushes** (`history.pushState`): Report Center → report, report → drill-down, drill-down → class P&L, and a source link
   to a document. Browser Back returns to the view left — only that: `App.navigate` closes any open dialog before it renders. The
   view's "Back to …" button goes back through history when the current entry's `history.state.from` (written by every push) is
   that view, else it opens the address; a three-deep chain goes back twice through history, each view as it was left. **Closing a view** (Close, ×, Escape) replaces its entry with the page under it (`App._dialogUnder`: `#/reports`, `#/budgets`, a document's list) through `closeModal` → `App.dialogClosed` (NEW-23), so a refresh, a reload or Back never reopens it; the app's own moves (navigate, popstate, `backTo`) pass `closeModal({ keepAddress: true })`.

`ReportsPage.setAddress(view, params)` applies rules 2 and 3 by itself: same view → replace (keeping the entry's state), other view → push (recording `from`;
a note in memory would go stale on Back, Forward, Close or a reload). Look a view up with `ReportsPage._view(name)`, never `_VIEWS[name]` (`constructor` is not a report). A date or period in the address that is not one (a real calendar day, not just the shape), or From after To, is ignored (`datesFromQuery`, the one reader) and a toast says so; From after To *typed* into any From / To boxes is refused by `reversedRangeRefused` (the one wording: said, the boxes put back, the address untouched — W-3, W-4). **The toolbar's Back** (`App.canGoBack`, v2.22.0) reads the same `from`: an entry with one has an app page behind it (`history.length` is never asked); every push writes it (`App.entryState`: `from`, and `n`, the entry's place in the chain, which a declined leave reads to find its way back, `App.stayPut`), `App.navigate` stamps a plain `<a href>`'s entry when first seen, and the session's first entry gets none — so a `replaceState` of your own must carry the state along (`history.replaceState(history.state, '', url)`, as `setAddress` does; `null` makes Back go dark on that entry), followed by `App.addressShown()`.

## Registering a new view

1. Add it to `ReportsPage._VIEWS` in `app/static/js/reports.js`:
   `'profit-loss-by-job': { label: 'P&L by Job', open: (p) => ReportsPage.profitLossByJob(p) }`
   — `open(params)` is what the address runs; `label` is the "Back to …" wording (a function returning `T(term)` where nonprofit mode renames it);
   `asOf: true` for a view dated by one `as_of_date`; `keep: ['class_id']` for drill-down params that ride back.
2. Put the address on the bar from the opener. A report that uses `openPeriodModal` passes `{ view: 'profit-loss-by-job', params: { job_id }, prefill }` in its opts:
   the period and dates are written on every render, `params` ahead of them, `prefill` (the query) sets the starting period and dates. `params` is the one object the
   address, the saved report and `ReportsPage.setParam(key, value)` share: a control in `opts.toolbar` (html beside the period select) sets it and the view redraws on
   the new address (a function as `params` is read on every render instead); `opts.actions` is html ahead of Save and Close (a "Back to …"); `opts.wide` is the wide dialog.
   A plain-modal view calls `ReportsPage.setAddress` itself before `openModal`.
3. A drill-down *from* the view: `ReportsPage.openDrillDown(accountId, name, start, end, classId, className, from, { job_id })` with `from` = your view name gives it
   "Back to <your label>" and `&from=<name>`; `ReportsPage.profitLossOfClass(classId, name, prefill, from)` likewise opens a class's P&L with the way back to your view.
   A page route (`#/jobs/:id?start_date=…&from=…`, `#/classes/:id?…`, `#/banking/:id?…`) reads its query the same way, replaces its address on a change inside it
   (`history.replaceState(history.state, '', url)`) and hops through `App.navigate(href)` from an anchor's onclick (a plain `<a href>` records no `from`);
   `ReportsPage._backButton(from, dates)` is its way back; `from=classes` + `class_id` → "Back to <class name>" via `ReportsPage.backToPage`. A customer's or vendor's page is a dialog over its list with an address (`#/customers/12`); `showDetails` puts it on the bar (`App.documentAddress`), so a report opened from its Reports row comes Back to it.

Saved reports: `report_type` is the view name with underscores (`profit_loss_by_class`) and `parameters` the query; `openSaved` navigates to `ReportsPage.viewUrl(view, parameters)`
— the builder of any link to a report (empty values and `period=custom` left out), as the dashboard cards use it (`DashboardPage._reportLink`). From any other page, open a view with
`App.navigate(ReportsPage.viewUrl(…))`, so the Report Center is the page under it after a reload. Tests: `tests/test_report_views.py` (router, registry), `tests/test_browser_report_views.py` (the rules in Chromium), `tests/test_browser_grid.py`, `tests/test_browser_report_links.py`.
