# ============================================================================
# Job dimension helpers — Customer:Job name handling, strict lookup, and the
# profitability aggregation every job report and the job detail share.
# ============================================================================

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from app.models.accounts import Account, AccountType
from app.models.contacts import Customer
from app.models.jobs import Job
from app.models.transactions import Transaction, TransactionLine
from app.services.terminology import Terms, terms_from_db

NO_JOB_LABEL = "No job"


def split_customer_job(name: str) -> tuple[str, Optional[str]]:
    """QuickBooks' "Customer:Job" → ("Customer", "Job").

    Only the first colon splits; a Desktop sub-job "A:B:C" becomes job
    "B:C" under customer "A" — one level of flattening is honest, and
    sub-jobs are rare. No colon → (name, None).
    """
    raw = (name or "").strip()
    if ":" not in raw:
        return raw, None
    cust, job = raw.split(":", 1)
    cust, job = cust.strip(), job.strip()
    if not cust or not job:
        return raw, None
    return cust, job


def find_customer(db: Session, name: str) -> Optional[Customer]:
    """Exact, then in any case, as find_job does: an import that spells a
    customer BOB JONES means the Bob Jones already on file (#195)."""
    if not name:
        return None
    row = db.query(Customer).filter(Customer.name == name).first()
    if not row:
        row = (
            db.query(Customer)
            .filter(sqlfunc.lower(Customer.name) == name.lower())
            .order_by(Customer.id)
            .first()
        )
    return row


def find_job(db: Session, customer_id: int, name: str) -> Optional[Job]:
    """Exact, then case-insensitive match within one customer."""
    if not name:
        return None
    row = db.query(Job).filter(Job.customer_id == customer_id, Job.name == name).first()
    if not row:
        row = (
            db.query(Job)
            .filter(Job.customer_id == customer_id, Job.name.ilike(name))
            .first()
        )
    return row


def get_or_create_job(db: Session, customer_id: int, name: str) -> Job:
    row = find_job(db, customer_id, name)
    if row:
        return row
    row = Job(customer_id=customer_id, name=name.strip()[:200])
    db.add(row)
    db.flush()
    return row


def resolve_customer_and_job(
    db: Session, full_name: str, create: bool = True
) -> tuple[Optional[Customer], Optional[Job]]:
    """Resolve an imported "Customer:Job" name to (customer, job).

    A flat customer literally named "A:B" that already exists keeps
    matching (re-imports of pre-jobs files stay stable); otherwise the
    name splits, the customer is found or created, and the job is found
    or created under it. `create=False` only looks up.
    """
    raw = (full_name or "").strip()
    if not raw:
        return None, None
    flat = find_customer(db, raw)
    if flat:
        return flat, None
    cust_name, job_name = split_customer_job(raw)
    customer = find_customer(db, cust_name)
    if not customer:
        if not create:
            return None, None
        customer = Customer(name=cust_name[:200], is_active=True)
        db.add(customer)
        db.flush()
    if not job_name:
        return customer, None
    job = find_job(db, customer.id, job_name)
    if not job and create:
        job = get_or_create_job(db, customer.id, job_name)
    return customer, job


def _refuse_foreign_jobs(db: Session, customer_id: int, checks, document, t) -> None:
    """`checks` are (job_id, where) pairs: each job must exist (404) and be
    the customer's (400, with the way out named)."""
    for wanted, where in checks:
        if wanted is None:
            continue
        job = db.get(Job, wanted)
        if job is None:
            raise HTTPException(status_code=404, detail=f"{t('Job')} not found")
        if job.customer_id != customer_id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{t('Job')} {job.name} belongs to a different {t('customer')} "
                    f"than this {document}{where} — clear the {t('Job')} field or "
                    f"pick one of this {t('customer')}'s."
                ),
            )


