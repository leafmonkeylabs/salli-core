"""Closing a year, filing it and who did what, against a real database: a
filed year's books stay closed until an amendment is recorded, returns are
append-only, a year-end close moves earnings to retained earnings, every
entry records its author and the ledger's hash chain finds a changed entry."""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from salli.application.entry_author import set_author
from salli.application.services.ledger_service import LedgerService
from salli.application.services.tax_rule_service import TaxRuleService
from salli.application.services.tax_service import TaxService
from salli.domain.accounting.models import BooksLocked, Direction
from tests.integration.pg import _sync, requires_postgres, scalar
from tests.integration.test_tax_service import A, _activate, _book, remitland

pytestmark = [requires_postgres, pytest.mark.asyncio]

LATER = datetime.date(2032, 10, 10)


@pytest.fixture
async def rules(uow_factory) -> TaxRuleService:
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(A, {"base_currency": "KWD", "tax_residency": "GB"})
    return TaxRuleService(uow_factory)


@pytest.fixture
async def filed(uow_factory, rules):
    """A's 2031/32 computed, its books closed and its return filed."""
    await _activate(rules, remitland())
    await _book(uow_factory, A, local="1000.000")
    tax = TaxService(uow_factory, rules, clock=lambda: LATER)
    computation = await tax.compute_tax(A, country="XG", year="2031/32")
    ledger = LedgerService(uow_factory, today=lambda: LATER)
    await ledger.set_lock_date(A, "2032-03-31")
    ret = await tax.record_return(
        A, computation["id"], "filed", reference="XG-123", filed_on=datetime.date(2032, 6, 1)
    )
    return tax, ledger, computation, ret


async def test_a_filed_year_stays_closed_until_an_amendment_is_recorded(filed, db):
    tax, ledger, computation, ret = filed
    assert (ret["version"], ret["status"], ret["supersedes_id"]) == (1, "filed", None)
    assert ret["snapshot"]["id"] == computation["id"]
    assert ret["snapshot_hash"].startswith("sha256:")
    # The postings behind each role, and the ledger as it stood.
    assert any(ret["snapshot"]["posting_ids"].values())
    assert ret["chain_head_hash"] == (await ledger.get_entries(A))[-1].hash

    for wanted in ("2031-12-31", None):
        with pytest.raises(BooksLocked) as refused:
            await ledger.set_lock_date(A, wanted)
        assert "has a return filed on 2032-06-01 (XG-123)" in str(refused.value)
        assert "lock date earlier" not in str(refused.value)
    # Later, or a day that leaves the year closed, is fine.
    await ledger.set_lock_date(A, "2032-04-30")
    await ledger.set_lock_date(A, "2032-03-31")

    with pytest.raises(ValueError, match="record an amendment"):
        await tax.record_return(A, computation["id"], "draft")
    with pytest.raises(ValueError, match="needs a reason"):
        await tax.record_return(A, computation["id"], "amended")
    amended = await tax.record_return(A, computation["id"], "amended", reason="Missed a bonus")
    assert (amended["version"], amended["supersedes_id"]) == (2, ret["id"])

    await ledger.set_lock_date(A, "2031-12-31")  # open now
    await ledger.set_lock_date(A, "2032-03-31")
    again = await tax.record_return(
        A, computation["id"], "filed", reference="XG-124", filed_on=datetime.date(2032, 9, 1)
    )
    assert again["version"] == 3
    with pytest.raises(BooksLocked):
        await ledger.set_lock_date(A, None)

    paid = await tax.add_return_payment(
        A, again["id"], paid_on=datetime.date(2032, 9, 2), amount=Decimal("12.5")
    )
    assert [(p["amount"], p["currency"]) for p in paid["payments"]] == [("12.500", "KWD")]
    assert [r["version"] for r in await tax.list_returns(A)] == [3, 2, 1]

    engine = create_engine(_sync(db))
    try:
        for statement in (
            "update tax_returns set reference = 'x'",
            "delete from tax_return_payments",
            "truncate tax_returns cascade",
        ):
            with pytest.raises(Exception, match="append-only"), engine.begin() as conn:
                conn.execute(text(statement))
    finally:
        engine.dispose()


async def test_erasure_clears_returns(filed, uow_factory, db):
    async with uow_factory() as uow:
        await uow.data_portability.delete_all(A)
    assert scalar(db, "select count(*) from tax_returns") == 0


