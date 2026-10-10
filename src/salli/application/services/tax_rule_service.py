"""
TaxRuleService: a user's own tax rule sets (`salli.tax/1`, docs/taxrules.md),
from a first draft to the version Salli computes with.

A rule set is one jurisdiction's tax for one year, stored as a series of
immutable versions. Each version's lifecycle:

    invalid ─┐
    draft  ──┼─ validate ─▶ validated ─ propose ─▶ proposed ─ activate ─▶ active ─▶ superseded
             └──────────────────────────────────────────────────────────┘

- **invalid**: the document doesn't compile (schema, references, types).
- **draft**: it compiles, but its worked examples are missing or don't all
  pass. Also where every import lands until it is validated.
- **validated**: it compiles and every example passes (`report.ok`).
- **proposed**: an agent (or the user) asks the user to review it.
- **active**: the version Salli computes with for that jurisdiction and year.
  Activating one supersedes the set's previous active version, atomically,
  under a lock on the set.
- **superseded**: was active once; kept, never changed, as history.

Storing is never refused for being wrong: an agent iterating on a draft needs
its mistakes stored and reported. What is refused is anything that isn't a
JSON object, anything over 1 MiB, and a document whose jurisdiction and year
can't be read (a version has to belong to some rule set).

**Only the user activates.** `activate` needs `tax:activate`
(application/permissions.py), which AI connectors and other applications
never hold, and it is checked here, not only at the route, so no other path
can activate. Proposing, validating, diffing and evaluating are open to
agents. Propose and activate re-run validation rather than trusting the stored
report.

Every lookup names the owner. Another user's rule set or version is "not
found", exactly like one that doesn't exist.
"""

from __future__ import annotations

import datetime
import json
import re
from collections.abc import Callable, Mapping
from typing import Any, Literal, cast

from pydantic import ValidationError

from salli.application.fx import rate_to_base
from salli.application.permissions import TAX_ACTIVATE, Actor
from salli.application.ports import (
    DocumentFetcher,
    FetchRefused,
    FxRatePort,
    FxUnavailableError,
    RuleSetExists,
)
from salli.domain.taxrules.arith import normalized_str
from salli.domain.taxrules.common import Problem, RuleSetError
from salli.domain.taxrules.diff import diff_documents
from salli.domain.taxrules.engine import (
    RuleSetEvaluationError,
    RuleSetResult,
    canonical_json,
    compile_rule_set,
    content_hash,
)
from salli.domain.taxrules.engine import evaluate as evaluate_rules
from salli.domain.taxrules.inputs import dates_needing_rates, role_postings, total_roles
from salli.domain.taxrules.schema import Jurisdiction, RuleSet, rule_set_json_schema
from salli.domain.taxrules.validate import (
    MAX_DOCUMENT_BYTES,
    ValidationReport,
    read_json,
)
from salli.domain.taxrules.validate import validate as validate_document

Status = Literal["draft", "validated", "proposed", "active", "superseded", "invalid"]

#: A document as a caller has it: JSON text, or JSON already parsed.
Document = str | Mapping[str, Any]

MAX_NOTE_LENGTH = 2_000

#: What every evaluation says about where its rules came from.
PROVENANCE = (
    "Computed by Salli's engine from rules you or your agent entered. Salli doesn't vouch "
    "for the law: check the rules' sources."
)


# ── errors ─────────────────────────────────────────────────────────────────────


class TaxRuleError(Exception):
    """Base of everything this service refuses."""


class RuleSetNotFound(TaxRuleError, LookupError):
    """No such rule set or version for this user: missing, or someone else's.
    The two are indistinguishable on purpose."""

    def __init__(self, what: str = "Tax rule set") -> None:
        super().__init__(f"{what} not found")


class RuleSetDocumentError(TaxRuleError, ValueError):
    """A document that can't be stored at all, with every problem found."""

    def __init__(self, message: str, problems: list[Problem] | tuple[Problem, ...] = ()) -> None:
        super().__init__(message)
        self.problems = tuple(problems)


class RuleSetInputError(TaxRuleError, ValueError):
    """A request that doesn't fit: an answer the rules don't ask for, a year
    the rules aren't for, a note too long."""

    def __init__(self, message: str, problems: list[Problem] | tuple[Problem, ...] = ()) -> None:
        super().__init__(message)
        self.problems = tuple(problems)


