"""The wide grid, in playwright's Chromium on the bakery's books of
tests/test_theme_contrast.py with eleven classes and a job added (R1 #231,
R2 #232, R3 #233, R5 #235, R13 #242, v2.22.0):

- P&L by Class opens in the wide dialog and its grid scrolls sideways
  inside its container while the Account column and the header row stay
  put, so the Total column is reachable with twelve classes;
- "Go to class" (the type-ahead picker), ‹ Prev / Next ›, and the status
  line that says "Column 4 of 12: Site Prep"; with the grid focused ←/→,
  Home/End move the column and Enter opens that class's own P&L;
- the class's own P&L is a report: period shell, a class picker with
  Prev/Next, Save and export; Back from its drill-down returns to it, not
  to the grid; the P&L Unclassified card; a subtotal cell opens it;
- Save PDF / Save CSV and Add to Saved Reports on the grid, a saved
  by-class report reopening with its columns;
- the column chooser: a subset says "filtered" and shows the filtered
  total, Active hides an archived class, "show empty" adds a zero column;
- P&L by Job: the same grid by job, "No job" first, a heading opening the
  job page on the report's dates with a way back;
- on a phone the wide dialog is the screen's width and the grid swipes
  with the Account column frozen.

Skipped, as one module, where playwright or its Chromium is not installed.
"""

import pytest

pytest.importorskip("playwright.sync_api")

from tests.test_theme_contrast import (  # noqa: E402,F401  (the fixtures)
    ORIGIN,
    SERVED,
    _served_by,
    _visit,
    books_fixture,
    browser_fixture,
    company_fixture,
    settle,
)

SEPT = ("2026-09-01", "2026-09-30")
BY_CLASS_URL = f"#/reports/profit-loss-by-class?start_date={SEPT[0]}&end_date={SEPT[1]}"
BY_JOB_URL = f"#/reports/profit-loss-by-job?start_date={SEPT[0]}&end_date={SEPT[1]}"

# eleven divisions; with Uncategorized (the books' untagged September
# activity) the grid has twelve columns, Site Prep the last
DIVISIONS = [
    "Concrete",
    "Drywall",
    "Electrical",
    "Flooring",
    "Framing",
    "HVAC",
    "Landscaping",
    "Painting",
    "Plumbing",
    "Roofing",
    "Site Prep",
]

MODAL_SHOWN = (
    "() => !document.getElementById('modal-overlay').classList.contains('hidden')"
)
TITLE = "() => document.getElementById('modal-title').textContent"
LIVE = "() => document.getElementById('grid-live').textContent"
CURRENT_HEAD = "() => (document.querySelector('#report-content thead th.is-current') || {}).textContent"
SCROLL = """() => { const b = document.getElementById('grid-scroll');
    const first = b.querySelector('thead th:first-child').getBoundingClientRect();
    const total = b.querySelector('thead th:last-child').getBoundingClientRect();
    const box = b.getBoundingClientRect();
    return { scrollLeft: b.scrollLeft, wider: b.scrollWidth > b.clientWidth,
             firstLeft: first.left - box.left, totalVisible: total.right <= box.right + 1 && total.left >= box.left,
             sticky: getComputedStyle(b.querySelector('tbody td:first-child, tbody th:first-child')).position,
             headSticky: getComputedStyle(b.querySelector('thead th:last-child')).position }; }"""


def _ok(resp):
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


