"""
The HTTP contract clients are generated from.

The committed `openapi/openapi.json` must be what the app serves, every one of
Salli's own operations must have its deliberate id, and the REST API must live
under /v1 while the old paths keep working, marked deprecated.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from salli.interfaces.api.contract import API_PREFIX, OPERATION_IDS, unversioned
from salli.interfaces.api.main import create_app
from salli.interfaces.api.spec import render

SPEC = Path(__file__).resolve().parents[2] / "openapi" / "openapi.json"
PROTOCOL_PATHS = ("/.well-known/", "/mcp/oauth/", "/healthz")


def _operations() -> list[tuple[str, str, dict]]:
    spec = create_app().openapi()
    return [
        (method.upper(), path, op)
        for path, ops in spec["paths"].items()
        for method, op in ops.items()
    ]


def test_the_committed_spec_is_what_the_app_serves():
    assert SPEC.read_text() == render(), (
        "openapi/openapi.json is stale. Regenerate it: "
        "uv run python -m salli.interfaces.api.spec > openapi/openapi.json"
    )


def test_every_operation_has_its_listed_id():
    unnamed = [
        (method, path)
        for method, path, op in _operations()
        if OPERATION_IDS.get((method, unversioned(path))) != op["operationId"]
    ]
    assert not unnamed, f"Add these to OPERATION_IDS in interfaces/api/contract.py: {unnamed}"


def test_operation_ids_are_unique():
    counts = Counter(op["operationId"] for _, _, op in _operations())
    assert [oid for oid, n in counts.items() if n > 1] == []


def test_the_table_lists_no_route_that_is_gone():
    served = {(method, unversioned(path)) for method, path, _ in _operations()}
    assert sorted(set(OPERATION_IDS) - served) == []


def test_the_rest_api_is_versioned_and_protocols_keep_their_paths():
    for _, path, _ in _operations():
        assert path.startswith(API_PREFIX + "/") or path.startswith(PROTOCOL_PATHS), path