class RuleSetStateError(TaxRuleError, ValueError):
    """Not possible in the version's state: proposing one whose examples fail,
    activating a superseded one, evaluating one that doesn't compile."""


class RuleSetConflict(TaxRuleError, ValueError):
    """The user already has a rule set for this jurisdiction and year."""

    def __init__(self, rule_set_id: str, label: str) -> None:
        super().__init__(
            f"You already have a rule set for {label} ({rule_set_id}): add a version to it instead."
        )
        self.rule_set_id = rule_set_id


class RuleSetPermissionError(TaxRuleError, PermissionError):
    """The caller's sign-in doesn't carry the permission this needs."""


class RuleSetRateMissing(TaxRuleError, LookupError):
    """No exchange rate to convert the ledger into the rule set's currency."""


# ── reports ────────────────────────────────────────────────────────────────────


def _problem(p: Problem) -> dict[str, Any]:
    return {"path": p.path, "message": p.message, "snippet": p.snippet}


def report_json(report: ValidationReport, at: datetime.datetime) -> dict[str, Any]:
    """A validation report as it is stored and served: every figure a
    decimal string."""
    return {
        "ok": report.ok,
        "content_hash": report.content_hash,
        "validated_at": at.isoformat(),
        "errors": [_problem(p) for p in report.errors],
        "warnings": [_problem(p) for p in report.warnings],
        "examples": [
            {
                "name": e.name,
                "passed": e.passed,
                "error": e.error,
                "mismatches": [
                    {
                        "key": m.key,
                        "expected": normalized_str(m.expected),
                        "got": normalized_str(m.got),
                        "expr": m.expr,
                        "message": str(m),
                    }
                    for m in e.mismatches
                ],
            }
            for e in report.examples
        ],
    }


def status_after(report: ValidationReport) -> Status:
    """validated when every example passes; draft when it compiles but its
    examples don't (yet); invalid when it doesn't compile."""
    if report.ok:
        return "validated"
    return "draft" if report.content_hash is not None else "invalid"


def _schema_hash(data: Mapping[str, Any]) -> str | None:
    """The content hash, for a document that matches the schema (even one
    that doesn't compile); None for one that doesn't."""
    try:
        return content_hash(RuleSet.model_validate(data))
    except ValidationError:
        return None


def _label(country: str, region: str | None, year: str) -> str:
    return f"{country} {region} {year}" if region else f"{country} {year}"


_FILENAME_UNSAFE = re.compile(r"[^a-z0-9]+")


def _filename(rule_set: Mapping[str, Any], version: int) -> str:
    parts = [rule_set["country"], rule_set.get("region") or "", rule_set["year_label"]]
    stem = "-".join(_FILENAME_UNSAFE.sub("-", p.lower()).strip("-") for p in parts if p)
    return f"{stem}-v{version}.salli-tax.json"


class _Read:
    """A document read far enough to store: its JSON, and which rule set it
    belongs to."""

    def __init__(self, data: dict[str, Any], country: str, region: str | None, year: str) -> None:
        self.data = data
        self.country = country
        self.region = region
        self.year = year

    @property
    def label(self) -> str:
        return _label(self.country, self.region, self.year)


