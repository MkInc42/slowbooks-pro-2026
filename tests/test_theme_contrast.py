"""Text on every page meets WCAG AA contrast, in both themes.

The macOS gate measures this off a live window (SlowBooks-Pro-Testing,
mac/macgate/check_css_regressions.py). It sweeps every visible element with
its own short text, works out the ground the text actually sits on, and
scores the pair. Its one standing FAIL at 2.18.0 was that list: 17 rules
below AA. Most were muted text: on the light theme's toolbar and status bar
gradients (2.57:1), on white (4.14), and the dark theme's grey on its panel
(4.32). The rest were the sidebar's section headings, the moon button, the
primary button, the dark skip link and the void badge.

This is the same sweep in playwright's Chromium, so the list is kept at zero
here rather than found again on a gate box:

- the gate's JavaScript: a translucent layer is composited, a gradient is
  scored at its worst stop, a bitmap is left out; and one thing the gate's
  scorer missed. It kept a text colour's r, g and b and dropped its alpha,
  so rgba(255,255,255,0.35) scored as white (skytech R3-1). Here the text
  is painted as the browser paints it: its colour's alpha, and every
  element's opacity, over each ground. A disabled control has no
  requirement (WCAG 1.4.3) and is left out;
- its thresholds: 4.5:1, or 3:1 for text of 24px, or 18.66px bold;
- its pages in its order, in dark and then light, and then the splash with
  the licence terms and What's new showing, in light and then dark.

The gate visits #/dashboard and #/pledges, which are not routes (the
dashboard is #/), so those two measure only the shell around "Page not
found"; and it reads only text of up to 60 characters, which leaves out
every hint paragraph. So every page is swept a second time, whole: the
dashboard with all its cards, a job's own page, the bank register, the
global search's results, the update notice, the notices (toasts) a save
shows. The dialogs are swept in tests/test_dialog_contrast.py.

A colour key, the "■" beside each band of the dashboard's A/R aging bar,
is a graphic rather than text: it is held to 3:1 (WCAG 1.4.11), and the
words beside it carry the band's name and amount (macbase1 NEW-11).

The page is the real index.html, scripts and stylesheets, served by the app
itself through the test client, on a bakery's books entered through the API
(seed_books): every list has rows, every document a status. Skipped, as one
module, where playwright or its Chromium is not installed.
"""

import re
from datetime import date, timedelta
from urllib.parse import urlsplit

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ORIGIN = "http://slowbooks.test"
AA = 4.5

# The gate's pages, in its order.
GATE_ROUTES = (
    "#/dashboard",
    "#/pledges",
    "#/invoices",
    "#/accounts",
    "#/reports",
    "#/settings",
)
# A route that only moves the address to another page
REDIRECTS = {"/check-register"}
# Colour keys, the "■" beside each band of the A/R aging bar: graphics, not
# text, so they are held to 3:1 (WCAG 1.4.11) rather than 4.5.
COLOUR_KEYS = {"■"}

