"""
CSV statements from any bank.

Every bank lays out its CSV export its own way, so the layout is read from the
file itself: the delimiter (comma, semicolon, tab or pipe); the header row,
after any lines about the account above it; which columns hold the date, the
payee and description, and the amount — one signed amount, money out and
money in as two columns, or an amount beside a column saying which way it
went; and how the file writes its numbers and dates (amounts.py, dates.py).
Headers are recognised in English, German, French, Spanish, Italian,
Portuguese and Dutch. A file with no header row is read when its columns can
still be told apart by what is in them, and says which columns it took.

When the detection gets a bank wrong, a `CsvMapping` states the layout
outright, and is meant to be saved per bank.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal

from salli.adapters.parsing.amounts import (
    amount_mark,
    currency_code_in,
    decimal_mark_for,
    detect_decimal_separator,
    is_blank_amount,
    parse_decimal,
)
from salli.adapters.parsing.dates import (
    DateOrder,
    candidate_orders,
    detect_date_order,
    find_date,
    parse_date,
)
from salli.adapters.parsing.support import (
    Extraction,
    RefKind,
    StatementLine,
    decode_text,
    join_description,
    looks_like_id,
)
from salli.domain.currency import exponent, is_currency

Column = str | int


@dataclass(frozen=True)
class CsvMapping:
    """A bank's CSV layout, stated instead of detected.

    Columns are named by their header (matched ignoring case, accents and
    punctuation) or by 0-based position. Give `amount` for one signed column
    (negative is money out), or `debit` (money out) and `credit` (money in);
    `direction` names a column saying which way an unsigned amount went
    (CR/DR, Credit/Debit, S/H, Af/Bij, ...). Several description columns are
    joined in the order given.
    """

    date: Column
    description: Column | tuple[Column, ...] = ()
    amount: Column | None = None
    debit: Column | None = None
    credit: Column | None = None
    direction: Column | None = None
    currency: Column | None = None
    reference: Column | None = None
    date_format: str | None = None  # strptime, e.g. "%d.%m.%Y"; wins over any date order
    date_order: DateOrder | None = None
    decimal_separator: str | None = None  # "." or ","
    delimiter: str | None = None
    invert_sign: bool = False  # some card issuers export money spent as positive


@dataclass
class _Layout:
    """Where things are in one particular file."""

    date: int
    text: list[int] = field(default_factory=list[int])  # payee, description, memo
    amount: int | None = None
    debit: int | None = None
    credit: int | None = None
    direction: int | None = None
    currency: int | None = None
    reference: int | None = None
    header_row: int | None = None  # index into the table; None without a header
    header_currency: str | None = None  # "Amount (EUR)"
    #: The reference column holds cheque numbers, never ids.
    cheque_reference: bool = False


# Header names, folded (lower case, no accents, punctuation as spaces, "/"
# kept), by role. Earlier names win when a file has several: a booking date
# beats a value date, a description beats a memo.
_HEADERS: dict[str, list[str]] = {
    "date": [
        "date", "transaction date", "trans date", "txn date", "tran date", "booking date",
        "booked date", "posting date", "posted date", "post date", "entry date",
        "completed date", "date posted", "operation date", "buchungstag", "buchungsdatum",
        "datum", "date operation", "date de l operation", "date comptable", "fecha",
        "fecha operacion", "fecha de operacion", "fecha contable", "data", "data operazione",
        "data contabile", "data movimento", "data lancamento", "data de lancamento",
        "boekdatum", "transactiedatum", "started date", "value date", "value dt", "valuta",
        "valutadatum", "wertstellung", "date valeur", "date de valeur", "fecha valor",
        "data valuta", "data valor", "rentedatum",
    ],
    "payee": [
        "payee", "payee name", "name", "merchant", "merchant name", "counterparty",
        "counter party", "counterparty name", "beneficiary", "beneficiary name", "payer",
        "payer name", "other party", "recipient", "beguenstigter/zahlungspflichtiger",
        "begunstigter/zahlungspflichtiger", "auftraggeber/zahlungsempfanger",
        "auftraggeber/empfanger", "auftraggeber/beguenstigter", "auftraggeber/begunstigter",
        "empfanger/zahlungspflichtiger", "zahlungsempfanger", "empfanger",
        "name zahlungsbeteiligter", "naam/omschrijving", "naam", "tegenpartij",
        "beneficiaire", "tiers", "beneficiario", "ordenante", "controparte",
    ],
    "description": [
        "description", "transaction description", "details", "transaction details",
        "narration", "narrative", "particulars", "transaction particulars",
        "payment details", "transaction remarks", "verwendungszweck",
        "vorgang/verwendungszweck", "umsatztext", "beschreibung", "libelle",
        "libelle operation", "libelle de l operation", "detail", "concepto", "descripcion",
        "detalle", "descrizione", "descrizione operazione", "causale", "omschrijving",
        "descricao", "historico", "descritivo",
    ],
    "memo": [
        "memo", "notes", "note", "notes and tags", "remarks", "payment reference",
        "reference text", "message", "additional information", "additional info",
        "buchungstext", "mededelingen", "commentaire", "observaciones",
    ],
    "amount": [
        "amount", "transaction amount", "amt", "value", "net amount", "betrag", "umsatz",
        "montant", "importe", "monto", "cantidad", "importo", "bedrag", "valor", "montante",
    ],
    "debit": [
        "debit", "debits", "debit amount", "dr", "dr amount", "withdrawal", "withdrawals",
        "withdrawal amount", "withdrawal amt", "paid out", "money out", "out", "outflow",
        "outgoing", "spent", "soll", "ausgang", "ausgaben", "belastung", "debito", "cargo",
        "cargos", "debe", "salida", "salidas", "addebiti", "addebito", "uscite", "dare",
        "af", "saida", "saidas",
    ],
    "credit": [
        "credit", "credits", "credit amount", "cr", "cr amount", "deposit", "deposits",
        "deposit amount", "deposit amt", "paid in", "money in", "in", "inflow", "incoming",
        "received", "haben", "eingang", "einnahmen", "gutschrift", "credito", "abono",
        "abonos", "haber", "ingreso", "ingresos", "entrada", "entradas", "accrediti",
        "accredito", "entrate", "avere", "bij",
    ],
    "direction": [
        "dr/cr", "cr/dr", "debit/credit", "credit/debit", "d/c", "c/d", "drcr", "crdr",
        "dr cr", "cr dr", "af bij", "af/bij", "soll/haben", "s/h", "direction",
        "transaction direction", "debit credit indicator", "credit debit indicator",
        "in/out",
    ],
    "currency": [
        "currency", "ccy", "curr", "currency code", "waehrung", "wahrung", "devise", "divisa",
        "moneda", "munt", "moeda",
    ],
    "reference": [
        "reference", "ref", "ref no", "ref number", "reference no", "reference number",
        "transaction reference", "transaction ref", "txn ref", "transaction id", "txn id",
        "transaction number", "id", "fitid", "bank reference", "cheque no", "chq no",
        "cheque number", "check number", "check no", "check or slip", "chq/ref no",
        "ref no/cheque no", "cheque/ref no", "kundenreferenz", "referenz", "bankreferenz",
        "referencia", "riferimento", "referentie",
    ],
}  # fmt: skip

_ROLES: dict[str, tuple[str, int]] = {
    name: (role, rank) for role, names in _HEADERS.items() for rank, name in enumerate(names)
}

# What a direction column says. Folded like headers.
_DIRECTIONS: dict[str, bool] = {
    **dict.fromkeys(
        ["cr", "c", "credit", "h", "haben", "bij", "in", "incoming", "deposit", "+", "credito",
         "avere", "abono", "haber", "gutschrift", "crdt", "money in", "paid in", "accredito",
         "accredit", "entrata", "entrada", "ingreso", "eingang", "inflow", "received",
         "credit transaction", "cr txn", "credited", "versement", "credit card payment"],
        True,
    ),
    **dict.fromkeys(
        ["dr", "d", "debit", "s", "soll", "af", "out", "outgoing", "withdrawal", "-", "debito",
         "dare", "cargo", "debe", "lastschrift", "dbit", "belastung", "debet", "money out",
         "paid out", "addebito", "addebit", "uscita", "salida", "ausgang", "outflow",
         "debit transaction", "dr txn", "debited", "retrait", "prelevement", "payment out"],
        False,
    ),
}  # fmt: skip

# Header words in brackets that say which way an amount column went:
# "Amount (credit)", "Betrag (Soll)".
_SIDES: dict[str, str] = {
    **dict.fromkeys(["credit", "cr", "haben", "h", "in", "money in", "deposit"], "credit"),
    **dict.fromkeys(["debit", "dr", "soll", "s", "out", "money out", "withdrawal"], "debit"),
}

# Cheque numbers are references, but a cheque book's numbers say nothing
# about which bank transaction a row is.
_CHEQUE_HEADERS = {
    "cheque no", "chq no", "cheque number", "check number", "check no", "check or slip",
}  # fmt: skip

# A line longer than this is no bank's CSV row: refuse the file rather than
# read past csv's field size limit.
_MAX_LINE = 100_000

_DELIMITERS = (",", ";", "\t", "|")
_HEADER_SCAN = 30  # rows searched for the header, past account details above it


@dataclass(frozen=True)
class Table:
    """Rows of cells from one place: a CSV file, a spreadsheet's sheet, a
    table on a PDF page."""

    rows: list[list[str]]
    #: How its rows are named in messages: "Row 5", "Page 2, row 5".
    label: str = "Row"
    #: The page its lines came from (`StatementLine.source_page`).
    page: int = 0


def extract_from_csv(
    data: bytes,
    mapping: CsvMapping | None = None,
    *,
    date_order: DateOrder | None = None,
    prefer_order: DateOrder = "DMY",
    currency: str | None = None,
) -> Extraction:
    """Every transaction in a CSV statement.

    `date_order` overrides the order detected from the file's dates (and the
    mapping's); `prefer_order` is the one to take when the dates genuinely
    read either way. `currency` is the statement's, when known: its decimals
    settle a decimal mark the amounts leave open.
    """
    text = decode_text(data)
    if any(len(line) > _MAX_LINE for line in text.splitlines()):
        return Extraction(
            errors=[
                f"This file has a line longer than {_MAX_LINE:,} characters: not a CSV statement"
            ]
        )
    delimiter = mapping.delimiter if mapping and mapping.delimiter else None
    # Excel's "sep=;" first line names the delimiter.
    hint = re.match(r"sep=(.)\r?\n", text)
    if hint:
        delimiter, text = delimiter or hint.group(1), text[hint.end() :]
    try:
        delimiter = delimiter or _sniff_delimiter(text)
        table = [
            [c.strip() for c in row] for row in csv.reader(io.StringIO(text), delimiter=delimiter)
        ]
    except csv.Error as exc:
        return Extraction(errors=[f"This CSV file could not be read: {exc}"])

    result = extract_from_tables(
        [Table(table)],
        mapping,
        date_order=date_order,
        prefer_order=prefer_order,
        currency=currency,
        # With no value to say, a semicolon file is from a country that writes
        # decimal commas: that is why its columns are not separated by commas.
        decimal_mark="," if delimiter == ";" else ".",
    )
    return result or Extraction(
        errors=["Couldn't tell which columns hold the date and the amount in this CSV file"]
    )


def extract_from_tables(
    tables: Sequence[Table],
    mapping: CsvMapping | None = None,
    *,
    date_order: DateOrder | None = None,
    prefer_order: DateOrder = "DMY",
    currency: str | None = None,
    decimal_mark: str = ".",
    infer: bool = True,
    unread: list[Table] | None = None,
) -> Extraction | None:
    """Every transaction in tables of cells, read as one statement: the date
    order and the decimal mark are decided from all of them at once. None
    when no table looks like a statement.

    A table without a header Salli knows is read as the next page of the
    statement table before it when it is as wide; and, when it is the only
    table and `infer` allows, by what its columns hold. Tables that could not
    be laid out at all are added to `unread`, when given.
    """
    result = Extraction()
    laid_out: list[tuple[Table, _Layout]] = []
    previous: tuple[_Layout, int] | None = None  # the last layout with a header, and its width
    for table in tables:
        width = max((len(row) for row in table.rows), default=0)
        if mapping is not None:
            found = _layout_from_mapping(table.rows, mapping)
            if isinstance(found, str):
                result.errors.append(found)
                continue
            layout: _Layout | None = found
        else:
            layout = _layout_from_header(table.rows)
            if layout is None and previous is not None and previous[1] == width:
                # A statement's next page often repeats no header.
                layout = replace(previous[0], header_row=None)
            elif layout is None and infer and len(tables) == 1:
                layout = _layout_from_content(table.rows, result)
        if layout is None:
            if unread is not None:
                unread.append(table)
            continue
        if layout.header_row is not None:
            previous = (layout, width)
        laid_out.append((table, layout))
    if not laid_out:
        return Extraction(errors=result.errors) if result.errors else None

    date_format = mapping.date_format if mapping else None

    def date_text(row: list[str], layout: _Layout) -> str:
        # A date cell may carry more: "02/10/2026*", "Mon 01/10/2026", or
        # two dates stacked in one cell, the first being the transaction's.
        cell = _cell(row, layout.date)
        return cell if date_format else (find_date(cell) or cell)

    # Transaction rows are the ones with a date, or something meant to be one.
    # The rest (blank lines, account details, totals) are passed over.
    rows: list[tuple[Table, _Layout, int, list[str]]] = []
    undated: list[tuple[Table, _Layout, int, list[str]]] = []
    for table, layout in laid_out:
        for number, row in enumerate(table.rows, 1):
            if layout.header_row is not None and number - 1 <= layout.header_row:
                continue
            text = date_text(row, layout)
            if candidate_orders(text) is not None or (
                date_format is not None and _date(text, date_format, "DMY")
            ):
                rows.append((table, layout, number, row))
            elif any(ch.isdigit() for ch in text):
                undated.append((table, layout, number, row))

    order = date_order or (mapping.date_order if mapping else None)
    if order is None and date_format is None:
        order, notice = detect_date_order(
            (date_text(row, layout) for _, layout, _, row in rows), prefer=prefer_order
        )
        if notice:
            result.errors.append(notice)
    places = _exponent(currency)
    money_cells = [
        _cell(row, column)
        for _, layout, _, row in rows
        for column in (layout.amount, layout.debit, layout.credit)
        if column is not None
    ]
    mark = (mapping.decimal_separator if mapping else None) or decimal_mark_for(
        money_cells, places, decimal_mark
    )
    invert = mapping.invert_sign if mapping else False

    # A row that looks like a transaction (it has an amount) but whose date
    # can't be read is said, never dropped silently.
    for table, layout, number, row in undated:
        try:
            if _amount(row, layout, mark, invert, _Direction()) is not None:
                result.errors.append(
                    f"{table.label} {number}: {_cell(row, layout.date)!r} is not a date; skipped"
                )
        except ValueError:
            continue

    directions = _directions(rows, result)
    if directions is None:
        return result
    references = _reference_kinds(rows)

    for table, layout, number, row in rows:
        label = f"{table.label} {number}"
        text = date_text(row, layout)
        date = _date(text, date_format, order or prefer_order)
        if date is None:
            result.errors.append(f"{label}: {_cell(row, layout.date)!r} is not a date; skipped")
            continue
        try:
            found_amount = _amount(row, layout, mark, invert, directions[id(layout)])
        except ValueError as exc:
            result.errors.append(f"{label}: {exc}; skipped")
            continue
        if found_amount is None:
            continue  # no amount, or zero: nothing moved
        amount, credit, code = found_amount
        reference = _cell(row, layout.reference)
        kind = references.get(id(layout), "text")
        description = join_description(*(_cell(row, i) for i in layout.text))
        if reference and kind == "text":
            # Words someone typed, or a cheque number: part of what the row
            # says, never the bank's id for it.
            description = join_description(description, reference)
        result.lines.append(
            StatementLine(
                date=date,
                description=description,
                amount=amount,
                credit_flag=credit,
                currency=_cell(row, layout.currency) or code or layout.header_currency,
                bank_ref=reference,
                source_page=table.page,
                ref_kind=kind,
            )
        )
    return result


def _exponent(currency: str | None) -> int | None:
    if not currency or not is_currency(currency):
        return None
    return exponent(currency)


@dataclass
class _Direction:
    """How a layout's rows say which way their money went, beyond a sign.

    `unmarked`: in an amount column where some values carry a CR or DR mark
    and the rest none, which way the unmarked ones went (a card statement
    marks only its credits, "15000.00 CR"). None when that does not apply."""

    unmarked: bool | None = None


def _directions(
    rows: list[tuple[Table, _Layout, int, list[str]]], result: Extraction
) -> dict[int, _Direction] | None:
    """What each layout's amounts and direction column say about direction,
    by the layout's id. Also finds a direction column by its content when no
    header named one (a blank-headed S/H column, a "Type" column of DR/CR).
    None, with an error, when a direction column holds nothing Salli can read."""
    found: dict[int, _Direction] = {}
    layouts: dict[int, _Layout] = {id(layout): layout for _, layout, _, _ in rows}
    for layout_id, layout in layouts.items():
        mine = [row for _, lay, _, row in rows if id(lay) == layout_id]
        info = found[layout_id] = _Direction()
        if layout.amount is None:
            continue
        signed = any(_cell(row, layout.amount).strip().startswith(("-", "(")) for row in mine)
        if layout.direction is None and not signed:
            # Unsigned amounts with no direction column named: a column may
            # still say which way, under a blank or generic header.
            layout.direction = _direction_by_content(mine, layout)
        if layout.direction is not None:
            said = [v for v in (_cell(row, layout.direction) for row in mine) if v]
            if said and not any(_said(v) is not None for v in said):
                result.errors.append(
                    f"Column {layout.direction + 1} says which way each amount went, but in "
                    f"words Salli doesn't know ({said[0]!r}), so nothing was imported. Use "
                    "a file with signed amounts or separate money in and out columns"
                )
                return None
            continue
        amounts = [_cell(row, layout.amount) for row in mine]
        live = [a for a in amounts if not is_blank_amount(a)]
        marked = {m for m in (amount_mark(a) for a in live) if m}
        bare = [a for a in live if amount_mark(a) is None and not a.strip().startswith(("-", "("))]
        if len(marked) == 1 and bare:
            (side,) = marked
            info.unmarked = side == "DR"
            result.errors.append(
                f"Only some amounts are marked {side}; the unmarked ones were read as money "
                f"{'in' if info.unmarked else 'out'}, as statements that mark one side print them"
            )
    return found


def _said(value: str) -> bool | None:
    """Which way a direction cell says the money went, or None if it doesn't."""
    return _DIRECTIONS.get(_fold(value) or value.strip())  # "+" and "-" fold to nothing


