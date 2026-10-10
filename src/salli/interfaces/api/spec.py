"""
The OpenAPI document clients are generated from, as committed in
`openapi/openapi.json`.

Regenerate it after changing a route:

    uv run python -m salli.interfaces.api.spec > openapi/openapi.json

tests/contract/test_openapi_spec.py fails when the committed copy and the app
disagree, so a change to the contract is always a visible diff in review.
"""

from __future__ import annotations

import json
import sys
from typing import Any


def build() -> dict[str, Any]:
    from salli.interfaces.api.main import create_app

    return create_app().openapi()


def render() -> str:
    return json.dumps(build(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    sys.stdout.write(render())
