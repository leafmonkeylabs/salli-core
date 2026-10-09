"""
Guards account deletion against the failure mode where someone adds a
user-scoped table and forgets `delete_all`.

`SQLDataPortabilityRepository.delete_all` is a hand-enumerated list of
`_delete(...)` calls, so a new table is NOT covered just by existing — it
silently survives "delete my account", which is a data-protection problem
rather than a cosmetic one. Reflecting over the ORM metadata turns that from
"hope someone remembers" into a failing test.

Deliberately asserts on the SOURCE of delete_all rather than running it: the
alternative needs a live Postgres, and this catches the omission at the point
it's introduced instead of in an integration suite.
"""

from __future__ import annotations

import inspect

from salli.adapters.db import models
from salli.adapters.db.repositories import SQLDataPortabilityRepository

# Tables whose rows are not keyed to one user, or are deleted transitively via
# an ON DELETE CASCADE from a table that IS listed. Each entry needs a reason.
_EXEMPT: dict[str, str] = {
    # Cascade-deleted by their parent entry/statement.
    "postings": "ON DELETE CASCADE from journal_entries.id",
    "parsed_transactions": "deleted explicitly by statement_id before journal_entries",
    # Not user-scoped.
    "oauth_clients": "per-client registration, shared across users",
}


def _user_scoped_tables() -> set[str]:
    return {
        table.name
        for table in models.Base.metadata.tables.values()
        if "user_id" in table.columns or table.name == "user_profiles"
    }


def test_delete_all_covers_every_user_scoped_table() -> None:
    source = inspect.getsource(SQLDataPortabilityRepository.delete_all)

    missing = []
    for name in sorted(_user_scoped_tables()):
        if name in _EXEMPT:
            continue
        orm = next(
            (
                obj.__name__
                for obj in vars(models).values()
                if inspect.isclass(obj)
                and hasattr(obj, "__tablename__")
                and obj.__tablename__ == name
            ),
            None,
        )
        if orm is None or orm not in source:
            missing.append(name)

    assert not missing, (
        "These user-scoped tables are not deleted by delete_all, so they would "
        f"survive account deletion: {missing}. Add an `await _delete(...)` line, "
        "or add the table to _EXEMPT here with the reason it's safe."
    )


def test_byok_credentials_are_deleted_with_the_account() -> None:
    """Called out separately because it holds a decryptable third-party secret —
    the one table where surviving deletion is worst."""
    source = inspect.getsource(SQLDataPortabilityRepository.delete_all)
    assert "UserLlmCredentialORM" in source


def test_chatgpt_connections_are_deleted_with_the_account() -> None:
    """The other table that holds a decryptable credential: a ChatGPT plan's
    sealed tokens."""
    source = inspect.getsource(SQLDataPortabilityRepository.delete_all)
    assert "AiConnectionORM" in source
