"""`salli ai`: signing in with ChatGPT from the terminal, end to end, with a
stand-in for OpenAI (httpx.MockTransport) and a stand-in browser that follows
the redirect to the real loopback listener."""

from __future__ import annotations

import asyncio
import json
import stat
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from click.testing import CliRunner as ClickRunner
from typer.testing import CliRunner

from salli.interfaces.cli import ai as ai_cli
from salli.interfaces.cli import main, support
from tests.unit.adapters.test_loopback import browser_get
from tests.unit.application.test_choosing_a_provider import World


@pytest.fixture
def world(monkeypatch):
    stand_in = World()
    auth, repo, settings = stand_in.auth, stand_in.connections, stand_in.instance
    chatgpt = stand_in.chatgpt
    monkeypatch.setattr(
        ai_cli,
        "services",
        lambda: SimpleNamespace(chatgpt=chatgpt, llm_credentials=stand_in.service),
    )
    monkeypatch.setattr(ai_cli, "require_user", lambda: "u1")
    # Every ChatGPTOAuth the CLI makes for itself talks to the stand-in too.
    import salli.adapters.llm.chatgpt_oauth as oauth_module

    monkeypatch.setattr(oauth_module, "default_http", auth.http)
    opened: list[str] = []

    def browser(url: str, *, answer: dict[str, str] | None = None) -> bool:
        """Follow the authorization URL as the user's browser would: OpenAI
        redirects to the loopback callback with the code."""
        opened.append(url)
        params = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        query = answer(params) if callable(answer) else auth.authorize(url)
        callback = urlsplit(params["redirect_uri"])
        asyncio.get_running_loop().create_task(
            browser_get(callback.port, f"{callback.path}?{urlencode(query)}")
        )
        return True

    monkeypatch.setattr(ai_cli, "open_browser", browser)
    return SimpleNamespace(
        auth=auth, repo=repo, chatgpt=chatgpt, opened=opened, settings=settings, stand_in=stand_in
    )


def _run(*args: str):
    return CliRunner().invoke(main.app, ["ai", *args])


def test_connect_signs_in_through_the_browser_and_keeps_it(world):
    result = _run("connect", "chatgpt", "--port", "0")

    assert result.exit_code == 0, result.output
    said = " ".join(result.output.split())  # Rich wraps long lines
    assert "Continue with ChatGPT" in said
    assert "count toward its usage limits" in said
    assert "You're using your ChatGPT plan" in said
    assert "chatgpt.com/settings/usage" in said
    (url,) = world.opened
    params = parse_qs(urlsplit(url).query)
    assert params["client_id"] == ["dynamic_agent_client"]
    assert params["ext_agent_host_id"][0].startswith("urn:uuid:")
    assert params["redirect_uri"][0].startswith("http://127.0.0.1:")
    assert world.repo.rows[("u1", "chatgpt")]["status"] == "active"
    for secret in ("access-1", "refresh-1"):
        assert secret not in result.output


def test_connecting_again_signs_the_same_account_in_with_its_client_id(world):
    assert _run("connect", "chatgpt", "--port", "0").exit_code == 0
    world.auth.valid_refresh = "refresh-2"

    result = _run("connect", "chatgpt", "--port", "0")

    assert result.exit_code == 0, result.output
    assert "Connected to ChatGPT as me@example.com" in " ".join(result.output.split())
    params = parse_qs(urlsplit(world.opened[1]).query)
    assert params["client_id"] == ["oaiapp_test"]
    assert "agent_name_hint" not in params
    assert params["login_hint"] == ["me@example.com"]
    # Same host id both times.
    assert (
        params["ext_agent_host_id"]
        == parse_qs(urlsplit(world.opened[0]).query)["ext_agent_host_id"]
    )


def test_declining_in_the_browser_connects_nothing(world, monkeypatch):
    original = ai_cli.open_browser

    def decline(url: str) -> bool:
        return original(url, answer=lambda p: {"error": "access_denied", "state": p["state"]})

    monkeypatch.setattr(ai_cli, "open_browser", decline)
    result = _run("connect", "chatgpt", "--port", "0")

    assert result.exit_code == 1
    assert "nothing was connected" in " ".join(result.output.split())
    assert world.repo.rows == {}