async def _ledger(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("ana", {"base_currency": "NZD"})
    ledger = LedgerService(uow_factory, today=lambda: datetime.date(2027, 2, 1))
    bank = await ledger.add_account("ana", "1000", "Bank", "asset")
    pay = await ledger.add_account("ana", "4000", "Pay", "income")
    food = await ledger.add_account("ana", "5000", "Food", "expense")
    kept = await ledger.add_account("ana", "3900", "Retained earnings", "equity")

    def legs(debit: str, credit: str, amount: str) -> list[dict[str, object]]:
        return [
            {"account_id": debit, "direction": Direction.DEBIT, "amount": Decimal(amount)},
            {"account_id": credit, "direction": Direction.CREDIT, "amount": Decimal(amount)},
        ]

    await ledger.add_entry("ana", "2026-03-01", "Pay", "manual", legs(bank, pay, "900"))
    await ledger.add_entry("ana", "2026-04-01", "Food", "manual", legs(food, bank, "250.50"))
    return ledger, {"bank": bank, "pay": pay, "food": food, "kept": kept}


async def test_a_year_end_close_moves_earnings_to_retained_earnings(uow_factory):
    ledger, ids = await _ledger(uow_factory)
    with pytest.raises(ValueError, match="retained earnings first"):
        await ledger.close_year("ana", "2026-12-31")
    with pytest.raises(ValueError, match="Retained earnings are equity"):
        await ledger.set_retained_earnings("ana", ids["food"])
    await ledger.set_retained_earnings("ana", ids["kept"])

    closed = await ledger.close_year("ana", "2026-12-31")
    assert (closed["earnings"], closed["currency"]) == ("649.50", "NZD")
    entry = await ledger.get_entry("ana", closed["entry_id"])
    assert entry is not None
    assert (entry.entry_date, entry.source) == ("2026-12-31", "year_end_close")
    balances = await ledger.get_trial_balance("ana")
    assert balances[ids["pay"]] == balances[ids["food"]] == 0
    assert balances[ids["kept"]] == Decimal("-649.50")
    with pytest.raises(ValueError, match="nothing to close"):
        await ledger.close_year("ana", "2026-12-31")


async def test_entries_record_their_author_and_the_chain_finds_a_change(uow_factory, db):
    ledger, ids = await _ledger(uow_factory)
    set_author("ana", "mcp:claude")
    try:
        await ledger.add_entry(
            "ana",
            "2026-05-01",
            "Lunch",
            "manual",
            [
                {"account_id": ids["food"], "direction": Direction.DEBIT, "amount": Decimal("9")},
                {"account_id": ids["bank"], "direction": Direction.CREDIT, "amount": Decimal("9")},
            ],
        )
    finally:
        set_author(None, "automation")
    entries = await ledger.get_entries("ana")
    assert [(e.seq, e.created_via) for e in entries] == [
        (1, "automation"),
        (2, "automation"),
        (3, "mcp:claude"),
    ]
    assert entries[1].hash and entries[2].hash
    assert await ledger.verify_chain("ana") == {"ok": True, "checked": 3, "first_break": None}

    # Changed behind the database's back (its triggers off, as a superuser can).
    engine = create_engine(_sync(db))
    try:
        with engine.begin() as conn:
            conn.execute(text("alter table journal_entries disable trigger user"))
            conn.execute(text("update journal_entries set description = 'Groceries' where seq = 2"))
            conn.execute(text("alter table journal_entries enable trigger user"))
    finally:
        engine.dispose()
    check = await ledger.verify_chain("ana")
    assert check["ok"] is False and check["checked"] == 1
    assert check["first_break"]["seq"] == 2 and check["first_break"]["reason"] == "content"


async def test_a_document_behind_a_filed_return_is_kept_from_the_filing(uow_factory, rules):
    from salli.application.services.document_service import DocumentRetained, DocumentService

    class _Storage:
        async def upload(self, user_id: str, key: str, data: bytes) -> str:
            return f"{user_id}/{key}"

    async with uow_factory() as uow:
        await uow.user_profiles.upsert(A, {"document_retention_years": 1})
    day = [datetime.date(2031, 6, 30)]
    docs = DocumentService(uow_factory, _Storage(), today=lambda: day[0])  # type: ignore[arg-type]
    await _activate(rules, remitland())
    await _book(uow_factory, A, local="1000.000")
    receipt = (await docs.save_file(A, "payslip.pdf", b"%PDF"))["id"]
    ledger = LedgerService(uow_factory, today=lambda: LATER)
    codes = {a.code: a.id for a in await ledger.list_accounts(A)}
    legs = [
        {"account_id": codes["1000"], "direction": Direction.DEBIT, "amount": Decimal("5")},
        {"account_id": codes["4000"], "direction": Direction.CREDIT, "amount": Decimal("5")},
    ]
    await ledger.add_entry(A, "2031-06-30", "Bonus", "manual", legs, external_ref=receipt)
    tax = TaxService(uow_factory, rules, clock=lambda: LATER)
    computation = await tax.compute_tax(A, country="XG", year="2031/32")
    await ledger.set_lock_date(A, "2032-03-31")
    await tax.record_return(
        A, computation["id"], "filed", reference="XG-9", filed_on=datetime.date(2032, 6, 1)
    )

    # Its own retention ended 2032-06-30; the return's runs from its filing.
    day[0] = datetime.date(2032, 7, 1)
    with pytest.raises(DocumentRetained, match="2033-06-01"):
        await docs.delete_document(A, receipt)
    day[0] = datetime.date(2033, 6, 1)
    await docs.delete_document(A, receipt)


async def test_a_break_in_a_filed_year_is_reported(filed, db):
    _, ledger, _, _ = filed
    assert await ledger.verify_chain(A) == {
        "ok": True,
        "checked": len(await ledger.get_entries(A)),
        "first_break": None,
    }
    engine = create_engine(_sync(db))
    try:
        with engine.begin() as conn:
            conn.execute(text("alter table journal_entries disable trigger user"))
            conn.execute(
                text(
                    "update journal_entries set description = 'Changed' where seq = 1 and user_id = :u"
                ),
                {"u": A},
            )
            conn.execute(text("alter table journal_entries enable trigger user"))
    finally:
        engine.dispose()
    check = await ledger.verify_chain(A)
    assert check["first_break"]["filed_years"] == ["2031/32"]
