"""/v1/tax/schema and /v1/tax/rule-sets over HTTP: the routes, the problems they
answer with, and who may activate."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from salli.application.permissions import Actor
from salli.application.ports import FetchRefused
from salli.application.services.tax_rule_service import (
    RuleSetConflict,
    RuleSetDocumentError,
    RuleSetNotFound,
    RuleSetPermissionError,
    RuleSetRateMissing,
    RuleSetStateError,
)
from salli.domain.taxrules.common import Problem
from salli.interfaces.api.deps import Principal, get_principal
from tests.unit.api.conftest import AUTH

pytestmark = pytest.mark.asyncio

NOW = datetime(2031, 2, 1, tzinfo=UTC)
BASE = "/v1/tax/rule-sets"
SUMMARY = {
    "id": "v1",
    "rule_set_id": "rs1",
    "version": 1,
    "status": "validated",
    "content_hash": "a" * 64,
    "author_kind": "user",
    "author_name": None,
    "change_note": None,
    "created_at": NOW,
    "proposed_at": None,
    "activated_at": None,
    "superseded_at": None,
}
VERSION = {
    **SUMMARY,
    "content": {"schema": "salli.tax/1"},
    "validation": {
        "ok": True,
        "content_hash": "a" * 64,
        "validated_at": NOW.isoformat(),
        "errors": [],
        "warnings": [{"path": "roles[1]", "message": "Role 'x' is never used", "snippet": None}],
        "examples": [{"name": "Basic", "passed": True, "error": None, "mismatches": []}],
    },
}


@pytest.fixture
def rules(mock_services):
    mock_services.tax_rules = AsyncMock()
    mock_services.tax_rules.schema = MagicMock(return_value={"title": "Salli tax rule set"})
    return mock_services.tax_rules


def _as(app, method: str, first_party_client: bool = False) -> None:
    app.dependency_overrides[get_principal] = lambda: Principal(
        "test-user-1", None, method, first_party_client=first_party_client
    )


async def test_the_schema_is_served(client, rules):
    r = await client.get("/v1/tax/schema", headers=AUTH)
    assert (r.status_code, r.json()) == (200, {"title": "Salli tax rule set"})


async def test_a_rule_set_is_created_from_a_document_and_shows_its_report(client, rules):
    rules.create.return_value = VERSION
    r = await client.post(BASE, json={"document": '{"schema": "salli.tax/1"}'}, headers=AUTH)
    assert r.status_code == 201
    body = r.json()
    assert body["document"] == {"schema": "salli.tax/1"}
    assert body["validation"]["warnings"][0]["path"] == "roles[1]"
    actor, document = rules.create.await_args.args
    assert actor == Actor("test-user-1", "user", None, actor.permissions)
    assert document == '{"schema": "salli.tax/1"}'


async def test_what_can_t_be_stored_is_a_422_listing_each_problem(client, rules):
    rules.create.side_effect = RuleSetDocumentError(
        "This is not a rule set Salli can read", [Problem("$", "Not valid JSON")]
    )
    r = await client.post(BASE, json={"document": "{"}, headers=AUTH)
    assert r.status_code == 422
    assert r.json()["type"] == "/problems/invalid-rule-set"
    assert r.json()["detail"] == "This is not a rule set Salli can read: $: Not valid JSON"


async def test_a_second_rule_set_for_the_same_year_is_a_409(client, rules):
    rules.create.side_effect = RuleSetConflict("rs1", "XZ 2031")
    r = await client.post(BASE, json={"document": {}}, headers=AUTH)
    assert (r.status_code, r.json()["type"]) == (409, "/problems/rule-set-exists")


async def test_someone_else_s_rule_set_is_simply_not_found(client, rules):
    rules.get.side_effect = RuleSetNotFound()
    r = await client.get(f"{BASE}/rs-of-someone-else", headers=AUTH)
    assert (r.status_code, r.json()["detail"]) == (404, "Tax rule set not found")


async def test_version_routes_name_their_rule_set(client, rules):
    rules.get_version.return_value = VERSION
    rules.validate.return_value = VERSION
    rules.propose.return_value = {**VERSION, "status": "proposed", "proposed_at": NOW}
    assert (await client.get(f"{BASE}/rs1/versions/v1", headers=AUTH)).status_code == 200
    rules.get_version.assert_awaited_once_with("test-user-1", "v1", "rs1")
    await client.post(f"{BASE}/rs1/versions/v1/validate", headers=AUTH)
    assert rules.validate.await_args.args[1:] == ("v1", "rs1")
    r = await client.post(f"{BASE}/rs1/versions/v1/propose", headers=AUTH)
    assert r.json()["status"] == "proposed"


async def test_a_proposal_that_fails_validation_is_a_409(client, rules):
    rules.propose.side_effect = RuleSetStateError("Version 2 can't be proposed: examples")
    r = await client.post(f"{BASE}/rs1/versions/v2/propose", headers=AUTH)
    assert (r.status_code, r.json()["type"]) == (409, "/problems/rule-set-state")


@pytest.mark.parametrize(
    ("method", "first_party_client", "allowed"),
    [
        ("session", False, True),
        ("pat", False, True),
        ("dev", False, True),
        ("oauth", True, True),  # the salli CLI
        ("oauth", False, False),  # any other OAuth client
    ],
)
async def test_only_the_user_s_own_sign_ins_reach_activation(
    app, client, rules, method, first_party_client, allowed
):
    _as(app, method, first_party_client)
    rules.activate.return_value = {**VERSION, "status": "active", "activated_at": NOW}
    r = await client.post(f"{BASE}/rs1/versions/v1/activate", headers=AUTH)
    if allowed:
        assert r.status_code == 200 and r.json()["status"] == "active"
        assert rules.activate.await_args.args[0].may("tax:activate")
    else:
        assert r.status_code == 403
        assert "tax:activate" in r.json()["detail"]
        rules.activate.assert_not_awaited()


async def test_the_service_s_own_refusal_is_a_403_too(client, rules):
    rules.activate.side_effect = RuleSetPermissionError("needs your own sign-in")
    r = await client.post(f"{BASE}/rs1/versions/v1/activate", headers=AUTH)
    assert (r.status_code, r.json()["type"]) == (403, "/problems/permission")


async def test_an_import_takes_a_document_or_a_url_never_both(client, rules):
    rules.import_url.return_value = {**VERSION, "status": "draft"}
    r = await client.post(
        f"{BASE}/import", json={"url": "https://rules.example/x.json"}, headers=AUTH
    )
    assert r.status_code == 201 and r.json()["status"] == "draft"
    for body in ({}, {"url": "https://x.example", "document": "{}"}):
        assert (await client.post(f"{BASE}/import", json=body, headers=AUTH)).status_code == 422
    rules.import_url.side_effect = FetchRefused(
        "That address is not on the public internet; refused"
    )
    r = await client.post(f"{BASE}/import", json={"url": "https://10.0.0.1/x"}, headers=AUTH)
    assert (r.status_code, r.json()["type"]) == (422, "/problems/fetch-refused")


async def test_the_diff_compares_from_the_named_version_or_the_active_one(client, rules):
    rules.diff.return_value = {
        "rule_set_id": "rs1",
        "from": SUMMARY,
        "to": {**SUMMARY, "id": "v2", "version": 2},
        "changes": [
            {
                "path": "blocks[key=allowance].amount",
                "kind": "changed",
                "before": "5000",
                "after": "6000",
                "figure": True,
                "source": "law",
            }
        ],
        "sources": {"law": {"id": "law", "url": "https://example.org/law", "title": "Law"}},
        "examples": [],
        "validation_ok": True,
    }
    r = await client.get(f"{BASE}/rs1/diff?to=v2&from=v1", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["from"]["id"] == "v1"
    assert r.json()["changes"][0]["after"] == "6000"
    rules.diff.assert_awaited_once_with("test-user-1", "rs1", "v2", "v1")
    await client.get(f"{BASE}/rs1/diff?to=v2", headers=AUTH)
    assert rules.diff.await_args.args == ("test-user-1", "rs1", "v2", None)


async def test_an_export_is_a_file_s_text(client, rules):
    rules.export.return_value = {
        "filename": "xz-2031-v1.salli-tax.json",
        "content_hash": "a" * 64,
        "canonical": True,
        "text": "{}",
    }
    r = await client.get(f"{BASE}/rs1/versions/v1/export", headers=AUTH)
    assert r.json()["filename"] == "xz-2031-v1.salli-tax.json"


async def test_evaluating_passes_the_answers_and_reports_a_missing_rate(client, rules):
    rules.evaluate.side_effect = RuleSetRateMissing("Salli has no EUR→USD exchange rate")
    r = await client.post(
        f"{BASE}/rs1/versions/v1/evaluate",
        json={"answers": {"status": "joint", "children": "2"}, "year": "2031"},
        headers=AUTH,
    )
    assert (r.status_code, r.json()["type"]) == (422, "/problems/fx-rate-unavailable")
    rules.evaluate.assert_awaited_once_with(
        "test-user-1",
        "v1",
        {"status": "joint", "children": "2"},
        year_label="2031",
        rule_set_id="rs1",
    )


async def test_evaluating_returns_every_line(client, rules):
    rules.evaluate.return_value = {
        "version": SUMMARY,
        "validated": True,
        "country": "XZ",
        "region": None,
        "year": "2031",
        "period_start": "2031-01-01",
        "period_end": "2031-12-31",
        "currency": "EUR",
        "base_currency": "EUR",
        "content_hash": "a" * 64,
        "roles": [
            {"key": "income", "kind": "income", "label": "Income", "total": "25000", "postings": 1}
        ],
        "rates": [],
        "lines": [
            {
                "key": "allowance",
                "label": "Allowance",
                "amount": "5000",
                "expr": "min(5000, max(0, role.income))",
                "source": "law",
                "refundable": None,
            }
        ],
        "net": "3000",
        "net_expr": "line.balance",
        "tax_payable": "3000",
        "refund_due": "0",
        "forms": [{"key": "return", "fields": [{"id": "box_1", "value": "3000"}]}],
        "warnings": [],
        "provenance": "Computed by Salli's engine from rules you or your agent entered.",
    }
    r = await client.post(f"{BASE}/rs1/versions/v1/evaluate", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["lines"][0]["expr"] == "min(5000, max(0, role.income))"
    assert rules.evaluate.await_args.args[2] == {}
