# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (requires uv)
uv sync --group dev

# Run all tests (migration tests also need SALLI_TEST_DATABASE_URL, a Postgres
# URL whose user may CREATE DATABASE; they are skipped without it)
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

# First-time setup of a local instance (after `supabase start`), then serve it
uv run salli-server setup
uv run salli-server serve
uv run salli-server doctor      # config, database, migrations; prints no secrets
uv run salli-server --help

# The TypeScript SDK and the `salli` CLI (packages/)
npm ci
npm run typecheck && npm run lint && npm test
npm run check:generated         # packages/sdk/src/generated matches openapi/openapi.json
npm run build && node packages/cli/dist/salli.js --help

# After changing a route: regenerate the API document, then the SDK
uv run python -m salli.interfaces.api.spec > openapi/openapi.json
npm run generate
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
extensions.py   how a deployment adds a usage meter, routes, commands, tables
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
(`domain/usage.py`), an `EntitlementPolicy` that may shape a surface, plus
routes, `salli-server` command groups, services, tables (own metadata, own migration history and
version table) and per-user purgers/exporters. The defaults —
`application/defaults.py` — meter nothing and show everything. Call
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
- **Nothing assumes a country.** A user's tax residency (ISO 3166-1, on their profile) decides whose rules compute their tax (`TaxService.resolve`; never inferred from their currency), and their active rule set decides their tax year, their filing reminders and the agents' tax framing. With no residency, or no active rules, no tax is computed and there is no country's framing at all.

### Tax engine

salli-core carries no country's tax law. `domain/taxrules/` is a generic engine for **tax rule sets** (`salli.tax/1`, [docs/taxrules.md](docs/taxrules.md)): a JSON document of named lines, building blocks, band tables, deadlines, suggested accounts and return forms that a user (or their agent) writes, cites and checks against the authority's worked examples. `compile_rule_set` + `evaluate` are pure; the engine never calls the LLM.

`TaxRuleService` stores rule sets as immutable versions through their lifecycle (activation needs `tax:activate`, and seeds the filing reminders from the version's `deadlines`). `TaxService` computes a user's tax only with their active rule set: jurisdiction from their residency (or as given), year as given or the active rule set covering today, ledger totals by account `tax_role` (`domain/taxrules/inputs.py`). An account's `tax_role` must be a role the user's own rule sets declare.

### Financial independence

`domain/fi/engine.py` is the pure FI engine; `domain/fi/assumptions.py` holds its planning assumptions. Defaults follow the base currency (a small table: each central bank's inflation target, a round real return, the 4% rule, each with its source; Sri Lanka keeps Salli's original figures). The user's own figures on their profile win, then their FIRE strategy's, then the defaults, and every FI response says which applied and where it came from.

### Agents (LangGraph)

Two distinct things in `domain/agents/`:

- **`tax_agent.py`** — conversational agent (`create_agent`) with read-only tools backed by the engine. Uses `AsyncPostgresSaver` checkpointer for per-thread persistence.
- **`return_workflow.py`** — deterministic `StateGraph` for return preparation: compute → build_draft (the active rule set's `forms`, filled in from the result) → review (human `interrupt()`; edit computes again) → finalize. Served by `/v1/tax/returns/prepare|resume`. The same interrupt gate would guard filing on the user's behalf, should an authority ever offer a channel for it.

### Test layout

| Directory | What goes there |
|---|---|
| `tests/unit/` | Pure domain logic — no DB, no LLM |
| `tests/properties/` | Hypothesis property tests for ledger invariants (trial balance nets zero, reversing restores balance, multi-currency reconciles) |
| `tests/golden/` | Engines' worked examples (budget, debt, FI, portfolio, …) |
| `tests/taxrules/` | The tax rule-set engine; `conformance/` holds fictional jurisdictions, each the structure of a real-world feature, never its law |
| `tests/integration/` | Against a real Postgres (migrations, triggers); skipped without `SALLI_TEST_DATABASE_URL` |
| `tests/contract/` | The committed OpenAPI document and the no-billing-vocabulary guard (CLI coverage of the API is `packages/cli/test/api-coverage.test.ts`) |

### Configuration

All config is in `config.py` via `pydantic-settings` and reads from environment / `.env` (see `.env.example`; `salli-server setup` writes it). Required: `DATABASE_URL` and the `SUPABASE_*` auth keys. `ANTHROPIC_API_KEY` enables the AI features. `SALLI_REGISTRATION` (closed by default), `SALLI_STORAGE`, `SALLI_EXTENSIONS`.

### Tax rules for a country

Not in code. A country's rules are a rule set: see the schema docs ([docs/taxrules.md](docs/taxrules.md)), the conformance suite (`tests/taxrules/conformance/`), and the MCP `research_tax_rules` prompt an agent follows to draft one. Extending the engine (a new block or function) needs a new fictional jurisdiction in the conformance suite.
