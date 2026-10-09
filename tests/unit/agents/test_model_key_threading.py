"""Every model must be constructed with an explicit key.

The failure this guards against is silent: `ChatAnthropic` falls back to the
ANTHROPIC_API_KEY environment variable, so a construction site that forgets to
pass a key doesn't raise — it quietly bills the platform for a user who is
supposed to be paying with their own. These tests set that env var on purpose,
so they fail if the fail-loud property ever regresses.
"""

from __future__ import annotations

import inspect

import pytest

from salli.application.services.agent_service import AgentService
from salli.domain.agents.model_factory import chat_model
from salli.domain.secrets import Secret

PLATFORM = "sk-ant-PLATFORM-MUST-NOT-BE-USED"


@pytest.fixture(autouse=True)
def _env_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """The hazardous condition, made explicit."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", PLATFORM)


def _service() -> AgentService:
    return AgentService(ledger_svc=None, tax_svc=None)


# ── Fail loud, don't fall back ────────────────────────────────────────────────


@pytest.mark.parametrize("missing", [None, ""])
def test_chat_model_refuses_a_missing_key(missing):
    with pytest.raises(ValueError, match="No Anthropic API key"):
        chat_model(api_key=missing)


def test_chat_model_requires_the_key_to_be_keyword_only():
    """Keyword-only so a positional refactor can't accidentally supply the model
    name where the key belongs."""
    with pytest.raises(TypeError):
        chat_model("sk-ant-whatever")  # type: ignore[misc]


def test_building_an_agent_without_a_key_raises():
    with pytest.raises(ValueError, match="No Anthropic API key"):
        _service()._get_agent("buddy")


def test_the_builders_all_require_api_key():
    """A default would reintroduce the silent-fallback path, so assert there
    isn't one on any builder."""
    from salli.domain.agents.buddy_agent import build_buddy_agent
    from salli.domain.agents.finance_worker import build_finance_worker
    from salli.domain.agents.manager_agent import build_manager_agent
    from salli.domain.agents.tax_worker import build_tax_worker

    for fn in (build_manager_agent, build_buddy_agent, build_tax_worker, build_finance_worker):
        param = inspect.signature(fn).parameters["api_key"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY, fn.__name__
        assert param.default is inspect.Parameter.empty, f"{fn.__name__} has a default api_key"


def test_no_model_is_constructed_outside_the_factory():
    """One construction site means one place a key is unwrapped. If this fails,
    a new bare ChatAnthropic/AsyncAnthropic has appeared somewhere."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[3] / "src" / "salli"
    allowed = {"model_factory.py", "anthropic_adapter.py", "secrets.py"}
    offenders = [
        str(path.relative_to(root))
        for path in root.rglob("*.py")
        if path.name not in allowed
        and ("ChatAnthropic(" in path.read_text() or "AsyncAnthropic()" in path.read_text())
    ]
    assert not offenders, f"models built outside model_factory: {offenders}"


# ── The key actually reaches the model ────────────────────────────────────────


def test_the_supplied_key_is_used_not_the_environment():
    model = chat_model(api_key=Secret("sk-ant-USER"))
    assert model.anthropic_api_key.get_secret_value() == "sk-ant-USER"


def test_a_plain_string_key_is_accepted_too():
    """The CLI and tests hold plain strings; only the request path wraps."""
    assert chat_model(api_key="sk-ant-PLAIN").anthropic_api_key.get_secret_value() == (
        "sk-ant-PLAIN"
    )


# ── Cache keyed by credential ─────────────────────────────────────────────────


def test_the_same_key_reuses_one_compiled_graph():
    svc = _service()
    assert svc._get_agent("buddy", Secret("sk-ant-A")) is svc._get_agent(
        "buddy", Secret("sk-ant-A")
    )


def test_different_keys_get_different_graphs():
    """The key is baked in at construction — langchain binds tools eagerly, so it
    cannot be swapped per invocation. Sharing a graph across keys would mean
    running one user's conversation on another's credential."""
    svc = _service()
    assert svc._get_agent("buddy", Secret("sk-ant-A")) is not svc._get_agent(
        "buddy", Secret("sk-ant-B")
    )


def test_personas_do_not_share_a_graph_even_on_the_same_key():
    svc = _service()
    assert svc._get_agent("buddy", Secret("sk-ant-A")) is not svc._get_agent(
        "scrooge", Secret("sk-ant-A")
    )


def test_the_cache_never_contains_the_key_itself():
    svc = _service()
    svc._get_agent("buddy", Secret("sk-ant-SENSITIVE"))
    assert "SENSITIVE" not in str(list(svc._agents.keys()))


def test_the_cache_is_bounded_and_evicts_least_recently_used():
    svc = _service()
    svc._AGENT_CACHE_MAX = 3
    first = svc._get_agent("buddy", Secret("sk-ant-0"))
    for i in range(1, 5):
        svc._get_agent("buddy", Secret(f"sk-ant-{i}"))

    assert len(svc._agents) <= 3
    # The first key was evicted, so it rebuilds rather than returning the old object.
    assert svc._get_agent("buddy", Secret("sk-ant-0")) is not first


def test_tools_are_built_once_and_shared_across_graphs():
    """Rebuilding tools is the dominant cost in graph construction, and they are
    user-independent (they read the current user from a contextvar), so a
    per-key cache must not multiply that work."""
    svc = _service()
    svc._get_agent("buddy", Secret("sk-ant-A"))
    manager_first = svc._tools_cache["manager"]
    svc._get_agent("buddy", Secret("sk-ant-B"))
    assert svc._tools_cache["manager"] is manager_first


def test_the_state_reader_needs_no_credential():
    """History and pending-interrupt reads only touch checkpointed state, so a
    user whose key was revoked must still be able to read their own history."""
    svc = _service()
    assert svc._get_state_reader() is svc._get_state_reader()