# check_css_regressions.py's SWEEP, verbatim but for its comments.
SWEEP = r"""
(function(){
  function parse(c){
    var m = (c || '').match(/[\d.]+/g);
    if (!m || m.length < 3) return null;
    return [+m[0], +m[1], +m[2], m.length > 3 ? +m[3] : 1];
  }
  function over(fg, bg){          // composite fg (with alpha) onto bg
    var a = fg[3];
    return [fg[0]*a + bg[0]*(1-a), fg[1]*a + bg[1]*(1-a),
            fg[2]*a + bg[2]*(1-a), 1];
  }
  // Premultiplied colours, [r*a, g*a, b*a, a]: an element with opacity
  // paints its own content, then lays it over what is behind at that
  // opacity, and source-over in premultiplied form is exactly that.
  function pm(c){ return [c[0]*c[3], c[1]*c[3], c[2]*c[3], c[3]]; }
  function pover(top, under){
    var a = top[3];
    return [top[0] + under[0]*(1-a), top[1] + under[1]*(1-a),
            top[2] + under[2]*(1-a), a + under[3]*(1-a)];
  }
  function fade(c, o){ return [c[0]*o, c[1]*o, c[2]*o, c[3]*o]; }
  // A gradient between known colours is a range: its stops. Only a bitmap
  // (url(...)) is unresolvable from here.
  function stops(bgi){
    if (!bgi || bgi === 'none') return null;
    if (/url\(/.test(bgi)) return null;                 // a real image
    var found = bgi.match(/rgba?\([^)]*\)/g) || [];
    var out = [];
    for (var i = 0; i < found.length; i++) {
      var c = parse(found[i]);
      if (c && c[3] > 0) out.push(c);
    }
    return out.length ? out : null;
  }
  var rgbs = function(c){ return 'rgb(' + Math.round(c[0]) + ', '
                 + Math.round(c[1]) + ', ' + Math.round(c[2]) + ')'; };
  // The text and the ground under it, as painted: the walk up to the
  // ground is the gate's; each element passed keeps its background and its
  // opacity, and the text colour's own alpha is painted on top. A gradient
  // is a range, so one pair per stop.
  function bg(el, text){
    var levels = [], e = el, img = false, grad = null, ground = null;
    while (e && e !== document.documentElement) {
      var cs = getComputedStyle(e), c = parse(cs.backgroundColor);
      var gs = stops(cs.backgroundImage);
      var hasImg = cs.backgroundImage && cs.backgroundImage !== 'none';
      var level = {color: c && c[3] > 0 ? c : null, opacity: +cs.opacity, grad: null};
      levels.push(level);
      if (gs && !grad) { grad = gs; level.grad = gs; }  // the nearest gradient wins
      if (c && c[3] > 0) {
        if (c[3] >= 0.999) { img = img || (!!hasImg && !gs); ground = e; break; }
        if (hasImg && !gs) img = true;
      } else if (hasImg && !gs) {
        img = true;                         // a bitmap: genuinely unresolvable
      }
      if (gs) { ground = e; break; }        // the gradient supplies the paint
      e = e.parentElement;
    }
    // opacity above the ground fades all of it over the page
    var above = 1;
    for (var p = ground && ground.parentElement; p && p !== document.documentElement;
         p = p.parentElement) above *= +getComputedStyle(p).opacity;
    var base = parse(getComputedStyle(document.body).backgroundColor)
               || [255,255,255,1];
    if (base[3] < 0.999) base = [255,255,255,1];
    function paint(withText, stop){
      var content = withText ? pm(text) : [0, 0, 0, 0];
      for (var i = 0; i < levels.length; i++) {
        var L = levels[i];
        if (L.grad && stop) content = pover(content, pm(stop));  // image over colour
        if (L.color) content = pover(content, pm(L.color));
        content = fade(content, L.opacity);
      }
      return pover(fade(content, above), pm(base));
    }
    var pairs = [];
    var each = grad || [null];
    for (var k = 0; k < each.length; k++)
      pairs.push([rgbs(paint(true, each[k])), rgbs(paint(false, each[k]))]);
    return {color: pairs[0][1], image: img, pairs: pairs};
  }
  var out = [], seen = {};
  var nodes = document.querySelectorAll(
    'a,button,label,td,th,h1,h2,h3,h4,h5,p,span,div,li,legend,summary,strong,em');
  for (var i = 0; i < nodes.length && out.length < 400; i++) {
    var el = nodes[i];
    // only elements with their OWN short visible text
    var own = '';
    for (var j = 0; j < el.childNodes.length; j++)
      if (el.childNodes[j].nodeType === 3) own += el.childNodes[j].nodeValue;
    own = own.trim();
    if (!own || own.length > 60) continue;
    var r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) continue;
    var cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
    // a disabled control has no contrast requirement (WCAG 1.4.3)
    if (el.closest('button:disabled, fieldset:disabled')) continue;
    var dim = 1;
    for (var q = el; q && q !== document.documentElement; q = q.parentElement)
      dim *= +getComputedStyle(q).opacity;
    var key = own + '|' + cs.color + '|' + dim;
    if (seen[key]) continue;
    seen[key] = 1;
    var b = bg(el, parse(cs.color));
    out.push({text: own.slice(0, 42), color: cs.color, background: b.color,
              pairs: b.pairs, unmeasurable: b.image,
              size: parseFloat(cs.fontSize) || 0,
              weight: cs.fontWeight, tag: el.tagName.toLowerCase(),
              cls: (el.className || '').toString().slice(0, 40)});
  }
  return out;
})()
"""


def sweep_of(root="document", cap=400):
    """The sweep over `root` (a JavaScript expression for an element, or the
    whole document) with no length limit, as the gate sweeps the splash: a
    What's-new box of long items once went unmeasured at 2.33:1, and the
    page sweep's 60-character limit leaves out every hint paragraph."""
    swept = SWEEP.replace("own.length > 60", "own.length > 100000", 1)
    swept = swept.replace("out.length < 400", f"out.length < {cap}", 1)
    if root != "document":
        swept = swept.replace(
            "document.querySelectorAll(", f"{root}.querySelectorAll(", 1
        )
    assert "100000" in swept and (root == "document" or root in swept)
    return swept


# the gate's splash sweep, exactly
SPLASH_SWEEP = sweep_of("document.getElementById('splash')")
# every other sweep here takes the whole text of everything it finds
PAGE_SWEEP = sweep_of(cap=5000)
TOAST_SWEEP = sweep_of("document.getElementById('toast-container')")


