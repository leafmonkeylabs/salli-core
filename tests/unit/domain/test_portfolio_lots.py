"""
Lot accounting: lots opened by buys and transfers in, consumed by sales first in
first out or as named, scaled by splits, with fees in the cost and the proceeds.
Each expected figure is worked by hand in the comment above it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from salli.domain.portfolio.lots import (
    Kind,
    LotPick,
    Replay,
    Transaction,
    TransactionError,
    plain,
    replay,
    split_factor,
    total,
    validate,
)

D = Decimal


def buy(id: str, on: str, quantity: str, price: str, fees: str = "0", fx: str = "1", seq: int = 0):
    return Transaction(
        id=id,
        kind=Kind.BUY,
        on=date.fromisoformat(on),
        quantity=D(quantity),
        price=D(price),
        fees=D(fees),
        fx_rate=D(fx),
        seq=seq,
    )


def sell(
    id: str,
    on: str,
    quantity: str,
    price: str,
    fees: str = "0",
    fx: str = "1",
    lots: tuple[LotPick, ...] = (),
    seq: int = 0,
):
    return Transaction(
        id=id,
        kind=Kind.SELL,
        on=date.fromisoformat(on),
        quantity=D(quantity),
        price=D(price),
        fees=D(fees),
        fx_rate=D(fx),
        lots=lots,
        seq=seq,
    )


def split(id: str, on: str, to: str, from_: str = "1"):
    return Transaction(
        id=id, kind=Kind.SPLIT, on=date.fromisoformat(on), split_to=D(to), split_from=D(from_)
    )


# ── first in, first out ───────────────────────────────────────────────────────


def test_a_sale_consumes_the_oldest_lots_first_and_fees_count_both_ways():
    book = replay(
        [
            buy("b1", "2026-01-05", "10", "100", fees="5"),  # lot cost 10 × 100 + 5 = 1005
            buy("b2", "2026-02-05", "10", "120", fees="5"),  # lot cost 1205
            sell("s1", "2026-03-05", "15", "130", fees="10"),
        ]
    )
    [sale] = book.sales
    # All of b1 (1005) and half of b2 (1205 × 5/10 = 602.5).
    assert [(c.lot_id, c.quantity, c.cost) for c in sale.consumed] == [
        ("b1", D(10), D(1005)),
        ("b2", D(5), D("602.5")),
    ]
    # Proceeds 15 × 130 = 1950; gain 1950 − 10 − 1607.5 = 332.5.
    assert (sale.proceeds, sale.fees, sale.cost, sale.gain) == (
        D(1950),
        D(10),
        D("1607.5"),
        D("332.5"),
    )
    assert [(lot.id, lot.quantity, lot.cost) for lot in book.open_lots] == [
        ("b2", D(5), D("602.5"))
    ]
    assert book.position.quantity == 5


def test_a_sale_can_name_its_lots():
    book = replay(
        [
            buy("b1", "2026-01-05", "10", "100", fees="5"),
            buy("b2", "2026-02-05", "10", "120", fees="5"),
            sell("s1", "2026-03-05", "5", "130", lots=(LotPick("b2", D(5)),)),
        ]
    )
    [sale] = book.sales
    # Half of b2: 1205 × 5/10 = 602.5; proceeds 650; gain 47.5.
    assert (sale.cost, sale.gain) == (D("602.5"), D("47.5"))
    assert [(lot.id, lot.quantity) for lot in book.open_lots] == [("b1", D(10)), ("b2", D(5))]


def test_a_sale_can_take_from_several_named_lots():
    book = replay(
        [
            buy("b1", "2026-01-05", "4", "10"),
            buy("b2", "2026-02-05", "4", "20"),
            buy("b3", "2026-03-05", "4", "30"),
            sell(
                "s1",
                "2026-04-05",
                "3",
                "25",
                lots=(LotPick("b3", D(2)), LotPick("b1", D(1))),
            ),
        ]
    )
    [sale] = book.sales
    # 2 of b3 (60) and 1 of b1 (10): cost 70, proceeds 75, gain 5.
    assert (sale.cost, sale.gain) == (D(70), D(5))
    assert [lot.quantity for lot in book.lots] == [D(3), D(4), D(2)]


def test_partial_sales_never_lose_or_make_money_in_the_division():
    # A lot of 3 that cost 10.00 cannot give up thirds exactly; whatever one
    # sale takes, the next gets the rest, so the three sales cost 10.00.
    book = replay(
        [
            buy("b1", "2026-01-05", "3", "0", fees="10"),
            sell("s1", "2026-02-05", "1", "4", seq=1),
            sell("s2", "2026-02-05", "1", "4", seq=2),
            sell("s3", "2026-02-05", "1", "4", seq=3),
        ]
    )
    assert total(s.cost for s in book.sales) == D(10)
    assert total(s.gain for s in book.sales) == D(2)
    assert book.position.quantity == 0 and book.position.cost == 0


def test_buying_and_selling_at_one_price_without_fees_gains_nothing():
    book = replay(
        [
            buy("b1", "2026-01-05", "7", "1.01"),
            buy("b2", "2026-01-06", "0.3", "1.01"),
            sell("s1", "2026-01-07", "3", "1.01"),
            sell("s2", "2026-01-08", "4.3", "1.01"),
        ]
    )
    assert [s.gain for s in book.sales] == [0, 0]


# ── splits ────────────────────────────────────────────────────────────────────


def test_a_split_scales_every_open_lot_and_keeps_its_cost():
    book = replay(
        [
            buy("b1", "2026-01-05", "10", "100"),  # cost 1000
            split("x1", "2026-02-01", "2"),  # 2-for-1: 20 units, still 1000
            sell("s1", "2026-03-01", "5", "60"),
        ]
    )
    [sale] = book.sales
    # 5 of 20 units: cost 1000 × 5/20 = 250; proceeds 300; gain 50.
    assert (sale.cost, sale.gain) == (D(250), D(50))
    [lot] = book.lots
    assert (lot.opened_quantity, lot.quantity, lot.cost) == (D(20), D(15), D(750))


def test_a_reverse_split_that_does_not_divide_keeps_eighteen_places():
    book = replay([buy("b1", "2026-01-05", "10", "3"), split("x1", "2026-02-01", "1", "3")])
    assert book.position.quantity == D("3.333333333333333333")
    assert book.position.cost == D(30)


def test_units_bought_on_a_split_date_are_already_split():
    # The split takes effect from the start of its day: the morning's lot
    # doubles, the units bought that day do not.
    book = replay(
        [
            buy("b1", "2026-01-05", "10", "100"),
            buy("b2", "2026-02-01", "10", "50"),
            split("x1", "2026-02-01", "2"),
        ]
    )
    assert [lot.quantity for lot in book.lots] == [D(20), D(10)]


def test_split_factor_is_the_product_of_the_splits_in_between():
    history = [split("x1", "2026-02-01", "2"), split("x2", "2026-06-01", "3", "2")]
    assert split_factor(history, date(2026, 1, 1), date(2026, 12, 31)) == D(3)
    # A price quoted on the split date is already post-split.
    assert split_factor(history, date(2026, 2, 1), date(2026, 5, 31)) == D(1)
    assert split_factor(history, date(2026, 1, 1), date(2026, 2, 1)) == D(2)


# ── order within a day, and income ────────────────────────────────────────────


def test_a_sale_can_use_units_bought_the_same_day():
    book = replay([sell("s1", "2026-01-05", "1", "10", seq=1), buy("b1", "2026-01-05", "1", "9")])
    assert book.sales[0].gain == D(1)


def test_income_after_everything_was_sold_is_still_income():
    book = replay(
        [
            buy("b1", "2026-01-05", "10", "100"),
            sell("s1", "2026-02-05", "10", "100"),
            Transaction(
                id="d1",
                kind=Kind.DIVIDEND,
                on=date(2026, 3, 1),
                amount=D("25.00"),
                withholding_tax=D("3.75"),
                fx_rate=D(2),
            ),
        ]
    )
    [income] = book.income
    assert (income.gross, income.withholding_tax, income.net) == (D(25), D("3.75"), D("21.25"))
    assert (income.gross_base, income.net_base) == (D(50), D("42.5"))


# ── the base currency ─────────────────────────────────────────────────────────


def test_base_figures_use_the_rate_of_the_day_each_thing_happened():
    # Bought in USD into a rupee base at 300, sold at 310.
    book = replay(
        [
            buy("b1", "2026-01-05", "10", "100", fees="1", fx="300"),
            sell("s1", "2026-06-05", "10", "110", fees="1", fx="310"),
        ]
    )
    [sale] = book.sales
    # Native: 1100 − 1 − 1001 = 98.
    assert sale.gain == D(98)
    # Base: cost 1001 × 300 = 300,300; proceeds 1100 × 310 = 341,000; fees 310.
    assert (sale.cost_base, sale.proceeds_base, sale.fees_base) == (
        D(300300),
        D(341000),
        D(310),
    )
    assert sale.gain_base == D(40390)


def test_a_transfer_in_opens_a_lot_at_its_stated_cost():
    book = replay(
        [
            Transaction(
                id="t1",
                kind=Kind.TRANSFER_IN,
                on=date(2015, 3, 1),
                quantity=D(50),
                amount=D(2500),
                fx_rate=D("0.9"),
            )
        ]
    )
    [lot] = book.lots
    assert (lot.kind, lot.quantity, lot.cost, lot.cost_base) == (
        Kind.TRANSFER_IN,
        D(50),
        D(2500),
        D(2250),
    )


# ── histories that cannot have happened ───────────────────────────────────────


def test_selling_more_than_is_held_is_refused():
    with pytest.raises(TransactionError, match="only 10 are held"):
        replay([buy("b1", "2026-01-05", "10", "1"), sell("s1", "2026-01-06", "10.5", "1")])


def test_selling_before_buying_is_refused():
    with pytest.raises(TransactionError, match="only 0 are held"):
        replay([sell("s1", "2026-01-04", "1", "1"), buy("b1", "2026-01-05", "1", "1")])


def test_naming_a_lot_that_was_not_held_is_refused():
    with pytest.raises(TransactionError, match="names lot b2"):
        replay(
            [
                buy("b1", "2026-01-05", "10", "1"),
                sell("s1", "2026-01-06", "1", "1", lots=(LotPick("b2", D(1)),)),
                buy("b2", "2026-01-07", "10", "1"),
            ]
        )


def test_taking_more_from_a_named_lot_than_it_holds_is_refused():
    with pytest.raises(TransactionError, match="from lot b1"):
        replay(
            [
                buy("b1", "2026-01-05", "1", "1"),
                buy("b2", "2026-01-05", "5", "1"),
                sell("s1", "2026-01-06", "2", "1", lots=(LotPick("b1", D(2)),)),
            ]
        )


@pytest.mark.parametrize(
    ("tx", "message"),
    [
        (buy("b", "2026-01-01", "-1", "1"), "quantity must be positive"),
        (buy("b", "2026-01-01", "0", "1"), "quantity must be positive"),
        (buy("b", "2026-01-01", "1", "-1"), "price must be zero or more"),
        (buy("b", "2026-01-01", "1", "1", fees="-1"), "fees must be zero or more"),
        (buy("b", "2026-01-01", "0.0000000000000000001", "1"), "more than 18 decimal places"),
        (buy("b", "2026-01-01", "1" + "0" * 20, "1"), "less than 10"),
        (buy("b", "2026-01-01", "1", "1", fx="0"), "fx_rate must be positive"),
        (split("x", "2026-01-01", "2", "2"), "cannot be 1:1"),
        (
            Transaction("d", Kind.DIVIDEND, date(2026, 1, 1), amount=D(1), withholding_tax=D(2)),
            "cannot exceed",
        ),
        (Transaction("d", Kind.INTEREST, date(2026, 1, 1)), "amount must be positive"),
        (
            Transaction(
                "b",
                Kind.BUY,
                date(2026, 1, 1),
                quantity=D(1),
                price=D(1),
                lots=(LotPick("x", D(1)),),
            ),
            "Only a sale",
        ),
        (
            sell("s", "2026-01-01", "2", "1", lots=(LotPick("a", D(1)),)),
            "add up to 1 units, not the 2 sold",
        ),
        (
            sell("s", "2026-01-01", "2", "1", lots=(LotPick("a", D(1)), LotPick("a", D(1)))),
            "names each lot once",
        ),
        (buy("b", "2026-01-01", "NaN", "1"), "must be a number"),
    ],
)
def test_a_malformed_transaction_is_refused(tx: Transaction, message: str):
    with pytest.raises(TransactionError, match=message):
        validate(tx)


def test_trailing_zeros_are_not_decimal_places():
    validate(buy("b", "2026-01-01", "1.500000000000000000000000", "1"))


def test_replay_moves_forward_a_day_at_a_time():
    history = [
        buy("b1", "2026-01-05", "10", "100"),
        split("x1", "2026-02-01", "2"),
        sell("s1", "2026-02-01", "4", "55"),
    ]
    steps = Replay(history)
    assert steps.advance(date(2026, 1, 31)).position().quantity == 10
    # The start of the split date: split, but not yet sold.
    assert steps.advance(date(2026, 2, 1), splits_only_on_last_day=True).position().quantity == 20
    assert steps.advance(date(2026, 2, 1)).position().quantity == 16


def test_plain_numbers_read_without_trailing_zeros_or_exponents():
    assert [plain(D(x)) for x in ("10.000", "0.50", "1E+3", "0", "-2.50")] == [
        "10",
        "0.5",
        "1000",
        "0",
        "-2.5",
    ]
