"""Spreadsheet and printable exports of the core ledger reports (#179).

One layout per report, the same columns as the screen, with a short
preamble (company, report, period) so a file saved from one company can be
read without the program — and, later, fed to group reporting (#180), which
reads one trial balance per company. The preamble is always four lines
(three labelled rows and a blank) so a reader can skip it by count.

Amounts are written with two decimals and no currency sign or thousands
separator, so a spreadsheet reads them as numbers.
"""

from __future__ import annotations

import csv
import io
from decimal import ROUND_HALF_UP, Decimal

from app.services.csv_export import _SafeWriter


def _money(v) -> Decimal:
    # A Decimal, not a string: the safe writer only guards text cells, so a
    # negative amount stays a number in the spreadsheet instead of "'-300.00".
    return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _preamble(writer, company: str, report: str, period: str) -> None:
    writer.writerow(["Company", company])
    writer.writerow(["Report", report])
    writer.writerow(["Period", period])
    writer.writerow([])


def trial_balance_csv(data: dict, company: str) -> str:
    """Account number | Account name | Type | Debit | Credit | Net, one row
    per account with activity, then a totals row where Debit equals Credit.
    Net is debit minus credit, as the screen shows it."""
    out = io.StringIO()
    w = _SafeWriter(out)
    _preamble(
        w, company, "Trial Balance", f"{data['start_date']} to {data['end_date']}"
    )
    w.writerow(["Account number", "Account name", "Type", "Debit", "Credit", "Net"])
    for i in data["items"]:
        w.writerow(
            [
                i["account_number"],
                i["account_name"],
                i["account_type"],
                _money(i["total_debit"]),
                _money(i["total_credit"]),
                _money(i["net_balance"]),
            ]
        )
    w.writerow(
        [
            "",
            "Total",
            "",
            _money(data["total_debit"]),
            _money(data["total_credit"]),
            _money(data["difference"]),
        ]
    )
    return out.getvalue()


def general_ledger_csv(data: dict, company: str) -> str:
    """One row per journal line, grouped by account as the screen is:
    Date | Reference | Description | Account number | Account name | Debit |
    Credit | Running balance | Source type | Class (#213, last so a sheet
    that reads the columns by position still lines up). Each account opens with its
    balance brought forward from before the period and closes with a
    period-total row; the period total's net equals that account's Net on
    the trial balance for the same dates."""
    out = io.StringIO()
    w = _SafeWriter(out)
    _preamble(
        w, company, "General Ledger", f"{data['start_date']} to {data['end_date']}"
    )
    w.writerow(
        [
            "Date",
            "Reference",
            "Description",
            "Account number",
            "Account name",
            "Debit",
            "Credit",
            "Running balance",
            "Source type",
            "Class",
        ]
    )
    for a in data["accounts"]:
        num, name = a["account_number"] or "", a["account_name"]
        w.writerow(
            [
                data["start_date"],
                "",
                "Balance brought forward",
                num,
                name,
                "",
                "",
                _money(a["opening_balance"]),
                "opening",
                "",
            ]
        )
        for e in a["entries"]:
            w.writerow(
                [
                    e["date"],
                    e["reference"],
                    e["description"],
                    num,
                    name,
                    _money(e["debit"]) if e["debit"] else "",
                    _money(e["credit"]) if e["credit"] else "",
                    _money(e["running_balance"]),
                    e["source_type"],
                    e.get("class_name", ""),
                ]
            )
        w.writerow(
            [
                data["end_date"],
                "",
                "Period total",
                num,
                name,
                _money(a["total_debit"]),
                _money(a["total_credit"]),
                _money(a["closing_balance"]),
                "total",
                "",
            ]
        )
    return out.getvalue()


def profit_loss_csv(data: dict, company: str, words) -> str:
    out = io.StringIO()
    w = _SafeWriter(out)
    _preamble(
        w,
        company,
        words("Profit & Loss"),
        f"{data['start_date']} to {data['end_date']}",
    )
    w.writerow(["Section", "Account number", "Account name", "Amount"])
    for label, key, total_key in (
        (words("Income"), "income", "total_income"),
        ("Cost of Goods Sold", "cogs", "total_cogs"),
        ("Expenses", "expenses", "total_expenses"),
    ):
        for i in data[key]:
            w.writerow(
                [
                    label,
                    i.get("account_number") or "",
                    i["account_name"],
                    _money(i["amount"]),
                ]
            )
        w.writerow([label, "", f"Total {label}", _money(data[total_key])])
    w.writerow(["", "", "Gross Profit", _money(data["gross_profit"])])
    w.writerow(["", "", words("Net Income"), _money(data["net_income"])])
    return out.getvalue()


def balance_sheet_csv(data: dict, company: str, words) -> str:
    out = io.StringIO()
    w = _SafeWriter(out)
    _preamble(w, company, words("Balance Sheet"), f"As of {data['as_of_date']}")
    w.writerow(["Section", "Account number", "Account name", "Amount"])
    for label, key, total_key in (
        ("Assets", "assets", "total_assets"),
        ("Liabilities", "liabilities", "total_liabilities"),
        (words("Equity"), "equity", "total_equity"),
    ):
        for i in data[key]:
            w.writerow(
                [
                    label,
                    i.get("account_number") or "",
                    i["account_name"],
                    _money(i["amount"]),
                ]
            )
        w.writerow([label, "", f"Total {label}", _money(data[total_key])])
    w.writerow(
        [
            "",
            "",
            words("Liabilities + Equity"),
            _money(data["total_liabilities"] + data["total_equity"]),
        ]
    )
    return out.getvalue()


def rows_of(text: str) -> list[list[str]]:
    """The table rows of an export, preamble skipped — for tests and for any
    reader that wants the data (group reporting, #180)."""
    return list(csv.reader(io.StringIO(text)))[4:]
