"""The Chart of Accounts opens an account's register, a filter box narrows
the chart, and the global search finds accounts (#240, R10).

- /api/search finds an account by number or name, inactive ones too (their
  history still opens), saying its bank_kind so the SPA knows which
  register to open.
- The chart page: an account's name is a link — #/banking/:id for a bank or
  card account, the drill-down address for this year for the rest; the
  filter box is named and keeps the type grouping; the search dropdown's
  Accounts section opens the same register.

The click and the typing are in tests/test_browser_class_filters.py.
"""

from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "app" / "static" / "js"


def _get(client, path, **params):
    r = client.get(path, params=params)
    assert r.status_code == 200, (path, r.status_code, r.text)
    return r.json()


def test_search_finds_accounts_by_number_and_name_inactive_too(client, seed_accounts):
    found = _get(client, "/api/search", q="6000")
    hits = found.get("accounts", [])
    assert [a["account_number"] for a in hits] == ["6000"]
    assert hits[0]["id"] == seed_accounts["6000"].id
    assert hits[0]["bank_kind"] is None and hits[0]["is_active"] is True
    by_name = _get(client, "/api/search", q="checking")
    names = {a["name"]: a for a in by_name["accounts"]}
    assert "Checking" in names and names["Checking"]["bank_kind"] == "bank"
    # an inactive account is found, and says so
    r = client.put(
        f"/api/accounts/{seed_accounts['6000'].id}", json={"is_active": False}
    )
    assert r.status_code == 200, r.text
    again = _get(client, "/api/search", q="6000")["accounts"]
    assert again[0]["is_active"] is False
    assert "accounts" not in _get(client, "/api/search", q="zzzzzz")


def test_the_chart_links_each_account_to_its_register():
    js = (JS / "app.js").read_text(encoding="utf-8")
    chart = js[js.index("    async renderAccounts() {") :]
    chart = chart[: chart.index("\n    },")]
    assert '<a href="${escapeHtml(App.accountRegisterHref(a))}"' in chart
    assert 'id="accounts-filter" aria-label="Filter accounts"' in chart
    assert 'data-account-group="${type}"' in chart
    assert 'data-account-row="${haystack}" data-account-type="${type}"' in chart
    href = js[js.index("    accountRegisterHref(account) {") :]
    href = href[: href.index("\n    },")]
    assert "if (account.bank_kind) return `#/banking/${Number(account.id)}`;" in href
    assert "ReportsPage.viewUrl('account-transactions'" in href
    assert "period: 'this_year'" in href
    # the filter keeps the headings of the rows left and hides the rest
    flt = js[js.index("    filterAccounts(text) {") :]
    flt = flt[: flt.index("\n    },")]
    assert "tr.hidden = !shown;" in flt
    assert "tr.hidden = !(groups[tr.dataset.accountGroup] || 0);" in flt
    # the search dropdown's Accounts section opens the register by id
    assert "key: 'accounts'" in js
    assert (
        "App.openAccountRegister(${Number(item.id)}, ${item.bank_kind ? 1 : 0})" in js
    )
