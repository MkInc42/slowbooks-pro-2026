"""Active / Inactive / All on the list pages, and one-click Make Inactive /
Make Active (#210, asked for by Ryan of Cimarron Site Services).

The Chart of Accounts already kept inactive records out of the way without
losing them (#139). Customers, vendors, items, employees and jobs stored
is_active and left the pickers, but their lists showed every record, and
changing one meant Edit, untick, Save. Each list now has a Show picker
(Active by default) and a button on each row.

Here, the API each list reads: an inactive_only filter beside the
active_only (and, for jobs, include_inactive) the pickers already use, and
PUT {is_active} on every one, employees included. Then the page sources. The
browser checks are in tests/test_active_lists_browser.py.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "app/static/js"


def _ids(client, url):
    r = client.get(url)
    assert r.status_code == 200, r.text
    return {row["id"] for row in r.json()}


def _pair(client, api, make):
    """One record left active and one made inactive, by PUT {is_active}."""
    keep = client.post(api, json=make("Keep")).json()["id"]
    drop = client.post(api, json=make("Drop")).json()["id"]
    r = client.put(f"{api}/{drop}", json={"is_active": False})
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is False
    return keep, drop


def _lists(client):
    customer = client.post("/api/customers", json={"name": "Job Owner"}).json()["id"]
    return {
        "/api/customers": lambda n: {"name": f"{n} Customer"},
        "/api/vendors": lambda n: {"name": f"{n} Vendor"},
        "/api/items": lambda n: {"name": f"{n} Item", "item_type": "service"},
        "/api/employees": lambda n: {"first_name": n, "last_name": "Employee"},
        "/api/jobs": lambda n: {"customer_id": customer, "name": f"{n} Job"},
    }


def test_each_list_shows_active_inactive_or_all(client):
    for api, make in _lists(client).items():
        keep, drop = _pair(client, api, make)
        active = _ids(client, f"{api}?active_only=true")
        inactive = _ids(client, f"{api}?inactive_only=true")
        assert keep in active and drop not in active, api
        assert drop in inactive and keep not in inactive, api
        # All: the plain list (jobs keep their default of active only, and
        # include_inactive for all)
        everything = "?include_inactive=true" if api == "/api/jobs" else ""
        both = _ids(client, f"{api}{everything}")
        assert {keep, drop} <= both, api


def test_the_pickers_default_is_unchanged(client):
    # a job list asked for without a filter is still active jobs only, and
    # the other lists still return everything
    lists = _lists(client)
    keep, drop = _pair(client, "/api/jobs", lists["/api/jobs"])
    plain = _ids(client, "/api/jobs")
    assert keep in plain and drop not in plain
    keep, drop = _pair(client, "/api/vendors", lists["/api/vendors"])
    assert {keep, drop} <= _ids(client, "/api/vendors")


def test_make_active_again_on_every_list(client):
    for api, make in _lists(client).items():
        _, drop = _pair(client, api, make)
        r = client.put(f"{api}/{drop}", json={"is_active": True})
        assert r.status_code == 200, (api, r.text)
        assert r.json()["is_active"] is True, api
        assert drop in _ids(client, f"{api}?active_only=true"), api


def test_the_guard_has_the_open_balance_on_each_row(client, seed_accounts):
    # the list rows carry what's open, so Make Inactive can ask before
    # hiding a customer who owes money or a vendor who is owed
    cid = client.post("/api/customers", json={"name": "Owes Money"}).json()["id"]
    r = client.post(
        "/api/invoices",
        json={
            "customer_id": cid,
            "date": "2026-10-01",
            "lines": [{"description": "Work", "quantity": 1, "rate": "250.00"}],
        },
    )
    assert r.status_code in (200, 201), r.text
    row = next(c for c in client.get("/api/customers").json() if c["id"] == cid)
    assert float(row["balance"]) == 250.0

    expense = next(
        a["id"]
        for a in client.get("/api/accounts").json()
        if a["account_type"] == "expense"
    )
    vid = client.post(
        "/api/vendors",
        json={"name": "Is Owed", "default_expense_account_id": expense},
    ).json()["id"]
    r = client.post(
        "/api/bills",
        json={
            "vendor_id": vid,
            "bill_number": "B-1",
            "date": "2026-10-01",
            "due_date": "2026-10-31",
            "lines": [{"description": "Supplies", "quantity": 1, "rate": "80.00"}],
        },
    )
    assert r.status_code in (200, 201), r.text
    row = next(v for v in client.get("/api/vendors").json() if v["id"] == vid)
    assert float(row["balance"]) == 80.0


# ── the pages ────────────────────────────────────────────────────────────

PAGES = {
    "customers": "customers.js",
    "vendors": "vendors.js",
    "items": "items.js",
    "employees": "employees.js",
    "jobs": "jobs.js",
}


def test_each_list_page_has_the_picker_and_the_buttons():
    for kind, name in PAGES.items():
        js = (JS / name).read_text(encoding="utf-8")
        assert f"ActiveLists.pickerHtml('{kind}')" in js, name
        assert f"ActiveLists.buttonHtml('{kind}'," in js, name
        assert f"ActiveLists.remember('{kind}'," in js, name
        if kind != "jobs":  # the Jobs page has every job and filters them
            assert f"ActiveLists.query('{kind}')" in js, name
    jobs = (JS / "jobs.js").read_text(encoding="utf-8")
    assert "ActiveLists.shows('jobs', j)" in jobs
    assert "__inactive__" not in jobs  # Show has Inactive now, not Status
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    assert '<script src="/static/js/active_lists.js"></script>' in index


def test_the_buttons_follow_the_roles():
    js = (JS / "active_lists.js").read_text(encoding="utf-8")
    # a read-only sign-in gets no button (data-write), and employees are the
    # administrator's (the server's /api/employees writes are admin-only)
    assert "data-write${k.admin ? ' data-admin' : ''}" in js
    employees = js[js.index("employees: {") :]
    assert "admin: true" in employees[: employees.index("},")]
    # the Show picker stays a plain list, not a type-ahead box (#207)
    assert '<select id="list-show" data-no-search' in js


def _run(script):
    out = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=30
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_show_choice_is_remembered_per_list():
    helper = (JS / "active_lists.js").read_text(encoding="utf-8")
    script = (
        "const store = {};\n"
        "const localStorage = { getItem: k => (k in store ? store[k] : null),"
        " setItem: (k, v) => { store[k] = String(v); } };\n"
        "const T = s => s; const App = { navigate() {} };\n"
        + helper
        + "\nconst out = {};\n"
        "out.default = [ActiveLists.show('vendors'), ActiveLists.query('vendors')];\n"
        "ActiveLists.choose('vendors', 'inactive');\n"
        "out.inactive = [ActiveLists.show('vendors'), ActiveLists.query('vendors'),"
        " ActiveLists.show('items')];\n"
        "ActiveLists.choose('vendors', 'all');\n"
        "out.all = [ActiveLists.query('vendors'),"
        " ActiveLists.shows('vendors', {is_active: false})];\n"
        "ActiveLists.choose('vendors', 'nonsense');\n"
        "out.kept = ActiveLists.show('vendors');\n"
        "out.shows = [ActiveLists.shows('items', {is_active: true}),"
        " ActiveLists.shows('items', {is_active: false})];\n"
        "process.stdout.write(JSON.stringify(out));"
    )
    out = _run(script)
    assert out["default"] == ["active", "?active_only=true"]
    assert out["inactive"] == ["inactive", "?inactive_only=true", "active"]
    assert out["all"] == ["", True]
    assert out["kept"] == "all"  # an unknown choice changes nothing
    assert out["shows"] == [True, False]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_storage_that_throws_falls_back_to_active():
    helper = (JS / "active_lists.js").read_text(encoding="utf-8")
    script = (
        "const localStorage = { getItem() { throw new Error('blocked'); },"
        " setItem() { throw new Error('blocked'); } };\n"
        "const T = s => s; const App = { navigate() {} };\n"
        + helper
        + "\nActiveLists.choose('customers', 'all');\n"
        "process.stdout.write(JSON.stringify(ActiveLists.show('customers')));"
    )
    assert _run(script) == "active"