@pytest.fixture(name="divisions")
def divisions_fixture(company, books):
    """Eleven classes, each with September income and an expense, and one
    September posting to the job: the twelve-column grid."""
    accounts = {a["account_number"]: a["id"] for a in _ok(company.get("/api/accounts"))}
    ids = {}
    for n, name in enumerate(DIVISIONS, start=1):
        cls = _ok(company.post("/api/classes", json={"name": name}))
        ids[name] = cls["id"]
        _ok(
            company.post(
                "/api/journal",
                json={
                    "date": f"2026-09-{n + 2:02d}",
                    "description": f"{name} work",
                    "class_id": cls["id"],
                    "lines": [
                        {
                            "account_id": accounts["1000"],
                            "debit": str(100 * n),
                            "credit": "0",
                        },
                        {
                            "account_id": accounts["4000"],
                            "debit": "0",
                            "credit": str(100 * n),
                        },
                        {
                            "account_id": accounts["6000"],
                            "debit": str(10 * n),
                            "credit": "0",
                        },
                        {
                            "account_id": accounts["1000"],
                            "debit": "0",
                            "credit": str(10 * n),
                        },
                    ],
                },
            )
        )
    _ok(
        company.post(
            "/api/journal",
            json={
                "date": "2026-09-20",
                "description": "gala staffing",
                "job_id": books["job"],
                "lines": [
                    {"account_id": accounts["1000"], "debit": "900", "credit": "0"},
                    {"account_id": accounts["4000"], "debit": "0", "credit": "900"},
                ],
            },
        )
    )
    uncategorized = next(
        c for c in _ok(company.get("/api/classes")) if c["is_system_default"]
    )
    ids["Uncategorized"] = uncategorized["id"]
    return ids


def _open_at(browser, client, page_hash, width=1280, height=800):
    """A fresh document at the address: what a bookmark, a pasted link or a
    reload does."""
    handled = []
    page = browser.new_page(viewport={"width": width, "height": height})
    page.route("**/*", _served_by(client, handled, SERVED))
    page.goto(f"{ORIGIN}/{page_hash}")
    page.wait_for_function("window.App && document.readyState === 'complete'")
    page.evaluate(
        "() => { const s = document.getElementById('splash'); if (s) s.classList.add('hidden'); }"
    )
    settle(page, handled)
    return page, handled


def _hash(page):
    return page.evaluate("location.hash")


def _history(page):
    return page.evaluate("history.length")


def _query(h):
    return dict(p.split("=", 1) for p in h.split("?", 1)[1].split("&"))


def _heads(page):
    return page.eval_on_selector_all(
        "#report-content thead th", "els => els.map(e => e.textContent.trim())"
    )


# ── R1: the wide grid ────────────────────────────────────────────────────


def test_the_grid_is_wide_and_scrolls_with_the_account_column_frozen(
    browser, company, divisions
):
    page, handled = _open_at(browser, company, BY_CLASS_URL)
    try:
        page.wait_for_selector("#report-content .pivot-grid")
        assert page.evaluate(
            "() => document.getElementById('modal').classList.contains('modal--wide')"
        )
        heads = _heads(page)
        assert heads[0] == "Account" and heads[-1] == "Total"
        assert heads[1:-1] == ["Uncategorized"] + DIVISIONS, heads
        before = page.evaluate(SCROLL)
        assert before["wider"], "twelve columns are wider than the dialog"
        assert before["sticky"] == "sticky" and before["headSticky"] == "sticky"
        assert not before["totalVisible"], "the Total column starts out of view"

        # End: the last column, and with it the Total column, into view;
        # the Account column has not moved
        page.focus("#grid-scroll")
        page.keyboard.press("End")
        after = page.evaluate(SCROLL)
        assert after["scrollLeft"] > 0
        assert after["totalVisible"]
        assert abs(after["firstLeft"]) < 1.5, "the Account column stays put"
        assert page.evaluate(LIVE) == "Column 12 of 12: Site Prep"
        assert page.evaluate(CURRENT_HEAD).strip() == "Site Prep"
        # every cell of the column is marked, the section rows included
        assert (
            page.locator(
                '#report-content .pivot-grid [data-col="11"].is-current'
            ).count()
            == page.locator('#report-content .pivot-grid [data-col="11"]').count()
        )
        # the frozen first column is a row header
        assert (
            page.locator(
                "#report-content tbody th[scope='row']:has-text('4000 - Service Income')"
            ).count()
            == 1
        )
    finally:
        page.close()


