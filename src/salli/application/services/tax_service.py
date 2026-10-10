"""
TaxService: a user's tax, computed by Salli's engine from the rule set they
activated (docs/taxrules.md). No country's law is built in.

**Whose rules.** The jurisdiction is the country asked for, or the user's tax
residency (on their profile): never inferred from their currency. Within it,
the rules are the user's *active* rule set for the year:

- the year asked for; or, with none,
- the year of their active rule set whose dates contain today (the current
  tax year); or, when today is in no such year (the year has ended and the
  next one's rules aren't in yet, say), the latest year whose active rules have
  begun;
- in a country with rule sets per region, the one asked for; without one, the
  national rule set (no region) or the only one there is.

Anything missing (no residency, no rule set, none active) is a
`NoTaxRulesError` that says what to do about it.

**Computing.** The active version's rules are applied to the ledger by
TaxRuleService.apply (each role's total from the accounts carrying it, within
the year). A stored computation records the version and its content hash, the
inputs the engine was given and every line, so it can be reproduced exactly
(`reproduce`) whatever the rules or the ledger say since. The amounts owed are
money: kept in minor units of the rules' currency.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

from salli.application.services.tax_rule_service import (
    PROVENANCE,
    Applied,
    TaxRuleError,
    TaxRuleService,
    form_rows,
    line_rows,
)
from salli.domain.currency import normalize_currency
from salli.domain.jurisdiction import COUNTRIES, UnknownCountryError, country_phrase
from salli.domain.money import from_minor, to_minor
from salli.domain.secrets import error_label
from salli.domain.taxrules.arith import normalized_str
from salli.domain.taxrules.common import is_user_assigned_country
from salli.domain.taxrules.engine import compile_rule_set
from salli.domain.taxrules.engine import evaluate as evaluate_rules
from salli.domain.taxrules.explain import LineExplanation, explain_line
from salli.domain.taxrules.expr import Value
from salli.domain.taxrules.schema import RuleSet, answer_value

#: What to do about having no rules to compute with, in every surface's words.
ADD_RULES = (
    "Add your tax rules with `salli tax rules create <file>` or "
    "`salli tax rules import <file|url>`, or ask your AI agent to research them "
    "(its `research_tax_rules` prompt drafts a rule set for you to review); then "
    "activate them yourself with `salli tax rules activate <set>`."
)

Reason = Literal["no_residency", "no_rule_set", "not_active", "no_year", "ambiguous"]


class NoTaxRulesError(LookupError):
    """Salli has no active rules to compute this user's tax with. `reason` says
    which part is missing; the message says what to do."""

    def __init__(self, reason: Reason, message: str) -> None:
        super().__init__(message)
        self.reason: Reason = reason


@dataclass(frozen=True)
class TaxJurisdiction:
    """Whose rules compute a user's tax, and why."""

    #: The country, or None when Salli can't tell.
    country: str | None
    region: str | None
    #: "given" when the caller named it, "tax_residency" when it is the
    #: user's; None with neither.
    source: Literal["given", "tax_residency"] | None
    tax_residency: str | None
    base_currency: str | None


@dataclass(frozen=True)
class ActiveRules:
    """One active rule set version, and the year it covers."""

    rule_set: Mapping[str, Any]
    version: Mapping[str, Any]
    document: RuleSet

    @property
    def country(self) -> str:
        return self.document.jurisdiction.country

    @property
    def region(self) -> str | None:
        return self.document.jurisdiction.region

    @property
    def year(self) -> str:
        return self.document.year.label

    @property
    def start(self) -> datetime.date:
        return self.document.year.start

    @property
    def end(self) -> datetime.date:
        return self.document.year.end

    def covers(self, day: datetime.date) -> bool:
        return self.start <= day <= self.end


@dataclass(frozen=True)
class TaxYearStatus:
    """Where a user stands today: their current tax year (the year of the
    active rule set whose dates contain today, or none) and the year a
    computation uses when none is named."""

    jurisdiction: TaxJurisdiction
    #: The active rules for today, or None.
    current: ActiveRules | None
    #: What /tax/compute uses with no year: today's, else the latest active
    #: year that has begun. None when there is none.
    latest: ActiveRules | None


