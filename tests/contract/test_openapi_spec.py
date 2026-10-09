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


def test_no_two_models_share_a_name():
    """Two different models with one name are both published under their
    module paths (`salli__interfaces__api__contract__Updated`), and those
    become type names in every generated client. Rename one, or reuse one of
    the shared shapes in interfaces/api/contract.py."""
    names = create_app().openapi()["components"]["schemas"]
    assert [name for name in names if name.startswith("salli__")] == []


def test_the_table_lists_no_route_that_is_gone():
    served = {(method, unversioned(path)) for method, path, _ in _operations()}
    assert sorted(set(OPERATION_IDS) - served) == []


def test_the_rest_api_is_versioned_and_protocols_keep_their_paths():
    for _, path, _ in _operations():
        assert path.startswith(API_PREFIX + "/") or path.startswith(PROTOCOL_PATHS), path


#: Operations whose success response has no schema yet, so generated clients
#: get `unknown` for them. Typing one means deleting its line; nothing may be
#: added. Grouped so work on different areas does not collide.
UNTYPED = {
    # Planning: financial independence, goals, the advisor, reports
    # Budgets, debts, holdings, subscriptions, insurance
    # Profile, onboarding, the agent, LLM keys, MCP connections
    # OAuth
    "oauth.authorizationServerMetadata",
    "oauth.authorize",
    "oauth.consent",
    "oauth.consentInfo",
    "oauth.protectedResourceMetadata",
    "oauth.register",
    "oauth.token",
}


def _is_typed(op: dict) -> bool:
    for code, response in op.get("responses", {}).items():
        if not code.startswith("2"):
            continue
        content = response.get("content")
        if not content:  # 204 No Content
            return True
        for media_type, body in content.items():
            # A stream or a file is described by its media type, not a schema.
            if media_type != "application/json" or body.get("schema"):
                return True
    return False


def test_untyped_operations_only_shrink():
    untyped = {op["operationId"] for _, _, op in _operations() if not _is_typed(op)}
    added = sorted(untyped - UNTYPED)
    assert not added, f"Give these a response model (a return type): {added}"
    fixed = sorted(UNTYPED - untyped)
    assert not fixed, f"These are typed now; delete them from UNTYPED: {fixed}"