def _rgba(s):
    m = re.findall(r"[\d.]+", s or "")
    if len(m) < 3:
        return None
    return [float(x) for x in m[:3]] + [float(m[3]) if len(m) > 3 else 1.0]


def contrast(fg, bg):
    """WCAG contrast ratio between two computed colours. A translucent text
    colour is seen over its ground, so it is composited there first: the
    gate's scorer kept only r, g and b, and scored rgba(255,255,255,0.35) as
    white (skytech R3-1)."""
    a, b = _rgba(fg), _rgba(bg)
    if not a or not b:
        return None
    a = [a[i] * a[3] + b[i] * (1 - a[3]) for i in range(3)]
    b = b[:3]

    def lum(c):
        out = []
        for v in c:
            v /= 255.0
            out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]

    l1, l2 = sorted((lum(a), lum(b)), reverse=True)
    return round((l1 + 0.05) / (l2 + 0.05), 2)


# What counts as bold for the large-text rule: the gate's page sweep leaves
# 600 out, its splash sweep counts it.
PAGE_BOLD = ("700", "800", "900", "bold")
SPLASH_BOLD = ("600",) + PAGE_BOLD


def _score(item, bold):
    """(ratio, needed) for one swept element, or None where it cannot be
    measured. A gradient is a range: the stop that reads worst. A colour key
    is a graphic: 3:1 (WCAG 1.4.11)."""
    if item.get("unmeasurable"):
        return None
    ratios = [r for r in (contrast(fg, bg) for fg, bg in item["pairs"]) if r]
    if not ratios:
        return None
    size = item.get("size") or 0
    heavy = str(item.get("weight")) in bold
    large = size >= 24 or (size >= 18.66 and heavy)
    need = 3.0 if large or item["text"] in COLOUR_KEYS else AA
    return min(ratios), need


def below_threshold(sweeps, bold=PAGE_BOLD):
    """The gate's report: one row per rule (tag, first class, colour, ground,
    theme) with its worst ratio and the pages it was on."""
    groups = {}
    for (theme, where), items in sweeps.items():
        for it in items:
            scored = _score(it, bold)
            if not scored or scored[0] >= scored[1]:
                continue
            cls = (it.get("cls") or "").split()
            key = (it["tag"], cls[0] if cls else "", it["color"], it["background"])
            g = groups.setdefault(
                key + (theme,),
                {"ratio": scored[0], "need": scored[1], "text": it["text"]},
            )
            g["ratio"] = min(g["ratio"], scored[0])
            g.setdefault("where", set()).add(where)
    return sorted(
        f"{g['ratio']:>5}:1 (needs {g['need']}) {k[0]}{'.' + k[1] if k[1] else ''}"
        f"  {k[2]} on {k[3]}  [{k[4]}]  {g['text']!r}  on {sorted(g['where'])}"
        for k, g in groups.items()
    )


# --- the company -----------------------------------------------------------
# A small bakery's books, entered through the API as a person would: every
# list has rows, every document a status, and every dialog something to show.


def _ok(r):
    assert r.status_code in (200, 201), (str(r.request.url), r.status_code, r.text)
    return r.json()


