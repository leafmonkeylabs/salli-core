# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (requires uv)
uv sync --group dev

# Run all tests (integration and migration tests also need
# SALLI_TEST_DATABASE_URL, a plain Postgres URL whose user may CREATE DATABASE;
# they are skipped without it). A local one:
#   docker run -d --name salli-core-test-pg -e POSTGRES_PASSWORD=postgres \
#     -p 127.0.0.1:54998:5432 postgres:17-alpine
#   export SALLI_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:54998/postgres
uv run pytest

# Run a single test file / test
uv run pytest tests/unit/domain/test_accounting.py
uv run pytest -k "test_journal_entry_must_balance"

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run pyright src/

# Migrate the database (Salli's history, then any enabled extension's)
uv run salli-server db upgrade

# New migration after editing adapters/db/models.py
uv run alembic revision --autogenerate -m "description"

# First-time setup of a local instance (DATABASE_URL in .env, any Postgres),
# then serve it. setup writes the server's secrets to .env and makes the owner.
uv run salli-server setup
uv run salli-server serve
uv run salli-server doctor      # config, database, migrations, owner; prints no secrets
uv run salli-server members add|list|reset-password
uv run salli-server --help

# The container, as self-hosters run it (compose.yaml, docs/self-host.md)
docker compose up -d --build
docker compose exec salli salli-server setup
docker compose down -v          # and its data

# The TypeScript SDK and the `salli` CLI (packages/)
npm ci
npm run typecheck && npm run lint && npm test
npm run check:generated         # packages/sdk/src/generated matches openapi/openapi.json
npm run build && node packages/cli/dist/salli.js --help

# After changing a route: regenerate the API document, then the SDK
uv run python -m salli.interfaces.api.spec > openapi/openapi.json
npm run generate

