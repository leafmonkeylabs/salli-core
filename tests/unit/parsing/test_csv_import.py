"""
CSV statements from banks around the world: the layout found from the file
(delimiter, header row, columns, decimal mark, date order), or stated with a
CsvMapping when detection would get it wrong.
"""

from decimal import Decimal
from pathlib import Path

from salli.adapters.parsing.csv_import import (
    CsvMapping,
    Table,
    extract_from_csv,
    extract_from_tables,
)

FIXTURES = Path(__file__).parents[2] / "fixtures" / "statements"


def _rows(result):
    return [
        (line.date, line.description, line.amount, line.credit_flag, line.currency, line.bank_ref)
        for line in result.lines
    ]


def test_a_us_export_with_one_signed_amount():
    result = extract_from_csv((FIXTURES / "us_checking.csv").read_bytes())

    assert result.errors == []  # the 28th and 15th prove the dates month-first
    assert _rows(result) == [
        ("2026-10-28", "WHOLE FOODS MARKET #10, SEATTLE WA", Decimal("84.17"), False, None, ""),
        ("2026-10-15", "ACME CORP PAYROLL PPD ID: 1234567890", Decimal("3250.00"), True, None, ""),
        ("2026-10-12", "CHECK 1042", Decimal("1200.00"), False, None, "1042"),
        ("2026-10-05", "AT&T MOBILITY AUTOPAY", Decimal("65.40"), False, None, ""),
        ("2026-10-02", "ZELLE PAYMENT TO JANE DOE", Decimal("1250.00"), False, None, ""),
    ]


def test_a_german_export_with_semicolons_and_decimal_commas():
    result = extract_from_csv((FIXTURES / "de_girokonto.csv").read_bytes())

    assert result.errors == []
    assert _rows(result) == [
        (
            "2026-10-01",
            "Hausverwaltung Schmidt GmbH - Miete Oktober 2026 Whg 3 - DAUERAUFTRAG",
            Decimal("1200.00"),
            False,
            "EUR",
            "",
        ),
        (
            "2026-10-05",
            "Telekom Deutschland GmbH - Kundennummer 123456789 Rechnung 10/2026 - FOLGELASTSCHRIFT",
            Decimal("54.99"),
            False,
            "EUR",
            "",
        ),
        (
            "2026-10-14",
            "Bäckerei Müller - 2026-10-13T18:22 Debitk.12 VISA Debit - KARTENZAHLUNG",
            Decimal("23.47"),
            False,
            "EUR",
            "",
        ),
        (
            "2026-10-28",
            "Contoso GmbH - LOHN/GEHALT 10/2026 - GUTSCHR. UEBERWEISUNG",
            Decimal("3450.00"),
            True,
            "EUR",
            "",
        ),
        (
            "2026-10-30",  # the booking date, not the value date beside it
            "Entgeltabrechnung siehe Anlage - ENTGELTABSCHLUSS",
            Decimal("4.90"),
            False,
            "EUR",
            "",
        ),
    ]


def test_a_uk_export_with_paid_out_and_paid_in_columns():
    result = extract_from_csv((FIXTURES / "uk_current_account.csv").read_bytes())

    assert result.errors == []
    assert _rows(result) == [
        ("2026-10-01", "Thames Water", Decimal("38.00"), False, None, ""),
        ("2026-10-03", "TESCO STORES 2041", Decimal("56.21"), False, None, ""),
        ("2026-10-07", "EMPLOYER LTD SALARY", Decimal("2850.00"), True, None, ""),
        ("2026-10-12", "Savings", Decimal("500.00"), False, None, ""),
        ("2026-10-15", "PRET A MANGER", Decimal("4.85"), False, None, ""),
        ("2026-10-31", "Interest earned", Decimal("0.42"), True, None, ""),
    ]


def test_a_dutch_export_with_a_direction_column():
    data = (
        b'"Datum","Naam / Omschrijving","Rekening","Tegenrekening","Code","Af Bij",'
        b'"Bedrag (EUR)","Mutatiesoort","Mededelingen"\r\n'
        b'"20261001","Albert Heijn 1234 AMSTERDAM","NL20INGB0001234567","","BA","Af","23,45",'
        b'"Betaalautomaat","Pasvolgnr: 001 01-10-2026 18:12"\r\n'
        b'"20261025","Werkgever BV","NL20INGB0001234567","NL91ABNA0417164300","GT","Bij",'
        b'"3.210,00","Online bankieren","Salaris oktober"\r\n'
    )
    assert _rows(extract_from_csv(data)) == [
        (
            "2026-10-01",
            "Albert Heijn 1234 AMSTERDAM - Pasvolgnr: 001 01-10-2026 18:12",
            Decimal("23.45"),
            False,
            "EUR",  # from the "Bedrag (EUR)" header
            "",
        ),
        ("2026-10-25", "Werkgever BV - Salaris oktober", Decimal("3210.00"), True, "EUR", ""),
    ]