def _direction_by_content(rows: list[list[str]], layout: _Layout) -> int | None:
    """A column that, by what it holds, says which way each amount went: every
    value a direction word, both ways present, and not a column already taken."""
    taken = {layout.date, layout.amount, layout.currency, layout.reference, *layout.text}
    width = max((len(row) for row in rows), default=0)
    for column in range(width):
        if column in taken:
            continue
        values = [v for v in (_cell(row, column) for row in rows) if v]
        if len(values) < 2:
            continue
        read = [_said(v) for v in values]
        known = [r for r in read if r is not None]
        if len(known) == len(values) and len(set(known)) == 2:
            return column
    return None


def _reference_kinds(rows: list[tuple[Table, _Layout, int, list[str]]]) -> dict[int, RefKind]:
    """Whether each layout's reference column holds ids: unique within the
    file and every one id-shaped (`support.looks_like_id`), and not a column
    of cheque numbers. Anything else is text."""
    kinds: dict[int, RefKind] = {}
    by_layout: dict[int, list[str]] = {}
    cheques: dict[int, bool] = {}
    for _, layout, _, row in rows:
        if layout.reference is None:
            continue
        by_layout.setdefault(id(layout), []).append(_cell(row, layout.reference))
        cheques[id(layout)] = layout.cheque_reference
    for layout_id, values in by_layout.items():
        present = [v for v in values if v]
        ids = (
            not cheques[layout_id]
            and present
            and len(set(present)) == len(present)
            and all(looks_like_id(v) for v in present)
        )
        kinds[layout_id] = "id" if ids else "text"
    return kinds