def seed_books(client, seed_accounts):
    """The ids of what it made, by name."""
    a = {number: account.id for number, account in seed_accounts.items()}

    def post(path, body=None):
        return _ok(client.post(path, json=body or {}))

    S = {"checking": a["1000"]}
    S["bank"] = post(
        "/api/banking/accounts",
        {
            "name": "Harbor Checking",
            "account_id": a["1000"],
            "bank_name": "Columbia Bank",
            "last_four": "4417",
            "opening_balance": "12500.00",
            "opening_date": "2026-01-01",
        },
    )["id"]
    S["service"] = post(
        "/api/items",
        {
            "name": "Catering Service",
            "item_type": "service",
            "description": "Event catering, per hour",
            "rate": 85,
            "income_account_id": a["4000"],
            "is_taxable": False,
        },
    )["id"]
    S["loaf"] = post(
        "/api/items",
        {
            "name": "Sourdough Loaf",
            "item_type": "product",
            "description": "Sourdough loaf, 1 kg",
            "rate": 8.5,
            "cost": 3.1,
            "is_taxable": True,
            "track_inventory": True,
            "quantity_on_hand": 40,
            "reorder_point": 10,
        },
    )["id"]
    S["customer"] = post(
        "/api/customers",
        {
            "name": "Salt & Pine Catering Co.",
            "company": "Salt & Pine Catering Co.",
            "email": "orders@saltandpine.example",
            "phone": "(503) 555-0142",
            "bill_address1": "1180 Commercial St",
            "bill_city": "Astoria",
            "bill_state": "OR",
            "bill_zip": "97103",
            "terms": "Net 15",
            "is_taxable": True,
        },
    )["id"]
    S["customer2"] = post(
        "/api/customers",
        {
            "name": "Harbor District Events",
            "email": "hello@harborevents.example",
            "terms": "Net 30",
        },
    )["id"]
    S["vendor"] = post(
        "/api/vendors",
        {
            "name": "Cascade Flour Mill",
            "company": "Cascade Flour Mill",
            "address1": "44 Mill Rd",
            "city": "Portland",
            "state": "OR",
            "zip": "97201",
            "terms": "Net 30",
        },
    )["id"]
    S["vendor2"] = post(
        "/api/vendors",
        {
            "name": "Blue Heron Installs",
            "is_1099_vendor": True,
            "vendor_1099_type": "NEC",
        },
    )["id"]

    def invoice(amount, date, **extra):
        return post(
            "/api/invoices",
            {
                "customer_id": S["customer"],
                "date": date,
                "tax_rate": 0,
                "lines": [
                    {
                        "item_id": S["service"],
                        "description": "Event catering",
                        "quantity": 1,
                        "rate": amount,
                    }
                ],
                **extra,
            },
        )

    def pay(inv, amount):
        return post(
            "/api/payments",
            {
                "customer_id": S["customer"],
                "date": "2026-09-20",
                "amount": amount,
                "method": "Check",
                "check_number": "2231",
                "allocations": [{"invoice_id": inv["id"], "amount": amount}],
            },
        )

    # an invoice in every status a list shows
    S["draft"] = invoice(120, "2026-09-24")["id"]
    S["sent"] = invoice(240, "2026-09-22", due_date="2026-12-31")["id"]
    _ok(client.post(f"/api/invoices/{S['sent']}/send"))
    paid = invoice(300, "2026-09-10")
    S["paid"], S["payment"] = paid["id"], pay(paid, 300)["id"]
    part = invoice(500, "2026-09-12")
    S["partial"] = part["id"]
    pay(part, 200)
    S["overdue"] = invoice(80, "2026-06-01", due_date="2026-06-15")["id"]
    _ok(client.post(f"/api/invoices/{S['overdue']}/send"))
    S["void"] = invoice(999, "2026-09-05")["id"]
    _ok(client.post(f"/api/invoices/{S['void']}/void"))
    loaves = [{"item_id": S["loaf"], "description": "Sourdough Loaf", "rate": 8.5}]
    S["estimate"] = post(
        "/api/estimates",
        {
            "customer_id": S["customer"],
            "date": "2026-09-18",
            "expiration_date": "2026-10-18",
            "tax_rate": 0.0825,
            "lines": [dict(loaves[0], quantity=24)],
        },
    )["id"]
    S["receipt"] = post(
        "/api/sales-receipts",
        {
            "customer_id": S["customer2"],
            "date": "2026-09-19",
            "tax_rate": 0.0825,
            "method": "card",
            "lines": [dict(loaves[0], quantity=3, is_taxable=True)],
        },
    )["invoice"]["id"]
    S["memo"] = post(
        "/api/credit-memos",
        {
            "customer_id": S["customer2"],
            "date": "2026-09-21",
            "lines": [
                {"description": "Returned tray deposit", "quantity": 1, "rate": 45}
            ],
        },
    )["id"]
    # an open invoice beside the credit memo, for the apply-credit dialogs
    S["invoice2"] = post(
        "/api/invoices",
        {
            "customer_id": S["customer2"],
            "date": "2026-09-23",
            "tax_rate": 0,
            "lines": [{"description": "Tasting menu", "quantity": 1, "rate": 150}],
        },
    )["id"]
    S["deposit"] = post(
        "/api/deposits",
        {"deposit_to_account_id": a["1000"], "date": "2026-09-22", "total": "300"},
    )["transaction_id"]
    S["recurring"] = post(
        "/api/recurring",
        {
            "customer_id": S["customer2"],
            "frequency": "monthly",
            "start_date": "2026-10-01",
            "lines": [
                {
                    "item_id": S["service"],
                    "description": "Monthly tasting",
                    "quantity": 2,
                    "rate": 85,
                }
            ],
        },
    )["id"]

    # purchases and the bank
    S["bill"] = post(
        "/api/bills",
        {
            "vendor_id": S["vendor"],
            "date": "2026-09-08",
            "terms": "Net 30",
            "bill_number": "CFM-0918",
            "lines": [
                {
                    "account_id": a["5000"],
                    "description": "Flour, 50 lb",
                    "quantity": 12,
                    "rate": 38.5,
                }
            ],
        },
    )["id"]
    S["paid_bill"] = post(
        "/api/bills",
        {
            "vendor_id": S["vendor2"],
            "date": "2026-08-28",
            "terms": "Net 15",
            "bill_number": "BHI-221",
            "lines": [
                {
                    "account_id": a["6000"],
                    "description": "Oven hood install",
                    "quantity": 1,
                    "rate": 640,
                }
            ],
        },
    )["id"]
    S["bill_payment"] = post(
        "/api/bill-payments",
        {
            "vendor_id": S["vendor2"],
            "date": "2026-09-09",
            "amount": 640,
            "allocations": [{"bill_id": S["paid_bill"], "amount": 640}],
        },
    )["id"]
    S["po"] = post(
        "/api/purchase-orders",
        {
            "vendor_id": S["vendor"],
            "date": "2026-09-15",
            "tax_rate": 0,
            "lines": [{"description": "Rye flour, 25 lb", "quantity": 8, "rate": 22}],
        },
    )["id"]
    S["vendor_credit"] = post(
        "/api/vendor-credits",
        {
            "vendor_id": S["vendor"],
            "date": "2026-09-16",
            "lines": [
                {
                    "description": "Short-shipped bag",
                    "quantity": 1,
                    "rate": 38.5,
                    "account_id": a["5000"],
                }
            ],
        },
    )["id"]
    S["journal"] = post(
        "/api/journal",
        {
            "date": "2026-09-25",
            "description": "September accrual",
            "lines": [
                {"account_id": a["6000"], "debit": "50.00", "credit": "0"},
                {"account_id": a["1000"], "debit": "0", "credit": "50.00"},
            ],
        },
    )["id"]
    S["expense"] = post(
        "/api/expenses",
        {
            "date": "2026-09-02",
            "expense_account_id": a["6000"],
            "paid_from_account_id": a["1000"],
            "amount": "30.30",
            "reference": "rcpt 1187",
            "memo": "Team lunch",
            "vendor_id": S["vendor"],
        },
    )["id"]
    S["cc_charge"] = post(
        "/api/cc-charges",
        {
            "date": "2026-09-01",
            "payee": "Fuel",
            "amount": "40",
            "account_id": a["6000"],
        },
    )["transaction_id"]
    S["bank_rule"] = post(
        "/api/bank-rules",
        {"name": "Fuel", "pattern": "SHELL", "account_id": a["6000"]},
    )["id"]
    # a statement imported to the bank feed: two lines it matches, one to review
    statement = (
        "Date,Description,Amount\n"
        "09/02/2026,SWEET FOREST CAFE,-30.30\n"
        "09/24/2026,SHELL OIL 5521,-48.12\n"
        '09/25/2026,MOBILE DEPOSIT,"300.00"\n'
    )
    _ok(
        client.post(
            f"/api/bank-import/import-csv/{S['bank']}",
            files={"file": ("statement.csv", statement.encode(), "text/csv")},
        )
    )
    feed = _ok(client.get(f"/api/banking/transactions?bank_account_id={S['bank']}"))
    S["feed_line"] = next(t["id"] for t in feed if t["match_status"] == "auto")
    # January's statement, reconciled
    recon = post(
        "/api/banking/reconciliations",
        {
            "account_id": a["1000"],
            "statement_date": "2026-01-31",
            "statement_balance": "12500.00",
        },
    )["id"]
    session = _ok(client.get(f"/api/banking/reconciliations/{recon}/transactions"))
    for line in session["transactions"]:
        post(f"/api/banking/reconciliations/{recon}/toggle/{line['id']}")
    post(f"/api/banking/reconciliations/{recon}/complete")
    S["reconciliation"] = recon

    # a job
    S["cost_code"] = post(
        "/api/cost-codes", {"code": "02-100", "name": "Site prep", "cost_type": "labor"}
    )["id"]
    S["job"] = post(
        "/api/jobs",
        {
            "customer_id": S["customer"],
            "name": "Waterfront Gala",
            "job_number": "J-1001",
            "job_type": "Catering",
            "start_date": "2026-09-01",
            "contract_amount": "4800.00",
            "notes": "Tent setup the day before.",
        },
    )["id"]
    S["job_cost"] = post(
        "/api/job-costs",
        {
            "date": "2026-09-12",
            "job_id": S["job"],
            "memo": "Rental chairs",
            "lines": [
                {
                    "description": "Chair rental",
                    "quantity": 120,
                    "rate": 2.5,
                    "cost_code_id": S["cost_code"],
                    "debit_account_id": a["5000"],
                    "credit_account_id": a["2000"],
                }
            ],
        },
    )["id"]

    # people
    staff = {
        "pay_frequency": "biweekly",
        "filing_status": "single",
        "city": "Astoria",
        "state": "OR",
        "zip": "97103",
        "work_state": "OR",
        "residence_state": "OR",
        "role": "employee",
    }
    S["employee"] = post(
        "/api/employees",
        dict(
            staff,
            first_name="Lena",
            last_name="Ortiz",
            ssn_last_four="4410",
            pay_type="salary",
            pay_rate=56000,
            address1="310 Duane St",
            email="lena@example.com",
            hire_date="2025-03-01",
        ),
    )["id"]
    S["employee2"] = post(
        "/api/employees",
        dict(
            staff,
            first_name="Jonah",
            last_name="Pike",
            ssn_last_four="5521",
            pay_type="hourly",
            pay_rate=19.5,
            hire_date="2026-02-10",
        ),
    )["id"]
    S["time_entry"] = post(
        "/api/time-entries",
        {
            "employee_id": S["employee2"],
            "date": "2026-09-15",
            "hours_regular": 8,
            "job_id": S["job"],
            "cost_code_id": S["cost_code"],
            "notes": "Gala prep",
        },
    )["id"]
    S["pay_run"] = post(
        "/api/payroll",
        {
            "period_start": "2026-09-01",
            "period_end": "2026-09-14",
            "pay_date": "2026-09-19",
            "stubs": [
                {"employee_id": S["employee"]},
                {"employee_id": S["employee2"], "hours": 72},
            ],
        },
    )["id"]
    S["pto_policy"] = post(
        "/api/pto/policies",
        {
            "name": "Paid Sick Leave",
            "pto_type": "sick",
            "accrual_method": "per_hour_worked",
            "accrual_rate": 0.025,
            "max_carryover": 40,
            "accrue_liability": True,
        },
    )["id"]
    post(
        "/api/pto/accruals",
        {"employee_id": S["employee"], "policy_id": S["pto_policy"], "balance": 6},
    )
    post("/api/benefits/setup-accounts")
    S["benefit_code"] = post("/api/benefits/codes/seed-standard")[0]["id"]
    S["benefit_group"] = post(
        "/api/benefits/groups",
        {"name": "Full-time staff", "description": "Salaried, and 30 or more hours"},
    )["id"]

    post("/api/email-templates/seed-defaults")
    S["template"] = _ok(client.get("/api/email-templates"))[0]["id"]

    # a fixed asset
    S["asset_type"] = post(
        "/api/fixed-assets/types",
        {
            "name": "Kitchen Equipment",
            "description": "Ovens, mixers, proofers",
            "depreciation_method": "straight_line",
            "effective_life_years": 7,
            "asset_account_id": a["1500"],
            "accumulated_depreciation_account_id": a["1510"],
            "depreciation_expense_account_id": a["6810"],
        },
    )["id"]
    S["asset"] = post(
        "/api/fixed-assets",
        {
            "name": "Deck oven",
            "asset_type_id": S["asset_type"],
            "purchase_date": "2025-11-04",
            "purchase_price": "18400.00",
            "salvage_value": "0.00",
        },
    )["id"]

    # a reseller permit in each state the page tells apart
    def permit(number, expires, active=True):
        return post(
            "/api/reseller-permits",
            {
                "entity_type": "customer",
                "entity_id": S["customer"],
                "jurisdiction": "WA",
                "permit_number": number,
                "issued_at": "2024-01-15",
                "expires_at": expires,
                "is_active": active,
            },
        )["id"]

    # "Expires soon" is within 30 days of today, so the date is worked out
    # from today: a fixed one went from soon to expired on 2026-10-07 and
    # the sweep lost the "Expires soon" badge it measures.
    soon = (date.today() + timedelta(days=10)).isoformat()
    S["permit_expired"] = permit("603112457", "2026-08-01")
    S["permit_soon"] = permit("603112458", soon)
    S["permit_active"] = permit("603112459", "2028-01-14")
    S["permit_inactive"] = permit("603112460", "2028-06-30", active=False)
    post(
        f"/api/reseller-permits/{S['permit_active']}/mark-verified",
        {"verified_by": "TVH"},
    )
    # a void expense and an inactive vendor and item, which their lists keep,
    # set aside
    voided = post(
        "/api/expenses",
        {
            "date": "2026-09-03",
            "expense_account_id": a["6000"],
            "paid_from_account_id": a["1000"],
            "amount": "12.00",
            "memo": "Entered twice",
        },
    )["id"]
    post(f"/api/expenses/{voided}/void")
    old = post("/api/vendors", {"name": "Old Harbor Ice Co."})["id"]
    _ok(client.put(f"/api/vendors/{old}", json={"is_active": False}))
    stollen = post(
        "/api/items",
        {"name": "Holiday Stollen", "item_type": "product", "rate": 14},
    )["id"]
    _ok(client.put(f"/api/items/{stollen}", json={"is_active": False}))
    # every card on the dashboard, not only the ones it starts with
    cards = _ok(client.get("/api/dashboard/widgets"))["widgets"]
    order = {"value": {"order": [c["id"] for c in cards]}}
    _ok(client.put("/api/preferences/dashboard", json=order))
    return S


