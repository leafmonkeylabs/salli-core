"""A test extension that uses every generic seam: capabilities with an offer,
a usage refusal with its own problem type, panels (good, invalid, failing), a
router at the root, and a system path of its own."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from salli.application import acting
from salli.application.ports import Capability, EntitlementPolicy, PayloadView, Surface, UsageMeter
from salli.domain.usage import AIAction, Offer, UsageLimitReached
from salli.extensions import Extension, ExtensionContext, ExtensionSpec, PanelSpec
from salli.interfaces.api.deps import AppServices

OFFER = Offer(title="More room", detail="Ask for more.", label="See options", panel="options")
REFUSED = frozenset({Capability.MEMBER_SHARING, Capability.BANK_FORMATS, "x-custom"})


class _View:
    def shape(self, surface: Surface, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def allows(self, capability: str) -> bool:
        return capability not in REFUSED

    def offer(self, capability: str) -> Offer | None:
        return OFFER


class Policy(EntitlementPolicy):
    async def for_user(self, user_id: str, email: str | None = None) -> PayloadView:
        return _View()


class Meter(UsageMeter):
    def __init__(self) -> None:
        self.own_key: list[bool] = []

    async def charge(self, user_id, action, *, model_id=None, email=None, own_key=False) -> None:
        self.own_key.append(own_key)
        raise UsageLimitReached(
            action,
            message="over",
            status_code=402,
            detail={"error": "over"},
            offer=OFFER,
            problem_type="over-the-line",
        )


api = APIRouter(prefix="/seams", tags=["seams"])
root = APIRouter()


@api.get("/charge")
async def charge(svc: AppServices) -> dict[str, str]:
    await svc.usage.charge("someone", AIAction.ENTRY_PARSE)
    return {}


@api.get("/capability")
async def capability(svc: AppServices) -> dict[str, str]:
    from salli.application.ports import require_capability

    await require_capability(svc.entitlements, "someone", None, "x-custom")
    return {}


@root.get("/hello")
async def hello() -> dict[str, str]:
    return {"hello": "root"}


async def _options(user_id: str) -> dict[str, Any]:
    return {
        "schema": "salli.panel/1",
        "id": "options",
        "title": "Options",
        "sections": [
            {
                "heading": "Now",
                "rows": [
                    {"kind": "text", "label": "Room", "value": "3.50"},
                    {"kind": "link", "label": "Terms", "detail": None, "url": "https://x.test/t"},
                    {
                        "kind": "action",
                        "label": "Ask",
                        "confirm": "Sure?",
                        "action": {"method": "POST", "path": "/v1/seams/ask", "then": "close"},
                    },
                ],
                "footnote": None,
            }
        ],
        "note": None,
    }


async def _leaky(user_id: str) -> dict[str, Any]:
    panel = await _options(user_id)
    panel["id"] = "leaky"
    panel["sections"][0]["rows"][1]["url"] = "http://elsewhere.test/"
    return panel


async def _broken(user_id: str) -> dict[str, Any]:
    raise RuntimeError("secret detail")


def build(ctx: ExtensionContext) -> Extension:
    return Extension(
        name="seams",
        usage_meter=Meter(),
        entitlements=Policy(),
        panels=[
            PanelSpec("options", "Options", _options, entry="more"),
            PanelSpec("leaky", "Leaky", _leaky),
            PanelSpec("broken", "Broken", _broken, entry="settings"),
        ],
    )


spec = ExtensionSpec(
    name="seams",
    build=build,
    api_routers=(api,),
    root_routers=(root,),
    system_paths={"seams-sweep": "the extension's sweep looks at every person"},
)


def own_system_path() -> None:
    with acting.as_system("seams-sweep"):
        pass
