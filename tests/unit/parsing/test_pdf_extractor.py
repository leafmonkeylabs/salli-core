"""
Unit tests for the PDF extractor helper functions.
No real PDF files needed — tests feed structured data directly.
"""

from decimal import Decimal

from salli.adapters.parsing.pdf_extractor import (
    _parse_table,
    header_map,
    is_credit,
    normalise_date,
    parse_amount,
)


def testnormalise_date_dmy_slash():
    assert normalise_date("25/04/2025") == "2025-04-25"


def testnormalise_date_dmy_dash():
    assert normalise_date("01-12-2025") == "2025-12-01"


def testnormalise_date_iso():
    assert normalise_date("2025-07-15") == "2025-07-15"


def testnormalise_date_text_month():
    assert normalise_date("03 Jan 2026") == "2026-01-03"


def testnormalise_date_invalid():
    assert normalise_date("not a date") is None


def testparse_amount_comma():
    assert parse_amount("1,234,567.89") == Decimal("1234567.89")


def testparse_amount_plain():
    assert parse_amount("50000.00") == Decimal("50000.00")


def testparse_amount_empty():
    assert parse_amount("") is None


def testis_credit_only_credit():
    assert is_credit("", "50000.00") is True


def testis_credit_only_debit():
    assert is_credit("15000.00", "") is False


def testis_credit_both_empty():
    assert is_credit("", "") is None


def testheader_map_standard():
    headers = ["Date", "Description", "Debit", "Credit", "Ref"]
    m = header_map(headers)
    assert m["date"] == 0
    assert m["desc"] == 1
    assert m["debit"] == 2
    assert m["credit"] == 3
    assert m["ref"] == 4


def testheader_map_alternate_names():
    headers = ["Txn Date", "Narration", "Withdrawals", "Deposits", "Cheque No"]
    m = header_map(headers)
    assert "date" in m
    assert "desc" in m
    assert "debit" in m
    assert "credit" in m


def test_parse_table_standard():
    table = [
        ["Date", "Description", "Debit", "Credit", "Ref"],
        ["25/04/2025", "SALARY CREDIT", "", "300,000.00", "REF001"],
        ["01/05/2025", "ATM WITHDRAWAL", "10,000.00", "", "REF002"],
        ["", "", "", "", ""],  # blank row — should be skipped
    ]
    rows = _parse_table(table, page=1)
    assert len(rows) == 2
    assert rows[0]["credit_flag"] is True
    assert rows[0]["amount"] == Decimal("300000.00")
    assert rows[0]["date"] == "2025-04-25"
    assert rows[0]["bank_ref"] == "REF001"
    assert rows[1]["credit_flag"] is False
    assert rows[1]["amount"] == Decimal("10000.00")


def test_parse_table_no_date_header():
    # Table without a recognisable date column → no rows extracted
    table = [["Item", "Qty", "Price"], ["Widget", "2", "500.00"]]
    assert _parse_table(table, page=1) == []


def test_parse_table_skips_rows_without_date():
    table = [
        ["Date", "Description", "Debit", "Credit"],
        ["not-a-date", "Mystery row", "100.00", ""],
        ["15/06/2025", "Utility payment", "5000.00", ""],
    ]
    rows = _parse_table(table, page=1)
    assert len(rows) == 1
    assert rows[0]["amount"] == Decimal("5000.00")
