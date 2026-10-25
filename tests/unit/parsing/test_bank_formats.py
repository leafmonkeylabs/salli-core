"""
Bank layouts as data (`salli.bankformat/1`): every market pack's formats load,
read their synthetic sample, and are the one picked from all of them.
"""

import csv
import io
import json
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