def tax_country(code: str) -> str:
    """A country a caller names for tax: an ISO 3166-1 alpha-2 code, or a
    user-assigned one (`XA`…) such as a fictional jurisdiction's rule set
    uses. UnknownCountryError otherwise."""
    normalized = code.strip().upper()
    if normalized in COUNTRIES or is_user_assigned_country(normalized):
        return normalized
    raise UnknownCountryError(f"{code!r} is not an ISO 3166-1 alpha-2 country code")


def _label(country: str, region: str | None, year: str | None = None) -> str:
    place = f"{country_phrase(country)} ({region})" if region else country_phrase(country)
    return f"{place} for {year}" if year else place


def _amount(minor: int, currency: str) -> str:
    return str(from_minor(minor, currency))


class TaxService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        rules: TaxRuleService,
        clock: Callable[[], datetime.date] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._rules = rules
        self._today = clock or datetime.date.today

    # ── Whose tax, which year ────────────────────────────────────────────────

    async def jurisdiction(
        self, user_id: str, country: str | None = None, region: str | None = None
    ) -> TaxJurisdiction:
        async with self._uow_factory() as uow:
            profile: Mapping[str, Any] = await uow.user_profiles.get(user_id) or {}
        residency: str | None = profile.get("tax_residency") or None
        base: str | None = profile.get("base_currency") or None
        if country:
            return TaxJurisdiction(tax_country(country), region, "given", residency, base)
        if residency:
            return TaxJurisdiction(residency, region, "tax_residency", residency, base)
        return TaxJurisdiction(None, region, None, None, base)

    async def _active(self, user_id: str, country: str) -> list[ActiveRules]:
        async with self._uow_factory() as uow:
            rows = await uow.tax_rule_sets.active_versions(user_id)
        found: list[ActiveRules] = []
        for row in rows:
            if row["country"] != country:
                continue
            found.append(
                ActiveRules(row, row["version"], RuleSet.model_validate(row["version"]["content"]))
            )
        return found

    @staticmethod
    def _pick_region(
        candidates: list[ActiveRules], region: str | None, where: str
    ) -> ActiveRules | None:
        if region is not None:
            matched = [c for c in candidates if c.region == region]
            return matched[0] if matched else None
        if len(candidates) <= 1:
            return candidates[0] if candidates else None
        national = [c for c in candidates if c.region is None]
        if len(national) == 1:
            return national[0]
        regions = ", ".join(sorted(c.region or "(national)" for c in candidates))
        raise NoTaxRulesError(
            "ambiguous",
            f"You have active rules for more than one region of {where} ({regions}): say which "
            "region to compute.",
        )

    async def status(
        self,
        user_id: str,
        *,
        country: str | None = None,
        region: str | None = None,
        today: datetime.date | None = None,
    ) -> TaxYearStatus:
        """The user's current tax year and the year a computation defaults to,
        in their country (or the one named)."""
        today = today or self._today()
        where = await self.jurisdiction(user_id, country, region)
        if where.country is None:
            return TaxYearStatus(where, None, None)
        actives = await self._active(user_id, where.country)
        if region is not None:
            actives = [a for a in actives if a.region == region]
        place = _label(where.country, region)

        def pick(candidates: list[ActiveRules]) -> ActiveRules | None:
            try:
                return self._pick_region(candidates, region, place)
            except NoTaxRulesError:
                return None

        current = pick([a for a in actives if a.covers(today)])
        begun = [a for a in actives if a.start <= today]
        latest = current
        if latest is None and begun:
            newest = max(a.start for a in begun)
            latest = pick([a for a in begun if a.start == newest])
        return TaxYearStatus(where, current, latest)

    async def resolve(
        self,
        user_id: str,
        *,
        country: str | None = None,
        region: str | None = None,
        year: str | None = None,
        today: datetime.date | None = None,
    ) -> ActiveRules:
        """The active rules that compute this user's tax for `year` (or the
        derived year) in `country` (or their residency): see the module
        docstring. NoTaxRulesError, saying what to do, when there are none."""
        today = today or self._today()
        where = await self.jurisdiction(user_id, country, region)
        if where.country is None:
            raise NoTaxRulesError(
                "no_residency",
                "Salli doesn't know where you're taxed. Set your tax residency "
                "(`salli profile set --tax-residency <country>`), or name the country. "
                + ADD_RULES,
            )
        actives = await self._active(user_id, where.country)
        place = _label(where.country, region)
        if year:
            chosen = self._pick_region([a for a in actives if a.year == year], region, place)
            if chosen is None:
                raise await self._missing(user_id, where.country, region, year)
            return chosen
        candidates = [a for a in actives if region is None or a.region == region]
        current = self._pick_region([a for a in candidates if a.covers(today)], region, place)
        if current is not None:
            return current
        begun = [a for a in candidates if a.start <= today]
        if begun:
            newest = max(a.start for a in begun)
            chosen = self._pick_region([a for a in begun if a.start == newest], region, place)
            if chosen is not None:
                return chosen
        if candidates:
            raise NoTaxRulesError(
                "no_year",
                f"Your active tax rules for {place} are for years that haven't begun "
                f"({', '.join(sorted(a.year for a in candidates))}): name the year to compute.",
            )
        raise await self._missing(user_id, where.country, region, None)

    async def _missing(
        self, user_id: str, country: str, region: str | None, year: str | None
    ) -> NoTaxRulesError:
        """Why there are no active rules: none at all, or some not activated."""
        async with self._uow_factory() as uow:
            sets = await uow.tax_rule_sets.list_sets(user_id)
        ours = [
            s
            for s in sets
            if s["country"] == country
            and (region is None or s["region"] == region)
            and (year is None or s["year_label"] == year)
        ]
        what = _label(country, region, year)
        if ours:
            names = ", ".join(s["name"] for s in ours)
            return NoTaxRulesError(
                "not_active",
                f"You have tax rules for {what} ({names}), but none is active yet. Review and "
                "activate one yourself: `salli tax rules activate <set>`.",
            )
        return NoTaxRulesError("no_rule_set", f"You have no tax rules for {what}. " + ADD_RULES)

    # ── Computations ─────────────────────────────────────────────────────────

    async def _apply(
        self,
        user_id: str,
        rules: ActiveRules,
        answers: Mapping[str, str | bool] | None,
    ) -> Applied:
        return await self._rules.apply(
            user_id, rules.version["id"], answers, rule_set_id=rules.rule_set["id"]
        )

    async def compute_tax(
        self,
        user_id: str,
        *,
        country: str | None = None,
        region: str | None = None,
        year: str | None = None,
        answers: Mapping[str, str | bool] | None = None,
        persist: bool = True,
    ) -> dict[str, Any]:
        """Compute the user's tax with their active rules (`resolve`) from
        their current ledger and `answers` (the rules' questions, by key), and
        store it unless `persist` is False."""
        view, _ = await self._compute(
            user_id, country=country, region=region, year=year, answers=answers, persist=persist
        )
        return view

    async def _compute(
        self,
        user_id: str,
        *,
        country: str | None,
        region: str | None,
        year: str | None,
        answers: Mapping[str, str | bool] | None,
        persist: bool,
    ) -> tuple[dict[str, Any], Applied]:
        rules = await self.resolve(user_id, country=country, region=region, year=year)
        applied = await self._apply(user_id, rules, answers)
        record = _record(rules, applied)
        if not persist:
            return _view({**record, "id": None, "created_at": None}), applied
        async with self._uow_factory() as uow:
            stored = await uow.tax_computations.save(user_id, record)
        return _view(stored), applied

    async def prepare_return(
        self,
        user_id: str,
        *,
        country: str | None = None,
        region: str | None = None,
        year: str | None = None,
        answers: Mapping[str, str | bool] | None = None,
    ) -> dict[str, Any]:
        """Compute (and store) the user's tax for a return, with each return
        form the active rules define filled in from the result: what the
        return workflow puts in front of the user for review.

        Never raises for what the user can fix: no rules, no forms in them, an
        answer the rules need. Those come back as `error`, in Salli's own
        words (safe to keep in a workflow's checkpoint)."""
        try:
            view, applied = await self._compute(
                user_id, country=country, region=region, year=year, answers=answers, persist=True
            )
        except (NoTaxRulesError, TaxRuleError, LookupError, ValueError) as exc:
            return {"error": str(exc)}
        if not applied.document.forms:
            return {
                "error": (
                    f"Your rules for {_label(view['country'], view['region'], view['year'])} "
                    "define no return form, so there is no return to prepare; the computation "
                    "is stored. Add the authority's form to the rules (`forms`: each field an "
                    "expression over the lines) to prepare returns."
                ),
                "computation": view,
            }
        return {
            "error": "",
            "country": view["country"],
            "region": view["region"],
            "year": view["year"],
            "computation": view,
            "forms": form_rows(applied.compiled, applied.result),
        }

    async def get_latest_computation(
        self,
        user_id: str,
        *,
        country: str | None = None,
        region: str | None = None,
        year: str | None = None,
    ) -> dict[str, Any] | None:
        """The last computation stored for the jurisdiction and year (each as
        given, or derived as `resolve` does); None when there is none."""
        where = await self.jurisdiction(user_id, country, region)
        try:
            rules = await self.resolve(user_id, country=country, region=region, year=year)
        except NoTaxRulesError:
            # The year's rules may be inactive now; what was stored still is.
            if where.country is None or not year:
                raise
            target = (where.country, region, year)
        else:
            target = (rules.country, rules.region, rules.year)
        async with self._uow_factory() as uow:
            stored = await uow.tax_computations.get_latest(user_id, *target)
        return _view(stored) if stored else None

    async def get_computation(self, user_id: str, computation_id: str) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            stored = await uow.tax_computations.get(user_id, computation_id)
        return _view(stored) if stored else None

    async def list_computations(self, user_id: str) -> list[dict[str, Any]]:
        """Every computation of the user's, newest first."""
        async with self._uow_factory() as uow:
            return [_view(c) for c in await uow.tax_computations.list_for_user(user_id)]

    async def reproduce(self, user_id: str, computation_id: str) -> dict[str, Any]:
        """Evaluate a stored computation again: the exact version it recorded,
        with the inputs it recorded. `reproduced` is True when every line and
        the amount owed come out as stored; otherwise `differences` says
        which didn't. KeyError for a computation that isn't the user's."""
        async with self._uow_factory() as uow:
            stored = await uow.tax_computations.get(user_id, computation_id)
        if stored is None:
            raise KeyError(computation_id)
        return await self._reproduce(user_id, stored)

    async def _reproduce(self, user_id: str, stored: Mapping[str, Any]) -> dict[str, Any]:
        version = await self._rules.get_version(user_id, stored["rule_set_version_id"])
        differences: list[str] = []
        if version["content_hash"] != stored["content_hash"]:
            differences.append(
                f"the version's content hash is {version['content_hash']}, not "
                f"{stored['content_hash']}"
            )
        inputs = stored["inputs"]
        compiled = compile_rule_set(version["content"])
        result = evaluate_rules(
            compiled,
            {r["key"]: Decimal(r["total"]) for r in inputs["roles"]},
            dict(inputs.get("answers") or {}),
        )
        fresh = {line["key"]: line["amount"] for line in line_rows(result)}
        kept = {line["key"]: line["amount"] for line in stored["lines"]}
        for key in sorted(fresh.keys() | kept.keys()):
            if fresh.get(key) != kept.get(key):
                differences.append(f"line {key}: stored {kept.get(key)}, now {fresh.get(key)}")
        net_minor = to_minor(result.net, stored["currency"])
        if net_minor != stored["net_minor"]:
            differences.append(
                f"net: stored {_amount(stored['net_minor'], stored['currency'])}, now "
                f"{_amount(net_minor, stored['currency'])}"
            )
        return {
            "computation_id": stored["id"],
            "rule_set_version_id": stored["rule_set_version_id"],
            "content_hash": stored["content_hash"],
            "reproduced": not differences,
            "differences": differences,
        }

    async def recompute_stored(self, *, apply: bool) -> list[dict[str, Any]]:
        """Re-run every user's newest computation for each jurisdiction and
        year with the rules active for it now, against the ledger as it is now
        and the answers it was computed with.

        `/tax/latest` serves what was stored, so a user whose ledger or rules
        changed keeps seeing the old figure until they compute again, and a
        wrong tax figure is exactly what they would act on. Each row also says
        whether the stored computation still reproduces from its own version
        (a check on the engine itself). With `apply`, a computation whose
        figures or version changed is stored afresh; nothing else is written,
        so a second run changes nothing.
        """
        async with self._uow_factory() as uow:
            latest = await uow.tax_computations.latest_of_each()
        report: list[dict[str, Any]] = []
        for stored in latest:
            user_id = stored["user_id"]
            row: dict[str, Any] = {
                "user_id": user_id,
                "country": stored["country"],
                "region": stored["region"],
                "year": stored["year"],
                "old_version": stored["version"],
            }
            try:
                reproduced = await self._reproduce(user_id, stored)
                fresh = await self.compute_tax(
                    user_id,
                    country=stored["country"],
                    region=stored["region"],
                    year=stored["year"],
                    answers=stored["inputs"].get("answers") or {},
                    persist=False,
                )
            except Exception as exc:  # noqa: BLE001 — one bad row must not halt the sweep
                report.append(
                    {
                        **row,
                        "error": str(exc) if isinstance(exc, NoTaxRulesError) else error_label(exc),
                    }
                )
                continue
            old = _view(stored)
            changed = (
                fresh["rule_set_version_id"] != stored["rule_set_version_id"]
                or fresh["net"] != old["net"]
                or [(ln["key"], ln["amount"]) for ln in fresh["lines"]]
                != [(ln["key"], ln["amount"]) for ln in old["lines"]]
            )
            if changed and apply:
                await self.compute_tax(
                    user_id,
                    country=stored["country"],
                    region=stored["region"],
                    year=stored["year"],
                    answers=stored["inputs"].get("answers") or {},
                )
            report.append(
                {
                    **row,
                    "new_version": fresh["version"],
                    "currency": stored["currency"],
                    "old_tax_payable": old["tax_payable"],
                    "new_tax_payable": fresh["tax_payable"],
                    "old_refund_due": old["refund_due"],
                    "new_refund_due": fresh["refund_due"],
                    "reproduces": reproduced["reproduced"],
                    "changed": changed,
                    "applied": bool(changed and apply),
                }
            )
        return report

    # ── Explanations ─────────────────────────────────────────────────────────

    async def explain(
        self,
        user_id: str,
        line_key: str,
        *,
        country: str | None = None,
        region: str | None = None,
        year: str | None = None,
        answers: Mapping[str, str | bool] | None = None,
    ) -> dict[str, Any]:
        """Where one line of the user's tax came from: computed now with their
        active rules (nothing stored), then read off the result. UnknownLine
        (a LookupError) for a key the rules have no line for."""
        rules = await self.resolve(user_id, country=country, region=region, year=year)
        applied = await self._apply(user_id, rules, answers)
        questions = {q.key: q for q in applied.document.questions}
        typed: dict[str, Value] = {
            key: answer_value(questions[key], raw)
            for key, raw in applied.answers.items()
            if key in questions
        }
        explanation = explain_line(
            applied.compiled,
            applied.result,
            line_key,
            roles=applied.totals.totals,
            answers=typed,
        )
        return {
            "country": rules.country,
            "region": rules.region,
            "year": rules.year,
            "currency": applied.document.currency,
            "rule_set_id": rules.rule_set["id"],
            "rule_set_version_id": rules.version["id"],
            "version": rules.version["version"],
            "content_hash": applied.result.content_hash,
            **_explanation(explanation),
            "provenance": PROVENANCE,
        }


