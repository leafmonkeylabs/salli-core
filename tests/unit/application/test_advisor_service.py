"""Unit tests for AdvisorService using in-memory fakes."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest

from salli.application.services.advisor_service import AdvisorService

# ── In-memory fakes ────────────────────────────────────────────────────────────


class FakeAdvisoryRepo:
    def __init__(self):
        self._reports: dict[str, dict] = {}

    async def save(self, user_id, report):
        rid = str(uuid.uuid4())
        self._reports[rid] = {**report, "id": rid, "user_id": user_id}
        return rid

    async def get(self, user_id, report_id):
        r = self._reports.get(report_id)
        return r if r and r["user_id"] == user_id else None

    async def get_latest(self, user_id):
        matches = [r for r in self._reports.values() if r["user_id"] == user_id]
        return matches[-1] if matches else None

    async def list(self, user_id, limit=30):
        return [r for r in self._reports.values() if r["user_id"] == user_id][:limit]

    async def export(self, user_id):
        return [r for r in self._reports.values() if r["user_id"] == user_id]

    async def ran_today(self, user_id, day):
        return any(
            r["user_id"] == user_id and r.get("created_at", "").startswith(day)
            for r in self._reports.values()
        )


class FakeReminderRepo:
    def __init__(self):
        self.created: list[tuple] = []

    async def create_reminder(self, user_id, reminder_id, label, due_date):
        self.created.append((user_id, reminder_id, label, due_date))
        return reminder_id


class FakeUserProfileRepo:
    """The daily run is now driven by an opt-in profile flag, not by plan."""

    def __init__(self, optins):
        self._optins = optins
        self.flags: dict[tuple[str, str], bool] = {}

    async def list_daily_briefing_optins(self):
        return self._optins

    async def get(self, user_id):
        return {
            "id": user_id,
            "daily_briefing_enabled": self.flags.get((user_id, "daily_briefing_enabled"), False),
        }

    async def set_flag(self, user_id, field, value):
        self.flags[(user_id, field)] = value


class FakeUoW:
    def __init__(self, advisories, reminders, user_profiles=None):
        self.advisories = advisories
        self.reminders = reminders
        self.user_profiles = user_profiles

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


def _make_service(optins=None):
    advisories = FakeAdvisoryRepo()
    reminders = FakeReminderRepo()
    profiles = FakeUserProfileRepo(optins or [])

    @asynccontextmanager
    async def uow_factory():
        yield FakeUoW(advisories, reminders, profiles)

    svc = AdvisorService(uow_factory, fi_service=None, usage_meter=None)
    return svc, advisories, reminders


# ── list_reports / get_latest_report ────────────────────────────────────────────


_BRIEFING = {"notes": [], "figures": {}, "signals": [], "assumptions": {}}


@pytest.mark.asyncio
async def test_list_reports_scoped_to_user():
    svc, advisories, _ = _make_service()
    await advisories.save("u1", {"briefing": _BRIEFING})
    await advisories.save("u2", {"briefing": _BRIEFING})

    reports = await svc.list_reports("u1")

    assert len(reports) == 1
    assert reports[0]["user_id"] == "u1"


@pytest.mark.asyncio
async def test_the_advisors_earlier_reports_are_in_the_export_only():
    """They recommended; Salli no longer shows them, and keeps them for the export."""
    svc, advisories, _ = _make_service()
    await advisories.save("u1", {"summary": "Old", "recommendations": [{"title": "Do X"}]})

    assert await svc.list_reports("u1") == []
    assert await svc.get_latest_report("u1") is None
    [kept] = await svc.export_reports("u1")
    assert kept["recommendations"] == [{"title": "Do X"}]


@pytest.mark.asyncio
async def test_get_latest_report_none_when_empty():
    svc, _, _ = _make_service()
    assert await svc.get_latest_report("u1") is None


@pytest.mark.asyncio
async def test_get_latest_report_returns_most_recent():
    svc, advisories, _ = _make_service()
    await advisories.save("u1", {"briefing": _BRIEFING, "summary": "first"})
    await advisories.save("u1", {"briefing": _BRIEFING, "summary": "second"})

    latest = await svc.get_latest_report("u1")

    assert latest["summary"] == "second"


# ── due_users ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_due_users_excludes_users_who_ran_today():
    import datetime

    today = datetime.date.today().isoformat()
    svc, advisories, _ = _make_service(
        optins=[{"user_id": "u1", "email": None}, {"user_id": "u2", "email": None}]
    )
    await advisories.save("u1", {"recommendations": [], "created_at": today})

    due = await svc.due_users()

    assert due == [{"user_id": "u2", "email": None}]


@pytest.mark.asyncio
async def test_due_users_empty_when_nobody_opted_in():
    """Free users are no longer excluded by plan — they're excluded by not having
    asked, which is the point: the run spends their own advisor allowance."""
    svc, _, _ = _make_service(optins=[])
    assert await svc.due_users() == []


@pytest.mark.asyncio
async def test_the_opt_in_toggle_round_trips_both_ways():
    """upsert skips None-ish values, so a toggle routed through it could be
    switched on but never off — hence set_flag."""
    svc, _, _ = _make_service()
    assert await svc.get_daily_briefing_enabled("u1") is False
    await svc.set_daily_briefing_enabled("u1", True)
    assert await svc.get_daily_briefing_enabled("u1") is True
    await svc.set_daily_briefing_enabled("u1", False)
    assert await svc.get_daily_briefing_enabled("u1") is False
