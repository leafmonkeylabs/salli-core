"""
server.json, Salli's entry for the official MCP registry (docs/connectors.md),
keeps to the registry's rules: a name in the publisher's GitHub namespace, a
description of at most 100 characters, the package's version, and a remote
over Streamable HTTP at /mcp on the host whoever connects names.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_the_registry_entry_is_salli_s_remote_at_the_package_s_version():
    entry = json.loads((ROOT / "server.json").read_text())
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert entry["$schema"].startswith("https://static.modelcontextprotocol.io/schemas/")
    assert entry["name"] == "io.github.leafmonkeylabs/salli"
    assert len(entry["description"]) <= 100
    assert entry["version"] == version
    [remote] = entry["remotes"]
    assert remote["type"] == "streamable-http" and remote["url"] == "https://{host}/mcp"
    assert remote["variables"]["host"]["isRequired"] is True
