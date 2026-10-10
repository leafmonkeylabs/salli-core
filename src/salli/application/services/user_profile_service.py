"""
UserProfileService — the fact-find profile: identity, risk profile, life stage, and
the onboarding steps that reuse LedgerService/FiService to record real opening
balances and income (rather than the old empty-accounts-only flow).
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from salli.application.fx import rate_to_base
from salli.application.ports import ProfileMissing
from salli.application.services.document_service import DocumentService
from salli.application.services.fi_service import FiService
from salli.application.services.ledger_service import LedgerService, tax_residency
from salli.domain.accounting.models import AccountType, Direction
from salli.domain.ai_models import DEFAULT_MODEL
from salli.domain.currency import normalize_currency
from salli.domain.fi.assumptions import check_override
from salli.domain.jurisdiction import (
    TaxId,
    normalize_country,
    parse_tax_ids,
    stored_tax_ids,
)
from salli.domain.risk import engine as risk_engine
from salli.domain.risk.life_stage import derive_life_stage
from salli.domain.risk.models import RiskQuestionnaireAnswers

_OPENING_EQUITY_CODE = "3000"
_OPENING_EQUITY_NAME = "Opening Equity"
_OPENING_EQUITY_TYPE: AccountType = "equity"

_DEFAULT_DEPOSIT_CODE = "1200"
_DEFAULT_DEPOSIT_NAME = "Bank Account"


class BaseCurrencyLockedError(ValueError):
    """The base currency cannot change once anything is stored in it."""


# Legacy onboarding stored these as free-text agent_documents "memories" (namespace
# "memories"). Best-effort, self-healing backfill into the structured columns the
# first time a profile is read after this migration — narrative fields like
# "motivation" have no structured equivalent and stay as memories.
_LEGACY_MEMORY_TO_COLUMN = {
    "user_name": "display_name",
    "residency_status": "residency_status",
    "employer": "employer",
    "employment_type": "employment_type",
}

#: Everything `update_identity` treats as part of the tax identity.
_TAX_IDENTITY_FIELDS = ("tax_residency", "tax_ids")


def tax_identity_view(profile: dict[str, Any]) -> dict[str, Any]:
    """`profile` with its tax residency, and its tax ids as clean dicts."""
    return {
        **profile,
        "tax_residency": profile.get("tax_residency"),
        "tax_ids": [t.as_dict() for t in stored_tax_ids(profile.get("tax_ids"))],
    }


#: The user's own FI assumptions: the name each has in the API, and its column.
_FI_ASSUMPTION_COLUMNS = {
    "inflation": "fi_inflation",
    "real_return": "fi_real_return",
    "safe_withdrawal_rate": "fi_safe_withdrawal_rate",
}


def fi_assumptions_view(profile: dict[str, Any]) -> dict[str, Any]:
    """`profile` with the user's own FI assumptions under `fi_assumptions`, as
    decimal strings ("0.03"), None where they use their currency's default."""
    view = {k: v for k, v in profile.items() if k not in _FI_ASSUMPTION_COLUMNS.values()}
    view["fi_assumptions"] = {
        name: None if profile.get(column) is None else f"{Decimal(profile[column]).normalize():f}"
        for name, column in _FI_ASSUMPTION_COLUMNS.items()
    }
    return view


def _checked_fi_changes(changes: dict[str, Any]) -> dict[str, Decimal | None]:
    unknown = set(changes) - set(_FI_ASSUMPTION_COLUMNS)
    if unknown:
        raise ValueError(f"Not FI assumptions: {', '.join(sorted(unknown))}")
    return {
        name: check_override(name, None if value is None else Decimal(str(value)))
        for name, value in changes.items()
    }


def _apply_tax_changes(
    current: dict[str, Any], changes: dict[str, Any]
) -> tuple[str | None, list[TaxId]]:
    """The residency and tax ids a profile has once `changes` apply to it.

    Raises a ValueError (UnknownCountryError, InvalidTaxIdError) for anything
    that does not validate, before anything is written. Neither implies the
    other: a residency is only ever what the user said.
    """
    residency: str | None = current.get("tax_residency")
    if "tax_residency" in changes:
        given = changes["tax_residency"]
        residency = normalize_country(given) if given else None
    if changes.get("tax_ids") is not None:
        ids = parse_tax_ids(changes["tax_ids"])
    else:
        ids = stored_tax_ids(current.get("tax_ids"))
    return residency, ids


