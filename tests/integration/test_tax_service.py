"""TaxService against a real database: the user's tax, computed only from the
rule set they activated, stored reproducibly, explained line by line, prepared
as a return, with filing reminders and suggested accounts from the same rules.

Every rule set here is a fictional jurisdiction from the conformance suite
(tests/taxrules/conformance/): Remitland (XG), whose year runs April to March,
in KWD (three decimals)."""

from __future__ import annotations

import copy
import datetime
import json
import pathlib
from decimal import Decimal
from typing import Any

import pytest

from salli.application.permissions import Actor
from salli.application.services.ledger_service import LedgerService
from salli.application.services.reminder_service import ReminderService
from salli.application.services.tax_rule_service import RuleSetStateError, TaxRuleService
from salli.application.services.tax_service import NoTaxRulesError, TaxService
from salli.domain.accounting.models import Direction
from salli.domain.taxrules.explain import UnknownLine
from tests.integration.pg import _sync, requires_postgres, scalar

pytestmark = requires_postgres

A, B = "user-a", "user-b"
ME = Actor.signed_in(A, "session")
AGENT = Actor.signed_in(A, "mcp", name="Claude")
TODAY = datetime.date(2031, 10, 10)  # in Remitland's 2031/32

CONFORMANCE = pathlib.Path(__file__).resolve().parents[1] / "taxrules" / "conformance"


def remitland(**changes: Any) -> dict[str, Any]:
    doc = json.loads((CONFORMANCE / "remitland.json").read_text())
    doc["forms"][0]["instructions"] = "Sign in to the Remitland portal and enter each box."
    doc["forms"][0]["url"] = "https://example.org/remitland/file"
    doc.update(changes)
    return doc


def next_year(doc: dict[str, Any]) -> dict[str, Any]:
    later = copy.deepcopy(doc)
    later["year"] = {"label": "2032/33", "start": "2032-04-01", "end": "2033-03-31"}
    later["deadlines"] = [{"key": "return", "label": "Return due", "date": "2033-09-30"}]
    return later


@pytest.fixture
async def rules(uow_factory) -> TaxRuleService:
    async with uow_factory() as uow:
        await uow.user_profiles.upsert(A, {"base_currency": "KWD", "tax_residency": "GB"})
        await uow.user_profiles.upsert(B, {"base_currency": "KWD"})
    return TaxRuleService(uow_factory)


@pytest.fixture
def tax(uow_factory, rules) -> TaxService:
    return TaxService(uow_factory, rules, clock=lambda: TODAY)


async def _activate(rules: TaxRuleService, doc: dict[str, Any]) -> dict[str, Any]:
    version = await rules.draft(ME, doc)
    return await rules.activate(ME, version["id"])


async def _book(
    uow_factory, user: str, *, local: str, withheld: str = "0", day: str = "2031-06-30"
) -> None:
    """Salary into the bank, some of it withheld, on accounts with Remitland's roles."""
    ledger = LedgerService(uow_factory)
    codes = {a.code: a.id for a in await ledger.list_accounts(user)}
    if "1000" not in codes:
        codes["1000"] = await ledger.add_account(user, "1000", "Bank", "asset")
        codes["4000"] = await ledger.add_account(
            user, "4000", "Salary", "income", tax_role="local_income"
        )
        codes["1450"] = await ledger.add_account(
            user, "1450", "Tax withheld", "asset", tax_role="tax_withheld"
        )
    postings = [
        {"account_id": codes["4000"], "direction": Direction.CREDIT, "amount": Decimal(local)},
        {
            "account_id": codes["1000"],
            "direction": Direction.DEBIT,
            "amount": Decimal(local) - Decimal(withheld),
        },
    ]
    if withheld != "0":
        postings.append(
            {"account_id": codes["1450"], "direction": Direction.DEBIT, "amount": Decimal(withheld)}
        )
    await ledger.add_entry(
        user, day, "Salary", "manual", [{**p, "currency": "KWD"} for p in postings]
    )


# ── whose rules ───────────────────────────────────────────────────────────────


