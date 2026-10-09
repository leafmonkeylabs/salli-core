"""
How an uploaded statement reaches the right importer, and the rules every
format then shares: the file's own currency wins over the caller's, a code
that is not a currency is reported rather than booked, a bank reference that
repeats within a file is not trusted to tell transactions apart, and what
could not be read ends up in ParseResult.errors.
"""

from __future__ import annotations

import io
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import openpyxl
import pytest

import salli.adapters.parsing.llm_classifier as llm_classifier
from salli.application.services.parsing_service import (
    ParsingService,
    _extract,
    _statement_format,
)
from salli.domain.parsing.models import ParsedTransaction, RawRow

FIXTURES = Path(__file__).parents[2] / "fixtures" / "statements"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _xlsx(rows: list[list[Any]]) -> bytes:
    workbook = openpyxl.Workbook()
    for row in rows:
        workbook.active.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("filename", "fixture", "expected"),
    [
        ("statement.ofx", "ofx1_checking.ofx", "ofx"),
        ("statement.qfx", "quicken_savings.qfx", "ofx"),
        ("statement.qif", "quicken_us.qif", "qif"),
        ("statement.xml", "camt053_v02.xml", "camt053"),
        ("statement.sta", "mt940_de.sta", "mt940"),
        ("statement.csv", "us_checking.csv", "csv"),
        # The content decides when the name is missing or misleading.
        ("download", "ofx2_credit_card.ofx", "ofx"),
        ("export.xml", "ofx2_credit_card.ofx", "ofx"),
        ("transactions.csv", "quicken_us.qif", "qif"),
        ("Kontoauszug", "camt053_v08.xml", "camt053"),
        ("statement.txt", "mt940_de.sta", "mt940"),
        ("statement.pdf", "mt940_de.sta", "mt940"),
        ("statement", "de_girokonto.csv", "csv"),
    ],
)
def test_the_file_reaches_the_right_importer(filename, fixture, expected):
    assert _statement_format(filename, _fixture(fixture)) == expected


def test_pdf_and_excel_are_found_as_before():
    assert _statement_format("statement", b"%PDF-1.7\n...") == "pdf"
    assert _statement_format("statement.pdf", b"not really a pdf") == "pdf"
    assert _statement_format("statement", _xlsx([["Date"]])) == "xlsx"
    assert _statement_format("statement.xls", b"\xd0\xcf\x11\xe0\x00\x00") == "xlsx"