def test_a_german_export_saying_soll_and_haben():
    data = (
        "Buchungstag;Empfänger;Verwendungszweck;Umsatz;Soll/Haben\n"
        "01.10.2026;Stadtwerke München;Abschlag Strom;85,00;S\n"
        "25.10.2026;Contoso GmbH;Gehalt;3.450,00;H\n"
    ).encode()
    assert [(line.amount, line.credit_flag) for line in extract_from_csv(data).lines] == [
        (Decimal("85.00"), False),
        (Decimal("3450.00"), True),
    ]


def test_an_indian_export_with_lakh_grouping():
    data = (
        b"Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance\n"
        b'01/10/26,UPI-SWIGGY-PAYMENT,0000627412345678,01/10/26,"1,245.00",,"1,23,455.00"\n'
        b"15/10/26,NEFT CR-ACME INDIA PVT LTD-SALARY OCT,N278262612345678,15/10/26,,"
        b'"1,50,000.00","2,73,455.00"\n'
    )
    result = extract_from_csv(data)
    assert result.errors == []
    assert _rows(result) == [
        ("2026-10-01", "UPI-SWIGGY-PAYMENT", Decimal("1245.00"), False, None, "0000627412345678"),
        (
            "2026-10-15",
            "NEFT CR-ACME INDIA PVT LTD-SALARY OCT",
            Decimal("150000.00"),
            True,
            None,
            "N278262612345678",
        ),
    ]


def test_ambiguous_dates_are_reported_and_can_be_overridden():
    data = b"Date,Description,Amount\n10/01/2026,A,-1.00\n10/05/2026,B,-2.00\n"

    guessed = extract_from_csv(data)
    assert [line.date for line in guessed.lines] == ["2026-10-01", "2026-10-05"]
    (notice,) = guessed.errors
    assert "month first (MDY)" in notice

    told = extract_from_csv(data, date_order="DMY")
    assert [line.date for line in told.lines] == ["2026-01-10", "2026-05-10"]
    assert told.errors == []


def test_a_file_without_a_header_row():
    data = (
        b'"10/01/2026","-45.67","*","","WHOLE FOODS MARKET SEATTLE WA"\n'
        b'"10/02/2026","2400.00","*","","ACME PAYROLL DIR DEP"\n'
        b'"10/15/2026","-12.00","*","1043","CHECK # 1043"\n'
    )
    result = extract_from_csv(data)
    assert [
        (line.date, line.description, line.amount, line.credit_flag) for line in result.lines
    ] == [
        ("2026-10-01", "WHOLE FOODS MARKET SEATTLE WA", Decimal("45.67"), False),
        ("2026-10-02", "ACME PAYROLL DIR DEP", Decimal("2400.00"), True),
        ("2026-10-15", "CHECK # 1043", Decimal("12.00"), False),
    ]
    assert result.errors == [
        "This file has no header row Salli recognises, so column 1 was read as the date, "
        "column 2 as the amount and column 5 as the description. If that is wrong, import it "
        "with a column mapping."
    ]


def test_a_file_whose_columns_cannot_be_told_apart():
    data = b"10/01/2026,WHOLE FOODS,-45.67,1000.00\n10/02/2026,PAYROLL,2400.00,3400.00\n"
    assert extract_from_csv(data).errors == [
        "Couldn't tell which columns hold the date and the amount in this CSV file"
    ]


def test_a_mapping_by_header_name_with_a_date_format():
    data = "Buchung;Text;Soll;Haben;Währung\n01.10.2026;Miete;1.200,00;;EUR\n".encode()
    mapping = CsvMapping(
        date="Buchung",
        description="Text",
        debit="Soll",
        credit="Haben",
        currency="Währung",
        date_format="%d.%m.%Y",
    )
    assert _rows(extract_from_csv(data, mapping)) == [
        ("2026-10-01", "Miete", Decimal("1200.00"), False, "EUR", "")
    ]


def test_a_mapping_by_position_for_a_card_that_shows_spending_as_positive():
    data = b"10/01/2026,UBER *TRIP,23.40,Travel\n10/03/2026,PAYMENT RECEIVED - THANK YOU,-500.00,\n"
    mapping = CsvMapping(date=0, description=(1, 3), amount=2, invert_sign=True, date_order="MDY")
    assert _rows(extract_from_csv(data, mapping)) == [
        ("2026-10-01", "UBER *TRIP - Travel", Decimal("23.40"), False, None, ""),
        ("2026-10-03", "PAYMENT RECEIVED - THANK YOU", Decimal("500.00"), True, None, ""),
    ]