async def test_without_a_residency_or_a_country_there_is_nothing_to_compute(tax):
    with pytest.raises(NoTaxRulesError) as raised:
        await tax.compute_tax(B)
    assert raised.value.reason == "no_residency"
    assert "Set your tax residency" in str(raised.value)
    assert "salli tax rules create" in str(raised.value)
    assert "research_tax_rules" in str(raised.value)


async def test_the_country_is_the_residency_never_the_currency(tax, rules):
    # A rule set in the user's base currency, for a country they don't live in.
    await _activate(rules, remitland())
    with pytest.raises(NoTaxRulesError) as raised:
        await tax.compute_tax(A)  # resident in GB: XG's rules don't apply
    assert raised.value.reason == "no_rule_set"
    assert "no tax rules for the United Kingdom" in str(raised.value)
    # Named, they do.
    assert (await tax.compute_tax(A, country="xg"))["country"] == "XG"


async def test_rules_that_aren_t_active_are_named_with_what_to_do(tax, rules):
    await rules.draft(AGENT, remitland())
    with pytest.raises(NoTaxRulesError, match="none is active yet") as raised:
        await tax.compute_tax(A, country="XG", year="2031/32")
    assert raised.value.reason == "not_active"
    assert "salli tax rules activate" in str(raised.value)


async def test_the_current_year_is_the_active_rules_covering_today(tax, rules):
    status = await tax.status(A, country="XG")
    assert (status.current, status.latest) == (None, None)

    this_year = await _activate(rules, remitland())
    status = await tax.status(A, country="XG")
    assert status.current is not None and status.current.year == "2031/32"
    assert status.current.version["id"] == this_year["id"]

    # Once the year is over and next year's rules are in, the year moves on;
    # between them, computing uses the latest year that has begun.
    later = TaxService(tax._uow_factory, rules, clock=lambda: datetime.date(2032, 5, 1))
    status = await later.status(A, country="XG")
    assert status.current is None and status.latest is not None
    assert status.latest.year == "2031/32"
    await _activate(rules, next_year(remitland()))
    status = await later.status(A, country="XG")
    assert status.current is not None and status.current.year == "2032/33"
    # Today (2031) the 2032/33 rules haven't begun: still this year.
    assert (await tax.resolve(A, country="XG")).year == "2031/32"


async def test_rules_only_for_a_year_that_hasn_t_begun_need_the_year_named(tax, rules):
    await _activate(rules, next_year(remitland()))
    with pytest.raises(NoTaxRulesError, match="haven't begun") as raised:
        await tax.compute_tax(A, country="XG")
    assert raised.value.reason == "no_year"
    assert (await tax.compute_tax(A, country="XG", year="2032/33"))["year"] == "2032/33"


async def test_with_regional_rules_the_region_is_asked_for(tax, rules):
    north = remitland()
    north["jurisdiction"] = {"country": "XG", "region": "North"}
    south = remitland()
    south["jurisdiction"] = {"country": "XG", "region": "South"}
    await _activate(rules, north)
    await _activate(rules, south)
    with pytest.raises(NoTaxRulesError, match=r"more than one region .*North, South"):
        await tax.compute_tax(A, country="XG")
    assert (await tax.compute_tax(A, country="XG", region="South"))["region"] == "South"
    # National rules, once there are some, are the default.
    await _activate(rules, remitland())
    assert (await tax.compute_tax(A, country="XG"))["region"] is None


# ── computing and storing ─────────────────────────────────────────────────────


async def test_a_computation_records_its_version_hash_lines_and_amounts(
    db, uow_factory, tax, rules
):
    version = await _activate(rules, remitland())
    await _book(uow_factory, A, local="20000", withheld="2000")

    c = await tax.compute_tax(A, country="XG")

    assert (c["rule_set_version_id"], c["version"]) == (version["id"], 1)
    assert c["content_hash"] == version["content_hash"]
    assert {r["key"]: r["total"] for r in c["roles"]}["local_income"] == "20000"
    lines = {line["key"]: line for line in c["lines"]}
    assert lines["local_tax.band_2.tax"]["amount"] == "750"
    assert lines["relief"]["source"] == "act"
    # 1,250 of tax less 2,000 withheld: 750 back, in KWD's three decimals.
    assert (c["net"], c["tax_payable"], c["refund_due"]) == ("-750.000", "0.000", "750.000")
    assert c["currency"] == "KWD" and "doesn't vouch" in c["provenance"]

    row = scalar(
        db,
        "select net_minor || ' ' || tax_payable_minor || ' ' || refund_due_minor || ' ' || currency"
        " from tax_computations",
    )
    assert row == "-750000 0 750000 KWD"
    assert (await tax.get_latest_computation(A, country="XG"))["id"] == c["id"]


