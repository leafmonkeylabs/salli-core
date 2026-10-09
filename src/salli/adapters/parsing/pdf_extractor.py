"""
PDF bank statement extractor using pdfplumber.

Handles the two ways statements are printed:
  1. Tables — read with the same table reader as CSV files (csv_import.py):
     header names, signed or split amounts, date order and decimal mark
     decided across the whole statement, and a table that runs on to the
     next page without repeating its header. A table that can't be read is
     said, never dropped silently, and a page whose tables gave no
     transactions (a boxed summary above them) is read as text outside them.
  2. Text — read line by line: a date, a description, then the amount and,
     on most statements, the running balance. The amount is taken from the
     right (the number before the balance), so a foreign amount in the
     description ("USD 12.99") never wins, and the change in the balance says
     which way the money went. Balance lines (brought forward, closing
     balance) are not transactions.

The extractor is deliberately dumb: it reads what the statement says. The LLM
classifier (llm_classifier.py) interprets descriptions and assigns accounts.
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from salli.adapters.parsing.amounts import decimal_mark_for, parse_decimal
from salli.adapters.parsing.csv_import import Table, extract_from_tables
from salli.adapters.parsing.dates import DateOrder, detect_date_order, parse_date
from salli.adapters.parsing.support import Extraction, StatementLine
from salli.domain.currency import exponent, is_currency

# A text line is read with its whitespace collapsed to single spaces, so no
# pattern below can backtrack over a long run of them; a longer line is no row.
_MAX_LINE = 400

# A date: numbers with separators, or a day, a month's name and a year.
_DATE = re.compile(
    r"(?<![\w.,])(?:\d{1,4}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{1,2}[ \-][^\W\d_]{3,9}\.?[ \-]\d{2,4})"
    r"(?!\w)"
)
# An amount standing alone: an optional sign or bracket, an optional currency
# symbol, digits grouped or not, none to three decimals, then Dr or Cr.
_AMOUNT = re.compile(
    r"(?<!\S)(?P<number>[(\-+]?[$€£¥₹]?(?:\d{1,3}(?:[,.']\d{3})+|\d+)(?:[.,]\d{1,3})?\)?-?)"
    r"(?: ?(?P<mark>[Dd][Rr]|[Cc][Rr])\b)?(?!\S)"
)

# Lines that state a balance, not a transaction, in the languages statements
# are printed in. Matched folded: lower case, no accents, single spaces.
_BALANCE_LINES = re.compile(
    r"\b(?:balance (?:b/?f|c/?f|brought forward|carried forward|forward)|b/f|c/f|"
    r"brought forward|carried forward|(?:opening|closing|previous|starting|ending|"
    r"available|ledger) balance|balance as (?:at|of|on)|"
    r"saldo (?:anterior|inicial|final|iniziale|finale|precedente|vorig|nieuw)|"
    r"(?:anfangs|end|alter |neuer |vortrags)saldo|kontostand|"
    r"solde (?:precedent|initial|final|anterior|reporte)|nouveau solde|ancien solde|"
    r"(?:begin|eind)saldo)\b"
)


@dataclass(frozen=True)
class _Row:
    page: int
    date_text: str
    description: str
    amount: str  # the amount as printed, without its mark
    mark: str  # "DR", "CR" or ""
    balance: str  # the running balance as printed, with its mark; "" when none
    is_balance_line: bool = False


def extract_from_pdf(
    data: bytes,
    *,
    date_order: DateOrder | None = None,
    prefer_order: DateOrder = "DMY",
    currency: str | None = None,
) -> Extraction:
    """Every transaction in a PDF statement, from its tables or its text."""
    import pdfplumber

    tables: list[Table] = []
    pages: dict[int, str] = {}  # page -> its text outside any table
    with_tables: set[int] = set()
    # The file is the user's upload: a damaged one is something to say, not
    # a server error.
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for number, page in enumerate(pdf.pages, 1):
                found: list[Any] = page.find_tables()
                outside: Any = page
                for table in found:
                    tables.append(
                        Table(
                            [[(cell or "").strip() for cell in row] for row in table.extract()],
                            label=f"Page {number}, row",
                            page=number,
                        )
                    )
                    outside = outside.outside_bbox(table.bbox)
                if found:
                    with_tables.add(number)
                pages[number] = outside.extract_text() or ""
    except Exception as exc:
        return Extraction(errors=[f"This PDF could not be read ({type(exc).__name__})"])

    unread: list[Table] = []
    from_tables = (
        extract_from_tables(
            tables,
            date_order=date_order,
            prefer_order=prefer_order,
            currency=currency,
            infer=False,
            unread=unread,
        )
        or Extraction()
    )
    errors = list(from_tables.errors)
    for table in unread:
        if any(any(cell for cell in row) for row in table.rows):
            errors.append(
                f"Page {table.page}: a table could not be read as transactions (no date and "
                "amount columns Salli recognises); check that page"
            )
    # Text is read on pages with no table, and on pages whose tables gave no
    # transactions: a boxed summary can sit above transactions printed as text.
    read_pages = {line.source_page for line in from_tables.lines}
    text_pages = [
        (number, text)
        for number, text in pages.items()
        if number not in with_tables or number not in read_pages
    ]
    from_text = _text_lines(text_pages, date_order, prefer_order, currency)
    return Extraction(
        lines=sorted([*from_tables.lines, *from_text.lines], key=lambda line: line.source_page),
        errors=[*errors, *from_text.errors],
    )


def _fold(text: str) -> str:
    folded = "".join(
        ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch)
    )
    return " ".join(folded.split())


def _parse_line(page: int, line: str) -> _Row | str | None:
    """A text line (whitespace collapsed) as a row; a reason when it starts
    like one but can't be read; None when it is no transaction line at all."""
    if len(line) > _MAX_LINE:
        return None
    date = _DATE.search(line)
    if date is None:
        return None
    rest = line[date.end() :]
    # A second date straight after the first is the value date.
    value_date = re.match(r" ?(?:" + _DATE.pattern + ")", rest)
    if value_date:
        rest = rest[value_date.end() :]
    # The amounts at the end of the line, with nothing but spaces between.
    trailing: list[re.Match[str]] = []
    end = len(rest.rstrip())
    for token in reversed(list(_AMOUNT.finditer(rest))):
        if rest[token.end() : end].strip():
            break
        trailing.insert(0, token)
        end = token.start()
    # The date opens the row, after at most a serial number or a bullet.
    starts_line = re.fullmatch(r"[ \-*|#.\d]{0,8}", line[: date.start()]) is not None
    if not trailing:
        if starts_line and rest.strip():
            return f"Page {page}: {line[:60]!r} has a date but no amount Salli can read; skipped"
        return None
    if not starts_line:
        return None  # a date mid-sentence ("Statement period 01/10 to 31/10")
    # Taken from the right: the number before the running balance. A foreign
    # amount earlier in the line ("USD 12.99") stays in the description.
    amount, balance = (trailing[-2], trailing[-1]) if len(trailing) >= 2 else (trailing[-1], None)
    description = " ".join(rest[: amount.start()].split()).strip(" -*|")
    return _Row(
        page=page,
        date_text=date.group(),
        description=description,
        amount=amount["number"],
        mark=(amount["mark"] or "").upper(),
        balance=balance["number"] + " " + (balance["mark"] or "") if balance else "",
        is_balance_line=bool(_BALANCE_LINES.search(_fold(description))),
    )