def _amount(
    row: list[str], layout: _Layout, mark: str, invert: bool, directions: _Direction
) -> tuple[Decimal, bool, str | None] | None:
    """(amount, money in?, currency code written with it), or None when the
    row moves no money. Raises ValueError for an amount that can't be read,
    or a direction that can't."""
    if layout.amount is not None:
        text = _cell(row, layout.amount)
        if is_blank_amount(text):
            return None
        value = _read(text, mark)
        if value == 0:
            return None
        written = amount_mark(text)
        if layout.direction is not None:
            way = _cell(row, layout.direction)
            said = _said(way) if way else None
            if said is None and (way or value > 0):
                # A direction column that says nothing readable is not
                # guessed past: these layouts print unsigned amounts.
                raise ValueError(f"{way!r} does not say whether money went in or out")
            credit = said if said is not None else False
        elif written is None and directions.unmarked is not None and value > 0:
            credit = directions.unmarked != invert
        elif written is not None:
            credit = written == "CR"  # a mark is the bank's word; never inverted
        else:
            credit = (value < 0) == invert
        return abs(value), credit, currency_code_in(text)

    out_text, in_text = _cell(row, layout.debit), _cell(row, layout.credit)
    out = Decimal(0) if is_blank_amount(out_text) else _read(out_text, mark)
    into = Decimal(0) if is_blank_amount(in_text) else _read(in_text, mark)
    if out and into:
        raise ValueError(f"both money out ({out_text!r}) and money in ({in_text!r})")
    if not out and not into:
        return None
    # The column says which way; a sign as well (-45.67 under "Debit") is
    # just how some banks print the same thing. The currency is the one
    # written on the side that moved, not on a "0.00" beside it.
    return abs(out or into), bool(into), currency_code_in(in_text if into else out_text)