async def test_previewing_stores_nothing(db, uow_factory, tax, rules):
    await _activate(rules, remitland())
    preview = await tax.compute_tax(A, country="XG", persist=False)
    assert preview["id"] is None
    assert scalar(db, "select count(*) from tax_computations") == 0
    assert await tax.get_latest_computation(A, country="XG") is None


async def test_a_net_finer_than_the_currency_is_stored_rounded_and_said_so(uow_factory, tax, rules):
    doc = remitland()
    del doc["result"]["round"]
    doc["band_tables"]["local"].pop("round")
    doc["examples"] = [e for e in doc["examples"] if "local_income" not in e["inputs"]]
    await _activate(rules, doc)
    await _book(uow_factory, A, local="5000.123")  # 0.123 × 5% = 0.00615

    c = await tax.compute_tax(A, country="XG")

    assert c["tax_payable"] == "0.006"
    assert any("finer than KWD's smallest unit" in w for w in c["warnings"])


async def test_a_stored_computation_reproduces_from_its_own_version(db, uow_factory, tax, rules):
    """However the rules and the ledger change later, re-evaluating the exact
    version a computation recorded, with its inputs, gives the same lines."""
    first = await _activate(rules, remitland())
    await _book(uow_factory, A, local="20000")
    old = await tax.compute_tax(A, country="XG")

    raised = remitland()
    raised["blocks"][1]["amount"] = "6000"  # a bigger relief…
    raised["examples"] = raised["examples"][:1]
    await _activate(rules, raised)
    await _book(uow_factory, A, local="5000", day="2031-09-30")  # …and more income
    new = await tax.compute_tax(A, country="XG")
    assert new["version"] == 2 and new["tax_payable"] != old["tax_payable"]

    again = await tax.reproduce(A, old["id"])
    assert again == {
        "computation_id": old["id"],
        "rule_set_version_id": first["id"],
        "content_hash": first["content_hash"],
        "reproduced": True,
        "differences": [],
    }

    # A row that no longer matches its version is caught, figure by figure.
    engine = __import__("sqlalchemy").create_engine(_sync(db))
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "update tax_computations set lines = jsonb_set(lines, '{0,amount}', '\"1\"'),"
            " net_minor = net_minor + 1, tax_payable_minor = tax_payable_minor + 1"
            f" where id = '{old['id']}'"
        )
    engine.dispose()
    tampered = await tax.reproduce(A, old["id"])
    assert tampered["reproduced"] is False
    assert tampered["differences"][0].startswith("line foreign_tax: stored 1, now 0")
    assert any(d.startswith("net:") for d in tampered["differences"])

    with pytest.raises(KeyError):
        await tax.reproduce(B, old["id"])


async def test_recomputing_stored_results_reports_then_applies_what_moved(uow_factory, tax, rules):
    await _activate(rules, remitland())
    await _book(uow_factory, A, local="20000")
    stored = await tax.compute_tax(A, country="XG")
    await _book(uow_factory, A, local="10000", day="2031-09-30")

    [dry] = await tax.recompute_stored(apply=False)
    assert (dry["old_tax_payable"], dry["new_tax_payable"]) == ("1250.000", "2750.000")
    assert dry["changed"] and not dry["applied"] and dry["reproduces"]
    assert (await tax.get_latest_computation(A, country="XG"))["id"] == stored["id"]

    [applied] = await tax.recompute_stored(apply=True)
    assert applied["applied"]
    latest = await tax.get_latest_computation(A, country="XG")
    assert latest["tax_payable"] == "2750.000"

    [settled] = await tax.recompute_stored(apply=True)
    assert not settled["changed"] and not settled["applied"]


