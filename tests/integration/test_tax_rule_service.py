"""TaxRuleService against a real database: the lifecycle, activation's lock and
permission, review, sharing, evaluation from a ledger, and that no user can
reach another's rules."""

from __future__ import annotations

import asyncio
import hashlib
import json
from decimal import Decimal

import pytest

from salli.application.permissions import Actor
from salli.application.ports import FetchedDocument, FetchRefused, FxQuote, FxUnavailableError
from salli.application.services.ledger_service import LedgerService, UnknownTaxRoleError
from salli.application.services.tax_rule_service import (
    RuleSetConflict,
    RuleSetDocumentError,
    RuleSetInputError,
    RuleSetNotFound,
    RuleSetPermissionError,
    RuleSetRateMissing,
    RuleSetStateError,
    TaxRuleService,
)
from salli.domain.accounting.models import Direction
from tests.integration.pg import requires_postgres, scalar
from tests.taxrules.documents import minimal

pytestmark = requires_postgres

A, B = "user-a", "user-b"
ME = Actor.signed_in(A, "session")
CLI = Actor.signed_in(A, "oauth", first_party_client=True, name="Salli CLI")
AGENT = Actor.signed_in(A, "mcp", name="Claude")
INTRUDER = Actor.signed_in(B, "session")


class _Fx:
    def __init__(self, rates: dict[tuple[str, str, str], str] | None = None) -> None:
        self.rates = rates or {}

    async def rate(self, from_currency: str, to_currency: str, on_date: str) -> FxQuote:
        key = (from_currency, to_currency, on_date)
        if key not in self.rates:
            raise FxUnavailableError(f"no rate for {key}")
        return FxQuote(Decimal(self.rates[key]), "test", on_date)


class _Fetcher:
    def __init__(self, text: str | None = None) -> None:
        self.text = text
        self.urls: list[str] = []

    async def fetch_text(self, url: str) -> FetchedDocument:
        self.urls.append(url)
        if self.text is None:
            raise FetchRefused("That address is not on the public internet; refused")
        return FetchedDocument(url, self.text)


