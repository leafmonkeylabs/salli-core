# Metrics plan

_What we would count, why, and how a Salli server would count it without
reading anyone's money. Not built yet: nothing in Salli counts or reports
anything today, and nothing here may become a default for self-hosters._

## The three numbers

| Metric | Definition | Why |
|---|---|---|
| **Activation** | Of the books created in a week, the share that within 14 days have entries in two different calendar months, at least one from an import (a statement, a bank feed), not only opening balances | The person has done the work that makes Salli's figures theirs |
| **Weekly active** | Books with any sign-in or MCP read in the last 7 days, as a count and as a share of activated books | Whether people (or their agents) come back |
| **Retained books** | Of the books activated in a month, the share with a new entry booked in the third month after it | Whether the books stay kept, the thing that makes every figure right |

Targets are not set until the design-partner pilot gives a baseline.

## How the server would count them

- **Counts, never content.** The job reads only timestamps Salli already
  stores (when an account was created, when an entry was created and from
  what source, when a session or MCP read was last used) and turns them
  into counts per week or month. It never reads descriptions, payees,
  amounts, balances, names or documents.
- **On the server, aggregated there.** The job runs where the data is (a
  `salli-server` job, as the digests are) and stores or sends only the
  totals: for example `{"week": "2026-W44", "activated": 12, "of": 20}`.
  No per-person row leaves the database.
- **Small numbers hidden.** A cell under 10 books is reported as "fewer than
  10", so a count cannot single anyone out.
- **No third parties.** No analytics library, no tracking pixel, no
  identifier sent anywhere; the console's strict content security policy
  already forbids it.
- **Hosted only, said plainly.** The hosted service's privacy notice says
  these counts are made. A self-hosted server never counts or sends anything
  unless its owner switches the job on, and then only to where they say.
- **Pilot consent.** Design partners agree to the counts in writing; they
  are shown the exact totals sent.

## What we will not measure

Time spent in the app, clicks, scroll depth, money under management, or any
figure from anyone's books. Salli's claim is that it keeps people's money
private; the metrics have to keep that claim too.