async def test_no_user_reaches_another_s_rules_or_computations(uow_factory, tax, rules):
    await _activate(rules, remitland())
    mine = await tax.compute_tax(A, country="XG")
    with pytest.raises(NoTaxRulesError):
        await tax.compute_tax(B, country="XG")
    assert await tax.get_computation(B, mine["id"]) is None
    assert await tax.list_computations(B) == []


# ── explanations ──────────────────────────────────────────────────────────────


async def test_a_line_is_explained_from_the_rules_and_the_result(uow_factory, tax, rules):
    await _activate(rules, remitland())
    await _book(uow_factory, A, local="20000")

    e = await tax.explain(A, "local_tax.band_2.tax", country="XG")

    assert (e["line"]["amount"], e["line"]["block"]) == ("750", "schedule")
    assert e["line"]["expr"] == 'round(line.local_tax.band_2.amount * 0.15, "nearest", 0.001)'
    [used] = e["lines"]
    assert (used["key"], used["amount"]) == ("local_tax.band_2.amount", "5000")
    assert e["used_by"] == ["local_tax"]

    amount = await tax.explain(A, "local_tax.band_2.amount", country="XG")
    assert amount["line"]["expr"] == 'band_amount(line.relief.remaining, "local", 2)'
    assert [(ln["key"], ln["amount"]) for ln in amount["lines"]] == [("relief.remaining", "15000")]
    [table] = amount["tables"]
    assert table["key"] == "local" and table["bands"][1] == {"upto": "30000", "rate": "0.15"}
    assert table["source"]["url"] == "https://example.org/remitland/income-tax-act"

    relief = await tax.explain(A, "relief", country="XG")
    assert relief["inputs"] == [
        {"key": "local_income", "label": "Local income", "kind": "income", "total": "20000"}
    ]
    assert relief["line"]["source"]["title"] == "Remitland Income Tax Act (fictional)"

    with pytest.raises(UnknownLine, match="no line 'band_1'"):
        await tax.explain(A, "band_1", country="XG")


# ── returns ───────────────────────────────────────────────────────────────────


async def test_a_return_is_the_rules_forms_filled_in_from_a_stored_computation(
    db, uow_factory, tax, rules
):
    await _activate(rules, remitland())
    await _book(uow_factory, A, local="20000")

    prepared = await tax.prepare_return(A, country="XG")

    assert prepared["error"] == ""
    [form] = prepared["forms"]
    assert form["url"] == "https://example.org/remitland/file"
    assert form["instructions"].startswith("Sign in to the Remitland portal")
    assert {f["id"]: f["value"] for f in form["fields"]} == {
        "local": "15000",
        "foreign": "0",
        "ftc": "0",
    }
    assert prepared["computation"]["id"] is not None
    assert scalar(db, "select count(*) from tax_computations") == 1


async def test_rules_without_forms_prepare_no_return(uow_factory, tax, rules):
    await _activate(rules, remitland(forms=[]))
    prepared = await tax.prepare_return(A, country="XG")
    assert "define no return form" in prepared["error"]
    nothing = await tax.prepare_return(B)
    assert "Set your tax residency" in nothing["error"]


# ── filing reminders ──────────────────────────────────────────────────────────


def _deadlines(db) -> list[tuple[str, str, str]]:
    engine = __import__("sqlalchemy").create_engine(_sync(db))
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "select kind, due_date, status from reminders where source_domain = 'tax_rules'"
            " order by due_date"
        ).all()
    engine.dispose()
    return [tuple(r) for r in rows]


