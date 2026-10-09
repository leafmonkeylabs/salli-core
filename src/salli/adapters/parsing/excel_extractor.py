"""
Excel bank statement extractor using openpyxl.

Most Sri Lankan banks offer .xlsx exports from their internet banking.
The extractor handles:
  - Single-sheet with header row (most common)
  - Multiple sheets (uses first sheet that looks like a statement)

CSV files have their own importer (csv_import.py).
"""

from __future__ import annotations

import io
from typing import Any

from salli.adapters.parsing.pdf_extractor import (
    header_map,
    is_credit,
    normalise_date,
    parse_amount,
)


def extract_from_excel(data: bytes) -> list[dict[str, Any]]:
    """
    Extract raw transaction rows from an .xlsx bank statement.
    Returns same dict schema as pdf_extractor: {date, description, amount, credit_flag, bank_ref, page}.
    """
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)

    for sheet in wb.worksheets:
        rows = _parse_sheet(sheet)
        if rows:
            wb.close()
            return rows

    wb.close()
    return []


def _parse_sheet(sheet) -> list[dict[str, Any]]:
    table = []
    for row in sheet.iter_rows(values_only=True):
        table.append([str(c).strip() if c is not None else "" for c in row])
    return _parse_raw_table(table, page=1)


def _parse_raw_table(table: list[list[str]], page: int) -> list[dict[str, Any]]:
    if not table:
        return []

    # Find header row: first row with a recognisable date/desc column header
    header_idx = None
    col_map: dict[str, int] = {}
    for i, row in enumerate(table):
        m = header_map(row)
        if "date" in m and "desc" in m:
            header_idx = i
            col_map = m
            break

    if header_idx is None:
        return []

    rows = []
    for row in table[header_idx + 1 :]:
        if not row or all(c == "" for c in row):
            continue

        date_str = normalise_date(row[col_map["date"]] if col_map["date"] < len(row) else "")
        if not date_str:
            continue

        desc = row[col_map["desc"]].strip() if col_map["desc"] < len(row) else ""
        if not desc:
            continue

        debit_cell = (
            row[col_map["debit"]] if "debit" in col_map and col_map["debit"] < len(row) else ""
        )
        credit_cell = (
            row[col_map["credit"]] if "credit" in col_map and col_map["credit"] < len(row) else ""
        )

        direction = is_credit(debit_cell, credit_cell)
        if direction is None:
            continue

        amount = parse_amount(credit_cell if direction else debit_cell)
        if not amount:
            continue

        ref = row[col_map["ref"]].strip() if "ref" in col_map and col_map["ref"] < len(row) else ""

        rows.append(
            {
                "date": date_str,
                "description": desc,
                "amount": amount,
                "credit_flag": direction,
                "bank_ref": ref,
                "page": page,
            }
        )

    return rows
