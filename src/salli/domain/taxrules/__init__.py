"""
Tax rules as data: a country-neutral engine for rule sets (`salli.tax/1`).

A rule set is a JSON document, written by a user or their agent, that says how
one jurisdiction taxes one year. This package reads it, checks it and applies
it. Nothing in here knows any country's law.

- `expr`     the small, safe expression language rule sets are written in
- `arith`    the decimal context, rounding and band arithmetic everything shares
- `common`   field types shared by the schema and the blocks
- `blocks`   building blocks (relief, schedule, credit, …) that compile to lines
- `schema`   the document's pydantic models and its JSON Schema
- `engine`   compile a document into an ordered line graph, then evaluate it
- `validate` everything an author needs to hear about a document, examples included
- `diff`     what changed between two versions, for the review before activating
- `inputs`   a rule set's role totals, added up from a ledger's postings

Pure domain: no I/O, no database, no HTTP. Storage, the API and the MCP tools
are phase 2 (application/services/tax_rule_service.py); the old
`salli.domain.tax` package is still what `/v1/tax/compute` uses until phase 3
of docs/design/country-neutral-core.md.
"""