def read_document(document: Document) -> _Read:
    """Parse `document` and find its jurisdiction and year, or
    RuleSetDocumentError. Nothing else about it is checked here: the rest is
    the validator's, and a wrong document is still stored."""
    if isinstance(document, str):
        data, problems = read_json(document)
        if problems:
            raise RuleSetDocumentError("This is not a rule set Salli can read", problems)
    else:
        try:
            size = len(json.dumps(document, allow_nan=False, ensure_ascii=False).encode("utf-8"))
        except (TypeError, ValueError):
            raise RuleSetDocumentError(
                "This is not a rule set Salli can read",
                [Problem("$", "It is not JSON (a NaN, an infinity, or something JSON can't hold)")],
            ) from None
        if size > MAX_DOCUMENT_BYTES:
            raise RuleSetDocumentError(
                "This is not a rule set Salli can read",
                [Problem("$", f"The document is larger than {MAX_DOCUMENT_BYTES} bytes")],
            )
        data = document
    if not isinstance(data, Mapping):
        raise RuleSetDocumentError(
            "This is not a rule set Salli can read", [Problem("$", "A rule set is a JSON object")]
        )
    data = dict(cast(Mapping[str, Any], data))

    problems: list[Problem] = []
    country = region = year = None
    try:
        jurisdiction = Jurisdiction.model_validate(data.get("jurisdiction"))
        country, region = jurisdiction.country, jurisdiction.region
    except ValidationError as error:
        problems.extend(
            Problem("jurisdiction" + "".join(f".{p}" for p in e["loc"]), e["msg"])
            for e in error.errors(include_url=False)
        )
    raw_year = data.get("year")
    label: object = (
        cast(dict[str, Any], raw_year).get("label") if isinstance(raw_year, dict) else None
    )
    if isinstance(label, str) and 1 <= len(label) <= 32:
        year = label
    else:
        problems.append(Problem("year.label", "is required: what the authority calls the year"))
    if problems or country is None or year is None:
        raise RuleSetDocumentError(
            "Salli files a rule set by its jurisdiction and year, and can't read them here; "
            "fix these, and the rest can be worked on as a draft",
            problems,
        )
    return _Read(data, country, region, year)


# ── the service ───────────────────────────────────────────────────────────────


