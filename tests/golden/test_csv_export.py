"""
Golden tests for the pure CSV export helper.
"""

from decimal import Decimal

from salli.domain.reports.csv_export import rows_to_csv


def test_headers_and_rows_present():
    csv_bytes = rows_to_csv(["Name", "Amount"], [["Cash", "1000"], ["Savings", "5000"]])
    text = csv_bytes.decode("utf-8")
    lines = text.strip().splitlines()

    assert lines[0] == "Name,Amount"
    assert lines[1] == "Cash,1000"
    assert lines[2] == "Savings,5000"


def test_empty_rows_produces_header_only():
    csv_bytes = rows_to_csv(["A", "B"], [])
    text = csv_bytes.decode("utf-8")

    assert text.strip() == "A,B"


def test_none_cells_render_as_empty_string():
    csv_bytes = rows_to_csv(["Name", "Note"], [["Cash", None]])
    text = csv_bytes.decode("utf-8")

    assert text.strip().splitlines()[1] == "Cash,"


def test_decimal_values_are_stringified():
    csv_bytes = rows_to_csv(["Account", "Balance"], [["Cash", Decimal("1234.56")]])
    text = csv_bytes.decode("utf-8")

    assert "1234.56" in text


def test_commas_in_values_are_quoted():
    csv_bytes = rows_to_csv(["Description"], [["Rent, utilities, and groceries"]])
    text = csv_bytes.decode("utf-8")

    assert '"Rent, utilities, and groceries"' in text


def test_output_is_bytes():
    result = rows_to_csv(["X"], [["1"]])
    assert isinstance(result, bytes)
