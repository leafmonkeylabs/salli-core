"""An uploaded file is stored under a key built from its safe name, never the
path a client put in its filename."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import pytest

from salli.adapters.storage.local import LocalStorageAdapter
from salli.application.services.document_service import DocumentService

pytestmark = pytest.mark.asyncio


class Storage:
    def __init__(self) -> None:
        self.keys: list[str] = []

    async def upload(self, user_id: str, key: str, data: bytes) -> str:
        self.keys.append(key)
        return f"{user_id}/{key}"


class Documents:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    async def save(self, user_id: str, doc: dict[str, Any]) -> None:
        self.saved.append(doc)


class UoW:
    def __init__(self) -> None:
        self.agent_documents = Documents()


def _service(storage: Any) -> tuple[DocumentService, UoW]:
    uow = UoW()

    @asynccontextmanager
    async def factory():
        yield uow

    return DocumentService(factory, storage), uow


@pytest.mark.parametrize(
    ("filename", "stored_as"),
    [
        ("../../evil.txt", "evil.txt"),
        ("/etc/passwd", "passwd"),
        ("..\\..\\boot.ini", "boot.ini"),
        ("..", "attachment"),
        ("statement.pdf", "statement.pdf"),
    ],
)
async def test_an_agent_upload_is_keyed_by_its_safe_name(filename, stored_as):
    storage = Storage()
    service, uow = _service(storage)

    doc = await service.save_file("u1", filename=filename, file_bytes=b"x")

    assert storage.keys == [f"agent-uploads/{doc['id']}/{stored_as}"]
    assert (
        uow.agent_documents.saved[0]["storage_key"] == f"u1/agent-uploads/{doc['id']}/{stored_as}"
    )


async def test_an_agent_upload_named_to_climb_out_lands_in_the_users_folder(tmp_path):
    root = tmp_path / "storage"
    service, _ = _service(LocalStorageAdapter(root))

    doc = await service.save_file("u1", filename="../../../../evil.txt", file_bytes=b"x")

    assert doc["storage_key"] == str(
        (root / "u1" / "agent-uploads" / doc["id"] / "evil.txt").resolve()
    )
    assert [p.name for p in tmp_path.rglob("evil.txt")] == ["evil.txt"]
