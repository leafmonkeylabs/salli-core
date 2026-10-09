"""
camt.053: entries from the .02 and the .08 schema, matched by local name
whatever the namespace; and an untrusted file with a DTD refused.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from salli.adapters.parsing.camt053 import extract_from_camt053

FIXTURES = Path(__file__).parents[2] / "fixtures" / "statements"


def _rows(result):
    return [
        (line.date, line.description, line.amount, line.credit_flag, line.currency, line.bank_ref)
        for line in result.lines
    ]


def _document(entries: str, namespace: str = "urn:iso:std:iso:20022:tech:xsd:camt.053.001.04"):
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><Document xmlns="{namespace}"><BkToCstmrStmt>'
        f"<Stmt><Acct><Ccy>EUR</Ccy></Acct>{entries}</Stmt></BkToCstmrStmt></Document>"
    ).encode()


def _entry(amount="10.00", indicator="DBIT", date="<BookgDt><Dt>2026-10-01</Dt></BookgDt>"):
    return (
        f'<Ntry><Amt Ccy="EUR">{amount}</Amt><CdtDbtInd>{indicator}</CdtDbtInd>'
        f"<Sts>BOOK</Sts>{date}<AcctSvcrRef>R-{amount}-{indicator}</AcctSvcrRef></Ntry>"
    )


def test_a_camt053_001_02_statement():
    result = extract_from_camt053((FIXTURES / "camt053_v02.xml").read_bytes())

    assert _rows(result) == [
        (
            "2026-10-01",
            "Hausverwaltung Schmidt GmbH - Miete Oktober 2026 Whg 3",
            Decimal("1200.00"),
            False,
            "EUR",
            "2026100100012345",
        ),
        (
            "2026-10-28",
            "Contoso GmbH - LOHN/GEHALT 10/2026",
            Decimal("3450.00"),
            True,
            "EUR",
            "2026102800098765",
        ),
        (
            "2026-10-05",
            "Telekom Deutschland GmbH - Kundennummer 123456789 Rechnung 10/2026",
            Decimal("54.99"),
            False,
            "EUR",
            "2026100500023456",
        ),
        # The returned direct debit: a reversal, booked as the credit it is.
        (
            "2026-10-08",
            "Ruecklastschrift Telekom Deutschland GmbH",
            Decimal("54.99"),
            True,
            "EUR",
            "2026100800034567",
        ),
        ("2026-10-31", "Kontofuehrungsentgelt", Decimal("4.90"), False, "EUR", "2026103100045678"),
    ]
    assert result.errors == ["camt.053 entry 2026110200056789: not booked yet (PDNG); skipped"]


def test_a_camt053_001_08_document_with_two_accounts():
    result = extract_from_camt053((FIXTURES / "camt053_v08.xml").read_bytes())

    assert result.errors == []
    assert _rows(result) == [
        (
            "2026-10-02",
            "Swisscom (Schweiz) AG - Rechnung 2026-10 Mobile",
            Decimal("89.50"),
            False,
            "CHF",
            "CH20261002-000731",
        ),
        # No AcctSvcrRef: the entry's own reference stands in.
        (
            "2026-10-25",
            "Example AG - Gutschrift Lohn Oktober",
            Decimal("6500.00"),
            True,
            "CHF",
            "2",
        ),
        # A batch booked as one amount: one line, all its remittance text.
        (
            "2026-10-30",
            "Elektrizitaetswerk der Stadt Zuerich - Strom Q3 2026 Steuern Rate 10/2026",
            Decimal("412.35"),
            False,
            "CHF",
            "CH20261030-001942",
        ),
        # The second statement is the EUR account; this amount has no Ccy of its own.
        (
            "2026-10-12",
            "Hotel Bellevue Como - Anzahlung Buchung 88213",
            Decimal("120.00"),
            False,
            "EUR",
            "EU20261012-000077",
        ),
    ]


def test_any_namespace_or_none():
    for namespace in ("urn:iso:std:iso:20022:tech:xsd:camt.053.001.13", ""):
        result = extract_from_camt053(_document(_entry(), namespace))
        assert [line.amount for line in result.lines] == [Decimal("10.00")]


def test_the_value_date_when_there_is_no_booking_date():
    result = extract_from_camt053(
        _document(_entry(date="<ValDt><DtTm>2026-10-03T23:30:00-05:00</DtTm></ValDt>"))
    )
    assert [line.date for line in result.lines] == ["2026-10-03"]


def test_an_unreadable_entry_is_reported_and_the_rest_kept():
    result = extract_from_camt053(
        _document(
            _entry(amount="-5.00")
            + _entry(amount="1,000.00")
            + _entry(indicator="CRDB")
            + _entry(date="")
            + _entry(amount="7.25", indicator="CRDT")
        )
    )
    assert _rows(result) == [("2026-10-01", "", Decimal("7.25"), True, "EUR", "R-7.25-CRDT")]
    assert result.errors == [
        "camt.053 entry R--5.00-DBIT: '-5.00' is not an amount; skipped",
        "camt.053 entry R-1,000.00-DBIT: '1,000.00' is not an amount; skipped",
        "camt.053 entry R-10.00-CRDB: 'CRDB' is neither credit nor debit; skipped",
        "camt.053 entry R-10.00-DBIT: no booking or value date; skipped",
    ]


@pytest.mark.parametrize(
    "document",
    [
        # Billion laughs: entities that expand to gigabytes.
        b'<?xml version="1.0"?><!DOCTYPE Document [<!ENTITY a "lol"><!ENTITY b "&a;&a;&a;&a;">]>'
        b"<Document><BkToCstmrStmt><Stmt><Ntry><AddtlNtryInf>&b;</AddtlNtryInf></Ntry>"
        b"</Stmt></BkToCstmrStmt></Document>",
        # An external entity that would read a local file.
        b'<?xml version="1.0"?><!DOCTYPE Document [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        b"<Document><BkToCstmrStmt><Stmt><Ntry><AddtlNtryInf>&x;</AddtlNtryInf></Ntry>"
        b"</Stmt></BkToCstmrStmt></Document>",
        # The same, in UTF-16, where a byte search for "<!DOCTYPE" finds nothing.
        '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE Document [<!ENTITY x "y">]>'
        "<Document><BkToCstmrStmt/></Document>".encode("utf-16"),
        # A DTD with no entities at all is still refused.
        b'<?xml version="1.0"?><!DOCTYPE Document SYSTEM "camt.053.dtd"><Document/>',
    ],
)
def test_a_document_with_a_dtd_is_refused(document):
    result = extract_from_camt053(document)
    assert result.lines == []
    assert result.errors == [
        "This XML file declares a DTD, which a bank statement never needs; refused"
    ]


def test_other_xml_is_not_a_statement():
    assert extract_from_camt053(b"<Document><BkToCstmrAcctRpt/></Document>").errors == [
        "This XML file is not a camt.053 bank statement"
    ]
    assert extract_from_camt053(b"<OFX></OFX>").errors == [
        "This XML file is not a camt.053 bank statement"
    ]
    (error,) = extract_from_camt053(b"<Document><BkToCstmrStmt>").errors
    assert error.startswith("This is not a readable XML file")


def test_each_statement_is_on_its_own_account_and_entry_refs_are_text():
    document = (
        b'<?xml version="1.0"?><Document><BkToCstmrStmt>'
        b"<Stmt><Acct><Id><IBAN>CH01</IBAN></Id><Ccy>CHF</Ccy></Acct>"
        b'<Ntry><Amt Ccy="CHF">10.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts>BOOK</Sts>'
        b"<BookgDt><Dt>2026-10-01</Dt></BookgDt><NtryRef>1</NtryRef></Ntry></Stmt>"
        b"<Stmt><Acct><Id><Othr><Id>CARD-9</Id></Othr></Id><Ccy>CHF</Ccy></Acct>"
        b'<Ntry><Amt Ccy="CHF">10.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts>'
        b"<BookgDt><Dt>2026-10-01</Dt></BookgDt><AcctSvcrRef>S-77</AcctSvcrRef></Ntry></Stmt>"
        b"</BkToCstmrStmt></Document>"
    )
    result = extract_from_camt053(document)
    assert result.accounts == ["CH01", "CARD-9"]
    assert [(line.account, line.bank_ref, line.ref_kind) for line in result.lines] == [
        ("CH01", "1", "text"),  # a statement's own entry number identifies nothing
        ("CARD-9", "S-77", "id"),
    ]


def test_a_placeholder_date_is_reported():
    result = extract_from_camt053(_document(_entry(date="<BookgDt><Dt>9999-12-31</Dt></BookgDt>")))
    assert result.lines == []
    assert "no booking or value date" in result.errors[0]