def test_a_mapping_that_does_not_fit_the_file():
    data = (FIXTURES / "us_checking.csv").read_bytes()
    assert extract_from_csv(data, CsvMapping(date="Datum", amount="Bedrag")).errors == [
        "No row of this CSV file has the columns 'Datum', 'Bedrag'"
    ]
    assert extract_from_csv(data, CsvMapping(date=1)).errors == [
        "A CSV mapping needs an amount column, or debit and credit columns"
    ]


def test_rows_that_are_not_transactions_are_passed_over_and_bad_ones_reported():
    data = (
        b"Date,Description,Amount\n"
        b"31/02/2026,Bad date,-1.00\n"
        b"13/03/2026,Bad amount,abc\n"
        b"14/03/2026,Fine,-3.00\n"
        b"15/03/2026,Opening balance,\n"
        b",,\n"
        b"Total,,-4.00\n"
    )
    result = extract_from_csv(data)
    assert [line.description for line in result.lines] == ["Fine"]
    assert result.errors == [
        "Row 2: '31/02/2026' is not a date; skipped",
        "Row 3: 'abc' is not an amount; skipped",
    ]


def test_money_both_out_and_in_on_one_row_is_reported():
    data = b"Date,Description,Debit,Credit\n13/03/2026,Odd,5.00,6.00\n14/03/2026,Fine,0.00,7.00\n"
    result = extract_from_csv(data)
    assert [(line.description, line.amount, line.credit_flag) for line in result.lines] == [
        ("Fine", Decimal("7.00"), True)
    ]
    assert result.errors == ["Row 2: both money out ('5.00') and money in ('6.00'); skipped"]


def test_the_currency_from_a_column_or_written_with_the_amount():
    data = (
        b"Date,Description,Amount,Currency\n"
        b"2026-10-01,Hotel,-120.00,eur\n"
        b"2026-10-02,Taxi,USD -15.50,\n"
        b"2026-10-03,Coffee,-3.20,\n"
    )
    assert [line.currency for line in extract_from_csv(data).lines] == ["eur", "USD", None]


def test_other_delimiters():
    excel_hint = b"sep=;\nDate;Description;Amount\n2026-10-01;Coffee;-3,20\n"
    tabs = b"Date\tDescription\tAmount\n2026-10-01\tRent\t-1200.00\n"
    assert extract_from_csv(excel_hint).lines[0].amount == Decimal("3.20")
    assert extract_from_csv(tabs).lines[0].amount == Decimal("1200.00")


# The naive CSV path this replaced handled these; they still work.


def test_debit_and_credit_columns_as_sri_lankan_banks_export_them():
    rows = extract_from_csv(b"Date,Description,Debit,Credit\n25/04/2025,Salary,,300000.00\n").lines
    assert [(r.date, r.amount, r.credit_flag) for r in rows] == [
        ("2025-04-25", Decimal("300000.00"), True)
    ]


def test_latin1_text():
    data = "Date,Description,Debit,Credit\n25/04/2025,Caf\xe9,,1500.00\n".encode("latin-1")
    assert [line.description for line in extract_from_csv(data).lines] == ["Café"]


def test_no_header_name_means_two_things():
    from collections import Counter

    from salli.adapters.parsing.csv_import import _HEADERS

    names = Counter(name for names in _HEADERS.values() for name in names)
    assert [name for name, count in names.items() if count > 1] == []


# Tables from elsewhere: a spreadsheet's sheets, a PDF's pages.


def test_tables_on_several_pages_are_one_statement():
    first = Table(
        [
            ["Statement of account", ""],
            ["Date", "Description", "Debit", "Credit", "Balance"],
            ["01/10/2026", "Rent", "1,200.00", "", "1,340.12"],
        ],
        label="Page 1, row",
        page=1,
    )
    # The next page carries on without repeating the header.
    second = Table(
        [
            ["13/10/2026", "Salary", "", "3,450.00", "4,790.12"],
            ["31/02/2026", "Misprint", "1.00", "", "4,789.12"],
        ],
        label="Page 2, row",
        page=2,
    )

    result = extract_from_tables([first, second])

    assert result is not None
    assert [(line.date, line.description, line.source_page) for line in result.lines] == [
        ("2026-10-01", "Rent", 1),  # day-first: the 13th on page 2 settles it
        ("2026-10-13", "Salary", 2),
    ]
    assert result.errors == ["Page 2, row 2: '31/02/2026' is not a date; skipped"]


def test_tables_that_are_no_statement():
    summary = Table([["Opening balance", "1,340.12"], ["Closing balance", "4,790.12"]])
    assert extract_from_tables([summary, summary]) is None
    # The only table, read by what its columns hold, when that is allowed.
    dated = Table([["01/10/2026", "Rent", "-1,200.00"], ["13/10/2026", "Salary", "3,450.00"]])
    assert extract_from_tables([dated], infer=False) is None
    assert extract_from_tables([dated]) is not None
