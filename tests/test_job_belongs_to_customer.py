"""A customer document carries its own customer's jobs only (2.22.0 gate,
NEW-36). An invoice could be saved with another customer's job: the form's
filter ran on the hidden select's focus, which the 2.19 type-ahead never
gives it, and the API took any job_id, so P&L by Job, the job page and Job
Profitability counted the invoice under a job that was not the customer's.

Every write that takes a job_id beside a customer refuses a job of another
customer with 400, in the words a payment to another customer's invoice is
refused with (#189), and writes nothing: invoices (create and edit, the
header's job and each line's), sales receipts (a counter sale is the
walk-in customer's), credit memos, estimates (create and edit), recurring
schedules (create and edit) and in-kind gifts. A job that does not exist
is 404. An edit is judged when it touches the customer, the job or the
lines; one that touches none of them saves a document as it is, even one
carrying a mismatch from before the rule. Deposits, bank entries, bills,
time entries and journal entries carry a job with no customer, so they are
not in this rule."""

import pytest

from app.models.contacts import Customer
from app.models.credit_memos import CreditMemo
from app.models.estimates import Estimate, EstimateLine
from app.models.in_kind import InKindGift
from app.models.invoices import Invoice, InvoiceLine
from app.models.payments import Payment
from app.models.recurring import RecurringInvoice
from app.models.transactions import Transaction

REFUSED = "belongs to a different customer"


def _count(TestSession):
    with TestSession() as s:
        return {
            m.__tablename__: s.query(m).count()
            for m in (
                Invoice,
                Payment,
                CreditMemo,
                Estimate,
                RecurringInvoice,
                InKindGift,
                Transaction,
            )
        }


@pytest.fixture
def two_jobs(client, db_session):
    """Alder Co with its Kitchen job, Birch Co with its Roof job."""
    alder, birch = Customer(name="Alder Co", is_active=True), Customer(
        name="Birch Co", is_active=True
    )
    db_session.add_all([alder, birch])
    db_session.commit()
    jobs = {}
    for cust, name in ((alder, "Kitchen"), (birch, "Roof")):
        r = client.post("/api/jobs", json={"customer_id": cust.id, "name": name})
        assert r.status_code == 201, r.text
        jobs[name] = r.json()["id"]
    return {
        "alder": alder.id,
        "birch": birch.id,
        "kitchen": jobs["Kitchen"],
        "roof": jobs["Roof"],
    }


def _line(**over):
    return {"description": "Service", "quantity": 1, "rate": 100, **over}


def _invoice_body(customer_id, **over):
    return {
        "customer_id": customer_id,
        "date": "2026-04-01",
        "lines": [_line()],
        **over,
    }


HINT = " — clear the Job field or pick one of this customer's."


def _refused(resp, document, where=""):
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert REFUSED in detail and detail.endswith(
        f"than this {document}{where}{HINT}"
    ), detail


# ── invoices ─────────────────────────────────────────────────────────────


def test_an_invoice_takes_only_its_customers_job(
    client, TestSession, seed_accounts, two_jobs
):
    before = _count(TestSession)
    r = client.post(
        "/api/invoices", json=_invoice_body(two_jobs["alder"], job_id=two_jobs["roof"])
    )
    _refused(r, "invoice")
    assert r.json()["detail"] == (
        "Job Roof belongs to a different customer than this invoice — clear the "
        "Job field or pick one of this customer's."
    )
    assert _count(TestSession) == before, "nothing was written"

    # a line's job as well as the header's
    r = client.post(
        "/api/invoices",
        json=_invoice_body(
            two_jobs["alder"],
            job_id=two_jobs["kitchen"],
            lines=[_line(), _line(job_id=two_jobs["roof"])],
        ),
    )
    _refused(r, "invoice", " (line 2)")
    assert _count(TestSession) == before

    # a job that does not exist
    r = client.post(
        "/api/invoices", json=_invoice_body(two_jobs["alder"], job_id=99999)
    )
    assert r.status_code == 404 and r.json()["detail"] == "Job not found"

    # its own job, on the header and a line
    r = client.post(
        "/api/invoices",
        json=_invoice_body(
            two_jobs["alder"],
            job_id=two_jobs["kitchen"],
            lines=[_line(job_id=two_jobs["kitchen"])],
        ),
    )
    assert r.status_code == 201, r.text
    assert r.json()["job_id"] == two_jobs["kitchen"]
    assert r.json()["lines"][0]["job_id"] == two_jobs["kitchen"]