def refuse_other_customers_jobs(
    db: Session,
    customer_id: int,
    job_id: Optional[int],
    lines=(),
    document: str = "invoice",
    terms: Optional[Terms] = None,
) -> None:
    """A customer document carries its own customer's jobs only: the job on
    its header and the job on each of its lines.

    An invoice could be saved with another customer's job (2.22.0 gate,
    NEW-36): the form hid other customers' jobs on the hidden select's
    focus, which the type-ahead in front of it never gives it, and the API
    checked nothing, so P&L by Job, the job page and Job Profitability
    counted the invoice under a job that was not the customer's. Refused
    with 400 the way a payment to another customer's invoice is (#189); a
    job that does not exist is 404.

    `lines` are the request's line models or the stored rows, either with
    a job_id; `document` is the document's name for the message, in the
    company's own words ("pledge", "donation" for a nonprofit).
    """
    t = terms or terms_from_db(db)
    checks = [(job_id, "")]
    checks += [
        (getattr(line, "job_id", None), f" (line {n})")
        for n, line in enumerate(lines, start=1)
    ]
    _refuse_foreign_jobs(db, customer_id, checks, document, t)


def refuse_other_customers_jobs_on_edit(
    db: Session,
    row,
    changes: dict,
    lines=None,
    document: str = "invoice",
    terms: Optional[Terms] = None,
) -> None:
    """What an edit CHANGES must leave the document on its customer's jobs;
    what it leaves alone is not judged.

    A new customer: every job the document has after the edit is theirs.
    A new header job: that job. A line's new job — one no stored line of
    the document carried — that job. A resent line with a job some stored
    line carried (its own, or another line's: a client that deletes line
    1 and sends old line 2 back changed no job), a header job sent
    unchanged, a note, a date: nothing to judge — so a document carrying a
    mismatch from before the rule (books the old fixture seeded) still
    saves from the form, which always sends every field, and a line's
    stored mismatch is cleared by sending the line without it.

    `row` is the stored document (customer_id, job_id, lines), `changes`
    the edit's set fields, `lines` the resent lines or None.
    """
    t = terms or terms_from_db(db)
    customer_after = changes.get("customer_id") or row.customer_id
    header_after = changes["job_id"] if "job_id" in changes else row.job_id
    if customer_after != row.customer_id:
        lines_after = lines if lines is not None else list(row.lines)
        refuse_other_customers_jobs(
            db, customer_after, header_after, lines_after, document, t
        )
        return
    checks = []
    if "job_id" in changes and changes["job_id"] != row.job_id:
        checks.append((changes["job_id"], ""))
    if lines is not None:
        carried = {ln.job_id for ln in row.lines if ln.job_id is not None}
        for n, line in enumerate(lines, start=1):
            after = getattr(line, "job_id", None)
            if after is not None and after not in carried:
                checks.append((after, f" (line {n})"))
    _refuse_foreign_jobs(db, customer_after, checks, document, t)


def own_job(
    db: Session, customer_id: int, job_id: Optional[int], left_off: list
) -> Optional[int]:
    """The job, if it is the customer's; else None, and the job's name goes
    on `left_off`. A copy of a document — an estimate converted, an invoice
    duplicated, a scheduled invoice generated — carries only the customer's
    jobs: a job of another customer stored on the original (books from
    before the rule) is left off the copy rather than minted again, and
    the copy is never refused for it."""
    if job_id is None:
        return None
    job = db.get(Job, job_id)
    if job is not None and job.customer_id == customer_id:
        return job_id
    name = job.full_name if job is not None else f"#{job_id}"
    if name not in left_off:
        left_off.append(name)
    return None