def test_go_to_class_picks_a_column_and_prev_next_step_through_them(
    browser, company, divisions
):
    page, handled = _open_at(browser, company, BY_CLASS_URL)
    try:
        page.wait_for_selector("#report-content .pivot-grid")
        picker = page.get_by_role("combobox", name="Go to class")
        assert picker.count() == 1, "the type-ahead attached to the picker, named"
        picker.click()
        page.keyboard.type("Site")
        page.wait_for_selector("#cbx-listbox [role='option']")
        page.keyboard.press("Enter")
        page.wait_for_function(f"({LIVE})() === 'Column 12 of 12: Site Prep'")
        assert page.evaluate(CURRENT_HEAD).strip() == "Site Prep"
        s = page.evaluate(SCROLL)
        assert s["scrollLeft"] > 0 and s["totalVisible"], "scrolled into view"

        nxt = page.get_by_role("button", name="Next class")
        prev = page.get_by_role("button", name="Previous class")
        assert nxt.count() == 1 and prev.count() == 1
        prev.click()
        assert page.evaluate(LIVE) == "Column 11 of 12: Roofing"
        prev.click()
        assert page.evaluate(LIVE) == "Column 10 of 12: Plumbing"
        nxt.click()
        assert page.evaluate(LIVE) == "Column 11 of 12: Roofing"
        assert picker.input_value() == "Roofing", "the picker follows"

        # a new period redraws the grid and keeps the columns' addressless
        # jump state out of the address
        assert "jump" not in _hash(page) and "col" not in _hash(page)
    finally:
        page.close()


def test_the_keyboard_moves_the_column_and_enter_opens_the_class(
    browser, company, divisions
):
    page, handled = _open_at(browser, company, BY_CLASS_URL)
    try:
        page.wait_for_selector("#report-content .pivot-grid")
        grid = page.locator("#grid-scroll")
        assert grid.get_attribute("role") == "region"
        assert grid.get_attribute("aria-label") == "P&L by Class"
        assert grid.get_attribute("tabindex") == "0"
        page.focus("#grid-scroll")
        page.keyboard.press("ArrowRight")
        assert page.evaluate(LIVE) == "Column 1 of 12: Uncategorized"
        page.keyboard.press("ArrowLeft")
        assert (
            page.evaluate(LIVE) == "Column 1 of 12: Uncategorized"
        ), "stops at the first"
        for _ in range(3):
            page.keyboard.press("ArrowRight")
        assert page.evaluate(LIVE) == "Column 4 of 12: Electrical"
        page.keyboard.press("Home")
        assert page.evaluate(LIVE) == "Column 1 of 12: Uncategorized"
        page.keyboard.press("End")
        page.keyboard.press("ArrowRight")
        assert page.evaluate(LIVE) == "Column 12 of 12: Site Prep", "stops at the last"
        page.keyboard.press("ArrowLeft")
        assert page.evaluate(LIVE) == "Column 11 of 12: Roofing"

        length = _history(page)
        page.keyboard.press("Enter")
        page.wait_for_selector("#class-pl-body table")
        page.wait_for_function(f"({TITLE})() === 'Profit & Loss — Roofing'")
        h = _hash(page)
        assert h.startswith("#/reports/profit-loss-class?class_id=")
        assert _query(h)["class_id"] == str(divisions["Roofing"])
        assert (_query(h)["start_date"], _query(h)["end_date"]) == SEPT
        assert _history(page) == length + 1, "a hop pushes"

        # the class view: a class picker with Prev / Next, and where it is
        pick = page.get_by_role("combobox", name="Class")
        assert pick.count() == 1 and pick.input_value() == "Roofing"
        where = page.evaluate(
            "() => document.getElementById('class-pl-where').textContent"
        )
        assert where == "Roofing: 11 of 12"
        page.get_by_role("button", name="Next class").click()
        page.wait_for_function(f"({TITLE})() === 'Profit & Loss — Site Prep'")
        assert _query(_hash(page))["class_id"] == str(divisions["Site Prep"])
        assert _history(page) == length + 1, "a step within the view replaces"
        assert (
            page.evaluate("() => document.getElementById('class-pl-where').textContent")
            == "Site Prep: 12 of 12"
        )
        page.get_by_role("button", name="Previous class").click()
        page.wait_for_function(f"({TITLE})() === 'Profit & Loss — Roofing'")
        # the picker itself
        pick.click()
        page.keyboard.type("Conc")
        page.wait_for_selector("#cbx-listbox [role='option']")
        page.keyboard.press("Enter")
        page.wait_for_function(f"({TITLE})() === 'Profit & Loss — Concrete'")
        assert _query(_hash(page))["class_id"] == str(divisions["Concrete"])
        body = page.inner_text("#class-pl-body")
        assert "$100.00" in body and "this class only" in body

        # back to the grid through history, as it was left
        page.get_by_role("button", name="Back to P&L by Class").click()
        page.wait_for_selector("#report-content .pivot-grid")
        assert _hash(page) == BY_CLASS_URL
        assert _history(page) == length + 1
    finally:
        page.close()


