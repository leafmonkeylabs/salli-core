"""
Tax-aware scenarios over HTTP and MCP: `POST /v1/scenarios/run`, `/compare`
and `/v1/decisions/start` carry the tax section; a tax role no rule set of
the caller's declares, or one of a kind that can't be tagged, is refused
with its path; and nothing in the section ranks. The household is
tests/golden/taxed.py's, on the fictional XA 2031.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from salli.application.services.principle_service import PrincipleService
from salli.application.services.scenario_service import ScenarioService
from salli.application.services.template_service import TemplateService
from salli.interfaces.api import mcp_server
from tests import baseline_ledger
from tests.golden import taxed
from tests.guardrails import assert_never_ranks
from tests.unit.api.conftest import AUTH
from tests.unit.api.test_baseline_api import USER

pytestmark = pytest.mark.asyncio

RAISE = {
    "type": "income_change",
    "monthly": "+1000.00",
    "from": "2031-07-01",
    "tax_role": "salary",
    "label": "Raise",
}


def _doc(*changes: dict[str, Any], **more: Any) -> dict[str, Any]:
    return {"schema": "salli.scenario/1", "changes": list(changes), **more}


@pytest.fixture
def scenarios(monkeypatch, mock_services) -> ScenarioService:
    monkeypatch.setattr(baseline_ledger, "USER", USER)
    monkeypatch.setattr(taxed, "USER", USER)
    books = taxed.ledger()
    service = ScenarioService(
        books.uow.factory(), baselines=books.service(taxed.AS_OF), today=lambda: taxed.AS_OF
    )
    principles = PrincipleService(books.uow.factory(), service)
    mock_services.scenarios = service
    mock_services.templates = TemplateService(service, principles)
    return service


async def test_a_run_carries_the_tax(client, scenarios):
    r = await client.post("/v1/scenarios/run", json=_doc(RAISE), headers=AUTH)
    assert r.status_code == 200, r.text
    tax = r.json()["tax"]
    assert (tax["status"], tax["change_this_year"], tax["carried_forward"]) == (
        "computed",
        "1600.00",
        True,
    )
    first = tax["years"][0]
    assert first["net"] == {"baseline": "7200.00", "scenario": "8800.00", "delta": "1600.00"}
    assert first["monthly"][-1] == {"month": "2031-12", "amount": "266.65"}
    assert first["roles"] == [
        {
            "key": "salary",
            "kind": "income",
            "label": "Salary",
            "actual": "24000.00",
            "projected": "48000.00",
            "scenario": "54000.00",
        }
    ]
    assert tax["this_year"] == first
    # The first two years, and those of the checkpoints at 1, 5, 10 and 20
    # years (2032-06, 2036-06, 2041-06, 2051-06).
    assert [y["year"] for y in tax["years"]] == ["2031", "2032", "2036", "2041", "2051"]
    assert "tax_rules_carried_forward" in r.json()["placeholders"]
    assert_never_ranks(tax)


async def test_a_role_no_rule_set_declares_is_refused_with_its_path(client, scenarios):
    for role, says in (
        ("bonus", "is not a role any of your tax rule sets declares"),
        ("tax_withheld", "only income and deduction roles can be tagged"),
    ):
        r = await client.post(
            "/v1/scenarios/run", json=_doc({**RAISE, "tax_role": role}), headers=AUTH
        )
        assert r.status_code == 422, r.text
        (problem,) = r.json()["detail"]
        assert problem["loc"] == ["body", "changes", 0, "tax_role"] and says in problem["msg"]


async def test_a_comparison_carries_each_options_tax(client, scenarios):
    untagged = {k: v for k, v in RAISE.items() if k != "tax_role"}
    r = await client.post(
        "/v1/scenarios/compare",
        json={"options": [_doc(RAISE, label="Before tax"), _doc(untagged, label="Take-home")]},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    taxed_, plain = r.json()["options"]
    assert (taxed_["tax"]["status"], plain["tax"]["status"]) == ("computed", "none")
    assert_never_ranks(r.json())


async def test_a_start_puts_tax_answers_in_every_option(client, scenarios):
    r = await client.post(
        "/v1/decisions/start",
        json={
            "template": "big-change",
            "as_of": "2031-06-30",
            "answers": {
                "label": "New job",
                "start": "2031-07-01",
                "monthly_income": "+1000",
                "income_tax_role": "salary",
            },
            "tax_answers": {},
        },
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    job = body["comparison"]["options"][1]
    assert job["tax"]["change_this_year"] == "1600.00"
    figures = body["principles"]["options"][1]["figures"]
    assert figures["tax_change_this_year"] == "1600.00"
    assert body["principles"]["baseline"]["figures"]["tax_change_this_year"] == "0.00"
    question = next(
        q
        for q in (await client.get("/v1/decisions/templates/big-change", headers=AUTH)).json()[
            "questions"
        ]
        if q["id"] == "income_tax_role"
    )
    assert question["type"] == "tax_role" and question["default"] is None
    assert_never_ranks(body)


async def test_mcp_runs_the_same_tax(client, scenarios):
    services = MagicMock()
    services.scenarios = scenarios
    server = mcp_server.build_mcp_server(services, "https://api.test")
    with patch.object(mcp_server, "_current_user_id", return_value=USER):
        _, result = await server.call_tool("run_scenario", {"scenario": _doc(RAISE)})
    api = await client.post("/v1/scenarios/run", json=_doc(RAISE), headers=AUTH)
    assert result["tax"] == api.json()["tax"]
    tools = {t.name: t for t in await server.list_tools()}
    assert "tax_role" in mcp_server.SCENARIO_GUIDE
    assert "tax_answers" in tools["start_decision"].inputSchema["properties"]