def _read(text: str, mark: str) -> Decimal:
    try:
        return parse_decimal(text, mark)
    except ValueError:
        raise ValueError(f"{text!r} is not an amount") from None


def _date(text: str, date_format: str | None, order: DateOrder) -> str | None:
    if date_format:
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            return None
    return parse_date(text, order)


def _cell(row: list[str], column: int | None) -> str:
    return row[column] if column is not None and column < len(row) else ""


def _fold(text: str) -> str:
    """Lower case, without accents, punctuation as single spaces, "/" kept."""
    folded = "".join(
        ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch)
    )
    folded = re.sub(r"[^\w/]|_", " ", folded)
    return " ".join(re.sub(r"\s*/\s*", "/", folded).split())


def _header(cell: str) -> tuple[str, str | None]:
    """A header's folded name, and the currency it names ("Bedrag (EUR)",
    "Withdrawal Amount (INR )", "Amount GBP"). Only a bracketed currency code
    is taken out of the name: "Amount (credit)" stays itself."""
    code = next(
        (
            inner.strip().upper()
            for inner in re.findall(r"\(([^)]*)\)", cell)
            if re.fullmatch(r"\s*[A-Za-z]{3}\s*", inner) and is_currency(inner.strip())
        ),
        None,
    )
    if code is not None:
        cell = re.sub(r"\(\s*" + code + r"\s*\)", " ", cell, flags=re.I)
    words = cell.split()
    if code is None and len(words) > 1 and words[-1].isupper() and is_currency(words[-1]):
        code, words = words[-1], words[:-1]
    return _fold(" ".join(words)), code


