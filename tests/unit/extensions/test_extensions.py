"""
The extension seam: Salli's permissive defaults, and the loader that lets a
deployment replace them.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint

import pytest

from salli.application.defaults import FullAccess, UnmeteredUsage
from salli.application.ports import Surface
from salli.domain.usage import AIAction, UsageLimitReached
from salli.extensions import (
    ENTRY_POINT_GROUP,
    Extension,
    ExtensionContext,
    ExtensionError,
    build_extensions,
    combine,
    load_specs,
    parse_enabled,
)
from tests.unit.extensions.fake_extension import GROUP, ROUTER, MarkingPolicy, RefusingMeter

CTX = ExtensionContext(
    settings=None, session_factory=None, uow_factory=lambda: None, llm_credentials=None
)


def _ep(name: str, target: str) -> EntryPoint:
    return EntryPoint(
        name=name,
        value=f"tests.unit.extensions.fake_extension:{target}",
        group=ENTRY_POINT_GROUP,
    )


def _discover(*eps: EntryPoint):
    return lambda: list(eps)


# ── Defaults ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("action", list(AIAction))
async def test_the_default_meter_allows_every_action(action):
    assert await UnmeteredUsage().charge("u1", action, model_id="any") is None


@pytest.mark.parametrize("surface", list(Surface))
async def test_the_default_policy_returns_every_surface_untouched(surface):
    payload = {"points": [{"conservative": "1", "growth": "3"}], "ai_rationale": "Because."}
    view = await FullAccess().for_user("u1")
    shaped = view.shape(surface, payload)
    assert shaped == {"points": [{"conservative": "1", "growth": "3"}], "ai_rationale": "Because."}
    # No lock markers leak into a self-hosted response.
    assert not any("lock" in key for key in shaped)


def test_no_extensions_means_the_defaults():
    merged = combine([])
    assert isinstance(merged.usage_meter, UnmeteredUsage)
    assert isinstance(merged.entitlements, FullAccess)
    assert merged.services == {}
    assert merged.user_data_purgers == []


# ── Enabling ────────────────────────────────────────────────────────────────


def test_parse_enabled_trims_and_drops_repeats():
    assert parse_enabled(" cloud, ,extra,cloud ") == ["cloud", "extra"]
    assert parse_enabled("") == []
    assert parse_enabled(None) == []


def test_nothing_enabled_loads_nothing_even_when_installed():
    """Installing a package must not change behaviour on its own."""
    assert load_specs([], discover=_discover(_ep("fake", "spec"))) == []


def test_an_enabled_extension_loads_its_static_parts_and_builds_its_runtime():
    [spec] = load_specs(["fake"], discover=_discover(_ep("fake", "spec")))
    assert spec.api_routers == (ROUTER,)
    assert spec.cli_groups == (("fake", GROUP),)

    merged = combine(build_extensions([spec], CTX))
    assert isinstance(merged.usage_meter, RefusingMeter)
    assert isinstance(merged.entitlements, MarkingPolicy)
    assert set(merged.services) == {"fake"}
    assert merged.names == ("fake",)


# ── Failing closed ──────────────────────────────────────────────────────────


def test_an_enabled_but_missing_extension_stops_startup():
    with pytest.raises(ExtensionError, match="not installed"):
        load_specs(["cloud"], discover=_discover(_ep("fake", "spec")))


def test_an_entry_point_that_fails_to_import_stops_startup():
    bad = EntryPoint(name="gone", value="tests.no_such_module:spec", group=ENTRY_POINT_GROUP)
    with pytest.raises(ExtensionError, match="failed to import"):
        load_specs(["gone"], discover=_discover(bad))


def test_an_entry_point_that_is_not_a_spec_stops_startup():
    with pytest.raises(ExtensionError, match="not an ExtensionSpec"):
        load_specs(["odd"], discover=_discover(_ep("odd", "not_a_spec")))


def test_an_extension_that_fails_to_build_stops_startup():
    [spec] = load_specs(["broken"], discover=_discover(_ep("broken", "broken_spec")))
    with pytest.raises(ExtensionError, match="failed to build: boom"):
        build_extensions([spec], CTX)


def test_an_extension_that_does_not_build_an_extension_stops_startup():
    [spec] = load_specs(["odd"], discover=_discover(_ep("odd", "wrong_type_spec")))
    with pytest.raises(ExtensionError, match="not an Extension"):
        build_extensions([spec], CTX)


def test_two_meters_are_refused():
    with pytest.raises(ExtensionError, match="usage meter"):
        combine(
            [
                Extension(name="a", usage_meter=RefusingMeter()),
                Extension(name="b", usage_meter=RefusingMeter()),
            ]
        )


def test_two_policies_are_refused():
    with pytest.raises(ExtensionError, match="entitlement policy"):
        combine(
            [
                Extension(name="a", entitlements=MarkingPolicy()),
                Extension(name="b", entitlements=MarkingPolicy()),
            ]
        )


def test_a_service_key_claimed_twice_is_refused():
    with pytest.raises(ExtensionError, match="'x'"):
        combine([Extension(name="a", services={"x": 1}), Extension(name="b", services={"x": 2})])


def test_contributions_from_several_extensions_are_merged():
    async def purge_a(session, user_id):
        return {}

    async def purge_b(session, user_id):
        return {}

    merged = combine(
        [
            Extension(name="a", usage_meter=RefusingMeter(), user_data_purgers=[purge_a]),
            Extension(name="b", entitlements=MarkingPolicy(), user_data_purgers=[purge_b]),
        ]
    )
    assert isinstance(merged.usage_meter, RefusingMeter)
    assert isinstance(merged.entitlements, MarkingPolicy)
    assert merged.user_data_purgers == [purge_a, purge_b]


# ── The refusal itself ──────────────────────────────────────────────────────


async def test_a_refusal_carries_what_each_surface_needs():
    meter = RefusingMeter()
    with pytest.raises(UsageLimitReached) as caught:
        await meter.charge("u1", AIAction.CHAT_MESSAGE, model_id="m")
    exc = caught.value
    assert exc.message == "nope"
    assert exc.status_code == 402
    assert exc.detail == {"error": "limit", "action": AIAction.CHAT_MESSAGE}
    assert meter.calls == [("u1", AIAction.CHAT_MESSAGE, "m")]


def test_a_refusal_without_detail_still_has_a_body():
    exc = UsageLimitReached(AIAction.ADVISOR_RUN, message="Slow down.")
    assert exc.status_code == 429
    assert exc.detail == {"error": "Slow down."}


def test_action_values_are_stable():
    """Persisted by meters; renaming a value would orphan their records."""
    assert {a.value for a in AIAction} == {
        "agent_message",
        "entry_parse",
        "advisor_run",
        "statement_upload",
        "fire_strategy",
    }
