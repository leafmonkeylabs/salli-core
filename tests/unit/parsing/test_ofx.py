"""
OFX and QFX: SGML (1.x) and XML (2.x), bank and credit-card statements.
The fixtures are synthetic but laid out the way banks' exports are.
"""

from decimal import Decimal
from pathlib import Path

from salli.adapters.parsing.ofx import extract_from_ofx
from salli.adapters.parsing.support import StatementLine

FIXTURES = Path(__file__).parents[2] / "fixtures" / "statements"


def _ofx(body: str) -> bytes:
    return ("OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\n\n<OFX>" + body + "</OFX>").encode()


def test_an_ofx1_sgml_bank_statement():
    result = extract_from_ofx((FIXTURES / "ofx1_checking.ofx").read_bytes())

    assert result.errors == []
    assert result.lines == [
        StatementLine(
            date="2026-09-02",
            description="WHOLE FOODS MARKET #10 - POS PURCHASE CARD 4821",
            amount=Decimal("84.17"),
            credit_flag=False,
            currency="USD",
            bank_ref="202609020001",
        ),
        StatementLine(
            date="2026-09-15",
            description="ACME CORP PAYROLL",  # the memo only repeats the name
            amount=Decimal("3250.00"),
            credit_flag=True,
            currency="USD",
            bank_ref="202609150002",
        ),
        StatementLine(
            date="2026-09-18",
            description="CHECK - 1042",  # no name: the type and the check number
            amount=Decimal("1200.00"),
            credit_flag=False,
            currency="USD",
            bank_ref="202609180003",
        ),
        StatementLine(
            date="2026-09-20",
            description="AT&T MOBILITY - AUTOPAY",
            amount=Decimal("65.40"),
            credit_flag=False,
            currency="USD",
            bank_ref="202609200004",
        ),
        StatementLine(
            date="2026-09-24",
            description="INCOMING WIRE J SMITH LONDON",
            amount=Decimal("250.00"),
            credit_flag=True,
            currency="GBP",  # <CURRENCY>: this amount is in pounds
            bank_ref="202609240005",
        ),
        StatementLine(
            date="2026-09-27",
            description="CAFE DE FLORE PARIS - FOREIGN PURCHASE EUR 27.50",
            amount=Decimal("31.92"),
            credit_flag=False,
            currency="USD",  # <ORIGCURRENCY>: converted from euros into dollars
            bank_ref="202609270006",
        ),
        # The 0.00 card verification is not money moving, so it is not a line.
        StatementLine(
            date="2026-09-30",
            description="INTEREST PAYMENT",
            amount=Decimal("1.07"),
            credit_flag=True,
            currency="USD",
            bank_ref="202609300008",
        ),
    ]


def test_an_ofx2_xml_credit_card_statement():
    result = extract_from_ofx((FIXTURES / "ofx2_credit_card.ofx").read_bytes())

    assert result.errors == []
    assert [
        (line.date, line.description, line.amount, line.credit_flag, line.currency, line.bank_ref)
        for line in result.lines
    ] == [
        (
            "2026-09-03",
            "DB Fernverkehr - Bahnticket München–Berlin",
            Decimal("42.90"),
            False,
            "EUR",
            "CC-20260903-01",
        ),
        ("2026-09-10", "Spotify AB", Decimal("18.00"), False, "EUR", "CC-20260910-01"),
        (
            "2026-09-15",
            "AMAZON MKTPLACE PMTS AMZN.COM/BILL WA",  # the memo has the name in full
            Decimal("129.99"),
            False,
            "USD",
            "CC-20260915-01",
        ),
        ("2026-09-28", "Zahlung – vielen Dank", Decimal("500.00"), True, "EUR", "CC-20260928-01"),
    ]