def documents_carrying_job(db: Session, job_id: int, t: Terms) -> list[tuple[str, int]]:
    """How many live customer documents carry the job, on their header or
    a line, by the noun each document is refused with (document_label's:
    invoice / pledge / sales receipt / donation receipt; credit memo;
    estimate; recurring invoice / pledge; in-kind gift), in the order a
    person reads them. Void ones are left out: they cannot be edited, so
    they could never be moved."""
    from sqlalchemy import or_

    from app.models.credit_memos import CreditMemo, CreditMemoStatus
    from app.models.estimates import Estimate, EstimateLine
    from app.models.in_kind import InKindGift, InKindGiftLine
    from app.models.invoices import Invoice, InvoiceLine, InvoiceStatus
    from app.models.recurring import RecurringInvoice
    from app.services.donor_documents import document_label

    on_invoice_line = db.query(InvoiceLine.invoice_id).filter(
        InvoiceLine.job_id == job_id
    )
    live_invoices = (
        db.query(Invoice)
        .filter(
            or_(Invoice.job_id == job_id, Invoice.id.in_(on_invoice_line)),
            Invoice.status != InvoiceStatus.VOID,
        )
        .all()
    )
    on_estimate_line = db.query(EstimateLine.estimate_id).filter(
        EstimateLine.job_id == job_id
    )
    on_gift_line = db.query(InKindGiftLine.gift_id).filter(
        InKindGiftLine.job_id == job_id
    )
    counts: dict[str, int] = {}
    for inv in live_invoices:
        noun = document_label(inv, t).lower()
        counts[noun] = counts.get(noun, 0) + 1
    counts["credit memo"] = (
        db.query(CreditMemo)
        .filter(CreditMemo.job_id == job_id, CreditMemo.status != CreditMemoStatus.VOID)
        .count()
    )
    counts["estimate"] = (
        db.query(Estimate)
        .filter(or_(Estimate.job_id == job_id, Estimate.id.in_(on_estimate_line)))
        .count()
    )
    counts["recurring " + t("invoice")] = (
        db.query(RecurringInvoice).filter(RecurringInvoice.job_id == job_id).count()
    )
    counts["in-kind gift"] = (
        db.query(InKindGift)
        .filter(
            or_(InKindGift.job_id == job_id, InKindGift.id.in_(on_gift_line)),
            InKindGift.status != "void",
        )
        .count()
    )
    order = (
        "invoice",
        "pledge",
        "sales receipt",
        "donation receipt",
        "credit memo",
        "estimate",
        "recurring " + t("invoice"),
        "in-kind gift",
    )
    return [(noun, counts.get(noun, 0)) for noun in order]


def refuse_moving_a_carried_job(db: Session, job: Job, terms=None) -> None:
    """A job moves to another customer only while no customer document
    carries it: moving it would put those documents on another customer's
    job, which the rule above refuses to create. 400, naming what carries
    it by the noun each is refused with ("1 pledge and 2 donation
    receipts"); a job with no documents still moves."""
    t = terms or terms_from_db(db)
    carried = [(noun, n) for noun, n in documents_carrying_job(db, job.id, t) if n]
    if not carried:
        return
    parts = [f"{n} {noun}{'' if n == 1 else 's'}" for noun, n in carried]
    listed = (
        parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    )
    who = job.customer.name if job.customer else f"its {t('customer')}"
    raise HTTPException(
        status_code=400,
        detail=f"{t('Job')} {job.name} is on {listed} for {who}; move those first.",
    )


def job_attribution():
    """SQL expression for the job a posted line belongs to: the line's own
    job, else the transaction header's. Reports group on this so header-
    tagged and line-tagged documents reconcile identically."""
    return sqlfunc.coalesce(TransactionLine.job_id, Transaction.job_id)


def job_profitability(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    job_ids: Optional[list[int]] = None,
    customer_id: Optional[int] = None,
    include_no_job: bool = True,
) -> list[dict]:
    """Income / COGS / expenses per job from posted lines.

    Untagged activity lands in the "No job" bucket (job_id None) so the
    report's totals equal the plain P&L for the same period.
    """
    # The untagged bucket is labelled in the business word; a nonprofit's
    # report reads "No grant" (vocabulary audit, 2.13.x).
    from app.services.terminology import terms_from_db

    no_job_label = terms_from_db(db).text(NO_JOB_LABEL)
    pl_types = (AccountType.INCOME, AccountType.COGS, AccountType.EXPENSE)
    attributed = job_attribution().label("job")
    q = (
        db.query(
            attributed,
            Account.account_type,
            sqlfunc.coalesce(sqlfunc.sum(TransactionLine.debit), 0),
            sqlfunc.coalesce(sqlfunc.sum(TransactionLine.credit), 0),
        )
        .select_from(TransactionLine)
        .join(Transaction, TransactionLine.transaction_id == Transaction.id)
        .join(Account, TransactionLine.account_id == Account.id)
        .filter(Account.account_type.in_(pl_types))
    )
    if start_date:
        q = q.filter(Transaction.date >= start_date)
    if end_date:
        q = q.filter(Transaction.date <= end_date)
    if job_ids is not None:
        q = q.filter(job_attribution().in_(job_ids))
    rows = q.group_by("job", Account.account_type).all()

    jobs = {j.id: j for j in db.query(Job).all()}
    customers = {c.id: c.name for c in db.query(Customer).all()}
    buckets: dict[Optional[int], dict] = {}
    for job_id, acct_type, dr, cr in rows:
        job = jobs.get(job_id)
        if customer_id is not None and (job is None or job.customer_id != customer_id):
            continue
        if job_id is None and not include_no_job:
            continue
        b = buckets.setdefault(
            job_id,
            {
                "job_id": job_id,
                "job_name": job.name if job else no_job_label,
                "customer_id": job.customer_id if job else None,
                "customer_name": customers.get(job.customer_id, "") if job else "",
                "status": job.status if job else None,
                "contract_amount": (
                    float(job.contract_amount) if job and job.contract_amount else None
                ),
                "income": Decimal("0"),
                "cogs": Decimal("0"),
                "expenses": Decimal("0"),
            },
        )
        dr, cr = Decimal(str(dr)), Decimal(str(cr))
        if acct_type == AccountType.INCOME:
            b["income"] += cr - dr
        elif acct_type == AccountType.COGS:
            b["cogs"] += dr - cr
        else:
            b["expenses"] += dr - cr

    out = []
    for b in sorted(
        buckets.values(),
        key=lambda x: (
            x["job_id"] is not None,
            x["customer_name"].lower(),
            x["job_name"].lower(),
        ),
    ):
        income, cogs, expenses = b["income"], b["cogs"], b["expenses"]
        costs = cogs + expenses
        net = income - costs
        b.update(
            {
                "income": float(income),
                "cogs": float(cogs),
                "expenses": float(expenses),
                "total_costs": float(costs),
                "gross_profit": float(income - cogs),
                "net_income": float(net),
                "margin_pct": (float(net / income * 100) if income else None),
            }
        )
        out.append(b)
    return out


