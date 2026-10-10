"""`/v1/tax`: computing from the user's active rules, explaining a line,
preparing a return, and the rule sets' suggested accounts, over HTTP. The
service is faked with what the real one returns (tests/tax_views.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock

from salli.application.services.tax_service import (
    ADD_RULES,
    NoTaxRulesError,
    TaxJurisdiction,
    TaxYearStatus,
)
from salli.domain.taxrules.explain import UnknownLine
from tests.tax_views import active_rules, computation_view
from tests.unit.api.conftest import AUTH

USER = "test-user-1"


async def test_compute_takes_the_jurisdiction_year_and_answers_as_given(client, mock_services):
    mock_services.tax.compute_tax.return_value = computation_view()

    r = await client.post(
        "/v1/tax/compute",
        params={"country": "XZ", "year": "2031"},
        json={"answers": {"status": "single"}},
        headers=AUTH,
    )

    assert r.status_code == 200
    mock_services.tax.compute_tax.assert_awaited_once_with(
        USER, country="XZ", region=None, year="2031", answers={"status": "single"}
    )
    body = r.json()
    assert (body["rule_set_version_id"], body["version"]) == ("version-2", 2)
    assert body["content_hash"] == computation_view()["content_hash"]
    assert (body["net"], body["tax_payable"], body["refund_due"]) == ("3000.00", "3000.00", "0.00")
    assert [line["key"] for line in body["lines"]][:2] == ["allowance", "allowance.remaining"]
    assert body["lines"][0]["expr"] == "min(5000, max(0, role.income))"
    assert "doesn't vouch" in body["provenance"]


async def test_without_a_body_or_a_year_the_service_derives_them(client, mock_services):
    mock_services.tax.compute_tax.return_value = computation_view()
    assert (await client.post("/v1/tax/compute", headers=AUTH)).status_code == 200
    mock_services.tax.compute_tax.assert_awaited_once_with(
        USER, country=None, region=None, year=None, answers={}
    )


async def test_no_active_rules_is_a_problem_that_says_what_to_do(client, mock_services):
    mock_services.tax.compute_tax.side_effect = NoTaxRulesError(
        "no_rule_set", "You have no tax rules for the United Kingdom. " + ADD_RULES
    )

    r = await client.post("/v1/tax/compute", headers=AUTH)

    assert r.status_code == 422
    body = r.json()
    assert (body["type"], body["title"]) == ("/problems/no-tax-rules", "No active tax rules")
    assert "salli tax rules create <file>" in body["detail"]
    assert "research_tax_rules" in body["detail"]


async def test_latest_is_null_until_computed_then_the_stored_one(client, mock_services):
    mock_services.tax.get_latest_computation.return_value = None
    assert (await client.get("/v1/tax/latest", headers=AUTH)).json() == {"result": None}

    mock_services.tax.get_latest_computation.return_value = computation_view()
    r = await client.get("/v1/tax/latest", params={"year": "2031"}, headers=AUTH)
    assert r.json()["result"]["id"] == "computation-1"
    assert mock_services.tax.get_latest_computation.await_args.kwargs == {
        "country": None,
        "region": None,
        "year": "2031",
    }


async def test_the_current_year_is_the_active_rules_covering_today(client, mock_services):
    rules = active_rules()
    mock_services.tax.status = AsyncMock(
        return_value=TaxYearStatus(
            TaxJurisdiction("XZ", None, "given", "GB", "EUR"), current=rules, latest=rules
        )
    )

    r = await client.get("/v1/tax/current-year", params={"country": "XZ"}, headers=AUTH)

    assert r.json() == {
        "country": "XZ",
        "country_source": "given",
        "year": "2031",
        "region": None,
        "start": "2031-01-01",
        "end": "2031-12-31",
        "rule_set_id": "rule-set-1",
        "rule_set_version_id": "version-2",
        "version": 2,
        "latest_year": "2031",
        "latest_rule_set_version_id": "version-2",
    }


async def test_without_active_rules_there_is_no_current_year(client, mock_services):
    mock_services.tax.status = AsyncMock(
        return_value=TaxYearStatus(TaxJurisdiction(None, None, None, None, "USD"), None, None)
    )
    body = (await client.get("/v1/tax/current-year", headers=AUTH)).json()
    assert body["country"] is None and body["year"] is None and body["latest_year"] is None


async def test_a_line_is_explained(client, mock_services):
    mock_services.tax.explain.return_value = {
        "country": "XZ",
        "region": None,
        "year": "2031",
        "currency": "EUR",
        "rule_set_id": "rule-set-1",
        "rule_set_version_id": "version-2",
        "version": 2,
        "content_hash": "h",
        "line": {
            "key": "allowance",
            "label": "allowance",
            "amount": "5000",
            "expr": "min(5000, max(0, role.income))",
            "path": "blocks[0]",
            "block": "relief",
            "refundable": None,
            "source": {
                "id": "law",
                "url": "https://example.org/law",
                "title": "A",
                "retrieved": None,
            },
        },
        "inputs": [{"key": "income", "label": "Income", "kind": "income", "total": "25000"}],
        "answers": [],
        "lines": [],
        "tables": [],
        "used_by": ["allowance.remaining"],
        "provenance": "p",
    }

    r = await client.post("/v1/tax/explain", json={"line_key": "allowance"}, headers=AUTH)

    assert r.status_code == 200
    assert r.json()["line"]["source"]["url"] == "https://example.org/law"
    mock_services.tax.explain.assert_awaited_once_with(
        USER, "allowance", country=None, region=None, year=None, answers={}
    )


async def test_explaining_a_line_the_rules_don_t_have_is_not_found(client, mock_services):
    mock_services.tax.explain.side_effect = UnknownLine("nowhere", ["allowance"])
    r = await client.post("/v1/tax/explain", json={"line_key": "nowhere"}, headers=AUTH)
    assert r.status_code == 404
    assert "no line 'nowhere'" in r.json()["detail"]


# ── returns ────────────────────────────────────────────────────────────────────


def _draft() -> dict:
    c = computation_view()
    return {
        "country": c["country"],
        "region": c["region"],
        "year": c["year"],
        "currency": c["currency"],
        "computation_id": c["id"],
        "rule_set_id": c["rule_set_id"],
        "rule_set_version_id": c["rule_set_version_id"],
        "version": c["version"],
        "content_hash": c["content_hash"],
        "net": c["net"],
        "tax_payable": c["tax_payable"],
        "refund_due": c["refund_due"],
        "lines": c["lines"],
        "answers": {},
        "forms": [
            {
                "key": "return",
                "label": "Annual return",
                "instructions": "Enter each box.",
                "url": "https://example.org/file",
                "fields": [{"id": "box_1", "label": "Tax", "value": "3000"}],
            }
        ],
        "warnings": [],
        "note": "n",
        "provenance": "p",
    }


async def test_preparing_a_return_holds_the_draft_under_the_users_thread(client, mock_services):
    mock_services.agent.prepare_return.return_value = {
        "thread_id": "t1",
        "draft_return": _draft(),
        "error": "",
    }

    r = await client.post(
        "/v1/tax/returns/prepare", json={"thread_id": "t1", "year": "2031"}, headers=AUTH
    )

    assert r.status_code == 200
    body = r.json()
    assert body["thread_id"] == "t1" and body["error"] == ""
    assert body["draft"]["forms"][0]["fields"] == [{"id": "box_1", "label": "Tax", "value": "3000"}]
    mock_services.agent.prepare_return.assert_awaited_once_with(
        USER, year="2031", country=None, region=None, answers={}, thread_id="t1"
    )


async def test_a_return_that_can_t_be_prepared_says_why(client, mock_services):
    mock_services.agent.prepare_return.return_value = {
        "thread_id": "t1",
        "draft_return": {},
        "error": "Your rules define no return form",
    }
    body = (await client.post("/v1/tax/returns/prepare", json={}, headers=AUTH)).json()
    assert body["draft"] is None and "no return form" in body["error"]


async def test_the_draft_waiting_on_a_thread_is_read_back(client, mock_services):
    mock_services.agent.get_return.return_value = {
        "thread_id": "t1",
        "waiting": True,
        "draft_return": _draft(),
    }
    body = (await client.get("/v1/tax/returns/t1", headers=AUTH)).json()
    assert body["waiting"] is True and body["draft"]["computation_id"] == "computation-1"
    mock_services.agent.get_return.assert_awaited_once_with(USER, "t1")

    mock_services.agent.get_return.return_value = {
        "thread_id": "t2",
        "waiting": False,
        "draft_return": {},
    }
    body = (await client.get("/v1/tax/returns/t2", headers=AUTH)).json()
    assert body == {"thread_id": "t2", "waiting": False, "draft": None}


async def test_resuming_a_return_needs_a_signed_in_user(client, mock_services):
    r = await client.post("/v1/tax/returns/resume", json={"thread_id": "t1", "decision": "approve"})
    assert r.status_code == 401
    mock_services.agent.resume_return.assert_not_awaited()


async def test_an_approved_return_is_the_worksheet(client, mock_services):
    mock_services.agent.resume_return.return_value = {
        "worksheet": {**_draft(), "status": "ready_to_file"},
        "draft_return": {},
        "error": "",
    }

    r = await client.post(
        "/v1/tax/returns/resume", json={"thread_id": "t1", "decision": "approve"}, headers=AUTH
    )

    body = r.json()
    assert body["worksheet"]["status"] == "ready_to_file" and body["draft"] is None
    mock_services.agent.resume_return.assert_awaited_once_with(
        user_id=USER, thread_id="t1", decision="approve", answers={}
    )


async def test_an_edit_comes_back_as_a_new_draft(client, mock_services):
    mock_services.agent.resume_return.return_value = {
        "worksheet": {},
        "draft_return": _draft(),
        "error": "",
    }
    r = await client.post(
        "/v1/tax/returns/resume",
        json={"thread_id": "t1", "decision": "edit", "answers": {"status": "joint"}},
        headers=AUTH,
    )
    body = r.json()
    assert body["worksheet"] is None and body["draft"]["year"] == "2031"
    assert mock_services.agent.resume_return.await_args.kwargs["answers"] == {"status": "joint"}


async def test_only_the_three_decisions_are_accepted(client, mock_services):
    r = await client.post(
        "/v1/tax/returns/resume", json={"thread_id": "t1", "decision": "file"}, headers=AUTH
    )
    assert r.status_code == 422
    mock_services.agent.resume_return.assert_not_awaited()


# ── suggested accounts ─────────────────────────────────────────────────────────


_SUGGESTED = {
    "rule_set_id": "rs",
    "version_id": "v",
    "version": 1,
    "applied": False,
    "accounts": [
        {
            "code": "1450",
            "name": "Tax withheld",
            "type": "asset",
            "tax_role": "withheld",
            "status": "missing",
            "account_id": None,
            "note": None,
        }
    ],
}


async def test_suggested_accounts_are_listed_then_applied(client, mock_services):
    mock_services.tax_rules = AsyncMock()
    mock_services.tax_rules.suggested_accounts.return_value = _SUGGESTED

    r = await client.get("/v1/tax/rule-sets/rs/suggested-accounts", headers=AUTH)
    assert r.json()["accounts"][0]["status"] == "missing"
    assert mock_services.tax_rules.suggested_accounts.await_args.kwargs == {"version_id": None}

    mock_services.tax_rules.suggested_accounts.return_value = {
        **_SUGGESTED,
        "applied": True,
        "accounts": [{**_SUGGESTED["accounts"][0], "status": "created", "account_id": "a1"}],
    }
    r = await client.post("/v1/tax/rule-sets/rs/suggested-accounts", headers=AUTH)
    assert r.json()["applied"] is True
    assert mock_services.tax_rules.suggested_accounts.await_args.kwargs == {
        "version_id": None,
        "apply": True,
    }


# ── what's gone ────────────────────────────────────────────────────────────────


async def test_the_built_in_packs_are_gone(client):
    assert (await client.get("/v1/tax/packs", headers=AUTH)).status_code in (404, 405)
    meta = (await client.get("/v1/meta")).json()
    assert "tax_packs" not in meta


async def test_refreshing_filing_reminders_reports_what_changed(client, mock_services):
    mock_services.reminders = AsyncMock()
    mock_services.reminders.seed_filing_calendar.return_value = {
        "created": ["r1"],
        "updated": ["r2"],
        "removed": [],
    }
    r = await client.post("/v1/reminders/seed", headers=AUTH)
    assert r.json() == {"created": 1, "ids": ["r1"], "updated": ["r2"], "removed": []}
    mock_services.reminders.seed_filing_calendar.assert_awaited_once_with(USER, None)
