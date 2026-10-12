"""
A digest says what is waiting, never what it is about (phase 3, decision 29),
and never presses (decision 30). From random people's data, full of
distinctive names, amounts and questions, every digest the service builds
holds none of them, no amount at all, and nothing from the "never" list.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from salli.application.services.notification_service import NotificationService
from salli.domain.notifications.digest import ITEM_KINDS
from tests.fakes import FakeUoW, RecordingNotifier
from tests.guardrails import assert_never_urges

NOW = dt.datetime(2026, 10, 12, 8, 30, tzinfo=dt.UTC)  # Monday 09:30 in Lisbon
TODAY = dt.date(2026, 10, 12)

#: Words no wording of Salli's contains, so finding one means it leaked.
names = st.from_regex(r"Zq[a-z]{4,10}", fullmatch=True)
amounts = st.decimals(
    min_value=Decimal("0.01"), max_value=Decimal("9999999.99"), places=2, allow_nan=False
)
sources = st.sampled_from([None, None, "decision", "tax_rules", "budget", "insurance"])
offsets = st.integers(min_value=-40, max_value=40)


@st.composite
def people(draw: st.DrawFn) -> dict[str, Any]:
    reminders: list[dict[str, Any]] = []
    secrets: list[str] = []
    for _ in range(draw(st.integers(0, 8))):
        name, amount = draw(names), draw(amounts)
        question = f"Should I buy the {draw(names)} for {amount}?"
        text = draw(
            st.sampled_from(
                [
                    f"Review your decision: {question}",
                    f"Pay {name} {amount}",
                    f"{name} return ({name} 2026)",
                    f"Over budget on {name} by {amount}",
                ]
            )
        )
        secrets += [name, str(amount), question]
        reminders.append(
            {
                "kind": text,
                "source_domain": draw(sources),
                "due_date": (TODAY + dt.timedelta(days=draw(offsets))).isoformat(),
                "status": draw(st.sampled_from(["pending", "pending", "done"])),
            }
        )
    return {
        "reminders": reminders,
        "secrets": secrets,
        "cash": draw(st.none() | offsets.map(lambda d: TODAY + dt.timedelta(days=abs(d)))),
        "review": draw(st.integers(0, 500)),
        "items": draw(st.lists(st.sampled_from(ITEM_KINDS), min_size=1, unique=True)),
        "cadence": draw(st.sampled_from(["weekly", "monthly"])),
    }


class Insights:
    def __init__(self, person: dict[str, Any]) -> None:
        self.person = person

    async def cash_below_zero_on(self, user_id: str, today: dt.date) -> dt.date | None:
        return self.person["cash"]

    async def transactions_waiting(self, user_id: str) -> tuple[int, dt.date | None]:
        n = self.person["review"]
        return n, (TODAY - dt.timedelta(days=3)) if n else None


class Reminders:
    async def sync_alerts(self, user_id: str, today: str) -> dict[str, int]:
        return {}


#: An amount in any of the usual forms: 950.00, 1,234.5, 1.234,56.
AMOUNT = re.compile(r"\d[\d,.]*[.,]\d")


@settings(max_examples=150, deadline=None)
@given(person=people())
async def test_no_digest_holds_a_name_an_amount_or_a_question(person):
    uow = FakeUoW("EUR")
    for i, r in enumerate(person["reminders"]):
        uow.reminders.rows[f"r{i}"] = {
            "id": f"r{i}",
            "user_id": "u1",
            "alert_type": None,
            "source_id": None,
            "severity": None,
            **r,
        }
    notifier = RecordingNotifier()
    service = NotificationService(
        uow.factory(),
        Reminders(),  # type: ignore[arg-type]
        Insights(person),  # type: ignore[arg-type]
        notifier,
        notifier_name="test",
        public_url="https://money.example.org",
        clock=lambda: NOW,
    )
    await service.set_preferences(
        "u1",
        {
            "enabled": True,
            "time_zone": "Europe/Lisbon",
            "items": person["items"],
            "cadence": person["cadence"],
        },
    )
    # Weekly digests go now; monthly ones went on the 5th (the month's first
    # Monday), so for those the preview is the message to check.
    preview = await service.preview("u1")
    await service.send_due()
    messages = [preview, *[n.text + n.subject for n in notifier.sent]]
    if preview["digest"] is not None:
        messages += [preview["digest"]["text"], preview["digest"]["subject"]]
        assert_never_urges(preview["digest"])
    rendered = " ".join(str(m) for m in messages)
    for secret in person["secrets"]:
        assert secret not in rendered
    assert not AMOUNT.search(rendered.replace("money.example.org", ""))
    for row in await service.deliveries("u1"):
        assert set(row) >= {"items", "hash"} and "text" not in row
        assert not any(secret in str(row) for secret in person["secrets"])
