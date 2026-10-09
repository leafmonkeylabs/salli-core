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
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from salli.adapters.parsing.amounts import (
    currency_code_in,
    detect_decimal_separator,
    parse_decimal,
)
from salli.adapters.parsing.dates import DateOrder, candidate_orders, detect_date_order, parse_date
from salli.adapters.parsing.support import Extraction, StatementLine, decode_text, join_description
from salli.domain.currency import is_currency

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
         "avere", "abono", "haber", "gutschrift"],
        True,
    ),
    **dict.fromkeys(
        ["dr", "d", "debit", "s", "soll", "af", "out", "outgoing", "withdrawal", "-", "debito",
         "dare", "cargo", "debe", "lastschrift"],
        False,
    ),
}  # fmt: skip

_DELIMITERS = (",", ";", "\t", "|")
_HEADER_SCAN = 30  # rows searched for the header, past account details above it


def extract_from_csv(
    data: bytes, mapping: CsvMapping | None = None, *, date_order: DateOrder | None = None
) -> Extraction:
    """Every transaction in a CSV statement.

    `date_order` overrides the order detected from the file's dates (and the
    mapping's).
    """
    result = Extraction()
    text = decode_text(data)
    delimiter = mapping.delimiter if mapping and mapping.delimiter else None
    # Excel's "sep=;" first line names the delimiter.
    hint = re.match(r"sep=(.)\r?\n", text)
    if hint:
        delimiter, text = delimiter or hint.group(1), text[hint.end() :]
    delimiter = delimiter or _sniff_delimiter(text)
    try:
        table = [
            [c.strip() for c in row] for row in csv.reader(io.StringIO(text), delimiter=delimiter)
        ]
    except csv.Error as exc:
        return Extraction(errors=[f"This CSV file could not be read: {exc}"])

    if mapping is not None:
        layout = _layout_from_mapping(table, mapping)
        if isinstance(layout, str):
            return Extraction(errors=[layout])
    else:
        layout = _layout_from_header(table) or _layout_from_content(table, result)
        if layout is None:
            return Extraction(
                errors=["Couldn't tell which columns hold the date and the amount in this CSV file"]
            )

    date_format = mapping.date_format if mapping else None
    # Transaction rows are the ones with a date, or something meant to be one.
    # The rest (blank lines, account details, totals) are passed over.
    rows = [
        (number, row)
        for number, row in enumerate(table, 1)
        if (layout.header_row is None or number - 1 > layout.header_row)
        and (
            candidate_orders(_cell(row, layout.date)) is not None
            or (date_format is not None and _date(_cell(row, layout.date), date_format, "DMY"))
        )
    ]
    order = date_order or (mapping.date_order if mapping else None)
    if order is None and date_format is None:
        order, notice = detect_date_order(_cell(row, layout.date) for _, row in rows)
        if notice:
            result.errors.append(notice)
    mark = (mapping.decimal_separator if mapping else None) or detect_decimal_separator(
        _cell(row, column)
        for _, row in rows
        for column in (layout.amount, layout.debit, layout.credit)
        if column is not None
    )
    # With no value to say, a semicolon file is from a country that writes
    # decimal commas: that is why its columns are not separated by commas.
    mark = mark or ("," if delimiter == ";" else ".")
    invert = mapping.invert_sign if mapping else False

    for number, row in rows:
        date_text = _cell(row, layout.date)
        date = _date(date_text, date_format, order or "DMY")
        if date is None:
            result.errors.append(f"Row {number}: {date_text!r} is not a date; skipped")
            continue
        try:
            found = _amount(row, layout, mark, invert)
        except ValueError as exc:
            result.errors.append(f"Row {number}: {exc}; skipped")
            continue
        if found is None:
            continue  # no amount, or zero: nothing moved
        amount, credit, code = found
        result.lines.append(
            StatementLine(
                date=date,
                description=join_description(*(_cell(row, i) for i in layout.text)),
                amount=amount,
                credit_flag=credit,
                currency=_cell(row, layout.currency) or code or layout.header_currency,
                bank_ref=_cell(row, layout.reference),
            )
        )
    return result


def _amount(
    row: list[str], layout: _Layout, mark: str, invert: bool
) -> tuple[Decimal, bool, str | None] | None:
    """(amount, money in?, currency code written with it), or None when the
    row moves no money. Raises ValueError for an amount that can't be read."""
    if layout.amount is not None:
        text = _cell(row, layout.amount)
        if not text:
            return None
        value = _read(text, mark)
        if value == 0:
            return None
        way = _cell(row, layout.direction)
        said = _DIRECTIONS.get(_fold(way) or way)  # "+" and "-" fold to nothing
        credit = said if said is not None else (value < 0) == invert
        return abs(value), credit, currency_code_in(text)

    out_text, in_text = _cell(row, layout.debit), _cell(row, layout.credit)
    out = _read(out_text, mark) if out_text else Decimal(0)
    into = _read(in_text, mark) if in_text else Decimal(0)
    if out and into:
        raise ValueError(f"both money out ({out_text!r}) and money in ({in_text!r})")
    if not out and not into:
        return None
    # The column says which way; a sign as well (-45.67 under "Debit") is
    # just how some banks print the same thing.
    return abs(out or into), bool(into), currency_code_in(out_text or in_text)


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
    "Withdrawal Amount (INR )", "Amount GBP")."""
    code = next(
        (
            inner.strip().upper()
            for inner in re.findall(r"\(([^)]*)\)", cell)
            if re.fullmatch(r"\s*[A-Za-z]{3}\s*", inner) and is_currency(inner.strip())
        ),
        None,
    )
    words = re.sub(r"\([^)]*\)", " ", cell).split()
    if code is None and len(words) > 1 and words[-1].isupper() and is_currency(words[-1]):
        code, words = words[-1], words[:-1]
    return _fold(" ".join(words)), code


def _sniff_delimiter(text: str) -> str:
    """The delimiter on which most lines agree about a number of columns
    above one; ties go to the one giving more columns."""
    sample = [line for line in text.splitlines()[:50] if line.strip()]
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
        for column, cell in enumerate(row):
            name, code = _header(cell)
            if name not in _ROLES:
                continue
            role, rank = _ROLES[name]
            if role not in best or rank < best[role][0]:
                best[role] = (rank, column)
            if code:
                codes[column] = code
        columns = {role: column for role, (_, column) in best.items()}
        if "date" not in columns or not {"amount", "debit", "credit"} & columns.keys():
            continue
        # One signed amount column, if there is one, is the simplest truth.
        split = "amount" not in columns
        layout = _Layout(
            date=columns["date"],
            text=[columns[r] for r in ("payee", "description", "memo") if r in columns],
            amount=columns.get("amount"),
            debit=columns.get("debit") if split else None,
            credit=columns.get("credit") if split else None,
            direction=columns.get("direction"),
            currency=columns.get("currency"),
            reference=columns.get("reference"),
            header_row=index,
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
        f"This CSV file has no header row Salli recognises, so column {date + 1} was read as "
        f"the date, column {amount + 1} as the amount"
        + (f" and column {text + 1} as the description" if text is not None else "")
        + ". If that is wrong, import it with a column mapping."
    )
    return _Layout(date=date, amount=amount, text=[] if text is None else [text])
