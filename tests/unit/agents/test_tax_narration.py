"""
The tax tool has to hand over enough to explain its own total.

Asked to break down a Rs. 11.7L bill, Salli produced a correct band table
(subtotal Rs. 937,788) and then said:

    "Wait, that's only 9.4L. The rest comes from credits:"

Every figure the engine produced was right and the final number matched. The
narration was wrong, and wrong twice over: the gap was the flat tax on foreign
service income, which sits outside the bands entirely, and credits *reduce* a
bill rather than make up a shortfall.

The cause was a gap in the tool's output, not in the prompt. `band_workings`
and `tax_before_credits` were both returned; `fsi_tax` was not. So the band
table looked like it should reconcile to the total, it did not, and the model
filled the hole with the only other number on the page. No amount of prompting
fixes a missing addend.

These tests pin the reconciliation the model narrates. They deliberately use a
ledger with non-zero foreign service income, because that is the only shape
where the bands and the total legitimately disagree — which is exactly the shape
that produced the bad answer.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from decimal import Decimal

import pytest

from salli.application.services.ledger_service import LedgerService
from salli.application.services.tax_service import TaxService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.agents.tools import make_tools, set_current_user
from tests.unit.agents.test_tools import FakeLedgerRepo, FakeTaxComputationRepo, FakeUoW

USER = "u1"
YEAR = "2025/26"


def _account(code: str, name: str, type_: str, tax_role: str | None = None) -> Account:
    return Account(
        id=str(uuid.uuid4()),
        user_id=USER,
        code=code,
        name=name,
        type=type_,
        tax_role=tax_role,
        currency="LKR",
    )


def _entry(debit: str, credit: str, amount: Decimal) -> StoredJournalEntry:
    return StoredJournalEntry(
        id=str(uuid.uuid4()),
        user_id=USER,
        entry_date="2025-04-01",
        description="test",
        source="manual",
        postings=[
            Posting(account_id=debit, direction=Direction.DEBIT, amount=amount, currency="LKR"),
            Posting(account_id=credit, direction=Direction.CREDIT, amount=amount, currency="LKR"),
        ],
    )


def _tax_tool(
    *,
    local_income: Decimal = Decimal("3_000_000"),
    fsi: Decimal = Decimal("3_680_000"),
    apit: Decimal = Decimal("250_000"),
):
    """A ledger in the shape that produced the bad narration.

    Local salary taxed through the bands, foreign service income taxed flat and
    outside them, and APIT already withheld — so band tax, FSI tax and credits
    are all non-zero and none of them can be inferred from the others.
    """
    salary = _account("4001", "Employment Income", "income")
    foreign = _account("4500", "Foreign Service Income", "income", "fsi_income")
    apit_acc = _account("1010", "APIT Receivable", "asset", "apit_credit")
    bank = _account("1001", "Bank", "asset")

    # Zero-value postings are rejected by the domain model, so an absent
    # income stream is an absent entry rather than an entry for nothing.
    amounts = [
        (bank.id, salary.id, local_income),
        (bank.id, foreign.id, fsi),
        (apit_acc.id, bank.id, apit),
    ]
    entries = [_entry(dr, cr, amt) for dr, cr, amt in amounts if amt > Decimal(0)]
    ledger_repo = FakeLedgerRepo(entries=entries, accounts=[salary, foreign, apit_acc, bank])
    tax_repo = FakeTaxComputationRepo()

    @asynccontextmanager
    async def uow_factory():
        yield FakeUoW(ledger_repo, tax_repo)

    tools = make_tools(LedgerService(uow_factory), TaxService(uow_factory))
    set_current_user(USER)
    return next(t for t in tools if t.name == "get_tax_computation")


@pytest.mark.asyncio
async def test_the_bands_and_the_flat_tax_add_up_to_the_gross_bill():
    """The addend that was missing, and the arithmetic it completes."""
    result = await _tax_tool().ainvoke({"year": YEAR, "user_id": USER})

    band_tax = Decimal(result["band_tax"])
    fsi_tax = Decimal(result["fsi_tax"])

    # The premise of the test: this is a ledger where the bands alone do not
    # explain the total. If this ever fails the fixture has drifted and the
    # assertion below stops testing anything.
    assert fsi_tax > Decimal(0)
    assert band_tax < Decimal(result["tax_before_credits"])

    assert band_tax + fsi_tax == Decimal(result["tax_before_credits"])


@pytest.mark.asyncio
async def test_band_tax_is_the_sum_of_the_band_table_the_model_is_shown():
    """`band_tax` must be the subtotal of `band_workings`, not a second opinion.

    The model reads both. If they disagree it has a genuine contradiction in
    front of it and no way to resolve one against the other.
    """
    result = await _tax_tool().ainvoke({"year": YEAR, "user_id": USER})

    rows = sum((Decimal(row["tax"]) for row in result["band_workings"]), Decimal(0))
    assert rows == Decimal(result["band_tax"])


@pytest.mark.asyncio
async def test_credits_only_ever_subtract():
    """The other half of the wrong answer: credits were offered as a top-up."""
    result = await _tax_tool().ainvoke({"year": YEAR, "user_id": USER})

    total_credits = Decimal(result["total_credits"])
    assert total_credits > Decimal(0)
    assert Decimal(result["tax_before_credits"]) - total_credits == Decimal(result["tax_payable"])
    assert Decimal(result["tax_payable"]) < Decimal(result["tax_before_credits"])


@pytest.mark.asyncio
async def test_the_income_split_the_bands_apply_to_is_visible():
    """Bands apply to regular income only; that has to be shown, not deduced.

    Without these the model has one `gross_income` figure and a band table that
    covers a smaller number, and nothing saying why.
    """
    result = await _tax_tool().ainvoke({"year": YEAR, "user_id": USER})

    for key in (
        "regular_income",
        "foreign_service_income",
        "personal_relief",
        "qualifying_payment_deduction",
        "taxable_income",
        "band_tax",
        "fsi_tax",
        "total_credits",
    ):
        assert key in result, f"missing {key}"
        assert isinstance(result[key], str), f"{key} must be a string for JSON safety"

    assert Decimal(result["regular_income"]) + Decimal(result["foreign_service_income"]) == Decimal(
        result["gross_income"]
    )


@pytest.mark.asyncio
async def test_the_arithmetic_is_stated_in_words_as_well_as_numbers():
    """Spelled out so the relationship never has to be inferred from the values.

    Asserting on substance rather than exact wording: the rules that were got
    wrong are that the bands exclude FSI and that credits only reduce.
    """
    result = await _tax_tool().ainvoke({"year": YEAR, "user_id": USER})

    gross = result["how_tax_before_credits_is_built"]
    assert "band_tax + fsi_tax = tax_before_credits" in gross
    assert "never appears in the bands" in gross

    payable = result["how_tax_payable_is_built"]
    assert "tax_before_credits - total_credits = tax_payable" in payable
    assert "reduce" in payable


@pytest.mark.asyncio
async def test_a_purely_local_ledger_still_reconciles():
    """No FSI is the ordinary case; the same identity has to hold there.

    Here the bands *do* sum to the gross bill, and `fsi_tax` must be zero rather
    than absent — an omitted key reads as "unknown", which is the ambiguity this
    whole fix exists to remove.
    """
    tool = _tax_tool(fsi=Decimal(0), apit=Decimal("100_000"))
    result = await tool.ainvoke({"year": YEAR, "user_id": USER})

    assert Decimal(result["fsi_tax"]) == Decimal(0)
    assert Decimal(result["foreign_service_income"]) == Decimal(0)
    assert Decimal(result["band_tax"]) == Decimal(result["tax_before_credits"])
