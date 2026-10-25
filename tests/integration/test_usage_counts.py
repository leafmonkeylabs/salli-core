"""`salli-server stats`'s counts against a real Postgres: counts only, over
the last week, and off unless the owner turns them on."""

from __future__ import annotations

import asyncio
import datetime

from typer.testing import CliRunner

from salli import config
from salli.adapters.db.models import PersonalAccessTokenORM
from salli.adapters.db.session import make_session_factory
from salli.adapters.db.usage_counts import usage_counts
from salli.config import Settings
from salli.interfaces.cli.main import app
from tests.integration.pg import requires_postgres

pytestmark = requires_postgres

NOW = datetime.datetime(2026, 3, 9, 12, tzinfo=datetime.UTC)


def test_the_counts_cover_the_last_week_only(db):
    sessions = make_session_factory(Settings(_env_file=None, database_url=db), pooled=False)

    async def run():
        async with sessions() as session:
            for n, used in enumerate(
                (NOW - datetime.timedelta(days=1), NOW - datetime.timedelta(days=9))
            ):
                session.add(
                    PersonalAccessTokenORM(
                        user_id=f"user-{n}", name="ci", token_hash=f"{n:064d}", prefix="p",
                        last_used_at=used,
                    )
                )  # fmt: skip
            await session.commit()
        return await usage_counts(sessions, NOW)

    assert asyncio.run(run()) == {
        "active_members": 1,
        "entries_imported": 0,
        "reconciliations_completed": 0,
    }


def test_stats_is_off_by_default(db, monkeypatch):
    def settings(**on):
        monkeypatch.setattr(config, "_settings", Settings(_env_file=None, database_url=db, **on))

    settings()
    result = CliRunner().invoke(app, ["stats"])
    assert result.exit_code == 1 and "off" in result.output
    settings(salli_usage_counters=True)
    result = CliRunner().invoke(app, ["stats"])
    assert result.exit_code == 0, result.output
    assert "Members active" in result.output


def test_a_report_sends_the_week_s_totals_only_when_set_up(db, monkeypatch):
    import httpx

    sent: list[tuple[str, dict]] = []

    def post(url, json, timeout):
        sent.append((url, json))
        return httpx.Response(204, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    on = {"database_url": db, "salli_usage_counters": True}
    monkeypatch.setattr(config, "_settings", Settings(_env_file=None, **on))
    result = CliRunner().invoke(app, ["stats", "--send"])
    assert result.exit_code == 1 and "SALLI_USAGE_REPORT_URL" in result.output
    result = CliRunner().invoke(app, ["stats", "--send", "--dry-run"])
    assert result.exit_code == 0 and sent == []

    url = "https://counts.example.org/v1/usage"
    monkeypatch.setattr(
        config,
        "_settings",
        Settings(
            _env_file=None, salli_usage_report_url=url, salli_usage_install_id="pilot-7", **on
        ),
    )
    result = CliRunner().invoke(app, ["jobs", "send-usage"])
    assert result.exit_code == 0, result.output
    [(to, body)] = sent
    assert to == url
    assert set(body) == {
        "schema",
        "install_id",
        "salli_version",
        "week_ending",
        "active_members",
        "entries_imported",
        "reconciliations_completed",
    }
    assert body["install_id"] == "pilot-7" and body["schema"] == "salli.usage/1"
