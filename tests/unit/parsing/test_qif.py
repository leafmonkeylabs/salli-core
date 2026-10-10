"""
QIF: bank, card and cash registers, ambiguous dates decided from the whole
file, amounts with thousands separators, and the sections that are not read.
"""

from decimal import Decimal
from pathlib import Path

from salli.adapters.parsing.qif import extract_from_qif

FIXTURES = Path(__file__).parents[2] / "fixtures" / "statements"


def _rows(result):
    return [
        (line.date, line.description, line.amount, line.credit_flag, line.bank_ref)
        for line in result.lines
    ]


def test_a_quicken_export_with_dates_that_read_both_ways():
    result = extract_from_qif((FIXTURES / "quicken_us.qif").read_bytes(), prefer_order="MDY")

    # Every date is the 10th of a month or a day in October: read month-first
    # they are twelve days in one month, so that is the reading, and it is said.
    assert _rows(result) == [
        (
            "2026-10-01",
            "Greenway Property Management - October rent",
            Decimal("1250.00"),
            False,
            "1043",
        ),
        ("2026-10-02", "Blue Bottle Coffee", Decimal("4.50"), False, ""),
        ("2026-10-05", "Northwind Payroll - Direct deposit", Decimal("2400.00"), True, "DEP"),
        (
            "2026-10-07",
            "Safeway #1123",
            Decimal("82.35"),
            False,
            "ATM",
        ),  # the total, not the splits
        ("2026-10-09", "ATM Withdrawal", Decimal("60.00"), False, "ATM"),
        ("2026-10-12", "Pacific Gas & Electric - Autopay", Decimal("89.99"), False, ""),
        ("2026-10-03", "Shell Oil 57442", Decimal("45.20"), False, ""),
        ("2026-10-10", "Payment - Thank You", Decimal("300.00"), True, ""),
    ]
    assert {line.currency for line in result.lines} == {None}  # QIF names no currency
    skipped, *notice = result.errors
    # Day-first, the dates run to December: a month or more ahead of today
    # while that lasts, and then a reading as good as month-first, which a
    # dollar statement's country prefers. Either way, month first.
    assert all("read them month first (MDY)" in n and "DMY" in n for n in notice)
    assert skipped == (
        "Skipped 1 record(s) in the investment register: "
        "only bank, card and cash registers are imported"
    )


def test_the_caller_can_say_the_date_order():
    result = extract_from_qif((FIXTURES / "quicken_us.qif").read_bytes(), date_order="DMY")
    assert result.lines[0].date == "2026-01-10"
    assert not any("could be read" in e for e in result.errors)


def test_one_unambiguous_date_settles_the_file():
    data = b"!Type:Bank\nD10/25/2026\nT-1.00\nPA\n^\nD10/01/2026\nT-2.00\nPB\n^\n"
    result = extract_from_qif(data)
    assert [line.date for line in result.lines] == ["2026-10-25", "2026-10-01"]
    assert result.errors == []


def test_a_european_qif_with_decimal_commas():
    data = (
        "!Type:Bank\n"
        "D01.10.2026\nT-1.234,56\nPMöbelhaus Berlin\n^\n"
        "D15.10.2026\nT-12,50\nPBäckerei\n^\n"
        "D20.10.2026\nT2.000\nPGehalt\n^\n"
    ).encode("cp1252")
    result = extract_from_qif(data)
    assert result.errors == []
    assert _rows(result) == [
        ("2026-10-01", "Möbelhaus Berlin", Decimal("1234.56"), False, ""),
        ("2026-10-15", "Bäckerei", Decimal("12.50"), False, ""),
        ("2026-10-20", "Gehalt", Decimal("2000"), True, ""),
    ]


def test_cash_registers_are_read_and_lists_are_not():
    data = (
        b"!Type:Cat\nNGroceries\nE\n^\n"
        b"!Type:Cash\nD2026-10-03\nT-20.00\nPFarmers market\n^\n"
        b"!Type:Class\nNBusiness\n^\n"
    )
    result = extract_from_qif(data)
    assert _rows(result) == [("2026-10-03", "Farmers market", Decimal("20.00"), False, "")]
    assert result.errors == []


def test_an_unreadable_record_is_reported_and_the_rest_kept():
    data = (
        b"!Type:Bank\n"
        b"D31/02/2026\nT-1.00\nPBad date\n^\n"
        b"D01/03/2026\nTabc\nPBad amount\n^\n"
        b"D02/03/2026\nT-3.00\nPGood\n"  # no closing ^ at the end of the file
    )
    result = extract_from_qif(data, date_order="DMY")
    assert _rows(result) == [("2026-03-02", "Good", Decimal("3.00"), False, "")]
    assert result.errors == [
        "QIF record at line 2: '31/02/2026' is not a date; skipped",
        "QIF record at line 6: 'abc' is not an amount; skipped",
    ]


def test_each_register_is_on_the_account_its_account_record_names():
    result = extract_from_qif((FIXTURES / "quicken_us.qif").read_bytes(), prefer_order="MDY")
    assert result.accounts == ["Everyday Checking", "Rewards Visa"]
    assert result.account_kinds == {
        "Everyday Checking": "bank account",
        "Rewards Visa": "credit card",
    }
    assert [line.account for line in result.lines] == ["Everyday Checking"] * 6 + [
        "Rewards Visa"
    ] * 2
    # N is what someone wrote (a cheque number, "ATM"), never the bank's id.
    assert {line.ref_kind for line in result.lines} == {"text"}
