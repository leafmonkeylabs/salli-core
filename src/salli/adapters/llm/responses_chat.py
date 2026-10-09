"""
A LangChain chat model over OpenAI's Responses API, for the LangGraph agents
on either OpenAI route (an API key, or the user's ChatGPT plan).

Why not `langchain_openai.ChatOpenAI(use_responses_api=True)`: checked against
langchain-openai 1.3.3, with every request captured. It can be told to send
`store: false` and `stream: true`, and it sends none of the plan route's
unsupported fields unless asked to; but it sends every SystemMessage as a
`{"type": "message", "role": "system"}` input item, with no way to route the
prompt LangGraph prepends into `instructions`, and that item is exactly what
the plan route rejects. It also binds function tools at the top level, where
the plan route wants them in a namespace. So this is a small model of its own,
over httpx, that builds the request with adapters/llm/responses.py: the same
body and the same stream handling as every other OpenAI call in Salli.

Async only: the agents run on asyncio throughout.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from contextlib import aclosing
from typing import Any, cast

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel, agenerate_from_stream
from langchain_core.messages import AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict, Field

from salli.adapters.llm.responses import (
    BearerSession,
    FinalResponse,
    HttpFactory,
    ResponsesRoute,
    request_body,
    stream_response,
    to_input,
)


class ResponsesChatModel(BaseChatModel):
    """Tool calling and token streaming on `POST /v1/responses`."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    route: ResponsesRoute
    model_name: str = Field(alias="model")
    session: Any = Field(exclude=True)
    http_factory: Any = Field(default=None, exclude=True)

    @property
    def _llm_type(self) -> str:
        return f"openai-responses-{self.route.provider}"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": self.model_name, "route": self.route.provider}

    def bind_tools(  # type: ignore[override]
        self,
        tools: Sequence[Any],
        *,
        tool_choice: Any = None,
        parallel_tool_calls: bool | None = None,
        **kwargs: Any,
    ) -> Any:
        """Bind tools, kept in LangChain's OpenAI shape: LangGraph reads the
        bound names back from it to check them. The request reshapes them for
        the route (adapters/llm/responses.py). `parallel_tool_calls` is taken
        so the supervisor can turn it off: two hand-offs at once is not a turn."""
        formatted = [convert_to_openai_tool(tool) for tool in tools]
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            kwargs["parallel_tool_calls"] = parallel_tool_calls
        return super().bind(tools=formatted, **kwargs)

    def _body(self, messages: list[BaseMessage], kwargs: dict[str, Any]) -> dict[str, Any]:
        instructions, items = to_input(messages, self.route)
        return request_body(
            self.route,
            model=self.model_name,
            instructions=instructions,
            items=items,
            tools=kwargs.get("tools") or (),
            tool_choice=kwargs.get("tool_choice"),
            parallel_tool_calls=kwargs.get("parallel_tool_calls"),
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError("ResponsesChatModel is async only: use ainvoke or astream")

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return await agenerate_from_stream(self._astream(messages, stop=stop, **kwargs))

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[ChatGenerationChunk, None]:
        # `stop` has no Responses equivalent, and nothing in Salli passes one.
        # LangChain reports each chunk to the callbacks itself, so this only yields.
        body = self._body(messages, kwargs)
        session = cast(BearerSession, self.session)
        factory = cast(HttpFactory | None, self.http_factory)
        async with aclosing(
            stream_response(self.route, body, session=session, http_factory=factory)
        ) as events:
            async for kind, value in events:
                if kind == "delta":
                    yield ChatGenerationChunk(message=AIMessageChunk(content=str(value)))
                else:
                    yield _final_chunk(cast(FinalResponse, value), self.model_name)


def _final_chunk(final: FinalResponse, model: str) -> ChatGenerationChunk:
    """The last chunk: the tool calls, whole, and what the response used.
    Text has already streamed, so none is repeated here."""
    message = AIMessageChunk(
        content="",
        tool_call_chunks=[
            {"name": call.name, "args": call.arguments, "id": call.call_id, "index": index}
            for index, call in enumerate(final.calls)
        ],
        response_metadata={"model_name": final.model or model, "id": final.response_id},
    )
    usage = final.usage or {}
    if usage:
        message.usage_metadata = {
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
        }
    return ChatGenerationChunk(message=message)
