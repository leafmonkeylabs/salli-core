"""A leaked provider key is the worst outcome of BYOK, so these test the
mechanism itself rather than any caller."""

from __future__ import annotations

import json
import logging

from salli.domain.secrets import Secret, redact, redact_obj

REAL = "sk-ant-api03-AbCdEf0123456789ZzYyXxWw"


# ── Secret ────────────────────────────────────────────────────────────────────


def test_the_value_never_appears_through_any_rendering_path():
    s = Secret(REAL)
    assert REAL not in str(s)
    assert REAL not in repr(s)
    assert REAL not in f"{s}"
    assert REAL not in "{}".format(s)  # noqa: UP032 - exercising .format explicitly
    assert REAL not in f"{s!r}"
    assert REAL not in f"{s!s}"
    # noqa: percent-format is one of the paths a key could leak through, so it's
    # exercised deliberately rather than modernised away.
    assert REAL not in "%s" % (s,)  # noqa: UP031


def test_it_is_not_a_str_subclass():
    """Inheriting from str would make every existing interpolation site silently
    succeed — exactly the bug Secret exists to prevent."""
    assert not isinstance(Secret(REAL), str)


def test_it_does_not_leak_through_logging():
    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record.getMessage())

    log = logging.getLogger("test.secrets")
    log.addHandler(_Capture())
    log.error("key=%s", Secret(REAL))
    log.addHandler(logging.NullHandler())

    assert records and REAL not in records[0]


def test_json_dumps_refuses_rather_than_leaking():
    """json.dumps(default=str) is how SSE frames are serialised, so a Secret must
    not quietly render there either."""
    assert REAL not in json.dumps({"k": Secret(REAL)}, default=str)


def test_reveal_returns_the_real_value():
    assert Secret(REAL).reveal() == REAL


def test_last4_and_truthiness():
    assert Secret(REAL).last4 == REAL[-4:]
    assert bool(Secret(REAL)) is True
    # Falsy when empty, so "has the user configured a key?" reads naturally.
    assert bool(Secret("")) is False
    assert Secret("").last4 == ""


def test_equality_compares_without_unwrapping():
    assert Secret(REAL) == Secret(REAL)
    assert Secret(REAL) != Secret("sk-ant-other")
    assert (Secret(REAL) == REAL) is False  # NotImplemented -> False, never a match


# ── redact ────────────────────────────────────────────────────────────────────


def test_redacts_an_anthropic_key_but_keeps_the_prefix():
    out = redact(f"401 unauthorized for {REAL}")
    assert REAL not in out
    assert "sk-ant-" in out  # operator can still tell which provider


def test_redacts_openai_shapes():
    for key in (
        "sk-proj-AbCdEf0123456789ZzYyXxWw",
        "sk-AbCdEf0123456789ZzYyXxWwVv",
    ):
        assert key not in redact(f"error: {key}")


def test_redacts_a_key_embedded_mid_sentence_and_repeated():
    text = f"first {REAL} then {REAL} again"
    out = redact(text)
    assert REAL not in out
    assert out.count("**********") == 2


def test_leaves_ordinary_text_alone():
    for benign in (
        "sk-short",  # too short to be a key
        "the risk-adjusted return",
        "no secrets here",
    ):
        assert redact(benign) == benign


def test_redact_obj_walks_nested_payloads():
    frame = {
        "type": "error",
        "message": f"bad key {REAL}",
        "parts": [{"tool_result": {"body": f"used {REAL}"}}],
    }
    out = json.dumps(redact_obj(frame))
    assert REAL not in out
    assert "sk-ant-" in out


def test_redact_obj_preserves_non_string_types():
    assert redact_obj({"n": 1, "b": True, "z": None}) == {"n": 1, "b": True, "z": None}
