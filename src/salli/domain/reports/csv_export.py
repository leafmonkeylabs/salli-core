"""
Pure CSV export helper — no I/O, no file handles. Formatting only: turning an
already-computed report (headers + rows) into CSV bytes for download.

Callers are responsible for producing the header/row shape from their own
domain data (see application/services/report_service.py) — this module knows
nothing about balance sheets, net worth, or goals.
"""

from __future__ import annotations

import csv
import io
from typing import Any


def rows_to_csv(headers: list[str], rows: list[list[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if cell is None else str(cell) for cell in row])
    return buffer.getvalue().encode("utf-8")
