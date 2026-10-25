"""The experimental engines (docs/scope.md) are marked in the API document,
and SALLI_EXPERIMENTAL (off by default) keeps their MCP tools out of an agent's list."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import salli.config
from salli.config import Settings
from salli.interfaces.api import experimental, mcp_server

SPEC = Path(__file__).parents[3] / "openapi" / "openapi.json"


def test_every_experimental_operation_is_marked_and_tagged():
    spec = json.loads(SPEC.read_text())
    marked = {
        op["operationId"]: op
        for item in spec["paths"].values()
        for op in item.values()
        if op.get("x-experimental")
    }
    assert set(marked) == experimental.OPERATIONS
    assert all("experimental" in op["tags"] for op in marked.values())
    assert "experimental" in {tag["name"] for tag in spec["tags"]}


async def _tools(monkeypatch, **settings) -> tuple[set[str], set[str]]:
    monkeypatch.setattr(salli.config, "_settings", Settings(_env_file=None, **settings))
    services = MagicMock()
    services.ledger._uow_factory = MagicMock(return_value=AsyncMock())
    server = mcp_server.build_mcp_server(services, "https://api.test")
    tools = {t.name for t in await server.list_tools()}
    prompts = {p.name for p in await server.list_prompts()}
    return tools, prompts


async def test_the_switch_hides_the_experimental_tools(monkeypatch):
    tools, prompts = await _tools(monkeypatch, salli_experimental=True)
    assert tools >= experimental.MCP_TOOLS and prompts >= experimental.MCP_PROMPTS
    tools, prompts = await _tools(monkeypatch)  # off by default
    assert not tools & experimental.MCP_TOOLS and not prompts & experimental.MCP_PROMPTS
    assert "get_overview" in tools
