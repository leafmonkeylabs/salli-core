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
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from salli.domain.secrets import redact_obj
from salli.domain.usage import AIAction
from salli.interfaces.api.contract import FileUpload
from salli.interfaces.api.deps import AppServices, Credentials, CurrentEmail, CurrentUser

router = APIRouter(prefix="/agent", tags=["agent"])

#: "scrooge" is the "Salli AI" persona (Pro Mode); "buddy" is the warmer one
#: behind the mobile app's Buddy Mode. A thread belongs to one of them.
Persona = Literal["scrooge", "buddy"]


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
                yield _sse({"type": "error", **payload})  # type: ignore[dict-item]
            elif event_type == "done":
                yield _sse({"type": "done"})
                return
        yield _sse({"type": "done"})
    except Exception as exc:
        yield _sse({"type": "error", "message": str(exc)})


# ── What the streams send ─────────────────────────────────────────────────────

_EVENTS = """Server-sent events. Each is one `data:` line holding a JSON object whose \
`type` says what it is:

- `token` `{content}`: text from the agent.
- `subagent_start` `{agent}`, `subagent_token` `{agent, content}`, `subagent_end` `{agent}`: \
a specialist (`tax_specialist`, `finance_specialist`) at work, and what it writes.
- `tool_call` `{name, input, agent?}` and `tool_result` `{name, output, agent?}`: a tool \
used by the agent, or by the specialist named in `agent`.
- `approval_required` `{action: {type, action, description, params}}`: a write waiting \
for the user. Answer it with `agent.resume` (`workflow: "chat"`, `decision: "approved"` \
or `"denied"`).
- `interrupt` `{data}`: any other pause.
- `error` `{message, code?, link?}`: the turn failed; `message` is a sentence to show. \
For an AI provider's own error, `code` names it (`chatgpt_usage_limit`: the user's ChatGPT \
plan reached its usage limit for Salli; `ai_sign_in_required`: sign in with ChatGPT again) \
and `link` is where the user can fix it (ChatGPT's usage settings).
- `done`: the last event, always sent."""

_CHAT_EVENTS = (
    _EVENTS + "\n\nA refusal from the deployment's usage meter comes before the stream "
    "opens, as an error response rather than an event, and so does an AI provider that "
    "cannot run at all (a ChatGPT plan paused at its limit, or needing a new sign-in)."
)

_RESUME_EVENTS = (
    _EVENTS + '\n\nWith `workflow: "return"` the stream is instead a single `token` whose '
    "`content` is the JSON-encoded result of the return workflow (`{worksheet, error}`), "
    "then `done`."
)


def _event_stream(description: str) -> dict[int | str, dict[str, Any]]:
    """An SSE response, documented by its media type and its events."""
    return {200: {"description": description, "content": {"text/event-stream": {}}}}


# ── Routes ────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    file_refs: list[str] = []
    # Defaulting to "scrooge" keeps any client that doesn't send this field
    # unchanged.
    persona: Persona = "scrooge"


@router.post("/chat", response_class=StreamingResponse, responses=_event_stream(_CHAT_EVENTS))
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
    # The model this conversation runs on: the pinned Claude model on
    # Anthropic, else the one picked from the user's own OpenAI or ChatGPT
    # models. The meter is told exactly that one.
    model_id = (
        await svc.profile.get_preferred_model(user_id)
        if creds.provider == "anthropic"
        else creds.model_for("best")
    )
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
                user_id, body.thread_id, body.message, ai_text, api_key=creds.llm or creds.anthropic
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
                    api_key=creds.llm or creds.anthropic,
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


class ChatAttachment(BaseModel):
    """A file uploaded for a chat message."""

    #: Pass it in the next `agent.chat` request's `file_refs` to attach the file.
    file_ref: str
    #: The file's name.
    name: str
    #: In bytes.
    size: int
    mime_type: str


@router.post("/files")
async def upload_file(
    form: Annotated[FileUpload, Form(media_type="multipart/form-data")],
    user_id: CurrentUser,
    svc: AppServices,
) -> ChatAttachment:
    """
    Upload a file to be attached to a chat message.
    Returns a file_ref ID to pass in the subsequent /agent/chat request.
    Supported: PDF, TXT, CSV, PNG, JPG, XLSX.
    """
    file = form.file
    file_bytes = await file.read()
    doc = await svc.documents.save_file(
        user_id,
        filename=file.filename or "attachment",
        file_bytes=file_bytes,
        mime_type=file.content_type or "application/octet-stream",
    )
    return ChatAttachment(
        file_ref=doc["id"],
        name=doc["title"],
        size=len(file_bytes),
        mime_type=doc["mime_type"],
    )