def _role(cell: str) -> tuple[str, int] | None:
    """(role, rank) of a header cell, or None.

    A known name wins. Otherwise a bracketed note may say which way an amount
    column went ("Amount (credit)", "Betrag (Soll)"), and any other bracketed
    note ("Date (dd/mm/yyyy)") is set aside."""
    name, _ = _header(cell)
    if name in _ROLES:
        return _ROLES[name]
    notes = [_fold(inner) for inner in re.findall(r"\(([^)]*)\)", cell)]
    base = _fold(re.sub(r"\([^)]*\)", " ", cell))
    if base not in _ROLES:
        return None
    role, rank = _ROLES[base]
    side = next((_SIDES[n] for n in notes if n in _SIDES), None)
    if side is not None and role in ("amount", "debit", "credit"):
        return side, -1  # as plain as a header gets
    return role, rank


def _sniff_delimiter(text: str) -> str:
    """The delimiter on which most lines agree about a number of columns
    above one; ties go to the one giving more columns."""
    sample = [line for line in text.splitlines()[:50] if line.strip()]
    # Raises csv.Error for a field past csv's size limit; the caller says so.
    best, best_score = ",", (0, 0)
    for delimiter in _DELIMITERS:
        widths = Counter(len(row) for row in csv.reader(sample, delimiter=delimiter))
        for width, rows in widths.items():
            if width > 1 and (rows, width) > best_score:
                best, best_score = delimiter, (rows, width)
    return best


