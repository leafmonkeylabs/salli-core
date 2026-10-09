"""The SSE stream stringifies provider exceptions (see _emit_events), so a
rejected-key error from Anthropic can carry the key. _sse is the single
chokepoint every frame passes through — these assert it actually redacts, at the
place the redaction has to happen rather than on the helper in isolation."""

from __future__ import annotations

from salli.interfaces.api.routers.agent import _sse

REAL = "sk-ant-api03-AbCdEf0123456789ZzYyXxWw"


def test_error_frames_do_not_carry_a_key():
    frame = _sse({"type": "error", "message": f"401 for {REAL}"})
    assert REAL not in frame
    assert "sk-ant-" in frame  # provider still identifiable


def test_nested_tool_result_frames_are_redacted_too():
    """A key could sit at any depth depending on the event type, which is why
    _sse redacts recursively rather than only touching a `message` field."""
    frame = _sse({"type": "tool_result", "name": "x", "output": {"detail": f"used {REAL}"}})
    assert REAL not in frame


def test_interrupt_frames_are_redacted():
    frame = _sse({"type": "interrupt", "data": {"message": f"bad {REAL}"}})
    assert REAL not in frame


def test_ordinary_frames_are_unchanged():
    """Redaction must not disturb the normal token path — this is the hot loop."""
    assert _sse({"type": "token", "content": "Your balance is Rs. 1,000"}) == (
        'data: {"type": "token", "content": "Your balance is Rs. 1,000"}\n\n'
    )


def test_frames_remain_valid_sse_json():
    import json

    frame = _sse({"type": "error", "message": f"bad {REAL}"})
    assert frame.startswith("data: ") and frame.endswith("\n\n")
    payload = json.loads(frame[len("data: ") :].strip())
    assert payload["type"] == "error"