# After changing what a scenario, template or principle check returns:
# write the CLI's fixtures again (packages/cli/test/helpers), as the API
# answers on the golden households; tests/contract/test_cli_fixtures.py
# fails while they differ
uv run python -m tests.cli_fixtures
```

## Architecture

### Hexagonal (ports & adapters)

The domain core has **no I/O and no framework imports**. Everything external is hidden behind *ports* (abstract interfaces in `application/ports.py`). *Adapters* implement those ports. The FastAPI app, the MCP server and the `salli-server` operator CLI are thin *interface adapters* that construct the same services via `composition.py`.

```
domain/       pure Python — no sqlalchemy, no fastapi, no httpx
application/  use-cases (services) + port interfaces
adapters/     concrete implementations of ports (db, llm, storage, fx, parsing)
interfaces/   api/ (incl. the MCP server), cli/ (salli-server) — thin wrappers over services
migrations/   Alembic history, shipped in the package (`salli-server db upgrade`)
composition.py  single place adapters are bound to ports
extensions.py   how a deployment adds a usage meter, a notifier, routes, commands, tables
config.py       pydantic-settings, env-driven
```

`salli-server` and the API both call `build_services(settings)` from `composition.py`, so the core is exercised identically from both surfaces.

Outside `src/`: `packages/sdk` is the TypeScript SDK, generated from `openapi/openapi.json`, and `packages/cli` is the `salli` command line (npm `@leafmonkeylabs/salli`), a client of the API built on it.

### CLI-first

Everything a person does goes through the API, and every API operation has a
`salli` command in `packages/cli`: `packages/cli/test/api-coverage.test.ts`
fails on an operation that no command reaches and that is not in its `EXEMPT`
table with a reason (OAuth plumbing, cron, health checks). Commands print the
API's JSON with `--json` (data on stdout, messages on stderr) and keep amounts
as decimal strings; the CLI never does arithmetic on money.

`salli-server` (`interfaces/cli/`) is only for what must run where the server
runs: `setup`, `serve`, `doctor`, `db`, `members`, and `jobs` that act on every
user. Never add a per-user feature there: add the route, then the `salli`
command. Every `salli-server` command takes `--json`; use `emit(data)` from
`interfaces/cli/support.py`. `support`'s helpers (`console`, `emit`,
`require_user`, `services`, `leaf_commands`) and `main.app` / `main.cli()` are
the stable surface extensions build on: keep their names and behaviour.

### Extensions

Salli has no billing, plans or metering. A deployment that needs them supplies
an extension (`extensions.py`): a `UsageMeter` that may refuse an AI action
(`domain/usage.py`), an `EntitlementPolicy` that may shape a surface, a
`Notifier` that delivers digests (at most one; see below), plus routes, `salli-server` command groups, services, tables (own metadata, own migration history and
version table) and per-user purgers/exporters. The defaults —
`application/defaults.py` — meter nothing, show everything and send nothing
(`NoNotifier`). Call
`services.usage.charge(...)` before any new AI action and
`services.entitlements.for_user(...)` for any new shapeable surface; never
branch on who a user is. `tests/contract/test_no_commercial_vocabulary.py`
keeps plan/payment vocabulary out of the codebase.

### Domain model invariants (non-negotiable)

- **LLM never computes money or tax.** Numbers reach the user only via deterministic engine output or tool results. The LLM parses documents, explains results, and drafts guidance.
- **Double-entry entries are immutable.** Corrections use reversing entries. Never edit or delete a posted `JournalEntry`.
- **Money is always `decimal.Decimal` in the domain; `BIGINT` minor units in the DB.** A float anywhere in the money path is a bug. Minor units are each currency's own (ISO 4217 exponent: JPY 0, USD 2, KWD 3 — `domain/currency.py`); never assume 100.
- **Every user has a base currency** (on their profile). Postings in it have `fx_rate` 1; postings in any other currency carry the rate into it — the one given, or the published one for the entry's date — and are refused when there is neither (`application/fx.py`). The base currency cannot change once anything is stored in it.
- **Tax rule sets are user data.** They are versioned and immutable once used. Every stored computation records the rule-set version and content hash. A rule set can't be activated until its worked examples pass, and only the user can activate one; AI connectors never hold `tax:activate`.
- **Nothing assumes a country.** A user's tax residency (ISO 3166-1, on their profile) decides whose rules compute their tax (`TaxService.resolve`; never inferred from their currency or a tax id), and their active rule set decides their tax year, their filing reminders and the agents' tax framing. With no residency, or no active rules, no tax is computed and there is no country's framing at all.
- **Nothing country-specific lives in the code.** Tax rules, planning assumptions, tax-id schemes and local market knowledge are user data, written by the user or their agent with sources. Tax ids are generic `{scheme, value}` pairs ("XX-KIND"). The code holds generic engines, neutral placeholders that are always labelled as such, and the ISO 3166/4217 tables, which treat every country alike. `tests/contract/test_no_country_knowledge.py` fails on one country's terms in code, skills or docs; its allowlist is the ISO tables and the historical migrations. Examples and tests use varied countries and currencies.
- **Planning assumptions are user data, in real terms.** FI projections run after inflation. The real return and the withdrawal rate fall back to a neutral 4% placeholder, and the share of the monthly surplus invested (`surplus_invested`) to all of it; inflation has none, and nominal figures appear only once the user sets it. Projections never block on missing assumptions, and every FI response says which figures are placeholders (`assumptions.status`, `assumptions.placeholders`).

### Tax engine

salli-core carries no country's tax law. `domain/taxrules/` is a generic engine for **tax rule sets** (`salli.tax/1`, [docs/taxrules.md](docs/taxrules.md)): a JSON document of named lines, building blocks, band tables, deadlines, suggested accounts and return forms that a user (or their agent) writes, cites and checks against the authority's worked examples. `compile_rule_set` + `evaluate` are pure; the engine never calls the LLM.

`TaxRuleService` stores rule sets as immutable versions through their lifecycle (activation needs `tax:activate`, and seeds the filing reminders from the version's `deadlines`). `TaxService` computes a user's tax only with their active rule set: jurisdiction from their residency (or as given), year as given or the active rule set covering today, ledger totals by account `tax_role` (`domain/taxrules/inputs.py`). An account's `tax_role` must be a role the user's own rule sets declare.

### The baseline

`domain/baseline/` is one pure, dated model of a user's money ([docs/baseline.md](docs/baseline.md)); `BaselineService.build(user_id, as_of)` gathers its inputs (nothing dated after `as_of`, which defaults to its injectable clock's today) and every figure that looks ahead starts from it: FI, insights' cash flow averages, the cash forecast and safe-to-spend, the debt plan, `GET /v1/baseline`. Its definitions, which nothing else should redefine:

- **Income and expenses:** signed amounts on income and expense accounts, netted per calendar month, averaged over the full months observed (at most twelve before the as-of month, from the first unreversed income or expense entry; `flows.py`).
- **Balances by role:** an asset account's `asset_role` (`cash`, `investment`, `other`; never its name) or liability; each in its own currency, valued at the **published rate for the as-of date** through the FX port, recorded with source and day. No rate: left out of the totals, in `notes`.
- **Debts counted once:** a debt linked to its liability account (`debts.account_id`) owes what the account says; an unlinked one its declared principal.
- **Holdings never counted:** the investment-role accounts are the investments. A holding may be linked to the investment account that holds it (`holdings.account_id`, core_0020); `Baseline.holdings` (`holdings.py`) values each at its last recorded price on or before the as-of date and the as-of rate, and `notes` say where a linked account and its holdings disagree. Never reconcile them silently. Cash accounts are cash-role assets and the cards money is spent from (`forecast.cash_accounts`), never a debt's account.
- **Two timelines** (`timelines.py`): daily cash for the as-of month and the twelve after it (the forecast's flows plus the rest of each month's plan, so month-ends land on the plan exactly), and monthly to 1–50 years in today's money (investments grow at the real return and take `surplus_invested`, the share of each month's regular surplus; the rest stays in cash, which earns nothing; debts on calendar-month schedules, deflated by the user's inflation, or kept at real value as a placeholder; other assets level in today's money, plus each asset a scenario buys (`Changes.assets`, the `asset` change: price out of cash, then its own real growth) counted at its value less its selling costs, `other_assets_value` beside it; FI's asset base never counts other assets). The regular surplus is the average surplus less debts' scheduled payments (freed once paid off) plus a scenario's recurring changes; one-offs, loan money, invest moves and extra payments are moves that go where they say; a deficit is drawn from cash, never from investments (`cash_plan`). Both take injected `changes` (`timelines.Changes`: `flows` are moves, `regular` are shared out) for scenarios.

Reads never write: only `FiService.record_score` (the recompute route, and the advisor's run) stores a score.

### Financial independence

`domain/fi/engine.py` is the pure FI engine: Decimal throughout, in real terms, with the withdrawal rate and the real returns passed in explicitly (the FI pack, `domain/fi/packs/`, is only the scoring method). `FiService` feeds it from the baseline (`snapshot_of`): the baseline's monthly income and expenses, cash-role accounts as liquid savings, investment-role accounts as investments, everything owned and owed (declared debts the ledger doesn't hold included). The FI date is a month, not whole years: it comes from the baseline's monthly timeline (`domain/baseline/fi.py`, `months_to_fi`), and `FiService` passes it to the engine as `projected_fi_months`; responses carry it as `projected_fi_month`, and `fi_by` per scenario. So the score, the projections and every scenario say the same month. `domain/fi/assumptions.py` decides which figures apply: the user's own (a real return, or a nominal one with their inflation; inflation; a withdrawal rate; the share of the surplus invested, 0 to 1; each with a `source` and `note`, stored as `user_profiles.fi_assumptions`), then their FIRE strategy's real returns and withdrawal rate, then the labelled placeholders (`PLACEHOLDERS`: a 4% real return, a 4% withdrawal rate, and all of the surplus invested). There is no table by currency or country. With the user's inflation, projections add each year's own money, derived from the real walk so the FI year never moves. A scenario's change in tax (below) moves the FI month through the regular surplus and never the FI number (tax on a salary isn't spending to live on); investment growth is never taxed, so the real return is the user's after tax. `PATCH /v1/fi/assumptions` (`salli fi assumptions set`, MCP `set_fi_assumption`) sets them; every FI response carries `assumptions` with its `status`, `placeholders` and `message`.

### Principles and the decision journal

`domain/decisions/` ([docs/decisions.md](docs/decisions.md)) is pure. A **principle** (`salli.principle/1`) is a label and a check in the tax rules' expression language in figure mode (`parse(text, figures=True)`: figures by plain name, `emergency_months >= 6`) over a fixed, documented figure set of 33 (`figures.FIGURES`, computed from a scenario's outlook by `figures.compute`; `tax_change_this_year` is the scenario's change in the as-of tax year's tax); checking says keeps, breaks or can't tell, never a ranking. Add a figure only by extending that set (and its docs), never by letting checks read anything else. The **decision journal** is append-only: `journal.entry`/`note`/`review` build `salli.decision/1` documents hashed over their canonical JSON (`domain/canonical.py`), returned exactly as stored. `SQLDecisionRepository` only adds and reads, and core_0017's trigger refuses UPDATE/DELETE/TRUNCATE on `decisions`, `decision_notes` and `decision_reviews` except while `delete_all` erases the user (`salli.erase_user`); never add an update or delete path. `DecisionService` runs every option itself (clients never supply figures), records a review reminder (`source_domain` "decision"), and reviews compare the chosen option's `projection` with the baseline as of a month's end (`review.compare`). MCP tools that store a principle, a decision or a review require `confirmed_by_user: true`.

**Tax in scenarios** ([docs/scenarios.md](docs/scenarios.md#tax)): a `one_off`, `recurring` or `income_change` may carry a `tax_role` (an `income` or `deduction` role of the user's rules; `income_change.monthly` is then before tax), and a `stop_recurring` takes its account's role. `domain/scenarios/tax.py` (pure) projects each tax year's role totals for the baseline and the scenario (actual to the as-of date, the rest at the role's monthly average from `Baseline.tax`, plus the tagged amounts, in each year's own money), evaluates both with `taxrules.engine.evaluate` and spreads the change in `net` over the year's months as regular flows (source "tax"). Only active rules in the user's residency compute (`BaselineInputs.tax`, gathered by `BaselineService`); later years with none carry the latest forward, level in today's money (`tax_rules_carried_forward`). Without rules, a scenario still runs with tagged amounts before tax, `tax.status` `not_computed` and `"tax"` among its placeholders. A scenario that tags nothing is exactly as without tax. `ScenarioService` refuses a role none of the user's rule sets declares.

**Holdings in scenarios** ([docs/scenarios.md](docs/scenarios.md#holdings), phase 3b): `invest` may name one of the person's holdings (`holding`) and `fees`; `sell` sells part of one (`quantity` or `amount`, `fees`, named `lots`, `into`, an income `tax_role` for the realised gain). `domain/scenarios/holdings.py` (pure) prices a trade at the holding's last recorded price, grown at the person's real return and inflation through the months before a later trade's month, at the as-of rate (no price or rate forecast), replays the holding's lots in memory with `portfolio.lots.replay` (first in, first out unless lots are named; nothing written), and refuses a sale of an unlinked holding or of more than its linked account holds. One real return: holdings supply prices, units, lots, fees and gains, never an expected return per holding; sensitivity and the break-evens retranslate an option with a later trade at the return they vary. Fees are the person's, zero (and said so) when not given. A holding id that isn't the caller's is `HoldingNotFound` (404), so no security the person doesn't hold gets into a scenario; no template default picks a holding.

**Templates** ([docs/templates.md](docs/templates.md)): `domain/decisions/templates.py` (the `salli.template/1` question types, answer checking with paths, `Facts` from the baseline and principles) and `catalogue.py` (the seven; `big-change` and `windfall` ask for a tax role, a `tax_role` question of the person's own roles, and a start takes `tax_answers`; `debt-or-invest` and `windfall` may ask for a `holding`, one of the person's own, never defaulted; `rent-or-buy` builds keep renting and buy once per mortgage, a home being an `asset` and a mortgage an ordinary `loan`) build options as scenarios by pure functions of the answers; a default comes only from the date, the person's own debts and principles, or a plain one of Salli's, never an invented figure, and no template holds a country's rule. The one exception is rent-or-buy's two growths beyond inflation, 0 with the source `placeholder` (labelled, never a forecast, with the `asset_growth` break-even beside it). `start.py` (`salli.decision-start/1`, served by `TemplateService.start`) compares the options, checks the principles, reads the time to a cash target from the engine (`engine.cover_target`; the `set_aside` change keeps part of the surplus in cash) and when buying draws level with renting (`comparison.level_from`, the start's `level`), and stores nothing: recording stays `record_decision`, from its `record`. Nothing a template or a start returns may rank: `tests/guardrails.py` fails on a ranking field or word, and the `think_through_decision` and `can_i_afford` prompts end with `mcp_server.GUARDRAILS` (never compute, never name products or securities of its own, the person's own holdings only as they named them, never a suggestion to buy or sell any security nor a comparison of holdings, a licensed professional for regulated advice, the person's principles, never rank, never record unconfirmed), which tests hold them to (`tests/contract/test_holdings_guardrail.py` holds the prompts, the CLI skill and docs/ai-clients.md to the holdings wording).

### Notifications (digests)

Phase 3d of the decision lab (docs/design/decision-lab-phase-3.md, section 4; docs/self-host.md#digests). **Core builds every message and sends none.** `domain/notifications/` is pure: `digest.py` holds the wording table and `build_digest` (each item's kind in Salli's own sentence, a count, the earliest date and the `SALLI_PUBLIC_URL` link; None when nothing is waiting), and `schedule.py` says when a digest goes (the ISO week or month of the person's local date, their weekday, or the month's first one, at their local hour through `zoneinfo`; an hour a clock change skips goes at the next that exists, one it repeats counts once). The items are decision reviews due (reminders with `source_domain` "decision"), the person's own reminders due before the next digest, filing deadlines (`source_domain` "tax_rules") within 14 days, the cash forecast below zero (`InsightsService.cash_below_zero_on`, the `low_balance_ahead` signal at `high`), and, only if chosen, transactions to review; other signals stay in the product. **A message never holds an amount, a name, a question, a note or anything else from the ledger**: the builder is given a reminder's source, due date and status (`ReminderFact`), never its text, and `tests/guardrails.assert_never_urges` (no ranking or urgency word, no streak, no countdown, no number of days, no `!`) and a property test over random people's data hold it. Never pass the builder text, and never let a model write a message.

`NotificationService` keeps the preferences (`notification_preferences`: opt-in, weekly or monthly, weekday, hour, items; `user_profiles.time_zone`, an IANA name, needed to opt in), previews the message (reads only), and `send_due(now)` sends what is due this hour through the deployment's `Notifier` (`Extension.notifier`, merged in `combine` like the meter; `NoNotifier` by default, and then the job does nothing). **Once a period:** the period's row in `notification_deliveries` (unique user and period) is claimed before the send, by an insert or by an update that only matches a FAILED row with attempts left; a FAILED send is retried at the same hour on a later day of the period, three attempts in all; a row left `sending` (the process stopped mid-send) is never retried. The log keeps the items and the message's hash, never its text; failures are logged by the exception's type only. `salli-server jobs send-digests` and `POST /v1/notifications/cron/send-due` (X-Cron-Secret) run it hourly; `salli-server doctor` names the notifier and warns when the job hasn't run in a day. Erasing an account deletes both tables' rows; the export carries them.

### Agents (LangGraph)

Two distinct things in `domain/agents/`:

- **`tax_agent.py`** — conversational agent (`create_agent`) with read-only tools backed by the engine. Uses `AsyncPostgresSaver` checkpointer for per-thread persistence.
- **`return_workflow.py`** — deterministic `StateGraph` for return preparation: compute → build_draft (the active rule set's `forms`, filled in from the result) → review (human `interrupt()`; edit computes again) → finalize. Served by `/v1/tax/returns/prepare|resume`. The same interrupt gate would guard filing on the user's behalf, should an authority ever offer a channel for it.

Every prompt ends with a section about the user (`jurisdiction.py`: date, base currency, tax residency, active rules) and knows no country. The agents carry no notes on any country's markets: the ones with web search research local products and rates when they need them, citing sources; the FIRE strategy (one call, no web) suggests kinds of product, never named local ones.

### Test layout

| Directory | What goes there |
|---|---|
| `tests/unit/` | Pure domain logic — no DB, no LLM |
| `tests/properties/` | Hypothesis property tests for ledger invariants (trial balance nets zero, reversing restores balance, multi-currency reconciles) |
| `tests/golden/` | Engines' worked examples (budget, debt, FI, portfolio, …) |
| `tests/taxrules/` | The tax rule-set engine; `conformance/` holds fictional jurisdictions, each the structure of a real-world feature, never its law |
| `tests/integration/` | Against a real Postgres (migrations, triggers, accounts and every sign-in path over HTTP); skipped without `SALLI_TEST_DATABASE_URL` |
| `tests/contract/` | The committed OpenAPI document, the CLI's fixtures (`tests/cli_fixtures.py`), the no-billing-vocabulary guard, the no-country-knowledge guard and the guard that keeps a former auth provider out (CLI coverage of the API is `packages/cli/test/api-coverage.test.ts`) |

### Configuration

All config is in `config.py` via `pydantic-settings` and reads from the environment, a `.env` (a checkout's; `salli-server setup` writes the server's secrets there) and `SALLI_SECRETS_DIR` (one file per secret; the container's, made by `salli-server secrets init`). Required: `DATABASE_URL` (its password may come from `DATABASE_PASSWORD`). `ANTHROPIC_API_KEY` enables the AI features. `SALLI_PUBLIC_URL`, `ALLOWED_ORIGINS` (none by default), `SALLI_STORAGE_DIR`, `SALLI_EXTENSIONS`. Every setting is in the table in [docs/self-host.md](docs/self-host.md#configuration): keep it in step.

### Signing in

Salli keeps its own accounts (decision D13); nothing but Postgres is needed. `application/services/login_service.py`: argon2id passwords (`adapters/auth/passwords.py`, rehashed when the parameters change), throttled failures (by a hash of the email and of the address), opaque `salli_st_` session tokens stored as SHA-256 hashes. `interfaces/api/deps.get_principal` accepts Salli's own tokens only (sessions, personal access tokens, OAuth tokens for the API), then an extension's `IdentityProvider` if one is enabled, then the development fallback; no request ever creates an account. The consent and device pages (`routers/mcp_consent_page.py`) check the same passwords, so the CLI's sign-in and MCP connections go through them. There is no sign-up and no email: the owner (`salli-server setup`) adds members and resets passwords. `tax:activate` follows from how the caller signed in (`application/permissions.py`). `tests/contract/test_auth_is_our_own.py` keeps the auth provider Salli used before out of the code and docs.

### Self-hosting

`Dockerfile` (uv from `uv.lock`, slim, non-root, `/healthz` healthcheck; the command migrates under an advisory lock, then serves) and `compose.yaml` (generated secrets, Postgres 17 on an internal network, Caddy under the `tls` profile). `.github/workflows/image.yml` builds both platforms on pull requests and pushes to GHCR from `server-v*` tags, after approval. The guide is [docs/self-host.md](docs/self-host.md).

### Tax rules for a country: rule-set authoring

There are no tax packs, and nothing to add to the code for a new country. A country's rules are a rule set: see the schema docs ([docs/taxrules.md](docs/taxrules.md)), the conformance suite (`tests/taxrules/conformance/`), and the MCP `research_tax_rules` prompt an agent follows to draft one. Extending the engine (a new block or function) needs a new fictional jurisdiction in the conformance suite.
