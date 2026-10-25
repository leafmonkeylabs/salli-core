# Security: threat model and controls

What Salli protects, where its trust boundaries are, and which controls it
has today, each with the file that implements it. Rows marked **not yet** are
gaps we know about. What personal data Salli keeps and who else sees it is in
[privacy.md](privacy.md); how to report a vulnerability is in
[SECURITY.md](../SECURITY.md); how an operator runs an instance safely is in
[self-host.md](self-host.md#security).

## Assets

- **People's books and plans:** accounts, journal entries, statements,
  holdings, debts, goals, decisions and principles, tax rule sets and
  computations, and the profile (date of birth, employer, tax residency and
  tax ids).
- **Credentials:** password hashes; hashes of sessions, personal access
  tokens and OAuth tokens; and three secrets Salli has to read back, sealed
  with AES-GCM: people's own AI provider keys, their ChatGPT plan sign-in and
  their bank feed's access URL.
- **The instance's secrets:** `BYOK_ENCRYPTION_KEYS` (opens the sealed
  secrets), `MCP_SIGNING_SECRET`, `CRON_SECRET` and the database password, in
  `SALLI_SECRETS_DIR` or `.env`.
- **The figures' integrity:** that every entry balances, that a posted entry
  and a recorded decision stay as they were, and that tax is computed only by
  a rule set the person activated.
- **What we publish:** the container image, the npm packages and the CLI's
  binaries.

## Trust boundaries