# What only another kind of install answers, answered as it does there: the
# company list of a Server Edition install (PostgreSQL), which says when each
# company was last opened, and the backups of a company kept in a file (the
# suite's is in memory, so it has none).
SERVED = {
    "/api/companies": [
        {
            "id": None,
            "name": "Harbor Light Bakery",
            "database_name": "harbor_light",
            "description": "the database this server is connected to",
            "last_accessed": None,
            "is_current": True,
        },
        {
            "id": 2,
            "name": "Harbor Light Catering",
            "database_name": "harbor_catering",
            "description": "Events and weddings",
            "last_accessed": "2026-09-21T16:02:11",
            "is_current": False,
        },
    ],
    "/api/backups": [
        {
            "id": 2,
            "filename": "harbor-light-bakery_2026-09-25_2210.db",
            "file_size": 1843200,
            "backup_type": "manual",
            "notes": "Before the September close",
            "created_at": "2026-09-25T22:10:04+00:00",
        },
        {
            "id": 1,
            "filename": "harbor-light-bakery_2026-09-18_0915_pre-restore.db",
            "file_size": 1720320,
            "backup_type": "pre-restore",
            "notes": None,
            "created_at": "2026-09-18T09:15:40+00:00",
        },
    ],
}


# Named, so another module can import them without shadowing the names its
# tests ask for (tests/test_dialog_contrast.py).
@pytest.fixture(name="books")
def books_fixture(client, seed_accounts):
    return seed_books(client, seed_accounts)


