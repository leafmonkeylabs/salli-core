"""
What every statement importer returns, and the small helpers they share.

An importer reads one file format and reports each transaction exactly as the
file states it. It does not decide the currency of a row whose file names
none, and it does not check the codes it reads: `parsing_service` does both,
the same way for every format, when it turns these lines into `RawRow`s.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from salli.adapters.parsing.amounts import MAX_INTEGER_DIGITS

#: What a row's reference is. An "id" is the bank's own unique id for the
#: transaction (OFX FITID, camt AcctSvcrRef, a feed's id, a CSV column of
#: unique id-shaped values): it may identify the transaction on its own. A
#: "text" reference (a cheque number, a customer's reference, a free-text
#: Reference column) is only part of what the row says.
RefKind = Literal["id", "text"]

# Dates a statement can hold. Placeholders such as 9999-12-31 or 0001-01-01
# are no transaction's.
_FIRST_YEAR, _LAST_YEAR = 1900, 2100


@dataclass(frozen=True)
class StatementLine:
    """One transaction as a statement file states it."""

    date: str  # YYYY-MM-DD
    description: str
    amount: Decimal  # always positive, exactly as written; never rounded here
    credit_flag: bool  # True = money in
    currency: str | None = None  # the file's own code, unchecked; None if it names none
    bank_ref: str = ""
    source_page: int = 0
    ref_kind: RefKind = "id"
    #: The account in the file the line is on (its number, or its name), when
    #: the file says; "" when it names none.
    account: str = ""


@dataclass
class Extraction:
    """An importer's result: the lines it read, and what it could not read."""

    lines: list[StatementLine] = field(default_factory=list[StatementLine])
    errors: list[str] = field(default_factory=list[str])
    #: Every account the file holds statements for, in file order ("" never).
    accounts: list[str] = field(default_factory=list[str])
    #: What kind each of `accounts` is, where the file says ("credit card").
    account_kinds: dict[str, str] = field(default_factory=dict[str, str])


def real_date(year: int, month: int, day: int) -> str | None:
    """YYYY-MM-DD, or None for no real date or one outside 1900-2100."""
    if not _FIRST_YEAR <= year <= _LAST_YEAR:
        return None
    try:
        return datetime.date(year, month, day).isoformat()
    except ValueError:
        return None


def too_large(amount: Decimal) -> bool:
    """More integer digits than any real amount (`amounts.MAX_INTEGER_DIGITS`)."""
    return amount.adjusted() >= MAX_INTEGER_DIGITS


def looks_like_id(value: str) -> bool:
    """Whether a reference looks generated: a bank's id for a transaction
    rather than words someone typed. Ids are long, carry digits, and are not
    mostly letters (`202610010001`, `TXN2026100100A1`, a UUID); free text
    (`BARBER`, `Rent Oct`) is mostly letters."""
    v = value.strip()
    if re.fullmatch(
        r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}", v
    ):
        return True
    alnum = [ch for ch in v if ch.isalnum()]
    letters = sum(ch.isalpha() for ch in alnum)
    return len(alnum) >= 6 and any(ch.isdigit() for ch in alnum) and letters * 2 <= len(alnum)


def decode_text(data: bytes) -> str:
    """The text of a bank export, in whatever encoding the bank wrote it.

    UTF-16 announces itself with a byte-order mark. Otherwise UTF-8 is tried
    first, because text in a legacy code page is almost never valid UTF-8;
    then Windows-1252, which most legacy exports really are; then Latin-1,
    which accepts any byte, so reading never fails outright.
    """
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def join_description(*parts: str) -> str:
    """The non-empty parts, joined with " - ".

    Statements often repeat themselves — a payee name, then a memo that starts
    with the same name in full — so a part already contained in another is
    left out, and a truncated copy gives way to the longer text.
    """
    kept: list[str] = []
    for part in (" ".join(p.split()) for p in parts):
        if not part:
            continue
        if any(_contains(k, part) for k in kept):
            continue
        kept = [k for k in kept if not _contains(part, k)]
        kept.append(part)
    return " - ".join(kept)


# A part this long that starts another is a copy cut to a field's width
# ("AMAZON MKTPLACE PMTS AMZN.CO"), not a word of its own.
_TRUNCATED = 12


def _contains(text: str, part: str) -> bool:
    """Whether `part` is in `text` as whole words ("Ann" is not in "Annual
    fee"), or is a long enough start of it to be a truncated copy."""
    folded, inner = text.casefold(), part.casefold()
    if len(inner) >= _TRUNCATED and folded.startswith(inner):
        return True
    pattern = r"(?<!\w)" + re.escape(inner) + r"(?!\w)"
    return re.search(pattern, folded) is not None