def test_a_file_nothing_can_read():
    rows, errors = _extract("photo", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", "LKR")
    assert rows == []
    assert errors == [
        "Salli can't read this file. It reads PDF, Excel (.xlsx), CSV, OFX/QFX, QIF, "
        "camt.053 and MT940 statements"
    ]


def test_a_currency_the_file_names_wins_over_the_callers():
    rows, errors = _extract("statement.ofx", _fixture("ofx1_checking.ofx"), "LKR")
    assert errors == []
    assert [row.currency for row in rows] == ["USD", "USD", "USD", "USD", "GBP", "USD", "USD"]

    rows, _ = _extract("statement.sta", _fixture("mt940_de.sta"), "LKR")
    assert {row.currency for row in rows} == {"EUR", "USD"}


def test_a_file_that_names_no_currency_is_in_the_callers():
    rows, _ = _extract("statement.qif", _fixture("quicken_us.qif"), "USD")
    assert {row.currency for row in rows} == {"USD"}

    rows, _ = _extract("statement.csv", _fixture("uk_current_account.csv"), "GBP")
    assert {row.currency for row in rows} == {"GBP"}


def test_codes_are_checked_and_normalized():
    data = (
        b"Date,Description,Amount,Currency\n"
        b"2026-10-01,Hotel,-120.00,eur\n"
        b"2026-10-02,Shop,-15.50,EURO\n"
        b"2026-10-03,Cafe,-3.20,EURO\n"
        b"2026-10-04,Market,-7.00,\n"
    )
    rows, errors = _extract("statement.csv", data, "LKR")
    assert [(row.description, row.currency) for row in rows] == [
        ("Hotel", "EUR"),
        ("Market", "LKR"),
    ]
    assert errors == ["Skipped 2 transaction(s) in 'EURO', which is not an ISO 4217 currency code"]


def test_a_reference_that_repeats_within_a_file_is_not_used():
    # Two different transactions sharing a reference would otherwise be taken
    # for one by the dedup matcher, and the second silently dropped.
    data = (
        b"Date,Description,Amount,Reference\n"
        b"2026-10-01,Transfer to J Perera,-50000.00,TXN123\n"
        b"2026-10-01,Transfer fee,-25.00,TXN123\n"
        b"2026-10-02,Salary,300000.00,TXN124\n"
    )
    rows, _ = _extract("statement.csv", data, "LKR")
    assert [(row.description, row.bank_ref) for row in rows] == [
        ("Transfer to J Perera", ""),
        ("Transfer fee", ""),
        ("Salary", "TXN124"),
    ]


def test_excel_rows_are_extracted_as_before():
    data = _xlsx(
        [
            ["Date", "Description", "Debit", "Credit", "Ref"],
            ["25/04/2025", "Salary", "", "300000.00", "R1"],
            ["30/04/2025", "Electricity", "4500.00", "", "R2"],
        ]
    )
    rows, errors = _extract("statement.xlsx", data, "LKR")
    assert errors == []
    assert rows == [
        RawRow("2025-04-25", "Salary", Decimal("300000.00"), True, "LKR", "R1", 1),
        RawRow("2025-04-30", "Electricity", Decimal("4500.00"), False, "LKR", "R2", 1),
    ]


def test_the_date_order_and_a_csv_mapping_reach_the_importer():
    from salli.adapters.parsing.csv_import import CsvMapping

    data = b"When,What,How much\n01/02/2026,Rent,-1200.00\n"
    mapping = CsvMapping(date="When", description="What", amount="How much")
    rows, errors = _extract("s.csv", data, "LKR", date_order="MDY", csv_mapping=mapping)
    assert [(row.date, row.description, row.amount) for row in rows] == [
        ("2026-01-02", "Rent", Decimal("1200.00"))
    ]
    assert errors == []


# ── Through the service ───────────────────────────────────────────────────────


class _Uow:
    def __init__(self, saved: list[Any]) -> None:
        self.ledger = self
        self.statements = self
        self._saved = saved

    async def get_accounts(self, user_id: str, **_: Any) -> list[Any]:
        return [SimpleNamespace(id="a", type="asset", is_active=True)]

    async def get_entries(self, user_id: str, **_: Any) -> list[Any]:
        return []

    async def imported_between(self, user_id: str, from_date: str, to_date: str) -> list[Any]:
        return []

    async def save_statement(self, **kwargs: Any) -> None:
        self._saved.append(kwargs)


async def test_what_the_importer_could_not_read_reaches_the_result(monkeypatch):
    async def classify(rows: list[RawRow], accounts: Any, **_: Any) -> list[ParsedTransaction]:
        return [
            ParsedTransaction(raw=row, debit_account_id="d", credit_account_id="c") for row in rows
        ]

    monkeypatch.setattr(llm_classifier, "classify_transactions", classify)
    saved: list[Any] = []

    @asynccontextmanager
    async def uow_factory():
        yield _Uow(saved)

    result = await ParsingService(uow_factory).parse_statement(
        "u1", "statement.xml", _fixture("camt053_v02.xml"), currency="LKR", api_key="k"
    )

    assert [t.raw.currency for t in result.transactions] == ["EUR"] * 5
    assert (result.period_start, result.period_end) == ("2026-10-01", "2026-10-31")
    assert result.errors == ["camt.053 entry 2026110200056789: not booked yet (PDNG); skipped"]
    assert len(saved[0]["transactions"]) == 5


async def test_a_file_that_yields_nothing_says_why():
    refused = (
        b'<?xml version="1.0"?><!DOCTYPE Document [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        b"<Document><BkToCstmrStmt/></Document>"
    )
    result = await ParsingService(uow_factory=None).parse_statement(
        "u1", "statement.xml", refused, currency="EUR"
    )
    assert result.transactions == []
    assert result.errors == [
        "This XML file declares a DTD, which a bank statement never needs; refused",
        "No transactions found in the file. Check the format is supported",
    ]
