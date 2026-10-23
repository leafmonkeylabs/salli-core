/**
 * The sign-in's fixtures: what the server says about itself, who is signed
 * in, their profile and their sign-ins. These are not a household's books,
 * so they are written by hand; the SDK's types check their shape, so an API
 * change that moves them fails the type check.
 */
import type { AuthIdentity, DataExport, McpConnection, Meta, Profile, SignIn } from '@leafmonkeylabs/salli-sdk';

export const ORIGIN = 'http://localhost:8000';

/** What `/v1/meta` says on a server whose SALLI_PUBLIC_URL is `origin`. */
export function metaAt(origin: string, extensions: string[] = []): Meta {
  return {
    api_version: '1',
    server_version: '0.3.1',
    extensions,
    oauth: {
      issuer: origin,
      authorization_endpoint: `${origin}/mcp/oauth/authorize`,
      token_endpoint: `${origin}/mcp/oauth/token`,
      registration_endpoint: `${origin}/mcp/oauth/register`,
      revocation_endpoint: `${origin}/mcp/oauth/revoke`,
      device_authorization_endpoint: `${origin}/mcp/oauth/device_authorization`,
      api_resource: `${origin}/v1`,
      device_verification_uri: `${origin}/mcp/oauth/device`,
      cli_client_id: 'salli-cli',
      console_client_id: 'salli-console',
      mobile_client_id: 'salli-mobile',
      mobile_redirect_uri: 'money.salli.app:/oauth/callback',
    },
    default_currency: 'EUR',
    console_url: `${origin}/console`,
  };
}

export const META: Meta = metaAt(ORIGIN);

export const ME: AuthIdentity = {
  user_id: 'household',
  email: 'ana@example.org',
  method: 'oauth',
  permissions: [],
};

export const SOMEONE_ELSE: AuthIdentity = {
  user_id: 'someone-else',
  email: 'bo@example.org',
  method: 'oauth',
  permissions: [],
};

export const PROFILE: Profile = {
  id: 'household',
  email: 'ana@example.org',
  display_name: 'Ana',
  base_currency: 'EUR',
  date_of_birth: null,
  dependents_count: null,
  employment_status: null,
  residency_status: null,
  employer: null,
  employment_type: null,
  risk_score: null,
  risk_category: null,
  life_stage: null,
  mcp_enabled: true,
  daily_briefing_enabled: false,
  preferred_model: null,
  tax_residency: 'PT',
  tax_ids: [],
  time_zone: 'Europe/Lisbon',
};

export const SIGN_INS: SignIn[] = [
  {
    id: 'grant-console-1',
    kind: 'console',
    client_name: 'Salli console',
    user_agent: null,
    started_at: '2026-10-11T08:00:00+00:00',
    last_used_at: '2026-10-11T09:30:00+00:00',
    expires_at: '2026-10-11T20:00:00+00:00',
    current: true,
  },
  {
    id: 'grant-cli-1',
    kind: 'cli',
    client_name: 'salli',
    user_agent: null,
    started_at: '2026-09-01T10:00:00+00:00',
    last_used_at: '2026-10-10T18:12:00+00:00',
    expires_at: null,
    current: false,
  },
  {
    id: 'session-1',
    kind: 'session',
    client_name: null,
    user_agent: 'curl/8.7.1',
    started_at: '2026-10-02T12:00:00+00:00',
    last_used_at: null,
    expires_at: '2026-11-01T12:00:00+00:00',
    current: false,
  },
];

/**
 * The AI clients connected over MCP. Like the sign-ins, they are how
 * someone reaches the books, not the books, so they are written here by
 * hand, typed by the SDK.
 */
export const MCP_CONNECTIONS: McpConnection[] = [
  {
    token_id: 'mcp-token-1',
    client_id: 'client-claude',
    client_name: 'Claude',
    scope: 'salli',
    connected_at: '2026-09-20T18:04:00+00:00',
  },
];

/**
 * "My data" (`account.export`), cut down to the person and two accounts,
 * with an amount a float can't hold: the console saves exactly what Salli
 * sent, never a figure changed on the way.
 */
export const MY_DATA: DataExport = {
  user_id: 'household',
  profile: PROFILE,
  accounts: [
    { id: 'chk', code: '1000', name: 'Checking', type: 'asset', currency: 'EUR', parent_id: null, is_active: true, tax_role: null },
    { id: 'eq', code: '3000', name: 'Opening equity', type: 'equity', currency: 'EUR', parent_id: null, is_active: true, tax_role: null },
  ],
  journal_entries: [
    {
      id: 'e001',
      entry_date: '2026-03-31',
      description: 'Opening balance',
      source: 'manual',
      external_ref: null,
      reversed_by: null,
      postings: [
        { account_id: 'chk', direction: 'DEBIT', amount: '9007199254740993.01', currency: 'EUR' },
        { account_id: 'eq', direction: 'CREDIT', amount: '9007199254740993.01', currency: 'EUR' },
      ],
    },
  ],
  budgets: [],
  debts: [],
  holdings: [],
  recurring_subscriptions: [],
  insurance_policies: [],
  insurance_targets: [],
  goals: [],
  fi_score_history: [],
  advisor_reports: [],
  reminders_and_alerts: [],
  documents: [],
};
