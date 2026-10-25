"""
Bank layouts as data (`salli.bankformat/1`): every market pack's formats load,
read their synthetic sample, and are the one picked from all of them.
"""

import csv
import io
import json
from decimal import Decimal
from pathlib import Path

import pytest

from salli.adapters.parsing.bankformat import load_bank_format, pick
from salli.adapters.parsing.csv_import import extract_from_csv
from salli.application.services.parsing_service import load_bank_formats

MARKETS = Path(__file__).resolve().parents[3] / "markets"
FILES = sorted(MARKETS.glob("*/banks/*.json"))


def _documents():
    return {path: json.loads(path.read_text()) for path in FILES}


def _rows_with_amounts(text: str) -> int:
    """The sample's transactions: its dated rows, less a stated balance."""
    rows = list(csv.reader(io.StringIO(text)))
    return sum(1 for row in rows if row and row[0][:1].isdigit() and "BALANCE" not in row[1])


@pytest.mark.parametrize("path", FILES, ids=lambda p: f"{p.parents[1].name}/{p.stem}")
def test_each_format_reads_its_sample_and_is_picked_among_all(path: Path):
    documents = _documents()
    doc = documents[path]
    assert "sources" in doc and "verified" in doc
    sample = (path.parent / doc["sample"]).read_bytes()
    formats = [load_bank_format(d) for d in documents.values()]
    own = load_bank_format(doc)

    alone = extract_from_csv(sample, own.mapping)
    assert len(alone.lines) == _rows_with_amounts(sample.decode()) > 0

    chosen, outcomes = pick(formats, lambda m: extract_from_csv(sample, m))
    assert [o.name for o in outcomes if o.chosen] == [own.name]
    assert len(chosen.lines) == len(alone.lines)
    mine = next(o for o in outcomes if o.name == own.name)
    assert mine.parsed == len(alone.lines)
    assert all(o.parsed == 0 for o in outcomes if o is not mine)
    if "balance" in doc["columns"]:
        # The running balance gives the statement's own opening and closing.
        [(opening, closing)] = alone.balances.values()
        moved = sum((ln.amount if ln.credit_flag else -ln.amount for ln in alone.lines), Decimal(0))
        assert opening is not None and opening + moved == closing


EXAMPLE = {
    "schema": "salli.bankformat/1",
    "name": "Banco Ficticio",
    "columns": {"date": "Fecha", "description": ["Concepto"], "amount": "Importe"},
    "date_format": "%d.%m.%Y",
    "decimal_separator": ",",
    "thousands_separator": ".",
    "delimiter": ";",
}


def test_a_decimal_comma_layout_is_read_as_stated():
    data = b"Fecha;Concepto;Importe\n03.02.2026;Alquiler;-1.250,40\n"
    result = extract_from_csv(data, load_bank_format(EXAMPLE).mapping)
    assert [(line.date, str(line.amount), line.credit_flag) for line in result.lines] == [
        ("2026-02-03", "1250.40", False)
    ]


@pytest.mark.parametrize(
    ("change", "says"),
    [
        ({"schema": "salli.tax/1"}, "schema"),
        ({"name": ""}, "name"),
        ({"columns": {"date": "Fecha"}}, "amount column"),
        ({"thousands_separator": ","}, "thousands"),
        ({"surprise": 1}, "unknown keys"),
        ({"date_order": "DDD"}, "date_order"),
    ],
)
def test_a_wrong_document_says_what_is_wrong(change, says):
    with pytest.raises(ValueError, match=says):
        load_bank_format({**EXAMPLE, **change})


def test_no_format_fitting_is_said_with_every_count():
    data = b"When,What,How much\n2026-01-02,Rent,-10.00\n"
    formats = load_bank_formats(json.dumps([EXAMPLE]))
    result, outcomes = pick(formats, lambda m: extract_from_csv(data, m))
    assert result.lines == [] and "No row matched" in result.errors[-1]
    assert [(o.parsed, o.chosen) for o in outcomes] == [(0, False)]
    assert outcomes[0].failed >= 1


def test_the_importer_counts_each_format_it_tried():
    from salli.application.services.parsing_service import (
        _extract,  # pyright: ignore[reportPrivateUsage]
    )

    other = {**EXAMPLE, "name": "Otro", "columns": {"date": "Día", "amount": "Suma"}}
    data = b"Fecha;Concepto;Importe\n03.02.2026;Alquiler;-1.250,40\n"
    outcomes = []
    rows, _ = _extract(
        "s.csv", data, "EUR", bank_formats=load_bank_formats(json.dumps([other, EXAMPLE])),
        outcomes=outcomes,
    )  # fmt: skip
    assert len(rows) == 1
    assert [(o.name, o.parsed, o.chosen) for o in outcomes] == [
        ("Otro", 0, False),
        ("Banco Ficticio", 1, True),
    ]


async def test_checking_a_statement_reads_it_and_stores_nothing():
    from unittest.mock import MagicMock

    from salli.application.services.parsing_service import ParsingService

    sample = b"""Fecha;Concepto;Importe;Saldo
01.10.2026;Saldo anterior;;1.000,00
02.10.2026;Nomina;2.500,00;3.500,00
05.10.2026;Alquiler;-900,00;2.600,00
"""
    doc = {**EXAMPLE, "columns": {**EXAMPLE["columns"], "balance": "Saldo"}}
    uow = MagicMock()
    result = await ParsingService(uow).check(
        "u1", "octubre.csv", sample, currency="EUR", bank_formats=[load_bank_format(doc)]
    )
    uow.assert_not_called()
    assert result["transactions"] == 2
    assert (result["money_in"], result["money_out"]) == (Decimal("2500"), Decimal("900"))
    assert (result["opening_balance"], result["closing_balance"]) == (
        Decimal("1000"),
        Decimal("2600"),
    )
    assert result["balances_agree"] is True
    assert (result["first_date"], result["last_date"]) == ("2026-10-02", "2026-10-05")