def test_a_qfx_on_one_line_in_windows_1252():
    result = extract_from_ofx((FIXTURES / "quicken_savings.qfx").read_bytes())

    assert result.errors == []
    assert [(line.description, line.amount, line.credit_flag) for line in result.lines] == [
        ("CAFÉ DÉPÔT #212 - Interac purchase", Decimal("4.75"), False),
        ("PAYROLL <NORTHWIND>", Decimal("1850.00"), True),
        ("MONTHLY ACCOUNT FEE", Decimal("3.95"), False),
    ]
    assert {line.currency for line in result.lines} == {"CAD"}


def test_a_comma_is_a_decimal_point_in_ofx():
    result = extract_from_ofx(
        _ofx(
            "<BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>EUR<BANKTRANLIST>"
            "<STMTTRN><DTPOSTED>20261001<TRNAMT>-12,50<FITID>1<NAME>BOULANGERIE</STMTTRN>"
            "<STMTTRN><DTPOSTED>20261002<TRNAMT>1,234<FITID>2<NAME>VIREMENT</STMTTRN>"
            "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1>"
        )
    )
    assert [line.amount for line in result.lines] == [Decimal("12.50"), Decimal("1.234")]


def test_each_statement_keeps_its_own_currency():
    result = extract_from_ofx(
        _ofx(
            "<BANKMSGSRSV1>"
            "<STMTTRNRS><STMTRS><CURDEF>USD<BANKTRANLIST>"
            "<STMTTRN><DTPOSTED>20261001<TRNAMT>-10.00<FITID>A1<NAME>ONE</STMTTRN>"
            "</BANKTRANLIST></STMTRS></STMTTRNRS>"
            "<STMTTRNRS><STMTRS><CURDEF>MXN<BANKTRANLIST>"
            "<STMTTRN><DTPOSTED>20261001<TRNAMT>-200.00<FITID>B1<NAME>TWO</STMTTRN>"
            "</BANKTRANLIST></STMTRS></STMTTRNRS>"
            "</BANKMSGSRSV1>"
        )
    )
    assert [(line.bank_ref, line.currency) for line in result.lines] == [
        ("A1", "USD"),
        ("B1", "MXN"),
    ]


def test_an_unreadable_transaction_is_reported_and_the_rest_kept():
    result = extract_from_ofx(
        _ofx(
            "<BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>USD<BANKTRANLIST>"
            "<STMTTRN><DTPOSTED>20261341<TRNAMT>-10.00<FITID>X1<NAME>BAD DATE</STMTTRN>"
            "<STMTTRN><DTPOSTED>20261001<TRNAMT>ten<FITID>X2<NAME>BAD AMOUNT</STMTTRN>"
            "<STMTTRN><DTPOSTED>20261002<TRNAMT>-5.00<NAME>NO FITID, BAD DATE ABOVE</STMTTRN>"
            "<STMTTRN><DTPOSTED>2026<TRNAMT>-5.00<NAME>FOURTH</STMTTRN>"
            "</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1>"
        )
    )
    assert [line.description for line in result.lines] == ["NO FITID, BAD DATE ABOVE"]
    assert result.errors == [
        "OFX transaction X1: '20261341' is not a date; skipped",
        "OFX transaction X2: 'ten' is not an amount; skipped",
        "OFX transaction 4: '2026' is not a date; skipped",
    ]


def test_investment_statements_are_not_read():
    result = extract_from_ofx(
        _ofx(
            "<INVSTMTMSGSRSV1><INVSTMTTRNRS><INVSTMTRS><CURDEF>USD<INVTRANLIST>"
            "<INVBANKTRAN><STMTTRN><DTPOSTED>20261001<TRNAMT>100.00<FITID>I1"
            "<NAME>DIVIDEND</STMTTRN><SUBACCTFUND>CASH</INVBANKTRAN>"
            "</INVTRANLIST></INVSTMTRS></INVSTMTTRNRS></INVSTMTMSGSRSV1>"
        )
    )
    assert result.lines == []


def test_a_file_without_ofx_in_it():
    assert extract_from_ofx(b"Date,Amount\n").errors == [
        "This is not an OFX file: it has no <OFX> element"
    ]