# Generous cap for a single push-to-talk turn — Voice Mode records short
# utterances, not long dictation, so this is well above any legitimate use.
class ResumeRequest(BaseModel):
    thread_id: str
    decision: str  # "approved"|"denied" (chat) or "approve"|"edit"|"reject" (return)
    workflow: str = "chat"  # "chat" | "return"
    edits: dict | None = None
    persona: Persona = "scrooge"


@router.post("/resume", response_class=StreamingResponse, responses=_event_stream(_RESUME_EVENTS))
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
                api_key=creds.llm or creds.anthropic,
                # The same model the conversation ran on (see `chat`).
                model=(
                    await svc.profile.get_preferred_model(user_id)
                    if creds.provider == "anthropic"
                    else creds.model_for("best")
                ),
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


# ── History ───────────────────────────────────────────────────────────────────


class ChatTextPart(BaseModel):
    """Text the agent wrote."""

    type: Literal["text"]
    content: str


class ChatToolCall(BaseModel):
    """A tool the agent called, and what it called it with."""

    type: Literal["tool_call"]
    name: str
    input: dict[str, Any]
    #: Always true here: the call has finished.
    done: bool


class ChatSubagentToken(BaseModel):
    """Text a specialist wrote, inside its section."""

    type: Literal["token"]
    content: str


class ChatSubagentSection(BaseModel):
    """Consecutive work by one specialist: what it wrote and the tools it called."""

    type: Literal["subagent_section"]
    #: `tax_specialist` or `finance_specialist`.
    agent: str
    #: Always false here: the specialist has finished.
    active: bool
    parts: list[Annotated[ChatSubagentToken | ChatToolCall, Field(discriminator="type")]]


class ChatUserMessage(BaseModel):
    role: Literal["user"]
    content: str


class ChatAssistantMessage(BaseModel):
    role: Literal["assistant"]
    parts: list[
        Annotated[ChatTextPart | ChatToolCall | ChatSubagentSection, Field(discriminator="type")]
    ]


class ChatHistory(BaseModel):
    """A conversation replayed as it looked while streaming: the user's
    messages, and each reply as the text, tool calls and specialist sections
    it streamed."""

    thread_id: str
    messages: list[Annotated[ChatUserMessage | ChatAssistantMessage, Field(discriminator="role")]]


@router.get("/history/{thread_id}")
async def get_history(
    thread_id: str,
    user_id: CurrentUser,
    svc: AppServices,
    persona: Persona = "scrooge",
) -> ChatHistory:
    """Return the message history for a conversation thread."""
    messages = await svc.agent.get_history(user_id=user_id, thread_id=thread_id, persona=persona)
    return ChatHistory.model_validate({"thread_id": thread_id, "messages": messages})


class AgentSession(BaseModel):
    """A conversation thread."""

    id: str
    user_id: str
    thread_id: str
    #: Generated after the first reply: null until then, or if that failed.
    title: str | None
    persona: Persona
    created_at: str
    last_active_at: str


class AgentSessions(BaseModel):
    #: Most recently active first.
    sessions: list[AgentSession]


@router.get("/sessions")
async def list_sessions(
    user_id: CurrentUser,
    svc: AppServices,
    limit: int = 50,
    persona: Persona = "scrooge",
) -> AgentSessions:
    """Return the user's conversation sessions (for this persona) sorted by most recent activity."""
    sessions = await svc.agent.list_sessions(user_id=user_id, limit=limit, persona=persona)
    return AgentSessions.model_validate({"sessions": sessions})


class AuditLogEntry(BaseModel):
    """A write the agent, or an MCP client, made or asked to make, and what was decided."""

    id: str
    user_id: str
    #: The write: create_account, create_reminder, post_journal_entry, ...
    action: str
    #: What the write was called with.
    params: dict[str, Any]
    #: The user's answer, "approved" or "denied". An MCP client's writes are
    #: recorded as approved.
    decision: str
    created_at: str


class AuditLog(BaseModel):
    #: Most recent first.
    entries: list[AuditLogEntry]


@router.get("/audit-log")
async def get_audit_log(user_id: CurrentUser, svc: AppServices, limit: int = 100) -> AuditLog:
    """Every agent-initiated write decision (approved or denied)."""
    entries = await svc.agent.get_audit_log(user_id=user_id, limit=limit)
    return AuditLog.model_validate({"entries": entries})


@router.delete("/sessions/{thread_id}", status_code=204)
async def delete_session(thread_id: str, user_id: CurrentUser, svc: AppServices):
    """Delete a conversation session."""
    await svc.agent.delete_session(user_id=user_id, thread_id=thread_id)
