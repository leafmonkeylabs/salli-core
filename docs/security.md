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
| MCP clients | AI connectors the person adds | OAuth 2.1 with PKCE; the person's MCP switch is checked on every call (`mcp_oauth_service.py`); MCP tokens are refused by the REST API and never hold `tax:activate` (`application/permissions.py`); a connection reads, and changes a part of the person's data only with that part's scope (`mcp:ledger`, `mcp:planning`, `mcp:documents`, `mcp:settings`), which the person ticks on the consent page; every MCP call, read or write, refused or not, is in the audit log (`interfaces/api/mcp_server.py`); a connection ends 90 days after its approval. |
| AI providers | Anthropic, OpenAI or a ChatGPT plan, as configured | Sends what [privacy.md](privacy.md#who-else-sees-it) lists. Model output is untrusted: it never computes money, tool calls act only as the signed-in person (`domain/agents/tools.py`), writes wait for the person's approval, and a briefing with a digit or advice is refused (`domain/agents/briefing.py`). |
| The open web | Pages an agent searches or a person asks Salli to fetch | Requests to a person's URL go only to public addresses over HTTPS, with size and time limits (`adapters/net/guard.py`, `adapters/net/fetch.py`). An agent that reads a planted instruction still can't activate a tax rule set. |
| Bank feed | A SimpleFIN bridge | Read-only; the pasted setup URL is vetted like any other; the access URL is sealed with AES-GCM bound to its row (`adapters/banks/simplefin.py`, `bank_connection_service.py`). |
| Exchange rates | Frankfurter, then ExchangeRate-API | Currency codes and a date only; no rate is invented (`adapters/fx/`). |
| Operator | Whoever runs the server | Trusted with the host: the database, the files and the secrets. Through Salli, the operator reads a member's books only in a [support session](#support-access): read-only, time-boxed, audited and shown to the member. There is no sign-up: the owner adds members (`salli-server members`). `salli-server doctor` prints no secrets. |
| Supply chain | Dependencies, actions, base images, registries | See the controls below. |

## Controls

Mapped to the SOC 2 Trust Services Criteria at a high level: CC is the
common criteria, C confidentiality, PI processing integrity, P privacy.

| Control | What Salli does | Where | Criteria |
|---|---|---|---|
| Passwords | argon2id (RFC 9106: 64 MiB, three passes, four lanes), rehashed when the parameters change; at least 12 characters | `adapters/auth/passwords.py`, `application/services/login_service.py` | CC6.1 |
| Two-step sign-in | Required of the owner: `salli-server setup` asks for it, `salli-server doctor` warns without it, and adding or inviting members is refused until it is on (the recovery stays `members reset-password --clear-totp`). Optional for everyone else. Once on, every password check (the sign-in, consent and device pages, so the step-up too; a session; changing the password) also needs an authenticator app's code (RFC 6238, each used once) or one of ten single-use recovery codes, kept as hashes; the app's secret is sealed like the secrets below; wrong codes are throttled like wrong passwords; turning it on or off goes through the step-up, and off needs the password and a code; the owner can clear it (`members reset-password --clear-totp`) | `application/totp.py`, `application/services/login_service.py`, `routers/auth.py` | CC6.1 |
| Sign-in throttling | 5 failures an email or 50 an address in 15 minutes refuse further sign-ins unchecked; counted by hashes, so the count reveals no account | `application/services/login_service.py` | CC6.1 |
| Session lifetimes | A session ends 12 hours after sign-in (`SALLI_SESSION_TTL_HOURS`) or after two idle hours (`SALLI_SESSION_IDLE_MINUTES`), whichever is first; a refresh token lasts 14 days (`MCP_REFRESH_TOKEN_TTL_SECONDS`), so an unused sign-in lapses; an AI client's connection still ends after 90 days | `config.py`, `login_service.py`, `mcp_oauth_service.py` | CC6.1 |
| Devices and push | Only Salli's own clients (app, console, CLI) add or remove push devices, each change audited; the push relay must be HTTPS and every post carries an HMAC-signed, timestamped bearer (`SALLI_PUSH_RELAY_SECRET`) | `routers/devices.py`, `adapters/net/push.py` | CC6.1, CC6.6 |
| Hashed tokens | Sessions, personal access tokens and OAuth tokens are random and stored only as SHA-256 hashes | `login_service.py`, `personal_access_token_service.py`, `mcp_oauth_service.py` | CC6.1 |
| OAuth | PKCE (S256 only); the console's and the app's redirects matched exactly, the CLI's to loopback only; a client that registers itself may use only https or loopback redirects, never the device grant (Salli's own CLI's alone), and the consent page shows its self-chosen name beside "Not verified by Salli"; refresh tokens rotate, and a reused one revokes its whole grant; an AI client's connection ends 90 days after the person approved it (`MCP_GRANT_LIFETIME_DAYS`) and the console's sign-in after 12 hours, however often they refresh, and the CLI's and the app's 90 days after their password (`SALLI_APP_SIGN_IN_DAYS`) | `application/services/mcp_oauth_service.py` | CC6.1, CC7.2 |
| Step-up | Activating tax rules, exporting everything and deleting the account need a password checked in the last five minutes in the console and the app; AI connectors never can activate | `application/permissions.py`, `interfaces/api/deps.py`, `routers/onboarding.py` | CC6.1, CC6.3 |
| Scoped tokens | A personal access token holds only the permissions it was made with, and no sign-in can mint one more capable than itself | `application/permissions.py`, `personal_access_token_service.py` | CC6.3 |
| MCP scopes | An AI connection reads (`mcp:read`); every tool that isn't read-only needs its part's scope (`mcp:ledger`, `mcp:planning`, `mcp:documents` or `mcp:settings`; `mcp:write`, from before the parts, holds all four), checked in one place, and is refused and does nothing without it. The consent page offers each part unticked; only the Salli app's own AI holds all by default, as the app asks the person before each change. Grants from before the scopes only read | `interfaces/api/mcp_server.py`, `mcp_oauth_service.py`, `routers/mcp_consent_page.py` | CC6.3 |
| Row-level security | Every table holding a person's data shows and accepts a row only for the person the transaction acts for (`salli.user_id`, set at the start of each transaction from the signed-in person); a transaction acting for no one sees nothing; the few paths that must act across people do so by name, each with its reason, and no other (below); the tables are `FORCE`d and Salli's role is no superuser, and `salli-server doctor` warns otherwise. A test fails on a new table without a policy | `migrations/versions/core_0051_row_security.py`, `application/acting.py`, `adapters/db/session.py`, `tests/integration/test_row_security.py` | CC6.1, C1.1 |
| Support access | The operator reads a member's books only in a support session: opened on the server for a reason, read-only (GET on the books alone), 60 minutes unless said, at most 240; its opening, every read and its end are in the audit chain; the member lists them and may end one | `application/services/support_access_service.py`, `interfaces/api/deps.py`, `interfaces/cli/support_access.py` | CC6.1, CC6.3, CC7.2 |
| Accounts and sign-ins | No sign-up; the owner adds members and resets passwords; a person lists and ends every sign-in (`/v1/auth/sign-ins`) and AI connection (`/v1/mcp/connections`) | `interfaces/cli/setup.py`, `interfaces/api/routers/auth.py`, `routers/mcp_oauth.py` | CC6.2 |
| Sealed secrets | AI keys, ChatGPT sign-ins, bank feed URLs and authenticator secrets sealed with AES-GCM, bound to their user and row; versioned keys for rotation; without a key Salli refuses to store one rather than keep it in plain text | `adapters/crypto/keyring.py` | CC6.1, C1.1 |
| Web hardening | CSP with Trusted Types, `frame-ancestors 'none'`, `no-referrer`, `Cache-Control: no-store` on API responses, HSTS where the public URL is HTTPS; MCP serves only requests addressed to the public URL's host (DNS rebinding); forwarded addresses believed only from the bundled proxy; production refuses to start without the Postgres checkpointer; the image pinned to a release in `compose.yaml` | `interfaces/api/console.py`, `interfaces/api/mcp_server.py`, `interfaces/api/main.py`, `compose.yaml` | CC6.6 |
| Outbound requests | Public addresses only, connecting to the address checked (no DNS rebinding), redirects vetted, size and time capped | `adapters/net/guard.py`, `adapters/net/fetch.py` | CC6.6 |
| Ledger integrity | The database checks every entry balances at commit; no route edits or deletes a posted entry, which is corrected by a reversing entry; no stored entry or posting is ever updated, or deleted but by erasure, by any path, and each entry records who posted it (user and client) and is hash-chained to the one before (`GET /v1/ledger/verify` finds the first break); closed books (the lock date) refuse any entry added there, a year with a filed return can't be opened without a recorded amendment, and every change of the lock date is audited; an AI's retried booking (`client_ref`) is unique in the database, so retries sent at once book one entry; money is `Decimal`, never a float | `migrations/versions/core_0001_baseline.py`, `core_0028_mcp_scopes_audit.py`, `core_0030_lock_edits.py`, `core_0037_filed_years.py`, `domain/accounting/chain.py`, `application/services/ledger_service.py` | PI1 |
| Decision journal | Append-only: a trigger refuses UPDATE, DELETE and TRUNCATE except while erasing that person; each record hashed over its canonical JSON | `migrations/versions/core_0017_decision_journal.py`, `domain/decisions/` | PI1, CC7.2 |
| Tax rule sets | A used version's content can't change (trigger); a version activates only after its worked examples pass, and only by the person | `migrations/versions/core_0010_tax_rule_sets.py`, `application/services/tax_rule_service.py` | PI1 |
| Audit log | Every MCP write, refused or not: the person, the connection's client, the tool, its arguments (secrets redacted) and the outcome (succeeded, refused, failed), written in the transaction that makes the change, so a change whose row can't be written isn't made. Every MCP read too, as one row with the person, the client, the tool and the outcome but no arguments, written before the answer is sent. Also every write the in-app agent proposes (approved or denied; best effort) and tax rule activations. Append-only: a trigger refuses UPDATE, DELETE and TRUNCATE except while erasing that person. Readable at `/v1/agent/audit-log` | `interfaces/api/mcp_server.py`, `application/unit_of_work.py`, `migrations/versions/core_0028_mcp_scopes_audit.py`, `domain/agents/tools.py`, `tax_rule_service.py` | CC7.2 |
| AI kept to describing | The model never computes money or tax; agent writes wait for approval; MCP tools that record a decision or principle need `confirmed_by_user`; a briefing is labelled `written_by: "ai"` with a notice | `domain/agents/`, `interfaces/api/mcp_server.py` | PI1 |
| Prompt injection (mitigated, not prevented) | Text from outside the person's own typing (statement and bank feed descriptions, the payees found in them, documents, saved memories, names, labels and notes a person or an agent wrote, web results) reaches a model only inside an `untrusted_text` field, fenced centrally on every read tool's answer, MCP and in-app (`fence`; a contract test walks every MCP read tool), and the MCP server's instructions, its conversation prompt and the in-app agents' prompts all say never to follow instructions there; every write still needs the person's approval (in-app, and not done when the audit log can't record it) or the part's scope and their go-ahead (MCP); the in-app agents' web search asks the person first and its prompt forbids figures, payees or personal details in a query. A model can still be misled by what it reads; these limit what that can do unseen | `domain/agents/untrusted.py`, `domain/agents/tools.py`, `interfaces/api/mcp_server.py` | PI1, CC6.6 |
| Data rights | Export everything (`GET /v1/onboarding/export`, with the files as a zip at `/export/archive`), conversations with the AI included, restore it into empty books on another server (`POST /v1/onboarding/restore`, first-party sign-ins only, the ledger's chain verified first), and erase the account (`DELETE /v1/onboarding/account`), each behind the step-up and, where two-step sign-in is on (always for the owner, who must turn it on first), an authenticator code (`Salli-Two-Step`): every row in one transaction, then the uploaded files and the conversations in LangGraph's checkpoint tables, any part left over said in the response and the log | `interfaces/api/routers/onboarding.py`, `application/services/data_portability_service.py`, `adapters/db/repositories.py`, `adapters/db/conversations.py`, `adapters/storage/local.py` | P4, P5 |
| Container | Non-root user, base images and compose.yaml's third-party images pinned by digest, healthcheck; every build scanned with Trivy (fixable HIGH and CRITICAL fail it); published images carry an SBOM and a provenance attestation and are signed with cosign, keyless (`cosign verify ghcr.io/leafmonkeylabs/salli:<version> --certificate-identity-regexp 'https://github.com/leafmonkeylabs/salli/.github/workflows/image.yml@refs/tags/server-v.*' --certificate-oidc-issuer https://token.actions.githubusercontent.com`) | `Dockerfile`, `.github/workflows/image.yml` | CC7.1, CC8.1 |
| Releases | Each npm package and the server's wheel carry a CycloneDX SBOM on their release; npm versions are staged and reach no one until a maintainer approves with 2FA; publishing through OIDC with provenance, no stored npm credential; image pushes wait for approval | `.github/workflows/release.yml`, `RELEASING.md` | CC8.1 |
| Supply chain | Actions pinned to commit SHAs; Dependabot weekly; CodeQL for Python and TypeScript; pip-audit and npm audit fail the build on a known vulnerability in what ships (npm at high or above), except the advisories accepted below; gitleaks over the history | `.github/workflows/`, `.github/dependabot.yml`, `.github/audit/` | CC7.1 |
| Change management | Every pull request runs lint, type checks, the tests (including the API contract) and the console's browser tests | `.github/workflows/ci.yml` | CC8.1 |
| Disclosure | Private reporting, response times, supported versions | `SECURITY.md` | CC2.3, CC7.3 |
| Processors | Who else sees personal data, what and when | `docs/privacy.md` | CC9.2 |
| **Not yet:** encryption at rest | Only the secrets above are sealed. The database and uploaded files are as encrypted as the operator's disk and backups | | CC6.1, C1.1 |
| **Not yet:** an append-only ledger in open periods | Closed books are refused by triggers on entries and postings; in an open period a posted entry is kept unchanged by the code only, and the reversal link is written onto the original | | PI1 |
| **Not yet:** complete audit trail | Changes a person makes through the API, and sign-ins, are not in the audit log | | CC7.2 |
| **Not yet:** signed artefacts | Images carry provenance but no signature; the macOS and Windows binaries are not code-signed | `RELEASING.md` | CC8.1 |
| **Not yet:** penetration test | No external test or audit has been done | | CC4.1 |

## Row-level security

Salli filters every query by person; Postgres checks it again. Each
transaction says whom it acts for: a request for its signed-in person (the
API's `get_principal`, the MCP gate, a page once its password is checked), a
scheduled job for each person in turn. The policies (core_0051) show and
accept a row only when its person is that one, or when the transaction is on
one of the system paths, which `application/acting.py` (`SYSTEM_PATHS`)
lists with their reasons and `as_system` holds to, a test failing on any
other:

| Path | Why it acts across people |
|---|---|
| `migrations` | A migration changes every person's rows |
| `sign-in` | A session, token, grant, code or invitation is looked up before anyone is known |
| `members` | The operator's `setup`, `members` and `doctor` list and add people |
| `member-lookup` | Sharing finds a member by email, and shows each side of a grant the other's email |
| `audit-chain` | The audit log is one hash chain for the instance: a row extends the last one, whoever's |
| `erasure` | Erasing an account pseudonymises its audit rows, and its refused sign-ins' (no one's) |
| `usage` | The instance's usage counts count everyone |
| `jobs` | Scheduled work finds who is due across everyone, then acts for each in turn |
| `support` | The operator opens, lists and ends support sessions |

Tables that hold no one's data (registered applications, instance settings,
invitations, the sign-in throttle) have no policy. The conversations
LangGraph keeps (its checkpoint tables, written on its own connection) are
kept apart by Salli's filtering alone, under thread ids that start with the
person's id.

## Support access

The operator of a server can read everything on the host; through Salli,
they read a member's books only this way, and the member sees it:

- `salli-server support open <member email> --reason "<ticket or why>"
  [--minutes 60]` opens a session (60 minutes unless said, at most 240) and
  shows its token once. With it, the `salli` CLI (`SALLI_TOKEN`) reads the
  member's books, the reads the books' routes allow (GET only, never
  sign-ins, tokens, keys, documents, imports or the export); anything else is
  refused.
- Opening it (with the reason), every read made under it (the path, before
  it is answered) and its end (by the member, by the operator with
  `salli-server support close`, or by its time) are rows in the audit log's
  hash chain, under the member.
- The member lists every session, open and past, with its reason and reads
  (`GET /v1/auth/support-access`, `salli support-access`, the console's
  Settings, Sign-ins) and ends an open one (`DELETE
  /v1/auth/support-access/{id}`, `salli support-access end`).
- Nothing else gives the operator a member's data through Salli: no route,
  command or token reads another person's books without the member's own
  grant (`salli access`) or a support session.

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
