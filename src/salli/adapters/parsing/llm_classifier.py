"""
LLM-based transaction classifier.

Given a list of RawRows and the user's chart of accounts, asks the model
to assign a debit account and credit account to each transaction. When the
statement says which account the rows are on (the money side), the model is
told so and chooses only the other account.

The LLM never invents amounts — it only assigns accounts from the provided list.
Transactions where the model is uncertain get confidence < 0.7 and are flagged
for manual review. The caller still checks every id it returns against the chart.
"""

from __future__ import annotations

import json
from typing import Any

from salli.domain.ai_models import EXTRACTION_MODEL
from salli.domain.parsing.models import ParsedTransaction, RawRow

_CLASSIFICATION_PROMPT = """\
You are a bookkeeping assistant. Classify each bank transaction by assigning the
correct debit and credit accounts from the provided chart of accounts.

RULES:
1. Only use account IDs from the provided list, never invent an account.
2. For money RECEIVED (credit_flag=true): debit a bank/cash account, credit an income account.
3. For money PAID (credit_flag=false): debit an expense/asset/liability account, credit a bank/cash account.
4. If you cannot determine the correct accounts, set confidence < 0.5 and use the most plausible accounts.
5. Return ONLY a JSON array with one object per transaction.

CHART OF ACCOUNTS:
{accounts_json}

TRANSACTIONS TO CLASSIFY:
{transactions_json}

Return a JSON array. Each element must have:
  - "index": the transaction index (0-based, matching the input order)
  - "debit_account_id": account ID from the chart above
  - "credit_account_id": account ID from the chart above
  - "category": short label (e.g. "salary", "bank_charge", "transfer", "interest")
  - "confidence": float 0.0–1.0

Return ONLY the JSON array. No prose, no markdown fences.
"""

_COUNTER_PROMPT = """\
You are a bookkeeping assistant. Every transaction below moved money in or out
of one account: {money_json}. Money RECEIVED (credit_flag=true) was paid into
it; money PAID (credit_flag=false) was paid out of it.

For each transaction, choose the OTHER account of the double entry from the
chart of accounts: where money received came from (usually an income account),
or where money paid went (usually an expense account; another asset or a
liability for a transfer, a saving or a card payment).

RULES:
1. Only use account IDs from the chart below; never invent one, and never choose {money_id}.
2. If you cannot determine the account, set confidence < 0.5 and give the most plausible one.
3. Return ONLY a JSON array with one object per transaction.

CHART OF ACCOUNTS:
{accounts_json}

TRANSACTIONS TO CLASSIFY:
{transactions_json}

Return a JSON array. Each element must have:
  - "index": the transaction index (0-based, matching the input order)
  - "account_id": the other account's ID, from the chart above
  - "category": short label (e.g. "salary", "bank_charge", "transfer", "interest")
  - "confidence": float 0.0–1.0

Return ONLY the JSON array. No prose, no markdown fences.
"""


async def classify_transactions(
    raw_rows: list[RawRow],
    accounts: list[Any],
    *,
    api_key: Any,
    money_account: Any = None,
    batch_size: int = 30,
) -> list[ParsedTransaction]:
    """
    Classify raw rows into ParsedTransactions using Claude, one per row, in order.
    Batches to stay within context limits.

    `money_account` is the account every row is on, when the statement says:
    the model then chooses only the other side, and the money side is that account.
    """
    import anthropic

    from salli.domain.agents.model_factory import reveal

    # Explicit key, not the SDK's zero-arg environment lookup: statement
    # classification must bill whoever's key resolved for this request.
    client = anthropic.AsyncAnthropic(api_key=reveal(api_key))

    accounts_json = json.dumps(
        [{"id": a.id, "code": a.code, "name": a.name, "type": a.type} for a in accounts]
    )

    results: list[ParsedTransaction] = []

    for batch_start in range(0, len(raw_rows), batch_size):
        batch = raw_rows[batch_start : batch_start + batch_size]
        txn_json = json.dumps(
            [
                {
                    "index": batch_start + i,
                    "date": r.date,
                    "description": r.description,
                    "amount": str(r.amount),
                    "credit_flag": r.credit_flag,
                    "bank_ref": r.bank_ref,
                }
                for i, r in enumerate(batch)
            ]
        )

        if money_account is None:
            prompt = _CLASSIFICATION_PROMPT.format(
                accounts_json=accounts_json,
                transactions_json=txn_json,
            )
        else:
            prompt = _COUNTER_PROMPT.format(
                money_json=json.dumps(
                    {"id": money_account.id, "name": money_account.name, "type": money_account.type}
                ),
                money_id=money_account.id,
                accounts_json=accounts_json,
                transactions_json=txn_json,
            )

        message = await client.messages.create(
            # Pinned to the extraction model: bulk classification is mechanical,
            # and the usage meter is never told a model for statement imports
            # on that basis (see routers/statements.py). Changing this without
            # changing that would meter one model and run another.
            model=EXTRACTION_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        block = message.content[0]
        raw_text = block.text.strip() if hasattr(block, "text") else ""  # type: ignore[union-attr]
        classifications = _parse_response(raw_text)

        for i, row in enumerate(batch):
            clf = classifications.get(batch_start + i, {})
            if money_account is None:
                debit = clf.get("debit_account_id") or ""
                credit = clf.get("credit_account_id") or ""
            else:
                counter = clf.get("account_id") or ""
                debit, credit = (
                    (money_account.id, counter) if row.credit_flag else (counter, money_account.id)
                )
            results.append(
                ParsedTransaction(
                    raw=row,
                    debit_account_id=str(debit),
                    credit_account_id=str(credit),
                    category=str(clf.get("category") or ""),
                    confidence=_confidence(clf.get("confidence", 0.5)),
                )
            )

    return results


def _confidence(value: Any) -> float:
    """The model's confidence as a number in 0..1; 0.5 when it gave none usable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    return min(max(number, 0.0), 1.0) if number == number else 0.5  # NaN is not equal to itself


def _parse_response(text: str) -> dict[int, dict[str, Any]]:
    """Parse LLM JSON response; returns {index: classification_dict}."""
    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(text.splitlines()[1:])
        text = text.rstrip("`").strip()

    try:
        items = json.loads(text)
        if not isinstance(items, list):
            return {}
        return {int(item["index"]): item for item in items if "index" in item}
    except (json.JSONDecodeError, KeyError, ValueError):
        return {}