def test_an_edit_keeps_the_invoice_on_its_customers_job(
    client, TestSession, seed_accounts, two_jobs
):
    inv = client.post(
        "/api/invoices",
        json=_invoice_body(
            two_jobs["alder"],
            job_id=two_jobs["kitchen"],
            lines=[_line(job_id=two_jobs["kitchen"])],
        ),
    ).json()
    before = _count(TestSession)

    # another customer's job
    _refused(
        client.put(f"/api/invoices/{inv['id']}", json={"job_id": two_jobs["roof"]}),
        "invoice",
    )
    # another customer, keeping the stored job: the header's, then a line's
    _refused(
        client.put(
            f"/api/invoices/{inv['id']}", json={"customer_id": two_jobs["birch"]}
        ),
        "invoice",
    )
    _refused(
        client.put(
            f"/api/invoices/{inv['id']}",
            json={"customer_id": two_jobs["birch"], "job_id": None},
        ),
        "invoice",
        " (line 1)",
    )
    # lines resent with another customer's job
    _refused(
        client.put(
            f"/api/invoices/{inv['id']}",
            json={"lines": [_line(job_id=two_jobs["roof"])]},
        ),
        "invoice",
        " (line 1)",
    )
    assert _count(TestSession) == before
    kept = client.get(f"/api/invoices/{inv['id']}").json()
    assert kept["customer_id"] == two_jobs["alder"]
    assert kept["job_id"] == two_jobs["kitchen"]

    # a new customer with their own job, the lines resent for it
    r = client.put(
        f"/api/invoices/{inv['id']}",
        json={
            "customer_id": two_jobs["birch"],
            "job_id": two_jobs["roof"],
            "lines": [_line(job_id=two_jobs["roof"])],
        },
    )
    assert r.status_code == 200, r.text
    assert (r.json()["customer_id"], r.json()["job_id"]) == (
        two_jobs["birch"],
        two_jobs["roof"],
    )
    # and an edit that leaves the job alone still goes through
    r = client.put(f"/api/invoices/{inv['id']}", json={"notes": "Thanks"})
    assert r.status_code == 200, r.text


