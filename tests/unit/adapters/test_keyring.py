"""The AAD binding and the version handling are the two things that would fail
silently if wrong, so both are tested directly."""

from __future__ import annotations

import base64
import os

import pytest

from salli.adapters.crypto.keyring import KeyRing, aad_for

K1 = base64.b64encode(os.urandom(32)).decode()
K2 = base64.b64encode(os.urandom(32)).decode()
KEY = "sk-ant-api03-AbCdEf0123456789"


def _ring(spec: str = f"1:{K1}") -> KeyRing:
    return KeyRing(spec)


# ── Round trip ────────────────────────────────────────────────────────────────


def test_round_trip():
    ring = _ring()
    sealed, version = ring.seal(KEY, aad=aad_for("u1", "anthropic"))
    assert ring.open(sealed, aad=aad_for("u1", "anthropic"), key_version=version) == KEY


def test_ciphertext_does_not_contain_the_plaintext():
    ring = _ring()
    sealed, _ = ring.seal(KEY, aad=aad_for("u1", "anthropic"))
    assert KEY not in sealed
    assert KEY.encode() not in base64.b64decode(sealed)


def test_sealing_twice_gives_different_ciphertext():
    """A fresh nonce per seal — otherwise identical keys would be linkable
    across users just by comparing rows."""
    ring = _ring()
    a, _ = ring.seal(KEY, aad=aad_for("u1", "anthropic"))
    b, _ = ring.seal(KEY, aad=aad_for("u1", "anthropic"))
    assert a != b


# ── AAD binding: the reason for AES-GCM over Fernet ───────────────────────────


def test_a_row_moved_to_another_user_will_not_open():
    """The whole point of the AAD. If this ever passes, a misdirected row would
    let one user's key be used — and billed — under another's account."""
    ring = _ring()
    sealed, version = ring.seal(KEY, aad=aad_for("victim", "anthropic"))
    with pytest.raises(Exception):
        ring.open(sealed, aad=aad_for("attacker", "anthropic"), key_version=version)


def test_a_row_moved_to_another_provider_will_not_open():
    ring = _ring()
    sealed, version = ring.seal(KEY, aad=aad_for("u1", "anthropic"))
    with pytest.raises(Exception):
        ring.open(sealed, aad=aad_for("u1", "openai"), key_version=version)


def test_tampered_ciphertext_will_not_open():
    ring = _ring()
    sealed, version = ring.seal(KEY, aad=aad_for("u1", "anthropic"))
    raw = bytearray(base64.b64decode(sealed))
    raw[-1] ^= 0xFF
    with pytest.raises(Exception):
        ring.open(
            base64.b64encode(bytes(raw)).decode(),
            aad=aad_for("u1", "anthropic"),
            key_version=version,
        )


# ── Versions / rotation ───────────────────────────────────────────────────────


def test_seals_with_the_highest_version():
    ring = _ring(f"1:{K1},2:{K2}")
    _, version = ring.seal(KEY, aad=aad_for("u1", "anthropic"))
    assert version == 2


def test_opens_a_row_sealed_by_an_older_key():
    """Rotation depends on this: the old key stays listed so existing rows keep
    working while new writes use the new one."""
    old = _ring(f"1:{K1}")
    sealed, version = old.seal(KEY, aad=aad_for("u1", "anthropic"))
    rotated = _ring(f"1:{K1},2:{K2}")
    assert rotated.open(sealed, aad=aad_for("u1", "anthropic"), key_version=version) == KEY


def test_dropping_a_still_referenced_version_fails_loudly():
    old = _ring(f"1:{K1}")
    sealed, version = old.seal(KEY, aad=aad_for("u1", "anthropic"))
    with pytest.raises(RuntimeError, match="not configured"):
        _ring(f"2:{K2}").open(sealed, aad=aad_for("u1", "anthropic"), key_version=version)


# ── Availability / config errors ──────────────────────────────────────────────


def test_unconfigured_ring_is_unavailable_and_refuses_to_seal():
    ring = _ring("")
    assert ring.available is False
    with pytest.raises(RuntimeError):
        ring.seal(KEY, aad=aad_for("u1", "anthropic"))


def test_configured_ring_is_available():
    assert _ring().available is True


@pytest.mark.parametrize(
    "spec",
    [
        "nokey",  # no version prefix
        "x:" + K1,  # non-numeric version
        "1:not-base64!!",  # undecodable
        "1:" + base64.b64encode(os.urandom(8)).decode(),  # wrong key length
    ],
)
def test_malformed_config_raises_rather_than_silently_emptying_the_ring(spec: str):
    """A typo must not degrade to 'BYOK unavailable' — that symptom would surface
    long after the deploy, with no obvious cause."""
    with pytest.raises(ValueError):
        KeyRing(spec)


def test_blank_and_whitespace_entries_are_ignored():
    assert KeyRing(f" 1:{K1} , ").available is True
