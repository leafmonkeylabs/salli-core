"""
A small household that rents, for the rent-or-buy goldens
(docs/design/decision-lab-phase-3.md, section 3, "Tests"): in New Zealand
dollars, as of 2031-06-30; no inflation set; none of the monthly surplus
invested (`surplus_invested` 0), so cash keeps what isn't spent.

The books open on 2030-12-31 with 60,000.00 in the bank: a salary of
3,000.00 on the 25th and rent of 1,000.00 on the 1st, January to June 2031.
The ledger shows the rent as a recurring payment, key "harbour".
"""

from __future__ import annotations

import datetime as dt

from tests.baseline_ledger import Ledger

AS_OF = dt.date(2031, 6, 30)
RENT_KEY = "harbour"


def ledger() -> Ledger:
    books = Ledger("NZD")
    books.account("bank", "asset", name="Bank")
    books.account("pay", "income")
    books.account("rent", "expense")
    books.account("eq", "equity")
    books.book("2030-12-31", "bank", "eq", "60000")
    for month in range(1, 7):
        books.book(f"2031-{month:02d}-01", "rent", "bank", "1000", description="HARBOUR LETTINGS")
        books.book(f"2031-{month:02d}-25", "bank", "pay", "3000", description="ACME SALARY")
    books.assume(surplus_invested="0")
    return books
