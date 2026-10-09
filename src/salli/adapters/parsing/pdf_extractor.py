"""
PDF bank statement extractor using pdfplumber.

Handles the two most common Sri Lankan bank statement layouts:
  1. Table-per-page — pdfplumber extracts table rows directly
  2. Text-mode — falls back to line-by-line regex parsing

The extractor is deliberately dumb: it returns raw text rows. The LLM
classifier (llm_classifier.py) interprets descriptions and assigns accounts.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

# ── Helpers ───────────────────────────────────────────────────────────────────

_DATE_PATTERNS = [
    re.compile(r"(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})"),  # DD/MM/YYYY or DD-MM-YYYY
    re.compile(r"(\d{4})[/\-\.](\d{2})[/\-\.](\d{2})"),  # YYYY-MM-DD
    re.compile(r"(\d{2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})", re.I),
]

_MONTHS = {
    m: str(i).zfill(2)
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
    )
}


def normalise_date(raw: str) -> str | None:
    raw = raw.strip()
    for pat in _DATE_PATTERNS:
        m = pat.search(raw)
        if m:
            g = m.groups()
            if len(g[0]) == 4:  # YYYY-MM-DD
                return f"{g[0]}-{g[1]}-{g[2]}"
            elif g[1] in _MONTHS:  # DD Mon YYYY
                return f"{g[2]}-{_MONTHS[g[1]]}-{g[0].zfill(2)}"
            else:  # DD/MM/YYYY
                return f"{g[2]}-{g[1].zfill(2)}-{g[0].zfill(2)}"
    return None


def parse_amount(text: str) -> Decimal | None:
    clean = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return Decimal(clean) if clean else None
    except InvalidOperation:
        return None


def is_credit(debit_cell: str, credit_cell: str) -> bool | None:
    """Given debit and credit column cells, determine direction. Returns None if unclear."""
    has_debit = bool(debit_cell and debit_cell.strip() and parse_amount(debit_cell))
    has_credit = bool(credit_cell and credit_cell.strip() and parse_amount(credit_cell))
    if has_credit and not has_debit:
        return True
    if has_debit and not has_credit:
        return False
    return None


# ── Table column heuristics ───────────────────────────────────────────────────

_DATE_HEADERS = {"date", "txn date", "transaction date", "value date", "posting date"}
_DESC_HEADERS = {"description", "particulars", "narration", "details", "transaction details"}
_DEBIT_HEADERS = {"debit", "dr", "withdrawals", "withdrawal", "dr amount"}
_CREDIT_HEADERS = {"credit", "cr", "deposits", "deposit", "cr amount"}
_REF_HEADERS = {"ref", "reference", "txn ref", "cheque no", "chq no", "transaction id"}


def header_map(headers: list[str]) -> dict[str, int]:
    """Return {role: column_index} for a header row."""
    mapping: dict[str, int] = {}
    for i, h in enumerate(headers):
        norm = h.lower().strip() if h else ""
        if norm in _DATE_HEADERS and "date" not in mapping:
            mapping["date"] = i
        elif norm in _DESC_HEADERS and "desc" not in mapping:
            mapping["desc"] = i
        elif norm in _DEBIT_HEADERS and "debit" not in mapping:
            mapping["debit"] = i
        elif norm in _CREDIT_HEADERS and "credit" not in mapping:
            mapping["credit"] = i
        elif norm in _REF_HEADERS and "ref" not in mapping:
            mapping["ref"] = i
    return mapping


# ── Public extractor ──────────────────────────────────────────────────────────


def extract_from_pdf(data: bytes) -> list[dict[str, Any]]:
    """
    Extract raw transaction rows from a PDF bank statement.
    Returns a list of dicts: {date, description, amount, credit_flag, bank_ref, page}.
    Rows that cannot be parsed are skipped.
    """
    import pdfplumber

    rows: list[dict[str, Any]] = []

    with pdfplumber.open(__import__("io").BytesIO(data)) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    rows.extend(_parse_table(table, page_num))
            else:
                # Fallback: text line parsing
                rows.extend(_parse_text_lines(page.extract_text() or "", page_num))

    return rows


def _parse_table(table: list[list[str | None]], page: int) -> list[dict[str, Any]]:
    if not table:
        return []

    # First non-empty row is likely the header
    header_row = next((r for r in table if any(c and c.strip() for c in r)), None)
    if header_row is None:
        return []

    col_map = header_map([c or "" for c in header_row])
    if "date" not in col_map or "desc" not in col_map:
        return []

    rows = []
    for row in table[table.index(header_row) + 1 :]:
        if row is None:
            continue
        cells = [c or "" for c in row]

        date_str = normalise_date(cells[col_map["date"]] if col_map["date"] < len(cells) else "")
        if not date_str:
            continue

        desc = cells[col_map["desc"]].strip() if col_map["desc"] < len(cells) else ""
        if not desc:
            continue

        debit_cell = (
            cells[col_map["debit"]] if "debit" in col_map and col_map["debit"] < len(cells) else ""
        )
        credit_cell = (
            cells[col_map["credit"]]
            if "credit" in col_map and col_map["credit"] < len(cells)
            else ""
        )

        direction = is_credit(debit_cell, credit_cell)
        if direction is None:
            continue

        amount = parse_amount(credit_cell if direction else debit_cell)
        if not amount:
            continue

        ref = (
            cells[col_map["ref"]].strip()
            if "ref" in col_map and col_map["ref"] < len(cells)
            else ""
        )

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


# Simple regex fallback for text-mode PDFs
_TEXT_ROW = re.compile(
    r"(?P<date>\d{2}[/\-\.]\d{2}[/\-\.]\d{4})"
    r"\s+(?P<desc>.+?)\s+"
    r"(?P<amount>[\d,]+\.\d{2})"
    r"\s*(?P<dir>Dr|Cr|DR|CR)?",
    re.IGNORECASE,
)


def _parse_text_lines(text: str, page: int) -> list[dict[str, Any]]:
    rows = []
    for line in text.splitlines():
        m = _TEXT_ROW.search(line)
        if not m:
            continue
        date_str = normalise_date(m.group("date"))
        if not date_str:
            continue
        amount = parse_amount(m.group("amount"))
        if not amount:
            continue
        direction_str = (m.group("dir") or "").upper()
        credit_flag = (
            direction_str == "CR" if direction_str else True
        )  # default credit if ambiguous

        rows.append(
            {
                "date": date_str,
                "description": m.group("desc").strip(),
                "amount": amount,
                "credit_flag": credit_flag,
                "bank_ref": "",
                "page": page,
            }
        )
    return rows
