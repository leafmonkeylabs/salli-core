"""
The household basics against a real Postgres: recategorising a booked entry
(a reversal and a corrected copy, the chain intact), the monthly budget with
rollover and its signals, owe lines with a rate becoming linked debts, and
push alerts (devices sealed, once per state, nothing from the ledger said).
"""

from __future__ import annotations

import base64
import datetime as dt
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from salli.adapters.crypto.keyring import KeyRing
from salli.application.services.budget_service import BudgetService
from salli.application.services.debt_service import DebtService
from salli.application.services.insights_service import InsightsService
from salli.application.services.ledger_service import LedgerService
from salli.application.services.notification_service import (
    NotificationService,
    PreferencesError,
    PushUnavailable,
)
from salli.application.services.reminder_service import ReminderService
from salli.application.services.user_profile_service import UserProfileService
from salli.domain.accounting.models import Direction
from tests.fakes import RecordingNotifier
from tests.guardrails import assert_never_urges
from tests.integration.pg import requires_postgres

pytestmark = [requires_postgres, pytest.mark.asyncio]

TODAY = dt.date(2026, 10, 12)
NOW = dt.datetime(2026, 10, 12, 8, 30, tzinfo=dt.UTC)
KEYS = "1:" + base64.b64encode(b"k" * 32).decode()


def _legs(debit: str, credit: str, amount: str) -> list[dict[str, object]]:
    return [
        {"account_id": debit, "direction": Direction.DEBIT, "amount": Decimal(amount)},
        {"account_id": credit, "direction": Direction.CREDIT, "amount": Decimal(amount)},
    ]


async def _books(uow_factory, user: str = "kofi"):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(user, {"base_currency": "GHS"})
    ledger = LedgerService(uow_factory, today=lambda: TODAY)
    bank = await ledger.add_account(user, "1000", "Zqbank", "asset")
    equity = await ledger.add_account(user, "3000", "Opening", "equity")
    food = await ledger.add_account(user, "5000", "Groceries", "expense")
    out = await ledger.add_account(user, "5100", "Eating out", "expense")
    await ledger.add_entry(user, "2026-08-01", "Opening", "manual", _legs(bank, equity, "100"))
    return ledger, bank, food, out


async def test_recategorise_books_a_reversal_and_a_corrected_copy(uow_factory):
    ledger, bank, food, out = await _books(uow_factory)
    lunch = await ledger.add_entry(
        "kofi", "2026-10-03", "Lunch", "manual", _legs(food, bank, "40"), "client-ref:lunch-1"
    )
    original = await ledger.get_entry("kofi", lunch)
    assert original is not None
    moved = next(p for p in original.postings if p.account_id == food)

    made = await ledger.recategorise_entry("kofi", lunch, moved.id or "", out, "Was a cafe")

    reversal = await ledger.get_entry("kofi", made["reversal_id"])
    corrected = await ledger.get_entry("kofi", made["corrected_id"])
    assert reversal is not None and corrected is not None
    assert (reversal.source, reversal.reverses, reversal.entry_date) == (
        "reversal",
        lunch,
        "2026-10-03",
    )
    # The copy keeps the original's provenance and links to it.
    assert (corrected.source, corrected.external_ref, corrected.corrects) == (
        "manual",
        "client-ref:lunch-1",
        lunch,
    )
    assert corrected.entry_date == "2026-10-03"
    provenance = await ledger.get_entry_provenance("kofi", made["corrected_id"])
    assert provenance is not None and provenance["corrects"] == lunch
    assert {p.account_id for p in corrected.postings} == {out, bank}
    again = await ledger.get_entry("kofi", lunch)
    assert again is not None and again.reversed_by == made["reversal_id"]
    assert (await ledger.verify_chain("kofi"))["first_break"] is None

    with pytest.raises(ValueError, match="already reversed"):
        await ledger.recategorise_entry("kofi", lunch, moved.id or "", food, "Again")


