"""
Which model runs a task, from the models an account can use. Pure domain, no I/O.

Salli never fixes an OpenAI model name: what a ChatGPT plan or an API key can
use differs by account and changes over time, so each account's own catalogue
(`GET /v1/models`) is read, and a model picked from it per tier:

- "best", for the chat agent, the FIRE strategy and advice;
- "fast", for sorting statement rows, quick add and naming a conversation.

A user can name either one themselves (an override); otherwise a heuristic
picks. It is deliberately simple, and an override is always the way out:

- A ChatGPT plan's catalogue comes in the order its server ranks it ("preserves
  the server's ordering"), with `visibility: "list"` marking what is for
  display. "best" is the first listed model that is not a small, fast
  variant; "fast" is the first that is, or "best" when there is none.
- An API key's catalogue is every model the key can see, of every kind. The
  ones that cannot hold a conversation with tools (embeddings, speech, images,
  moderation, search, dated snapshots of an alias, premium "-pro" models) are
  left out, the rest ranked newest first, and picked the same way.

Anthropic is not here: its models are the catalogue's own (ai_models.py).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from salli.domain.llm import LLMNotConfigured, Tier


@dataclass(frozen=True)
class CatalogModel:
    #: What the API takes as `model`.
    id: str
    #: What a person reads.
    name: str
    #: When the provider published it (Unix seconds), when it says.
    created: int = 0


#: A small, quick variant, by name: "gpt-x-mini", "Fast", "Instant".
_FAST = re.compile(r"(?:^|[-_.\s])(mini|nano|lite|fast|flash|instant|small|spark)(?:$|[-_.\s\d])")

#: API models that are not for a conversation with tools.
_NOT_FOR_CHAT = re.compile(
    r"embedding|tts|whisper|transcribe|audio|realtime|image|dall-e|sora|moderation|search"
    r"|computer-use|codex|davinci|babbage|instruct|chat-latest|deep-research|^chatgpt-"
    r"|(?:^|-)pro(?:$|-)"
)
#: Made for one kind of work (coding, search, speech): picked only when an
#: account has nothing else.
_SPECIALISED = re.compile(r"codex|search|audio|realtime|image|transcribe|tts|embedding")
#: A dated snapshot: gpt-x-2025-08-07.
_SNAPSHOT = re.compile(r"-\d{4}-\d{2}-\d{2}$")
#: Model families the Responses API serves for chat: gpt-*, and o1, o3, o4-mini...
_CHAT_FAMILY = re.compile(r"^(gpt-|o\d)")


def is_fast(model: CatalogModel) -> bool:
    return bool(_FAST.search(model.id.lower()) or _FAST.search(model.name.lower()))


def plan_catalogue(body: Any) -> list[CatalogModel]:
    """A ChatGPT plan's `GET /v1/models` answer (`{"models": [...]}`): the
    models meant for display, in the server's order."""
    raw: Any = cast(dict[str, Any], body).get("models") if isinstance(body, dict) else body
    out: list[CatalogModel] = []
    for item in cast(list[Any], raw) if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        entry = cast(dict[str, Any], item)
        slug = entry.get("slug") or entry.get("id")
        if not isinstance(slug, str) or not slug:
            continue
        if entry.get("visibility", "list") != "list":
            continue
        out.append(CatalogModel(id=slug, name=str(entry.get("display_name") or slug)))
    return out


def api_catalogue(body: Any) -> list[CatalogModel]:
    """An API key's `GET /v1/models` answer (`{"data": [...]}`): the chat
    models, newest first, aliases over their dated snapshots."""
    raw: Any = cast(dict[str, Any], body).get("data") if isinstance(body, dict) else body
    found: list[CatalogModel] = []
    for item in cast(list[Any], raw) if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        entry = cast(dict[str, Any], item)
        model_id = entry.get("id")
        if not isinstance(model_id, str) or not model_id:
            continue
        lowered = model_id.lower()
        if not _CHAT_FAMILY.match(lowered) or _NOT_FOR_CHAT.search(lowered):
            continue
        created = entry.get("created")
        found.append(
            CatalogModel(
                id=model_id, name=model_id, created=created if isinstance(created, int) else 0
            )
        )
    aliases = {m.id for m in found}
    kept = [m for m in found if not (_SNAPSHOT.search(m.id) and _SNAPSHOT.sub("", m.id) in aliases)]
    return sorted(kept, key=lambda m: m.created, reverse=True)


def choose(
    models: list[CatalogModel], overrides: Mapping[str, str | None] | None = None
) -> dict[Tier, str]:
    """The model for each tier: the user's own choice where they made one,
    else the heuristic's. LLMNotConfigured when the account has no model."""
    chosen = {tier: model for tier, model in (overrides or {}).items() if model}
    if not models and not ("best" in chosen and "fast" in chosen):
        raise LLMNotConfigured(
            "This account has no model Salli can use for chat. Check what it can use, "
            "or choose another AI provider in Salli's settings."
        )
    general = [m for m in models if not _SPECIALISED.search(m.id.lower())] or models
    fast = [m for m in general if is_fast(m)]
    full = [m for m in general if not is_fast(m)]
    best = chosen.get("best") or (full[0].id if full else general[0].id)
    return {"best": best, "fast": chosen.get("fast") or (fast[0].id if fast else best)}
