"""
What an MCP connection may do: read always; change only with `mcp:write`,
checked in one place for every tool that isn't read-only. Every call of one
is audited with the person, the client, the tool, its arguments and the
outcome, never a decision nobody made; every read with the tool, the client
and the outcome.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types

from salli.application.unit_of_work import AuditRecord, UnitOfWork, pending_audit
from salli.interfaces.api import mcp_server

pytestmark = pytest.mark.asyncio


@pytest.fixture
def services():
    services = MagicMock()
    services.reminders = AsyncMock()
    services.reminders.create_reminder.return_value = "r1"
    services.documents = AsyncMock()
    services.documents.get_memory.return_value = {"content": "Ana", "updated_at": None}
    audit = SimpleNamespace(log=AsyncMock())
    unit = MagicMock()
    unit.__aenter__ = AsyncMock(return_value=SimpleNamespace(audit_log=audit))
    unit.__aexit__ = AsyncMock(return_value=False)
    services.ledger._uow_factory = MagicMock(return_value=unit)
    services.audit = audit
    return services


async def _request(services, tool: str, args: dict, scopes: list[str]) -> types.CallToolResult:
    """A tools/call as a client sends it, on a connection with `scopes`."""
    server = mcp_server.build_mcp_server(services, "https://api.test")
    handler = server._mcp_server.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        method="tools/call", params=types.CallToolRequestParams(name=tool, arguments=args)
    )
    with (
        patch.object(mcp_server, "_current_user_id", return_value="u1"),
        patch.object(mcp_server, "_current_client_id", return_value="claude-1"),
        patch.object(mcp_server, "_current_scopes", return_value=scopes),
    ):
        result = await handler(request)
    return result.root


REMINDER = {"description": "Renew the lease", "due_date": "2027-03-01"}


@pytest.mark.parametrize("scopes", [[], ["mcp:read"], ["salli"]])
async def test_a_write_on_a_read_only_connection_is_refused_and_does_nothing(services, scopes):
    result = await _request(services, "create_reminder", REMINDER, scopes)

    assert result.isError is True
    [text] = result.content
    assert isinstance(text, types.TextContent)
    assert "can only read" in text.text and "Allow changes" in text.text
    assert result.structuredContent is not None
    assert result.structuredContent["error"]["code"] == "scope"
    services.reminders.create_reminder.assert_not_awaited()
    services.audit.log.assert_awaited_once_with(
        "u1", "create_reminder", REMINDER, "refused", client_id="claude-1"
    )


async def test_a_write_with_the_write_scope_is_made_and_audited(services):
    result = await _request(services, "create_reminder", REMINDER, ["mcp:read", "mcp:write"])

    assert result.isError is False
    services.reminders.create_reminder.assert_awaited_once_with(
        "u1", "Renew the lease", "2027-03-01"
    )
    services.audit.log.assert_awaited_once_with(
        "u1", "create_reminder", REMINDER, "succeeded", client_id="claude-1"
    )


async def test_a_write_that_fails_is_audited_as_failed(services):
    services.reminders.create_reminder.side_effect = RuntimeError("the store is down")
    result = await _request(services, "create_reminder", REMINDER, ["mcp:write"])

    assert result.isError is True
    assert services.audit.log.await_args.args[3] == "failed"


@pytest.mark.parametrize("scopes", [[], ["mcp:read"]])
async def test_reads_need_no_scope_and_are_audited_without_their_arguments(services, scopes):
    result = await _request(services, "get_memory", {"slug": "accountant_name"}, scopes)

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["value"] == {"untrusted_text": "Ana"}
    services.audit.log.assert_awaited_once_with(
        "u1", "get_memory", {}, "succeeded", client_id="claude-1"
    )


async def test_a_read_that_fails_is_audited_as_failed(services):
    services.documents.get_memory.side_effect = RuntimeError("the store is down")
    result = await _request(services, "get_memory", {"slug": "accountant_name"}, [])

    assert result.isError is True
    services.audit.log.assert_awaited_once_with(
        "u1", "get_memory", {}, "failed", client_id="claude-1"
    )


async def test_a_read_whose_audit_row_cant_be_written_is_not_answered(services):
    services.audit.log.side_effect = RuntimeError("audit_logs refused it")
    result = await _request(services, "get_memory", {"slug": "accountant_name"}, [])

    assert result.isError is True
    assert result.structuredContent is None


async def test_every_tool_that_is_not_read_only_is_gated(services):
    """Fail closed: a tool with no readOnlyHint counts as a write."""
    server = mcp_server.build_mcp_server(services, "https://api.test")
    writes = [
        t.name
        for t in await server.list_tools()
        if t.annotations is None or t.annotations.readOnlyHint is not True
    ]
    assert {"post_journal_entry", "delete_document", "discard_transactions", "create_rule"} <= set(
        writes
    )
    for name in writes:
        services.audit.log.reset_mock()
        result = await _request(services, name, {}, ["mcp:read"])
        assert result.isError is True, name
        assert services.audit.log.await_args.args[3] == "refused", name


async def test_secrets_never_reach_the_audit_log():
    assert mcp_server._redacted({"api_key": "sk-1", "Password": "pw", "slug": "x"}) == {
        "api_key": "[redacted]",
        "Password": "[redacted]",
        "slug": "x",
    }


def _session(changed: object, *, audit_fails: bool = False) -> MagicMock:
    session = MagicMock()
    flushes: list[object] = [None, RuntimeError("audit_logs refused it")] if audit_fails else []
    session.flush = AsyncMock(side_effect=flushes or None)
    session.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=changed)))
    session.commit, session.rollback, session.close = AsyncMock(), AsyncMock(), AsyncMock()
    return session


async def _in_unit(session: MagicMock, record: AuditRecord) -> None:
    token = pending_audit.set(record)
    try:
        async with UnitOfWork(MagicMock(return_value=session)):
            pass
    finally:
        pending_audit.reset(token)


async def test_a_change_is_audited_in_the_transaction_that_makes_it():
    session = _session(changed=812)
    record = AuditRecord("u1", "claude-1", "create_rule", {"name": "Rent"})
    await _in_unit(session, record)

    assert record.recorded
    [row] = [c.args[0] for c in session.add.call_args_list]
    assert (row.action, row.decision, row.client_id) == ("create_rule", "succeeded", "claude-1")
    session.commit.assert_awaited_once()


async def test_a_transaction_that_changed_nothing_writes_no_row():
    session = _session(changed=None)
    record = AuditRecord("u1", "claude-1", "create_rule", {})
    await _in_unit(session, record)

    assert not record.recorded
    session.add.assert_not_called()
    session.commit.assert_awaited_once()


async def test_a_change_whose_audit_row_cant_be_written_is_not_made():
    session = _session(changed=812, audit_fails=True)
    record = AuditRecord("u1", "claude-1", "create_rule", {})
    with pytest.raises(RuntimeError, match="audit_logs refused it"):
        await _in_unit(session, record)

    assert not record.recorded
    session.commit.assert_not_awaited()
    session.close.assert_awaited_once()  # closing rolls the change back
