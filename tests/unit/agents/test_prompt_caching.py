"""
Prompt caching is a cost lever, so it is pinned like one.

The conversational agents resend a system-plus-tools prefix of roughly 3,600
tokens on every round trip, and a single turn is several round trips. Caching
that prefix is the largest saving available to the app (see UNIT_ECONOMICS.md).
Nothing about it is visible at runtime without reading `usage`, so a regression
here would be silent and would only show up on the bill.
"""

from __future__ import annotations

import warnings

import pytest

from salli.domain.agents.model_factory import chat_model

KEY = "sk-ant-dummy"
EPHEMERAL = {"type": "ephemeral"}


def test_caching_is_off_unless_asked_for():
    """A cache write costs 1.25x, so a one-shot call must not pay it by default."""
    assert chat_model(api_key=KEY).model_kwargs.get("cache_control") is None


def test_cache_flag_sets_top_level_cache_control():
    model = chat_model(api_key=KEY, cache=True)
    assert model.model_kwargs["cache_control"] == EPHEMERAL


def test_cache_control_reaches_the_request_payload():
    """The flag is worthless if langchain drops it before the wire.

    `model_kwargs` is spread into the payload rather than validated against a
    schema, so this asserts the actual outgoing request rather than trusting
    that the constructor stored it.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    model = chat_model(api_key=KEY, cache=True)
    payload = model._get_request_payload([SystemMessage("stable prefix"), HumanMessage("hi")])
    assert payload["cache_control"] == EPHEMERAL


def test_cache_does_not_clobber_caller_supplied_model_kwargs():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = chat_model(api_key=KEY, cache=True, model_kwargs={"betas": ["x"]})
    # langchain hoists recognised keys out of model_kwargs into their own
    # field, so `betas` is asserted where it ends up rather than where it went in.
    assert model.betas == ["x"]
    assert model.model_kwargs["cache_control"] == EPHEMERAL


class _Stop(Exception):
    """Raised in place of building a real model, to end the call early."""


@pytest.mark.parametrize(
    ("module_name", "builder_name"),
    [
        ("salli.domain.agents.manager_agent", "build_manager_agent"),
        ("salli.domain.agents.buddy_agent", "build_buddy_agent"),
        ("salli.domain.agents.finance_worker", "build_finance_worker"),
        ("salli.domain.agents.tax_worker", "build_tax_worker"),
        ("salli.domain.agents.tax_agent", "build_tax_agent"),
    ],
)
def test_every_conversational_agent_asks_for_caching(module_name, builder_name, monkeypatch):
    """The five agents that carry the big prefix must all opt in.

    Driven through each real builder rather than by reading the source, so an
    agent that stops passing the flag fails here even if the call still looks
    right. Each module imports `chat_model` inside the function body, so the
    patch goes on the factory module they import *from*.
    """
    import importlib
    import inspect
    from unittest.mock import MagicMock

    module = importlib.import_module(module_name)
    builder = getattr(module, builder_name)
    seen: list[bool] = []

    def fake_chat_model(*, api_key, model=None, cache=False, **kwargs):
        seen.append(cache)
        raise _Stop

    monkeypatch.setattr("salli.domain.agents.model_factory.chat_model", fake_chat_model)

    # Every service argument is a stand-in; the builder never gets far enough
    # to call one, because the patched model factory stops it first.
    sig = inspect.signature(builder)
    args = [
        MagicMock()
        for p in sig.parameters.values()
        if p.default is inspect.Parameter.empty and p.kind is p.POSITIONAL_OR_KEYWORD
    ]
    kwargs: dict = {"api_key": KEY}
    if "tools" in sig.parameters:
        kwargs["tools"] = []

    with pytest.raises(_Stop):
        builder(*args, **kwargs)

    assert seen == [True], f"{builder_name} builds its model without cache=True"
