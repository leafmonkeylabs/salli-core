"""`salli.panel/1` (docs/design/panels.md): what a valid screen is."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from salli.domain.panels import Panel, check_panel

GOOD: dict[str, Any] = {
    "schema": "salli.panel/1",
    "id": "billing-info",
    "title": "Your account",
    "sections": [
        {
            "heading": "Use",
            "rows": [
                {"kind": "text", "label": "Room left", "value": "3.50"},
                {"kind": "link", "label": "Terms", "detail": None, "url": "https://x.test/t"},
                {
                    "kind": "action",
                    "label": "Cancel",
                    "detail": None,
                    "confirm": "Are you sure?",
                    "action": {
                        "method": "DELETE",
                        "path": "/v1/x/1",
                        "body": None,
                        "then": "close",
                    },
                },
                {
                    "kind": "form",
                    "label": "Ask",
                    "fields": [
                        {"name": "size", "label": "Size", "type": "number", "required": True},
                        {
                            "name": "kind",
                            "label": "Kind",
                            "type": "select",
                            "options": [{"value": "a", "label": "A"}],
                            "required": False,
                        },
                    ],
                    "submit": {
                        "label": "Send",
                        "method": "POST",
                        "path": "/v1/x/ask",
                        "then": "refresh",
                    },
                },
            ],
            "footnote": "All figures are the deployment's.",
        }
    ],
    "note": None,
}


def _with(change) -> dict[str, Any]:
    doc = copy.deepcopy(GOOD)
    change(doc)
    return doc


def test_a_valid_panel_round_trips_and_has_a_json_schema():
    assert check_panel(GOOD)["sections"][0]["rows"][0] == {
        "kind": "text",
        "label": "Room left",
        "value": "3.50",
    }
    assert json.dumps(Panel.model_json_schema(by_alias=True))


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(schema="salli.panel/2"),
        lambda d: d.update(id="Not Valid"),
        lambda d: d.update(extra=1),
        lambda d: d.update(sections=[{"rows": []}] * 9),
        lambda d: d["sections"][0].update(rows=[{"kind": "text", "label": "x"}] * 25),
        lambda d: d.update(title="x" * 281),
        lambda d: d["sections"][0]["rows"][1].update(url="http://x.test/"),
        lambda d: d["sections"][0]["rows"][1].update(url="javascript:alert(1)"),
        lambda d: d["sections"][0]["rows"][2]["action"].update(path="https://evil.test/v1/x"),
        lambda d: d["sections"][0]["rows"][2]["action"].update(path="/v2/x"),
        lambda d: d["sections"][0]["rows"][2]["action"].update(path="/v1/../admin"),
        lambda d: d["sections"][0]["rows"][2]["action"].update(path="/v1//evil.test"),
        lambda d: d["sections"][0]["rows"][2]["action"].update(method="PUT"),
        lambda d: d["sections"][0]["rows"][2]["action"].update(then="open"),
        lambda d: d["sections"][0]["rows"][3]["submit"].update(path="/accounts"),
        lambda d: d["sections"][0]["rows"][3]["submit"].update(method="DELETE"),
        lambda d: d["sections"][0]["rows"][3]["fields"][0].update(type="date"),
        lambda d: d["sections"][0]["rows"][3]["fields"][1].update(options=None),
        lambda d: d["sections"][0]["rows"][3]["fields"][0].update(
            options=[{"value": "a", "label": "A"}]
        ),
        lambda d: d["sections"][0]["rows"].append({"kind": "image", "label": "x"}),
    ],
)
def test_a_document_outside_the_schema_is_refused(change):
    with pytest.raises(ValueError):
        check_panel(_with(change))
