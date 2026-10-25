"""Row-level security on every table holding a person's data.

Each such table shows and accepts a row only when its person is the one the
transaction acts for (`salli.user_id`), or the transaction is on one of the
system paths (`salli.scope = 'system'`; application/acting.py). FORCE makes
the table's owner subject to it too, so the one thing that still passes is
a superuser or a role with BYPASSRLS: on a database where Salli connects as
one (an existing install, until its role is changed: docs/self-host.md,
"The database role"), the policies are in place and nothing changes until
it does. Rows reached through another table (postings through their entry,
a posting's tags through the posting, a statement's lines through the
statement) are checked through that table's own policy. No column changes.

Revision ID: core_0051_row_security
Revises: core_0050_app_grant_lifetime
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "core_0051_row_security"
down_revision: str | None = "core_0050_app_grant_lifetime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Tables with the person in `user_id`.
_BY_USER_ID = (
    "accounts", "advisory_reports", "agent_documents", "agent_sessions", "ai_connections",
    "audit_logs", "bank_connection_accounts", "bank_connections", "budgets",
    "categorization_rules", "cma_packs", "debts", "decision_notes", "decision_reviews",
    "decisions", "documents", "fi_goals", "fi_scores", "fire_strategies", "goal_allocations",
    "holding_prices", "holding_transactions", "holdings", "insurance_targets",
    "investment_policies", "journal_entries", "login_sessions", "logins", "mcp_client_refs",
    "notification_deliveries", "notification_preferences", "oauth_access_tokens",
    "oauth_authorization_codes", "oauth_device_codes", "oauth_grants", "oauth_refresh_tokens",
    "personal_access_tokens", "policies", "principles", "push_devices", "reconciliations",
    "recurring_subscriptions", "reminders", "statements", "tags", "tax_computations",
    "tax_return_payments", "tax_returns", "tax_rule_set_versions", "tax_rule_sets",
    "user_llm_credentials",
)  # fmt: skip

#: The other tables, and whose rows they are.
_OTHERS = {
    "user_profiles": "salli_row_visible(id)",
    "access_grants": "salli_row_visible(grantor_id) OR salli_row_visible(grantee_id)",
    "postings": "EXISTS (SELECT 1 FROM journal_entries e WHERE e.id = entry_id)",
    "posting_tags": "EXISTS (SELECT 1 FROM postings p WHERE p.id = posting_id)",
    "parsed_transactions": "EXISTS (SELECT 1 FROM statements s WHERE s.id = statement_id)",
}

_VISIBLE = """
CREATE FUNCTION salli_row_visible(owner varchar) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT coalesce(current_setting('salli.scope', true), '') = 'system'
        OR owner = nullif(current_setting('salli.user_id', true), '')
$$
"""


def _secure(table: str, check: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"CREATE POLICY person_rows ON {table} USING ({check}) WITH CHECK ({check})")


def upgrade() -> None:
    op.execute(_VISIBLE)
    for table in _BY_USER_ID:
        _secure(table, "salli_row_visible(user_id)")
    for table, check in _OTHERS.items():
        _secure(table, check)


def downgrade() -> None:
    for table in (*_BY_USER_ID, *_OTHERS):
        op.execute(f"DROP POLICY person_rows ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION salli_row_visible(varchar)")
