"""The audit trail of AI connections' writes, against a real database:

- a write and its audit row commit together: a change whose row can't be
  written is not made;
- the audit log is append-only: the database refuses an UPDATE, DELETE or
  TRUNCATE, except pseudonymising the user's own rows as their account is
  erased;
- its rows form one hash chain, which still verifies after an erasure.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from salli.application.services.ledger_service import LedgerService
from salli.application.unit_of_work import AuditRecord, pending_audit
from tests.integration.pg import _sync, requires_postgres, scalar

pytestmark = [requires_postgres, pytest.mark.asyncio]


async def _while_pending(record: AuditRecord, write):
    token = pending_audit.set(record)
    try:
        return await write
    finally:
        pending_audit.reset(token)


async def test_a_write_is_audited_in_its_own_transaction(uow_factory, db):
    ledger = LedgerService(uow_factory)
    async with uow_factory() as uow:
        await uow.user_profiles.upsert("ana", {"base_currency": "EUR"})
    record = AuditRecord("ana", "claude-1", "create_account", {"code": "1000"})
    await _while_pending(record, ledger.add_account("ana", "1000", "Cash", "asset"))

    assert record.recorded
    async with uow_factory() as uow:
        [row] = await uow.audit_log.list("ana")
    assert (row["action"], row["decision"], row["client_id"], row["params"]) == (
        "create_account",
        "succeeded",
        "claude-1",
        {"code": "1000"},
    )

    # A row that can't be written (a client id longer than its column) takes
    # the change down with it.
    broken = AuditRecord("ana", "c" * 65, "create_account", {"code": "2000"})
    with pytest.raises(Exception, match="too long"):
        await _while_pending(broken, ledger.add_account("ana", "2000", "Savings", "asset"))
    assert not broken.recorded
    assert scalar(db, "select count(*) from accounts where code = '2000'") == 0
    assert scalar(db, "select count(*) from audit_logs") == 1


async def test_reads_write_no_audit_row(uow_factory, db):
    ledger = LedgerService(uow_factory)
    record = AuditRecord("ana", "claude-1", "list_accounts", {})
    await _while_pending(record, ledger.list_accounts("ana"))
    assert not record.recorded
    assert scalar(db, "select count(*) from audit_logs") == 0


@pytest.mark.parametrize(
    "statement",
    [
        "update audit_logs set decision = 'succeeded'",
        "update audit_logs set params = '{}'::jsonb",
        "delete from audit_logs",
        "truncate audit_logs",
        "update audit_logs set user_id = 'erased:x'",
    ],
)
async def test_the_database_refuses_to_change_the_audit_log(uow_factory, db, statement):
    async with uow_factory() as uow:
        await uow.audit_log.log("ana", "delete_document", {"doc_id": "d1"}, "refused", "claude-1")
    engine = create_engine(_sync(db))
    try:
        with pytest.raises(Exception, match="append-only"), engine.begin() as conn:
            conn.execute(text(statement))
        # Not even while erasing someone else's account.
        with pytest.raises(Exception, match="append-only"), engine.begin() as conn:
            conn.execute(text("select set_config('salli.erase_user', 'ben', true)"))
            conn.execute(text("update audit_logs set user_id = 'erased:x', params = '{}'"))
    finally:
        engine.dispose()
    assert scalar(db, "select decision from audit_logs") == "refused"


async def test_erasing_an_account_pseudonymises_its_audit_rows_and_no_one_elses(uow_factory, db):
    async with uow_factory() as uow:
        await uow.audit_log.log("ana", "create_rule", {"name": "Rent"}, "succeeded", "claude-1")
        await uow.audit_log.log("ben", "create_rule", {"name": "Rent"}, "succeeded", "claude-2")
        await uow.audit_log.log("f" * 64, "sign_in", {}, "refused")
    async with uow_factory() as uow:
        counts = await uow.data_portability.delete_all("ana", "erased:abc", ["f" * 64])
    assert counts["audit_logs_pseudonymised"] == 2
    assert scalar(db, "select count(*) from audit_logs") == 3
    assert scalar(db, "select count(*) from audit_logs where user_id = 'erased:abc'") == 2
    assert scalar(db, "select params::text from audit_logs where seq = 1") == "{}"
    assert scalar(db, "select params::text from audit_logs where user_id = 'ben'") != "{}"
    async with uow_factory() as uow:
        assert (await uow.audit_log.verify())["ok"]


async def test_the_chain_names_the_first_changed_row(uow_factory, db):
    async with uow_factory() as uow:
        for name in ("Rent", "Food", "Fuel"):
            await uow.audit_log.log("ana", "create_rule", {"name": name}, "succeeded")
    async with uow_factory() as uow:
        check = await uow.audit_log.verify()
    assert check == {"ok": True, "checked": 3, "first_break": None}
    engine = create_engine(_sync(db))
    try:
        with engine.begin() as conn:
            conn.execute(text("alter table audit_logs disable trigger trg_audit_logs_append_only"))
            conn.execute(text('update audit_logs set params = \'{"name": "Gift"}\' where seq = 2'))
            conn.execute(text("alter table audit_logs enable trigger trg_audit_logs_append_only"))
    finally:
        engine.dispose()
    async with uow_factory() as uow:
        check = await uow.audit_log.verify()
    assert (check["checked"], check["first_break"]["seq"], check["first_break"]["reason"]) == (
        1,
        2,
        "content",
    )
