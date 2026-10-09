"""
PDF bank statement extractor using pdfplumber.

Handles the two ways statements are printed:
  1. Tables — read with the same table reader as CSV files (csv_import.py):
     header names, signed or split amounts, date order and decimal mark
     decided across the whole statement, and a table that runs on to the
     next page without repeating its header.
  2. Text — a page with no table is read line by line: a date, a
     description, then an amount, with Dr or Cr after it if the bank prints one.

The extractor is deliberately dumb: it reads what the statement says. The LLM
classifier (llm_classifier.py) interprets descriptions and assigns accounts.
"""

from __future__ import annotations

import io
import re

from salli.adapters.parsing.amounts import detect_decimal_separator, parse_decimal
from salli.adapters.parsing.csv_import import Table, extract_from_tables
from salli.adapters.parsing.dates import DateOrder, detect_date_order, parse_date
from salli.adapters.parsing.support import Extraction, StatementLine

# A line of a text-mode statement: its date (numbers in any order, or a
# month's name), a description, and the first amount after it, which comes
# before the running balance. The amount has no spaces in it, so the two
# never run together.
_TEXT_ROW = re.compile(
    r"(?P<date>\d{1,4}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{1,2}[\s\-]+[^\W\d_]{3,9}\.?[\s\-]+\d{2,4})"
    r"\s+(?P<desc>.+?)\s+"
    r"(?P<amount>\(?-?\d[\d.,']*[.,]\d{2}\)?-?)"
    r"(?:\s*(?P<mark>Dr|Cr)\b)?",
    re.IGNORECASE,
)


def extract_from_pdf(data: bytes, *, date_order: DateOrder | None = None) -> Extraction:
    """Every transaction in a PDF statement, from its tables or its text."""
    import pdfplumber

    tables: list[Table] = []
    pages: list[tuple[int, str]] = []
    # The file is the user's upload: a damaged one is something to say, not
    # a server error.
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for number, page in enumerate(pdf.pages, 1):
                found = page.extract_tables()
                if found:
                    tables += [
                        Table(
                            [[(cell or "").strip() for cell in row] for row in table],
                            label=f"Page {number}, row",
                            page=number,
                        )
                        for table in found
                    ]
                else:
                    pages.append((number, page.extract_text() or ""))
    except Exception as exc:
        return Extraction(errors=[f"This PDF could not be read ({type(exc).__name__})"])

    from_tables = extract_from_tables(tables, date_order=date_order, infer=False) or Extraction()
    from_text = _text_lines(pages, date_order)
    return Extraction(
        lines=sorted([*from_tables.lines, *from_text.lines], key=lambda line: line.source_page),
        errors=[*from_tables.errors, *from_text.errors],
    )


def _text_lines(pages: list[tuple[int, str]], date_order: DateOrder | None) -> Extraction:
    """The transactions printed as lines of text on these (page, text) pages."""
    result = Extraction()
    found = [
        (number, match)
        for number, text in pages
        for line in text.splitlines()
        if (match := _TEXT_ROW.search(line))
    ]
    if date_order is None:
        date_order, notice = detect_date_order(match["date"] for _, match in found)
        if notice:
            result.errors.append(notice)
    mark = detect_decimal_separator(match["amount"] for _, match in found) or "."

    for number, match in found:
        date = parse_date(match["date"], date_order)
        try:
            value = parse_decimal(match["amount"], mark)
        except ValueError:
            continue
        if date is None or value == 0:
            continue
        description = " ".join(match["desc"].split())
        marked = (match["mark"] or "").upper()
        if marked:
            credit = marked == "CR"
        elif value < 0:
            credit = False
        else:
            # Nothing on the line says which way the money went. It is read
            # as money in, as it always was, but said, since it may well be
            # spending.
            credit = True
            result.errors.append(
                f"Page {number}: {date} {description[:40]!r} has no Dr/Cr mark; "
                "read as money in, so check it"
            )
        result.lines.append(
            StatementLine(date, description, abs(value), credit, source_page=number)
        )
    return result