def _text_lines(
    pages: list[tuple[int, str]],
    date_order: DateOrder | None,
    prefer_order: DateOrder,
    currency: str | None,
) -> Extraction:
    """The transactions printed as lines of text on these (page, text) pages."""
    result = Extraction()
    rows: list[_Row] = []
    for number, text in pages:
        for raw in text.splitlines():
            parsed = _parse_line(number, " ".join(raw.split()))
            if isinstance(parsed, str):
                result.errors.append(parsed)
            elif parsed is not None:
                rows.append(parsed)
    if not rows:
        return result

    if date_order is None:
        date_order, notice = detect_date_order(
            (r.date_text for r in rows if not r.is_balance_line), prefer=prefer_order
        )
        if notice:
            result.errors.append(notice)
    places = exponent(currency) if currency and is_currency(currency) else None
    mark = decimal_mark_for(
        [r.amount for r in rows] + [r.balance for r in rows if r.balance], places
    )

    read: list[tuple[_Row, str, Decimal, Decimal | None]] = []
    for row in rows:
        date = parse_date(row.date_text, date_order)
        if date is None:
            result.errors.append(
                f"Page {row.page}: {row.date_text!r} ({row.description[:40]!r}) is not a date; "
                "skipped"
            )
            continue
        try:
            value = parse_decimal(row.amount, mark)
            # A balance's mark is its sign: Dr is overdrawn (or owed on a
            # card), below zero; Cr and an unmarked one above.
            balance = parse_decimal(row.balance, mark) if row.balance else None
        except ValueError:
            result.errors.append(
                f"Page {row.page}: {date} {row.description[:40]!r}: {row.amount!r} is not an "
                "amount; skipped"
            )
            continue
        if row.is_balance_line and balance is None:
            # "BALANCE B/F 166,100.00 Cr": its only number is the balance.
            balance = parse_decimal(f"{row.amount} {row.mark}", mark)
        read.append((row, date, value, balance))

    # Through the rows oldest first (statements print either way round), the
    # change in the running balance says which way each row's money went.
    chronological = read if not read or read[0][1] <= read[-1][1] else read[::-1]
    previous: Decimal | None = None
    ways: dict[int, bool] = {}
    for row, _, value, balance in chronological:
        if balance is not None and previous is not None and not row.is_balance_line:
            change = balance - previous
            if value and abs(change) == abs(value):
                ways[id(row)] = change > 0
        if balance is not None:
            previous = balance

    for row, date, value, _ in read:
        if row.is_balance_line or value == 0:
            continue  # a balance brought or carried forward moves no money
        credit = ways.get(id(row))
        if credit is None and row.mark:
            credit = row.mark == "CR"
        if credit is None and value < 0:
            credit = False
        if credit is None:
            # Nothing says which way the money went: no mark, no sign, and no
            # balance whose change shows it. Read as money in, as it always
            # was, and said, since it may well be spending.
            credit = True
            result.errors.append(
                f"Page {row.page}: {date} {row.description[:40]!r} has no Dr/Cr mark; "
                "read as money in, so check it"
            )
        result.lines.append(
            StatementLine(date, row.description, abs(value), credit, source_page=row.page)
        )
    return result
