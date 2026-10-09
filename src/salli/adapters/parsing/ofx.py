"""
OFX and QFX statements (Open Financial Exchange; QFX is Quicken's flavour).

OFX comes in two generations. 1.x is SGML: a block of KEY:VALUE headers, then
tags in which an element holding a value is usually never closed
(<TRNAMT>-45.67 and no </TRNAMT>). 2.x is XML. Rather than two parsers, both
are read as one stream of tags: a tag followed by text is an element with
that value, closed or not; a tag followed straight by another tag opens an
aggregate, which both generations always close.

Bank (<STMTRS>) and credit-card (<CCSTMTRS>) statements are read. Investment
statements are not: their cash lines sit beside holdings this does not model.
"""

from __future__ import annotations

import datetime
import html
import re
from decimal import Decimal

from salli.adapters.parsing.amounts import parse_decimal
from salli.adapters.parsing.support import Extraction, StatementLine, decode_text, join_description

_TAG = re.compile(r"<(/?)([A-Za-z0-9.]+)>([^<]*)")
_STATEMENTS = ("STMTRS", "CCSTMTRS")


def extract_from_ofx(data: bytes) -> Extraction:
    """Every transaction in the bank and card statements of an OFX/QFX file."""
    text = decode_text(data)
    start = text.upper().find("<OFX>")
    if start < 0:
        return Extraction(errors=["This is not an OFX file: it has no <OFX> element"])

    result = Extraction()
    in_statement = False
    statement_currency: str | None = None
    txn: dict[str, str] | None = None
    path: list[str] = []  # aggregates open inside the current transaction
    seen = 0

    def finish() -> None:
        nonlocal txn
        if txn is not None:
            _add(txn, seen, statement_currency, result)
        txn = None

    for match in _TAG.finditer(text, start):
        closing, name, value = match.group(1), match.group(2).upper(), match.group(3).strip()
        if closing:
            if name in ("STMTTRN", "BANKTRANLIST", *_STATEMENTS):
                finish()
            if name in _STATEMENTS:
                in_statement = False
            elif name in path:
                del path[path.index(name) :]
        elif name in _STATEMENTS:
            in_statement, statement_currency = True, None
        elif not in_statement:
            continue
        elif name == "STMTTRN":
            finish()
            txn, path, seen = {}, [], seen + 1
        elif txn is not None:
            if value:
                txn.setdefault("/".join([*path, name]), html.unescape(value))
            else:
                path.append(name)
        elif name == "CURDEF" and value:
            statement_currency = value
    finish()
    return result


def _add(
    txn: dict[str, str], number: int, statement_currency: str | None, result: Extraction
) -> None:
    fitid = txn.get("FITID", "")
    label = f"OFX transaction {fitid or number}"

    date = _date(txn.get("DTPOSTED", ""))
    if date is None:
        result.errors.append(f"{label}: {txn.get('DTPOSTED', '')!r} is not a date; skipped")
        return
    try:
        amount = _amount(txn.get("TRNAMT", ""))
    except ValueError:
        result.errors.append(f"{label}: {txn.get('TRNAMT', '')!r} is not an amount; skipped")
        return
    if amount == 0:
        return

    description = join_description(
        txn.get("NAME") or txn.get("PAYEE/NAME", ""), txn.get("MEMO", "")
    ) or join_description(txn.get("TRNTYPE", ""), txn.get("CHECKNUM", ""))
    result.lines.append(
        StatementLine(
            date=date,
            description=description,
            amount=abs(amount),
            credit_flag=amount > 0,
            # <CURRENCY> means this amount is in another currency than the
            # statement's. <ORIGCURRENCY> means it was converted *into* the
            # statement's currency from that one, so the amount is still in
            # the statement's.
            currency=txn.get("CURRENCY/CURSYM") or statement_currency,
            bank_ref=fitid,
        )
    )


def _date(value: str) -> str | None:
    """An OFX datetime (20261001120000.000[-5:EST]) as YYYY-MM-DD.

    The date is taken as the bank wrote it, in the bank's own time zone,
    which is the date its statement shows; converting to UTC would move a
    late-evening purchase to the next day.
    """
    match = re.match(r"(\d{4})(\d{2})(\d{2})", value)
    if match is None:
        return None
    try:
        return datetime.date(*(int(g) for g in match.groups())).isoformat()
    except ValueError:
        return None


def _amount(value: str) -> Decimal:
    # OFX amounts have no thousands separators, and some banks (French ones,
    # for a start) write the decimal point as a comma.
    return parse_decimal(value, "," if "," in value and "." not in value else ".")
