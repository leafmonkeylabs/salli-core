"""
One golden household's Salli as a stdio MCP server, for a client that runs
its own MCP connections (`claude -p`; benchmark/run.py's `--via claude`).

It lists and answers exactly what benchmark/households.py's in-process Salli
does, on a connection that may only read, and appends each tool call and its
answer to `--log` (one JSON line each), the evidence the scorer checks
figures against:

    uv run python -m benchmark.serve --household household --log calls.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from benchmark.households import HOUSEHOLDS, Salli


def build(household: str, log: str | None) -> Server[Any, Any]:
    salli = Salli(household)
    server: Server[Any, Any] = Server("salli", instructions=salli.instructions)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(name=t["name"], description=t["description"], inputSchema=t["input_schema"])
            for t in await salli.tools()
        ]

    @server.call_tool(validate_input=False)
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        result = await salli.call(name, arguments)
        if log:
            with open(log, "a") as out:
                out.write(json.dumps({"tool": name, "args": arguments, "result": result}) + "\n")
        return [types.TextContent(type="text", text=json.dumps(result))]

    return server


async def serve(household: str, log: str | None) -> None:
    server = build(household, log)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m benchmark.serve", description=__doc__)
    parser.add_argument("--household", choices=sorted(HOUSEHOLDS), required=True)
    parser.add_argument("--log", help="append each tool call and its answer here (JSON lines)")
    args = parser.parse_args(argv)
    asyncio.run(serve(args.household, args.log))


if __name__ == "__main__":
    main()
