from datetime import date as dt_date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator

from app.schemas.common import (
    StrictModel,
    TaxRateFloat,
    TaxRateOut,
    validate_non_negative_line,
)
from app.schemas.invoices import RateOut


class BillLineCreate(StrictModel):
    item_id: Optional[int] = None
    account_id: Optional[int] = None
    job_id: Optional[int] = None
    class_id: Optional[int] = None
    cost_code_id: Optional[int] = None
    function: Optional[str] = None
    is_billable: bool = False
    description: Optional[str] = None
    quantity: float = 1
    rate: float = 0
    line_order: int = 0

    @model_validator(mode="after")
    def _check_non_negative(self):
        validate_non_negative_line(self.quantity, self.rate)
        return self


class BillLineResponse(BaseModel):
    id: int
    item_id: Optional[int] = None
    account_id: Optional[int] = None
    job_id: Optional[int] = None
    class_id: Optional[int] = None
    cost_code_id: Optional[int] = None
    function: Optional[str] = None
    is_billable: bool = False
    description: Optional[str] = None
    quantity: Decimal = Decimal("0")
    rate: RateOut = Decimal("0")
    amount: Decimal = Decimal("0")
    line_order: int = 0
    model_config = {"from_attributes": True}


class BillCreate(StrictModel):
    vendor_id: int
    # The vendor's invoice number; blank → generated (date + vendor initials).
    bill_number: Optional[str] = None
    date: dt_date
    due_date: Optional[dt_date] = None
    terms: str = "Net 30"
    ref_number: Optional[str] = None
    po_id: Optional[int] = None
    tax_rate: TaxRateFloat = 0
    notes: Optional[str] = None
    class_id: Optional[int] = None
    job_id: Optional[int] = None
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    lines: list[BillLineCreate] = []

    @field_validator("lines")
    @classmethod
    def _require_lines(cls, v):
        if not v:
            raise ValueError("bill must have at least one line")
        return v


class BillUpdate(StrictModel):
    """An edit of a posted bill (#225): whatever is sent changes, the rest
    stays. Lines, when sent, replace the bill's lines."""

    vendor_id: Optional[int] = None
    bill_number: Optional[str] = None
    date: Optional[dt_date] = None
    due_date: Optional[dt_date] = None
    terms: Optional[str] = None
    ref_number: Optional[str] = None
    tax_rate: Optional[TaxRateFloat] = None
    notes: Optional[str] = None
    class_id: Optional[int] = None
    job_id: Optional[int] = None
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    lines: Optional[list[BillLineCreate]] = None


class BillResponse(BaseModel):
    id: int
    bill_number: str
    vendor_id: int
    vendor_name: Optional[str] = None
    status: str
    po_id: Optional[int] = None
    date: dt_date
    due_date: Optional[dt_date] = None
    terms: Optional[str] = None
    ref_number: Optional[str] = None
    subtotal: Decimal = Decimal("0")
    tax_rate: TaxRateOut = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    amount_paid: Decimal = Decimal("0")
    balance_due: Decimal = Decimal("0")
    notes: Optional[str] = None
    class_id: Optional[int] = None
    job_id: Optional[int] = None
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    lines: list[BillLineResponse] = []
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class BillPaymentAllocationCreate(StrictModel):
    bill_id: int
    amount: float


class BillPaymentCreate(StrictModel):
    vendor_id: int
    date: dt_date
    amount: float
    method: Optional[str] = None
    check_number: Optional[str] = None
    pay_from_account_id: Optional[int] = None
    notes: Optional[str] = None
    # No class_id or job_id (v2.22.0, #234): the schema accepted both and the
    # route dropped them — BillPayment has no column and the payment's
    # journal never carried them — so a client that sent one was told
    # nothing. Nothing sends them (Pay Bills offers neither), and a body
    # that does is now refused like any other unknown field.
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    allocations: list[BillPaymentAllocationCreate] = []


class BillPaymentAllocationResponse(BaseModel):
    bill_id: int
    amount: Decimal = Decimal("0")
    model_config = {"from_attributes": True}


class BillPaymentResponse(BaseModel):
    id: int
    vendor_id: int
    vendor_name: Optional[str] = None
    date: dt_date
    amount: Decimal = Decimal("0")
    method: Optional[str] = None
    check_number: Optional[str] = None
    notes: Optional[str] = None
    currency: Optional[str] = None
    exchange_rate: Optional[Decimal] = None
    is_voided: bool = False
    created_at: Optional[datetime] = None
    # Which bills this payment paid, and how much of each — the bill's view
    # lists its payments from here so one can be voided on screen.
    allocations: list[BillPaymentAllocationResponse] = []
    model_config = {"from_attributes": True}
