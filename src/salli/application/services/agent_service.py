"""
AgentService — use-case orchestration for agent interactions.

Builds the manager agent (supervisor) and the return workflow. Exposes:
  - stream_chat(): streaming manager agent conversation as typed events
  - resume_chat(): resume after an interrupt (write-tool approval gate)
  - prepare_return(): run the return workflow to the review interrupt
  - resume_return(): resume after human decision
  - get_history(): fetch message history for a thread
"""

from __future__ import annotations

import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import Any

from salli.domain.ai_models import DEFAULT_MODEL
from salli.domain.llm import LLMError

_WORKER_NODES = {"tax_specialist", "finance_specialist"}


def _error_event(exc: BaseException) -> dict[str, Any]:
    """The `error` event for a failed turn: a sentence to show, and, for the
    typed model errors, a stable `code` and the `link` where the user can fix
    it (ChatGPT's usage settings, when a plan's limit was reached)."""
    if isinstance(exc, LLMError):
        event: dict[str, Any] = {"message": exc.message, "code": exc.code}
        if exc.link:
            event["link"] = exc.link
        return event
    return {"message": _provider_error_message(exc)}


def _provider_error_message(exc: BaseException) -> str:
    """A user-facing sentence for a failure that came from the LLM provider.

    Auth failures get their own wording because they're the one case the user can
    actually fix, and with BYOK they're expected rather than exotic: a key can be
    revoked, run out of credit, or be pasted wrong at any time.

    Never interpolates the provider's own message — an SDK error can quote the
    key it rejected. (`_sse` redacts as a second line of defence, but the right
    answer is not to put it there in the first place.) The typed errors in
    domain/llm.py already carry our own sentence, so they say it.
    """
    if isinstance(exc, LLMError):
        return exc.message
    text = f"{type(exc).__name__}: {exc}"
    if "401" in text or "authentication_error" in text or "invalid x-api-key" in text.lower():
        return (
            "The Anthropic API key was rejected. If you're using your own key, "
            "check it in Settings. Otherwise this is on our side."
        )
    if "429" in text or "rate_limit" in text:
        return "The AI provider is rate-limiting this key. Please try again shortly."
    if "credit" in text.lower() or "quota" in text.lower():
        return "The AI provider reported this key is out of credit."
    return "Something went wrong reaching the AI provider. Please try again."


async def _pending_interrupt(agent: Any, config: dict[str, Any]) -> Any | None:
    """
    Return the value of a pending interrupt() gate, or None.

    langgraph 1.x does not raise GraphInterrupt out of astream_events, nor emit a
    custom event — when a tool calls interrupt() the graph pauses and the interrupt
    is recorded in the checkpointed state. We read it back after the stream ends.
    """
    try:
        state = await agent.aget_state(config)
    except Exception:
        return None

    interrupts = list(getattr(state, "interrupts", None) or [])
    if not interrupts:
        for task in getattr(state, "tasks", None) or []:
            interrupts.extend(getattr(task, "interrupts", None) or [])
    if interrupts:
        return getattr(interrupts[0], "value", interrupts[0])
    return None


def _worker_from_event(event: dict) -> str | None:
    """
    Return the worker name if this LangGraph event originates from a worker agent.

    langgraph-supervisor compiles workers as subgraphs. Inside a subgraph the
    `langgraph_node` field is the *internal* node name (e.g. "agent"), NOT the
    worker's name. The worker name is recoverable from `langgraph_checkpoint_ns`
    which is formatted as "<worker>:<uuid>|<internal_node>:<uuid>".
    """
    meta = event.get("metadata", {})
    node = meta.get("langgraph_node", "")

    # Direct match — sometimes langgraph_node IS the worker name
    if node in _WORKER_NODES:
        return node

    # Inspect checkpoint namespace for the subgraph path
    ns: str = meta.get("langgraph_checkpoint_ns", "")
    if ns:
        # namespace looks like "tax_specialist:uuid|agent:uuid" or just "tax_specialist:uuid"
        first_segment = ns.split("|")[0].split(":")[0]
        if first_segment in _WORKER_NODES:
            return first_segment

    return None


