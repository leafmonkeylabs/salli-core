"""FI pack registry — the canonical FiPack used for scoring."""

from __future__ import annotations

from salli.domain.fi.models import FiPack
from salli.domain.fi.packs.default_v1 import DEFAULT_V1

_REGISTRY: dict[str, FiPack] = {
    DEFAULT_V1.version: DEFAULT_V1,
}

CURRENT_VERSION = DEFAULT_V1.version


def get_pack(version: str | None = None) -> FiPack:
    if version is None:
        version = CURRENT_VERSION
    pack = _REGISTRY.get(version)
    if pack is None:
        raise KeyError(f"No FI pack version {version!r}. Available: {', '.join(_REGISTRY)}")
    return pack
