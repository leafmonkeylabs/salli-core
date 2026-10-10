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

Pure domain: no I/O, no database, no HTTP. Phase 1 of
docs/design/country-neutral-core.md: the old `salli.domain.tax` package is
untouched and is still what the app computes with.
"""
