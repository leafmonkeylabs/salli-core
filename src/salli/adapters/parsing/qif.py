"""
QIF statements (Quicken Interchange Format).

QIF is old and loose, but many banks still offer it beside CSV. A file is a
run of sections, each opened by a "!Type:" line, holding records of
one-letter fields that end with "^": D date, T (or U) amount, P payee, M memo,
N number, and others not needed here (categories, splits, addresses). Bank,
card and cash registers are read; investment and other-account registers, and
the account and category lists, are not.

QIF names no currency, so its rows are in the currency the caller gives. Its
dates are ambiguous (10/01/2026, 10/1'26, 1.10.2026), so their order is
decided from the whole file at once (see dates.py), and so is the decimal mark.
"""

from __future__ import annotations

from collections import Counter

from salli.adapters.parsing.amounts import detect_decimal_separator, parse_decimal
from salli.adapters.parsing.dates import DateOrder, detect_date_order, parse_date
from salli.adapters.parsing.support import Extraction, StatementLine, decode_text, join_description

_REGISTERS = {"bank", "ccard", "cash"}

# Registers that hold money but are not read. Saying so means a file that
# imports nothing, or less than expected, is not a mystery.
_UNREAD_REGISTERS = {"invst": "investment", "oth a": "other asset", "oth l": "other liability"}


def extract_from_qif(data: bytes, *, date_order: DateOrder | None = None) -> Extraction:
    """Every transaction in a QIF file's bank, card and cash registers.

    `date_order` overrides the order detected from the file's dates.
    """
    result = Extraction()
    records: list[tuple[int, dict[str, str]]] = []  # (line it starts on, fields)
    unread: Counter[str] = Counter()
    section: str | None = None
    fields: dict[str, str] = {}
    start = 0

    for number, raw in enumerate(decode_text(data).splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("!"):
            header = line[1:].strip().lower()
            if header.startswith("type:"):
                section = header[5:].strip()
            elif not header.startswith(("option:", "clear:")):
                section = header  # !Account: a list of accounts, not transactions
            fields = {}
        elif line.startswith("^"):
            if fields and section in _REGISTERS:
                records.append((start, fields))
            elif fields and section in _UNREAD_REGISTERS:
                unread[section] += 1
            fields = {}
        else:
            if not fields:
                start = number
            # The first of each field counts. Splits repeat S, E and $, but
            # never the date, amount, payee, memo or number.
            fields.setdefault(line[0], line[1:].strip())
    if fields and section in _REGISTERS:  # a last record without its "^"
        records.append((start, fields))

    for kind, count in unread.items():
        result.errors.append(
            f"Skipped {count} record(s) in the {_UNREAD_REGISTERS[kind]} register: "
            "only bank, card and cash registers are imported"
        )

    def amount_text(record: dict[str, str]) -> str:
        return record.get("T") or record.get("U") or ""

    mark = detect_decimal_separator(amount_text(f) for _, f in records) or "."
    if date_order is None:
        date_order, notice = detect_date_order(f.get("D", "") for _, f in records)
        if notice:
            result.errors.append(notice)

    for first_line, record in records:
        label = f"QIF record at line {first_line}"
        date = parse_date(record.get("D", ""), date_order)
        if date is None:
            result.errors.append(f"{label}: {record.get('D', '')!r} is not a date; skipped")
            continue
        try:
            amount = parse_decimal(amount_text(record), mark)
        except ValueError:
            result.errors.append(f"{label}: {amount_text(record)!r} is not an amount; skipped")
            continue
        if amount == 0:
            continue
        # N is a cheque or reference number, or else a word Quicken uses in
        # its place (ATM, DEP, EFT, Print). Only the numbers identify anything.
        reference = record.get("N", "")
        result.lines.append(
            StatementLine(
                date=date,
                description=join_description(record.get("P", ""), record.get("M", "")),
                amount=abs(amount),
                credit_flag=amount > 0,
                bank_ref=reference if any(ch.isdigit() for ch in reference) else "",
            )
        )
    return result
