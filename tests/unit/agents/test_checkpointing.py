"""Production never builds a workflow on the in-memory checkpointer."""

from types import SimpleNamespace

import pytest

import salli.config
from salli.domain.agents.briefing_workflow import build_briefing_workflow
from salli.domain.agents.checkpointing import checkpointer_or_memory
from salli.domain.agents.return_workflow import build_return_workflow
from salli.domain.agents.tax_agent import build_tax_agent


def _environment(monkeypatch, environment):
    monkeypatch.setattr(
        salli.config, "get_settings", lambda: SimpleNamespace(environment=environment)
    )


def test_an_injected_checkpointer_is_kept_in_production(monkeypatch):
    _environment(monkeypatch, "production")
    given = object()
    assert checkpointer_or_memory(given) is given


def test_development_falls_back_to_memory(monkeypatch):
    from langgraph.checkpoint.memory import MemorySaver

    _environment(monkeypatch, "development")
    assert isinstance(checkpointer_or_memory(None), MemorySaver)


@pytest.mark.parametrize(
    "build",
    [
        lambda: build_briefing_workflow(None),
        lambda: build_return_workflow(None, None),
        lambda: build_tax_agent(None, None, api_key="sk-test"),
    ],
)
def test_production_refuses_to_build_without_one(monkeypatch, build):
    _environment(monkeypatch, "production")
    with pytest.raises(RuntimeError, match="PostgreSQL checkpointer"):
        build()
