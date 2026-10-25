"""
Recategorising a booked entry while its day is open gives the same monthly
budget totals and tax role totals, per period, as booking it right first time:
the reversal and the corrected copy land on the original's day.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from salli.domain.accounting.models import Account
from salli.domain.budget.monthly import spend_by_month
from salli.domain.taxrules.inputs import role_postings, total_roles
from tests.unit.application.test_reverse_entry import _service

ROLES = ("deductible_a", "deductible_b")
ACCOUNTS = [
    Account(id="bank", user_id="u1", code="1000", name="Bank", type="asset", currency="LKR"),
    Account(
        id="a",
        user_id="u1",
        code="5000",
        name="A",
        type="expense",
        currency="LKR",
        tax_role="deductible_a",
    ),
    Account(
        id="b",
        user_id="u1",
        code="5100",
        name="B",
        type="expense",
        currency="LKR",
        tax_role="deductible_b",
    ),
]


async def _book(rows: list[tuple[int, str, str]], fix: list[bool]) -> tuple[object, object]:
    svc, repo = _service()
    repo.accounts.update({a.id: a for a in ACCOUNTS})
    for (day, amount, wrong), recategorise in zip(rows, fix, strict=True):
        on = (dt.date(2026, 1, 1) + dt.timedelta(days=day)).isoformat()
        right = "b" if wrong == "a" else "a"
        entry_id = await svc.add_entry(
            "u1",
            on,
            "Spend",
            "manual",
            [
                {
                    "account_id": wrong if recategorise else right,
                    "direction": 1,
                    "amount": Decimal(amount),
                    "currency": "LKR",
                },
                {
                    "account_id": "bank",
                    "direction": -1,
                    "amount": Decimal(amount),
                    "currency": "LKR",
                },
            ],
        )
        if recategorise:
            # The fake store gives postings no ids: name them as the ledger would.
            booked = repo.entries[entry_id]
            repo.entries[entry_id] = booked.model_copy(
                update={
                    "postings": [
                        p.model_copy(update={"id": f"{entry_id}:{i}"})
                        for i, p in enumerate(booked.postings)
                    ]
                }
            )
            made = await svc.recategorise_entry("u1", entry_id, f"{entry_id}:0", right, "Wrong one")
            assert made["dated"] == "original" and made["dated_reason"] is None
    entries = list(repo.entries.values())
    roles = {
        quarter: total_roles(
            role_postings(entries, ACCOUNTS, ROLES, dt.date(2026, m, 1), dt.date(2026, m + 2, 28)),
            ROLES,
            "LKR",
            "LKR",
        ).totals
        for quarter, m in (("q1", 1), ("q2", 4), ("q3", 7))
    }
    spent = {k: v for k, v in spend_by_month(entries, ACCOUNTS).items() if v}
    return spent, roles


@settings(max_examples=40, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.integers(0, 240),
            st.decimals("0.01", "99999", places=2).map(str),
            st.sampled_from(["a", "b"]),
        ),
        min_size=1,
        max_size=6,
    ).flatmap(
        lambda rows: st.tuples(
            st.just(rows), st.lists(st.booleans(), min_size=len(rows), max_size=len(rows))
        )
    )
)
def test_recategorising_in_open_books_matches_booking_it_right(case) -> None:
    rows, fix = case
    right_first = asyncio.run(_book(rows, [False] * len(rows)))
    recategorised = asyncio.run(_book(rows, fix))
    assert recategorised == right_first
