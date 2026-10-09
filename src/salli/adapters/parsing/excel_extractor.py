"""
Excel bank statement extractor using openpyxl.

Reads the workbook's first sheet that is a statement — one with a header row
Salli knows, or else one whose columns can still be told apart — with the
same table reader as CSV files (csv_import.py). So an Excel export is read as
well as a CSV one: header names in several languages, signed, split or
direction-column amounts, day- or month-first dates, decimal commas.
"""

from __future__ import annotations

import datetime
import io

from salli.adapters.parsing.csv_import import Table, extract_from_tables
from salli.adapters.parsing.dates import DateOrder
from salli.adapters.parsing.support import Extraction


def extract_from_excel(data: bytes, *, date_order: DateOrder | None = None) -> Extraction:
    """Every transaction on the first sheet of an .xlsx workbook that is a statement."""
    import openpyxl

    # The file is the user's upload: a damaged one is something to say, not
    # a server error.
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            sheets = [
                Table(
                    [[_text(cell) for cell in row] for row in sheet.iter_rows(values_only=True)],
                    label=f"Sheet {sheet.title!r}, row",
                    page=number,
                )
                for number, sheet in enumerate(workbook.worksheets, 1)
            ]
        finally:
            workbook.close()
    except Exception as exc:
        return Extraction(errors=[f"This Excel file could not be read ({type(exc).__name__})"])

    for infer in (False, True):
        for sheet in sheets:
            result = extract_from_tables([sheet], date_order=date_order, infer=infer)
            if result is not None and result.lines:
                return result
    return Extraction(
        errors=["No sheet in this workbook looks like a statement: no date and amount columns"]
    )


def _text(value: object) -> str:
    """A cell as text. Excel keeps a date as a date, and a number as a binary
    float; the shortest decimal that is that float, which is what str()
    gives, is the amount that was typed, ungrouped and with a dot."""
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value).strip()
