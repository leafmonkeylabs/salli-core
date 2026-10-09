"""
What every statement importer returns, and the small helpers they share.

An importer reads one file format and reports each transaction exactly as the
file states it. It does not decide the currency of a row whose file names
none, and it does not check the codes it reads: `parsing_service` does both,
the same way for every format, when it turns these lines into `RawRow`s.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


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


@dataclass
class Extraction:
    """An importer's result: the lines it read, and what it could not read."""

    lines: list[StatementLine] = field(default_factory=list[StatementLine])
    errors: list[str] = field(default_factory=list[str])


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
        folded = part.casefold()
        if any(folded in k.casefold() for k in kept):
            continue
        kept = [k for k in kept if k.casefold() not in folded]
        kept.append(part)
    return " - ".join(kept)
