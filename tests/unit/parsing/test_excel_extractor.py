"""
Unit tests for the Excel extractor.
Builds in-memory workbooks — no real files needed.
"""

import datetime
import io
from decimal import Decimal

import openpyxl

from salli.adapters.parsing.excel_extractor import extract_from_excel


def _make_xlsx(*sheets: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    for i, rows in enumerate(sheets):
        ws = wb.active if i == 0 else wb.create_sheet(f"Sheet{i + 1}")
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_extract_from_excel_basic():
    data = _make_xlsx(
        [
            ["Date", "Description", "Debit", "Credit"],
            ["25/04/2025", "Salary", "", "300000.00"],
            ["30/04/2025", "Electricity", "4500.00", ""],
        ]
    )
    rows = extract_from_excel(data).lines
    assert len(rows) == 2
    assert rows[0].credit_flag is True
    assert rows[0].amount == Decimal("300000.00")
    assert rows[0].date == "2025-04-25"
    assert rows[1].credit_flag is False
    assert rows[1].amount == Decimal("4500.00")
    assert {r.source_page for r in rows} == {1}


def test_extract_from_excel_empty():
    data = _make_xlsx([["Date", "Description", "Debit", "Credit"]])
    assert extract_from_excel(data).lines == []


def test_extract_from_excel_skips_blank_rows():
    data = _make_xlsx(
        [
            ["Date", "Description", "Debit", "Credit"],
            ["", "", "", ""],
            ["01/06/2025", "Transfer", "1000.00", ""],
        ]
    )
    assert len(extract_from_excel(data).lines) == 1


def test_extract_from_excel_with_ref_column():
    data = _make_xlsx(
        [
            ["Date", "Narration", "Withdrawals", "Deposits", "Cheque No"],
            ["01/05/2025", "NEFT Transfer", "", "50000.00", "TXN123"],
        ]
    )
    assert extract_from_excel(data).lines[0].bank_ref == "TXN123"


def test_typed_cells_and_signed_amounts_as_us_banks_export_them():
    # Real dates and numbers, as Excel keeps them, and one signed amount column.
    data = _make_xlsx(
        [
            ["Posting Date", "Description", "Amount"],
            [datetime.datetime(2026, 10, 2), "WHOLE FOODS", -84.17],
            [datetime.datetime(2026, 10, 15), "ACME PAYROLL", 3250],
        ]
    )
    rows = extract_from_excel(data).lines
    assert [(r.date, r.amount, r.credit_flag) for r in rows] == [
        ("2026-10-02", Decimal("84.17"), False),
        ("2026-10-15", Decimal("3250"), True),
    ]


def test_text_cells_in_european_and_us_formats():
    european = _make_xlsx(
        [
            ["Buchungstag", "Verwendungszweck", "Betrag"],
            ["01.10.2026", "Miete", "-1.200,00"],
            ["28.10.2026", "Gehalt", "3.450,00"],
        ]
    )
    assert [r.amount for r in extract_from_excel(european).lines] == [
        Decimal("1200.00"),
        Decimal("3450.00"),
    ]
    us = _make_xlsx([["Date", "Description", "Amount"], ["10/28/2026", "Rent", "(1,200.00)"]])
    (rent,) = extract_from_excel(us).lines
    assert (rent.date, rent.amount, rent.credit_flag) == ("2026-10-28", Decimal("1200.00"), False)


def test_the_first_sheet_that_is_a_statement():
    data = _make_xlsx(
        [["Account summary"], ["Opening balance", 1340.12]],
        [["Date", "Description", "Amount"], ["2026-10-01", "Rent", -1200]],
    )
    (rent,) = extract_from_excel(data).lines
    assert (rent.description, rent.source_page) == ("Rent", 2)


def test_a_damaged_workbook_is_said_to_be():
    assert extract_from_excel(b"PK\x03\x04 not really a workbook").errors == [
        "This Excel file could not be read (BadZipFile)"
    ]