def test_a_forged_callback_is_refused(world, monkeypatch):
    original = ai_cli.open_browser

    def forge(url: str) -> bool:
        return original(url, answer=lambda p: {"code": "x", "state": "forged"})

    monkeypatch.setattr(ai_cli, "open_browser", forge)
    result = _run("connect", "chatgpt", "--port", "0")

    assert result.exit_code == 1
    assert world.repo.rows == {}


def test_signing_in_for_a_server_elsewhere_writes_a_private_file(world, tmp_path):
    target = tmp_path / "salli-chatgpt.json"
    server_host = "urn:uuid:11111111-2222-4333-8444-555555555555"

    result = _run(
        "connect", "chatgpt", "--port", "0", "--save-to", str(target), "--host-id", server_host
    )

    assert result.exit_code == 0, result.output
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    record = json.loads(target.read_text())
    assert record["ext_agent_host_id"] == server_host
    assert record["client_id"] == "oaiapp_test"
    assert record["subject"] == "user-sub-1"
    assert "chatgpt.tokens.use.direct" in record["scopes"]
    assert world.repo.rows == {}  # written, not kept here
    params = parse_qs(urlsplit(world.opened[0]).query)
    assert params["ext_agent_host_id"] == [server_host]
    assert "access-1" not in result.output

    # ...and the server keeps it, under its own host id.
    kept = _run("connect", "chatgpt", "--from-file", str(target))
    assert kept.exit_code == 0, kept.output
    assert world.repo.rows[("u1", "chatgpt")]["status"] == "active"
    assert asyncio.run(world.chatgpt.host_id()) != server_host


def test_save_to_needs_the_servers_host_id(world, tmp_path):
    result = _run("connect", "chatgpt", "--save-to", str(tmp_path / "x.json"))
    assert result.exit_code == 1
    assert "--host-id" in result.output


def test_only_chatgpt_is_signed_in_to(world):
    result = _run("connect", "openai")
    assert result.exit_code == 2
    assert "salli llm-keys set openai" in " ".join(result.output.split())


def test_host_prints_the_instances_host_id(world):
    result = _run("host")
    assert result.exit_code == 0
    assert result.output.strip().startswith("urn:uuid:")


def test_disconnect_ends_the_session(world):
    _run("connect", "chatgpt", "--port", "0")

    result = _run("disconnect", "chatgpt")

    assert result.exit_code == 0, result.output
    assert "Disconnected from ChatGPT" in " ".join(result.output.split())
    assert [r["token"] for r in world.auth.revoked] == ["refresh-1"]
    assert _run("disconnect", "chatgpt").exit_code == 1


def test_status_in_json_never_carries_a_token(world, monkeypatch):
    # --json switches the process into JSON mode and points the console at
    # stderr; both are put back afterwards, so later tests see plain output.
    monkeypatch.setattr(support, "_json_mode", False)
    monkeypatch.setattr(support.console, "_file", support.console._file)
    _run("connect", "chatgpt", "--port", "0")

    result = ClickRunner().invoke(main.cli(), ["ai", "status", "--json"])

    assert result.exit_code == 0, result.output
    shown = json.loads(result.stdout)
    status = shown["chatgpt"]
    assert status["status"] == "active"
    assert shown["settings"]["active"] == {"provider": "chatgpt", "source": "user"}
    assert status["email"] == "me@example.com"
    for secret in ("access-1", "refresh-1"):
        assert secret not in result.output


def test_use_chooses_the_provider(world):
    result = _run("use", "anthropic")
    assert result.exit_code == 0, result.output
    assert "runs on anthropic" in " ".join(result.output.split())
    assert _run("use", "gemini").exit_code == 1


def test_models_lists_the_accounts_own_and_set_models_names_one(world):
    _run("connect", "chatgpt", "--port", "0")

    listed = _run("models", "chatgpt")
    assert listed.exit_code == 0, listed.output
    assert "best = gpt-test-best" in listed.output and "gpt-test-mini" in listed.output

    chosen = _run("set-models", "chatgpt", "--fast", "gpt-test-best")
    assert chosen.exit_code == 0, chosen.output
    assert "chosen by you: fast = gpt-test-best" in chosen.output
    assert _run("set-models", "chatgpt", "--best", "gpt-nope").exit_code == 1
