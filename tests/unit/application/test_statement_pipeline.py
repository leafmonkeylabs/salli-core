"""
The statement import pipeline as a service: the account a statement is for,
and what happens to its rows on the way to review and posting.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

import salli.adapters.parsing.llm_classifier as llm_classifier
from salli.application.services.llm_credential_service import ResolvedCredentials
from salli.application.services.parsing_service import ParsingService
from salli.application.services.rules_service import RulesService
from salli.domain.accounting.models import Account, StoredJournalEntry
from salli.domain.parsing.models import ParsedTransaction, RawRow
from salli.domain.secrets import Secret
from tests.fakes import FakeProfiles
from tests.unit.application.test_rules_service import Rules

USER = "u1"
FIXTURES = Path(__file__).parents[2] / "fixtures" / "statements"


def _account(id_: str, type_: str, currency: str = "USD", active: bool = True) -> Account:
    return Account(
        id=id_,
        user_id=USER,
        code=id_,
        name=id_.title(),
        type=type_,
        currency=currency,
        is_active=active,
    )


ACCOUNTS = [
    _account("checking", "asset"),
    _account("card", "liability"),
    _account("euros", "asset", currency="EUR"),
    _account("closed", "asset", active=False),
    _account("food", "expense"),
    _account("transport", "expense"),
    _account("retired", "expense", active=False),
    _account("salary", "income"),
]


class Ledger:
    def __init__(self, accounts: list[Account]) -> None:
        self.accounts = {a.id: a for a in accounts}
        self.entries: list[StoredJournalEntry] = []

    async def get_account(self, user_id: str, account_id: str) -> Account | None:
        return self.accounts.get(account_id)

    async def get_accounts(self, user_id: str, include_inactive: bool = False) -> list[Account]:
        return [a for a in self.accounts.values() if include_inactive or a.is_active]

    async def get_entries(
        self, user_id: str, from_date: str | None = None, to_date: str | None = None
    ) -> list[StoredJournalEntry]:
        return [
            e
            for e in self.entries
            if (from_date is None or e.entry_date >= from_date)
            and (to_date is None or e.entry_date <= to_date)
        ]

    async def save_entry(self, user_id: str, entry: Any) -> str:
        entry_id = f"e{len(self.entries) + 1}"
        self.entries.append(StoredJournalEntry(id=entry_id, user_id=user_id, **entry.model_dump()))
        return entry_id


class Statements:
    def __init__(self) -> None:
        self.statements: dict[str, dict[str, Any]] = {}
        self.rows: dict[str, ParsedTransaction] = {}

    async def save_statement(
        self,
        user_id: str,
        statement_id: str,
        bank: str,
        period_start: str,
        period_end: str,
        transactions: list[ParsedTransaction],
        storage_key: str = "",
        account_id: str | None = None,
    ) -> None:
        self.statements[statement_id] = {
            "id": statement_id,
            "bank": bank,
            "account_id": account_id,
            "period_start": period_start,
            "period_end": period_end,
            "storage_key": storage_key,
        }
        for txn in transactions:
            txn.id, txn.statement_id = str(uuid.uuid4()), statement_id
            txn.account_id = account_id or ""
            self.rows[txn.id] = replace(txn)

    async def get_statement(self, user_id: str, statement_id: str) -> dict[str, Any] | None:
        return self.statements.get(statement_id)

    async def get_pending(self, user_id: str, statement_id: str) -> list[ParsedTransaction]:
        return [
            replace(t)
            for t in self.rows.values()
            if t.statement_id == statement_id
            and t.dedup_status not in ("posted", "discarded", "exact_duplicate")
        ]

    async def discard(self, user_id: str, statement_id: str, ids: list[str] | None = None) -> int:
        chosen = [
            t for t in await self.get_pending(user_id, statement_id) if ids is None or t.id in ids
        ]
        for t in chosen:
            self.rows[t.id].dedup_status = "discarded"
        return len(chosen)

    async def imported_between(
        self, user_id: str, from_date: str, to_date: str
    ) -> list[ParsedTransaction]:
        return [
            replace(t)
            for t in self.rows.values()
            if from_date <= t.raw.date <= to_date and t.dedup_status != "exact_duplicate"
        ]

    async def get_by_ids(self, user_id: str, ids: list[str]) -> list[ParsedTransaction]:
        return [replace(self.rows[i]) for i in ids if i in self.rows]

    async def mark_posted(self, transaction_id: str, entry_id: str) -> None:
        self.rows[transaction_id].dedup_status = "posted"


class World:
    def __init__(self, base_currency: str = "LKR") -> None:
        self.ledger = Ledger(ACCOUNTS)
        self.statements = Statements()
        self.user_profiles = FakeProfiles(base_currency)
        self.rules = Rules()

    @asynccontextmanager
    async def uow(self):
        yield self

    def service(self, **kwargs: Any) -> ParsingService:
        return ParsingService(self.uow, rules=RulesService(self.uow), **kwargs)


@pytest.fixture
def world() -> World:
    return World()


class ModelCalls(list[list[RawRow]]):
    """The rows the model was asked about, one list per call, and how."""

    def __init__(self) -> None:
        super().__init__()
        self.asked: list[dict[str, Any]] = []


@pytest.fixture(autouse=True)
def model(monkeypatch):
    """A stand-in for the model: money out to food, money in from salary, the
    bank side on checking. It records what it was asked about, and how."""
    calls = ModelCalls()

    async def classify(rows: list[RawRow], accounts: Any, **kwargs: Any) -> list[ParsedTransaction]:
        calls.append(list(rows))
        calls.asked.append(kwargs)
        money = kwargs.get("money_account")
        bank = money.id if money is not None else "checking"
        return [
            ParsedTransaction(
                raw=row,
                debit_account_id=bank if row.credit_flag else "food",
                credit_account_id="salary" if row.credit_flag else bank,
                category="groceries",
                confidence=0.9,
            )
            for row in rows
        ]

    monkeypatch.setattr(llm_classifier, "classify_transactions", classify)
    return calls


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# ── The account a statement is for ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("account_id", "message"),
    [
        ("food", "Food is an expense account"),
        ("closed", "No active account 'closed'"),
        ("nowhere", "No active account 'nowhere'"),
    ],
)
async def test_a_statement_is_for_one_of_the_users_money_accounts(world, account_id, message):
    with pytest.raises(ValueError, match=message):
        await world.service().parse_statement(
            USER, "s.csv", _fixture("us_checking.csv"), account_id=account_id, api_key="k"
        )


async def test_the_account_is_the_money_side_and_its_currency_the_default(world):
    # A CSV names no currency: its rows are in the account's (USD), not the
    # user's base currency (LKR).
    result = await world.service().parse_statement(
        USER, "s.csv", _fixture("us_checking.csv"), account_id="checking", api_key="k"
    )

    assert {t.raw.currency for t in result.transactions} == {"USD"}
    for txn in result.transactions:
        assert txn.account_id == "checking"
        if txn.raw.credit_flag:  # money in: the account is debited
            assert (txn.debit_account_id, txn.credit_account_id) == ("checking", "salary")
        else:  # money out: the account is credited
            assert (txn.debit_account_id, txn.credit_account_id) == ("food", "checking")
    (statement,) = world.statements.statements.values()
    assert statement["account_id"] == "checking"


async def test_a_row_in_another_currency_than_the_account_is_skipped(world):
    # The fixture's wire from London is in pounds; the account is in dollars.
    result = await world.service().parse_statement(
        USER, "s.ofx", _fixture("ofx1_checking.ofx"), account_id="checking", api_key="k"
    )

    assert len(result.transactions) == 6
    assert "INCOMING WIRE" not in " ".join(t.raw.description for t in result.transactions)
    assert result.errors == ["Skipped 1 transaction(s) in GBP: Checking is kept in USD"]


async def test_a_currency_that_contradicts_the_account_is_refused(world):
    with pytest.raises(ValueError, match="Euros is kept in EUR, not USD"):
        await world.service().parse_statement(
            USER,
            "s.csv",
            _fixture("us_checking.csv"),
            account_id="euros",
            currency="USD",
            api_key="k",
        )


async def test_without_an_account_rows_are_in_the_base_currency(world):
    result = await world.service().parse_statement(
        USER, "s.csv", _fixture("us_checking.csv"), api_key="k"
    )
    assert {t.raw.currency for t in result.transactions} == {"LKR"}
    assert {t.account_id for t in result.transactions} == {""}
    first = result.transactions[0]
    assert first.raw.amount == Decimal("84.17")
    # Nothing forces a side: both are as the model chose them.
    assert (first.debit_account_id, first.credit_account_id) == ("food", "checking")


# ── Rows from anywhere: import_rows ───────────────────────────────────────────


class Storage:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, str, bytes]] = []

    async def upload(self, user_id: str, key: str, data: bytes) -> str:
        self.uploads.append((user_id, key, data))
        return f"stored/{key}"


def _row(
    description: str,
    amount: str,
    money_in: bool = False,
    date: str = "2026-10-05",
    bank_ref: str = "",
    currency: str = "USD",
) -> RawRow:
    return RawRow(
        date=date,
        description=description,
        amount=Decimal(amount),
        credit_flag=money_in,
        currency=currency,
        bank_ref=bank_ref,
    )


async def test_rows_from_a_feed_import_without_a_file(world):
    storage = Storage()
    feed = [
        _row("BLUE BOTTLE COFFEE", "4.50", bank_ref="txn_8f2k"),
        _row("NORTHWIND PAYROLL", "2400.00", money_in=True, date="2026-10-01", bank_ref="txn_8f2m"),
    ]

    result = await world.service(storage=storage).import_rows(
        USER, feed, bank="Example Bank", account_id="checking", api_key="k"
    )

    assert storage.uploads == []  # a feed has no file to keep
    assert (result.period_start, result.period_end) == ("2026-10-01", "2026-10-05")
    assert [t.raw.bank_ref for t in result.transactions] == ["txn_8f2k", "txn_8f2m"]
    (statement,) = world.statements.statements.values()
    assert statement | {"id": "-"} == {
        "id": "-",
        "bank": "Example Bank",
        "account_id": "checking",
        "period_start": "2026-10-01",
        "period_end": "2026-10-05",
        "storage_key": "",
    }


async def test_the_original_file_is_kept(world):
    storage = Storage()
    data = _fixture("us_checking.csv")

    result = await world.service(storage=storage).parse_statement(
        USER, "october.csv", data, account_id="checking", api_key="k"
    )

    assert storage.uploads == [(USER, f"{result.statement_id}/october.csv", data)]
    assert world.statements.statements[result.statement_id]["storage_key"] == (
        f"stored/{result.statement_id}/october.csv"
    )


async def test_nothing_to_import(world):
    result = await world.service().import_rows(USER, [], bank="", account_id=None)
    assert (result.statement_id, result.errors) == ("", ["No transactions to import"])

    result = await world.service().import_rows(
        USER, [_row("HOTEL", "120.00", currency="EUR")], bank="", account_id="checking"
    )
    assert result.errors == [
        "Skipped 1 transaction(s) in EUR: Checking is kept in USD",
        "No transactions to import",
    ]
    assert world.statements.statements == {}


# ── Posting what was approved ─────────────────────────────────────────────────


def _parsed(world: World, row: RawRow, debit: str, credit: str, **fields: Any) -> str:
    """A row as an import leaves it, pending review; its id."""
    row_id = str(uuid.uuid4())
    world.statements.rows[row_id] = ParsedTransaction(
        raw=row, debit_account_id=debit, credit_account_id=credit, id=row_id, **fields
    )
    return row_id


@pytest.fixture
def usd_world() -> World:
    return World(base_currency="USD")


async def test_tags_go_on_the_other_side_never_the_bank_account(usd_world):
    paid = _parsed(
        usd_world,
        _row("KEELLS", "12.00"),
        "food",
        "checking",
        category="groceries",
        need="essential",
        account_id="checking",
    )
    received = _parsed(
        usd_world,
        _row("PAYROLL", "2400.00", money_in=True),
        "checking",
        "salary",
        category="Salary",
        account_id="checking",
    )

    await usd_world.service().post_approved(USER, [paid, received])

    spent, earned = usd_world.ledger.entries
    assert [p.tags for p in spent.postings] == [{"category": "groceries", "need": "essential"}, {}]
    # Money in: the income is the credit, so that is where the tag goes.
    assert [p.tags for p in earned.postings] == [{}, {"category": "salary"}]


async def test_without_a_statement_account_the_income_or_expense_side_is_tagged(usd_world):
    received = _parsed(
        usd_world, _row("PAYROLL", "2400.00", money_in=True), "checking", "salary", category="pay"
    )
    moved = _parsed(usd_world, _row("TO CARD", "50.00"), "card", "checking", category="transfer")

    await usd_world.service().post_approved(USER, [received, moved])

    earned, transfer = usd_world.ledger.entries
    assert [p.tags for p in earned.postings] == [{}, {"category": "pay"}]
    # Neither side is income or expense: the debit, as before.
    assert [p.tags for p in transfer.postings] == [{"category": "transfer"}, {}]


async def test_an_entry_is_booked_with_the_description_it_should_have(usd_world):
    plain = _parsed(usd_world, _row("POS 4821 WHOLEFDS", "84.17"), "food", "checking")
    renamed = _parsed(
        usd_world,
        _row("AMZN MKTP US*2K4LT0", "12.99"),
        "food",
        "checking",
        description="Amazon",
    )

    await usd_world.service().post_approved(USER, [plain, renamed])

    assert [e.description for e in usd_world.ledger.entries] == ["POS 4821 WHOLEFDS", "Amazon"]


async def test_a_row_is_posted_once(usd_world):
    row = _parsed(usd_world, _row("RENT", "1200.00"), "food", "checking")

    first = await usd_world.service().post_approved(USER, [row])
    again = await usd_world.service().post_approved(USER, [row])

    assert (len(first), again) == (1, [])
    assert len(usd_world.ledger.entries) == 1


# ── Duplicates ────────────────────────────────────────────────────────────────


async def test_importing_a_statement_again_marks_every_row_and_posts_none(usd_world, model):
    data = _fixture("us_checking.csv")
    first = await usd_world.service().parse_statement(
        USER, "oct.csv", data, account_id="checking", api_key="k"
    )
    first_ids = [t.id for t in first.transactions]
    model.clear()

    again = await usd_world.service().parse_statement(
        USER, "oct.csv", data, account_id="checking", api_key="k"
    )

    assert {t.dedup_status for t in again.transactions} == {"exact_duplicate"}
    assert [t.duplicate_of for t in again.transactions] == first_ids
    assert model == []  # a duplicate costs no model call
    stored = [r for r in usd_world.statements.rows.values() if r.statement_id == again.statement_id]
    assert await usd_world.service().post_approved(USER, [r.id for r in stored]) == []


async def test_two_identical_rows_in_one_statement_are_both_kept(world):
    coffee = _row("BLUE BOTTLE COFFEE", "4.50")
    result = await world.service().import_rows(
        USER, [coffee, coffee], bank="", account_id="checking", api_key="k"
    )
    assert [t.dedup_status for t in result.transactions] == ["pending", "pending"]


async def test_a_transaction_booked_by_hand_is_flagged_for_review(usd_world):
    from salli.domain.accounting.models import Direction, JournalEntry, Posting

    await usd_world.ledger.save_entry(
        USER,
        JournalEntry(
            entry_date="2026-10-04",
            description="Blue Bottle coffee",
            source="manual",
            postings=[
                Posting(
                    account_id="food",
                    direction=Direction.DEBIT,
                    amount=Decimal("4.50"),
                    currency="USD",
                ),
                Posting(
                    account_id="checking",
                    direction=Direction.CREDIT,
                    amount=Decimal("4.50"),
                    currency="USD",
                ),
            ],
        ),
    )

    result = await usd_world.service().import_rows(
        USER, [_row("BLUE BOTTLE COFFEE", "4.50")], bank="", account_id="checking", api_key="k"
    )

    (txn,) = result.transactions
    assert (txn.dedup_status, txn.duplicate_of) == ("fuzzy_match", "e1")
    # Flagged, not dropped: the user may still post it.
    (stored,) = usd_world.statements.rows.values()
    assert len(await usd_world.service().post_approved(USER, [stored.id])) == 1


async def test_rows_on_another_account_are_not_duplicates(world):
    coffee = _row("BLUE BOTTLE COFFEE", "4.50", bank_ref="FIT-1")
    await world.service().import_rows(USER, [coffee], bank="", account_id="checking", api_key="k")

    on_card = await world.service().import_rows(
        USER, [coffee], bank="", account_id="card", api_key="k"
    )

    assert [t.dedup_status for t in on_card.transactions] == ["pending"]


# ── Rules before the model ────────────────────────────────────────────────────


def _rule(world: World, contains: str, **actions: str) -> str:
    rule_id = f"r{len(world.rules.rows) + 1}"
    world.rules.rows[rule_id] = {
        "id": rule_id,
        "name": contains.title(),
        "priority": 10,
        "match_all": True,
        "enabled": True,
        "conditions": [{"field": "description", "operator": "contains", "value": contains}],
        "actions": actions,
    }
    return rule_id


async def test_a_rule_decides_its_rows_and_the_model_sees_only_the_rest(world, model):
    uber = _rule(
        world,
        "uber",
        account_id="transport",
        category="rides",
        need="essential",
        description="Uber",
    )
    rows = [_row("UBER *TRIP 8H3K2", "23.40"), _row("WHOLE FOODS", "84.17")]

    result = await world.service().import_rows(
        USER, rows, bank="", account_id="checking", api_key="k"
    )

    ride, groceries = result.transactions
    assert (ride.debit_account_id, ride.credit_account_id) == ("transport", "checking")
    assert (ride.rule_id, ride.category, ride.need, ride.description) == (
        uber,
        "rides",
        "essential",
        "Uber",
    )
    assert ride.confidence == 1.0
    assert (groceries.debit_account_id, groceries.rule_id) == ("food", "")
    # The model was asked about the groceries only, and told whose statement it is.
    assert [[r.description for r in call] for call in model] == [["WHOLE FOODS"]]
    assert model.asked[0]["money_account"].id == "checking"
    assert world.rules.hits == {uber: 1}


async def test_a_rule_that_only_tags_leaves_the_account_to_the_model(world, model):
    _rule(world, "foods", category="groceries", need="essential")

    result = await world.service().import_rows(
        USER, [_row("WHOLE FOODS", "84.17")], bank="", account_id="checking", api_key="k"
    )

    (txn,) = result.transactions
    assert (txn.debit_account_id, txn.need) == ("food", "essential")
    assert len(model) == 1


async def test_a_rules_retired_account_is_not_booked_to(world, model):
    _rule(world, "foods", account_id="retired", category="groceries")

    result = await world.service().import_rows(
        USER, [_row("WHOLE FOODS", "84.17")], bank="", account_id="checking", api_key="k"
    )

    # The rule's tag stands; the account is the model's to choose.
    assert (result.transactions[0].debit_account_id, result.transactions[0].category) == (
        "food",
        "groceries",
    )


async def test_an_account_the_model_invents_is_dropped(world, monkeypatch):
    async def classify(rows: list[RawRow], accounts: Any, **_: Any) -> list[ParsedTransaction]:
        return [
            ParsedTransaction(raw=r, debit_account_id="made-up", credit_account_id="checking")
            for r in rows
        ]

    monkeypatch.setattr(llm_classifier, "classify_transactions", classify)

    result = await world.service().import_rows(
        USER, [_row("WHOLE FOODS", "84.17")], bank="", account_id="checking", api_key="k"
    )

    (txn,) = result.transactions
    assert (txn.debit_account_id, txn.credit_account_id, txn.confidence) == ("", "checking", 0.0)
    assert result.errors == ["1 transaction(s) still need an account; choose one to post"]


class NoKey:
    """A deployment with no platform key, and a user who has not added one."""

    async def resolve(self, user_id: str) -> ResolvedCredentials:
        return ResolvedCredentials(anthropic=Secret(""), anthropic_is_user_key=False)


@pytest.mark.parametrize("credentials", [NoKey(), None])
async def test_without_an_ai_key_the_rules_sort_what_they_can(world, model, credentials):
    _rule(world, "uber", account_id="transport")
    rows = [_row("UBER *TRIP 8H3K2", "23.40"), _row("WHOLE FOODS", "84.17")]

    result = await world.service(credentials=credentials).import_rows(
        USER, rows, bank="", account_id="checking"
    )

    ride, groceries = result.transactions
    assert (ride.debit_account_id, ride.confidence) == ("transport", 1.0)
    assert (groceries.debit_account_id, groceries.credit_account_id) == ("", "checking")
    assert groceries.confidence == 0.0
    assert model == []
    assert result.errors == [
        "1 transaction(s) need an account: with no AI key set up, only your rules sorted "
        "this statement"
    ]
    assert len(world.statements.rows) == 2  # imported all the same, for review


# ── Review ────────────────────────────────────────────────────────────────────


async def test_an_import_returns_the_ids_its_rows_were_saved_under(world):
    result = await world.service().parse_statement(
        USER, "oct.csv", _fixture("us_checking.csv"), account_id="checking", api_key="k"
    )

    ids = [t.id for t in result.transactions]
    assert all(ids) and set(ids) == set(world.statements.rows)
    assert {t.statement_id for t in result.transactions} == {result.statement_id}


async def test_a_discarded_row_never_posts_and_leaves_review(usd_world):
    result = await usd_world.service().parse_statement(
        USER, "oct.csv", _fixture("us_checking.csv"), account_id="checking", api_key="k"
    )
    statement_id = result.statement_id
    first, *rest = (t.id for t in result.transactions)
    service = usd_world.service()

    assert await service.discard(USER, statement_id, [first]) == 1
    pending = await service.get_pending(USER, statement_id)
    assert [t.id for t in pending] == rest
    assert await service.post_approved(USER, [first]) == []

    assert await service.discard(USER, statement_id) == len(rest)  # the rest
    assert await service.get_pending(USER, statement_id) == []
    assert await service.discard(USER, "not-theirs") is None


async def test_a_discarded_row_is_no_duplicate_of_a_later_import(world):
    coffee = _row("BLUE BOTTLE COFFEE", "4.50")
    first = await world.service().import_rows(
        USER, [coffee], bank="", account_id="checking", api_key="k"
    )
    await world.service().discard(USER, first.statement_id)

    again = await world.service().import_rows(
        USER, [coffee], bank="", account_id="checking", api_key="k"
    )

    assert [t.dedup_status for t in again.transactions] == ["pending"]


async def test_a_discarded_bank_transaction_does_not_come_back_with_the_next_sync(world):
    # The feed overlaps its last sync; what the user discarded is still that
    # bank transaction, by its reference.
    card_hold = _row("HOTEL AUTH HOLD", "200.00", bank_ref="t-77")
    first = await world.service().import_rows(
        USER, [card_hold], bank="", account_id="checking", api_key="k"
    )
    await world.service().discard(USER, first.statement_id)

    again = await world.service().import_rows(
        USER, [card_hold], bank="", account_id="checking", api_key="k", keep_duplicates=False
    )

    assert (again.statement_id, again.transactions, again.duplicates_dropped) == ("", [], 1)


async def test_a_feed_leaves_out_what_it_imported_before_and_keeps_what_is_new(world, model):
    seen = _row("WHOLE FOODS", "84.17", bank_ref="t-1")
    new = _row("BLUE BOTTLE COFFEE", "4.50", date="2026-10-06", bank_ref="t-2")
    await world.service().import_rows(USER, [seen], bank="", account_id="checking", api_key="k")
    model.clear()

    synced = await world.service().import_rows(
        USER, [seen, new], bank="", account_id="checking", api_key="k", keep_duplicates=False
    )

    assert [t.raw.bank_ref for t in synced.transactions] == ["t-2"]
    assert synced.duplicates_dropped == 1
    assert [[r.bank_ref for r in call] for call in model] == [["t-2"]]
    # An exact duplicate a statement keeps is in its result, never in review.
    stored = await world.service().import_rows(
        USER, [seen], bank="", account_id="checking", api_key="k"
    )
    assert [t.dedup_status for t in stored.transactions] == ["exact_duplicate"]
    assert await world.service().get_pending(USER, stored.statement_id) == []


class Meter:
    def __init__(self, refuse: bool = False) -> None:
        self.charged: list[tuple[str, Any, str | None]] = []
        self.refuse = refuse

    async def charge(self, user_id: str, action: Any, *, model_id: Any = None, email: Any = None):
        from salli.domain.usage import UsageLimitReached

        if self.refuse:
            raise UsageLimitReached(action, message="Monthly imports used up", status_code=402)
        self.charged.append((user_id, action, email))


async def test_the_meter_is_charged_only_when_the_model_is_asked(world, model):
    from salli.domain.usage import AIAction

    _rule(world, "uber", account_id="transport")
    meter = Meter()
    service = world.service(usage=meter)

    # The user's rules sort it all: no model, no charge.
    await service.import_rows(
        USER, [_row("UBER *TRIP 8H3K2", "23.40")], bank="", account_id="checking", api_key="k"
    )
    assert meter.charged == []

    await service.import_rows(
        USER,
        [_row("WHOLE FOODS", "84.17")],
        bank="",
        account_id="checking",
        api_key="k",
        email="me@example.com",
    )
    assert meter.charged == [(USER, AIAction.STATEMENT_IMPORT, "me@example.com")]


async def test_a_refusing_meter_refuses_a_request_and_lets_a_sync_go_on(world, model):
    from salli.domain.usage import UsageLimitReached

    service = world.service(usage=Meter(refuse=True))
    rows = [_row("WHOLE FOODS", "84.17")]
    with pytest.raises(UsageLimitReached):
        await service.import_rows(USER, rows, bank="", account_id="checking", api_key="k")

    synced = await service.import_rows(
        USER, rows, bank="", account_id="checking", api_key="k", on_usage_limit="skip"
    )
    [groceries] = synced.transactions
    assert groceries.debit_account_id == ""  # no rule, and the model was not asked
    assert model == [] and any("Monthly imports used up" in e for e in synced.errors)
