# Commercial licence for Salli's AGPL-3.0 parts

_An offer, not yet a contract. Prices are hypotheses._

## The rule: one charge per way of running Salli

| Way of running it | What you pay | Licence |
|---|---|---|
| Self-host, sharing your changes | Nothing, commercial use included | AGPL-3.0 |
| Salli's hosted service (any plan, including developer hosting) | The plan's price, commercial use included | None needed: the hosted terms cover it |
| Self-host or embed **without** sharing your changes, or with a warranty | The commercial licence below | This offer |

Nobody pays a licence fee on top of a hosted plan for the same use.

## What is under which licence

| Part | Licence | Commercial licence needed? |
|---|---|---|
| The server (`src/salli`), its migrations and the MCP server | AGPL-3.0-only | Only to avoid the AGPL's terms |
| The console (`packages/console`) | AGPL-3.0-only | Only to avoid the AGPL's terms |
| The phone app (`packages/mobile`) | AGPL-3.0-only | Only to avoid the AGPL's terms |
| The CLI (`packages/cli`) and the SDK (`packages/sdk`) | Apache-2.0 | Never |
| The MCP tool interface: tool names, argument and result schemas and descriptions, as `tools/list` returns them and as documented | Apache-2.0 | Never |
| The fidelity benchmark (`benchmark/`): questions, key, scorer and judge prompt | Apache-2.0 | Never |

Anyone may run, modify and offer Salli under the AGPL-3.0, including for
money, provided they give the people using it over a network the source of
their modified version. A client, agent or benchmark written against the
Apache-2.0 parts takes on none of the AGPL. Leaf Monkey Labs can offer other
terms because every contribution comes under the CLA (CLA.md,
CLA-ENTITY.md).

## Who it is for

An organisation that wants to:

- build Salli's server or console into a product of its own and keep its
  changes private;
- run a modified Salli for its customers on its own machines without
  publishing the changes;
- or have a written warranty and indemnity the AGPL does not give.

A person, household, practice or developer who self-hosts and shares their
changes, uses Salli's hosted service, or uses only the Apache-2.0 parts
does not need it.

## What the licence gives

- The right to use, modify and distribute the AGPL parts, for the term, in
  the named product, without the AGPL's source-sharing obligation.
- The releases during the term, and the security fixes for each supported
  release.
- A named contact for security reports and an agreed response time.
- A limited warranty that Leaf Monkey Labs has the right to grant it, and an
  indemnity against claims that Salli's own code infringes copyright.

It does not give the hosted service, its data, or the closed edition's
extensions, which are licensed separately if wanted.

## Terms (hypotheses)

| | Proposed |
|---|---|
| Term | One year, renewable |
| Fee | From USD 5,000 a year for one product, scaled by the number of people it serves; quoted, not listed |
| Pilot | A free 90-day evaluation licence, not for production |
| Payment | Annually in advance |

Each figure is a _Hypothesis_ to test with the first organisation that asks.
None has been agreed with anyone.

## Before the first licence is signed

Leaf Monkey Labs must hold the copyright it licenses: the founder assigns
it to the company, and counsel advises on the code written with an AI
assistant. Until then this stays an offer.

## How to ask

Open an issue titled "Commercial licence" on the repository, or write to the
maintainers, saying what you would build and for how many people.
