# Salli

Your own personal-finance platform — a double-entry ledger, bank connections
and statement imports, budgets, debts, investments, insurance, subscriptions,
cash-flow forecasts, income tax and financial-independence planning, with an
AI advisor that explains it all. Runs on your machine, on your own data, with
the AI you already pay for.

- **CLI-first.** Everything the API can do, the `salli` command line does
  from the terminal, on any machine, with `--json` for scripts. It is a client
  of your server, like the MCP server's AI clients and any app you build on
  the API.
- **The LLM never does the maths.** Money and tax come from deterministic
  engines; the model parses documents, explains results and drafts advice.
- **Your transactions come to you.** Connect banks through SimpleFIN and they
  sync on a schedule, or import a statement in any common format (OFX, QIF,
  camt.053, MT940, CSV, Excel, PDF). Nothing is booked until you review it,
  and a transaction is never hidden or booked twice.
- **See what's coming.** Cash flow, spending, net worth over time, the
  recurring payments you may not be tracking, a forecast of your cash to its
  lowest point, what is safe to spend before payday, and the signals that
  need your attention: `salli insights`.
- **Real investment tracking.** Transactions and lots, the prices you keep,
  realised and unrealised gains, income, time-weighted and money-weighted
  returns.
- **Rules that learn.** Deterministic rules book imported and quick-added
  transactions before any model is asked, so a payee is booked the same way
  every time; `salli rules suggest` offers the rules your own bookkeeping
  implies.
- **Tax rules are yours, as data.** Salli knows no country's tax law: you, or
  your AI agent, write your country's rules as a versioned, cited rule set
  (`salli.tax/1`), checked against the authority's own worked examples, and
  only you can activate it. Salli's engine computes with it, explains every
  line, prepares your return from the rules' forms and reminds you of their
  deadlines; each computation records the exact rules that produced it, so a
  past return can be reproduced after the rules change
  ([docs/taxrules.md](docs/taxrules.md)).
- **Your books, in plain text.** `salli export beancount` or `salli export hledger`
  writes every account and entry as a Beancount file or an hledger journal, so
  you can leave with your whole ledger at any time, or use Fava alongside.
- **Works with the AI you already have.** Connect Claude, Claude Code or
  ChatGPT to Salli over MCP, so your subscription does the thinking and Salli
  supplies the numbers ([docs/ai-clients.md](docs/ai-clients.md)). Salli's own
  AI features run on your ChatGPT plan (`salli ai connect chatgpt`), an OpenAI
  or Anthropic key, or no key at all: your rules still sort your statements.
  Or let your own agent drive the CLI with the skills in
  [`packages/cli/skills`](packages/cli/skills).

> **Not tax advice.** Salli computes tax from your own records with the rules
> you (or your agent) entered and you activated. It doesn't vouch for the
> law: the rules' sources do.

## Where Salli is today

Salli is for anyone, anywhere. It started in Sri Lanka, and that is still
where it does the most:

- **Tax:** any country, from rules you or your agent write
  (`salli tax rules create|import`, or an AI client's `research_tax_rules`
  prompt) and you activate. Your tax residency (`salli profile set
  --tax-residency GB`) decides whose rules compute your tax, and the year is
  the one your active rules cover today; with none set, nothing assumes a
  country. Rule sets can be exported and shared as files, but salli-core
  ships none: see [CONTRIBUTING.md](CONTRIBUTING.md#tax-rules).
- **Imports:** OFX/QFX, QIF, camt.053, MT940, CSV and Excel statements from
  any bank. PDF statements vary the most, and have mostly been tried with Sri
  Lankan banks' so far.
- **Financial independence:** the default assumptions follow your base
  currency: its central bank's inflation target (5% for the rupee, 2% for the
  US dollar, euro and pound, and so on), a round 4% real return (Sri Lanka keeps
  Salli's original 6/10/14% nominal scenarios) and the 4% rule, each with its
  source. Currencies without figures of their own get cautious placeholders.
  They are starting points, not forecasts: `salli fi assumptions` shows what
  applies and why, and `salli profile set --fi-inflation 3%` (with
  `--fi-real-return` and `--fi-swr`) sets your own.

Everything else — the ledger, budgets, debts, investments, insurance,
subscriptions and reports — follows no country's rules.

### Currencies

Your ledger is kept in one **base currency** — any ISO 4217 currency, chosen
when you set up (`salli-server setup` asks) and fixed once you have entries. Amounts
are kept at your currency's own precision: no decimals for yen, three for
Kuwaiti dinar.

Accounts can be held in other currencies. An amount in another currency carries
the exchange rate into your base currency: the one your bank used, if you give
it (`--fx-rate`, or `fx_rate` in the API), or else the published rate for the
entry's date — [ECB reference rates](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)
through [Frankfurter](https://frankfurter.dev), and
[Rates By Exchange Rate API](https://www.exchangerate-api.com) for today's rate
in currencies the ECB does not publish. Every posting records which. When
there is no rate, Salli asks for one rather than guessing.

## Quickstart (about 10 minutes)

Salli comes in two parts: the **server** (this repository's Python package,
run with `salli-server`) holds your data and does the work, and the **`salli`
command line** (Node.js 22, in [`packages/cli`](packages/cli/README.md)) is how
you use it, from the server's machine or any other.

For the server you need [Docker](https://docs.docker.com/get-docker/),
[uv](https://docs.astral.sh/uv/) and the
[Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started).

```bash
git clone https://github.com/leafmonkeylabs/salli-core && cd salli-core
uv sync
supabase start -x studio,storage-api,imgproxy,realtime,edge-runtime,logflare,vector,postgres-meta,mailpit,supavisor,postgrest
uv run salli-server setup
uv run salli-server serve       # http://localhost:8000; API docs at /docs
```

`supabase start` runs Postgres and Auth locally (the `-x` list skips the parts
Salli doesn't use, which keeps the first download small). `salli-server setup`
writes `.env`, migrates the database, creates your account, and seeds a starter
chart of accounts. It asks for your email, a password, the currency you keep
your money in, and optionally an
[Anthropic API key](https://console.anthropic.com/) — without one, everything
except the AI features works. `salli-server doctor` checks the setup at any
time, without printing a secret.

Then, in another terminal:

```bash
npm install --global @leafmonkeylabs/salli
salli login                     # http://localhost:8000 by default; the email and password above
salli status
salli add "lunch 12.50 cash"    # the AI drafts the entry, you confirm it
salli --help
```

## Using it

| You want to… | Run |
|---|---|
| Record a transaction | `salli add "lunch 12.50 cash"`, or exactly: `salli entries add --desc Lunch --debit groceries:12.50 --credit cash:12.50` |
| Import a bank statement | `salli import statement.ofx --account checking` |
| See your tax position | `salli tax compute` |
| Budget, debts, investments, insurance | `salli budgets …`, `salli debts …`, `salli holdings …`, `salli portfolio …`, `salli insurance …` |
| Net worth and reports | `salli reports net-worth`, `salli reports export balance-sheet -o bs.csv` |
| Financial independence | `salli fi score`, `salli fi projections`, `salli goals …` |
| Talk it through | `salli chat`, or `salli ask "…"` |
| Script it | add `--json` to any command — data on stdout, messages on stderr |

Ids can be shortened to any unique prefix. More in
[packages/cli/README.md](packages/cli/README.md); coming from the old Python
`salli` commands, see [docs/cli-migration.md](docs/cli-migration.md).

### The API and MCP

The REST API lives under `/v1`; its OpenAPI document is committed in
[`openapi/openapi.json`](openapi/openapi.json), so you can generate a client
from it. Amounts are decimal strings in their currency's own precision (never
JSON numbers), with the currency alongside, and errors are
[RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) problem details.
`GET /v1/meta` describes the server: its version and sign-in endpoints.

Clients other than a browser sign in with OAuth 2.1: PKCE with a loopback
redirect on any port, or a device code (approved at `/mcp/oauth/device`) on a
machine without a browser. Tokens are issued for the REST API (`resource=…/v1`)
or for MCP, and each accepts only its own. For scripts and CI, make a personal
access token (`salli tokens create`, or `POST /v1/tokens`) and send it as a
bearer token.

To use Salli from Claude, Claude Code or ChatGPT, on the subscription you
already have, add `https://<your-salli>/mcp` as a connector. You'll approve it
on Salli's own consent page. Claude's apps connect from Anthropic's cloud, so
they need a Salli reachable over the internet; Claude Code also works with
`http://localhost:8000/mcp`. Step by step, with what each client can do:
[docs/ai-clients.md](docs/ai-clients.md). `salli mcp connections` lists what's
connected; `salli mcp disable` cuts everything off.

### Your agent, driving the CLI

```bash
salli skills install            # into ~/.claude/skills; --project for ./.claude/skills
```

Skills (from [`packages/cli/skills`](packages/cli/skills)) that teach an agent the CLI's rules: always `--json`,
confirm before writing, reverse rather than edit, and never compute money
itself. Then "add this month's statement" just works.

### The `salli` command line

[`packages/cli`](packages/cli/README.md) is a client of a running Salli server,
so it works against your own instance or one someone runs for you, from any
machine. It signs in with OAuth (in a browser, or with a device code where
there is none) or a personal access token, keeps tokens in your system
keychain, prints tables for people and the API's JSON for scripts, has stable
exit codes, and never does arithmetic on money. It is built on the TypeScript
SDK in [`packages/sdk`](packages/sdk), generated from `openapi/openapi.json`.
To run it from a checkout: `npm install && npm run build`, then
`node packages/cli/dist/salli.js`.

## Running the server

`salli-server` is for whoever runs the instance, on its own machine:

| You want to… | Run |
|---|---|
| Set up a new instance | `salli-server setup` |
| Serve the API and MCP | `salli-server serve --host 0.0.0.0 --port 8000` |
| Check it is healthy | `salli-server doctor` |
| Migrate after an upgrade | `salli-server db upgrade` (and `db current`) |
| Let someone else use it | `salli-server members add partner@example.com` |
| Scheduled work for every user (cron) | `salli-server jobs run-advisor`, `jobs sync-banks`, `jobs recompute-tax` |

Each member has their own ledger and signs in with `salli login`. Public
sign-up is off: only accounts you create can use your instance. Every
command takes `--json`.

## Configuration

Everything is in `.env` (see [`.env.example`](.env.example)); `salli-server
setup` fills in the essentials. The ones you might change:

| Setting | Default | |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Your key; every AI feature runs on it |
| `SALLI_REGISTRATION` | `closed` | `open` lets anyone who can sign in create an account |
| `SALLI_STORAGE` | `local` (after setup) | Uploaded files stay in `~/.salli/storage` |
| `MCP_PUBLIC_BASE_URL` | `http://localhost:8000` | This API's URL as MCP clients see it |

Database migrations: `salli-server db upgrade` (setup runs it for you).

## How it's built

Hexagonal: a pure domain core (`domain/` — ledger, the tax rule-set engine, FI,
budgets, debts, portfolio, insurance, risk, reports), application services
behind ports (`application/`), adapters for Postgres, Anthropic, FX and
document parsing (`adapters/`), and thin interfaces over the same services —
the FastAPI app, the MCP server, and the `salli-server` operator commands
(`interfaces/`). The `salli` command line is a client of the API.
[`CLAUDE.md`](CLAUDE.md) has the details.

### Extensions

A deployment can add to Salli without changing it: an installed package
registered under the `salli.extensions` entry point, and named in
`SALLI_EXTENSIONS`, can contribute a usage meter, an entitlement policy, API
routes, `salli-server` commands, its own tables and migrations. Salli itself ships with
none — nothing is metered and every feature is on. See
[`src/salli/extensions.py`](src/salli/extensions.py).

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).
Contributors accept the [Contributor License Agreement](CLA.md) once, by
commenting on their first pull request. Security issues:
[SECURITY.md](SECURITY.md).

## License

[GNU Affero General Public License v3.0](LICENSE). If you run a modified
Salli as a network service, you must offer its source to its users.

The TypeScript SDK and CLI in [`packages/sdk`](packages/sdk) and
[`packages/cli`](packages/cli) are [Apache-2.0](packages/sdk/LICENSE), so other
apps and integrations can embed the SDK without taking on the AGPL.
