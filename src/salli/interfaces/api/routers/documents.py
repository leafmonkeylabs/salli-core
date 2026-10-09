"""
Agent documents router — browse and manage saved agent documents and memories.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from salli.interfaces.api.deps import AppServices, CurrentUser

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/")
async def list_documents(
    user_id: CurrentUser,
    svc: AppServices,
    namespace: str | None = Query(None, description="Filter: 'documents' or 'memories'"),
    tags: list[str] = Query([], description="Filter by tags"),
    search: str | None = Query(None, description="Full-text search over title and content"),
):
    """List agent documents. Optionally filter by namespace, tags, or full-text search."""
    docs = await svc.documents.list_documents(
        user_id,
        namespace=namespace,
        tags=tags or None,
        search=search,
    )
    return {"documents": docs, "count": len(docs)}


@router.get("/{doc_id}")
async def get_document(doc_id: str, user_id: CurrentUser, svc: AppServices):
    """Retrieve a single document by ID."""
    doc = await svc.documents.get_document(user_id, doc_id)
    if not doc:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: str, user_id: CurrentUser, svc: AppServices):
    """Permanently delete a document."""
    await svc.documents.delete_document(user_id, doc_id)