class TaxRuleService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        fx: FxRatePort | None = None,
        fetcher: DocumentFetcher | None = None,
        clock: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._fx = fx
        self._fetcher = fetcher
        self._now = clock or (lambda: datetime.datetime.now(datetime.UTC))

    # ── reading ──────────────────────────────────────────────────────────────

    @staticmethod
    def schema() -> dict[str, Any]:
        """The rule-set document's JSON Schema (Draft 2020-12)."""
        return rule_set_json_schema()

    async def list_rule_sets(self, user_id: str) -> list[dict[str, Any]]:
        async with self._uow_factory() as uow:
            return await uow.tax_rule_sets.list_sets(user_id)

    async def get(self, user_id: str, rule_set_id: str) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            found = await uow.tax_rule_sets.get_set(user_id, rule_set_id)
        if found is None:
            raise RuleSetNotFound()
        return found

    async def _version(
        self, uow: Any, user_id: str, version_id: str, rule_set_id: str | None
    ) -> dict[str, Any]:
        version = await uow.tax_rule_sets.get_version(user_id, version_id)
        if version is None or (rule_set_id is not None and version["rule_set_id"] != rule_set_id):
            raise RuleSetNotFound("Tax rule set version")
        return version

    async def get_version(
        self, user_id: str, version_id: str, rule_set_id: str | None = None
    ) -> dict[str, Any]:
        """One version, with its document and last validation report."""
        async with self._uow_factory() as uow:
            return await self._version(uow, user_id, version_id, rule_set_id)

    # ── writing ──────────────────────────────────────────────────────────────

    def _check(self, document: Document) -> tuple[_Read, ValidationReport, dict[str, Any]]:
        read = read_document(document)
        report = validate_document(read.data)
        return read, report, report_json(report, self._now())

    @staticmethod
    def _note(note: str | None) -> str | None:
        if note is not None and len(note) > MAX_NOTE_LENGTH:
            raise RuleSetInputError(f"A change note is at most {MAX_NOTE_LENGTH} characters")
        return note or None

    def _fields(
        self,
        actor: Actor,
        read: _Read,
        report: ValidationReport,
        stored: dict[str, Any],
        note: str | None,
        status: Status | None = None,
    ) -> dict[str, Any]:
        return {
            "content": read.data,
            "content_hash": _schema_hash(read.data),
            "status": status or status_after(report),
            "validation": stored,
            "author_kind": actor.kind,
            "author_name": actor.name,
            "change_note": note,
        }

    async def create(
        self, actor: Actor, document: Document, *, note: str | None = None
    ) -> dict[str, Any]:
        """A new rule set, with the document as its first version: stored
        whatever its validation found (the report says what). RuleSetConflict
        when the user already has one for that jurisdiction and year."""
        note = self._note(note)
        read, report, stored = self._check(document)
        async with self._uow_factory() as uow:
            try:
                rule_set = await uow.tax_rule_sets.create_set(
                    actor.user_id, read.country, read.region, read.year, read.label
                )
            except RuleSetExists as exists:
                raise RuleSetConflict(exists.rule_set_id, read.label) from None
            version = await uow.tax_rule_sets.add_version(
                actor.user_id, rule_set["id"], self._fields(actor, read, report, stored, note)
            )
        return version

    async def new_version(
        self,
        actor: Actor,
        rule_set_id: str,
        document: Document,
        *,
        note: str | None = None,
    ) -> dict[str, Any]:
        """A new version of one of the user's rule sets. Its jurisdiction and
        year must be the set's."""
        note = self._note(note)
        read, report, stored = self._check(document)
        async with self._uow_factory() as uow:
            rule_set = await uow.tax_rule_sets.get_set(actor.user_id, rule_set_id, lock=True)
            if rule_set is None:
                raise RuleSetNotFound()
            self._same_rule_set(rule_set, read)
            return await uow.tax_rule_sets.add_version(
                actor.user_id, rule_set_id, self._fields(actor, read, report, stored, note)
            )

    @staticmethod
    def _same_rule_set(rule_set: Mapping[str, Any], read: _Read) -> None:
        if (rule_set["country"], rule_set["region"], rule_set["year_label"]) != (
            read.country,
            read.region,
            read.year,
        ):
            ours = _label(rule_set["country"], rule_set["region"], rule_set["year_label"])
            raise RuleSetDocumentError(
                f"This document is for {read.label}, but the rule set is for {ours}; "
                "a rule set's versions are all for one jurisdiction and year",
                [Problem("jurisdiction", f"expected {ours}")],
            )

    async def draft(
        self,
        actor: Actor,
        document: Document,
        *,
        rule_set_id: str | None = None,
        note: str | None = None,
        imported: bool = False,
    ) -> dict[str, Any]:
        """Store a document as a new version: of `rule_set_id`, or of the
        user's rule set for its jurisdiction and year, created if there is
        none. What an agent drafting rules, and an import, both want.

        An import lands as draft or invalid even when it passes: rules from
        somewhere else are validated (and activated) by the user's own step.
        """
        note = self._note(note)
        read, report, stored = self._check(document)
        status = status_after(report)
        if imported and status == "validated":
            status = "draft"
        async with self._uow_factory() as uow:
            repo = uow.tax_rule_sets
            if rule_set_id is not None:
                rule_set = await repo.get_set(actor.user_id, rule_set_id, lock=True)
                if rule_set is None:
                    raise RuleSetNotFound()
                self._same_rule_set(rule_set, read)
            else:
                rule_set = await repo.find_set(
                    actor.user_id, read.country, read.region, read.year, lock=True
                )
                if rule_set is None:
                    try:
                        rule_set = await repo.create_set(
                            actor.user_id, read.country, read.region, read.year, read.label
                        )
                    except RuleSetExists as exists:  # created meanwhile: use it
                        rule_set = await repo.get_set(actor.user_id, exists.rule_set_id, lock=True)
                        assert rule_set is not None
            return await repo.add_version(
                actor.user_id,
                rule_set["id"],
                self._fields(actor, read, report, stored, note, status),
            )

    async def import_document(
        self, actor: Actor, document: Document, *, note: str | None = None
    ) -> dict[str, Any]:
        """A rule set from a file: data, never code, landing as a draft (or
        invalid). Its examples must pass and the user activate it, like any."""
        return await self.draft(actor, document, note=note or "Imported", imported=True)

    async def import_url(self, actor: Actor, url: str) -> dict[str, Any]:
        """A rule set fetched from `url`, through the SSRF guard
        (adapters/net): https, public addresses only, size and time limits.
        FetchRefused when it won't be fetched."""
        if self._fetcher is None:
            raise FetchRefused("This server doesn't fetch rule sets from URLs")
        fetched = await self._fetcher.fetch_text(url)
        return await self.draft(
            actor,
            fetched.text,
            note=f"Imported from {fetched.url}"[:MAX_NOTE_LENGTH],
            imported=True,
        )

    # ── the lifecycle ────────────────────────────────────────────────────────

    async def validate(
        self, actor: Actor, version_id: str, rule_set_id: str | None = None
    ) -> dict[str, Any]:
        """Run the validator again and store its report. A draft, invalid,
        validated or proposed version moves to what the report says (a
        proposal stays one while it passes); an active or superseded version
        keeps its status, as history, with the fresh report."""
        async with self._uow_factory() as uow:
            version = await self._version(uow, actor.user_id, version_id, rule_set_id)
            report = validate_document(version["content"])
            fields: dict[str, Any] = {"validation": report_json(report, self._now())}
            if version["status"] in ("draft", "invalid", "validated") or (
                version["status"] == "proposed" and not report.ok
            ):
                fields["status"] = status_after(report)
            await uow.tax_rule_sets.update_version(actor.user_id, version_id, fields)
            return await self._version(uow, actor.user_id, version_id, None)

    async def propose(
        self, actor: Actor, version_id: str, rule_set_id: str | None = None
    ) -> dict[str, Any]:
        """Ask the user to review and activate a version. It must pass
        validation, run again now."""
        failed: str | None = None
        async with self._uow_factory() as uow:
            version = await self._version(uow, actor.user_id, version_id, rule_set_id)
            if version["status"] in ("active", "superseded"):
                raise RuleSetStateError(
                    f"Version {version['version']} is {version['status']}; only a newer version "
                    "can be proposed"
                )
            report = validate_document(version["content"])
            fields: dict[str, Any] = {"validation": report_json(report, self._now())}
            if report.ok:
                fields["status"] = "proposed"
                if version["status"] != "proposed":
                    fields["proposed_at"] = self._now()
            else:
                fields["status"] = status_after(report)
                failed = _failure(report)
            # The fresh report is kept either way, so the refusal is explained.
            await uow.tax_rule_sets.update_version(actor.user_id, version_id, fields)
            stored = await self._version(uow, actor.user_id, version_id, None)
        if failed:
            raise RuleSetStateError(f"Version {version['version']} can't be proposed: {failed}")
        return stored

    async def activate(
        self, actor: Actor, version_id: str, rule_set_id: str | None = None
    ) -> dict[str, Any]:
        """Make a version the one Salli computes with for its jurisdiction and
        year, superseding the set's active version, atomically under a lock on
        the set. Needs `tax:activate`: only the user's own sign-ins hold it."""
        if not actor.may(TAX_ACTIVATE):
            raise RuleSetPermissionError(
                "Activating tax rules needs your own sign-in to Salli (the app, the salli CLI "
                "or a personal access token). AI connectors and other applications can "
                "propose rules, never activate them."
            )
        failed: str | None = None
        async with self._uow_factory() as uow:
            repo = uow.tax_rule_sets
            version = await self._version(uow, actor.user_id, version_id, rule_set_id)
            rule_set = await repo.get_set(actor.user_id, version["rule_set_id"], lock=True)
            assert rule_set is not None  # the composite foreign key
            # Read again under the lock: another activation may have finished.
            version = await self._version(uow, actor.user_id, version_id, None)
            if version["status"] == "active":
                return version
            if version["status"] == "superseded":
                raise RuleSetStateError(
                    f"Version {version['version']} was superseded. To use these rules again, "
                    "add them as a new version (export it, then add the export)."
                )
            now = self._now()
            report = validate_document(version["content"])
            if not report.ok:
                failed = _failure(report)
                await repo.update_version(
                    actor.user_id,
                    version_id,
                    {"validation": report_json(report, now), "status": status_after(report)},
                )
            else:
                previous = rule_set["active_version_id"]
                # The old one first: the one-active-version index is checked
                # on every statement.
                if previous is not None and previous != version_id:
                    await repo.update_version(
                        actor.user_id, previous, {"status": "superseded", "superseded_at": now}
                    )
                await repo.update_version(
                    actor.user_id,
                    version_id,
                    {
                        "status": "active",
                        "activated_at": now,
                        "validation": report_json(report, now),
                    },
                )
                await repo.set_active(actor.user_id, rule_set["id"], version_id)
                await uow.audit_log.log(
                    actor.user_id,
                    "activate_tax_rule_set",
                    {
                        "rule_set_id": rule_set["id"],
                        "version_id": version_id,
                        "version": version["version"],
                        "content_hash": version["content_hash"],
                        "superseded_version_id": previous,
                        "by": actor.name or actor.kind,
                    },
                    "approved",
                )
            stored = await self._version(uow, actor.user_id, version_id, None)
        if failed:
            raise RuleSetStateError(f"Version {version['version']} can't be activated: {failed}")
        return stored

    # ── review and sharing ───────────────────────────────────────────────────

    async def diff(
        self,
        user_id: str,
        rule_set_id: str,
        to_version_id: str,
        from_version_id: str | None = None,
    ) -> dict[str, Any]:
        """What changed from one version to another of a rule set: from the
        active version unless another is named (from nothing when there is no
        active version), with the source behind each change and the `to`
        version's example results: what the user reviews before activating."""
        async with self._uow_factory() as uow:
            rule_set = await uow.tax_rule_sets.get_set(user_id, rule_set_id)
            if rule_set is None:
                raise RuleSetNotFound()
            to = await self._version(uow, user_id, to_version_id, rule_set_id)
            base_id = from_version_id or rule_set["active_version_id"]
            base = await self._version(uow, user_id, base_id, rule_set_id) if base_id else None
        diff = diff_documents(base["content"] if base else None, to["content"])
        return {
            "rule_set_id": rule_set_id,
            "from": _summary(base) if base else None,
            "to": _summary(to),
            "changes": [
                {
                    "path": c.path,
                    "kind": c.kind,
                    "before": c.before,
                    "after": c.after,
                    "figure": c.figure,
                    "source": c.source,
                }
                for c in diff.changes
            ],
            "sources": {key: dict(value) for key, value in diff.sources.items()},
            "examples": to["validation"].get("examples", []),
            "validation_ok": bool(to["validation"].get("ok")),
        }

    async def export(
        self, user_id: str, version_id: str, rule_set_id: str | None = None
    ) -> dict[str, Any]:
        """The version's document as a file: canonical JSON (docs/taxrules.md,
        "Content hash") when it matches the schema, so the file's sha256 is its
        content hash; otherwise as stored, keys sorted."""
        async with self._uow_factory() as uow:
            version = await self._version(uow, user_id, version_id, rule_set_id)
            rule_set = await uow.tax_rule_sets.get_set(user_id, version["rule_set_id"])
            assert rule_set is not None
        canonical = version["content_hash"] is not None
        text = (
            canonical_json(version["content"])
            if canonical
            else json.dumps(version["content"], sort_keys=True, ensure_ascii=False, indent=2)
        )
        return {
            "filename": _filename(rule_set, version["version"]),
            "content_hash": version["content_hash"],
            "canonical": canonical,
            "text": text,
        }

    # ── computing ────────────────────────────────────────────────────────────

    async def evaluate(
        self,
        user_id: str,
        version_id: str,
        answers: Mapping[str, str | bool] | None = None,
        *,
        year_label: str | None = None,
        rule_set_id: str | None = None,
    ) -> dict[str, Any]:
        """Apply a version's rules to the user's own ledger, read-only.

        Each role's total is added up from the postings on the user's
        accounts whose `tax_role` is that role, within the rule set's year,
        in each account's normal-balance direction (domain/taxrules/inputs.py:
        the generic replacement for tax_service's `_build_ledger_view`),
        converted into the rule set's currency at each entry date's rate when
        the ledger is kept in another. Then the engine computes every line.
        Nothing is stored. `year_label`, when given, must be the rules' own:
        a guard against applying one year's rules to another's question.
        """
        async with self._uow_factory() as uow:
            version = await self._version(uow, user_id, version_id, rule_set_id)
            try:
                compiled = compile_rule_set(version["content"])
            except RuleSetError:
                raise RuleSetStateError(
                    f"Version {version['version']} doesn't compile, so it can't compute "
                    "anything: validate it to see why"
                ) from None
            doc = compiled.document
            if year_label is not None and year_label != doc.year.label:
                raise RuleSetInputError(
                    f"These rules are for {doc.year.label}, not {year_label}",
                    [Problem("year", f"expected {doc.year.label}")],
                )
            base = await uow.user_profiles.base_currency(user_id)
            accounts = await uow.ledger.get_accounts(user_id, include_inactive=True)
            entries = await uow.ledger.get_entries(
                user_id, from_date=doc.year.start.isoformat(), to_date=doc.year.end.isoformat()
            )

        roles = [r.key for r in doc.roles]
        postings = role_postings(entries, accounts, roles, doc.year.start, doc.year.end)
        rates: dict[str, Any] = {}
        sources: list[dict[str, str | None]] = []
        for day in dates_needing_rates(postings, base, doc.currency):
            try:
                rate, source = await rate_to_base(self._fx, base, doc.currency, day)
            except FxUnavailableError:
                raise RuleSetRateMissing(
                    f"Salli has no {base}→{doc.currency} exchange rate for {day}, so it can't "
                    f"convert your ledger into these rules' currency. Record the amounts in "
                    f"{doc.currency}, or try again when a rate is published."
                ) from None
            rates[day] = rate
            sources.append({"date": day, "rate": normalized_str(rate), "source": source})
        totals = total_roles(postings, roles, base, doc.currency, rates)

        try:
            result = evaluate_rules(compiled, totals.totals, dict(answers or {}))
        except RuleSetEvaluationError as error:
            raise RuleSetInputError(
                "These rules couldn't be applied: " + "; ".join(str(p) for p in error.problems),
                error.problems,
            ) from None

        warnings: list[str] = []
        if not version["validation"].get("ok"):
            warnings.append(
                "This version hasn't passed its worked examples, so its figures may be wrong."
            )
        warnings += [
            f"The ledger's total for {key} is negative ({normalized_str(totals.totals[key])}); "
            "it is used as it is."
            for key in totals.negative
        ]
        return _evaluation(version, doc, result, totals, base, sources, warnings)