def _layout_from_header(table: list[list[str]]) -> _Layout | None:
    """The layout named by the first row that reads as a header."""
    for index, row in enumerate(table[:_HEADER_SCAN]):
        best: dict[str, tuple[int, int]] = {}  # role -> (rank, column)
        codes: dict[int, str] = {}
        below = table[index + 1] if index + 1 < len(table) else []
        for column, cell in enumerate(row):
            found = _role(cell)
            if found is None:
                continue
            role, rank = found
            name, code = _header(cell)
            if name == "value" and "date" in (
                _header(_cell(row, column + 1))[0],
                _header(_cell(below, column))[0],
            ):
                continue  # "Value | Date": a value date's header split in two
            if role not in best or rank < best[role][0]:
                best[role] = (rank, column)
            if code:
                codes[column] = code
        columns = {role: column for role, (_, column) in best.items()}
        if "date" not in columns or not {"amount", "debit", "credit"} & columns.keys():
            continue
        # Money out and money in as two columns are the plainest truth: an
        # unsigned "Amount" beside them (a total, a running figure) must not
        # override them. Else one signed amount column.
        split = {"debit", "credit"} <= columns.keys() or "amount" not in columns
        reference = columns.get("reference")
        layout = _Layout(
            date=columns["date"],
            text=[columns[r] for r in ("payee", "description", "memo") if r in columns],
            amount=None if split else columns.get("amount"),
            debit=columns.get("debit") if split else None,
            credit=columns.get("credit") if split else None,
            direction=columns.get("direction"),
            currency=columns.get("currency"),
            reference=reference,
            header_row=index,
            cheque_reference=reference is not None
            and _header(row[reference])[0] in _CHEQUE_HEADERS,
        )
        money = [c for c in (layout.amount, layout.debit, layout.credit) if c is not None]
        layout.header_currency = next((codes[c] for c in money if c in codes), None)
        return layout
    return None