# ── shapes ─────────────────────────────────────────────────────────────────────


def _record(rules: ActiveRules, applied: Applied) -> dict[str, Any]:
    """What is stored for a computation."""
    result, doc = applied.result, applied.document
    currency = normalize_currency(doc.currency)
    net_minor = to_minor(result.net, currency)
    warnings = list(applied.warnings)
    if from_minor(net_minor, currency) != result.net:
        warnings.append(
            f"These rules leave the amount owed at {normalized_str(result.net)} {currency}, "
            f"finer than {currency}'s smallest unit, so it is taken as "
            f"{from_minor(abs(net_minor), currency)}. Give the rules a result.round to say how "
            "the authority rounds it."
        )
    return {
        "country": rules.country,
        "region": rules.region,
        "year": rules.year,
        "rule_set_id": rules.rule_set["id"],
        "rule_set_version_id": rules.version["id"],
        "version": rules.version["version"],
        "content_hash": result.content_hash,
        "currency": currency,
        "net_minor": net_minor,
        "tax_payable_minor": max(net_minor, 0),
        "refund_due_minor": max(-net_minor, 0),
        "lines": line_rows(result),
        "inputs": {
            "period_start": doc.year.start.isoformat(),
            "period_end": doc.year.end.isoformat(),
            "base_currency": applied.base_currency,
            "roles": applied.role_rows(),
            "answers": applied.answers,
            "rates": applied.rates,
        },
        "warnings": warnings,
    }