async def test_recategorise_keeps_the_type_and_dates_a_closed_day_today(uow_factory):
    ledger, bank, food, out = await _books(uow_factory)
    lunch = await ledger.add_entry("kofi", "2026-09-03", "Lunch", "manual", _legs(food, bank, "40"))
    entry = await ledger.get_entry("kofi", lunch)
    assert entry is not None
    on_food = next(p for p in entry.postings if p.account_id == food)
    with pytest.raises(ValueError, match="same type"):
        await ledger.recategorise_entry("kofi", lunch, on_food.id or "", bank, "Wrong")
    await ledger.deactivate_account("kofi", out)
    with pytest.raises(ValueError, match="inactive"):
        await ledger.recategorise_entry("kofi", lunch, on_food.id or "", out, "Cafe")
    await ledger.reactivate_account("kofi", out)

    await ledger.set_lock_date("kofi", "2026-09-30")
    made = await ledger.recategorise_entry("kofi", lunch, on_food.id or "", out, "Cafe")
    corrected = await ledger.get_entry("kofi", made["corrected_id"])
    assert corrected is not None and corrected.entry_date == TODAY.isoformat()


async def test_the_monthly_budget_rolls_over_and_signals(uow_factory):
    ledger, bank, food, out = await _books(uow_factory)
    budget = BudgetService(uow_factory, today=lambda: dt.date(2026, 9, 1))
    await budget.set_monthly_lines(
        "kofi",
        [
            {"account_id": food, "limit_amount": "50", "rollover": True},
            {"account_id": out, "limit_amount": "20"},
        ],
    )
    with pytest.raises(ValueError, match="expense"):
        await budget.set_monthly_lines("kofi", [{"account_id": bank, "limit_amount": "5"}])
    await ledger.add_entry("kofi", "2026-09-10", "Shop", "manual", _legs(food, bank, "30"))
    await ledger.add_entry("kofi", "2026-10-02", "Shop", "manual", _legs(food, bank, "20"))
    await ledger.add_entry("kofi", "2026-10-03", "Cafe", "manual", _legs(out, bank, "25"))

    now = BudgetService(uow_factory, today=lambda: TODAY)
    current = await now.current("kofi")
    lines = {line["account_id"]: line for line in current["lines"]}
    assert lines[food]["carried"] == "20.00"
    assert lines[food]["available"] == "70.00"
    assert lines[food]["left"] == "50.00"
    assert lines[out]["left"] == "-5.00"
    trend = await now.trend("kofi", 2)
    assert trend["months"] == ["2026-09", "2026-10"]
    assert {c["account_id"]: c["spent"] for c in trend["categories"]}[food] == ["30.00", "20.00"]
    assert trend["totals"] == [
        str(sum((Decimal(c["spent"][i]) for c in trend["categories"]), Decimal(0)))
        for i in range(2)
    ]
    assert trend["totals"][1] == "45.00"

    insights = InsightsService(uow_factory, today=lambda: TODAY, budget=now)
    kinds = {s["kind"]: s for s in (await insights.signals("kofi"))["signals"]}
    assert kinds["budget_over"]["refs"] == [out]


