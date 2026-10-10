"""
Parse a free-text / dictated sentence into a DRAFT double-entry journal entry.

The LLM only *extracts* the amount the user stated and *maps* the description to
existing account IDs from the user's chart — it never computes money and never
posts. The draft pre-fills the New Entry form; the user reviews and posts it
through the deterministic, balance-checked `POST /entries/` path. This mirrors
the posture of adapters/parsing/llm_classifier.py.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from salli.application.ports import LLMPort
from salli.application.services.ledger_service import LedgerService
from salli.domain.currency import is_currency
from salli.domain.rules.engine import Facts

_DRAFT_SCHEMA: dict[str, Any] = {
    "title": "JournalEntryDraft",
    "description": "A draft double-entry journal entry parsed from the user's own words.",
    "type": "object",
    "properties": {
        "entry_type": {
            "type": "string",
            "enum": ["income", "expense", "transfer"],
            "description": "expense = money paid out; income = money received; transfer = moved between own accounts.",
        },
        "amount": {
            "type": "string",
            "description": "The amount exactly as stated by the user, as a plain number string (no currency symbol, no commas). Never invent or compute an amount; if none is stated, use an empty string.",
        },
        "description": {
            "type": "string",
            "description": "A short human description of the transaction (e.g. 'Groceries, Keells').",
        },
        "debit_account_id": {
            "type": ["string", "null"],
            "description": "Id of the account to DEBIT, ONLY from the provided chart. null if the user did not clearly indicate one — do not guess a default.",
        },
        "credit_account_id": {
            "type": ["string", "null"],
            "description": "Id of the account to CREDIT, ONLY from the provided chart. null if the user did not clearly indicate one — do not guess a default.",
        },
        "debit_account_hint": {
            "type": ["object", "null"],
            "description": (
                "ONLY when debit_account_id is null AND you can clearly infer what kind of NEW "
                "account this transaction implies (e.g. a merchant/category with no existing match) — "
                "a suggested name and type for an account that doesn't exist yet in the chart. "
                "null whenever debit_account_id is non-null, or when nothing sensible can be inferred."
            ),
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Suggested account name, e.g. 'Uber Eats'.",
                },
                "type": {
                    "type": "string",
                    "enum": ["asset", "liability", "equity", "income", "expense"],
                },
            },
            "required": ["name", "type"],
        },
        "credit_account_hint": {
            "type": ["object", "null"],
            "description": (
                "Same as debit_account_hint, but for the credit side. ONLY when credit_account_id is null."
            ),
            "properties": {
                "name": {"type": "string", "description": "Suggested account name."},
                "type": {
                    "type": "string",
                    "enum": ["asset", "liability", "equity", "income", "expense"],
                },
            },
            "required": ["name", "type"],
        },
        "currency": {
            "type": "string",
            "description": "ISO 4217 code; the user's base currency unless the note names another.",
        },
        "confidence": {
            "type": "number",
            "description": "0.0–1.0 confidence that the account mapping is correct.",
        },
    },
    "required": [
        "entry_type",
        "amount",
        "description",
        "debit_account_id",
        "credit_account_id",
        "debit_account_hint",
        "credit_account_hint",
        "currency",
        "confidence",
    ],
}

_PROMPT = """You convert a person's plain-language note about a single transaction into a DRAFT \
double-entry journal entry. You do NOT post anything; the user reviews your draft first.

The user's chart of accounts (choose account ids ONLY from this list, never invent an id):
{accounts}