def _layout_from_mapping(table: list[list[str]], mapping: CsvMapping) -> _Layout | str:
    """The layout a mapping states, or why it does not fit this file."""
    descriptions = (
        mapping.description if isinstance(mapping.description, tuple) else (mapping.description,)
    )
    named = [
        c
        for c in (mapping.date, *descriptions, mapping.amount, mapping.debit, mapping.credit,
                  mapping.direction, mapping.currency, mapping.reference)
        if isinstance(c, str)
    ]  # fmt: skip
    header_row: int | None = None
    positions: dict[str, int] = {}
    if named:
        wanted = {_header(name)[0] for name in named}
        for index, row in enumerate(table[:_HEADER_SCAN]):
            folded = [_header(cell)[0] for cell in row]
            if wanted <= set(folded):
                header_row = index
                positions = {name: folded.index(name) for name in wanted}
                break
        else:
            return f"No row of this CSV file has the columns {', '.join(map(repr, named))}"

    def column(c: Column) -> int:
        return c if isinstance(c, int) else positions[_header(c)[0]]

    def optional(c: Column | None) -> int | None:
        return None if c is None else column(c)

    if mapping.amount is None and mapping.debit is None and mapping.credit is None:
        return "A CSV mapping needs an amount column, or debit and credit columns"
    return _Layout(
        date=column(mapping.date),
        text=[column(c) for c in descriptions],
        amount=optional(mapping.amount),
        debit=optional(mapping.debit),
        credit=optional(mapping.credit),
        direction=optional(mapping.direction),
        currency=optional(mapping.currency),
        reference=optional(mapping.reference),
        header_row=header_row,
    )


