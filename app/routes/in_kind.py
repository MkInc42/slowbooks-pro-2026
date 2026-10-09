"""In-kind gifts — donated property, posted two-sided and acknowledged
without a stated value."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.contacts import Customer
from app.models.in_kind import InKindGift, InKindGiftLine
from app.schemas.in_kind import InKindGiftCreate, InKindGiftResponse, InKindLineResponse
from app.services.closing_date import check_closing_date
from app.services.jobs_service import refuse_other_customers_jobs
from app.services.in_kind import (
    build_lines,
    next_in_kind_number,
    post_in_kind_gift,
    void_in_kind_gift,
)

router = APIRouter(prefix="/api/in-kind-gifts", tags=["in-kind-gifts"])


def _response(gift: InKindGift) -> InKindGiftResponse:
    data = InKindGiftResponse.model_validate(gift)
    data.customer_name = gift.customer.name if gift.customer else None
    data.class_name = gift.fund.name if gift.fund else None
    data.lines = []
    for ln in gift.lines:
        lr = InKindLineResponse.model_validate(ln)
        lr.debit_account_name = ln.debit_account.name if ln.debit_account else None
        lr.credit_account_name = ln.credit_account.name if ln.credit_account else None
        data.lines.append(lr)
    return data


def _query(db: Session):
    return db.query(InKindGift).options(
        joinedload(InKindGift.customer),
        joinedload(InKindGift.fund),
        joinedload(InKindGift.lines).joinedload(InKindGiftLine.debit_account),
        joinedload(InKindGift.lines).joinedload(InKindGiftLine.credit_account),
    )


def _get(db: Session, gift_id: int) -> InKindGift:
    gift = _query(db).filter(InKindGift.id == gift_id).first()
    if not gift:
        raise HTTPException(status_code=404, detail="In-kind gift not found")
    return gift


@router.get("", response_model=list[InKindGiftResponse])
def list_in_kind_gifts(
    customer_id: Optional[int] = None,
    status: Optional[str] = None,
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = _query(db)
    if customer_id is not None:
        q = q.filter(InKindGift.customer_id == customer_id)
    if status:
        q = q.filter(InKindGift.status == status)
    if start_date:
        q = q.filter(InKindGift.date >= start_date)
    if end_date:
        q = q.filter(InKindGift.date <= end_date)
    return [
        _response(g)
        for g in q.order_by(InKindGift.date.desc(), InKindGift.id.desc()).all()
    ]


@router.get("/{gift_id}", response_model=InKindGiftResponse)
def get_in_kind_gift(gift_id: int, db: Session = Depends(get_db)):
    return _response(_get(db, gift_id))


@router.post("", response_model=InKindGiftResponse, status_code=201)
def create_in_kind_gift(data: InKindGiftCreate, db: Session = Depends(get_db)):
    check_closing_date(db, data.date)
    if not db.get(Customer, data.customer_id):
        raise HTTPException(status_code=404, detail="Donor not found")
    # The job (grant), on the header or a line, is this donor's (NEW-36).
    refuse_other_customers_jobs(
        db, data.customer_id, data.job_id, data.lines, "in-kind gift"
    )
    gift = InKindGift(
        number=next_in_kind_number(db),
        customer_id=data.customer_id,
        date=data.date,
        memo=data.memo,
        class_id=data.class_id,
        job_id=data.job_id,
        status="posted",
    )
    db.add(gift)
    try:
        gift.total = build_lines(db, gift, data.lines)
        db.flush()
        post_in_kind_gift(db, gift)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return _response(_get(db, gift.id))


@router.post("/{gift_id}/void", response_model=InKindGiftResponse)
def void_in_kind_gift_route(gift_id: int, db: Session = Depends(get_db)):
    gift = _get(db, gift_id)
    check_closing_date(db, gift.date)
    try:
        void_in_kind_gift(db, gift)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return _response(_get(db, gift.id))