@pytest.fixture(name="company")
def company_fixture(client, books):
    return client


# --- the browser ----------------------------------------------------------


@pytest.fixture(scope="module", name="browser")
def browser_fixture():
    with sync_api.sync_playwright() as p:
        try:
            chromium = p.chromium.launch()
        except Exception as exc:  # the package without its browser
            pytest.skip(f"playwright's Chromium is not installed: {exc}")
        yield chromium
        chromium.close()


_HOP_BY_HOP = {"content-length", "content-encoding", "transfer-encoding", "connection"}


def _served_by(client, handled, served):
    """Every request the page makes, answered by the app through the test
    client, which is signed in to the company above, except the paths in
    `served`, answered with that body. Anything off the origin (web fonts
    and the like) is refused: not part of what is measured."""

    def serve(route):
        req = route.request
        url = urlsplit(req.url)
        if f"{url.scheme}://{url.netloc}" != ORIGIN:
            return route.abort()
        target = url.path + (f"?{url.query}" if url.query else "")
        if req.method == "GET" and url.path in served:
            handled.append(target)
            return route.fulfill(json=served[url.path])
        headers = {
            k: v
            for k, v in req.headers.items()
            if k.lower() in ("content-type", "accept")
        }
        resp = client.request(
            req.method, target, headers=headers, content=req.post_data_buffer
        )
        handled.append(target)
        route.fulfill(
            status=resp.status_code,
            headers={
                k: v for k, v in resp.headers.items() if k.lower() not in _HOP_BY_HOP
            },
            body=resp.content,
        )

    return serve


