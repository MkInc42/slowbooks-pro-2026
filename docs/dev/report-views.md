# Report views and their addresses

Every report view has an address: `#/reports/<view>?<params>` — `#/reports/profit-loss-by-class?start_date=2026-07-01&end_date=2026-09-30`,
`#/reports/account-transactions?account_id=5120&class_id=3&start_date=…&end_date=…&from=general-ledger`.
The route `/reports/:view` (`app/static/js/app.js`) renders the Report Center and opens the view over it with
`ReportsPage.openView(view, query)`; `App.parseHash(hash)` splits the path from the query and the router hands the
query to the route's render as its second argument (a plain object of strings — `class_id` is `"3"`, parse it).

## The three rules

1. **A reload reproduces the view.** Everything the view needs is in the address; nothing is kept in memory.
   Names (an account's, a class's) are taken from the server's answer when the address has only an id.
2. **A change inside the view replaces the address** (`history.replaceState`): a new period, a filter, a year.
   Back never walks through every period a user tried.
3. **A hop pushes** (`history.pushState`): Report Center → report, report → drill-down, drill-down → class P&L,
   and a source link to a document. Browser Back returns to the view left; the view's own "Back to …" button
   goes back through history when that is where it came from, otherwise it opens the address.

`ReportsPage.setAddress(view, params)` applies rules 2 and 3 by itself: same view → replace, other view → push.
Close/Escape leaves the address alone, as a document over its list does; the view is one reload or Back away.

## Registering a new view (two lines)

1. Add it to `ReportsPage._VIEWS` in `app/static/js/reports.js`:
   `'profit-loss-by-job': { label: 'P&L by Job', open: (p) => ReportsPage.profitLossByJob(p) }`
   — `open(params)` is what the address runs; `label` is the "Back to …" wording (a function returning `T(term)` where nonprofit mode renames it);
   `asOf: true` for a view dated by one `as_of_date`; `keep: ['class_id']` for drill-down params that ride back.
2. Put the address on the bar from the opener. A report that uses `openPeriodModal` passes
   `{ view: 'profit-loss-by-job', params: { job_id }, prefill }` in its opts — the period and dates are written on
   every render, `params` ahead of them, and `prefill` (the query) sets the starting period and dates. A plain-modal
   view calls `ReportsPage.setAddress('name', { … })` itself before `openModal`.

Opening a drill-down *from* the view: `ReportsPage.openDrillDown(accountId, name, start, end, classId, className, from)`
with `from` = your view name gives it "Back to <your label>" and `&from=<name>`; a page route (`#/classes/:id?…`) reads its query the same way.

Saved reports: `report_type` is the view name with underscores (`profit_loss_by_class`) and `parameters` the query;
`openSaved` navigates to `ReportsPage.viewUrl(view, parameters)` — the builder of any link to a report (empty values
and `period=custom` are left out), as the dashboard cards use it (`DashboardPage._reportLink`). From any other page,
open a view with `App.navigate(ReportsPage.viewUrl(…))`, so the Report Center is the page under it after a reload.
Tests: `tests/test_report_views.py` (router, registry) and `tests/test_browser_report_views.py` (the rules in Chromium).
