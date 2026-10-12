/**
 * The sign-in's fixtures: what the server says about itself, who is signed
 * in, their profile and their sign-ins. These are not a household's books,
 * so they are written by hand; the SDK's types check their shape, so an API
 * change that moves them fails the type check.
 */
import type { AuthIdentity, Meta, Profile, SignIn } from '@leafmonkeylabs/salli-sdk';

export const ORIGIN = 'http://localhost:8000';

export const META: Meta = {
  api_version: '1',
  server_version: '0.3.1',
  extensions: [],
  oauth: {
    issuer: ORIGIN,
    authorization_endpoint: `${ORIGIN}/mcp/oauth/authorize`,
    token_endpoint: `${ORIGIN}/mcp/oauth/token`,
    registration_endpoint: `${ORIGIN}/mcp/oauth/register`,
    revocation_endpoint: `${ORIGIN}/mcp/oauth/revoke`,
    device_authorization_endpoint: `${ORIGIN}/mcp/oauth/device_authorization`,
    api_resource: `${ORIGIN}/v1`,
    device_verification_uri: `${ORIGIN}/mcp/oauth/device`,
    cli_client_id: 'salli-cli',
    console_client_id: 'salli-console',
  },
  default_currency: 'EUR',
  console_url: `${ORIGIN}/console`,
};

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