def _open(browser, client, served=None):
    handled = []
    # the gate's window: 1500 x 980
    page = browser.new_page(viewport={"width": 1500, "height": 980})
    page.route(
        "**/*", _served_by(client, handled, SERVED if served is None else served)
    )
    page.goto(f"{ORIGIN}/")
    page.wait_for_function("window.App && document.readyState === 'complete'")
    # The lists open on Show: Active since #210. The sweeps look at them on
    # Show: All, so the inactive vendor and item set aside above (dimmed,
    # badged) are still measured.
    page.evaluate("""() => ['customers', 'vendors', 'items', 'employees', 'jobs']
            .forEach(k => localStorage.setItem('slowbooks-show-' + k, 'all'))""")
    return page, handled


def _visit(page, handled, route):
    """The page at `route`, rendered, with whatever it fills in afterwards.
    App.navigate is what the address change runs; awaiting it directly means
    the page is in, rather than guessing how long that takes."""
    page.evaluate("async (h) => { await App.navigate(h); }", route)
    settle(page, handled)


def settle(page, handled):
    """A moment in which the page asks for nothing more: some fill in parts
    after they open."""
    quiet = 0
    for _ in range(125):
        n = len(handled)
        page.wait_for_timeout(40)
        quiet = quiet + 1 if len(handled) == n else 0
        if quiet >= 2:
            return


def _theme(page, theme):
    # as the gate does it: the attribute and the remembered choice
    page.evaluate(
        """(t) => { document.documentElement.setAttribute('data-theme', t);
                    localStorage.setItem('slowbooks-theme', t); }""",
        theme,
    )
    # Buttons fade to the new theme's colours (transition: all 0.1s), and a
    # colour read halfway is neither theme's. The gate waits 1.2 s; here the
    # fades are run to their end, which is the colour the theme sets.
    page.evaluate("""() => document.getAnimations()
                   .filter(a => a instanceof CSSTransition)
                   .forEach(a => a.finish())""")