| Boundary | On the other side | What Salli does at it |
|---|---|---|
| Browser | The console, a page that injected script would aim at | Strict CSP with Trusted Types, no framing, no third-party request (`interfaces/api/console.py`); PKCE sign-in, the access token in memory only, idle sign-out after 30 minutes (`packages/console/src/auth/session.ts`); no cookies; CORS trusts no origin unless `ALLOWED_ORIGINS` names it (`config.py`). |
| Phone | The Salli app on a device Salli doesn't control | PKCE through an exactly matched private-use redirect (`mcp_oauth_service.py`); the sign-in in the device's secure store, readable only while unlocked (`packages/mobile/src/session.tsx`). The person's AI key stays on the phone (`packages/mobile/src/ai/store.tsx`), which calls their provider directly. |
| CLI | A terminal, often beside an agent | PKCE with a loopback redirect; tokens in the OS keychain, or a mode-0600 file without one (`packages/cli/src/auth/store.ts`). |
| MCP clients | AI connectors the person adds | OAuth 2.1 with PKCE; the person's MCP switch is checked on every call (`mcp_oauth_service.py`); MCP tokens are refused by the REST API and never hold `tax:activate` (`application/permissions.py`); a connection reads, and changes anything only with `mcp:write`, which the person ticks on the consent page; every MCP write, refused or not, is in the audit log (`interfaces/api/mcp_server.py`). |
| AI providers | Anthropic, OpenAI or a ChatGPT plan, as configured | Sends what [privacy.md](privacy.md#who-else-sees-it) lists. Model output is untrusted: it never computes money, tool calls act only as the signed-in person (`domain/agents/tools.py`), writes wait for the person's approval, and a briefing with a digit or advice is refused (`domain/agents/briefing.py`). |
| The open web | Pages an agent searches or a person asks Salli to fetch | Requests to a person's URL go only to public addresses over HTTPS, with size and time limits (`adapters/net/guard.py`, `adapters/net/fetch.py`). An agent that reads a planted instruction still can't activate a tax rule set. |
| Bank feed | A SimpleFIN bridge | Read-only; the pasted setup URL is vetted like any other; the access URL is sealed with AES-GCM bound to its row (`adapters/banks/simplefin.py`, `bank_connection_service.py`). |
| Exchange rates | Frankfurter, then ExchangeRate-API | Currency codes and a date only; no rate is invented (`adapters/fx/`). |
| Operator | Whoever runs the server | Trusted with everything: the database, the files and the secrets. There is no sign-up: the owner adds members (`salli-server members`). `salli-server doctor` prints no secrets. |
| Supply chain | Dependencies, actions, base images, registries | See the controls below. |

## Controls

Mapped to the SOC 2 Trust Services Criteria at a high level: CC is the
common criteria, C confidentiality, PI processing integrity, P privacy.

| Control | What Salli does | Where | Criteria |
|---|---|---|---|
| Passwords | argon2id (RFC 9106: 64 MiB, three passes, four lanes), rehashed when the parameters change; at least 12 characters | `adapters/auth/passwords.py`, `application/services/login_service.py` | CC6.1 |
| Two-step sign-in | Optional per person: once on, every password check (the sign-in, consent and device pages, so the step-up too; a session; changing the password) also needs an authenticator app's code (RFC 6238, each used once) or one of ten single-use recovery codes, kept as hashes; the app's secret is sealed like the secrets below; wrong codes are throttled like wrong passwords; turning it on or off goes through the step-up, and off needs the password and a code; the owner can clear it (`members reset-password --clear-totp`) | `application/totp.py`, `application/services/login_service.py`, `routers/auth.py` | CC6.1 |
| Sign-in throttling | 5 failures an email or 50 an address in 15 minutes refuse further sign-ins unchecked; counted by hashes, so the count reveals no account | `application/services/login_service.py` | CC6.1 |
| Hashed tokens | Sessions, personal access tokens and OAuth tokens are random and stored only as SHA-256 hashes | `login_service.py`, `personal_access_token_service.py`, `mcp_oauth_service.py` | CC6.1 |
| OAuth | PKCE (S256 only); the console's and the app's redirects matched exactly, the CLI's to loopback only; refresh tokens rotate, and a reused one revokes its whole grant | `application/services/mcp_oauth_service.py` | CC6.1, CC7.2 |
| Step-up | Activating tax rules needs a password checked in the last five minutes in the console and the app; AI connectors never can | `application/permissions.py` | CC6.1, CC6.3 |
| Scoped tokens | A personal access token holds only the permissions it was made with, and no sign-in can mint one more capable than itself | `application/permissions.py`, `personal_access_token_service.py` | CC6.3 |
| MCP scopes | An AI connection reads (`mcp:read`); every tool that isn't read-only needs `mcp:write`, checked in one place, and is refused and does nothing without it. The consent page offers it unticked; only the Salli app's own AI holds it by default, as the app asks the person before each change. Grants from before the scopes only read | `interfaces/api/mcp_server.py`, `mcp_oauth_service.py`, `routers/mcp_consent_page.py` | CC6.3 |
| Accounts and sign-ins | No sign-up; the owner adds members and resets passwords; a person lists and ends every sign-in (`/v1/auth/sign-ins`) and AI connection (`/v1/mcp/connections`) | `interfaces/cli/setup.py`, `interfaces/api/routers/auth.py`, `routers/mcp_oauth.py` | CC6.2 |
| Sealed secrets | AI keys, ChatGPT sign-ins, bank feed URLs and authenticator secrets sealed with AES-GCM, bound to their user and row; versioned keys for rotation; without a key Salli refuses to store one rather than keep it in plain text | `adapters/crypto/keyring.py` | CC6.1, C1.1 |
| Web hardening | CSP with Trusted Types, `frame-ancestors 'none'`, `no-referrer`, `Cache-Control: no-store` on API responses | `interfaces/api/console.py` | CC6.6 |
| Outbound requests | Public addresses only, connecting to the address checked (no DNS rebinding), redirects vetted, size and time capped | `adapters/net/guard.py`, `adapters/net/fetch.py` | CC6.6 |
| Ledger integrity | The database checks every entry balances at commit; no route edits or deletes a posted entry, which is corrected by a reversing entry; closed books (the lock date) refuse any entry or posting added, changed or deleted there, by any path, and every change of the lock date is audited; an AI's retried booking (`client_ref`) is unique in the database, so retries sent at once book one entry; money is `Decimal`, never a float | `migrations/versions/core_0001_baseline.py`, `core_0028_mcp_scopes_audit.py`, `core_0030_lock_edits.py`, `application/services/ledger_service.py` | PI1 |
| Decision journal | Append-only: a trigger refuses UPDATE, DELETE and TRUNCATE except while erasing that person; each record hashed over its canonical JSON | `migrations/versions/core_0017_decision_journal.py`, `domain/decisions/` | PI1, CC7.2 |
| Tax rule sets | A used version's content can't change (trigger); a version activates only after its worked examples pass, and only by the person | `migrations/versions/core_0010_tax_rule_sets.py`, `application/services/tax_rule_service.py` | PI1 |
| Audit log | Every MCP write, refused or not: the person, the connection's client, the tool, its arguments (secrets redacted) and the outcome (succeeded, refused, failed), written in the transaction that makes the change, so a change whose row can't be written isn't made. Also every write the in-app agent proposes (approved or denied; best effort) and tax rule activations. Append-only: a trigger refuses UPDATE, DELETE and TRUNCATE except while erasing that person. Readable at `/v1/agent/audit-log` | `interfaces/api/mcp_server.py`, `application/unit_of_work.py`, `migrations/versions/core_0028_mcp_scopes_audit.py`, `domain/agents/tools.py`, `tax_rule_service.py` | CC7.2 |
| AI kept to describing | The model never computes money or tax; agent writes wait for approval; MCP tools that record a decision or principle need `confirmed_by_user`; a briefing is labelled `written_by: "ai"` with a notice | `domain/agents/`, `interfaces/api/mcp_server.py` | PI1 |
| Data rights | Export everything (`GET /v1/onboarding/export`), conversations with the AI included, and erase the account (`DELETE /v1/onboarding/account`): every row in one transaction, then the uploaded files and the conversations in LangGraph's checkpoint tables, any part left over said in the response and the log | `interfaces/api/routers/onboarding.py`, `application/services/data_portability_service.py`, `adapters/db/repositories.py`, `adapters/db/conversations.py`, `adapters/storage/local.py` | P4, P5 |
| Container | Non-root user, base images pinned by digest, healthcheck; published images carry an SBOM and a provenance attestation | `Dockerfile`, `.github/workflows/image.yml` | CC7.1, CC8.1 |
| Releases | npm versions are staged and reach no one until a maintainer approves with 2FA; publishing through OIDC with provenance, no stored npm credential; image pushes wait for approval | `.github/workflows/release.yml`, `RELEASING.md` | CC8.1 |
| Supply chain | Actions pinned to commit SHAs; Dependabot weekly; CodeQL for Python and TypeScript; pip-audit and npm audit fail the build on a known vulnerability in what ships (npm at high or above), except the advisories accepted below; gitleaks over the history | `.github/workflows/`, `.github/dependabot.yml`, `.github/audit/` | CC7.1 |
| Change management | Every pull request runs lint, type checks, the tests (including the API contract) and the console's browser tests | `.github/workflows/ci.yml` | CC8.1 |
| Disclosure | Private reporting, response times, supported versions | `SECURITY.md` | CC2.3, CC7.3 |
| Processors | Who else sees personal data, what and when | `docs/privacy.md` | CC9.2 |
| **Not yet:** encryption at rest | Only the secrets above are sealed. The database and uploaded files are as encrypted as the operator's disk and backups | | CC6.1, C1.1 |
| **Not yet:** database-enforced ledger | Entries are kept unchanged by the code, not by a trigger as the decision journal and the audit log are | | PI1 |
| **Not yet:** complete audit trail | Changes a person makes through the API, and sign-ins, are not in the audit log | | CC7.2 |
| **Not yet:** signed artefacts | Images carry provenance but no signature; the macOS and Windows binaries are not code-signed | `RELEASING.md` | CC8.1 |
| **Not yet:** penetration test | No external test or audit has been done | | CC4.1 |

## Accepted advisories

Known advisories the audit lets through, each with no fixed release that
Salli can take. Every other one fails CI's `security` job.

| Advisory | Where | Why it is accepted |
|---|---|---|
| PYSEC-2026-4146 (PyJWT) | The server | `decode()` writes into an `options` dict it is given when signature checks are off. Salli never turns them off and passes a new dict on every call. |
| GHSA-86w9-cpqp-85rv (node-forge) | The app's build tools | Reached only through `@expo/cli`, Expo's command line, which builds the app and is not part of it. No node-forge release fixes it, and Expo SDK 58 has no `@expo/cli` without it. |
| GHSA-mrhx-c7xc-m3w5 (zod 3) | The app's build tools | The copy `@expo/cli` requires; zod 3 has no fixed release. The app's own zod, which the AI SDK uses on the phone, is 4.6.7. |

The npm entries are in `.github/audit/npm-allowlist.json`, each for the one
installed path named, so the same advisory anywhere else still fails. Each
goes when a release fixes it.

## What the operator owns

HTTPS in front of the server (compose's `tls` profile), the host and its
disk encryption, encrypted off-site backups of the database, files and
secrets ([self-host.md](self-host.md#backup-and-restore)), keeping
`SALLI_INSECURE_DEV_AUTH` off, upgrading images, and watching the server's
logs. Salli itself sends no telemetry.
