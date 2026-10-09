"""
OnboardingService — the all-in-one first-run flow: profile facts saved as agent
memories, a starter chart of accounts built from the user's income sources, an
optional first goal, and the seeded `need` tags.

Shared by `POST /onboarding/complete`, `salli onboarding complete` and
`salli setup`, so every surface creates the same starting ledger. Idempotent.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, NamedTuple

from salli.application.ports import AccountCodeTaken
from salli.domain.jurisdiction import LEGACY_TAX_ID_FIELDS, InvalidTaxIdError, make_tax_id
from salli.domain.tax.models import StarterAccount
from salli.domain.tax.packs import registry

# ── The starter chart of accounts ──────────────────────────────────────────────


class AccountSeed(NamedTuple):
    code: str
    name: str
    type: str
    # What the tax engine reads (`domain.accounting.models.TaxRole`). Declared
    # rather than inferred downstream from the name: credit accounts are
    # correctly typed `asset` (withheld tax is a receivable), and the engine
    # used to look for them among liabilities, so every seeded credit account
    # was silently ignored.
    tax_role: str | None = None


# What everyone gets, whatever their country: nothing here is about tax. A tax
# resident's pack adds its own accounts (`TaxPack.starter_accounts`: Sri Lanka's
# APIT and AIT receivables, say) and may give one of these its own name and
# role, by using its code (Sri Lanka's 4500 is "Foreign Service Income (FSI)").
BASE_ACCOUNTS: list[AccountSeed] = [
    AccountSeed("1100", "Cash", "asset"),
    AccountSeed("1200", "Bank Account", "asset"),
    AccountSeed("3000", "Opening Equity", "equity"),
    AccountSeed("5000", "General Expenses", "expense"),
]

SOURCE_ACCOUNTS: dict[str, list[AccountSeed]] = {
    "employment": [AccountSeed("4100", "Employment Income", "income")],
    "freelance": [
        AccountSeed("4200", "Freelance / Business Income", "income"),
        AccountSeed("5100", "Business Expenses", "expense"),
    ],
    "rental": [
        AccountSeed("4300", "Rental Income", "income"),
        AccountSeed("5200", "Property & Maintenance Expenses", "expense"),
    ],
    "interest": [AccountSeed("4400", "Interest Income", "income")],
    "foreign": [
        AccountSeed("1300", "Foreign Currency Account", "asset"),
        AccountSeed("4500", "Foreign Income", "income"),
    ],
    "dividends": [AccountSeed("4600", "Dividend Income", "income")],
}


def _with_pack_accounts(
    seeds: Sequence[AccountSeed], pack_accounts: Iterable[StarterAccount]
) -> list[AccountSeed]:
    """`seeds`, where a pack account with the same code takes the seed's
    place, followed by the pack's other accounts in the pack's order."""
    by_code = {a.code: AccountSeed(a.code, a.name, a.type, a.tax_role) for a in pack_accounts}
    merged = [by_code.pop(seed.code, seed) for seed in seeds]
    return merged + list(by_code.values())


def starter_chart(tax_residency: str | None, income_sources: Iterable[str]) -> list[AccountSeed]:
    """The starter chart for someone taxed in `tax_residency` with these income
    sources: the neutral accounts, and what that country's tax pack adds.

    With no residency, or no pack for it, nothing tax-specific is added: Sri
    Lankan receivables in a chart for someone who is not Sri Lankan would be
    wrong, and their roles would not be ones their tax uses.
    """
    pack_accounts = registry.starter_accounts(tax_residency)
    chart = _with_pack_accounts(BASE_ACCOUNTS, [a for a in pack_accounts if not a.income_source])
    for source in income_sources:
        from_pack = [a for a in pack_accounts if a.income_source == source]
        chart += _with_pack_accounts(SOURCE_ACCOUNTS.get(source, []), from_pack)
    return chart


# The `need` axis — a closed, seeded set the reports reference by slug. Users
# can rename these but not delete them. Category tags are open and are created
# on demand as people tag things.
#
# Kept in sync by hand with `_NEED_TAGS` in the f5c93a71d84e migration, which
# seeds the same rows for users who onboarded before tags existed.
SYSTEM_NEED_TAGS = [
    ("essential", "Needs", "#2E7D6B"),
    ("discretionary", "Wants", "#C77D3A"),
    ("savings", "Savings & Debt", "#3A5FC7"),
]

_MEMORIES = {
    "onboarding_complete": "true",
}

GOAL_LABELS = {
    "financial_independence": "Financial Independence",
    "retirement": "Retirement",
    "home": "Buy a home",
    "emergency_fund": "Emergency fund",
    "debt_free": "Become debt-free",
    "wealth_growth": "Grow my wealth",
}


_ANSWER_DEFAULTS: dict[str, Any] = {
    "nic": "",
    "residency": "resident",
    "tax_residency": None,
    "employer": "",
    "employment_type": "",
    "ird_number": "",
    "income_sources": [],
    "primary_goal": "",
    "goal_target_amount": 0,
    "goal_target_year": "",
    "risk_appetite": "",
    "motivation": "",
}


class OnboardingService:
    def __init__(self, documents: Any, fi: Any, ledger: Any, profile: Any = None) -> None:
        self._documents = documents
        self._fi = fi
        self._ledger = ledger
        # Where the tax identity goes (UserProfileService). Optional so the
        # service builds without one; then only memories record the numbers.
        self._profile = profile

    async def is_complete(self, user_id: str) -> bool:
        return await self._documents.get_memory(user_id, "onboarding_complete") is not None

    async def complete(self, user_id: str, answers: dict[str, Any]) -> dict[str, Any]:
        """Save profile memories and create a starter chart of accounts.
        Idempotent — safe to call again if the user re-runs onboarding.

        `answers` has the fields of the API's OnboardingRequest; only `name` is
        required; the rest default as the API's request model does.
        """
        a: dict[str, Any] = {**_ANSWER_DEFAULTS, **answers}

        # Save profile memories
        memories: dict[str, str] = {
            "onboarding_complete": "true",
            "user_name": a["name"],
            "residency_status": a["residency"],
        }
        if a["nic"]:
            memories["nic_number"] = a["nic"]
        if a["employer"]:
            memories["employer"] = a["employer"]
        if a["employment_type"]:
            memories["employment_type"] = a["employment_type"]
        if a["ird_number"]:
            memories["ird_number"] = a["ird_number"]
        if a["income_sources"]:
            memories["income_sources"] = ", ".join(a["income_sources"])
        if a["primary_goal"]:
            memories["primary_goal"] = a["primary_goal"]
        if a["goal_target_amount"]:
            memories["goal_target_amount"] = str(a["goal_target_amount"])
        if a["goal_target_year"]:
            memories["goal_target_year"] = a["goal_target_year"]
        if a["risk_appetite"]:
            memories["risk_appetite"] = a["risk_appetite"]
        if a["motivation"]:
            memories["motivation"] = a["motivation"]

        for slug, value in memories.items():
            await self._documents.save_memory(user_id, slug=slug, value=value)

        await self._record_tax_identity(user_id, a)

        # If they named a concrete target, seed an initial Financial Independence goal.
        if a["primary_goal"] and a["goal_target_amount"] > 0:
            try:
                await self._fi.create_goal(
                    user_id,
                    {
                        "name": GOAL_LABELS.get(a["primary_goal"], "My goal"),
                        "kind": a["primary_goal"],
                        "target_amount": a["goal_target_amount"],
                        "target_date": f"{a['goal_target_year']}-12-31"
                        if a["goal_target_year"]
                        else None,
                        "priority": 1,
                    },
                )
            except Exception:
                pass

        # Create accounts — skip any that already exist (unique constraint will
        # catch duplicates). Which ones depends on where the user is taxed, so
        # this comes after the residency has been recorded above.
        residency = await self._profile.get_tax_residency(user_id) if self._profile else None
        accounts_to_create = starter_chart(residency, a["income_sources"])

        # Deduplicate by code
        seen_codes: set[str] = set()
        created: list[str] = []
        skipped: list[str] = []

        # Deactivated accounts too: the code is still taken, and re-creating a
        # starter account the user closed would fail on it.
        existing = await self._ledger.list_accounts(user_id, include_inactive=True)
        existing_codes = {a.code for a in existing}

        for code, name, acct_type, tax_role in accounts_to_create:
            if code in seen_codes or code in existing_codes:
                skipped.append(code)
                continue
            seen_codes.add(code)
            # Existing codes were skipped above; anything else that fails now
            # is a real failure, and reporting "0 accounts created" hid it.
            try:
                await self._ledger.add_account(
                    user_id,
                    code=code,
                    name=name,
                    type=acct_type,  # type: ignore[arg-type]
                    tax_role=tax_role,
                )
            except AccountCodeTaken:
                # Created meanwhile, by an onboarding running at the same time.
                skipped.append(code)
                continue
            created.append(f"{code} {name}")

        # Seed the need axis. Idempotent — `ensure_system_tags` is a no-op when the
        # rows already exist, so re-running onboarding does not duplicate them.
        await self._ledger.ensure_system_tags(user_id, SYSTEM_NEED_TAGS)

        return {
            "memories_saved": list(memories.keys()),
            "accounts_created": created,
            "accounts_skipped": skipped,
        }

    async def _record_tax_identity(self, user_id: str, a: dict[str, Any]) -> None:
        """Put where the user is taxed, and the Sri Lankan numbers this flow
        collects, on the profile (where a Sri Lankan number with no residency
        makes the user LK; see UserProfileService.update_identity)."""
        if self._profile is None:
            return
        identity: dict[str, Any] = {}
        if a.get("tax_residency"):
            identity["tax_residency"] = a["tax_residency"]
        for field, scheme in LEGACY_TAX_ID_FIELDS.items():
            value = a.get(field)
            if not value:
                continue
            try:
                make_tax_id(scheme, value)
            except InvalidTaxIdError:
                # This flow always took any text. One that cannot be a number
                # stays the memory it always was, rather than failing onboarding.
                continue
            identity[field] = value
        if identity:
            await self._profile.update_identity(user_id, identity)
