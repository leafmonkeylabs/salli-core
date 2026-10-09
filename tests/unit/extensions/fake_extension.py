"""Extension factories used by the loader tests, resolved through real
`importlib.metadata.EntryPoint` objects so `ep.load()` is exercised too."""

from __future__ import annotations

from typing import Any

from salli.application.ports import EntitlementPolicy, PayloadView, Surface, UsageMeter
from salli.domain.usage import AIAction, UsageLimitReached
from salli.extensions import Extension, ExtensionContext, ExtensionSpec


class RefusingMeter(UsageMeter):
    def __init__(self) -> None:
        self.calls: list[tuple[str, AIAction, str | None]] = []

    async def charge(self, user_id, action, *, model_id=None, email=None) -> None:
        self.calls.append((user_id, action, model_id))
        raise UsageLimitReached(
            action, message="nope", status_code=402, detail={"error": "limit", "action": action}
        )


class _MarkingView:
    def shape(self, surface: Surface, payload: dict[str, Any]) -> dict[str, Any]:
        return {**payload, "shaped_for": surface.value}


class MarkingPolicy(EntitlementPolicy):
    async def for_user(self, user_id: str, email: str | None = None) -> PayloadView:
        return _MarkingView()


def build(ctx: ExtensionContext) -> Extension:
    return Extension(
        name="fake",
        usage_meter=RefusingMeter(),
        entitlements=MarkingPolicy(),
        services={"fake": object()},
        user_data_purgers=[],
    )


def build_meter_only(ctx: ExtensionContext) -> Extension:
    return Extension(name="meter-only", usage_meter=RefusingMeter())


def build_broken(ctx: ExtensionContext) -> Extension:
    raise RuntimeError("boom")


def build_wrong_type(ctx: ExtensionContext) -> Any:
    return {"name": "not an extension"}


ROUTER = object()
GROUP = object()

spec = ExtensionSpec(name="fake", build=build, api_routers=(ROUTER,), cli_groups=(("fake", GROUP),))
broken_spec = ExtensionSpec(name="broken", build=build_broken)
wrong_type_spec = ExtensionSpec(name="odd", build=build_wrong_type)
not_a_spec = build
