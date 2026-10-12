"""
Holdings in the baseline (decision lab 3b, decision 17): valued as of the
as-of date at their last recorded price and the as-of rate, never counted
(the ledger's investment accounts are), and a note wherever a linked account
and its holdings disagree. Nothing is reconciled silently.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal as D

from tests.baseline_ledger import Ledger

AS_OF = dt.date(2027, 3, 31)


def books(brokerage: str = "1500") -> Ledger:
    """In rand: a brokerage account holding `brokerage`, and a fund the
    person calls "My index fund": 10 units bought at 100.00 with 5.00 of
    fees, a close of 150.00 on the as-of date."""
    b = Ledger("ZAR")
    b.account("chk", "asset")
    b.account("brk", "asset", asset_role="investment", name="Brokerage")
    b.account("eq", "equity")
    b.book("2027-01-02", "chk", "eq", "5000")
    b.book("2027-01-02", "brk", "eq", brokerage)
    b.holding("fund", "My index fund", account_id="brk")
    b.trade("fund", "buy", "2027-01-10", "10", "100", fees="5")
    b.close("fund", "2027-03-31", "150")
    return b


def test_a_holding_is_valued_at_its_last_price_and_never_counted():
    b = books().baseline(AS_OF)
    (fund,) = b.holdings
    assert (fund.holding_id, fund.name, fund.account_id) == ("fund", "My index fund", "brk")
    assert (fund.quantity, fund.cost, fund.price, fund.price_date, fund.price_source) == (
        D("10"),
        D("1005"),
        D("150"),
        "2027-03-31",
        "user",
    )
    assert (fund.value, fund.value_base, fund.fx_rate) == (D("1500"), D("1500"), D(1))
    # The investments are the ledger's: the brokerage's 1,500.00.
    assert b.investments == D("1500")
    assert not any("Brokerage" in n for n in b.notes)


def test_a_linked_account_that_disagrees_is_noted_never_reconciled():
    b = books(brokerage="1200").baseline(AS_OF)
    assert b.investments == D("1200")
    (note,) = [n for n in b.notes if n.startswith("Brokerage")]
    assert "your ledger holds 1,200.00 ZAR" in note
    assert "worth 1,500.00 ZAR at their recorded prices (300.00 more)" in note
    assert "The ledger's figure is the one counted" in note


def test_a_price_after_the_as_of_date_is_not_read():
    ledger = books()
    ledger.close("fund", "2027-04-02", "180")
    ledger.trade("fund", "buy", "2027-04-03", "1", "181")
    (fund,) = ledger.baseline(AS_OF).holdings
    assert (fund.quantity, fund.price) == (D("10"), D("150"))


def test_a_holding_in_another_currency_is_valued_at_the_as_of_rate():
    ledger = books(brokerage="2100")
    ledger.holding("etf", "My dollar fund", currency="USD", account_id="brk")
    ledger.trade("etf", "buy", "2027-02-01", "2", "30", fx="17.5")
    ledger.close("etf", "2027-03-30", "35")
    ledger.rate("USD", "18")
    b = ledger.baseline(AS_OF)
    etf = next(h for h in b.holdings if h.holding_id == "etf")
    # 2 × 35.00 = 70.00 dollars, at the as-of rate of 18: 1,260.00 rand.
    assert (etf.value, etf.fx_rate, etf.value_base) == (D("70"), D("18"), D("1260"))
    # Its cost at the rate it was bought at: 60.00 × 17.5 = 1,050.00.
    assert etf.cost_base == D("1050")
    (note,) = [n for n in b.notes if n.startswith("Brokerage")]
    assert "worth 2,760.00 ZAR" in note and "(660.00 more)" in note


def test_without_a_rate_the_two_are_not_compared():
    ledger = books()
    ledger.holding("etf", "My dollar fund", currency="USD", account_id="brk")
    ledger.trade("etf", "buy", "2027-02-01", "2", "30", fx="17.5")
    b = ledger.baseline(AS_OF)
    etf = next(h for h in b.holdings if h.holding_id == "etf")
    assert etf.fx_rate is None and etf.value_base is None
    (note,) = [n for n in b.notes if n.startswith("Brokerage")]
    assert "My dollar fund can't be valued in ZAR" in note


def test_a_holding_linked_to_an_account_no_longer_an_investment_is_noted():
    ledger = books()
    ledger.uow.ledger.accounts[1] = ledger.uow.ledger.accounts[1].model_copy(
        update={"asset_role": "cash"}
    )
    b = ledger.baseline(AS_OF)
    assert any(
        "Brokerage holds My index fund but isn't an investment account" in n for n in b.notes
    )


def test_holdings_are_in_the_fingerprint_only_when_there_are_some():
    plain = Ledger("ZAR")
    plain.account("chk", "asset")
    plain.account("eq", "equity")
    plain.book("2027-01-02", "chk", "eq", "5000")
    before = plain.baseline(AS_OF).fingerprint
    plain.holding("fund", "My index fund")
    with_one = plain.baseline(AS_OF).fingerprint
    assert with_one != before
    del plain.uow.holdings.rows["fund"]
    assert plain.baseline(AS_OF).fingerprint == before
