"""
LocalStorageAdapter — dev/test fallback that writes to ~/.salli/storage/.

Not suitable for production (no auth, no CDN, no multi-instance). Wire the
SupabaseStorageAdapter in production by setting SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY.
"""

from __future__ import annotations

import pathlib

from salli.application.ports import StoragePort

_DEFAULT_ROOT = pathlib.Path.home() / ".salli" / "storage"


class LocalStorageAdapter(StoragePort):
    def __init__(self, root: pathlib.Path | None = None) -> None:
        self._root = root or _DEFAULT_ROOT

    async def upload(self, user_id: str, key: str, data: bytes) -> str:
        dest = self._root / user_id / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    async def download(self, key: str) -> bytes:
        # key is the full path returned by upload()
        return pathlib.Path(key).read_bytes()
