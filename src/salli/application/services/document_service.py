"""
DocumentService — manages agent documents and named memories.

Documents are stored inline (content field) for text/small data, or as opaque
blobs in StoragePort for large binary files. Named memories use upsert-by-slug
so the agent can update a memory key without creating duplicates.
"""

from __future__ import annotations

import base64
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from salli.application.ports import StoragePort
    from salli.application.unit_of_work import UnitOfWork


class DocumentService:
    def __init__(self, uow_factory: Any, storage: StoragePort) -> None:
        self._uow_factory = uow_factory
        self._storage = storage

    async def save_document(
        self,
        user_id: str,
        title: str,
        content: str | None = None,
        mime_type: str = "text/plain",
        tags: list[str] | None = None,
        source: str = "agent_created",
        namespace: str = "documents",
        slug: str | None = None,
        description: str | None = None,
    ) -> str:
        doc: dict[str, Any] = {
            "title": title,
            "content": content,
            "mime_type": mime_type,
            "tags": tags or [],
            "source": source,
            "namespace": namespace,
            "slug": slug,
            "description": description,
        }
        async with self._uow_factory() as uow:
            uow: UnitOfWork
            doc_id = await uow.agent_documents.save(user_id, doc)
        return doc_id

    async def get_document(self, user_id: str, doc_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            uow: UnitOfWork
            return await uow.agent_documents.get(user_id, doc_id)

    async def update_document(self, user_id: str, doc_id: str, **updates: Any) -> None:
        async with self._uow_factory() as uow:
            uow: UnitOfWork
            await uow.agent_documents.update(user_id, doc_id, updates)

    async def list_documents(
        self,
        user_id: str,
        tags: list[str] | None = None,
        namespace: str | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            uow: UnitOfWork
            return await uow.agent_documents.list(
                user_id, tags=tags, namespace=namespace, search=search
            )

    async def delete_document(self, user_id: str, doc_id: str) -> None:
        async with self._uow_factory() as uow:
            uow: UnitOfWork
            doc = await uow.agent_documents.get(user_id, doc_id)
            if doc and doc.get("storage_key"):
                # Note: StoragePort has no delete method — files are retained
                pass
            await uow.agent_documents.delete(user_id, doc_id)

    async def save_memory(
        self, user_id: str, slug: str, value: str, namespace: str = "memories"
    ) -> str:
        doc: dict[str, Any] = {
            "title": slug,
            "content": value,
            "source": "agent_memory",
            "mime_type": "text/plain",
            "tags": ["memory"],
        }
        async with self._uow_factory() as uow:
            uow: UnitOfWork
            return await uow.agent_documents.upsert_by_slug(user_id, namespace, slug, doc)

    async def get_memory(
        self, user_id: str, slug: str, namespace: str = "memories"
    ) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            uow: UnitOfWork
            return await uow.agent_documents.get_by_slug(user_id, namespace, slug)

    async def list_memories(
        self, user_id: str, namespace: str = "memories"
    ) -> list[dict[str, Any]]:
        return await self.list_documents(user_id, namespace=namespace)

    async def save_file(
        self,
        user_id: str,
        filename: str,
        file_bytes: bytes,
        mime_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        """Upload bytes to StoragePort and record metadata as an agent document."""
        doc_id = str(uuid.uuid4())
        # Store the path upload() *returns*, not the key we passed in: both adapters
        # prefix the key with {user_id}, and download() expects that full returned
        # path. Building the key by hand here meant every uploaded file was recorded
        # under a location nothing had written to, so get_file_as_base64 could never
        # read one back. parsing_service.py does this correctly — match it.
        storage_key = await self._storage.upload(
            user_id, f"agent-uploads/{doc_id}/{filename}", file_bytes
        )
        async with self._uow_factory() as uow:
            uow: UnitOfWork
            await uow.agent_documents.save(
                user_id,
                {
                    "id": doc_id,
                    "title": filename,
                    "storage_key": storage_key,
                    "mime_type": mime_type,
                    "source": "user_upload",
                    "namespace": "documents",
                    "tags": ["upload"],
                },
            )
        return {
            "id": doc_id,
            "title": filename,
            "storage_key": storage_key,
            "mime_type": mime_type,
        }

    async def get_file_as_base64(self, user_id: str, doc_id: str) -> tuple[str, str] | None:
        """Return (base64_data, mime_type) for a stored file, or None."""
        doc = await self.get_document(user_id, doc_id)
        if not doc or not doc.get("storage_key"):
            return None
        file_bytes = await self._storage.download(doc["storage_key"])
        b64 = base64.b64encode(file_bytes).decode()
        return b64, doc.get("mime_type", "application/octet-stream")
