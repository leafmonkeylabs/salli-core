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
        # Keys carry client-supplied names, so the resolved destination must
        # stay inside the user's own folder: "../" in a key, or an absolute
        # one, would otherwise write anywhere this process can.
        root = self._root.resolve()
        folder = (root / user_id).resolve()
        dest = (folder / key).resolve()
        if folder == root or not folder.is_relative_to(root) or not dest.is_relative_to(folder):
            raise ValueError(f"Storage key escapes the user's folder: {key!r}")
        if dest == folder:
            raise ValueError(f"Storage key names no file: {key!r}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    async def download(self, key: str) -> bytes:
        # key is the full path returned by upload(); nothing outside the root
        # was written by upload(), so nothing outside it is read.
        path = pathlib.Path(key).resolve()
        if not path.is_relative_to(self._root.resolve()):
            raise ValueError(f"Storage key is outside the storage root: {key!r}")
        return path.read_bytes()
