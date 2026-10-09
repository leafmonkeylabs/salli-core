"""
The profile, onboarding and data-portability routes answer with the shapes
their services build — the web and mobile apps read them — and the models
describing them say exactly that: same fields, same JSON types.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi.encoders import jsonable_encoder

from salli.application.services.data_portability_service import DataPortabilityService
from salli.domain.accounting.models import Account, Direction, Posting, StoredJournalEntry
from salli.domain.risk import engine as risk_engine
from salli.domain.risk.models import RiskQuestionnaireAnswers
from salli.interfaces.api.routers.onboarding import RiskBreakdown

from .conftest import AUTH

USER = "test-user-1"


def _profile_row() -> dict[str, Any]:
    """What UserProfileService.get_profile returns for a profile row."""
    return {
        "id": USER,
        "email": "me@example.com",
        "display_name": "Ama",
        "base_currency": "USD",
        "date_of_birth": "1990-04-01",
        "dependents_count": 2,
        "employment_status": "employed",
        "residency_status": "resident",
        "employer": "Acme",
        "employment_type": "permanent",
        "ird_number": None,
        "risk_score": 58,
        "risk_category": "balanced",
        "life_stage": "family",
        "mcp_enabled": False,
        "daily_briefing_enabled": True,
        "preferred_model": None,
        "tax_residency": None,
        "tax_ids": [],
        "nic": None,
    }


# ── Profile ───────────────────────────────────────────────────────────────────


async def test_the_profile_is_the_stored_row(client, mock_services):
    mock_services.profile.get_profile.return_value = _profile_row()
    r = await client.get("/v1/onboarding/profile", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == _profile_row()


async def test_a_profile_that_is_not_there_is_not_found(client, mock_services):
    """With no row the service answers a bare {"id": ...}: not a profile, and
    not something to pass off as one with every field missing."""
    mock_services.profile.get_profile.return_value = {"id": USER}
    r = await client.get("/v1/onboarding/profile", headers=AUTH)
    assert r.status_code == 404


async def test_updating_the_profile_says_so(client, mock_services):
    r = await client.patch("/v1/onboarding/profile", json={"employer": "Acme"}, headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"updated": True}


async def test_the_profile_carries_the_tax_identity_and_the_fields_it_replaced(
    client, mock_services
):
    """The web and mobile apps read `ird_number` and `nic`; they stay, derived
    from the tax ids."""
    row = {
        **_profile_row(),
        "tax_residency": "LK",
        "tax_ids": [
            {"scheme": "LK-TIN", "value": "123456789"},
            {"scheme": "LK-NIC", "value": "200012345678"},
        ],
        "ird_number": "123456789",
        "nic": "200012345678",
    }
    mock_services.profile.get_profile.return_value = row
    body = (await client.get("/v1/onboarding/profile", headers=AUTH)).json()
    assert body == row


async def test_the_tax_identity_is_updated_through_the_profile(client, mock_services):
    r = await client.patch(
        "/v1/onboarding/profile",
        json={
            "tax_residency": "GB",
            "tax_ids": [{"scheme": "GB-UTR", "value": "1234567890"}],
            "nic": "200012345678",
        },
        headers=AUTH,
    )
    assert r.status_code == 200
    mock_services.profile.update_identity.assert_awaited_once_with(
        "test-user-1",
        {
            "tax_residency": "GB",
            "tax_ids": [{"scheme": "GB-UTR", "value": "1234567890"}],
            "nic": "200012345678",
        },
    )


async def test_an_explicit_null_clears_the_residency_and_an_omitted_one_does_not(
    client, mock_services
):
    await client.patch("/v1/onboarding/profile", json={"tax_residency": None}, headers=AUTH)
    assert mock_services.profile.update_identity.await_args.args[1] == {"tax_residency": None}

    await client.patch("/v1/onboarding/profile", json={"employer": "Acme"}, headers=AUTH)
    assert mock_services.profile.update_identity.await_args.args[1] == {"employer": "Acme"}


async def test_a_malformed_country_or_scheme_is_a_422(client, mock_services):
    for body in (
        {"tax_residency": "Sri Lanka"},
        {"tax_residency": "lk"},
        {"tax_ids": [{"scheme": "TIN", "value": "1"}]},
        {"tax_ids": [{"scheme": "lk-tin", "value": "1"}]},
        {"tax_ids": [{"scheme": "LK-TIN", "value": ""}]},
    ):
        r = await client.patch("/v1/onboarding/profile", json=body, headers=AUTH)
        assert r.status_code == 422, body
    mock_services.profile.update_identity.assert_not_awaited()


# ── Onboarding steps ──────────────────────────────────────────────────────────


async def test_completing_onboarding_reports_what_it_saved_and_opened(client, mock_services):
    result = {
        "memories_saved": ["onboarding_complete", "user_name", "residency_status"],
        "accounts_created": ["1100 Cash", "1200 Bank Account"],
        "accounts_skipped": ["3000"],
    }
    mock_services.onboarding = AsyncMock()
    mock_services.onboarding.complete.return_value = result
    r = await client.post("/v1/onboarding/complete", json={"name": "Ama"}, headers=AUTH)
    assert r.status_code == 200
    assert r.json() == result


async def test_declarations_return_the_entries_they_posted(client, mock_services):
    mock_services.profile.declare_opening_balances.return_value = ["e-1", "e-2"]
    mock_services.profile.declare_income.return_value = ["e-3"]

    balances = await client.post(
        "/v1/onboarding/balance-sheet",
        json={"balances": [{"code": "1200", "name": "Bank", "type": "asset", "amount": "10"}]},
        headers=AUTH,
    )
    income = await client.post(
        "/v1/onboarding/income",
        json={"incomes": [{"code": "4100", "name": "Salary", "amount": "5000"}]},
        headers=AUTH,
    )

    assert balances.json() == {"entries_created": ["e-1", "e-2"]}
    assert income.json() == {"entries_created": ["e-3"]}


async def test_declared_goals_return_their_ids(client, mock_services):
    mock_services.fi.create_goal.side_effect = ["g-1", "g-2"]
    r = await client.post(
        "/v1/onboarding/goals",
        json={"goals": [{"name": "House"}, {"name": "Car"}]},
        headers=AUTH,
    )
    assert r.status_code == 201
    assert r.json() == {"goal_ids": ["g-1", "g-2"]}


def _scored(answers: RiskQuestionnaireAnswers) -> dict[str, Any]:
    """What UserProfileService.submit_risk_questionnaire returns."""
    profile = risk_engine.compute(answers)
    return {"score": profile.score, "category": profile.category, "breakdown": profile.breakdown}


async def test_the_risk_questionnaire_returns_the_engines_score(client, mock_services):
    answers = RiskQuestionnaireAnswers(
        time_horizon_years=12,
        drawdown_reaction="hold",
        income_stability="stable",
        investment_experience="some",
        dependents_count=1,
    )
    mock_services.profile.submit_risk_questionnaire.return_value = _scored(answers)
    r = await client.post(
        "/v1/onboarding/risk-questionnaire",
        json={
            "time_horizon_years": 12,
            "drawdown_reaction": "hold",
            "income_stability": "stable",
            "investment_experience": "some",
            "dependents_count": 1,
        },
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json() == _scored(answers)


def test_the_breakdown_model_names_every_dimension_the_engine_scores():
    """A dimension the engine adds must reach clients rather than be dropped
    by a model that does not know it."""
    answers = RiskQuestionnaireAnswers(
        time_horizon_years=1,
        drawdown_reaction="sell_all",
        income_stability="unstable",
        investment_experience="none",
    )
    assert set(risk_engine.compute(answers).breakdown) == set(RiskBreakdown.model_fields)


# ── Data portability ─────────────────────────────────────────────────────────


def _portability_service(exporters=()) -> DataPortabilityService:
    """The real service over fakes that return what the real services do."""
    profile, ledger, tax = AsyncMock(), AsyncMock(), AsyncMock()
    budget, debt, portfolio, subscription = AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock()
    insurance, fi, advisor, documents, reminders = (AsyncMock() for _ in range(5))

    profile.get_profile.return_value = _profile_row()
    ledger.list_accounts.return_value = [
        Account(id="a-1", user_id=USER, code="1200", name="Bank", type="asset", currency="USD"),
        Account(id="a-2", user_id=USER, code="4100", name="Salary", type="income", currency="USD"),
    ]
    ledger.get_entries.return_value = [
        StoredJournalEntry(
            id="e-1",
            user_id=USER,
            entry_date="2026-01-15",
            description="Salary",
            source="manual",
            postings=[
                Posting(
                    account_id="a-1",
                    direction=Direction.DEBIT,
                    amount=Decimal("1234.50"),
                    currency="USD",
                ),
                Posting(
                    account_id="a-2",
                    direction=Direction.CREDIT,
                    amount=Decimal("1234.50"),
                    currency="USD",
                ),
            ],
        )
    ]
    tax.get_latest_computation.return_value = {"pack_version": "1", "tax_payable": "0.00"}
    budget.list_budgets.return_value = [
        {
            "id": "b-1",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "currency": "USD",
            "lines": [{"account_id": "a-1", "limit_amount": "500.00"}],
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    debt.list_debts.return_value = []
    portfolio.list_holdings.return_value = []
    subscription.list_subscriptions.return_value = []
    insurance.list_policies.return_value = []
    insurance.list_targets.return_value = []
    fi.list_goals.return_value = [{"id": "g-1", "progress": 0.4567, "target_amount": "100.00"}]
    fi.get_score_history.return_value = [
        {"score": 61.5, "net_worth": "1234.50", "created_at": "2026-01-02T00:00:00+00:00"}
    ]
    advisor.list_reports.return_value = []
    reminders.list_reminders.return_value = []
    documents.list_documents.return_value = []
    return DataPortabilityService(
        MagicMock(),
        profile,
        ledger,
        tax,
        budget,
        debt,
        portfolio,
        subscription,
        insurance,
        fi,
        advisor,
        documents,
        reminders,
        exporters=exporters,
    )


async def _bug_reports(user_id: str) -> dict[str, Any]:
    """An extension's section, holding values JSON has no type for."""
    return {
        "bug_reports": [
            {
                "id": "r-1",
                "created_at": datetime.datetime(2026, 10, 9, 8, 30, tzinfo=datetime.UTC),
                "estimate": Decimal("1.50"),
            }
        ]
    }


