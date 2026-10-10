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
- **Tax packs are versioned `(country, year, version)`.** Every stored `TaxComputation` records the pack version so historical returns remain reproducible after rate changes.
- **Nothing assumes a country.** A user's tax residency (ISO 3166-1, on their profile, with their tax ids) decides which packs compute their tax (`TaxService.jurisdiction`; with none set, the one country whose packs compute in their base currency), their tax year, the tax accounts in their starter chart, and the agents' tax framing. With no residency there is no country's framing at all.

### Tax engine

`domain/tax/engine.py` exports a pure function `compute(ledger_view, pack) -> TaxComputation`. It applies the pack's rate bands to taxable income **after** deducting personal relief, then subtracts credits (APIT, AIT, FTC). The engine never calls the LLM.

Tax packs live in `domain/tax/packs/`. The first pack is Sri Lanka 2025/26 (`lk_2025_26.py`): LKR 1,800,000 personal relief, bands 6/18/24/30/36%, 15% final tax on foreign service income remitted via bank, credits for APIT/AIT/FTC.

A pack also declares its tax year's shape (`year_start`/`year_end`, so the registry can name the year any date falls in, and the pack for a date), its `withholding_kinds` (the `tax_role`s an account may carry for them; only kinds the engine credits, `CREDITED_KINDS`), the accounts a resident's starter chart gets (`starter_accounts`), and how the agents should talk about it (`authority`, `law`, `year_name`). Nothing hard-codes "the current year": with none named, the latest year whose pack has begun is computed.

### Financial independence

`domain/fi/engine.py` is the pure FI engine; `domain/fi/assumptions.py` holds its planning assumptions. Defaults follow the base currency (a small table: each central bank's inflation target, a round real return, the 4% rule, each with its source; Sri Lanka keeps Salli's original figures). The user's own figures on their profile win, then their FIRE strategy's, then the defaults, and every FI response says which applied and where it came from.

### Agents (LangGraph)

Two distinct things in `domain/agents/`:

- **`tax_agent.py`** — conversational agent (`create_agent`) with read-only tools backed by the engine. Uses `AsyncPostgresSaver` checkpointer for per-thread persistence.
- **`return_workflow.py`** — deterministic `StateGraph` for return preparation: gather → compute → map_to_cages → review (human `interrupt()`) → finalize. The same interrupt gate will guard agent-assisted filing when/if an IRD individual-IIT API appears.

### Test layout

| Directory | What goes there |
|---|---|
| `tests/unit/` | Pure domain logic — no DB, no LLM |
| `tests/properties/` | Hypothesis property tests for ledger invariants (trial balance nets zero, reversing restores balance, multi-currency reconciles) |
| `tests/golden/` | IRD worked examples → expected `TaxComputation` JSON; a pack is wrong until these pass |
| `tests/integration/` | Against a real Postgres (migrations, triggers); skipped without `SALLI_TEST_DATABASE_URL` |
| `tests/contract/` | The committed OpenAPI document and the no-billing-vocabulary guard (CLI coverage of the API is `packages/cli/test/api-coverage.test.ts`) |

### Configuration

All config is in `config.py` via `pydantic-settings` and reads from environment / `.env` (see `.env.example`; `salli-server setup` writes it). Required: `DATABASE_URL` and the `SUPABASE_*` auth keys. `ANTHROPIC_API_KEY` enables the AI features. `SALLI_REGISTRATION` (closed by default), `SALLI_STORAGE`, `SALLI_EXTENSIONS`.

### Adding a new tax pack

1. Add `domain/tax/packs/<country>_<year>.py` declaring a `TaxPack` dataclass instance: its rates, its tax year (`year_start`, `year_end`; `year` named as `year_label` names it), its withholding kinds and starter accounts.
2. Register it in `domain/tax/packs/registry.py` (`validate_pack` refuses a malformed one at import).
3. Add golden tests in `tests/golden/` using IRD/revenue-authority worked examples.
4. A chartered accountant must review the pack before it is used in production.
