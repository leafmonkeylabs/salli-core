"""
Agent documents router — browse and manage saved agent documents and memories.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/documents", tags=["documents"])


class AgentDocument(BaseModel):
    id: str
    user_id: str
    title: str
    #: Text kept inline; null for a file held in storage.
    content: str | None
    #: Where an uploaded file is held; null for inline text.
    storage_key: str | None
    mime_type: str
    tags: list[str]
    #: Who made it: "user_upload", "agent_created", "agent_memory", "mcp_client".
    source: str
    #: "documents" or "memories".
    namespace: str
    #: A memory's name, unique within its namespace; null for documents.
    slug: str | None
    description: str | None
    created_at: str
    updated_at: str


class AgentDocumentList(BaseModel):
    documents: list[AgentDocument]
    count: int


@router.get("/")
async def list_documents(
    user_id: CurrentUser,
    svc: AppServices,
    namespace: str | None = Query(None, description="Filter: 'documents' or 'memories'"),
    tags: list[str] = Query([], description="Filter by tags"),
    search: str | None = Query(None, description="Full-text search over title and content"),
) -> AgentDocumentList:
    """List agent documents. Optionally filter by namespace, tags, or full-text search."""
    docs = await svc.documents.list_documents(
        user_id,
        namespace=namespace,
        tags=tags or None,
        search=search,
    )
    return AgentDocumentList.model_validate({"documents": docs, "count": len(docs)})


@router.get("/{doc_id}")
async def get_document(doc_id: str, user_id: CurrentUser, svc: AppServices) -> AgentDocument:
    """Retrieve a single document by ID."""
    doc = await svc.documents.get_document(user_id, doc_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Document not found")
    return AgentDocument.model_validate(doc)


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str, user_id: CurrentUser, svc: AppServices):
    """Permanently delete a document."""
    await svc.documents.delete_document(user_id, doc_id)