Double-entry rules:
- expense (money paid out): DEBIT the matching expense account, CREDIT the asset/bank/cash account paid from.
- income (money received): DEBIT the asset/bank/cash account received into, CREDIT the matching income account.
- transfer (between the user's own accounts): DEBIT the destination asset account, CREDIT the source asset account.

Rules:
- Extract the amount EXACTLY as the user stated it. Never compute, sum, or invent an amount. If no amount is stated, return an empty string.
- Choose accounts ONLY from the chart above, and ONLY when the user's note clearly points to one. Match on the account's name/purpose (e.g. "groceries" → the groceries expense account; "commercial bank" → that bank asset account).
- If the user did NOT indicate an account for a side — no bank/cash source named, or the category is unclear/ambiguous — return null for that side and lower the confidence. A null account is the correct, expected answer when the user omitted that detail. NEVER guess, and NEVER fall back to a "default" or "main" account. The user will pick it in the form.
- When a side's account id is null because nothing in the chart matches, but the transaction clearly implies what KIND of new account is needed (e.g. "Uber Eats" clearly implies a new expense account, even though no such account exists yet), populate that side's *_account_hint with a suggested name and type. Only do this when a real account is genuinely missing — never hint if an existing account already matches well enough, and never populate a hint for a side whose id is non-null. If you can't confidently suggest one, leave the hint null too.
- currency is {base_currency} (the user's own) unless the note clearly names another; each account above says which currency it is held in.
- Keep the description short and human.

User's note:
\"\"\"{text}\"\"\"
"""


class EntryParseService:
    """Free-text → draft journal entry.

    Takes an `llm_factory` rather than a prebuilt LLMPort so the adapter can be
    constructed against whichever key resolved for this request. Previously this
    service only existed when a *platform* Anthropic key was configured, which
    meant a BYOK user got a 503 from /entries/parse despite having a working key
    of their own.
    """

    def __init__(
        self, ledger: LedgerService, llm_factory: Any, credentials: Any = None, rules: Any = None
    ) -> None:
        self._ledger = ledger
        self._llm_factory = llm_factory
        self._credentials = credentials
        # The user's categorisation rules, applied after the model's draft.
        self._rules = rules

    @property
    def available(self) -> bool:
        """False only when there is no credential source at all — availability is
        now a per-user question, answered at call time."""
        return self._credentials is not None

    async def _llm_for(self, user_id: str) -> LLMPort:
        creds = await self._credentials.resolve(user_id)
        return self._llm_factory(creds.anthropic)

    async def parse_draft(self, user_id: str, text: str) -> dict[str, Any]:
        accounts = [a for a in await self._ledger.list_accounts(user_id) if a.is_active]
        base = await self._ledger.base_currency(user_id)
        chart = [
            {"id": a.id, "code": a.code, "name": a.name, "type": a.type, "currency": a.currency}
            for a in accounts
        ]
        prompt = _PROMPT.format(
            accounts=json.dumps(chart, ensure_ascii=False),
            text=text.strip(),
            base_currency=base,
        )

        llm = await self._llm_for(user_id)
        draft = await llm.extract_structured(prompt, _DRAFT_SCHEMA, model_tier="fast")

        # Guard: never let a hallucinated account id through — only ids from the chart.
        valid_ids = {a.id for a in accounts}
        for side in ("debit_account_id", "credit_account_id"):
            if draft.get(side) not in valid_ids:
                draft[side] = None

        # Guard: a hint only ever accompanies an unresolved side — if the id
        # resolved after all, drop any hint the model returned alongside it.
        for id_key, hint_key in (
            ("debit_account_id", "debit_account_hint"),
            ("credit_account_id", "credit_account_hint"),
        ):
            if draft.get(id_key) is not None:
                draft[hint_key] = None

        # Normalise the amount to a plain number string (strip commas / currency noise).
        amount = str(draft.get("amount") or "").replace(",", "").strip()
        draft["amount"] = amount
        # Only a real ISO code survives; anything else becomes the base currency.
        currency = str(draft.get("currency") or "").strip().upper()
        draft["currency"] = currency if is_currency(currency) else base
        if draft.get("entry_type") not in ("income", "expense", "transfer"):
            draft["entry_type"] = "expense"
        await self._apply_rules(user_id, text, draft, valid_ids)
        return draft

    async def _apply_rules(
        self, user_id: str, text: str, draft: dict[str, Any], valid_ids: set[str]
    ) -> None:
        """A rule that matches the note decides where the money went, over the
        model's guess: the user wrote the rule, the model only inferred. Matched
        on the note itself, which says more than the model's short description."""
        if self._rules is None:
            return
        try:
            amount = Decimal(draft["amount"])
        except (InvalidOperation, ValueError):
            return
        if amount <= 0:
            return
        facts = Facts(
            description=text,
            amount=amount,
            direction="in" if draft["entry_type"] == "income" else "out",
            currency=draft["currency"],
        )
        [rule] = await self._rules.decide(user_id, [facts])
        if rule is None:
            return
        target = rule.actions.account_id
        if target in valid_ids:
            # Expenses and transfers debit where the money went; income
            # credits where it came from.
            side = "credit" if draft["entry_type"] == "income" else "debit"
            draft[f"{side}_account_id"] = target
            draft[f"{side}_account_hint"] = None
        if rule.actions.description:
            draft["description"] = rule.actions.description
        draft["rule"] = rule.name