#: How many graph steps one turn may take before LangGraph gives up.
#:
#: The default is 25, and a supervisor turn spends them fast: the manager's own
#: call, a handoff, the specialist's call, each of its tool round trips, the
#: handoff back, and the manager's synthesis. A tax question that consults both
#: specialists can pass 25 legitimately, and hitting the ceiling truncates the
#: turn rather than answering it, which looks exactly like the model choosing to
#: stop. Raised so the limit is a runaway backstop again instead of something a
#: normal question can reach.
GRAPH_RECURSION_LIMIT = 60


class AgentService:
    def __init__(
        self,
        ledger_svc: Any,
        tax_svc: Any,
        doc_svc: Any = None,
        profile_svc: Any = None,
        budget_svc: Any = None,
        debt_svc: Any = None,
        portfolio_svc: Any = None,
        subscription_svc: Any = None,
        insurance_svc: Any = None,
        advisor_svc: Any = None,
        fi_svc: Any = None,
        checkpointer: Any = None,
        uow_factory: Any = None,
        credentials: Any = None,
    ) -> None:
        self._ledger_svc = ledger_svc
        self._tax_svc = tax_svc
        self._doc_svc = doc_svc
        self._profile_svc = profile_svc
        self._budget_svc = budget_svc
        self._debt_svc = debt_svc
        self._portfolio_svc = portfolio_svc
        self._subscription_svc = subscription_svc
        self._insurance_svc = insurance_svc
        self._advisor_svc = advisor_svc
        self._fi_svc = fi_svc
        self._checkpointer = checkpointer
        self._uow_factory = uow_factory
        # LlmCredentialService: what a turn runs on when the caller did not
        # resolve it already (the CLI, which has no request boundary).
        self._credentials = credentials
        # Compiled graphs, keyed by (persona, date, key fingerprint, model) — see
        # _get_agent. Bounded because the key dimension is per-user.
        self._agents: OrderedDict[tuple[str, str, str, str], Any] = OrderedDict()
        self._tools_cache: dict[str, Any] = {}
        self._workflow: Any = None
        self._briefing_workflow: Any = None
        self._state_reader: Any = None

    _PERSONA_BUILDERS = {
        "scrooge": "salli.domain.agents.manager_agent:build_manager_agent",
        "buddy": "salli.domain.agents.buddy_agent:build_buddy_agent",
    }

    # A compiled graph is ~220 KB, so this caps the cache at ~28 MB. Platform-key
    # users collapse onto one entry per (persona, model), so in practice this only
    # fills up with distinct BYOK users, and evicting one is cheap: every
    # ChatAnthropic shares a process-wide httpx connection pool
    # (langchain_anthropic lru_caches it on base_url/timeout/proxy), so dropping a
    # graph closes no sockets.
    #
    # Raised from 32 when `model` joined the key. The key is now four-dimensional
    # (persona x date x credential x model), so with four selectable models the
    # old bound held a quarter as many distinct users as it used to — a BYOK user
    # switching models would evict everyone else's graph and pay the ~23 ms
    # rebuild on the next turn.
    _AGENT_CACHE_MAX = 128

    def _build_tools(self, persona: str) -> tuple[Any, Any]:
        """Manager + read tool lists, built once and shared across every graph.

        Safe to share regardless of user or key: the tools read the current user
        from a contextvar at call time rather than closing over one. Worth doing
        because rebuilding them is the single largest cost in graph construction
        (23 of ~41 ms), and with a per-key cache that cost would otherwise be
        paid per distinct user rather than once per day.
        """
        if "manager" not in self._tools_cache:
            from salli.domain.agents.tools import make_manager_tools, make_read_tools

            self._tools_cache["manager"] = make_manager_tools(
                self._doc_svc,
                self._ledger_svc,
                self._tax_svc,
                self._profile_svc,
                self._budget_svc,
                self._debt_svc,
                self._portfolio_svc,
                self._subscription_svc,
                self._insurance_svc,
                self._advisor_svc,
                self._fi_svc,
            )
            self._tools_cache["read"] = make_read_tools(self._ledger_svc, self._tax_svc)
        return self._tools_cache["manager"], self._tools_cache["read"]

    def _get_agent(
        self, persona: str = "scrooge", api_key: Any = None, model: str | None = None
    ) -> Any:
        """A compiled graph for this persona, credential, and model.

        The key has to be part of the cache key: langchain binds tools eagerly, so
        a model's api_key is fixed at construction and cannot be overridden
        per-invocation via config — attempting that silently falls back to the
        platform key, which is the one outcome BYOK must never produce.

        `model` is in the key for exactly the same reason. It is fixed at
        construction too, so without it a user who switched to Opus would have
        the usage meter told Opus and then be served the cached Sonnet graph —
        metered for a model they never got.

        Fingerprinted, never keyed on the key itself, so the cache cannot be a
        place a credential leaks from. The date component preserves the existing
        daily rebuild, which exists because the prompt bakes in today's date.
        """
        import datetime
        import hashlib
        import importlib

        from salli.domain.agents.model_factory import is_llm_client

        if persona not in self._PERSONA_BUILDERS:
            persona = "scrooge"

        if is_llm_client(api_key):
            # A resolved client names its provider and credential without
            # holding the secret, and its own "best" model is the default:
            # never a Claude id a model on another provider could not run.
            fingerprint = api_key.fingerprint
            model = model or api_key.model_for("best")
        else:
            raw = api_key.reveal() if hasattr(api_key, "reveal") else (api_key or "")
            fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:16] if raw else "none"
            model = model or DEFAULT_MODEL
        cache_key = (persona, datetime.date.today().isoformat(), fingerprint, model)

        cached = self._agents.get(cache_key)
        if cached is not None:
            self._agents.move_to_end(cache_key)
            return cached

        module_path, func_name = self._PERSONA_BUILDERS[persona].split(":")
        build_fn = getattr(importlib.import_module(module_path), func_name)
        manager_tools, read_tools = self._build_tools(persona)

        agent = build_fn(
            self._ledger_svc,
            self._tax_svc,
            self._doc_svc,
            self._profile_svc,
            self._budget_svc,
            self._debt_svc,
            self._portfolio_svc,
            self._subscription_svc,
            self._insurance_svc,
            self._advisor_svc,
            self._fi_svc,
            checkpointer=self._checkpointer,
            api_key=api_key,
            model=model,
            tools=manager_tools,
            read_tools=read_tools,
        )

        self._agents[cache_key] = agent
        # Drop the least recently used, and any entry from a previous day.
        while len(self._agents) > self._AGENT_CACHE_MAX:
            self._agents.popitem(last=False)
        return agent

    def _get_state_reader(self) -> Any:
        """One graph, built once, used only for aget_state.

        get_history and _pending_interrupt only read checkpointed state — they
        never invoke the model — so they must not need a credential. That keeps
        history readable for a user whose key was revoked, and keeps a listing
        from paying graph-construction cost. The placeholder key is never used;
        if this graph ever did invoke, it would fail with a 401 rather than
        quietly bill the platform.
        """
        if self._state_reader is None:
            self._state_reader = self._get_agent(
                "scrooge", "unused-state-reader-never-invokes-the-model"
            )
        return self._state_reader

    def _get_workflow(self) -> Any:
        if self._workflow is None:
            from salli.domain.agents.return_workflow import build_return_workflow

            self._workflow = build_return_workflow(
                self._ledger_svc,
                self._tax_svc,
                checkpointer=self._checkpointer,
            )
        return self._workflow

    def _get_briefing_workflow(self) -> Any:
        if self._briefing_workflow is None:
            from salli.domain.agents.briefing_workflow import build_briefing_workflow

            self._briefing_workflow = build_briefing_workflow(
                self._advisor_svc,
                checkpointer=self._checkpointer,
            )
        return self._briefing_workflow

    async def _build_message_content(
        self,
        user_id: str,
        message: str,
        file_refs: list[str] | None = None,
    ) -> Any:
        """Build a HumanMessage content block list, injecting file attachments."""
        from langchain_core.messages import HumanMessage

        content: list[Any] = [{"type": "text", "text": message}]

        if file_refs and self._doc_svc:
            for ref_id in file_refs:
                result = await self._doc_svc.get_file_as_base64(user_id, ref_id)
                if result:
                    b64, mime = result
                    doc_meta = await self._doc_svc.get_document(user_id, ref_id)
                    title = doc_meta.get("title", "attachment") if doc_meta else "attachment"
                    content.append(
                        {
                            "type": "document",
                            "source": {"type": "base64", "media_type": mime, "data": b64},
                            "title": title,
                        }
                    )

        if len(content) == 1 and content[0]["type"] == "text":
            return HumanMessage(content=content[0]["text"])
        return HumanMessage(content=content)

    async def _build_input_messages(
        self,
        user_id: str,
        message: str,
        file_refs: list[str] | None = None,
    ) -> list[Any]:
        """Build the message list sent into the manager agent graph: a leading
        tone-instruction SystemMessage when the user's message reads as
        frustrated/anxious/positive (see domain/agents/sentiment.py), then the
        HumanMessage itself. Extracted from stream_chat so it's unit-testable
        without invoking the graph or the LLM."""
        from salli.domain.agents.sentiment import classify_sentiment, tone_instruction

        human_msg = await self._build_message_content(user_id, message, file_refs)
        instruction = tone_instruction(classify_sentiment(message))
        if not instruction:
            return [human_msg]

        from langchain_core.messages import SystemMessage

        return [SystemMessage(content=instruction), human_msg]

    async def _stream_events(
        self, agent: Any, input_: Any, config: dict[str, Any]
    ) -> AsyncIterator[tuple[str, Any]]:
        """Shared SSE event extraction for both stream_chat and resume_chat."""
        active_worker: str | None = None

        try:
            async for event in agent.astream_events(input_, config=config, version="v2"):
                kind = event["event"]
                worker = _worker_from_event(event)

                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    content = chunk.content
                    text = ""
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        text = "".join(
                            b.get("text", "")
                            for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        )

                    if text:
                        if worker:
                            if active_worker != worker:
                                if active_worker:
                                    yield ("subagent_end", {"agent": active_worker})
                                active_worker = worker
                                yield ("subagent_start", {"agent": worker})
                            yield ("subagent_token", {"agent": worker, "content": text})
                        else:
                            if active_worker:
                                yield ("subagent_end", {"agent": active_worker})
                                active_worker = None
                            yield ("token", text)

                elif kind == "on_tool_start":
                    if active_worker and not worker:
                        yield ("subagent_end", {"agent": active_worker})
                        active_worker = None
                    name = event.get("name", "")
                    input_data = event["data"].get("input", {})
                    payload: dict[str, Any] = {"name": name, "input": input_data}
                    if worker:
                        payload["agent"] = worker
                    yield ("tool_call", payload)

                elif kind == "on_tool_end":
                    output = event["data"].get("output")
                    if hasattr(output, "content"):
                        output = output.content
                    name = event.get("name", "")
                    payload = {"name": name, "output": output}
                    if worker:
                        payload["agent"] = worker
                    yield ("tool_result", payload)

                elif kind == "on_custom_event" and event.get("name") == "interrupt":
                    yield ("interrupt", event["data"])

            # langgraph 1.x surfaces interrupt() via the checkpointed state rather
            # than an exception or custom event. After the stream drains, check for
            # a pending approval gate and surface it so the client can approve/deny.
            approval = await _pending_interrupt(agent, config)
            if approval is not None:
                yield ("approval_required", approval)

        except Exception as exc:
            exc_repr = repr(exc)
            # LangGraph raises an exception wrapping interrupt payloads
            if "GraphInterrupt" in exc_repr or "interrupt" in type(exc).__name__.lower():
                # Extract the interrupt value from the exception
                interrupt_value = getattr(exc, "args", [{}])
                if interrupt_value and isinstance(interrupt_value[0], (dict, list)):
                    data = interrupt_value[0]
                    if isinstance(data, list) and data:
                        data = data[0]
                        if hasattr(data, "value"):
                            data = data.value
                    yield ("approval_required", data)
                else:
                    yield ("interrupt", {"message": str(exc)})
            else:
                # Emit rather than re-raise. The `finally` below yields, and a
                # yield inside a finally while an exception is propagating
                # discards that exception — so `raise` here never reached the
                # router's handler, and the client got a clean `done` with no
                # reply and no explanation. A provider 401 looked identical to
                # a successful empty answer.
                yield ("error", _error_event(exc))
        finally:
            if active_worker:
                yield ("subagent_end", {"agent": active_worker})
            yield ("done", None)

    async def _credential_for(self, user_id: str, api_key: Any) -> Any:
        """The caller's credential (an HTTP route resolves it at the boundary),
        else this user's, resolved now: the CLI has no boundary to do it at.
        Left as it is when there is nothing to resolve with, so a missing key
        still fails loud in the model factory."""
        if api_key is not None or self._credentials is None:
            return api_key
        creds = await self._credentials.resolve(user_id)
        return creds.llm if creds.llm is not None else creds.anthropic

    # ── Session management ────────────────────────────────────────────────────

    async def _ensure_session(self, user_id: str, thread_id: str, persona: str = "scrooge") -> None:
        if not self._uow_factory:
            return
        try:
            async with self._uow_factory() as uow:
                await uow.agent_sessions.upsert(user_id, thread_id, persona=persona)
        except Exception:
            pass

    async def _persona_for_thread(self, user_id: str, thread_id: str, fallback: str) -> str:
        """The persona this thread was actually created with.

        Resuming and replaying must not trust a client-supplied persona. The two
        graphs have identical topology and node names — only the prompt differs —
        so resuming a Buddy thread as "scrooge" doesn't fail, it silently runs
        the wrong system prompt over Buddy's checkpoint, including over a pending
        write approval. `_ensure_session` already records the real persona on
        creation, so read it back instead.

        Falls back to the caller's value when there is no session row (a thread
        that predates session tracking) or no DB at all.
        """
        if not self._uow_factory:
            return fallback
        try:
            async with self._uow_factory() as uow:
                session = await uow.agent_sessions.get(user_id, thread_id)
        except Exception:
            return fallback
        stored = (session or {}).get("persona")
        return stored if stored in self._PERSONA_BUILDERS else fallback

    async def _try_generate_title(
        self, user_id: str, thread_id: str, user_msg: str, ai_text: str, *, api_key: Any
    ) -> None:
        """Fire-and-forget: generate a title on the fast model and persist it.

        `api_key` is the turn's credential: an LLMClient, or an Anthropic key."""
        if not self._uow_factory:
            return
        try:
            from salli.application.services.llm_credential_service import as_llm

            llm = as_llm(api_key)
            if llm is None:
                return
            prompt = (
                "Generate a 3-5 word title for this conversation. "
                "Reply with ONLY the title. No quotes, no punctuation, no explanation.\n\n"
                f"User: {user_msg[:200]}\n"
                f"Assistant: {ai_text[:400]}"
            )
            answer = await llm.generate(
                instructions="", input=prompt, tier="fast", temperature=0, max_output_tokens=20
            )
            title = answer.strip()[:100]
            if title:
                async with self._uow_factory() as uow:
                    await uow.agent_sessions.set_title(user_id, thread_id, title)
        except Exception:
            pass  # title generation is best-effort

    async def list_sessions(
        self, user_id: str, limit: int = 50, persona: str = "scrooge"
    ) -> list[dict[str, Any]]:
        if not self._uow_factory:
            return []
        async with self._uow_factory() as uow:
            return await uow.agent_sessions.list(user_id, limit=limit, persona=persona)

    async def get_audit_log(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Every agent-initiated write decision (approved or denied) recorded
        by create_account/create_reminder/post_journal_entry."""
        if not self._uow_factory:
            return []
        async with self._uow_factory() as uow:
            return await uow.audit_log.list(user_id, limit=limit)

    async def delete_session(self, user_id: str, thread_id: str) -> None:
        if not self._uow_factory:
            return
        async with self._uow_factory() as uow:
            await uow.agent_sessions.delete(user_id, thread_id)

    # ── Chat streaming ────────────────────────────────────────────────────────

    async def stream_chat(
        self,
        user_id: str,
        message: str,
        thread_id: str | None = None,
        file_refs: list[str] | None = None,
        persona: str = "scrooge",
        api_key: Any = None,
        model: str | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        """
        Yield (event_type, payload) tuples for SSE:
          ("token",            str)
          ("tool_call",        {"name": str, "input": dict, "agent"?: str})
          ("tool_result",      {"name": str, "output": Any, "agent"?: str})
          ("approval_required",{"type": str, "action": str, "description": str, "params": dict})
          ("subagent_start",   {"agent": str})
          ("subagent_end",     {"agent": str})
          ("subagent_token",   {"agent": str, "content": str})
          ("interrupt",        dict)
          ("done",             None)
        """
        if thread_id is None:
            thread_id = str(uuid.uuid4())

        from salli.domain.agents.tools import set_current_user

        set_current_user(user_id)  # tools read this, never the LLM-supplied id
        await self._ensure_session(user_id, thread_id, persona=persona)

        try:
            api_key = await self._credential_for(user_id, api_key)
        except LLMError as exc:
            # Resolved here only without an HTTP boundary (the CLI): say it as
            # the stream would, rather than end in a traceback.
            yield ("error", _error_event(exc))
            yield ("done", None)
            return
        agent = self._get_agent(persona, api_key, model)
        config = {
            "configurable": {"thread_id": f"{user_id}:{thread_id}", "user_id": user_id},
            "recursion_limit": GRAPH_RECURSION_LIMIT,
        }
        input_messages = await self._build_input_messages(user_id, message, file_refs)

        async for event in self._stream_events(agent, {"messages": input_messages}, config):
            yield event

    async def resume_chat(
        self,
        user_id: str,
        thread_id: str,
        decision: str,
        persona: str = "scrooge",
        api_key: Any = None,
        model: str | None = None,
    ) -> AsyncIterator[tuple[str, Any]]:
        """
        Resume the manager agent after an interrupt (write-tool approval gate).
        decision: "approved" | "denied"
        """
        from langgraph.types import Command

        from salli.domain.agents.tools import set_current_user

        set_current_user(user_id)
        api_key = await self._credential_for(user_id, api_key)
        # Server-owned, not the request's `persona` — see _persona_for_thread.
        agent = self._get_agent(
            await self._persona_for_thread(user_id, thread_id, persona), api_key, model
        )
        config = {
            "configurable": {"thread_id": f"{user_id}:{thread_id}", "user_id": user_id},
            "recursion_limit": GRAPH_RECURSION_LIMIT,
        }

        async for event in self._stream_events(agent, Command(resume=decision), config):
            yield event

    async def get_history(
        self,
        user_id: str,
        thread_id: str,
        persona: str = "scrooge",
    ) -> list[dict[str, Any]]:
        """
        Rebuild the full rich conversation so a reloaded thread looks like it did
        while streaming: user messages, manager text, handoff/tool calls, and
        collapsible specialist (sub-agent) sections with their detailed output.

        Each assistant turn is a list of `parts` mirroring the frontend MessagePart:
          {"type": "text", "content": str}
          {"type": "tool_call", "name": str, "input": dict, "done": true}
          {"type": "subagent_section", "agent": str, "active": false, "parts": [...]}
        """
        agent = self._get_state_reader()
        config = {"configurable": {"thread_id": f"{user_id}:{thread_id}"}}
        state = await agent.aget_state(config)
        all_msgs = state.values.get("messages", [])

        def _text(content: Any) -> str:
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                return " ".join(
                    b.get("text", "").strip()
                    for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                ).strip()
            return ""

        # Handoff plumbing the user should not see as a visible step
        _HIDE_TOOLS = {"transfer_back_to_supervisor"}

        result: list[dict[str, Any]] = []
        parts: list[dict[str, Any]] = []
        current_section: dict[str, Any] | None = None

        def flush_turn() -> None:
            nonlocal parts, current_section
            if parts:
                result.append({"role": "assistant", "parts": parts})
            parts = []
            current_section = None

        for msg in all_msgs:
            cls = msg.__class__.__name__
            name = getattr(msg, "name", None)

            if cls == "HumanMessage":
                flush_turn()
                user_text = _text(msg.content)
                if user_text:
                    result.append({"role": "user", "content": user_text})

            elif cls == "AIMessage":
                is_worker = name in _WORKER_NODES
                text = _text(msg.content)
                tool_calls = getattr(msg, "tool_calls", None) or []

                # A message whose only purpose is handing control back is plumbing —
                # skip both its tool call and its narration ("Transferring back...").
                is_handoff = any(tc.get("name") in _HIDE_TOOLS for tc in tool_calls)

                if is_worker:
                    # Group consecutive worker messages into one collapsible section
                    if current_section is None or current_section["agent"] != name:
                        current_section = {
                            "type": "subagent_section",
                            "agent": name,
                            "active": False,
                            "parts": [],
                        }
                        parts.append(current_section)
                    for tc in tool_calls:
                        if tc.get("name") in _HIDE_TOOLS:
                            continue
                        current_section["parts"].append(
                            {
                                "type": "tool_call",
                                "name": tc.get("name", ""),
                                "input": tc.get("args", {}),
                                "done": True,
                            }
                        )
                    if text and not is_handoff:
                        current_section["parts"].append({"type": "token", "content": text})
                else:
                    # A supervisor message closes any open worker section
                    current_section = None
                    if text:
                        parts.append({"type": "text", "content": text})
                    for tc in tool_calls:
                        if tc.get("name") in _HIDE_TOOLS:
                            continue
                        parts.append(
                            {
                                "type": "tool_call",
                                "name": tc.get("name", ""),
                                "input": tc.get("args", {}),
                                "done": True,
                            }
                        )

            # ToolMessage outputs are not rendered in the UI, so they are skipped.

        flush_turn()
        return result

    async def prepare_return(
        self,
        user_id: str,
        year: str | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Run the return workflow up to the human review gate, for `year` or the
        latest year Salli can compute for the user.
        Returns the interrupt payload (draft return for human approval), or the
        reason there is none (`error`).
        """
        if thread_id is None:
            thread_id = str(uuid.uuid4())

        workflow = self._get_workflow()
        config = {"configurable": {"thread_id": thread_id}}

        result = await workflow.ainvoke(
            {"user_id": user_id, "year": year or ""},
            config=config,
        )
        return {
            "thread_id": thread_id,
            "draft_return": result.get("draft_return", {}),
            "error": result.get("error", ""),
            "state": result,
        }

    async def resume_return(
        self,
        thread_id: str,
        decision: str,
    ) -> dict[str, Any]:
        """
        Resume the return workflow after human review.
        decision: "approve" | "edit" | "reject"
        """
        from langgraph.types import Command

        workflow = self._get_workflow()
        config = {"configurable": {"thread_id": thread_id}}

        result = await workflow.ainvoke(Command(resume=decision), config=config)
        return {"worksheet": result.get("worksheet", {}), "error": result.get("error", "")}

    async def prepare_briefing(
        self,
        user_id: str,
        email: str | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Run the monthly briefing workflow up to the human review gate.
        Returns the interrupt payload (draft briefing for human approval), or
        the gather-step error (e.g. a usage limit) if it never reached review.
        """
        if thread_id is None:
            thread_id = str(uuid.uuid4())

        workflow = self._get_briefing_workflow()
        config = {"configurable": {"thread_id": thread_id}}

        result = await workflow.ainvoke(
            {"user_id": user_id, "email": email},
            config=config,
        )
        advice = result.get("advice")
        return {
            "thread_id": thread_id,
            "error": result.get("error", ""),
            "briefing": {
                "summary": advice.summary if advice else "",
                "fire_tier_assessment": advice.fire_tier_assessment if advice else "",
                "recommendations": [r.model_dump() for r in advice.recommendations]
                if advice
                else [],
            },
        }

    async def resume_briefing(
        self,
        thread_id: str,
        decision: str,
    ) -> dict[str, Any]:
        """
        Resume the briefing workflow after human review.
        decision: "approve" | "edit" | "reject"
        """
        from langgraph.types import Command

        workflow = self._get_briefing_workflow()
        config = {"configurable": {"thread_id": thread_id}}

        result = await workflow.ainvoke(Command(resume=decision), config=config)
        return {"report": result.get("report", {}), "error": result.get("error", "")}
