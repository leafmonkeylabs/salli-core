"""
Secret handling — a value that refuses to render itself, plus a last-resort
redactor for text that may already have a key baked into it.

Two layers on purpose, because they fail differently:

`Secret` is the primary defense. A provider key that cannot be interpolated,
logged, f-stringed, or JSON-dumped by accident removes the whole leak class at
the type level, instead of relying on someone remembering to redact at each of
N call sites. Reading the value is a deliberate, greppable `.reveal()`.

`redact()` is belt-and-braces for strings we did not construct — chiefly
exception messages from provider SDKs, which can carry the offending key. It is
a net, not a guarantee: never rely on it where a `Secret` would do.
"""

from __future__ import annotations

import re

_MASK = "**********"

# Provider key shapes, longest-prefix first so the more specific pattern wins.
#   sk-ant-...      Anthropic
#   sk-proj-.../sk- OpenAI (project-scoped and classic)
# The {16,} tail avoids eating ordinary hyphenated words that happen to follow
# "sk-", while still catching every real key (all are far longer).
_KEY_RE = re.compile(r"\b(sk-ant-|sk-proj-|sk-)[A-Za-z0-9_\-]{16,}")


class Secret:
    """A string that does not appear in its own repr, str, or format output.

    Deliberately not a str subclass: inheriting from str would make every
    existing interpolation site silently succeed, which is the bug this class
    exists to prevent.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """The real value. Call this only where the secret is actually used —
        e.g. the ChatAnthropic(api_key=...) boundary."""
        return self._value

    @property
    def last4(self) -> str:
        return self._value[-4:] if len(self._value) >= 4 else ""

    def __bool__(self) -> bool:
        return bool(self._value)

    def __len__(self) -> int:
        # The length of a key is itself a (weak) hint, so report the mask's.
        return len(_MASK)

    def __str__(self) -> str:
        return _MASK

    def __repr__(self) -> str:
        return f"Secret({_MASK})"

    def __format__(self, _spec: str) -> str:
        return _MASK

    # Equality compares secrets to secrets in constant time, so a Secret can be
    # used in tests and cache keys without ever being unwrapped.
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Secret):
            import hmac

            return hmac.compare_digest(self._value, other._value)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)


def redact(text: str) -> str:
    """Replace anything key-shaped in `text`, preserving the prefix so an
    operator can still tell *which* provider rejected the call."""
    return _KEY_RE.sub(lambda m: f"{m.group(1)}{_MASK}", text)


def error_label(exc: BaseException) -> str:
    """A safe, stable label for an exception that will be *stored*, not just shown.

    Use this instead of `str(exc)` anywhere the value lands in LangGraph state:
    those fields are written into the Postgres checkpoint permanently, and
    `delete_all` does not cover the checkpoint tables, so a provider SDK message
    carrying a rejected API key would persist indefinitely with no way to purge
    it. The class name is non-sensitive, stable enough to branch on, and the full
    traceback is still in the server log — correlatable via the X-Request-Id
    response header that RequestContextMiddleware sets on every response.
    """
    return type(exc).__name__


def redact_obj(obj: object) -> object:
    """Recursively redact strings inside dicts/lists, leaving other types alone.

    Used on SSE frames, where the payload shape varies by event type and a key
    could sit at any depth (an `error` message, a `tool_result` body).
    """
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v) for v in obj]
    return obj
