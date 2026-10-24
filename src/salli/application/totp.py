"""
Codes from an authenticator app: time-based one-time passwords (RFC 6238,
over RFC 4226's HOTP), as every authenticator app makes them: SHA-1, six
digits, a new one every 30 seconds. And the recovery codes that stand in for
the app when it is lost, each good once.

Pure functions: the login service keeps the secret (sealed) and the step a
code was last used at, so a code can't be used twice.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote, urlencode

STEP_SECONDS = 30
DIGITS = 6
#: A code from the step before or after now still counts, for a clock that
#: is a little out or a code typed as it changed.
DRIFT_STEPS = 1
RECOVERY_CODES = 10
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o, 1/l/i


def new_secret() -> str:
    """A new secret: 160 random bits (RFC 4226's recommended length), base32."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _key(secret: str) -> bytes:
    text = secret.replace(" ", "").upper()
    return base64.b32decode(text + "=" * (-len(text) % 8))


def code_at(secret: str, step: int, *, digits: int = DIGITS) -> str:
    """The code for time step `step` (seconds since the epoch // 30)."""
    mac = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    number = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**digits).zfill(digits)


def step_of(unix_seconds: float) -> int:
    return int(unix_seconds // STEP_SECONDS)


def matching_step(secret: str, code: str, unix_seconds: float) -> int | None:
    """The time step `code` is the code for, within the drift allowed of
    now, or None if it is none of them."""
    typed = code.replace(" ", "")
    if len(typed) != DIGITS or not typed.isdigit():
        return None
    now = step_of(unix_seconds)
    found = None
    for step in range(now - DRIFT_STEPS, now + DRIFT_STEPS + 1):
        # Every step compared, in constant time, whichever matches.
        if hmac.compare_digest(code_at(secret, step), typed):
            found = step
    return found


def looks_like_totp(code: str) -> bool:
    typed = code.replace(" ", "")
    return len(typed) == DIGITS and typed.isdigit()


def provisioning_uri(secret: str, account: str, issuer: str = "Salli") -> str:
    """The `otpauth://` URI an authenticator app reads (as a QR code, or
    pasted)."""
    label = quote(f"{issuer}:{account}")
    query = urlencode(
        {
            "secret": secret,
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": DIGITS,
            "period": STEP_SECONDS,
        }
    )
    return f"otpauth://totp/{label}?{query}"


def new_recovery_codes(count: int = RECOVERY_CODES) -> list[str]:
    """`count` recovery codes like `k7m2p-x9qrt`: 50 random bits each."""

    def one() -> str:
        chars = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        return f"{chars[:5]}-{chars[5:]}"

    return [one() for _ in range(count)]


def recovery_hash(code: str) -> str:
    """How a recovery code is kept: a SHA-256 of it, as typed in any case,
    with or without its hyphen and spaces."""
    typed = "".join(ch for ch in code.lower() if ch.isalnum())
    return hashlib.sha256(f"recovery:{typed}".encode()).hexdigest()