def test_a_nonprofit_is_told_in_its_own_words(client, seed_accounts, two_jobs):
    assert (
        client.put("/api/settings", json={"company_type": "nonprofit"}).status_code
        == 200
    )
    r = client.post(
        "/api/invoices",
        json=_invoice_body(two_jobs["alder"], job_id=two_jobs["roof"], is_pledge=True),
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == (
        "Grant Roof belongs to a different donor than this pledge — clear the "
        "Grant field or pick one of this donor's."
    )
    # a donation receipt is refused by that name
    receipt = {
        "customer_id": two_jobs["alder"],
        "date": "2026-04-03",
        "method": "card",
        "job_id": two_jobs["roof"],
        "lines": [_line()],
    }
    r = client.post("/api/sales-receipts", json=receipt)
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == (
        "Grant Roof belongs to a different donor than this donation receipt — "
        "clear the Grant field or pick one of this donor's."
    )
    # and a move is refused in the same words, each document by that name
    pledge = client.post(
        "/api/invoices",
        json=_invoice_body(two_jobs["birch"], job_id=two_jobs["roof"], is_pledge=True),
    )
    assert pledge.status_code == 201, pledge.text
    r = client.put(
        f"/api/jobs/{two_jobs['roof']}", json={"customer_id": two_jobs["alder"]}
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == (
        "Grant Roof is on 1 pledge for Birch Co; move those first."
    )
    r = client.post(
        "/api/sales-receipts", json={**receipt, "customer_id": two_jobs["birch"]}
    )
    assert r.status_code == 201, r.text
    r = client.put(
        f"/api/jobs/{two_jobs['roof']}", json={"customer_id": two_jobs["alder"]}
    )
    assert r.json()["detail"] == (
        "Grant Roof is on 1 pledge and 1 donation receipt for Birch Co; move those first."
    )


# ── sales receipts ───────────────────────────────────────────────────────


def test_a_sales_receipt_takes_only_its_customers_job(
    client, TestSession, seed_accounts, two_jobs
):
    body = {
        "customer_id": two_jobs["alder"],
        "date": "2026-04-03",
        "method": "card",
        "lines": [_line()],
    }
    before = _count(TestSession)
    r = client.post("/api/sales-receipts", json={**body, "job_id": two_jobs["roof"]})
    _refused(r, "sales receipt")
    r = client.post(
        "/api/sales-receipts",
        json={**body, "lines": [_line(job_id=two_jobs["roof"])]},
    )
    _refused(r, "sales receipt", " (line 1)")
    # a counter sale is the walk-in customer's, whose job no one's is
    r = client.post(
        "/api/sales-receipts",
        json={**body, "customer_id": None, "job_id": two_jobs["kitchen"]},
    )
    _refused(r, "sales receipt")
    assert _count(TestSession) == before, "no invoice and no payment"

    r = client.post("/api/sales-receipts", json={**body, "job_id": two_jobs["kitchen"]})
    assert r.status_code == 201, r.text
    assert r.json()["invoice"]["job_id"] == two_jobs["kitchen"]


# ── credit memos ─────────────────────────────────────────────────────────


def test_a_credit_memo_takes_only_its_customers_job(
    client, TestSession, seed_accounts, two_jobs
):
    body = {
        "customer_id": two_jobs["alder"],
        "date": "2026-04-02",
        "lines": [{"description": "Credit", "quantity": 1, "rate": 50}],
    }
    before = _count(TestSession)
    _refused(
        client.post("/api/credit-memos", json={**body, "job_id": two_jobs["roof"]}),
        "credit memo",
    )
    assert _count(TestSession) == before
    r = client.post("/api/credit-memos", json={**body, "job_id": two_jobs["kitchen"]})
    assert r.status_code == 201, r.text
    assert r.json()["job_id"] == two_jobs["kitchen"]


# ── estimates ────────────────────────────────────────────────────────────


def test_an_estimate_takes_only_its_customers_job(
    client, TestSession, seed_accounts, two_jobs
):
    body = {
        "customer_id": two_jobs["alder"],
        "date": "2026-04-04",
        "tax_rate": 0,
        "lines": [_line()],
    }
    before = _count(TestSession)
    _refused(
        client.post("/api/estimates", json={**body, "job_id": two_jobs["roof"]}),
        "estimate",
    )
    _refused(
        client.post(
            "/api/estimates", json={**body, "lines": [_line(job_id=two_jobs["roof"])]}
        ),
        "estimate",
        " (line 1)",
    )
    assert _count(TestSession) == before

    est = client.post("/api/estimates", json={**body, "job_id": two_jobs["kitchen"]})
    assert est.status_code == 201, est.text
    est = est.json()
    _refused(
        client.put(f"/api/estimates/{est['id']}", json={"job_id": two_jobs["roof"]}),
        "estimate",
    )
    _refused(
        client.put(
            f"/api/estimates/{est['id']}", json={"customer_id": two_jobs["birch"]}
        ),
        "estimate",
    )
    _refused(
        client.put(
            f"/api/estimates/{est['id']}",
            json={"lines": [_line(job_id=two_jobs["roof"])]},
        ),
        "estimate",
        " (line 1)",
    )
    kept = client.get(f"/api/estimates/{est['id']}").json()
    assert (kept["customer_id"], kept["job_id"]) == (
        two_jobs["alder"],
        two_jobs["kitchen"],
    )
    r = client.put(
        f"/api/estimates/{est['id']}",
        json={"customer_id": two_jobs["birch"], "job_id": two_jobs["roof"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["job_id"] == two_jobs["roof"]


# ── recurring schedules ──────────────────────────────────────────────────


def test_a_recurring_schedule_takes_only_its_customers_job(
    client, TestSession, seed_accounts, two_jobs
):
    body = {
        "customer_id": two_jobs["alder"],
        "frequency": "monthly",
        "start_date": "2026-01-01",
        "lines": [{"description": "Retainer", "quantity": 1, "rate": "100"}],
    }
    before = _count(TestSession)
    _refused(
        client.post("/api/recurring", json={**body, "job_id": two_jobs["roof"]}),
        "recurring invoice",
    )
    assert _count(TestSession) == before

    rec = client.post("/api/recurring", json={**body, "job_id": two_jobs["kitchen"]})
    assert rec.status_code == 201, rec.text
    rec = rec.json()
    _refused(
        client.put(f"/api/recurring/{rec['id']}", json={"job_id": two_jobs["roof"]}),
        "recurring invoice",
    )
    assert (
        client.get(f"/api/recurring/{rec['id']}").json()["job_id"]
        == two_jobs["kitchen"]
    )
    r = client.put(f"/api/recurring/{rec['id']}", json={"job_id": None})
    assert r.status_code == 200 and r.json()["job_id"] is None, r.text


# ── in-kind gifts (a nonprofit's donor documents) ────────────────────────


def test_an_in_kind_gift_takes_only_its_donors_grant(
    client, TestSession, seed_accounts, two_jobs
):
    client.put("/api/settings", json={"company_type": "nonprofit"})
    client.post("/api/nonprofit/setup-accounts")
    asset = client.post(
        "/api/accounts",
        json={"name": "Instruments", "account_number": "1550", "account_type": "asset"},
    ).json()
    line = {
        "description": "Upright piano",
        "quantity": 1,
        "fair_value": "6500",
        "debit_account_id": asset["id"],
    }
    body = {"customer_id": two_jobs["alder"], "date": "2026-04-20", "lines": [line]}
    before = _count(TestSession)
    r = client.post("/api/in-kind-gifts", json={**body, "job_id": two_jobs["roof"]})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == (
        "Grant Roof belongs to a different donor than this in-kind gift — clear "
        "the Grant field or pick one of this donor's."
    )
    r = client.post(
        "/api/in-kind-gifts",
        json={**body, "lines": [{**line, "job_id": two_jobs["roof"]}]},
    )
    assert (
        r.status_code == 400
        and "(line 1) — clear the Grant field" in r.json()["detail"]
    )
    assert _count(TestSession) == before

    r = client.post("/api/in-kind-gifts", json={**body, "job_id": two_jobs["kitchen"]})
    assert r.status_code == 201, r.text
    # the gift carries the grant, so the grant stays with its donor
    r = client.put(
        f"/api/jobs/{two_jobs['kitchen']}", json={"customer_id": two_jobs["birch"]}
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == (
        "Grant Kitchen is on 1 in-kind gift for Alder Co; move those first."
    )


# ── books from before the rule ───────────────────────────────────────────
# A document that already carries another customer's job (seeded by the old
# fixture, or entered before 2.22.0) is judged by what an edit CHANGES: a
# new customer, a new header job, a line's new job. What the edit leaves
# alone — the job sent back as stored, a note, a date, the terms — is not
# judged, so the form, which sends every field, still saves it; and a
# line's stored mismatch is cleared by sending the line without it, which
# is what the form does. The mismatch is written straight into the
# database, since the API will no longer create it.


def _stored_mismatch(db_session, model, doc_id, job_id):
    row = db_session.get(model, doc_id)
    row.job_id = job_id
    db_session.commit()


def _by_job_income(client):
    """Income by job over every date, the No job column under None."""
    r = client.get(
        "/api/reports/profit-loss-by-job?start_date=2020-01-01&end_date=2030-12-31"
        "&include_empty=true"
    )
    assert r.status_code == 200, r.text
    return {j["job_id"]: float(j["income"]) for j in r.json()["jobs"]}


def test_the_forms_save_keeps_an_invoice_with_an_old_mismatch(
    client, db_session, seed_accounts, two_jobs
):
    inv = client.post(
        "/api/invoices",
        json=_invoice_body(two_jobs["alder"], lines=[_line(), _line(rate=40)]),
    ).json()
    # the old fixture's doing: Birch's job on Alder's invoice, header and line 2
    _stored_mismatch(db_session, Invoice, inv["id"], two_jobs["roof"])
    _stored_mismatch(db_session, InvoiceLine, inv["lines"][1]["id"], two_jobs["roof"])

    # what the form sends for a note: every field as stored, the line's
    # foreign job dropped (the form knows the customer's jobs)
    r = client.put(
        f"/api/invoices/{inv['id']}",
        json={
            "customer_id": two_jobs["alder"],
            "job_id": two_jobs["roof"],
            "notes": "Paid at the counter",
            "lines": [_line(), _line(rate=40)],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == "Paid at the counter"
    assert r.json()["job_id"] == two_jobs["roof"], "the untouched header job stays"
    assert [ln["job_id"] for ln in r.json()["lines"]] == [None, None], "cleared"
    r = client.put(f"/api/invoices/{inv['id']}", json={"terms": "Net 60"})
    assert r.status_code == 200, r.text

    # a line sent back with its stored job is untouched too
    lines = client.get(f"/api/invoices/{inv['id']}").json()["lines"]
    _stored_mismatch(db_session, InvoiceLine, lines[1]["id"], two_jobs["roof"])
    r = client.put(
        f"/api/invoices/{inv['id']}",
        json={"lines": [_line(), _line(rate=40, job_id=two_jobs["roof"])]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["lines"][1]["job_id"] == two_jobs["roof"]

    # changed: a line's new job, a new line with one, another header job,
    # a customer none of them are for
    third = client.post("/api/customers", json={"name": "Cedar Co"}).json()
    patio = client.post(
        "/api/jobs", json={"customer_id": third["id"], "name": "Patio"}
    ).json()
    _refused(
        client.put(
            f"/api/invoices/{inv['id']}",
            json={"lines": [_line(job_id=patio["id"]), _line(rate=40)]},
        ),
        "invoice",
        " (line 1)",
    )
    _refused(
        client.put(
            f"/api/invoices/{inv['id']}",
            json={"lines": [_line(), _line(rate=40), _line(job_id=patio["id"])]},
        ),
        "invoice",
        " (line 3)",
    )
    _refused(
        client.put(f"/api/invoices/{inv['id']}", json={"job_id": patio["id"]}),
        "invoice",
    )
    _refused(
        client.put(f"/api/invoices/{inv['id']}", json={"customer_id": third["id"]}),
        "invoice",
    )
    # the ways out: the job cleared, or one of the customer's own
    r = client.put(f"/api/invoices/{inv['id']}", json={"job_id": None})
    assert r.status_code == 200 and r.json()["job_id"] is None, r.text
    r = client.put(f"/api/invoices/{inv['id']}", json={"job_id": two_jobs["kitchen"]})
    assert r.status_code == 200 and r.json()["job_id"] == two_jobs["kitchen"], r.text


def test_a_resent_line_keeps_a_job_some_stored_line_carried(
    client, db_session, seed_accounts, two_jobs
):
    """The skeptic's edge: a client deletes line 1 and sends old line 2
    back with its stored foreign job. No job changed, so nothing is
    judged — the resent job is one a stored line carried, whatever its
    position; a job no stored line had is judged."""
    inv = client.post(
        "/api/invoices",
        json=_invoice_body(two_jobs["alder"], lines=[_line(), _line(rate=40)]),
    ).json()
    _stored_mismatch(db_session, InvoiceLine, inv["lines"][1]["id"], two_jobs["roof"])

    # line 1 deleted, old line 2 first now, its stored job with it
    r = client.put(
        f"/api/invoices/{inv['id']}",
        json={"lines": [_line(rate=40, job_id=two_jobs["roof"])]},
    )
    assert r.status_code == 200, r.text
    assert [ln["job_id"] for ln in r.json()["lines"]] == [two_jobs["roof"]]

    # a job no stored line had is judged, wherever it lands
    third = client.post("/api/customers", json={"name": "Cedar Co"}).json()
    patio = client.post(
        "/api/jobs", json={"customer_id": third["id"], "name": "Patio"}
    ).json()
    _refused(
        client.put(
            f"/api/invoices/{inv['id']}",
            json={
                "lines": [
                    _line(rate=40, job_id=two_jobs["roof"]),
                    _line(job_id=patio["id"]),
                ]
            },
        ),
        "invoice",
        " (line 2)",
    )
    assert [
        ln["job_id"] for ln in client.get(f"/api/invoices/{inv['id']}").json()["lines"]
    ] == [two_jobs["roof"]]


def test_the_forms_save_keeps_an_estimate_with_an_old_mismatch(
    client, db_session, seed_accounts, two_jobs
):
    est = client.post(
        "/api/estimates",
        json={
            "customer_id": two_jobs["alder"],
            "date": "2026-04-04",
            "tax_rate": 0,
            "lines": [_line()],
        },
    ).json()
    _stored_mismatch(db_session, Estimate, est["id"], two_jobs["roof"])
    _stored_mismatch(db_session, EstimateLine, est["lines"][0]["id"], two_jobs["roof"])

    r = client.put(f"/api/estimates/{est['id']}", json={"notes": "Valid 30 days"})
    assert r.status_code == 200, r.text
    assert r.json()["job_id"] == two_jobs["roof"]
    # the form's save: every field as stored, its lines without jobs
    r = client.put(
        f"/api/estimates/{est['id']}",
        json={
            "customer_id": two_jobs["alder"],
            "job_id": two_jobs["roof"],
            "expiration_date": "2026-05-04",
            "lines": [_line()],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["lines"][0]["job_id"] is None, "the line's mismatch is cleared"

    third = client.post("/api/customers", json={"name": "Cedar Co"}).json()
    patio = client.post(
        "/api/jobs", json={"customer_id": third["id"], "name": "Patio"}
    ).json()
    _refused(
        client.put(f"/api/estimates/{est['id']}", json={"job_id": patio["id"]}),
        "estimate",
    )
    _refused(
        client.put(f"/api/estimates/{est['id']}", json={"customer_id": third["id"]}),
        "estimate",
    )
    # the customer the job is for makes it consistent again
    r = client.put(
        f"/api/estimates/{est['id']}", json={"customer_id": two_jobs["birch"]}
    )
    assert r.status_code == 200, r.text
    assert (r.json()["customer_id"], r.json()["job_id"]) == (
        two_jobs["birch"],
        two_jobs["roof"],
    )


def test_the_forms_save_keeps_a_schedule_with_an_old_mismatch(
    client, db_session, seed_accounts, two_jobs
):
    rec = client.post(
        "/api/recurring",
        json={
            "customer_id": two_jobs["alder"],
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "lines": [{"description": "Retainer", "quantity": 1, "rate": "100"}],
        },
    ).json()
    _stored_mismatch(db_session, RecurringInvoice, rec["id"], two_jobs["roof"])

    r = client.put(f"/api/recurring/{rec['id']}", json={"notes": "Bill on the 1st"})
    assert r.status_code == 200, r.text
    assert r.json()["job_id"] == two_jobs["roof"]
    # the form's save: the job as stored, the lines resent
    r = client.put(
        f"/api/recurring/{rec['id']}",
        json={
            "job_id": two_jobs["roof"],
            "end_date": "2026-12-01",
            "lines": [{"description": "Retainer", "quantity": 1, "rate": "120"}],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["job_id"] == two_jobs["roof"]

    r = client.put(f"/api/recurring/{rec['id']}", json={"job_id": None})
    assert r.status_code == 200 and r.json()["job_id"] is None, r.text
    # changed back to the other customer's job: refused
    _refused(
        client.put(f"/api/recurring/{rec['id']}", json={"job_id": two_jobs["roof"]}),
        "recurring invoice",
    )
    r = client.put(f"/api/recurring/{rec['id']}", json={"job_id": two_jobs["kitchen"]})
    assert r.status_code == 200 and r.json()["job_id"] == two_jobs["kitchen"], r.text


# ── copies: convert, duplicate, generate ─────────────────────────────────
# A copy of a document with an old mismatch carries the customer's jobs
# only; the foreign job is left off, never minted again, and the copy is
# never refused for it.


def test_converting_an_estimate_leaves_another_customers_job_off(
    client, db_session, seed_accounts, two_jobs
):
    est = client.post(
        "/api/estimates",
        json={
            "customer_id": two_jobs["alder"],
            "date": "2026-04-04",
            "tax_rate": 0,
            "lines": [_line(), _line(rate=40, job_id=two_jobs["kitchen"])],
        },
    ).json()
    _stored_mismatch(db_session, Estimate, est["id"], two_jobs["roof"])
    _stored_mismatch(db_session, EstimateLine, est["lines"][0]["id"], two_jobs["roof"])

    r = client.post(f"/api/estimates/{est['id']}/convert")
    assert r.status_code == 200, r.text
    inv = r.json()
    assert inv["job_id"] is None
    assert [ln["job_id"] for ln in inv["lines"]] == [None, two_jobs["kitchen"]]
    assert inv["jobs_left_off"] == ["Birch Co: Roof"]
    income = _by_job_income(client)
    assert income[two_jobs["roof"]] == 0, "nothing counted under Birch's job"
    assert income[two_jobs["kitchen"]] == 40 and income[None] == 100


def test_a_converted_estimate_posts_each_lines_job(
    client, db_session, seed_accounts, two_jobs
):
    """Convert posted the header's job only, so a line's own job counted
    under "No job" in P&L by Job; it posts through the same path as create
    and duplicate now, each income line tagged with its line's job."""
    from app.models.transactions import Transaction

    bath = client.post(
        "/api/jobs", json={"customer_id": two_jobs["alder"], "name": "Bath"}
    ).json()
    est = client.post(
        "/api/estimates",
        json={
            "customer_id": two_jobs["alder"],
            "date": "2026-04-04",
            "tax_rate": 0,
            "job_id": two_jobs["kitchen"],
            "lines": [_line(), _line(rate=40, job_id=bath["id"])],
        },
    ).json()
    before = _by_job_income(client)

    r = client.post(f"/api/estimates/{est['id']}/convert")
    assert r.status_code == 200, r.text
    inv = r.json()
    assert inv["job_id"] == two_jobs["kitchen"]
    assert [ln["job_id"] for ln in inv["lines"]] == [None, bath["id"]]
    assert inv["jobs_left_off"] == []

    txn = db_session.get(Transaction, db_session.get(Invoice, inv["id"]).transaction_id)
    assert txn.job_id == two_jobs["kitchen"], "the entry carries the header's job"
    income_lines = [ln for ln in txn.lines if ln.credit and ln.credit > 0]
    assert sorted((float(ln.credit), ln.job_id) for ln in income_lines) == [
        (40.0, bath["id"]),
        (100.0, two_jobs["kitchen"]),  # the header's job, filled in by the posting
    ]
    assert sum(float(ln.debit) for ln in txn.lines) == 140.0, "amounts unchanged"

    after = _by_job_income(client)
    assert after[bath["id"]] == before.get(bath["id"], 0) + 40, "the line's job"
    assert after[two_jobs["kitchen"]] == before.get(two_jobs["kitchen"], 0) + 100
    assert after.get(None, 0) == before.get(None, 0), "nothing extra under No job"


def test_duplicating_an_invoice_leaves_another_customers_job_off(
    client, db_session, seed_accounts, two_jobs
):
    inv = client.post(
        "/api/invoices", json=_invoice_body(two_jobs["alder"], lines=[_line()])
    ).json()
    _stored_mismatch(db_session, Invoice, inv["id"], two_jobs["roof"])
    _stored_mismatch(db_session, InvoiceLine, inv["lines"][0]["id"], two_jobs["roof"])
    counted_before = _by_job_income(client)[two_jobs["roof"]]

    r = client.post(f"/api/invoices/{inv['id']}/duplicate")
    assert r.status_code == 201, r.text
    copy = r.json()
    assert copy["job_id"] is None and copy["lines"][0]["job_id"] is None
    assert copy["jobs_left_off"] == ["Birch Co: Roof"]
    # an invoice carrying no foreign job: a plain copy, nothing left off
    assert (
        client.post(f"/api/invoices/{copy['id']}/duplicate").json()["jobs_left_off"]
        == []
    )
    assert (
        _by_job_income(client)[two_jobs["roof"]] == counted_before
    ), "the copy added nothing under Birch's job"


def test_a_generated_invoice_leaves_another_customers_job_off(
    client, db_session, seed_accounts, two_jobs, caplog
):
    rec = client.post(
        "/api/recurring",
        json={
            "customer_id": two_jobs["alder"],
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "lines": [{"description": "Retainer", "quantity": 1, "rate": "100"}],
        },
    ).json()
    _stored_mismatch(db_session, RecurringInvoice, rec["id"], two_jobs["roof"])

    with caplog.at_level("WARNING", logger="app.services.recurring_service"):
        r = client.post("/api/recurring/generate?as_of=2026-01-01")
    assert r.status_code == 200, r.text
    assert r.json()["invoices_created"] == 1
    made = client.get(f"/api/invoices/{r.json()['invoice_ids'][0]}").json()
    assert made["recurring_invoice_id"] == rec["id"] and made["job_id"] is None
    assert any(
        "Birch Co: Roof" in m and "left off" in m for m in caplog.messages
    ), caplog.messages
    assert _by_job_income(client)[two_jobs["roof"]] == 0


# ── moving a job to another customer ─────────────────────────────────────


def test_a_job_moves_only_while_nothing_carries_it(client, seed_accounts, two_jobs):
    kitchen, alder, birch = two_jobs["kitchen"], two_jobs["alder"], two_jobs["birch"]
    inv = client.post("/api/invoices", json=_invoice_body(alder, job_id=kitchen)).json()
    client.post(
        "/api/sales-receipts",
        json={
            "customer_id": alder,
            "date": "2026-04-03",
            "method": "card",
            "job_id": kitchen,
            "lines": [_line()],
        },
    )
    client.post(
        "/api/credit-memos",
        json={
            "customer_id": alder,
            "date": "2026-04-02",
            "job_id": kitchen,
            "lines": [{"description": "Credit", "quantity": 1, "rate": 50}],
        },
    )
    client.post(
        "/api/estimates",
        json={
            "customer_id": alder,
            "date": "2026-04-04",
            "tax_rate": 0,
            "lines": [_line(job_id=kitchen)],  # on a line only
        },
    )
    client.post(
        "/api/recurring",
        json={
            "customer_id": alder,
            "frequency": "monthly",
            "start_date": "2026-01-01",
            "job_id": kitchen,
            "lines": [{"description": "Retainer", "quantity": 1, "rate": "100"}],
        },
    )
    r = client.put(f"/api/jobs/{kitchen}", json={"customer_id": birch})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == (
        "Job Kitchen is on 1 invoice, 1 sales receipt, 1 credit memo, 1 estimate "
        "and 1 recurring invoice for Alder Co; move those first."
    )
    assert client.get(f"/api/jobs/{kitchen}").json()["customer_id"] == alder

    # a void document can't be moved, so it isn't counted
    assert client.post(f"/api/invoices/{inv['id']}/void").status_code == 200
    r = client.put(f"/api/jobs/{kitchen}", json={"customer_id": birch})
    assert r.json()["detail"].startswith("Job Kitchen is on 1 sales receipt, ")

    # the same customer, or a rename, is not a move
    r = client.put(
        f"/api/jobs/{kitchen}", json={"customer_id": alder, "name": "Kitchen remodel"}
    )
    assert r.status_code == 200, r.text

    # a job nothing carries still moves
    patio = client.post(
        "/api/jobs", json={"customer_id": alder, "name": "Patio"}
    ).json()
    r = client.put(f"/api/jobs/{patio['id']}", json={"customer_id": birch})
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Birch Co: Patio"
