# Contributing to Salli

Thanks for helping. Bug reports, tax-rule corrections, new tax packs, and
fixes are all welcome.

## Before you open a pull request

- **Sign the Contributor License Agreement.** Salli is AGPL-3.0, and Leaf
  Monkey Labs also uses this code in its hosted service. The CLA lets it do
  that with your contribution while you keep your copyright. The CLA bot will
  ask you to sign on your first pull request.
- **Keep the rules in `CLAUDE.md`.** The LLM never computes money or tax;
  posted entries are never edited; money is `Decimal`; tax packs are versioned.
- **CLI-first.** A new API route needs a `salli` command (and a line in
  `src/salli/interfaces/parity.py`), and new commands support `--json`.
- **Tests pass.** `uv run ruff check src tests`, `uv run ruff format --check
  src tests`, and `uv run pytest`. Migration tests need a Postgres:
  `SALLI_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres uv run pytest`
  works against `supabase start`.

## Tax packs

A pack is wrong until it passes golden tests built from the revenue
authority's own worked examples (`tests/golden/`). Cite the source in the
test. A pack is not used in production until a chartered accountant has
reviewed it.

## Reporting a security issue

Please don't open a public issue — see [SECURITY.md](SECURITY.md).