async def test_activating_seeds_the_rules_deadlines_and_replaces_the_superseded_ones(
    db, uow_factory, rules
):
    first = await _activate(rules, remitland())
    assert _deadlines(db) == [("Return due (XG 2031/32)", "2032-09-30", "pending")]

    reminders = ReminderService(uow_factory)
    [mine] = await reminders.list_reminders(A)
    await reminders.mark_done(A, mine["id"])

    # The same deadline survives a new version, done; a moved one goes back to
    # pending; a new one is added; a dropped one is removed.
    second = remitland()
    second["deadlines"].append({"key": "payment", "label": "Payment due", "date": "2032-10-31"})
    await rules.activate(ME, (await rules.new_version(ME, first["rule_set_id"], second))["id"])
    assert _deadlines(db) == [
        ("Return due (XG 2031/32)", "2032-09-30", "done"),
        ("Payment due (XG 2031/32)", "2032-10-31", "pending"),
    ]
    third = remitland()
    third["deadlines"] = [{"key": "return", "label": "Return due", "date": "2032-08-31"}]
    await rules.activate(ME, (await rules.new_version(ME, first["rule_set_id"], third))["id"])
    assert _deadlines(db) == [("Return due (XG 2031/32)", "2032-08-31", "pending")]

    # A refresh on demand changes nothing more; reminders the user made stay.
    await reminders.create_reminder(A, "Gather statements", "2032-05-01")
    assert await reminders.seed_filing_calendar(A) == {
        "created": [],
        "updated": [],
        "removed": [],
    }
    assert len(await reminders.list_reminders(A)) == 2
    assert await reminders.list_reminders(B) == []


# ── suggested accounts ────────────────────────────────────────────────────────


async def test_suggested_accounts_are_shown_then_created_once(uow_factory, rules):
    first = await _activate(rules, remitland())
    ledger = LedgerService(uow_factory)
    await ledger.add_account(A, "1490", "Overseas tax", "asset")  # code taken, no role

    preview = await rules.suggested_accounts(ME, first["rule_set_id"])
    assert preview["applied"] is False and preview["version_id"] == first["id"]
    assert [(a["code"], a["status"]) for a in preview["accounts"]] == [
        ("4600", "missing"),
        ("1490", "exists"),
    ]
    assert "left as it is" in preview["accounts"][1]["note"]
    assert len(await ledger.list_accounts(A)) == 1

    applied = await rules.suggested_accounts(AGENT, first["rule_set_id"], apply=True)
    assert [(a["code"], a["status"]) for a in applied["accounts"]] == [
        ("4600", "created"),
        ("1490", "exists"),
    ]
    created = {a.code: a for a in await ledger.list_accounts(A)}["4600"]
    assert (created.tax_role, created.currency, created.type) == ("foreign_income", "KWD", "income")

    again = await rules.suggested_accounts(ME, first["rule_set_id"], apply=True)
    assert {a["status"] for a in again["accounts"]} == {"exists"}
    assert len(await ledger.list_accounts(A)) == 2


async def test_a_superseded_version_suggests_nothing(rules):
    first = await _activate(rules, remitland())
    second = await rules.new_version(
        ME, first["rule_set_id"], remitland(sources=remitland()["sources"])
    )
    await rules.activate(ME, second["id"])
    with pytest.raises(RuleSetStateError, match="superseded"):
        await rules.suggested_accounts(ME, first["rule_set_id"], version_id=first["id"])


# ── tax roles no rule set declares any more ───────────────────────────────────


async def test_a_role_left_on_accounts_by_a_superseded_version_is_a_warning(uow_factory, rules):
    first = await _activate(rules, remitland())
    await _book(uow_factory, A, local="1000", withheld="10")  # 1450 carries tax_withheld

    renamed = remitland()
    renamed["roles"][3]["key"] = "withheld"
    renamed["blocks"][4]["of"] = "role.withheld"
    renamed["examples"] = [
        {
            **e,
            "inputs": {
                ("withheld" if k == "tax_withheld" else k): v for k, v in e["inputs"].items()
            },
        }
        for e in renamed["examples"]
    ]
    draft = await rules.new_version(ME, first["rule_set_id"], renamed)
    # While the old version is active, the role is still declared.
    assert not [w for w in draft["validation"]["warnings"] if w["path"] == "roles"]

    activated = await rules.activate(ME, draft["id"])
    assert activated["status"] == "active"  # a warning, never a refusal
    [warning] = [w for w in activated["validation"]["warnings"] if w["path"] == "roles"]
    assert "Account 1450 carries the tax role 'tax_withheld'" in warning["message"]
    assert "none of your rule sets in use declares any more" in warning["message"]
    # Validating again says it again.
    revalidated = await rules.validate(ME, draft["id"])
    assert [w for w in revalidated["validation"]["warnings"] if w["path"] == "roles"]
