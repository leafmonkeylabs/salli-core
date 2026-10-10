# Tax rule sets (`salli.tax/1`)

A **tax rule set** is a JSON document that says how one jurisdiction taxes one
year. A user writes it, or their AI agent does (citing official sources), and
Salli's engine applies it. The agent may *write* rules; only the engine
*computes* with them. This is the format and the language, for authors and for
agents. The design behind it is `docs/design/country-neutral-core.md`.

Salli knows no country's tax law. A user's tax is computed only from the rule
set they activated (see [Computing a user's tax](#computing-a-users-tax)):
without one, there is nothing to compute. The engine, language, schema and
validator live in `src/salli/domain/taxrules/`, proven by a conformance suite
of fictional jurisdictions; storage, the lifecycle, the API, the MCP tools and
the `salli tax` commands are described below.

## The document

```jsonc
{
  "schema": "salli.tax/1",
  "jurisdiction": { "country": "XA", "region": null },
  "year": { "label": "2031", "start": "2031-01-01", "end": "2031-12-31" },
  "currency": "USD",
  "sources": [{ "id": "act", "url": "https://example.org/act", "title": "Income Tax Act", "retrieved": "2031-02-01" }],
  "roles": [
    { "key": "salary", "kind": "income", "label": "Salary" },
    { "key": "tax_withheld", "kind": "withholding", "label": "Tax withheld" }
  ],
  "questions": [],
  "band_tables": {
    "main": {
      "bands": [{ "upto": "40000", "rate": "0.20" }, { "upto": null, "rate": "0.40" }],
      "source": "act"
    }
  },
  "blocks": [
    { "type": "relief", "key": "allowance", "of": "role.salary", "amount": "12000", "source": "act" },
    { "type": "schedule", "key": "income_tax", "of": "line.allowance.remaining", "table": "main" },
    { "type": "credit", "key": "withholding", "of": "role.tax_withheld", "refundable": true }
  ],
  "lines": [
    { "key": "balance", "label": "Tax less withholding", "expr": "line.income_tax - line.withholding" }
  ],
  "result": { "net": "line.balance", "round": { "mode": "nearest", "unit": "0.01" } },
  "deadlines": [{ "key": "return", "label": "Return due", "date": "2032-04-30", "source": "act" }],
  "suggested_accounts": [{ "code": "1450", "name": "Tax withheld", "type": "asset", "tax_role": "tax_withheld" }],
  "forms": [{ "key": "return", "label": "Annual return",
              "fields": [{ "id": "box_1", "label": "Tax", "value": "line.income_tax" }] }],
  "examples": [{
    "name": "Salary of 30,000", "source": "act",
    "inputs": { "salary": "30000" },
    "expected": { "payable": "3600", "lines": { "allowance.remaining": "18000" } }
  }]
}
```

`schema`, `jurisdiction`, `year`, `currency` and `result` are required; every
list defaults to empty. Unknown fields are refused everywhere.
`rule_set_json_schema()` (in `schema.py`) returns the document's JSON Schema,
Draft 2020-12, for agents to write against; phase 2 serves it as
`GET /v1/tax/schema`. The schema describes the shape; the validator also checks
what spans fields (unique keys, declared sources, expressions that compile,
examples that pass).

**Amounts, rates and limits are decimal strings**: `"0.15"`, `"1800000"`,
`"-3"`. A JSON number is refused, because whatever wrote `0.1` may have produced
the binary float `0.1000000000000000055…`. No exponents, separators or spaces,
and at most 28 significant digits. Dates are `"YYYY-MM-DD"`.

| Field | What it holds |
|---|---|
| `jurisdiction.country` | ISO 3166-1 alpha-2, or a user-assigned code (`AA`, `QM`–`QZ`, `XA`–`XZ`, `ZZ`) for a fictional one. `region` is free text. |
| `year` | `label` (what the authority calls it), `start` before `end`. |
| `currency` | An upper-case ISO 4217 code. Every amount is in it. |
| `sources` | `{id, url, title, retrieved?}`. Anything with a `source` field names one of these ids. |
| `roles` | Inputs from the ledger: account totals by `tax_role`. `{key, kind: income\|deduction\|withholding\|other, label, description?}`. Keys are at most 30 characters (an account's `tax_role` column). |
| `questions` | Inputs from the user. `{key, label, type: number\|boolean\|choice, choices?, default?}`. A `choice` lists its choices; a default fits the type (a decimal string, `true`/`false`, or one of the choices). With no default, an answer is required. A question can't share a role's key. |
| `band_tables` | Progressive tables by key: `{label?, bands, round?, source?}`. See [Band tables](#band-tables). |
| `blocks` | Building blocks that compile to lines. See [Building blocks](#building-blocks). |
| `lines` | `{key, label, expr, source?}`: a named amount, computed by an expression. |
| `result` | `{net, round?}`. See [The result](#the-result). |
| `deadlines` | `{key, label, date, source?}`. |
| `suggested_accounts` | Accounts a user's chart should have: `{code, name, type: asset\|liability\|equity\|income\|expense, tax_role?}`; `tax_role` names a declared role. |
| `forms` | `{key, label, fields: [{id, label, value}], instructions?, url?}`; each `value` is an expression giving a number or true/false. |
| `examples` | Worked examples: `{name, source?, inputs, expected}`. See [Validation](#validation). |

Keys are `[a-z][a-z0-9_]*`, at most 64 characters, and unique within their
kind. Blocks and lines share one namespace (a block's key is a line too).

Limits on one document: 1 MiB of JSON, 200 sources, 200 roles, 100 questions,
50 band tables of at most 40 bands, 500 blocks, 1,000 lines (2,000 once blocks
are expanded), 50 forms and 200 examples.

## The expression language

Lines, block fields, `result.net` and form fields are expressions in a small
language of decimal arithmetic. It is parsed by its own grammar (never Python's
`eval`), has no loops, recursion, attribute access or host functions, and is
type-checked before anything runs.

### Values and references

- **Numbers**: digits with an optional fraction, `_` allowed between digits:
  `1_800_000`, `0.15`. No exponent, no leading `.`; at most 28 significant
  digits. A negative number is `-` applied to one.
- **Booleans**: `true`, `false`.
- **References**, in three namespaces:
  - `role.<key>`: the ledger's total for that role (zero when there is none);
  - `answer.<key>`: the user's answer to that question;
  - `line.<key>`: another line's amount. Lines a block compiled to have dotted
    keys: `line.income_tax.band_2.tax`.
- **Strings** appear only where a function needs a name: a rounding mode, a
  band table, a choice's option. They are keys in double quotes: `"nearest"`,
  `"main"`, `"joint"`.

### Operators, loosest first

| | |
|---|---|
| `or` | either is true (the right side runs only when needed) |
| `and` | both are true (likewise) |
| `not` | |
| `<  <=  >  >=  ==  !=` | compare two numbers (`==`/`!=` also two booleans); can't be chained: write `a < b and b < c` |
| `+  -` | |
| `*  /` | |
| `-x` | negation |

Operators of the same level group left to right: `10 - 4 - 3` is 3.
Parentheses group as usual. So `not a < b` is `not (a < b)`, and `-2 * 3` is −6.

### Functions

| Function | Value |
|---|---|
| `min(a, b, ...)`, `max(a, b, ...)` | the smallest or largest of two or more numbers |
| `clamp(x, lo, hi)` | `x`, but at least `lo` and at most `hi` (an error if `lo > hi`) |
| `abs(x)` | `x` without its sign |
| `if(cond, then, else)` | `then` when `cond` is true, else `else`; only the chosen branch runs, so `if(x == 0, 0, y / x)` is safe; both branches have the same type |
| `round(x, mode, unit)` | `x` rounded to a multiple of `unit`, a positive number literal (`1` whole units, `0.01` hundredths, `5` fives); modes below |
| `bands(amount, "table")` | the tax on `amount` over a band table |
| `band_amount(amount, "table", n)` | the part of `amount` in band `n` (counting from 1; `n` a whole number literal) |
| `choice(answer.x, "a", value_a, "b", value_b, ...)` | the value listed for the user's answer to a choice question. It must list every one of the question's choices, and only those; only the chosen value runs. |

**Rounding modes.** For a value between two multiples of `unit`:

| Mode | |
|---|---|
| `"nearest"` | the nearer; a tie goes away from zero (ROUND_HALF_UP): 2.5 → 3, −2.5 → −3 |
| `"half_even"` | the nearer; a tie goes to the even multiple: 2.5 → 2, 3.5 → 4 |
| `"down"` | towards zero: 2.9 → 2, −2.9 → −2 |
| `"up"` | away from zero: 2.1 → 3, −2.1 → −3 |

Rounding works on the size of a value, so a refund (a negative net) rounds the
same way a bill does.

### Types

Every expression is a number, a boolean, or (only a choice question's answer) a
choice. Arithmetic and ordering need numbers; `and`, `or`, `not` and `if`'s
condition need booleans; `==` compares two values of the same type. A choice
answer can only be `choice()`'s first argument. Lines and `result.net` must be
numbers; form fields may be numbers or booleans.

### Arithmetic

Everything is exact decimal arithmetic to 28 significant digits (Python's
default context), installed fresh
for every evaluation so nothing outside can change a result. Division by zero,
an undefined result (`0 / 0`) and an overflow are errors, never NaN or
infinity. The same document and inputs always give the same figures.

### Limits

An expression may be at most 4,000 characters, 1,000 parts (numbers,
references, operators, calls), 50 levels deep (operators, calls and
parentheses all count), and a function takes at most 64 arguments. Errors give
the line and column, and a caret under the mistake:

```
lines[0].expr: Unknown function or name 'mn' (line 1, column 1)
mn(role.salary, 5000)
^
```

## Band tables

```json
"main": {
  "bands": [
    { "upto": "10000", "rate": "0.05" },
    { "upto": "30000", "rate": "0.15" },
    { "upto": null, "rate": "0.25" }
  ],
  "round": { "mode": "nearest", "unit": "1" },
  "source": "act"
}
```

`upto` is each band's ceiling counted from zero, the way tables are printed:
the second band above taxes 10,000 to 30,000. Ceilings are positive and
ascend; the last band has none (`null`), and only the last. To stop taxing
above a ceiling, end with a band at rate `"0"`. Rates are between 0 and 1.

`round`, when given, rounds each band's tax on its own before the bands are
added, as some authorities do. Nothing falls in any band of an amount of zero
or less.

## Building blocks

Blocks are shorthand for shapes tax law keeps repeating. Each compiles to
ordinary lines, which a computation lists like any other, so an explanation
can show exactly what a block became. Every block has `type`, `key`, and
optionally `label` and `source`. For a block with key `k`:

| Block | Fields | Lines |
|---|---|---|
| `relief` | `of`, `amount` | `k` = `min(amount, max(0, of))`, the amount applied; `k.remaining` = `max(0, of - line.k)` |
| `deduction` | `of`, `amount` | the same as `relief`, for laws that call it a deduction |
| `capped_share` | `of`, `claimed`, `fraction`, `cap?` | `k.limit` = `min(of * fraction, cap)` (or `of * fraction`); `k` = `min(claimed, line.k.limit)`; `k.remaining` = `max(0, of - line.k)` |
| `schedule` | `of`, `table` | for each band `N`: `k.band_N.amount` = `band_amount(of, table, N)` and `k.band_N.tax` = that amount times the band's rate (rounded if the table rounds per band); `k` = the sum of the band taxes |
| `final_rate` | `of`, `rate`, `round?` | `k` = `of * rate`, rounded if `round` is given |
| `credit` | `of`, `refundable`, `cap?` | `k` = `of`, or `min(of, cap)`; the line records whether the credit is refundable |

`of`, `amount`, `claimed` and a credit's `cap` are expressions; `fraction` and
`rate` are decimal strings from 0 to 1, a `capped_share`'s `cap` a
non-negative decimal string.

The engine doesn't apply credits on its own: `result.net` subtracts them. A
non-refundable credit should be capped at the tax it may reduce, or it can turn
into a refund; validation warns when one has no cap.

## The result

`result.net` is what the taxpayer owes after every credit: positive to pay,
negative to be refunded. It is rounded with `result.round` (if given), then
split: `tax_payable` is the net when positive, `refund_due` its size when
negative, and the other is zero.

A computation returns every line, each after the lines it uses (otherwise in
the order declared, blocks before lines), with its key, label, amount, the
expression behind it, its source and, for a credit, whether it is refundable.
It also carries the net, payable, refund, each form's field values and the
document's content hash.

Inputs: a role with no total is zero. A question with no answer takes its
default, or is an error. A role or question the rule set doesn't declare is an
error, never ignored.

## Validation

`validate(document)` checks, in order:

1. **JSON and schema.** Duplicate keys in an object, NaN, a JSON number where a
   decimal string belongs, a missing or unknown field: each reported with its
   path, like `band_tables.main.bands[0].rate`.
2. **Compilation.** Every expression parses; every reference names a declared
   role, question, line or band table; no lines depend on each other in a
   cycle (the cycle is named: `a -> b -> a`); the types agree; every `source`
   names a declared source.
3. **Warnings**, which don't block: a band table or deadline with no source;
   a `final_rate` or `capped_share` block with no source; any other block, or a
   line, whose expressions contain a figure (a number other than 0 or 1) but
   which has no source; a role, question or band table that is never used; a
   non-refundable credit with no cap. When Salli stores a version it adds one
   more: each tax role the user's accounts carry that none of their rule sets
   in use declares any more ([below](#evaluating-against-the-ledger)).
4. **Examples.** Each runs through the engine. Every figure it expects (the
   `payable` amount, the `refund`, and any `lines` by key, dotted keys
   included) must match exactly. A mismatch names the figure, what was expected,
   what came out and the expression behind it:

   ```
   payable: expected 2999, got 3000 (from line.balance)
   ```

A report is **ok** only with no errors, at least one example, and every
example passing. That is the bar before Salli will compute with a rule set:
include the authority's own worked examples wherever there are any.

## Content hash

Each document has a content hash: SHA-256 of its canonical JSON (the validated
document with every field present, keys sorted, no whitespace, decimals in
their shortest form). Two spellings of the same rules (different key order or
spacing, `"0.150"` for `"0.15"`) hash alike; any change to the rules changes
it. Every computation carries the hash of the rules that produced it.

## Examples to learn from

`tests/taxrules/conformance/` holds seven fictional jurisdictions, each
showing one shape real tax systems have, with the arithmetic behind every
example in `tests/taxrules/test_conformance.py`:

| | |
|---|---|
| `taperland.json` | an allowance withdrawn as income rises |
| `jointland.json` | a filing-status question choosing allowances and band tables |
| `stackland.json` | capital gains in their own bands, stacked on top of ordinary income |
| `capland.json` | a social contribution between a floor and a ceiling |
| `formulaland.json` | a formula tariff in zones, rounded down to whole units |
| `rebateland.json` | a rebate with marginal relief at its threshold |
| `remitland.json` | final-rate foreign income, a capped foreign tax credit, and refundable withholding |

## Lifecycle

A user's rule sets are stored per jurisdiction and year: one rule set per
country, region and year label, holding a series of **versions**. A version's
document never changes once stored (the database refuses it): an edit is a
new version, with a note saying why. Each version has a status:

| Status | Meaning |
|---|---|
| `invalid` | The document doesn't compile (schema, references, types, cycles). |
| `draft` | It compiles, but its worked examples are missing or don't all pass. Every import lands here (or as `invalid`) until it is validated. |
| `validated` | It compiles and every example passes: the report is **ok**. |
| `proposed` | Someone (usually an agent) asks the user to review and activate it. Needs an ok report. |
| `active` | What Salli computes with for that jurisdiction and year. At most one per rule set. |
| `superseded` | Was active; kept unchanged as history. |

- **Storing never fails for being wrong**, so an agent can iterate: a draft
  with mistakes is stored with its report. Refused outright: anything that
  isn't a JSON object, more than 1 MiB, or a document whose
  `jurisdiction.country` and `year.label` can't be read.
- **Validate** runs the validator again and stores the report; a draft,
  invalid, validated or proposed version moves to what the report says.
- **Propose** and **activate** run validation again rather than trust the
  stored report, and refuse (409) a version that isn't ok.
- **Activate** supersedes the rule set's active version in one transaction,
  under a lock on the rule set, and is written to the audit log.
- **Diff** compares two versions (by default the active one with another):
  each change has a path that survives reordering
  (`blocks[key=allowance].amount`), figures are compared as numbers (`"0.150"`
  is `"0.15"`), and each change names the source it cites, with that source's
  URL. With the `to` version's example results, that is the review before
  activating.
- **Export** gives the canonical JSON, so the file's SHA-256 is its content
  hash. **Import** takes a document or an https URL and lands as a draft.
- **Evaluate** applies a version to the user's own ledger, read-only (below).

### Who may activate: `tax:activate`

An agent researching tax law reads arbitrary web pages, any of which can carry
instructions planted to trick it, and "the user said yes" relayed through the
agent is only as trustworthy as the agent. So activation needs the
`tax:activate` permission, which follows from how the caller signed in
(`application/permissions.py`, the one place it is decided):

| Sign-in | `tax:activate` |
|---|---|
| The web or mobile app (a Supabase session) | yes |
| The local-development sign-in | yes |
| OAuth for the REST API, as Salli's own CLI (`salli-cli`, a first-party client the server knows), from any grant | yes |
| A personal access token | only if made with it |
| OAuth for the REST API, as a client that registered itself | no |
| OAuth for MCP (an AI connector), any client | never |

A client that registers itself (RFC 7591) can call itself anything, so only a
client the server seeded as first party counts; `/v1/meta` names the CLI's
(`oauth.cli_client_id`). An MCP token is refused by the REST API altogether,
the MCP server has no activate tool, and the service checks the permission
itself, so no route or tool that forgot to could activate. What a caller
without it writes is recorded as written by an `agent`, with the client's
name (a personal access token's writes are the user's, under the token's
name).

**Personal access tokens opt in.** Tokens are what people hand to scripts and
agents, so a token holds `tax:activate` only if the user asked for it when
making it (`POST /v1/tokens` with `"permissions": ["tax:activate"]`, or
`salli tokens create <name> --allow tax:activate`); it is the one sign-in whose
permissions are stored (`personal_access_tokens.permissions`, core_0012), and
tokens made before then hold none. Only a first-party sign-in may make a token
(never a token, never a client that registered itself), and only with
permissions it holds itself. `GET /v1/tokens` shows each token's permissions,
and `GET /v1/auth/me` what the current sign-in holds.

**The honest limit.** An agent running on the user's own machine, in the
user's own terminal, with the user's own credentials, *is* the user as far as
any server can tell. Nothing Salli checks can tell such an agent from its
user. The protections are layered so that, short of that, activation stays
with a person looking at what they activate:

- remote AI connectors (MCP) can never hold the permission;
- personal access tokens don't carry it unless the user opts in;
- the CLI's `activate` needs a person at a terminal (below), and has no `--yes`;
- its review screen makes plain what is being activated, what changed, the
  source of each changed figure, whether every worked example passes, and who
  wrote it.

### Evaluating against the ledger

For each role the rule set declares, Salli adds up the postings on the user's
accounts whose `tax_role` is that role's key, dated within `year.start` to
`year.end` (both included):

- in the account's normal-balance direction (debits add on asset and expense
  accounts, credits on income, liability and equity ones), so income and tax
  withheld come out positive;
- signed, so a reversing entry cancels the entry it reverses;
- never clamped: a negative total is used as it is, with a warning;
- in the rule set's currency: the base-currency amounts when they are the
  same, otherwise a posting already in the rule set's currency at its own
  amount and any other at the published rate for its entry's date (refused,
  never guessed, when there is no rate); each total is then rounded to the
  currency's minor units.

Then the engine computes every line. Limits for now: an account counts
towards one role (its `tax_role`); amounts come only from the ledger and the
user's answers (no portfolio lots, so no capital gains yet); and conversion is
always at each entry date's rate, never an annual average.

An account's `tax_role` must be a role one of the user's own rule sets
declares now: in a version that matches the schema and hasn't been superseded
(whatever else its status, so accounts can be set up while the rules are
still a draft). Salli has no roles of its own. An account keeps its role when
the version that declared it is superseded (an edit that keeps a role never
fails on it), but then counts towards no tax: validating, proposing or
activating any version of the user's rules warns about each such role and
the accounts that carry it (path `roles`), never refuses.

## Computing a user's tax

`TaxService` (application/services/tax_service.py) computes a user's tax with
their **active** rule set, and nothing else.

**Whose rules.** The jurisdiction is the country asked for (`country`, which
may be a user-assigned code such as `XA`), or else the user's tax residency
from their profile: never their currency. With neither, nothing is computed.
Within it:

- **the year** is the one asked for (`year`, as the rules name it); or, with
  none, the **current tax year**: the year of the user's active rule set
  whose dates contain today. When today is in no such year (the year has
  ended and next year's rules aren't in yet, say), it is the latest active
  year that has begun. Active rules only for years that haven't begun need
  the year named.
- **the region**, for rules set per region, is the one asked for; without
  one, the national rule set (no region), or the only one there is. Two
  regional rule sets and no national one need the region named.

Anything missing is a 422 problem, `/problems/no-tax-rules`, whose detail
says what is missing (no residency, no rule set for the jurisdiction and
year, one not activated yet, a year that hasn't begun, a region to choose)
and what to do: add rules with `salli tax rules create|import`, or have an
AI agent research them (the MCP `research_tax_rules` prompt), then activate
them yourself.

**Computing.** The active version's rules are applied to the ledger exactly
as [evaluating](#evaluating-against-the-ledger) does, with the user's answers
to the rules' questions. A computation is stored (`POST /tax/compute`) with:

| Field | |
|---|---|
| `rule_set_version_id`, `version`, `content_hash` | The exact version that computed it, and its content hash. |
| `country`, `region`, `year`, `currency` | The jurisdiction and year, and the rules' currency. |
| `lines` | Every line: key, label, amount (an exact decimal string), the expression, its source, whether a credit is refundable. |
| `net`, `tax_payable`, `refund_due` | What is owed: stored as integer minor units of the currency. |
| `inputs` | What the engine was given: each role's total (and how many postings it came from), the answers, the base currency, the exchange rates. |
| `warnings` | Negative role totals; a version that hasn't passed its examples; a net finer than the currency's smallest unit. |

The amount owed is money, so it is kept in the currency's minor units. When
the rules leave the net finer than that (no `result.round`, say), it is
rounded half-up to the minor unit, and the computation says so: give the
rules a `result.round` saying how the authority rounds.

**Reproducing.** A stored computation always reproduces: evaluating the very
version it recorded (versions never change) with the inputs it recorded gives
the same lines and the same amount owed, whatever the rules or the ledger say
since (`TaxService.reproduce`). `salli-server jobs recompute-tax` recomputes
every user's latest computation for each jurisdiction and year with the
rules active now and the ledger as it is now (storing it with `--apply` when
anything moved), and says for each whether it still reproduces from its own
version.

**Explaining.** `POST /tax/explain` computes with the active rules (nothing
stored) and reads one line off the result: its amount and expression, where
in the rules it is written (and the block it came from), the source it
cites, every role total, answer and other line it uses with their values,
any band table it applies, and the lines that use it. Nothing is worked out:
every figure is the engine's.

**Returns.** A rule set's `forms` are the user's return. `POST
/tax/returns/prepare` computes (and stores) the tax and fills in each form's
fields from the result, with the form's filing instructions and URL, and
holds the draft for review on a thread of the user's own
(`<user>:return:<thread>`). `GET /tax/returns/{thread}` reads the draft back;
`POST /tax/returns/resume` takes the user's decision: `approve` gives the
worksheet, ready to file; `reject` ends it; `edit` computes again (after the
ledger is fixed, or with new `answers`) and comes back to review. Nobody
edits a figure, and Salli files nothing. Rules without forms have no return
to prepare (the computation is still stored).

**Filing reminders** are the active version's `deadlines`. Activating a
version seeds them, and replaces the reminders of the version it supersedes:
a deadline it keeps stays as it was (still done, if it was done and its date
hasn't moved), a moved one is updated and goes back to pending, a new one is
added and a dropped one removed. Reminders the user made are never touched.
`POST /reminders/seed` refreshes them on demand.

**Suggested accounts.** Onboarding opens no tax accounts: no rule set exists
then. `GET /tax/rule-sets/{id}/suggested-accounts` lists the accounts a rule
set suggests (from its active version, else its newest) and whether the user
has one with each code; `POST` creates the missing ones, in the base
currency, with their tax roles. Idempotent: an account whose code is taken
(open or closed) is left as it is, and reported with how it differs.

## Interfaces

**API** (`/v1`, typed, errors as RFC 9457 problems):

| | |
|---|---|
| `GET /tax/schema` | The JSON Schema. |
| `GET /tax/rule-sets` | The user's rule sets, with their versions. |
| `POST /tax/rule-sets` | A new rule set from `{document, note?}` (the document as JSON text, read strictly, or as JSON). 409 if one exists for that jurisdiction and year. |
| `GET /tax/rule-sets/{id}` | One rule set. |
| `POST /tax/rule-sets/{id}/versions` | A new version. |
| `GET /tax/rule-sets/{id}/versions/{version_id}` | The document and its report. |
| `POST …/validate`, `…/propose`, `…/activate` | The lifecycle. Activate needs `tax:activate` (403 otherwise). |
| `GET /tax/rule-sets/{id}/diff?to=&from=` | The review diff (`from` defaults to the active version). |
| `GET …/export` | `{filename, content_hash, canonical, text}`. |
| `POST /tax/rule-sets/import` | `{document}` or `{url}`; lands as a draft. |
| `POST …/evaluate` | `{answers?, year?}`: the line-by-line result from the ledger. |
| `GET\|POST /tax/rule-sets/{id}/suggested-accounts` | The accounts the rules suggest; `POST` creates the missing ones. |
| `POST /tax/compute?country=&region=&year=` | `{answers?}`: the user's tax with their active rules, stored. |
| `GET /tax/latest?country=&region=&year=` | The last stored computation, or `{result: null}`. |
| `GET /tax/current-year?country=&region=` | The current tax year, and the year computing defaults to. |
| `POST /tax/explain?country=&region=&year=` | `{line_key, answers?}`: where one line came from. 404 for a line the rules don't have. |
| `POST /tax/returns/prepare` | `{thread_id?, year?, country?, region?, answers?}`: a return held for review. |
| `GET /tax/returns/{thread_id}` | The draft waiting for review on the thread. |
| `POST /tax/returns/resume` | `{thread_id, decision: approve\|edit\|reject, answers?}`. |

Another user's rule set or version is a 404, exactly like one that doesn't
exist.

**URL import** goes through Salli's SSRF guard (`adapters/net`): https only,
no credentials in the URL, every address the host resolves to public (not
loopback, private, link-local, shared, unique local, multicast or reserved,
nor an IPv6 address embedding one), the connection made to the address that
was checked, at most three redirects each checked again, 1 MiB at most and
15 seconds for the whole exchange.

**CLI** (`packages/cli`, see its README): `salli tax schema [-o file]`;
the user's tax:

| | |
|---|---|
| `salli tax year [--country] [--region]` | The current tax year, and the year computing defaults to. |
| `salli tax compute [--year] [--country] [--region] [--answer key=value]…` | Every line, then net, payable or refund, and the rules' version. |
| `salli tax latest [--year] [--country] [--region]` | The last stored computation. |
| `salli tax explain <line> [--year] [--country] [--answer]…` | What a line used, and its source. |
| `salli tax return prepare [--year] [--country] [--answer]… [--thread]` | The rules' forms filled in, held for review. |
| `salli tax return review <thread> [--approve\|--edit\|--reject] [--answer]…` | Shows the draft, then the decision (asked at a terminal); an edit computes again and comes back to review. |

and the rule sets:

| | |
|---|---|
| `salli tax rules list` | Rule sets, their active and newest versions. |
| `salli tax rules show <set> [--version <n\|id>]` | Versions with status, author, note and hash; or one version's details and validation report. |
| `salli tax rules create <file> [--note]` | A new rule set (the file's text is sent as it is, so it is read strictly). |
| `salli tax rules version <set> <file> [--note]` | A new version. |
| `salli tax rules import <file\|url>` | Lands as a draft. |
| `salli tax rules export <set> [--version] [-o file]` | The canonical text, byte for byte. |
| `salli tax rules validate <set> [--version]` | Problems, warnings, every example; each mismatch with expected, got and its expression. Exits 1 until valid. |
| `salli tax rules propose <set> [--version]` | |
| `salli tax rules diff <set> [--from] [--to]` | Active against newest by default; each changed figure with its source's title and URL. |
| `salli tax rules evaluate <set> [--version] [--answer key=value]…` | Line by line, then net, payable or refund. |
| `salli tax rules accounts <set> [--version] [--apply]` | The accounts the rules suggest; `--apply` creates the missing ones. |
| `salli tax rules activate <set> [--version]` | For a person at a terminal only (below). |

`<set>` is a rule set's id, a unique start of it, or its name (`XA 2031`);
`--version` a number or a version id; without it, the newest. `--json`
prints the API's JSON, as everywhere in the CLI.

`activate` defaults to the newest proposed version. It shows a review: the
diff against the active version (or "first version"), each changed figure
next to its source, every worked example and whether it passes, and the
author (the user, or an agent and its client's name) with the change note.
Then the user types the version number to confirm. It refuses, before
signing in, when stdin or stdout isn't a terminal or when the output is for
a program (`--json`, `--output`), and has no `--yes`: an agent running
commands can't answer the prompt. A 403 from the server is explained (an
agent's or another application's sign-in, or a token made without
`tax:activate`) with what to do instead.

`salli login` signs in as `salli-cli` (the browser's PKCE flow and the device
flow alike), the client `/v1/meta` names as `oauth.cli_client_id`, so its
sign-ins hold `tax:activate`. Against a server that names none it registers
a client for itself, which doesn't; `salli doctor` says so.

**MCP** (see [ai-clients.md](ai-clients.md)): `get_tax_computation` and
`explain_tax_line` (the user's tax from their active rules, read-only);
`get_tax_rule_schema`, `list_tax_rule_sets`, `get_tax_rule_set`,
`draft_tax_rule_set`, `validate_tax_rule_set`, `propose_tax_rule_set`,
`diff_tax_rule_set_versions`, `evaluate_tax_rule_set` and
`suggested_tax_accounts`; and the `research_tax_rules(country, year)` prompt.
No activate tool. Salli's own agents have `get_tax_computation` and
`explain_tax_line` too, and are told the user's residency and which rules are
active, never a figure: those reach the user only through the engine.
