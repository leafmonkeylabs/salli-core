"""
Unit tests for the Excel/CSV extractor.
Builds in-memory workbooks and CSV bytes — no real files needed.
"""

import io
from decimal import Decimal

import openpyxl

from salli.adapters.parsing.excel_extractor import extract_from_csv, extract_from_excel


def _make_xlsx(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
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
    rows = extract_from_excel(data)
    assert len(rows) == 2
    assert rows[0]["credit_flag"] is True
    assert rows[0]["amount"] == Decimal("300000.00")
    assert rows[0]["date"] == "2025-04-25"
    assert rows[1]["credit_flag"] is False
    assert rows[1]["amount"] == Decimal("4500.00")


def test_extract_from_excel_empty():
    data = _make_xlsx([["Date", "Description", "Debit", "Credit"]])
    assert extract_from_excel(data) == []


def test_extract_from_excel_skips_blank_rows():
    data = _make_xlsx(
        [
            ["Date", "Description", "Debit", "Credit"],
            ["", "", "", ""],
            ["01/06/2025", "Transfer", "1000.00", ""],
        ]
    )
    rows = extract_from_excel(data)
    assert len(rows) == 1


def test_extract_from_csv_basic():
    csv_bytes = b"Date,Description,Debit,Credit\n25/04/2025,Salary,,300000.00\n"
    rows = extract_from_csv(csv_bytes)
    assert len(rows) == 1
    assert rows[0]["amount"] == Decimal("300000.00")
    assert rows[0]["credit_flag"] is True


def test_extract_from_csv_latin1():
    csv_bytes = "Date,Description,Debit,Credit\n25/04/2025,Caf\xe9,,1500.00\n".encode("latin-1")
    rows = extract_from_csv(csv_bytes)
    assert len(rows) == 1


def test_extract_from_excel_with_ref_column():
    data = _make_xlsx(
        [
            ["Date", "Narration", "Withdrawals", "Deposits", "Cheque No"],
            ["01/05/2025", "NEFT Transfer", "", "50000.00", "TXN123"],
        ]
    )
    rows = extract_from_excel(data)
    assert rows[0]["bank_ref"] == "TXN123"
