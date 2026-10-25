"""
Bank statement layouts as data: `salli.bankformat/1`.

A bank's layout is a JSON document rather than code, so one country's banks
can be added without touching the importer. The document states what a
`CsvMapping` states, and applies to the bank's CSV exports and to the tables
of its PDF and Excel statements, which share the same table reader:

    {
      "schema": "salli.bankformat/1",
      "name": "Example Bank current account",
      "columns": {"date": "Txn Date", "description": ["Description"],
                  "debit": "Withdrawals", "credit": "Deposits"},
      "date_format": "%d/%m/%Y",
      "decimal_separator": ".",
      "thousands_separator": ","
    }

Columns are named by header (the header row is the first row holding every
named column) or by 0-based position. Give `amount` (signed; `invert_sign`
when money out is positive), or `debit` and `credit`, or `amount` with a
`direction` column. Anything else in the document (`sources`, `verified`,
`notes`) is for the people who keep it and is not read here.

Several formats can be given at once: each is tried, and the one that reads
the most rows is taken (`pick`).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, cast

from salli.adapters.parsing.csv_import import Column, CsvMapping
from salli.adapters.parsing.support import Extraction
from salli.domain.parsing.models import FormatOutcome

SCHEMA = "salli.bankformat/1"

_COLUMNS = {"date", "description", "amount", "debit", "credit", "direction", "currency",
            "reference"}  # fmt: skip
_KEYS = {"schema", "name", "columns", "date_format", "date_order", "decimal_separator",
         "thousands_separator", "delimiter", "invert_sign", "bank", "sources", "verified",
         "notes", "sample"}  # fmt: skip


@dataclass(frozen=True)
class BankFormat:
    name: str
    mapping: CsvMapping


def load_bank_format(document: object) -> BankFormat:
    """A `salli.bankformat/1` document as a BankFormat; ValueError says what
    is wrong with it."""
    if not isinstance(document, dict):
        raise ValueError("A bank format is a JSON object")
    doc = cast("dict[str, Any]", document)
    if doc.get("schema") != SCHEMA:
        raise ValueError(f'A bank format\'s "schema" is "{SCHEMA}"')
    name = doc.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError('A bank format needs a "name"')
    if unknown := sorted(set(doc) - _KEYS):
        raise ValueError(f"{name}: unknown keys {', '.join(unknown)}")
    columns = doc.get("columns")
    if not isinstance(columns, dict):
        raise ValueError(f'{name}: "columns" is an object naming the columns')
    columns = cast("dict[str, Any]", columns)
    if unknown := sorted(set(columns) - _COLUMNS):
        raise ValueError(f"{name}: unknown columns {', '.join(unknown)}")

    def column(key: str) -> Column | None:
        value = columns.get(key)
        if value is None or (isinstance(value, str) and value) or type(value) is int:
            return value
        raise ValueError(f"{name}: column {key!r} is a header name or a 0-based position")

    raw_description = columns.get("description", [])
    descriptions = raw_description if isinstance(raw_description, list) else [raw_description]
    for value in cast("list[Any]", descriptions):
        if not ((isinstance(value, str) and value) or type(value) is int):
            raise ValueError(f"{name}: a description column is a header name or a position")
    date = column("date")
    if date is None:
        raise ValueError(f"{name}: the date column is required")
    amount, debit, credit = column("amount"), column("debit"), column("credit")
    if amount is None and (debit is None or credit is None):
        raise ValueError(f"{name}: give an amount column, or debit and credit columns")
    decimal = doc.get("decimal_separator")
    thousands = doc.get("thousands_separator")
    if decimal not in (None, ".", ","):
        raise ValueError(f'{name}: "decimal_separator" is "." or ","')
    if thousands not in (None, ",", ".", " ", "'", "") or (thousands and thousands == decimal):
        raise ValueError(f'{name}: "thousands_separator" is one other than the decimal one')
    order = doc.get("date_order")
    if order not in (None, "DMY", "MDY", "YMD"):
        raise ValueError(f'{name}: "date_order" is DMY, MDY or YMD')
    date_format = doc.get("date_format")
    delimiter = doc.get("delimiter")
    if date_format is not None and not isinstance(date_format, str):
        raise ValueError(f'{name}: "date_format" is a strptime format')
    if delimiter is not None and not (isinstance(delimiter, str) and len(delimiter) == 1):
        raise ValueError(f'{name}: "delimiter" is one character')
    return BankFormat(
        name=name.strip(),
        mapping=CsvMapping(
            date=date,
            description=tuple(cast("list[Column]", descriptions)),
            amount=amount,
            debit=debit,
            credit=credit,
            direction=column("direction"),
            currency=column("currency"),
            reference=column("reference"),
            date_format=date_format,
            date_order=order,
            decimal_separator=decimal,
            delimiter=delimiter,
            invert_sign=doc.get("invert_sign") is True,
        ),
    )


def pick(
    formats: Sequence[BankFormat], read: Callable[[CsvMapping], Extraction]
) -> tuple[Extraction, list[FormatOutcome]]:
    """Reads the file with each format and takes the one that read the most
    rows (the fewest failures between equals). Every format's counts are
    returned, the chosen one marked."""
    results = [(f, read(f.mapping)) for f in formats]
    best = max(
        range(len(results)), key=lambda i: (len(results[i][1].lines), -len(results[i][1].errors))
    )
    outcomes = [
        FormatOutcome(f.name, len(r.lines), len(r.errors), chosen=i == best and bool(r.lines))
        for i, (f, r) in enumerate(results)
    ]
    chosen = results[best][1]
    if not chosen.lines:
        names = ", ".join(f.name for f in formats)
        return Extraction(
            errors=[*chosen.errors, f"No row matched the formats given ({names})"]
        ), outcomes
    return chosen, outcomes
