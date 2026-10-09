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
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from salli.adapters.parsing.csv_import import Table, extract_from_tables
from salli.adapters.parsing.dates import DateOrder
from salli.adapters.parsing.support import Extraction


def extract_from_excel(
    data: bytes,
    *,
    date_order: DateOrder | None = None,
    prefer_order: DateOrder = "DMY",
    currency: str | None = None,
) -> Extraction:
    """Every transaction on the first sheet of an .xlsx workbook that is a
    statement. Sheets are read one at a time, and reading stops at the
    statement: a workbook's other sheets (a 60,000-row data dump) are never
    loaded when an earlier one is the statement."""
    import openpyxl

    def read(sheet: Table) -> Extraction | None:
        result = extract_from_tables(
            [sheet],
            date_order=date_order,
            prefer_order=prefer_order,
            currency=currency,
            infer=infer,
        )
        return result if result is not None and result.lines else None

    # The file is the user's upload: a damaged one is something to say, not
    # a server error.
    seen: list[Table] = []
    infer = False
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        try:
            for number, worksheet in enumerate(workbook.worksheets, 1):
                sheet = Table(
                    [
                        [_text(cell) for cell in row]
                        for row in worksheet.iter_rows(values_only=True)
                    ],
                    label=f"Sheet {worksheet.title!r}, row",
                    page=number,
                )
                found = read(sheet)
                if found is not None:
                    return found
                seen.append(sheet)
        finally:
            workbook.close()
    except Exception as exc:
        return Extraction(errors=[f"This Excel file could not be read ({type(exc).__name__})"])

    # No sheet has a header Salli knows: read each by what its columns hold.
    infer = True
    for sheet in seen:
        found = read(sheet)
        if found is not None:
            return found
    return Extraction(
        errors=["No sheet in this workbook looks like a statement: no date and amount columns"]
    )


# Excel keeps a number as a binary float. Nine decimals are more than any
# currency has, and few enough that a formula's float noise is rounded away.
_PLACES = 9


def _text(value: object) -> str:
    """A cell as text. Excel keeps a date as a date, and a number as a binary
    float: 12.1 typed, or worked out by a formula as 12.100000000000001. The
    float's shortest repr, rounded to nine decimals and stripped of trailing
    zeros, is the amount that was typed, ungrouped and with a dot."""
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return ""
        with localcontext() as ctx:
            ctx.prec = 64  # room for any float's digits and nine decimals
            exact = Decimal(repr(value)).quantize(Decimal(1).scaleb(-_PLACES), ROUND_HALF_EVEN)
            return format(exact.normalize(), "f")
    return str(value).strip()
