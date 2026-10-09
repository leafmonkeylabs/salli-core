"""
Agent router — SSE streaming for the manager agent chat.

Stream protocol (newline-delimited JSON events):
  {"type": "token",            "content": "..."}          Manager LLM text
  {"type": "tool_call",        "name": "...", "input": {}, "agent"?: "..."} Tool call
  {"type": "tool_result",      "name": "...", "output": {}, "agent"?: "..."} Tool result
  {"type": "approval_required", "action": {...}}            Write-tool approval gate
  {"type": "subagent_start",   "agent": "..."}             Worker agent started
  {"type": "subagent_end",     "agent": "..."}             Worker agent done
  {"type": "subagent_token",   "agent": "...", "content": "..."} Worker token
  {"type": "interrupt",        "data": {...}}               Other interrupt
  {"type": "done"}                                          Stream complete
  {"type": "error",            "message": "..."}            Unrecoverable error

Clients resume an interrupted chat agent by POSTing to /agent/resume with
workflow: "chat". Return-workflow resume uses workflow: "return".
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Literal

from fastapi import APIRouter, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from salli.domain.secrets import redact_obj
from salli.domain.usage import AIAction
from salli.interfaces.api.deps import AppServices, Credentials, CurrentEmail, CurrentUser

router = APIRouter(prefix="/agent", tags=["agent"])


# ── SSE helpers ───────────────────────────────────────────────────────────────


def _sse(data: dict) -> str:
    # Redact here rather than at each yield site: every frame in this module goes
    # through _sse, so one pass covers `error`, `interrupt`, and `tool_result`
    # alike. Needed because provider exceptions are stringified into the stream
    # (see _emit_events below) and a rejected-key error can carry the key itself.
    return f"data: {json.dumps(redact_obj(data), default=str)}\n\n"


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


async def _emit_events(
    event_iter: AsyncIterator[tuple[str, object]],
) -> AsyncIterator[str]:
    try:
        async for event_type, payload in event_iter:
            if event_type == "token":
                yield _sse({"type": "token", "content": payload})
            elif event_type == "subagent_token":
                yield _sse(
                    {
                        "type": "subagent_token",
                        "agent": payload["agent"],
                        "content": payload["content"],
                    }
                )  # type: ignore[index]
            elif event_type == "subagent_start":
                yield _sse({"type": "subagent_start", "agent": payload["agent"]})  # type: ignore[index]
            elif event_type == "subagent_end":
                yield _sse({"type": "subagent_end", "agent": payload["agent"]})  # type: ignore[index]
            elif event_type == "tool_call":
                yield _sse({"type": "tool_call", **payload})  # type: ignore[arg-type]
            elif event_type == "tool_result":
                yield _sse({"type": "tool_result", **payload})  # type: ignore[arg-type]
            elif event_type == "approval_required":
                yield _sse({"type": "approval_required", "action": payload})
            elif event_type == "interrupt":
                yield _sse({"type": "interrupt", "data": payload})
            elif event_type == "error":
                # The service emits this for a provider failure instead of
                # raising, because raising past its `finally` would discard the
                # exception. Without this branch the event would fall through
                # every elif and vanish just as silently.
                yield _sse({"type": "error", "message": payload["message"]})  # type: ignore[index]
            elif event_type == "done":
                yield _sse({"type": "done"})
                return
        yield _sse({"type": "done"})
    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})


# ── Routes ────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    file_refs: list[str] = []
    # "scrooge" is the existing "Salli AI" persona (Pro Mode); "buddy" is the
    # warmer persona behind the mobile app's Buddy Mode. Defaulting to
    # "scrooge" keeps any client that doesn't send this field unchanged.
    persona: Literal["scrooge", "buddy"] = "scrooge"


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user_id: CurrentUser,
    email: CurrentEmail,
    svc: AppServices,
    creds: Credentials,
):
    """
    Stream a manager agent response as Server-Sent Events.
    Passes the deployment's usage meter once per user message (not per LLM call)
    before streaming; after the stream completes a background task generates a
    session title via Haiku.
    """
    model_id = await svc.profile.get_preferred_model(user_id)
    await svc.usage.charge(user_id, AIAction.CHAT_MESSAGE, model_id=model_id, email=email)

    ai_acc: list[str] = []

    async def _collect(event_iter):
        async for event_type, payload in event_iter:
            if event_type == "token":
                ai_acc.append(str(payload))
            yield event_type, payload

    async def _generate_title_bg():
        ai_text = "".join(ai_acc)[:500]
        if ai_text:
            await svc.agent._try_generate_title(
                user_id, body.thread_id, body.message, ai_text, api_key=creds.anthropic
            )

    return StreamingResponse(
        _emit_events(
            _collect(
                svc.agent.stream_chat(
                    user_id=user_id,
                    thread_id=body.thread_id,
                    message=body.message,
                    file_refs=body.file_refs or None,
                    persona=body.persona,
                    api_key=creds.anthropic,
                    # The same id the usage meter above was told about. If
                    # these two ever diverge a meter prices one model while
                    # another runs, so they are deliberately the one variable.
                    model=model_id,
                )
            )
        ),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
        background=BackgroundTask(_generate_title_bg),
    )


@router.post("/files")
async def upload_file(file: UploadFile, user_id: CurrentUser, svc: AppServices):
    """
    Upload a file to be attached to a chat message.
    Returns a file_ref ID to pass in the subsequent /agent/chat request.
    Supported: PDF, TXT, CSV, PNG, JPG, XLSX.
    """
    file_bytes = await file.read()
    doc = await svc.documents.save_file(
        user_id,
        filename=file.filename or "attachment",
        file_bytes=file_bytes,
        mime_type=file.content_type or "application/octet-stream",
    )
    return {
        "file_ref": doc["id"],
        "name": doc["title"],
        "size": len(file_bytes),
        "mime_type": doc["mime_type"],
    }


# Generous cap for a single push-to-talk turn — Voice Mode records short
# utterances, not long dictation, so this is well above any legitimate use.
class ResumeRequest(BaseModel):
    thread_id: str
    decision: str  # "approved"|"denied" (chat) or "approve"|"edit"|"reject" (return)
    workflow: str = "chat"  # "chat" | "return"
    edits: dict | None = None
    persona: Literal["scrooge", "buddy"] = "scrooge"


@router.post("/resume")
async def resume(body: ResumeRequest, user_id: CurrentUser, svc: AppServices, creds: Credentials):
    """
    Resume an interrupted agent.
    - workflow="chat": resumes a write-tool approval gate (decision: "approved"|"denied")
    - workflow="return": resumes the return-preparation workflow (decision: "approve"|"reject")
    """
    if body.workflow == "return":
        return StreamingResponse(
            _emit_events(_wrap_return_resume(svc, body.thread_id, body.decision)),
            media_type="text/event-stream",
            headers=_SSE_HEADERS,
        )
    return StreamingResponse(
        _emit_events(
            svc.agent.resume_chat(
                user_id=user_id,
                thread_id=body.thread_id,
                decision=body.decision,
                persona=body.persona,
                api_key=creds.anthropic,
                model=await svc.profile.get_preferred_model(user_id),
            )
        ),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


async def _wrap_return_resume(
    svc: AppServices, thread_id: str, decision: str
) -> AsyncIterator[tuple[str, object]]:
    result = await svc.agent.resume_return(thread_id=thread_id, decision=decision)
    yield ("token", json.dumps(result))
    yield ("done", None)


@router.get("/history/{thread_id}")
async def get_history(
    thread_id: str,
    user_id: CurrentUser,
    svc: AppServices,
    persona: Literal["scrooge", "buddy"] = "scrooge",
):
    """Return the message history for a conversation thread."""
    messages = await svc.agent.get_history(user_id=user_id, thread_id=thread_id, persona=persona)
    return {"thread_id": thread_id, "messages": messages}


@router.get("/sessions")
async def list_sessions(
    user_id: CurrentUser,
    svc: AppServices,
    limit: int = 50,
    persona: Literal["scrooge", "buddy"] = "scrooge",
):
    """Return the user's conversation sessions (for this persona) sorted by most recent activity."""
    sessions = await svc.agent.list_sessions(user_id=user_id, limit=limit, persona=persona)
    return {"sessions": sessions}


@router.get("/audit-log")
async def get_audit_log(user_id: CurrentUser, svc: AppServices, limit: int = 100):
    """Every agent-initiated write decision (approved or denied)."""
    entries = await svc.agent.get_audit_log(user_id=user_id, limit=limit)
    return {"entries": entries}


@router.delete("/sessions/{thread_id}", status_code=204)
async def delete_session(thread_id: str, user_id: CurrentUser, svc: AppServices):
    """Delete a conversation session."""
    await svc.agent.delete_session(user_id=user_id, thread_id=thread_id)
