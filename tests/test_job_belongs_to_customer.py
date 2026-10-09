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
is 404. Deposits, bank entries, bills, time entries and journal entries
carry a job with no customer, so they are not in this rule."""

import pytest

from app.models.contacts import Customer
from app.models.credit_memos import CreditMemo
from app.models.estimates import Estimate
from app.models.in_kind import InKindGift
from app.models.invoices import Invoice
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


def _refused(resp, document, where=""):
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert REFUSED in detail and detail.endswith(
        f"than this {document}{where}."
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
        "Job Roof belongs to a different customer than this invoice."
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
        "Grant Roof belongs to a different donor than this pledge."
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
        "Grant Roof belongs to a different donor than this in-kind gift."
    )
    r = client.post(
        "/api/in-kind-gifts",
        json={**body, "lines": [{**line, "job_id": two_jobs["roof"]}]},
    )
    assert r.status_code == 400 and r.json()["detail"].endswith("(line 1).")
    assert _count(TestSession) == before

    r = client.post("/api/in-kind-gifts", json={**body, "job_id": two_jobs["kitchen"]})
    assert r.status_code == 201, r.text