async def test_an_owe_line_with_a_rate_is_a_linked_debt(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(
            "lena", {"base_currency": "NOK", "books_start": dt.date(2026, 10, 1)}
        )
    ledger = LedgerService(uow_factory, today=lambda: TODAY)
    profile = UserProfileService(uow_factory, ledger, MagicMock(), MagicMock())
    line = {
        "code": "2100",
        "name": "Car loan",
        "type": "liability",
        "amount": "12000",
        "rate": "0.06",
        "minimum_payment": "400",
    }
    await profile.declare_opening_balances("lena", [line])
    await profile.declare_opening_balances("lena", [{**line, "code": "2100", "amount": "0"}])

    debts = DebtService(uow_factory, today=lambda: TODAY)
    (debt,) = await debts.list_debts("lena")
    assert (debt["apr"], debt["minimum_payment"]) == ("0.0600", "400.00")
    assert debt["account_id"] is not None
    plan = await debts.get_payoff_plan("lena", Decimal(0), "avalanche")
    (planned,) = plan["debts"]
    assert (planned["apr"], planned["minimum_payment"]) == ("0.0600", "400.00")
    assert planned["payoff_month"] == plan["debt_free_month"]

    with pytest.raises(ValueError, match="something owed"):
        await profile.declare_opening_balances(
            "lena",
            [{"code": "1000", "name": "Bank", "type": "asset", "amount": "5", "rate": "0.1"}],
        )


def _push(uow_factory, notifier, keys: str = KEYS) -> NotificationService:
    return NotificationService(
        uow_factory,
        ReminderService(uow_factory),
        InsightsService(uow_factory, today=lambda: TODAY),
        notifier,
        clock=lambda: NOW,
        push_enabled=True,
        keyring=KeyRing(keys),
        budget=BudgetService(uow_factory, today=lambda: TODAY),
    )


async def test_push_alerts_go_once_per_state_and_say_nothing_of_the_ledger(uow_factory):
    ledger, bank, food, out = await _books(uow_factory)
    await ledger.add_entry(
        "kofi", "2026-10-03", "ZQCAFE 77.13", "manual", _legs(out, bank, "77.13")
    )
    await BudgetService(uow_factory, today=lambda: TODAY).set_monthly_lines(
        "kofi", [{"account_id": out, "limit_amount": "20"}]
    )
    async with uow_factory() as uow:
        await uow.reminders.create_reminder("kofi", "r1", "Pay Zqlandlord 900", "2026-10-11")

    with pytest.raises(PushUnavailable):
        await _push(uow_factory, RecordingNotifier(), keys="").add_device(
            "kofi", "ExponentPushToken[x]", "ios"
        )
    notifier = RecordingNotifier()
    svc = _push(uow_factory, notifier)
    device = await svc.add_device("kofi", "ExponentPushToken[abc]", "ios")
    async with uow_factory() as uow:
        (stored,) = await uow.notifications.devices("kofi")
    assert stored["token"] != "ExponentPushToken[abc]"
    assert svc.open_token(stored) == "ExponentPushToken[abc]"

    # Nothing goes until the person opts in.
    assert (await svc.send_pushes())["sent"] == 0
    await svc.set_preferences("kofi", {"push_items": ["reminder_due", "budget_over"]})
    first = await svc.send_pushes()
    second = await svc.send_pushes()
    assert (first["sent"], second["skipped"]) == (1, 1)
    (sent,) = notifier.sent
    assert sent.kind == "push"
    assert {i.kind for i in sent.items} >= {"budget_over", "reminder_due"}
    assert not any(word in sent.text for word in ("Zq", "77", "900", "Eating"))
    assert_never_urges(sent.text)

    assert await svc.remove_device("kofi", device["id"])
    assert await svc.devices("kofi") == []


async def test_push_alerts_take_the_kinds_chosen_and_wait_out_quiet_hours(uow_factory):
    ledger, bank, food, out = await _books(uow_factory)
    await ledger.add_entry(
        "kofi", "2026-10-03", "ZQCAFE 77.13", "manual", _legs(out, bank, "77.13")
    )
    await BudgetService(uow_factory, today=lambda: TODAY).set_monthly_lines(
        "kofi", [{"account_id": out, "limit_amount": "20"}]
    )
    async with uow_factory() as uow:
        await uow.reminders.create_reminder("kofi", "r1", "Pay Zqlandlord 900", "2026-10-11")
    notifier = RecordingNotifier()
    svc = _push(uow_factory, notifier)
    await svc.add_device("kofi", "ExponentPushToken[abc]", "ios")

    start = NOW.astimezone(dt.UTC).strftime("%H:00")
    end = (NOW.astimezone(dt.UTC) + dt.timedelta(hours=1)).strftime("%H:00")
    saved = await svc.set_preferences(
        "kofi", {"push_items": ["reminder_due"], "quiet_hours": {"start": start, "end": end}}
    )
    assert saved["push_items"] == ["reminder_due"]
    assert (await svc.send_pushes())["quiet"] == 1
    assert notifier.sent == []

    await svc.set_preferences("kofi", {"quiet_hours": None})
    assert (await svc.send_pushes())["sent"] == 1
    (sent,) = notifier.sent
    assert [i.kind for i in sent.items] == ["reminder_due"]

    with pytest.raises(PreferencesError):
        await svc.set_preferences("kofi", {"quiet_hours": {"start": "22:00", "end": "22:00"}})
    with pytest.raises(PreferencesError):
        await svc.set_preferences("kofi", {"push_items": ["transactions_to_review"]})
