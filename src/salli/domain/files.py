"""
File names that came from a client, made safe to put in a storage key.

A multipart upload's filename arrives exactly as the client sent it, so
"../../x" or "C:\\x" would otherwise become path segments of the key a file is
written under.
"""

from __future__ import annotations

import unicodedata

#: In UTF-8 bytes: filesystems cap a name at 255 bytes, and a name in Sinhala
#: or Tamil takes three bytes a character, so a character cap would not hold.
MAX_FILENAME_BYTES = 150

#: Bidirectional overrides and isolates: they make "fdp.exe" display as
#: "exe.pdf", and nobody's file is meant to have one.
_BIDI_CONTROLS = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")

_DROPPED_CATEGORIES = frozenset({"Cc", "Cs", "Zl", "Zp"})

#: Characters that mean something in a URL (Supabase Storage puts the key in
#: one, and would decode "%2e%2e%2f" back to "../") or that Windows refuses in a
#: name. Replaced rather than dropped, so "a?b" does not become "ab".
_REPLACED = frozenset('%?#<>:"|*')


def safe_filename(name: str | None, default: str) -> str:
    """
    The last path component of `name`, without control characters or leading
    dots, at most MAX_FILENAME_BYTES long with its extension kept; `default`
    when nothing is left.
    """
    last = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    kept = "".join("_" if ch in _REPLACED else ch for ch in last if _allowed(ch))
    # A leading dot hides the file, and ".." on its own is the parent directory.
    kept = kept.lstrip(". ").rstrip(" ")
    if not kept:
        return default
    return _truncate(kept)


def _allowed(ch: str) -> bool:
    # Control characters, surrogates and line breaks go. Other format characters
    # stay: Sinhala needs the zero-width joiner to spell some letters.
    return unicodedata.category(ch) not in _DROPPED_CATEGORIES and ch not in _BIDI_CONTROLS


def _truncate(name: str) -> str:
    if len(name.encode()) <= MAX_FILENAME_BYTES:
        return name
    stem, dot, ext = name.rpartition(".")
    # Only something that looks like an extension is kept whole.
    if not dot or not stem or len(ext.encode()) > 16:
        stem, ext = name, ""
    suffix = f".{ext}" if ext else ""
    budget = MAX_FILENAME_BYTES - len(suffix.encode())
    # Cut on bytes, dropping a character the cut splits.
    return stem.encode()[:budget].decode(errors="ignore").rstrip(" ") + suffix
