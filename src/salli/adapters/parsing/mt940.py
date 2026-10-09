"""
SWIFT MT940 statements.

Banks across Europe, the Middle East and Asia offer MT940 as their
"accounting software" export. It is a run of tagged fields: :20: starts a
statement, :60F: (:60M: on a continuation page) is the opening balance and
names the currency, each :61: is a transaction, and the :86: after it
describes that transaction over as many lines as it needs.

A :61: packs its subfields together without separators:

    2610011002DR12,50NTRFNONREF//B6J1001ABCD

value date 261001, entry (booking) date 1002, mark D, funds code R (EUR's
third letter, optional), amount 12,50, transaction type NTRF, then the
customer's reference and, after //, the bank's. The mark is C or D, or RC/RD
for the reversal of a credit or a debit, which moves money the other way.
Amounts always use a comma as the decimal mark.
"""

from __future__ import annotations

import datetime
import re
from decimal import Decimal

from salli.adapters.parsing.dates import full_year
from salli.adapters.parsing.support import Extraction, StatementLine, decode_text, join_description

_FIELD = re.compile(r"^:(\d{2}[A-Z]?|NS):", re.M)
_BALANCE = re.compile(r"[CD]\d{6}([A-Z]{3})")
_TRANSACTION = re.compile(
    r"(?P<value>\d{6})(?P<entry>\d{4})?"
    r"(?P<mark>RC|RD|C|D)[A-Z]?"
    r"(?P<amount>\d+(?:,\d*)?)"
    r"[A-Z][A-Z0-9]{3}"
    r"(?P<customer>.*?)(?://(?P<bank>.*))?"
)

# German banks structure :86: into ?NN subfields. These are the ones a person
# reads: the posting text (00), the purpose (20-29, 60-63) and the other
# party's name (32-33). The rest are codes, bank and account numbers.
_STRUCTURED = re.compile(r"(?:\d{3})?\?\d{2}")
_SUBFIELD = re.compile(r"\?(\d{2})")


def extract_from_mt940(data: bytes) -> Extraction:
    """Every transaction in the statements of an MT940 file."""
    text = decode_text(data).replace("\r\n", "\n").replace("\r", "\n")
    # The SWIFT header block can run straight into the first field ("{4::20:").
    text = text.replace("{4:", "{4:\n")
    starts = list(_FIELD.finditer(text))
    fields = [
        (match.group(1), _content(text[match.end() : end]))
        for match, end in zip(starts, [m.start() for m in starts[1:]] + [len(text)], strict=True)
    ]
    tags = {tag for tag, _ in fields}
    if "34F" in tags and not tags & {"60F", "60M"}:
        return Extraction(
            errors=["This is an MT942 interim report, not a statement; import the MT940 instead"]
        )

    result = Extraction()
    currency: str | None = None
    pending: tuple[int, list[str], str | None] | None = None  # a :61: awaiting its :86:
    seen = 0
    for tag, lines in fields:
        if tag == "86" and pending is not None:
            _add(*pending, _information(lines), result)
            pending = None
            continue
        if pending is not None:
            _add(*pending, "", result)
            pending = None
        if tag == "20":
            currency = None
        elif tag in ("60F", "60M"):
            match = _BALANCE.match(lines[0].strip()) if lines else None
            currency = match.group(1) if match else None
        elif tag == "61":
            seen += 1
            pending = (seen, lines, currency)
    if pending is not None:
        _add(*pending, "", result)
    return result


def _content(raw: str) -> list[str]:
    """A field's lines, up to the end of its message ("-}", a lone "-") or
    the next message's header block."""
    lines: list[str] = []
    for line in raw.split("\n"):
        if line.strip() in ("-", "}") or line.lstrip().startswith(("-}", "{")):
            break
        lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _add(
    number: int, lines: list[str], currency: str | None, information: str, result: Extraction
) -> None:
    first = lines[0].strip() if lines else ""
    match = _TRANSACTION.fullmatch(first)
    if match is None:
        result.errors.append(f"MT940 transaction {number}: {first!r} is not a :61: line; skipped")
        return
    date = _date(match.group("value"), match.group("entry"))
    if date is None:
        result.errors.append(
            f"MT940 transaction {number}: {first[:10]!r} has no real date; skipped"
        )
        return
    amount = Decimal(match.group("amount").replace(",", "."))
    if amount == 0:
        return

    customer = match.group("customer").strip()
    bank = (match.group("bank") or "").strip()
    result.lines.append(
        StatementLine(
            date=date,
            # Without a :86:, the :61:'s own supplementary details, if any.
            description=information or _unwrap([line.strip() for line in lines[1:]], 34),
            amount=amount,
            credit_flag=match.group("mark") in ("C", "RD"),
            currency=currency,
            bank_ref=bank or ("" if customer.upper() == "NONREF" else customer),
        )
    )


def _date(value: str, entry: str | None) -> str | None:
    """The entry (booking) date if the line has one, else the value date.

    The entry date comes without a year. It takes whichever year puts it
    nearest the value date: booked 2 January for a value date of 31 December
    is the next year.
    """
    try:
        value_date = datetime.date(full_year(int(value[:2])), int(value[2:4]), int(value[4:]))
    except ValueError:
        return None
    if not entry:
        return value_date.isoformat()
    candidates: list[datetime.date] = []
    for year in (value_date.year - 1, value_date.year, value_date.year + 1):
        try:
            candidates.append(datetime.date(year, int(entry[:2]), int(entry[2:])))
        except ValueError:
            continue
    if not candidates:
        return None
    return min(candidates, key=lambda d: abs((d - value_date).days)).isoformat()


def _information(lines: list[str]) -> str:
    """The text of a :86: field."""
    joined = "".join(lines).strip()
    if not _STRUCTURED.match(joined):
        return _unwrap(lines, 65)
    # Structured: the line breaks are only wrapping, the ?NN codes divide it.
    parts = _SUBFIELD.split(joined)
    posting: list[str] = []
    name: list[str] = []
    purpose: list[str] = []
    for code, text in zip(parts[1::2], parts[2::2], strict=True):
        if code == "00":
            posting.append(text)
        elif code in ("32", "33"):
            name.append(text)
        elif "20" <= code <= "29" or "60" <= code <= "63":
            purpose.append(text)
    return join_description(_unwrap(posting, 27), _unwrap(name, 27), _unwrap(purpose, 27))


def _unwrap(pieces: list[str], width: int) -> str:
    """Pieces of text that were cut to `width` characters, joined again.

    A piece that fills its width was cut mid-text, so the next one continues
    it directly ("Okt" + "ober"); a shorter one ended, so a space follows.
    """
    text = ""
    for i, piece in enumerate(pieces):
        if i and len(pieces[i - 1]) < width:
            text += " "
        text += piece
    return " ".join(text.split())
