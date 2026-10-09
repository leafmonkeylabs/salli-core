"""
MT940: :61: transactions with their :86: descriptions, structured or free,
reversals, the currency from each statement's opening balance, and dates
that cross a year end.
"""

import dataclasses
from decimal import Decimal
from pathlib import Path

from salli.adapters.parsing.mt940 import extract_from_mt940
from salli.adapters.parsing.support import StatementLine

FIXTURES = Path(__file__).parents[2] / "fixtures" / "statements"


def _statement(*fields: str, currency: str = "EUR") -> bytes:
    return "\r\n".join(
        [":20:REF", ":25:12345678/0001234567", f":60F:C261001{currency}100,00", *fields, "-"]
    ).encode()


def test_a_german_bank_export_of_two_statements():
    result = extract_from_mt940((FIXTURES / "mt940_de.sta").read_bytes())

    assert result.errors == []
    # Two statements, on two accounts (:25:).
    assert result.accounts == ["37040044/0532013000", "37040044/0532013001"]
    assert [dataclasses.replace(line, account="") for line in result.lines] == [
        StatementLine(
            date="2026-10-01",
            description=(
                "SEPA-UEBERWEISUNG - Hausverwaltung Schmidt GmbH - "
                "EREF+NOTPROVIDED SVWZ+Miete Oktober 2026 Whg 3"
            ),
            amount=Decimal("1200.00"),
            credit_flag=False,
            currency="EUR",
            bank_ref="026100100012345",
        ),
        StatementLine(
            date="2026-10-05",
            # ?23 is a full 27 characters, so ?24 carries on the same number.
            description=(
                "SEPA-BASISLASTSCHRIFT - Telekom Deutschland GmbH - EREF+TDG-2026-10-998877 "
                "MREF+M-123456789 CRED+DE12ZZZ00000012345 SVWZ+Kundennummer 1234567890 "
                "Rechnung 10/2026"
            ),
            amount=Decimal("54.99"),
            credit_flag=False,
            currency="EUR",
            bank_ref="026100500023456",
        ),
        # RD: the reversal of a debit brings the money back.
        StatementLine(
            date="2026-10-08",
            description="RÜCKLASTSCHRIFT - Telekom Deutschland GmbH - Rückgabe mangels Deckung",
            amount=Decimal("54.99"),
            credit_flag=True,
            currency="EUR",
            bank_ref="026100800034567",
        ),
        StatementLine(
            date="2026-10-28",
            description="SEPA-GUTSCHRIFT - Contoso GmbH - SVWZ+LOHN/GEHALT 10/2026",
            amount=Decimal("3450.00"),
            credit_flag=True,
            currency="EUR",
            bank_ref="026102800098765",  # the bank's reference wins over the customer's
        ),
        # The second statement is in dollars. Valued 31 December, booked 2 January.
        StatementLine(
            date="2027-01-02",
            description=(
                "Wire transfer to Northwind Traders Inc Invoice INV-2026-1187 "
                "consulting services December 2026"
            ),
            amount=Decimal("250"),
            credit_flag=False,
            currency="USD",
            bank_ref="026123100011111",
        ),
        StatementLine(
            date="2026-12-31",
            description="",  # no :86: at all
            amount=Decimal("15"),
            credit_flag=True,
            currency="USD",
            bank_ref="",  # NONREF is no reference
        ),
    ]


def test_the_reversal_of_a_credit_takes_the_money_back_out():
    result = extract_from_mt940(_statement(":61:261002RC12,50NTRFREF-77", ":86:Storno Gutschrift"))
    assert [(line.credit_flag, line.amount, line.bank_ref) for line in result.lines] == [
        (False, Decimal("12.50"), "REF-77")  # no bank reference: the customer's
    ]


def test_a_free_text_line_of_full_width_continues_on_the_next():
    text = "Payment for the annual maintenance contract of the office building in Colombo"
    result = extract_from_mt940(
        # Wrapped at 65 characters, in the middle of "building".
        _statement(":61:2610021002D100,NTRFNONREF", f":86:{text[:65]}", text[65:])
    )
    assert result.lines[0].description == text


def test_the_header_block_may_run_into_the_first_field():
    data = b"{1:F01BANKLKLXAXXX0000000000}{2:I940BANKLKLXXXXXN}{4::20:S1\r\n" + _statement(
        ":61:2610021002C5000,00NTRFNONREF", ":86:Salary", currency="LKR"
    )
    result = extract_from_mt940(data)
    assert [(line.amount, line.currency) for line in result.lines] == [(Decimal("5000.00"), "LKR")]


def test_without_an_opening_balance_the_currency_is_left_to_the_caller():
    data = b":20:S1\r\n:25:123\r\n:61:2610021002D5,00NTRFNONREF\r\n:86:Fee\r\n-"
    assert [line.currency for line in extract_from_mt940(data).lines] == [None]


def test_an_unreadable_transaction_is_reported_and_the_rest_kept():
    result = extract_from_mt940(
        _statement(
            ":61:2613011301D5,00NTRFNONREF",  # month 13
            ":86:Bad date",
            ":61:garbage",
            ":61:2610021002D7,00NTRFNONREF",
            ":86:Good",
        )
    )
    assert [line.description for line in result.lines] == ["Good"]
    assert result.errors == [
        "MT940 transaction 1: '2613011301' has no real date; skipped",
        "MT940 transaction 2: 'garbage' is not a :61: line; skipped",
    ]


def test_an_mt942_interim_report_is_refused():
    data = b":20:S1\r\n:25:123\r\n:28C:1\r\n:34F:EURD0,\r\n:13D:2610021200+0100\r\n" + (
        b":61:2610021002D5,00NTRFNONREF\r\n:86:Pending card payment\r\n-"
    )
    result = extract_from_mt940(data)
    assert result.lines == []
    assert result.errors == [
        "This is an MT942 interim report, not a statement; import the MT940 instead"
    ]


def test_a_non_swift_field_between_a_transaction_and_its_description():
    result = extract_from_mt940(
        _statement(":61:2610021002D9,99NTRFNONREF", ":NS:22Kartenzahlung", ":86:Netflix")
    )
    assert [line.description for line in result.lines] == ["Netflix"]


def test_no_reference_written_as_such_is_no_reference():
    data = _statement(
        ":61:2610011001DR12,50NTRFNOTPROVIDED//NONREF",
        ":86:Fee",
        ":61:2610021002DR3,00NTRFCUST-7",
        ":86:Coffee",
    )
    lines = extract_from_mt940(data).lines
    # The customer's own reference is text, never the bank's id.
    assert [(line.bank_ref, line.ref_kind) for line in lines] == [("", "id"), ("CUST-7", "text")]
