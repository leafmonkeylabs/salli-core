"""
LocalStorageAdapter — uploaded files (statements, receipts) on the server's
own disk, under one root: SALLI_STORAGE_DIR, or ~/.salli/storage.

A file's key is its path relative to the root (`<user id>/<key>`), so the
root can move — a restore onto another machine, a different volume — without
rewriting what the database holds. Back the root up with the database
(docs/self-host.md). Erasing an account deletes the user's folder.
"""

from __future__ import annotations

import pathlib
import shutil

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
        return dest.relative_to(root).as_posix()

    async def download(self, key: str) -> bytes:
        # key is what upload() returned, relative to the root; nothing outside
        # the root was written by upload(), so nothing outside it is read.
        root = self._root.resolve()
        path = (root / key).resolve()
        if path == root or not path.is_relative_to(root):
            raise ValueError(f"Storage key is outside the storage root: {key!r}")
        return path.read_bytes()

    async def delete_user(self, user_id: str) -> int:
        # Everything upload() wrote for the user is in their folder.
        root = self._root.resolve()
        folder = (root / user_id).resolve()
        if folder == root or not folder.is_relative_to(root):
            raise ValueError(f"User id names no folder of its own: {user_id!r}")
        if not folder.exists():
            return 0
        files = sum(1 for path in folder.rglob("*") if path.is_file())
        shutil.rmtree(folder)
        return files
