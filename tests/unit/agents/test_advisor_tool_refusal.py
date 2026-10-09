"""
When the usage meter refuses a fresh advisor run, the agent's tool and the MCP
tool both hand the meter's own sentence to the model instead of failing the
turn — the model can then tell the user why, in the deployment's words.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from salli.domain.usage import AIAction, UsageLimitReached

pytestmark = pytest.mark.asyncio

REFUSAL = UsageLimitReached(AIAction.ADVISOR_RUN, message="The meter's own words.")


async def test_the_agent_tool_returns_the_meter_message():
    from salli.domain.agents.tools import make_manager_tools, set_current_user

    advisor = AsyncMock()
    advisor.run_advisor.side_effect = REFUSAL
    with patch.dict("os.environ", {"TAVILY_API_KEY": "tvly-test"}):
        tools = make_manager_tools(MagicMock(), MagicMock(), MagicMock(), advisor_svc=advisor)
    tool = next(t for t in tools if t.name == "run_wealth_advisor")
    set_current_user("u1")

    assert await tool.ainvoke({}) == {"error": "The meter's own words."}


async def test_the_mcp_tool_returns_the_meter_message():
    from salli.interfaces.api import mcp_server

    services = MagicMock()
    services.advisor = AsyncMock()
    services.advisor.run_advisor.side_effect = REFUSAL
    server = mcp_server.build_mcp_server(services, "https://api.test")

    with patch.object(mcp_server, "_current_user_id", return_value="u1"):
        _, structured = await server.call_tool("run_wealth_advisor", {})

    assert structured == {"error": "The meter's own words."}