def test_the_gate_pages_and_the_splash_meet_aa_in_both_themes(browser, company):
    """The gate's sequence: its six pages, and the dashboard, in dark and
    then light, with the splash still up behind them as the gate leaves it;
    then the splash with its terms, in light and then dark."""
    page, handled = _open(browser, company)
    try:
        pages = {}
        for theme in ("dark", "light"):
            _theme(page, theme)
            for route in GATE_ROUTES + ("#/",):
                _visit(page, handled, route)
                pages[(theme, route)] = page.evaluate(SWEEP)
        splash = {}
        for theme in ("light", "dark"):
            _theme(page, theme)
            page.evaluate(
                """() => { document.getElementById('splash').classList.remove('hidden');
                           const t = document.getElementById('splash-terms');
                           if (t) t.hidden = false; }"""
            )
            page.wait_for_function(
                "() => !document.getElementById('splash-whatsnew').hidden"
            )
            splash[(theme, "splash")] = page.evaluate(SPLASH_SWEEP)
    finally:
        page.close()

    # the sweep read the pages, the void badge and the splash's licence block
    texts = {it["text"] for items in pages.values() for it in items}
    assert {"Chart of Accounts", "Reports", "void"} <= texts
    splash_texts = {it["text"] for items in splash.values() for it in items}
    assert {"Before you start", "I understand"} <= splash_texts
    assert all(splash.values())

    # the gate's report, which should be empty: one row per rule below AA
    assert (below_threshold(pages), below_threshold(splash, SPLASH_BOLD)) == ([], [])


def test_every_page_and_notice_meets_aa_in_both_themes(browser, company, books):
    """Every page of the app, a job's and the bank register's own pages
    among them, each swept whole in both themes; and a success, an error and
    an information notice."""
    # the desktop app with an update waiting: the notice at the top of the
    # sidebar shows on every page
    info = _ok(company.get("/api/system"))
    served = dict(SERVED)
    served["/api/system"] = dict(info, update_check_enabled=True)
    served["/api/system/update-check"] = {
        "update_available": True,
        "latest_version": "2.18.1",
        "download_url": "https://github.com/VonHoltenCodes/SlowBooks-Pro-2026/releases",
    }
    page, handled = _open(browser, company, served)
    try:
        paths = page.evaluate(
            "() => Object.keys(App.routes).filter(k => !k.includes('/:'))"
        )
        # the gate's pages too: the gate sweep reads only text of up to 60
        # characters
        routes = [f"#{p}" for p in paths if p not in REDIRECTS]
        assert len(routes) >= 45, routes
        routes += [f"#/jobs/{books['job']}", f"#/banking/{books['checking']}"]
        pages = {}
        for route in routes:
            _visit(page, handled, route)
            for theme in ("dark", "light"):
                _theme(page, theme)
                pages[(theme, route)] = page.evaluate(PAGE_SWEEP)
        # the global search's dropdown
        page.fill("#global-search", "an")
        page.wait_for_selector("#search-results .search-item")
        for theme in ("dark", "light"):
            _theme(page, theme)
            pages[(theme, "search")] = page.evaluate(
                sweep_of("document.getElementById('search-results')")
            )
        page.fill("#global-search", "")
        notices = {}
        for theme in ("light", "dark"):
            _theme(page, theme)
            page.evaluate("""() => { toast('Invoice saved', 'success');
                           toast('Could not save the invoice', 'error');
                           toast('Opening the report', 'info'); }""")
            # measured once they have faded in (toast-in, 0.2 s)
            page.wait_for_function(
                """() => { const t = [...document.querySelectorAll('#toast-container .toast')];
                           return t.length === 3
                               && t.every(e => getComputedStyle(e).opacity === '1'); }"""
            )
            notices[(theme, "toasts")] = page.evaluate(TOAST_SWEEP)
            page.evaluate(
                "() => document.querySelectorAll('#toast-container .toast')"
                ".forEach(e => e.remove())"
            )
    finally:
        page.close()

    # every page was in, not an error in its place
    failed = [
        where
        for where, items in pages.items()
        if any(
            it["text"] in ("Couldn't load this page", "Page not found") for it in items
        )
    ]
    assert failed == []
    # and they showed what they show with books in them: permits in every
    # state, a job, the register, when another company was last opened
    texts = {it["text"] for items in pages.values() for it in items}
    shown = {"Expired", "Expires soon", "Active", "Inactive", "Never", "Note:"}
    shown |= {"Click to browse", "Waterfront Gala", "Checking", "See what changed →"}
    assert shown <= texts, shown - texts
    assert any(t.startswith("Last accessed:") for t in texts)
    assert [len(items) for items in notices.values()] == [3, 3]

    assert (below_threshold(pages), below_threshold(notices)) == ([], [])