@pytest.fixture
async def svc(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(A, {"base_currency": "EUR"})
        await uow.user_profiles.upsert(B, {"base_currency": "EUR"})
    return TaxRuleService(uow_factory, fx=_Fx(), fetcher=_Fetcher(json.dumps(minimal())))


def _failing() -> dict:
    doc = minimal()
    doc["examples"][0]["expected"]["payable"] = "2999"
    return doc


def _broken() -> dict:
    doc = minimal()
    doc["lines"][0]["expr"] = "line.tax - line.nowhere"
    return doc


def _raised() -> dict:
    """The next year's rules: a larger allowance."""
    doc = minimal()
    doc["blocks"][0]["amount"] = "6000"
    doc["examples"][0]["expected"]["payable"] = "2800"
    return doc


async def _salary(uow_factory, user: str, gross: str, withheld: str, day: str = "2031-03-31"):
    ledger = LedgerService(uow_factory)
    accounts = {a.code: a.id for a in await ledger.list_accounts(user)}
    if not accounts:
        accounts = {
            "1000": await ledger.add_account(user, "1000", "Bank", "asset"),
            "4000": await ledger.add_account(user, "4000", "Salary", "income", tax_role="income"),
            "1450": await ledger.add_account(
                user, "1450", "Withheld", "asset", tax_role="withheld"
            ),
        }
    net = str(Decimal(gross) - Decimal(withheld))
    await ledger.add_entry(
        user,
        day,
        "Salary",
        "manual",
        [
            {
                "account_id": accounts["1000"],
                "direction": Direction.DEBIT,
                "amount": Decimal(net),
                "currency": "EUR",
            },
            {
                "account_id": accounts["1450"],
                "direction": Direction.DEBIT,
                "amount": Decimal(withheld),
                "currency": "EUR",
            },
            {
                "account_id": accounts["4000"],
                "direction": Direction.CREDIT,
                "amount": Decimal(gross),
                "currency": "EUR",
            },
        ],
    )


# ── storing ───────────────────────────────────────────────────────────────────


async def test_every_document_is_stored_with_the_status_its_report_earns(svc):
    passing = await svc.create(ME, json.dumps(minimal()))
    assert passing["status"] == "validated" and passing["version"] == 1
    assert passing["validation"]["ok"] is True
    assert passing["author_kind"] == "user"

    failing = await svc.new_version(AGENT, passing["rule_set_id"], _failing(), note="try 2999")
    assert failing["status"] == "draft" and failing["version"] == 2
    [example] = failing["validation"]["examples"]
    assert (
        example["mismatches"][0]["message"]
        == "payable: expected 2999, got 3000 (from line.balance)"
    )
    assert (failing["author_kind"], failing["author_name"]) == ("agent", "Claude")

    broken = await svc.new_version(AGENT, passing["rule_set_id"], _broken())
    assert broken["status"] == "invalid" and broken["content_hash"] is not None
    assert "Unknown line: line.nowhere" in broken["validation"]["errors"][0]["message"]


async def test_what_can_t_be_stored_is_refused_with_its_problems(svc):
    with pytest.raises(RuleSetDocumentError) as raised:
        await svc.create(ME, "{not json")
    assert "Not valid JSON" in raised.value.problems[0].message
    with pytest.raises(RuleSetDocumentError):
        await svc.create(ME, "[1, 2]")
    with pytest.raises(RuleSetDocumentError):
        await svc.create(ME, '{"a": 1, "a": 2}')
    with pytest.raises(RuleSetDocumentError) as raised:
        await svc.create(ME, '{"x": "' + "a" * 1_100_000 + '"}')
    assert "larger than 1048576 bytes" in raised.value.problems[0].message
    nameless = minimal()
    del nameless["jurisdiction"]
    with pytest.raises(RuleSetDocumentError, match="jurisdiction and year") as raised:
        await svc.create(ME, nameless)
    assert raised.value.problems[0].path.startswith("jurisdiction")
    assert await svc.list_rule_sets(A) == []


async def test_one_rule_set_per_jurisdiction_and_year(svc):
    first = await svc.create(ME, minimal())
    with pytest.raises(RuleSetConflict) as raised:
        await svc.create(ME, minimal())
    assert raised.value.rule_set_id == first["rule_set_id"]
    # A draft goes into the existing set instead.
    drafted = await svc.draft(AGENT, _raised())
    assert (drafted["rule_set_id"], drafted["version"]) == (first["rule_set_id"], 2)


async def test_a_version_must_be_for_its_set_s_jurisdiction_and_year(svc):
    first = await svc.create(ME, minimal())
    other = minimal()
    other["year"] = {"label": "2032", "start": "2032-01-01", "end": "2032-12-31"}
    with pytest.raises(RuleSetDocumentError, match="for XZ 2032, but the rule set is for XZ 2031"):
        await svc.new_version(ME, first["rule_set_id"], other)


# ── the lifecycle ─────────────────────────────────────────────────────────────


async def test_proposing_needs_every_example_to_pass_and_keeps_the_fresh_report(svc):
    first = await svc.create(ME, minimal())
    draft = await svc.new_version(AGENT, first["rule_set_id"], _failing())
    with pytest.raises(RuleSetStateError, match="worked examples don't match: Basic"):
        await svc.propose(AGENT, draft["id"])
    proposed = await svc.propose(AGENT, first["id"])
    assert proposed["status"] == "proposed" and proposed["proposed_at"] is not None


async def test_only_the_user_s_own_sign_in_can_activate(svc):
    first = await svc.create(AGENT, minimal())
    await svc.propose(AGENT, first["id"])
    with pytest.raises(RuleSetPermissionError, match="never activate"):
        await svc.activate(AGENT, first["id"])
    assert (await svc.get_version(A, first["id"]))["status"] == "proposed"
    active = await svc.activate(CLI, first["id"])
    assert active["status"] == "active"


async def test_activating_supersedes_the_active_version_and_is_audited(db, svc):
    first = await svc.create(ME, minimal())
    await svc.activate(ME, first["id"])
    second = await svc.new_version(AGENT, first["rule_set_id"], _raised(), note="2031 budget")
    activated = await svc.activate(ME, second["id"], first["rule_set_id"])
    assert activated["status"] == "active"
    old = await svc.get_version(A, first["id"])
    assert old["status"] == "superseded" and old["superseded_at"] is not None
    assert (await svc.get(A, first["rule_set_id"]))["active_version_id"] == second["id"]
    # Again is a no-op; a superseded version can't come back.
    assert (await svc.activate(ME, second["id"]))["status"] == "active"
    with pytest.raises(RuleSetStateError, match="superseded"):
        await svc.activate(ME, first["id"])
    assert scalar(db, "select count(*) from audit_logs where action = 'activate_tax_rule_set'") == 2


async def test_a_version_that_fails_validation_is_never_activated(svc):
    first = await svc.create(ME, minimal())
    draft = await svc.new_version(ME, first["rule_set_id"], _failing())
    with pytest.raises(RuleSetStateError, match="can't be activated"):
        await svc.activate(ME, draft["id"])
    assert (await svc.get(A, first["rule_set_id"]))["active_version_id"] is None


async def test_concurrent_activations_leave_exactly_one_active_version(svc):
    first = await svc.create(ME, minimal())
    second = await svc.new_version(ME, first["rule_set_id"], _raised())
    third = await svc.new_version(ME, first["rule_set_id"], minimal())
    await asyncio.gather(*(svc.activate(ME, v["id"]) for v in (first, second, third)))
    rule_set = await svc.get(A, first["rule_set_id"])
    statuses = [v["status"] for v in rule_set["versions"]]
    assert statuses.count("active") == 1
    assert statuses.count("superseded") == 2
    active = next(v for v in rule_set["versions"] if v["status"] == "active")
    assert rule_set["active_version_id"] == active["id"]


async def test_validating_again_moves_a_draft_but_keeps_history_as_it_was(svc):
    first = await svc.create(ME, minimal())
    await svc.activate(ME, first["id"])
    revalidated = await svc.validate(AGENT, first["id"])
    assert revalidated["status"] == "active"
    assert revalidated["validation"]["ok"] is True


# ── review and sharing ────────────────────────────────────────────────────────


async def test_the_diff_shows_changed_figures_with_their_sources_against_the_active_version(svc):
    first = await svc.create(ME, minimal())
    await svc.activate(ME, first["id"])
    second = await svc.new_version(AGENT, first["rule_set_id"], _raised())
    diff = await svc.diff(A, first["rule_set_id"], second["id"])
    assert diff["from"]["id"] == first["id"]
    figures = {c["path"]: c for c in diff["changes"] if c["figure"]}
    allowance = figures["blocks[key=allowance].amount"]
    assert (allowance["before"], allowance["after"], allowance["source"]) == ("5000", "6000", "law")
    assert diff["sources"]["law"]["url"] == "https://example.org/law"
    assert diff["examples"][0]["passed"] is True


async def test_an_export_is_canonical_json_whose_hash_is_the_content_hash(svc):
    first = await svc.create(ME, json.dumps(minimal(), indent=4))
    exported = await svc.export(A, first["id"])
    assert exported["canonical"] is True
    assert exported["filename"] == "xz-2031-v1.salli-tax.json"
    assert hashlib.sha256(exported["text"].encode()).hexdigest() == first["content_hash"]
    # Re-importing the export changes nothing about the rules.
    again = await svc.import_document(ME, exported["text"])
    assert again["content_hash"] == first["content_hash"]


async def test_an_import_lands_as_a_draft_even_when_it_passes(svc):
    imported = await svc.import_document(AGENT, minimal())
    assert imported["status"] == "draft" and imported["validation"]["ok"] is True
    assert imported["change_note"] == "Imported"
    validated = await svc.validate(ME, imported["id"])
    assert validated["status"] == "validated"


async def test_a_url_import_goes_through_the_fetcher_and_lands_as_a_draft(uow_factory, svc):
    fetched = await svc.import_url(ME, "https://rules.example/xz.json")
    assert fetched["status"] == "draft"
    assert fetched["change_note"] == "Imported from https://rules.example/xz.json"
    refusing = TaxRuleService(uow_factory, fetcher=_Fetcher(None))
    with pytest.raises(FetchRefused, match="public internet"):
        await refusing.import_url(ME, "https://10.0.0.1/xz.json")


# ── evaluating from the ledger ────────────────────────────────────────────────


async def test_evaluating_adds_up_the_user_s_roles_and_runs_every_line(db, uow_factory, svc):
    first = await svc.create(ME, minimal())  # its roles can now go on accounts
    await _salary(uow_factory, A, "25000", "1000")
    await _salary(uow_factory, A, "999", "0.01", day="2030-12-31")  # another year
    before = scalar(db, "select count(*) from tax_computations")
    result = await svc.evaluate(A, first["id"])
    roles = {r["key"]: r["total"] for r in result["roles"]}
    assert roles == {"income": "25000", "withheld": "1000"}
    lines = {line["key"]: line["amount"] for line in result["lines"]}
    assert lines["allowance.remaining"] == "20000"
    assert (result["tax_payable"], result["net"]) == ("2000", "2000")  # 3000 − 1000 withheld
    assert result["validated"] is True and result["warnings"] == []
    assert "doesn't vouch" in result["provenance"]
    # Read-only.
    assert scalar(db, "select count(*) from tax_computations") == before


async def test_evaluating_in_another_currency_converts_at_each_entry_s_date(uow_factory):
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(A, {"base_currency": "EUR"})
    usd = minimal()
    usd["currency"] = "USD"
    usd["examples"][0]["expected"] = {"payable": "3000"}
    svc = TaxRuleService(uow_factory, fx=_Fx({("EUR", "USD", "2031-03-31"): "1.1"}))
    first = await svc.create(ME, usd)
    await _salary(uow_factory, A, "25000", "1000")
    result = await svc.evaluate(A, first["id"])
    assert {r["key"]: r["total"] for r in result["roles"]} == {
        "income": "27500",
        "withheld": "1100",
    }
    assert result["rates"] == [{"date": "2031-03-31", "rate": "1.1", "source": "test"}]

    without = TaxRuleService(uow_factory, fx=_Fx())
    with pytest.raises(RuleSetRateMissing, match="no EUR→USD exchange rate for 2031-03-31"):
        await without.evaluate(A, first["id"])


async def test_evaluating_refuses_what_doesn_t_fit(svc):
    first = await svc.create(ME, minimal())
    with pytest.raises(RuleSetInputError, match="for 2031, not 2030"):
        await svc.evaluate(A, first["id"], year_label="2030")
    with pytest.raises(RuleSetInputError, match="not a question"):
        await svc.evaluate(A, first["id"], {"filing_status": "single"})
    broken = await svc.new_version(ME, first["rule_set_id"], _broken())
    with pytest.raises(RuleSetStateError, match="doesn't compile"):
        await svc.evaluate(A, broken["id"])


async def test_a_role_declared_by_the_user_s_rule_set_may_go_on_their_accounts(uow_factory, svc):
    ledger = LedgerService(uow_factory)
    with pytest.raises(UnknownTaxRoleError):
        await ledger.add_account(A, "4000", "Salary", "income", tax_role="income")
    await svc.create(AGENT, _failing())  # a draft is enough to set accounts up
    await ledger.add_account(A, "4000", "Salary", "income", tax_role="income")
    # Not on anyone else's.
    with pytest.raises(UnknownTaxRoleError):
        await ledger.add_account(B, "4000", "Salary", "income", tax_role="income")


# ── nothing of one user's reaches another ─────────────────────────────────────


async def test_another_user_can_reach_none_of_a_user_s_rule_sets(uow_factory, svc):
    first = await svc.create(ME, minimal())
    await _salary(uow_factory, A, "25000", "1000")
    set_id, version_id = first["rule_set_id"], first["id"]
    second = await svc.new_version(ME, set_id, _raised())

    assert await svc.list_rule_sets(B) == []
    attempts = {
        "read": svc.get(B, set_id),
        "read a version": svc.get_version(B, version_id),
        "read a version through its set": svc.get_version(B, version_id, set_id),
        "version": svc.new_version(INTRUDER, set_id, minimal()),
        "draft into": svc.draft(INTRUDER, minimal(), rule_set_id=set_id),
        "validate": svc.validate(INTRUDER, version_id),
        "propose": svc.propose(INTRUDER, version_id),
        "activate": svc.activate(INTRUDER, version_id),
        "activate through the set": svc.activate(INTRUDER, version_id, set_id),
        "diff": svc.diff(B, set_id, second["id"], version_id),
        "export": svc.export(B, version_id),
        "evaluate": svc.evaluate(B, version_id),
    }
    for what, attempt in attempts.items():
        with pytest.raises(RuleSetNotFound):
            await attempt
            pytest.fail(f"user B could {what} user A's rule set")

    # Nor by pairing their own set with A's version.
    mine = await svc.create(INTRUDER, minimal())
    for attempt in (
        svc.get_version(B, version_id, mine["rule_set_id"]),
        svc.diff(B, mine["rule_set_id"], mine["id"], version_id),
        svc.diff(B, mine["rule_set_id"], version_id),
        svc.activate(INTRUDER, version_id, mine["rule_set_id"]),
    ):
        with pytest.raises(RuleSetNotFound):
            await attempt

    # A's rules are as A left them.
    untouched = await svc.get(A, set_id)
    assert [v["status"] for v in untouched["versions"]] == ["validated", "validated"]
    assert untouched["active_version_id"] is None
    # And B's own import made B's own set, not a version of A's.
    assert mine["rule_set_id"] != set_id