def _failure(report: ValidationReport) -> str:
    if report.errors:
        first = report.errors[0]
        more = f" (and {len(report.errors) - 1} more)" if len(report.errors) > 1 else ""
        return f"{first}{more}"
    failing = [e.name for e in report.examples if not e.passed]
    return f"worked examples don't match: {', '.join(failing)}"


def _summary(version: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: version[key]
        for key in (
            "id",
            "rule_set_id",
            "version",
            "status",
            "content_hash",
            "author_kind",
            "author_name",
            "change_note",
            "created_at",
            "proposed_at",
            "activated_at",
            "superseded_at",
        )
    }


def _evaluation(
    version: Mapping[str, Any],
    doc: RuleSet,
    result: RuleSetResult,
    totals: Any,
    base: str,
    rates: list[dict[str, str | None]],
    warnings: list[str],
) -> dict[str, Any]:
    def number(value: object) -> str | bool:
        return value if isinstance(value, bool) else normalized_str(cast(Any, value))

    return {
        "version": _summary(version),
        "validated": bool(version["validation"].get("ok")),
        "country": result.country,
        "region": doc.jurisdiction.region,
        "year": result.year,
        "period_start": doc.year.start.isoformat(),
        "period_end": doc.year.end.isoformat(),
        "currency": result.currency,
        "base_currency": base,
        "content_hash": result.content_hash,
        "roles": [
            {
                "key": role.key,
                "kind": role.kind,
                "label": role.label,
                "total": normalized_str(totals.totals[role.key]),
                "postings": totals.postings[role.key],
            }
            for role in doc.roles
        ],
        "rates": rates,
        "lines": [
            {
                "key": line.key,
                "label": line.label,
                "amount": normalized_str(line.amount),
                "expr": line.expr,
                "source": line.source,
                "refundable": line.refundable,
            }
            for line in result.lines
        ],
        "net": normalized_str(result.net),
        "net_expr": result.net_expr,
        "tax_payable": normalized_str(result.tax_payable),
        "refund_due": normalized_str(result.refund_due),
        "forms": [
            {
                "key": key,
                "fields": [{"id": fid, "value": number(value)} for fid, value in fields.items()],
            }
            for key, fields in result.forms.items()
        ],
        "warnings": warnings,
        "provenance": PROVENANCE,
    }
