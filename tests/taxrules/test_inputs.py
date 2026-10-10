"""Role totals read from a ledger: the generic replacement for `_build_ledger_view`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.taxrules.inputs import dates_needing_rates, role_postings, total_roles

ROLES = ("salary", "withheld", "gift_aid")
YEAR = (date(2031, 1, 1), date(2031, 12, 31))


def _account(id: str, type: str, role: str | None, currency: str = "EUR") -> Account:
    return Account(
        id=id, user_id="u", code=id, name=id, type=type, currency=currency, tax_role=role
    )  # type: ignore[arg-type]


ACCOUNTS = [
    _account("bank", "asset", None),
    _account("salary", "income", "salary"),
    _account("withheld", "asset", "withheld"),
    _account("gift", "expense", "gift_aid"),
    _account("other", "income", "not_declared"),
    _account("usd_salary", "income", "salary", "USD"),
]


def _entry(day: str, *postings: tuple[str, Direction, str, str, str]) -> StoredJournalEntry:
    return StoredJournalEntry(
        id=f"e-{day}-{len(postings)}",
        user_id="u",
        entry_date=day,
        description="x",
        source="manual",
        postings=[
            Posting(
                account_id=acc,
                direction=direction,
                amount=Decimal(amount),
                currency=currency,
                fx_rate=Decimal(rate),
            )
            for acc, direction, amount, currency, rate in postings
        ],
    )


D, C = Direction.DEBIT, Direction.CREDIT


def _payday(day: str, gross: str, tax: str) -> StoredJournalEntry:
    net = str(Decimal(gross) - Decimal(tax))
    withheld = [("withheld", D, tax, "EUR", "1")] if Decimal(tax) else []
    return _entry(day, ("bank", D, net, "EUR", "1"), *withheld, ("salary", C, gross, "EUR", "1"))


def _totals(entries, base="EUR", target="EUR", rates=None):
    postings = role_postings(entries, ACCOUNTS, ROLES, *YEAR)
    return total_roles(postings, ROLES, base, target, rates)


def test_income_and_withholding_come_out_positive_in_their_normal_direction():
    result = _totals([_payday("2031-01-31", "3000", "600"), _payday("2031-02-28", "3000", "600")])
    assert result.totals == {
        "salary": Decimal("6000.00"),
        "withheld": Decimal("1200.00"),
        "gift_aid": Decimal("0.00"),
    }
    assert result.postings["salary"] == 2
    assert result.negative == ()


def test_only_the_tax_year_counts_both_ends_included():
    entries = [
        _payday("2030-12-31", "1", "0.5"),
        _payday("2031-01-01", "10", "1"),
        _payday("2031-12-31", "100", "10"),
        _payday("2032-01-01", "1000", "100"),
    ]
    assert _totals(entries).totals["salary"] == Decimal("110.00")


def test_a_reversal_cancels_what_it_reverses():
    original = _payday("2031-03-31", "3000", "600")
    reversal = _entry(
        "2031-04-01",
        ("bank", C, "2400", "EUR", "1"),
        ("withheld", C, "600", "EUR", "1"),
        ("salary", D, "3000", "EUR", "1"),
    )
    assert _totals([original, reversal]).totals["salary"] == Decimal("0.00")


def test_a_negative_total_is_kept_and_reported():
    refund = _entry("2031-05-01", ("salary", D, "50", "EUR", "1"), ("bank", C, "50", "EUR", "1"))
    result = _totals([refund])
    assert result.totals["salary"] == Decimal("-50.00")
    assert result.negative == ("salary",)


def test_roles_the_rule_set_does_not_declare_and_accounts_with_none_do_not_count():
    entry = _entry("2031-06-01", ("bank", D, "70", "EUR", "1"), ("other", C, "70", "EUR", "1"))
    assert _totals([entry]).totals["salary"] == Decimal("0.00")


def test_another_currency_converts_at_each_entry_date_s_rate():
    # A USD salary in a EUR ledger: booked at 0.9 EUR per USD.
    usd = _entry(
        "2031-07-01",
        ("bank", D, "900", "EUR", "1"),
        ("usd_salary", C, "1000", "USD", "0.9"),
    )
    eur = _payday("2031-07-31", "100", "0")
    postings = role_postings([usd, eur], ACCOUNTS, ROLES, *YEAR)

    # Computing in EUR, the base: the booked base amounts, no rates needed.
    assert dates_needing_rates(postings, "EUR", "EUR") == []
    assert total_roles(postings, ROLES, "EUR", "EUR").totals["salary"] == Decimal("1000.00")

    # Computing in USD: the USD posting at its own amount, the EUR one
    # converted at its date's EUR→USD rate.
    assert dates_needing_rates(postings, "EUR", "USD") == ["2031-07-31"]
    totals = total_roles(postings, ROLES, "EUR", "USD", {"2031-07-31": Decimal("1.1")})
    assert totals.totals["salary"] == Decimal("1110.00")


def test_a_missing_rate_is_never_taken_as_one():
    postings = role_postings([_payday("2031-07-31", "100", "0")], ACCOUNTS, ROLES, *YEAR)
    with pytest.raises(KeyError):
        total_roles(postings, ROLES, "EUR", "USD", {})


def test_totals_are_rounded_to_the_currency_s_minor_units():
    entry = _entry(
        "2031-08-01",
        ("bank", D, "1", "JPY", "1"),
        ("salary", C, "1", "JPY", "1"),
    )
    postings = role_postings([entry], ACCOUNTS, ROLES, *YEAR)
    totals = total_roles(postings, ROLES, "EUR", "JPY", {})
    assert totals.totals["salary"] == Decimal("1")
