"""
OnboardingService — the all-in-one first-run flow: profile facts saved as agent
memories, a starter chart of accounts built from the user's income sources, an
optional first goal, and the seeded `need` tags.

Shared by `POST /onboarding/complete`, `salli onboarding complete` and
`salli setup`, so every surface creates the same starting ledger. Idempotent.
"""

from __future__ import annotations

from typing import Any

from salli.application.ports import AccountCodeTaken

# ── Account templates per income source ───────────────────────────────────────

# (code, name, account_type, tax_role). `tax_role` is what the tax engine reads
# — see `domain.accounting.models.TaxRole`. It must be declared here rather than
# inferred downstream from the name: these credit accounts are correctly typed
# `asset` (withheld tax is a receivable), and the engine used to look for them
# among liabilities, so every seeded credit account was silently ignored.
AccountSeed = tuple[str, str, str, "str | None"]

BASE_ACCOUNTS: list[AccountSeed] = [
    ("1100", "Cash", "asset", None),
    ("1200", "Bank Account", "asset", None),
    ("3000", "Opening Equity", "equity", None),
    ("5000", "General Expenses", "expense", None),
    # Without this account there is nowhere to post a donation, so the
    # qualifying-payment deduction was unreachable for every default user.
    ("5900", "Donations & Qualifying Payments", "expense", "qualifying_payment"),
]

SOURCE_ACCOUNTS: dict[str, list[AccountSeed]] = {
    "employment": [
        ("4100", "Employment Income", "income", None),
        ("4110", "APIT Receivable", "asset", "apit_credit"),
    ],
    "freelance": [
        ("4200", "Freelance / Business Income", "income", None),
        ("5100", "Business Expenses", "expense", None),
    ],
    "rental": [
        ("4300", "Rental Income", "income", None),
        ("5200", "Property & Maintenance Expenses", "expense", None),
    ],
    "interest": [
        ("4400", "Interest Income", "income", None),
        ("4410", "AIT Receivable", "asset", "ait_credit"),
    ],
    "foreign": [
        ("1300", "Foreign Currency Account", "asset", None),
        ("4500", "Foreign Service Income (FSI)", "income", "fsi_income"),
        ("4510", "Foreign Tax Credit Receivable", "asset", "foreign_tax_credit"),
    ],
    "dividends": [
        ("4600", "Dividend Income", "income", None),
    ],
}

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
    def __init__(self, documents: Any, fi: Any, ledger: Any) -> None:
        self._documents = documents
        self._fi = fi
        self._ledger = ledger

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

        # Create accounts — skip any that already exist (unique constraint will catch duplicates)
        accounts_to_create = list(BASE_ACCOUNTS)
        for source in a["income_sources"]:
            accounts_to_create.extend(SOURCE_ACCOUNTS.get(source, []))

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
                    tax_role=tax_role,  # type: ignore[arg-type]
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