def _age_from_dob(dob: datetime.date | str | None) -> int | None:
    if dob is None:
        return None
    if isinstance(dob, str):
        dob = datetime.date.fromisoformat(dob)
    today = datetime.date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class UserProfileService:
    def __init__(
        self,
        uow_factory: Callable[[], Any],
        ledger_service: LedgerService,
        fi_service: FiService,
        document_service: DocumentService,
        fx_service: Any = None,
        default_currency: str = "USD",
    ) -> None:
        self._uow_factory = uow_factory
        self._ledger = ledger_service
        self._fi = fi_service
        self._documents = document_service
        # Converts declarations made in another currency into the base one.
        # Optional so call sites that never declare foreign amounts need not
        # build one; without it such a declaration must carry its own fx_rate.
        self._fx = fx_service
        # The base currency a profile is created with when the caller names none.
        self._default_currency = normalize_currency(default_currency)
        self._members: set[str] = set()

    # ── Membership ───────────────────────────────────────────────────────────

    async def ensure_user(
        self,
        user_id: str,
        email: str | None,
        *,
        may_create: bool,
        base_currency: str | None = None,
    ) -> bool:
        """Make sure an authenticated caller has a profile row; report whether
        they may use this instance.

        A caller with a row is a member. A caller without one is created only
        when `may_create` — an instance open to sign-ups — and refused
        otherwise, so a self-hosted instance answers only the people its owner
        set up, whatever else the auth provider would vouch for.

        A new profile is created in `base_currency`, or the instance's default.
        An existing one keeps its own; use `set_base_currency` to change it.

        Members are remembered per process, so this is one read on a caller's
        first request rather than one per request.
        """
        if user_id in self._members:
            return True
        async with self._uow_factory() as uow:
            profile = await uow.user_profiles.get(user_id)
            if profile is None:
                if not may_create:
                    return False
                currency = (
                    normalize_currency(base_currency) if base_currency else self._default_currency
                )
                await uow.user_profiles.upsert(user_id, {"email": email, "base_currency": currency})
            elif email and not profile.get("email"):
                await uow.user_profiles.upsert(user_id, {"email": email})
        self._members.add(user_id)
        return True

    def forget(self, user_id: str) -> None:
        """Drop a deleted account from the membership cache."""
        self._members.discard(user_id)

    # ── Base currency ────────────────────────────────────────────────────────

    async def get_base_currency(self, user_id: str) -> str:
        async with self._uow_factory() as uow:
            return await uow.user_profiles.base_currency(user_id)

    async def set_base_currency(self, user_id: str, currency: str) -> str:
        """Change the currency the ledger is measured in — only while it is empty.

        Every stored amount (postings' base amounts, budgets, debts, holdings,
        goals, policies) is a number in the base currency. Changing the
        currency under them would silently reinterpret all of it, so once there
        is any, it is refused (`BaseCurrencyLockedError`). Setting the currency
        it already has is always fine. The profile must exist (`ProfileMissing`
        otherwise): this never creates one.
        """
        code = normalize_currency(currency)
        async with self._uow_factory() as uow:
            # `ProfileMissing` without a profile: creating one is ensure_user's,
            # behind its may_create gate, so callers ensure the user first.
            current = await uow.user_profiles.base_currency(user_id)
            if code == current:
                return code
            if await uow.user_profiles.has_financial_data(user_id):
                raise BaseCurrencyLockedError(
                    f"Your amounts are kept in {current}, so the base currency can no longer "
                    "change. Accounts can still be held in any currency."
                )
            await uow.user_profiles.upsert(user_id, {"base_currency": code})
        return code

    # ── Profile ──────────────────────────────────────────────────────────────

    async def get_profile(self, user_id: str) -> dict[str, Any]:
        async with self._uow_factory() as uow:
            stored = await uow.user_profiles.get(user_id)
        profile = stored if stored is not None else {"id": user_id}
        # Only into a profile that exists: a read never creates one.
        await self._backfill_from_legacy_memories(user_id, profile, persist=stored is not None)
        return fi_assumptions_view(tax_identity_view(profile))

    async def get_tax_residency(self, user_id: str) -> str | None:
        """Where the user is taxed (ISO 3166-1 alpha-2), or None while they
        have not said."""
        async with self._uow_factory() as uow:
            return await tax_residency(uow, user_id)

    async def get_preferred_model(self, user_id: str) -> str:
        """
        The model this user's conversations run on: always the pinned one.

        The name is kept because four call sites and a guard test reference it,
        but there is no longer a preference to read. It deliberately does NOT
        consult the stored `preferred_model` — doing so would leave every user
        who had already chosen Opus or Fable running (and being charged) on it
        forever, which is the opposite of pinning the cost.

        No longer touches the database at all, so the agent and FI routes lose a
        profile read per request.
        """
        return DEFAULT_MODEL

    async def update_identity(self, user_id: str, data: dict[str, Any]) -> None:
        """Update the identity fields present in `data`; the rest stay as they are.

        The tax identity, validated before anything is written:

        - `tax_residency`: an ISO 3166-1 alpha-2 code; None or "" clears it.
        - `tax_ids`: replaces every tax id, `[{"scheme", "value"}]`, one per
          scheme ("XX-KIND").

        `fi_assumptions`: the user's own planning assumptions present in it
        (`inflation`, `real_return`, `safe_withdrawal_rate`, yearly fractions);
        None returns one to the default for their currency.
        """
        fields: dict[str, Any] = {}
        for key in (
            "display_name",
            "employer",
            "employment_status",
            "employment_type",
            "residency_status",
        ):
            if key in data:
                fields[key] = data[key]
        if data.get("date_of_birth"):
            fields["date_of_birth"] = datetime.date.fromisoformat(data["date_of_birth"])
        if "dependents_count" in data:
            fields["dependents_count"] = int(data["dependents_count"])
        tax_changes = {key: data[key] for key in _TAX_IDENTITY_FIELDS if key in data}
        fi_changes = _checked_fi_changes(data.get("fi_assumptions") or {})
        if not fields and not tax_changes and not fi_changes:
            return
        # One unit of work: a change that does not validate writes nothing.
        async with self._uow_factory() as uow:
            if fields:
                await uow.user_profiles.upsert(user_id, fields)
            if tax_changes:
                current = await uow.user_profiles.get(user_id)
                if current is None:
                    raise ProfileMissing(user_id)
                residency, ids = _apply_tax_changes(current, tax_changes)
                await uow.user_profiles.set_tax_identity(
                    user_id, tax_residency=residency, tax_ids=[t.as_dict() for t in ids]
                )
            if fi_changes:
                await uow.user_profiles.set_fi_assumptions(user_id, fi_changes)
        await self._recompute_life_stage(user_id)

    async def _recompute_life_stage(self, user_id: str) -> None:
        async with self._uow_factory() as uow:
            profile = await uow.user_profiles.get(user_id)
            if profile is None:
                return
            life_stage = derive_life_stage(
                _age_from_dob(profile.get("date_of_birth")),
                profile.get("dependents_count") or 0,
                profile.get("employment_status"),
            )
            await uow.user_profiles.upsert(user_id, {"life_stage": life_stage})

    async def _backfill_from_legacy_memories(
        self, user_id: str, profile: dict[str, Any], *, persist: bool = True
    ) -> None:
        missing = {
            slug: column
            for slug, column in _LEGACY_MEMORY_TO_COLUMN.items()
            if profile.get(column) is None
        }
        updates: dict[str, Any] = {}
        for slug, column in missing.items():
            mem = await self._documents.get_memory(user_id, slug)
            if mem and mem.get("content"):
                updates[column] = mem["content"]
                profile[column] = mem["content"]
        if profile.get("risk_category") is None:
            mem = await self._documents.get_memory(user_id, "risk_appetite")
            if mem and mem.get("content") in ("conservative", "balanced", "aggressive"):
                updates["risk_category"] = mem["content"]
                profile["risk_category"] = mem["content"]
        if updates and persist:
            async with self._uow_factory() as uow:
                await uow.user_profiles.upsert(user_id, updates)

    # ── Risk questionnaire ───────────────────────────────────────────────────

    async def submit_risk_questionnaire(
        self, user_id: str, answers_data: dict[str, Any]
    ) -> dict[str, Any]:
        answers = RiskQuestionnaireAnswers(
            time_horizon_years=int(answers_data["time_horizon_years"]),
            drawdown_reaction=answers_data["drawdown_reaction"],
            income_stability=answers_data["income_stability"],
            investment_experience=answers_data["investment_experience"],
            dependents_count=int(answers_data.get("dependents_count", 0)),
        )
        profile = risk_engine.compute(answers)
        async with self._uow_factory() as uow:
            await uow.user_profiles.upsert(
                user_id,
                {
                    "risk_score": profile.score,
                    "risk_category": profile.category,
                    "dependents_count": answers.dependents_count,
                },
            )
        await self._recompute_life_stage(user_id)
        return {
            "score": profile.score,
            "category": profile.category,
            "breakdown": profile.breakdown,
        }

    # ── Opening balances / income (reuse LedgerService, never reinvent it) ──

    async def _ensure_account(
        self, user_id: str, cache: dict[str, str], code: str, name: str, type_: AccountType
    ) -> str:
        if code in cache:
            return cache[code]
        new_id = await self._ledger.add_account(user_id, code, name, type_)
        cache[code] = new_id
        return new_id

    async def declare_opening_balances(
        self, user_id: str, balances: list[dict[str, Any]]
    ) -> list[str]:
        """balances: [{"code", "name", "type": "asset"|"liability", "amount",
        "currency"?, "fx_rate"?}].

        Amounts are in the base currency unless an item names another, in which
        case it is converted at `fx_rate`, or today's rate when none is given.
        """
        today = datetime.date.today().isoformat()
        base = await self._ledger.base_currency(user_id)
        cache = {a.code: a.id for a in await self._ledger.list_accounts(user_id)}
        entry_ids: list[str] = []

        for item in balances:
            amount = Decimal(str(item["amount"]))
            if amount == 0:
                continue
            currency = normalize_currency(item.get("currency") or base)
            fx_rate, fx_source = await self._rate_to_base(
                currency, base, today, item.get("fx_rate")
            )
            acc_type = item["type"]
            if acc_type not in ("asset", "liability"):
                raise ValueError(f"Unsupported opening-balance account type: {acc_type}")

            acc_id = await self._ensure_account(
                user_id, cache, item["code"], item["name"], acc_type
            )
            equity_id = await self._ensure_account(
                user_id, cache, _OPENING_EQUITY_CODE, _OPENING_EQUITY_NAME, _OPENING_EQUITY_TYPE
            )
            if acc_type == "asset":
                debit_id, credit_id = acc_id, equity_id
            else:
                debit_id, credit_id = equity_id, acc_id

            postings = [
                {
                    "account_id": debit_id,
                    "direction": Direction.DEBIT,
                    "amount": amount,
                    "currency": currency,
                    "fx_rate": fx_rate,
                    "fx_rate_source": fx_source,
                },
                {
                    "account_id": credit_id,
                    "direction": Direction.CREDIT,
                    "amount": amount,
                    "currency": currency,
                    "fx_rate": fx_rate,
                    "fx_rate_source": fx_source,
                },
            ]
            entry_id = await self._ledger.add_entry(
                user_id, today, f"Opening balance: {item['name']}", "manual", postings
            )
            entry_ids.append(entry_id)
        return entry_ids

    async def _rate_to_base(
        self, currency: str, base: str, on_date: str, given: Any = None
    ) -> tuple[Decimal, str | None]:
        """Both postings of a declared entry carry the same rate, so the entry
        balances in base terms whatever the currency. See application/fx.py:
        no rate means FxUnavailableError, never a rate of 1."""
        return await rate_to_base(self._fx, currency, base, on_date, given)

    async def declare_income(self, user_id: str, incomes: list[dict[str, Any]]) -> list[str]:
        """incomes: [{"code", "name", "amount", "currency"?, "fx_rate"?,
        "deposit_account_code"?, "deposit_account_name"?}].

        Posts one representative monthly entry per income source so FI/cash-flow
        calculations have real data to work from immediately after onboarding.
        An amount in another currency is converted at `fx_rate`, or today's
        rate when none is given.
        """
        today = datetime.date.today().isoformat()
        base = await self._ledger.base_currency(user_id)
        cache = {a.code: a.id for a in await self._ledger.list_accounts(user_id)}
        entry_ids: list[str] = []

        for item in incomes:
            amount = Decimal(str(item["amount"]))
            if amount == 0:
                continue
            # Foreign income is the reason this exists. Booking it at face value
            # in the base currency misstates it by the exchange rate: a $2,000
            # remittance into a rupee ledger became Rs. 2,000.
            currency = normalize_currency(item.get("currency") or base)
            fx_rate, fx_source = await self._rate_to_base(
                currency, base, today, item.get("fx_rate")
            )
            income_id = await self._ensure_account(
                user_id, cache, item["code"], item["name"], "income"
            )
            deposit_code = item.get("deposit_account_code", _DEFAULT_DEPOSIT_CODE)
            deposit_name = item.get("deposit_account_name", _DEFAULT_DEPOSIT_NAME)
            deposit_id = await self._ensure_account(
                user_id, cache, deposit_code, deposit_name, "asset"
            )

            postings = [
                {
                    "account_id": deposit_id,
                    "direction": Direction.DEBIT,
                    "amount": amount,
                    "currency": currency,
                    "fx_rate": fx_rate,
                    "fx_rate_source": fx_source,
                },
                {
                    "account_id": income_id,
                    "direction": Direction.CREDIT,
                    "amount": amount,
                    "currency": currency,
                    "fx_rate": fx_rate,
                    "fx_rate_source": fx_source,
                },
            ]
            entry_id = await self._ledger.add_entry(
                user_id, today, f"Declared income: {item['name']}", "manual", postings
            )
            entry_ids.append(entry_id)
        return entry_ids