def test_on_a_phone_the_dialog_is_the_screen_and_the_grid_swipes(
    browser, company, divisions
):
    page, handled = _open_at(browser, company, BY_CLASS_URL, width=390, height=800)
    try:
        page.wait_for_selector("#report-content .pivot-grid")
        width = page.evaluate(
            "() => document.getElementById('modal').getBoundingClientRect().width"
        )
        assert abs(width - 390 * 0.96) < 2, width
        s = page.evaluate(SCROLL)
        assert s["wider"] and s["sticky"] == "sticky"
        page.get_by_role("button", name="Next class").click()
        page.get_by_role("button", name="Next class").click()
        assert page.evaluate(LIVE) == "Column 2 of 12: Concrete"
        assert abs(page.evaluate(SCROLL)["firstLeft"]) < 1.5
        # the dialog and the grid's container stay inside the screen; the
        # table's overflow is the container's to scroll
        assert page.evaluate(
            "() => document.getElementById('modal').getBoundingClientRect().right <= 390"
        )
        assert page.evaluate(
            "() => document.getElementById('grid-scroll').getBoundingClientRect().right <= 390"
        )
    finally:
        page.close()


# ── R2: export and save ──────────────────────────────────────────────────


def test_the_grid_saves_as_pdf_and_csv_and_as_a_saved_report(
    browser, company, divisions
):
    page, handled = _open_at(browser, company, BY_CLASS_URL)
    try:
        page.wait_for_selector("#report-content .pivot-grid")
        opens = []
        page.expose_function("_opened", lambda url: opens.append(url))
        page.evaluate(
            "() => { window.open = (u) => { window._opened(u); return null; }; }"
        )
        page.get_by_role("button", name="Save PDF").click()
        page.get_by_role("button", name="Save CSV").click()
        assert opens == [
            f"/api/reports/profit-loss-by-class/pdf?start_date={SEPT[0]}&end_date={SEPT[1]}",
            f"/api/reports/profit-loss-by-class/csv?start_date={SEPT[0]}&end_date={SEPT[1]}",
        ]
        # the PDF and CSV the buttons open really come back
        pdf = company.get(opens[0])
        assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
        csv = company.get(opens[1])
        assert csv.status_code == 200 and "Site Prep" in csv.text

        page.evaluate("() => { window.prompt = () => 'Divisions, September'; }")
        page.get_by_role("button", name="Add to Saved Reports…").click()
        page.wait_for_selector("#saved-reports-list")
        saved = company.get("/api/saved-reports").json()
        mine = next(s for s in saved if s["name"] == "Divisions, September")
        assert mine["report_type"] == "profit_loss_by_class"
        assert mine["parameters"] == {
            "period": "custom",
            "start_date": SEPT[0],
            "end_date": SEPT[1],
        }
        # and it reopens on its dates, as the grid (the report stays open
        # over the refreshed Report Center; close it first)
        page.keyboard.press("Escape")
        page.wait_for_function(f"!({MODAL_SHOWN})()")
        page.get_by_role("button", name="Open").first.click()
        page.wait_for_selector("#report-content .pivot-grid")
        assert _hash(page) == BY_CLASS_URL
        assert page.evaluate(TITLE) == "P&L by Class"
        assert len(_heads(page)) == 14
    finally:
        page.close()
