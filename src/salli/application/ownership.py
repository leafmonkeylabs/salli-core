"""
Checks that ids a caller names belong to the caller.

Rows that point at an account (a parent account, a subscription, a budget
line) store the id they are given. The database checks at most that the
account exists (a budget line's id, in JSONB, not even that), never whose it
is. So a service checks first, or one user's row could point into another
user's ledger, and whether the save failed would say whether that account
exists.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from salli.application.ports import AccountNotFound


async def require_own_accounts(uow: Any, user_id: str, account_ids: Iterable[str | None]) -> None:
    """AccountNotFound unless every id named (None and "" ignored) is one of
    the user's accounts, active or not."""
    named = {account_id for account_id in account_ids if account_id}
    if not named:
        return
    owned = {a.id for a in await uow.ledger.get_accounts(user_id, include_inactive=True)}
    if named - owned:
        raise AccountNotFound(named - owned)
