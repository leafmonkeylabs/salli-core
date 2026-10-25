"""
Erasing an account deletes the rows first, in their one transaction, then the
person's uploaded files and their conversations with the AI; a part that
can't be deleted is logged by its type and said in the counts.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from salli.application.services.data_portability_service import DataPortabilityService

pytestmark = pytest.mark.asyncio

USER = "0b8f3c1e-5d2a-4f6b-9c7e-1a2b3c4d5e6f"


def _service(order: list[str], storage: Any, conversations: Any) -> DataPortabilityService:
    class Rows:
        async def delete_all(self, user_id: str, *_: Any) -> dict[str, int]:
            order.append("rows")
            return {"accounts": 2}

    class NoLogins:
        async def get(self, user_id: str) -> None:
            return None

    class UoW:
        data_portability = Rows()
        logins = NoLogins()

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *exc: object) -> None:
            order.append("commit")

    class Profiles:
        def forget(self, user_id: str) -> None:
            order.append("forget")

    return DataPortabilityService(
        UoW,
        Profiles(),
        *([None] * 11),
        storage=storage,
        conversations=conversations,
    )


class Store:
    """A store of files or of conversations: deletes and says how many."""

    def __init__(self, name: str, order: list[str], count: int = 0, fails: bool = False) -> None:
        self._name, self._order, self._count, self._fails = name, order, count, fails

    async def _delete(self, user_id: str) -> int:
        assert user_id == USER
        self._order.append(self._name)
        if self._fails:
            raise OSError(f"permission denied: /storage/{USER}/salary.pdf")
        return self._count

    delete_user = _delete
    delete_all = _delete


async def test_rows_go_first_then_files_then_conversations():
    order: list[str] = []
    service = _service(order, Store("files", order, 3), Store("conversations", order, 2))

    counts = await service.delete_account(USER)

    assert order == ["rows", "commit", "forget", "files", "conversations"]
    assert counts == {"accounts": 2, "stored_files": 3, "conversations": 2}


async def test_a_part_that_fails_is_said_and_the_rest_still_goes(caplog):
    order: list[str] = []
    service = _service(order, Store("files", order, fails=True), Store("conversations", order, 2))

    with caplog.at_level(logging.WARNING):
        counts = await service.delete_account(USER)

    assert order == ["rows", "commit", "forget", "files", "conversations"]
    assert counts == {"accounts": 2, "stored_files_failed": 1, "conversations": 2}
    # By its type only: the message names the person's file.
    assert "OSError" in caplog.text
    assert "salary.pdf" not in caplog.text


async def test_failed_conversations_are_said_too():
    order: list[str] = []
    service = _service(order, Store("files", order, 1), Store("conversations", order, fails=True))

    counts = await service.delete_account(USER)

    assert counts == {"accounts": 2, "stored_files": 1, "conversations_failed": 1}


async def test_without_storage_or_a_checkpointer_only_rows_are_counted():
    order: list[str] = []

    counts = await _service(order, None, None).delete_account(USER)

    assert counts == {"accounts": 2}