def _layout_from_content(table: list[list[str]], result: Extraction) -> _Layout | None:
    """For a file without a header row Salli knows: the first column that is
    nearly all dates, the one column of amounts (written with a decimal mark
    or a sign, so not a column of cheque numbers), and the longest text. What
    was taken is said, so the user can check it."""
    rows = [row for row in table if any(row)]
    width = max((len(row) for row in rows), default=0)

    def values(column: int, among: list[list[str]]) -> list[str]:
        return [v for v in (_cell(row, column) for row in among) if v]

    def mostly(column: int, among: list[list[str]], test: Callable[[str], bool]) -> bool:
        found = values(column, among)
        return len(found) >= 2 and sum(map(test, found)) >= 0.8 * len(found)

    def date_like(value: str) -> bool:
        return candidate_orders(value) is not None

    def amount_like(value: str) -> bool:
        try:
            parse_decimal(value, detect_decimal_separator([value]) or ".")
        except ValueError:
            return False
        return bool(re.search(r"[.,()-]", value))

    date = next((c for c in range(width) if mostly(c, rows, date_like)), None)
    if date is None:
        return None
    dated = [row for row in rows if date_like(_cell(row, date))]
    amounts = [c for c in range(width) if c != date and mostly(c, dated, amount_like)]
    if len(amounts) != 1:
        return None
    (amount,) = amounts
    worded = [
        c
        for c in range(width)
        if c not in (date, amount) and any(re.search(r"[^\W\d_]", v) for v in values(c, dated))
    ]
    text = max(worded, key=lambda c: sum(len(v) for v in values(c, dated)), default=None)
    result.errors.append(
        f"This file has no header row Salli recognises, so column {date + 1} was read as "
        f"the date, column {amount + 1} as the amount"
        + (f" and column {text + 1} as the description" if text is not None else "")
        + ". If that is wrong, set the date order (--date-order), or give the file a header"
        " row naming its columns (Date, Description, Amount)."
    )
    return _Layout(date=date, amount=amount, text=[] if text is None else [text])
