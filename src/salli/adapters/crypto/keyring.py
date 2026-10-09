"""
AES-GCM key ring for secrets Salli must be able to read back.

Distinct from the SHA-256 hashing used for MCP OAuth tokens: those are values
Salli issued and only ever needs to *compare*, so a one-way hash suffices. A
user's provider API key has to be replayed to Anthropic/OpenAI, so it must be
reversible — a different problem needing a different primitive.

AES-GCM rather than Fernet specifically for the associated data. Fernet has no
AAD, so nothing about a ciphertext ties it to the row it came from: a bad WHERE
clause, or a restore that mixes backups, could move user A's key onto user B's
row and B would silently make calls billed to A, with no way to detect it from
the data. Binding "{user_id}|{provider}" as AAD makes that a decryption failure
instead of a silent mischarge.
"""

from __future__ import annotations

import base64
import os

_NONCE_BYTES = 12  # AES-GCM standard; 96-bit nonces are the recommended size.


def _parse_spec(spec: str) -> dict[int, bytes]:
    """Parse "1:base64key,2:base64key" into {version: key_bytes}.

    Raises ValueError on a malformed entry rather than skipping it — a typo in
    the encryption config must not silently reduce the ring to nothing, because
    the visible symptom would be "BYOK unavailable" long after the deploy.
    """
    keys: dict[int, bytes] = {}
    for entry in (e.strip() for e in spec.split(",")):
        if not entry:
            continue
        version, _, b64 = entry.partition(":")
        if not _ or not version.strip().isdigit():
            raise ValueError("BYOK_ENCRYPTION_KEYS entries must look like '1:<base64 32-byte key>'")
        key = base64.b64decode(b64.strip(), validate=True)
        if len(key) not in (16, 24, 32):
            raise ValueError("BYOK encryption keys must decode to 16, 24, or 32 bytes")
        keys[int(version)] = key
    return keys


class KeyRing:
    """Seals with the highest configured version; opens with whichever sealed it.

    Rotation is therefore: add a higher-numbered key, keep the old one listed
    until nothing references it. Dropping a version whose rows still exist makes
    those rows permanently unreadable, which is why every row records its
    version rather than assuming "current".
    """

    def __init__(self, spec: str) -> None:
        self._keys = _parse_spec(spec or "")
        self._current: int | None = max(self._keys) if self._keys else None

    @property
    def available(self) -> bool:
        """False when no key is configured — callers must report the feature
        unavailable rather than falling back to storing plaintext."""
        return self._current is not None

    @property
    def current_version(self) -> int:
        if self._current is None:
            raise RuntimeError("No BYOK encryption key configured")
        return self._current

    def seal(self, plaintext: str, *, aad: str) -> tuple[str, int]:
        """Encrypt, returning (base64(nonce || ciphertext), key_version)."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        version = self.current_version
        nonce = os.urandom(_NONCE_BYTES)
        blob = AESGCM(self._keys[version]).encrypt(
            nonce, plaintext.encode("utf-8"), aad.encode("utf-8")
        )
        return base64.b64encode(nonce + blob).decode("ascii"), version

    def open(self, sealed: str, *, aad: str, key_version: int) -> str:
        """Decrypt. Raises if the key is missing, the AAD doesn't match (the row
        moved), or the ciphertext was tampered with — all indistinguishable by
        design, and all reasons to refuse rather than guess."""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = self._keys.get(key_version)
        if key is None:
            raise RuntimeError(
                f"BYOK encryption key version {key_version} is not configured; "
                "rows sealed with it cannot be read until it is restored"
            )
        raw = base64.b64decode(sealed, validate=True)
        nonce, blob = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
        return AESGCM(key).decrypt(nonce, blob, aad.encode("utf-8")).decode("utf-8")


def aad_for(user_id: str, provider: str) -> str:
    """The associated data bound into every sealed credential. Kept here so the
    seal and open sides cannot drift apart."""
    return f"{user_id}|{provider}"