def job_transactions(
    db: Session,
    job_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> list[dict]:
    """Every posted P&L line attributed to the job — the job cost detail."""
    pl_types = (AccountType.INCOME, AccountType.COGS, AccountType.EXPENSE)
    q = (
        db.query(TransactionLine, Transaction, Account)
        .join(Transaction, TransactionLine.transaction_id == Transaction.id)
        .join(Account, TransactionLine.account_id == Account.id)
        .filter(job_attribution() == job_id, Account.account_type.in_(pl_types))
    )
    if start_date:
        q = q.filter(Transaction.date >= start_date)
    if end_date:
        q = q.filter(Transaction.date <= end_date)
    rows = q.order_by(Transaction.date, Transaction.id, TransactionLine.id).all()
    out = []
    for line, txn, acct in rows:
        if acct.account_type == AccountType.INCOME:
            kind, amount = "income", Decimal(str(line.credit)) - Decimal(
                str(line.debit)
            )
        else:
            kind, amount = "cost", Decimal(str(line.debit)) - Decimal(str(line.credit))
        out.append(
            {
                "transaction_id": txn.id,
                "date": txn.date.isoformat(),
                "source_type": txn.source_type,
                "source_id": txn.source_id,
                "reference": txn.reference,
                "description": line.description or txn.description or "",
                "account_id": acct.id,
                "account_name": acct.name,
                "account_type": acct.account_type.value,
                "kind": kind,
                "amount": float(amount),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Milestone 2: cost codes and committed cost
# ---------------------------------------------------------------------------


def committed_cost(
    db: Session, job_ids: Optional[list[int]] = None
) -> dict[int, float]:
    """Open purchase-order value per job: ordered but not yet billed.

    A PO is committed once it has left draft and until it is closed
    (conversion to a bill closes it, moving the cost into the ledger). A
    line's job is its own, else the PO header's."""
    from app.models.purchase_orders import POStatus, PurchaseOrder, PurchaseOrderLine

    line_job = sqlfunc.coalesce(PurchaseOrderLine.job_id, PurchaseOrder.job_id)
    q = (
        db.query(
            line_job.label("job"),
            sqlfunc.coalesce(sqlfunc.sum(PurchaseOrderLine.amount), 0),
        )
        .select_from(PurchaseOrderLine)
        .join(PurchaseOrder, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
        .filter(
            PurchaseOrder.status.in_(
                (POStatus.SENT, POStatus.PARTIAL, POStatus.RECEIVED)
            ),
            line_job.isnot(None),
        )
    )
    if job_ids is not None:
        q = q.filter(line_job.in_(job_ids))
    return {int(j): float(v) for j, v in q.group_by("job").all()}
