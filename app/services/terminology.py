"""Terminology — the words a company sees, decided by Settings -> company_type.

A nonprofit never sells anything, so "Customer", "Invoice", "Sales Receipt"
and "Profit & Loss" are wrong on every screen and every printed page.
Instead of a second set of pages, one dictionary swaps the visible words
at render time: Customer -> Donor, Invoice -> Pledge, Class -> Fund, Profit
& Loss -> Statement of Activities. Nothing in the API, the database or the
export formats changes name; a business company sees no difference.

This is the server twin of ``app/static/js/terms.js`` — the two
dictionaries must agree (``tests/test_terminology.py`` checks). Keys are
ALWAYS the business words. Bare "Sales", "Vendor", "Bill", "Estimate" and
"Payment" are deliberately not keys: phrases carry the swap, so "Sales Tax"
can never become "Contributions Tax".
"""

from __future__ import annotations

import re

NONPROFIT: dict[str, str] = {
    # people
    "Customer": "Donor",
    "Customers": "Donors",
    "Customer Center": "Donor Center",
    "New Customer": "New Donor",
    "Active Customers": "Active Donors",
    "Customer Statement": "Donor Statement",
    "Customers & Sales": "Donors & Contributions",
    "Income by Customer": "Contributions by Donor",
    # documents
    "Invoice": "Pledge",
    "Invoices": "Pledges",
    "Create Invoice": "Create Pledge",
    "Create Invoices": "Create Pledges",
    "New Invoice": "New Pledge",
    "Recurring Invoices": "Recurring Pledges",
    "Overdue Invoices": "Overdue Pledges",
    "Recent Invoices": "Recent Pledges",
    "Total Invoiced": "Total Pledged",
    "Sales Receipt": "Donation",
    "Sales Receipts": "Donations",
    "Enter Sales Receipts": "Enter Donations",
    # ledger
    "Income": "Revenue & Support",
    "Total Income": "Total Revenue & Support",
    "Net Income": "Change in Net Assets",
    "Equity": "Net Assets",
    "Total Equity": "Total Net Assets",
    "Liabilities + Equity": "Liabilities + Net Assets",
    "Profit & Loss": "Statement of Activities",
    "P&L": "Activities",
    "P&L by Class": "Activities by Fund",
    "P&L: This Month vs Last": "Activities: This Month vs Last",
    "P&L: Year to Date": "Activities: Year to Date",
    "Balance Sheet": "Statement of Financial Position",
    "Balance Sheet Trend": "Statement of Financial Position Trend",
    "Class": "Fund",
    "Classes": "Funds",
    # grants
    "Job": "Grant",
    "Jobs": "Grants",
    "Job Costs": "Grant Costs",
    "Job Cost Entries": "Grant Cost Entries",
    "Job Cost Entry": "Grant Cost Entry",
    "Job Budget vs Actual": "Grant Budget vs Actual",
    "Jobs: Budget vs Actual": "Grants: Budget vs Actual",
    "Job Profitability": "Grant Income & Costs",
    # receivables
    "Total Receivables": "Pledges Receivable",
    "A/R Aging": "Pledge Aging",
    "Accounts Receivable Aging": "Pledges Receivable Aging",
    "Monthly Revenue": "Monthly Revenue & Support",
    "Receivables": "Pledges Receivable",
    "Revenue by Customer": "Revenue & Support by Donor",
}

# Words that must never be mapped, whole or as a phrase start.
PROTECTED_WORDS = ("Sales", "Sales Tax", "Vendor", "Bill", "Estimate", "Payment")

MODES = ("business", "nonprofit")

_WORD_RE = re.compile(
    r"\b("
    + "|".join(re.escape(k) for k in sorted(NONPROFIT, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)


class Terms:
    """Callable dictionary: ``t("Invoice") -> "Pledge"`` in nonprofit mode,
    the key itself otherwise. Plurals and lowercase forms of known keys
    resolve too, so ``t("invoices") -> "pledges"``."""

    def __init__(self, mode: str = "business"):
        self.mode = mode if mode in MODES else "business"

    @property
    def is_nonprofit(self) -> bool:
        return self.mode == "nonprofit"

    def __call__(self, key: str) -> str:
        if not self.is_nonprofit or not key:
            return key
        d = NONPROFIT
        if key in d:
            return d[key]
        if key.endswith("s") and key[:-1] in d:
            return d[key[:-1]] + "s"
        cap = key[0].upper() + key[1:]
        if cap != key and (cap in d or (cap.endswith("s") and cap[:-1] in d)):
            return self(cap).lower()
        return key

    def text(self, s: str) -> str:
        """Prose helper: swap every whole-word key inside a sentence,
        keeping the case of what was matched."""
        if not self.is_nonprofit or not s:
            return s

        def _swap(m: re.Match) -> str:
            found = m.group(0)
            exact = next((k for k in NONPROFIT if k.lower() == found.lower()), None)
            out = NONPROFIT[exact] if exact else found
            # "P&L" and "A/R" are upper-case as keys; matching them is
            # not a shouted sentence, so "P&L analysis" must not become
            # "ACTIVITIES analysis".
            if found.isupper() and not (exact or "").isupper():
                return out.upper()
            if found[0].islower():
                # a lower-case word in running text takes a lower-case phrase:
                # "equity" -> "net assets", not "net Assets" (2.16.0 gate). An
                # acronym inside the replacement keeps its capitals.
                return " ".join(
                    w if (w.isupper() and len(w) > 1) else w.lower()
                    for w in out.split(" ")
                )
            return out

        return _WORD_RE.sub(_swap, s)

    def slug(self, key: str) -> str:
        """Filename form: ``profit-loss`` / ``statement-of-activities``."""
        return re.sub(r"[^a-z0-9]+", "-", self(key).lower()).strip("-")

    def compact(self, key: str) -> str:
        """CamelCase form for document filenames: ``SalesReceipt`` / ``Donation``."""
        return re.sub(r"\W", "", self(key))


def document_reference(face: str, number, name: str | None = None) -> str:
    """The text a posting writes for itself — "Invoice #1081 - Boise Neon
    Supply", "Pledge #1081 - Grant Foundation" — from the document's own
    face (donor_documents.document_label), never from the company's
    vocabulary: a nonprofit's program-fee invoice stays an Invoice in its
    ledger because it prints as one.

    DISPLAY text, written once at posting time and never parsed: the
    ledger keys documents by source_type and source_id, and the payment
    providers by their own ids and metadata. History keeps the words in
    use when it was posted; nothing rewrites it.
    """
    ref = f"{face} #{number}"
    return f"{ref} - {name}" if name else ref


def terms_for(settings: dict | None) -> Terms:
    """Build from a settings dict (``get_all_settings``)."""
    return Terms((settings or {}).get("company_type", "business"))


def terms_from_db(db) -> Terms:
    from app.services.settings_service import get_setting_raw

    return Terms(get_setting_raw(db, "company_type") or "business")