async def test_the_export_is_the_document_the_service_builds(client, mock_services):
    service = _portability_service([_bug_reports])
    expected = jsonable_encoder(await service.export_all(USER))
    mock_services.data_portability = service

    r = await client.get("/v1/onboarding/export", headers=AUTH)

    assert r.status_code == 200
    assert r.json() == expected
    assert list(r.json())[-1] == "bug_reports"


async def test_an_extensions_section_is_encoded_as_it_always_was(client, mock_services):
    """The model cannot see an extension's values, so they keep the encoding
    they had before the export had a model: a datetime keeps "+00:00" and a
    Decimal stays a JSON number."""
    mock_services.data_portability = _portability_service([_bug_reports])

    r = await client.get("/v1/onboarding/export", headers=AUTH)

    assert r.json()["bug_reports"] == [
        {"id": "r-1", "created_at": "2026-10-09T08:30:00+00:00", "estimate": 1.5}
    ]


async def test_exported_postings_keep_amounts_as_decimal_strings(client, mock_services):
    mock_services.data_portability = _portability_service()
    r = await client.get("/v1/onboarding/export", headers=AUTH)
    postings = r.json()["journal_entries"][0]["postings"]
    assert postings[0] == {
        "account_id": "a-1",
        "direction": "DEBIT",
        "amount": "1234.50",
        "currency": "USD",
        # With what reproduces its base amount, and its tags.
        "fx_rate": "1",
        "fx_rate_source": None,
        "tags": {},
    }


async def test_deleting_the_account_reports_what_went(client, app, mock_services):
    from salli.interfaces.api.deps import get_current_email

    app.dependency_overrides[get_current_email] = lambda: "me@example.com"
    mock_services.data_portability = AsyncMock()
    mock_services.data_portability.delete_account.return_value = {"accounts": 2, "budgets": 0}

    r = await client.request(
        "DELETE",
        "/v1/onboarding/account",
        json={"confirm_email": "Me@Example.com"},
        headers=AUTH,
    )

    assert r.status_code == 200
    assert r.json() == {"deleted": True, "counts": {"accounts": 2, "budgets": 0}}


async def test_the_export_keeps_closed_accounts_and_every_tax_year():
    service = _portability_service()
    document = await service.export_all(USER)
    # Entries refer to closed accounts too, so they must be in the document.
    service._ledger.list_accounts.assert_awaited_with(USER, include_inactive=True)
    assert "tax_role" in document["accounts"][0]
    years = {call.args[1] for call in service._tax.get_latest_computation.await_args_list}
    assert "2025/26" in years and isinstance(document["tax_computations"], list)