def _view(stored: Mapping[str, Any]) -> dict[str, Any]:
    """A computation as the API, the MCP tools and the agents see it."""
    currency = stored["currency"]
    inputs = stored["inputs"]
    created = stored.get("created_at")
    return {
        "id": stored.get("id"),
        "created_at": created.isoformat() if isinstance(created, datetime.datetime) else created,
        "country": stored["country"],
        "region": stored["region"],
        "year": stored["year"],
        "period_start": inputs["period_start"],
        "period_end": inputs["period_end"],
        "currency": currency,
        "base_currency": inputs["base_currency"],
        "rule_set_id": stored["rule_set_id"],
        "rule_set_version_id": stored["rule_set_version_id"],
        "version": stored["version"],
        "content_hash": stored["content_hash"],
        "roles": inputs["roles"],
        "answers": inputs.get("answers") or {},
        "rates": inputs.get("rates") or [],
        "lines": stored["lines"],
        "net": _amount(stored["net_minor"], currency),
        "tax_payable": _amount(stored["tax_payable_minor"], currency),
        "refund_due": _amount(stored["refund_due_minor"], currency),
        "warnings": stored.get("warnings") or [],
        "provenance": PROVENANCE,
    }


def _explanation(e: LineExplanation) -> dict[str, Any]:
    def source(s: Any) -> dict[str, Any] | None:
        if s is None:
            return None
        return {"id": s.id, "url": s.url, "title": s.title, "retrieved": s.retrieved}

    def value(v: Value) -> str | bool:
        return v if isinstance(v, bool | str) else normalized_str(v)

    return {
        "line": {
            "key": e.key,
            "label": e.label,
            "amount": normalized_str(e.amount),
            "expr": e.expr,
            "path": e.path,
            "block": e.block,
            "refundable": e.refundable,
            "source": source(e.source),
        },
        "inputs": [
            {"key": r.key, "label": r.label, "kind": r.kind, "total": normalized_str(r.amount)}
            for r in e.roles
        ],
        "answers": [
            {"key": a.key, "label": a.label, "value": value(a.value), "default": a.default}
            for a in e.answers
        ],
        "lines": [
            {
                "key": ln.key,
                "label": ln.label,
                "amount": normalized_str(ln.amount),
                "expr": ln.expr,
            }
            for ln in e.lines
        ],
        "tables": [
            {
                "key": t.key,
                "label": t.label,
                "bands": [
                    {
                        "upto": None if upto is None else normalized_str(upto),
                        "rate": normalized_str(rate),
                    }
                    for upto, rate in t.bands
                ],
                "source": source(t.source),
            }
            for t in e.tables
        ],
        "used_by": list(e.used_by),
    }
