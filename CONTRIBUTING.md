# Contributing to Salli

Thanks for helping. Bug reports, engine fixes, new fictional jurisdictions
for the tax conformance suite, and fixes are all welcome.

## Before you open a pull request

- **Accept the Contributor License Agreement** — once, on your first pull
  request. See [below](#contributor-license-agreement).
- **Keep the rules in `CLAUDE.md`.** The LLM never computes money or tax;
  posted entries are never edited; money is `Decimal`; tax rules are user data;
  nothing country-specific lives in the code (see [below](#local-knowledge)).
- **CLI-first.** A new API route needs a `salli` command in `packages/cli`
  (TypeScript, over the API), or a line in `EXEMPT` in
  `packages/cli/test/api-coverage.test.ts` saying why a person never calls
  it; that test fails otherwise. Commands print the API's JSON with `--json`,
  and amounts stay decimal strings. `salli-server` (Python) is only for what
  must run on the server's own machine: setup, serving, migrations, members,
  health and jobs across every user.
- **The API contract is committed.** A new route also needs its operation id in
  `src/salli/interfaces/api/contract.py` (it becomes a function name in every
  generated client), and `openapi/openapi.json` regenerated:
  `uv run python -m salli.interfaces.api.spec > openapi/openapi.json`.
- **Tests pass.** `uv run ruff check src tests`, `uv run ruff format --check
  src tests`, and `uv run pytest`. Migration tests need a Postgres:
  `SALLI_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres uv run pytest`
  works against `supabase start`. For `packages/`: `npm ci`, then
  `npm run typecheck`, `npm run lint`, `npm test` and `npm run check:generated`.

## Contributor License Agreement

Salli is open source under the AGPL-3.0; its TypeScript SDK and CLI
(`packages/`) are under Apache-2.0. Leaf Monkey Labs, which maintains it,
also runs Salli as a hosted service that is not open source. The
[Contributor License Agreement](CLA.md) lets Leaf Monkey Labs use your
contribution in both: you keep the copyright and can use your work however you
like, and you give Leaf Monkey Labs a broad, permanent, non-exclusive license
to it (including the right to license it under other terms) and a patent
license. Read [CLA.md](CLA.md) itself — the summary isn't the agreement.

**To accept it**, read the agreement and reply to your pull request with
exactly:

> I have read the Salli CLA and I agree to its terms.

The CLA bot then records your acceptance and its check turns green. You only
do this once; later pull requests pass automatically, until the agreement's
version changes.

- **Everyone who wrote commits** in a pull request must have accepted it, not
  only the person who opened it. Commits must be authored with an email that
  belongs to your GitHub account (https://github.com/settings/emails), or the
  bot can't match them to you — fix the email and comment `recheck`.
- **Contributing for your employer or another company?** The company accepts
  the [entity version](CLA-ENTITY.md) through someone who can sign for it:
  open an issue and we'll arrange it.
- **What's recorded, publicly:** your GitHub account and its id, the date, the
  pull request, and the version of the agreement, on the
  [`cla-signatures`](../../tree/cla-signatures) branch.

## Tax rules

salli-core carries no country's tax law, and won't take a pull request that
adds one: a country's rules are user data, a rule set (`salli.tax/1`,
[docs/taxrules.md](docs/taxrules.md)) that its user or their agent writes,
cites and checks against the authority's own worked examples. Share one as a
file (`salli tax rules export`); anyone can import it as a draft.

What belongs here is the engine: the expression language, the building
blocks, the schema and validator. A change to them needs a conformance test:
a fictional jurisdiction in `tests/taxrules/conformance/` that copies the
*structure* of the real-world feature, never its law, with the arithmetic
behind every worked example written out in `tests/taxrules/test_conformance.py`.

## Local knowledge

The same goes for everything else that differs by country. Planning
assumptions (inflation, returns, withdrawal rates) are the user's, set with
their sources; where there are none, a neutral placeholder stands in, always
labelled as one. Tax ids are generic `{scheme, value}` pairs. Investment
products, providers and rates are for the user's agent to research, citing
sources. So salli-core takes no table of any country's figures, schemes or
products, and no example that reads as one: use varied currencies and
countries in examples and tests.

`tests/contract/test_no_country_knowledge.py` keeps it that way: it fails on
one country's terms in `src/`, the CLI, the SDK, the API document, the skills
and the docs. The ISO 3166 and ISO 4217 tables (data about every country
alike) and the historical migrations are its only, commented, exceptions.

## Reporting a security issue

Please don't open a public issue — see [SECURITY.md](SECURITY.md).
