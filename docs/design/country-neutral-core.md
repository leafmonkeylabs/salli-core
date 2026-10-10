# A country-neutral core: tax rules and local knowledge as user data

Status: **done.** The decisions are recorded at the end. Approved on 2026-10-10 and
shipped in October 2026:

| Phase | PRs | What shipped |
|---|---|---|
| 1 | #29 | The engine, the expression language and the conformance suite |
| 2 | #30, #31 | Storage, the API, MCP and CLI, and the `tax:activate` permission |
| 3 | #32, #33 | The switch to rule sets; the country-specific code removed |

This is a design record. It describes the code as it stood when the design was
written, including the country-specific code it set out to remove. For how rule
sets work now, see [`docs/taxrules.md`](../taxrules.md).

There are **no real users yet**. So there is no user data to migrate, no need to run
two engines side by side, and no deprecation windows. Old code and endpoints are
replaced outright.

## Why

Salli's core ships one country's tax law. Sri Lanka's 2025/26 income tax lives in
`domain/tax/packs/lk_2025_26.py`, and about a dozen other places fall back to "LK" or
"LKR". Tax law changes every year, in every country. If the developers keep it in the
codebase, Salli is tied to whichever countries they have time to follow. It's also
always a release behind the law.

So **nothing country-specific is kept in salli-core**.
- **The code provides:** generic, deterministic engines and the interfaces to feed
  them.
- **The country knowledge:** tax rules, filing forms and dates, tax-ID schemes,
  planning assumptions. It's **data the user owns**, written by the user or by the AI
  agent they use (with web access). It is versioned, cited, and checked against
  worked examples before Salli computes with it.

The rule that matters most still holds: **the LLM never computes money or tax.** An
agent may *write rules*. Only Salli's engine *applies* them.

## What moves out of the code

From the survey of `main` (5186f88):

| Today, in code | Becomes |
|---|---|
| `TaxPack` and `lk_2025_26.py` (bands, relief, qualifying payments, foreign service income, the filing calendar, withholding kinds, starter accounts, rounding "nearest_rupee") | A **tax rule set**: user data, using the schema below |
| `registry.py` (`_REGISTRY`, `country_for_currency`, roles) | A per-user store of rule sets. No inference of country from currency |
| Engine's hardwired Sri Lankan buckets: `CREDITED_KINDS`, the fixed fields on `LedgerView` and `TaxComputation` (`fsi_tax`, `apit_credit`, …) | Lines the rule set defines, fed by account `tax_role`s |
| Return workflow's `_RETURN_FORMS`, `_map_to_cages` (RAMIS cages), and the instructions for `ramis.ird.gov.lk` | **Form definitions** inside the rule set: fields mapped to lines, plus filing instructions |
| `LK_TIN` / `LK_NIC`, the legacy `ird_number` / `nic` fields, and `_LEGACY_TAX_ID_COUNTRY = "LK"` | Only the generic `tax_ids` (`scheme`, `value`). A rule set may suggest schemes |
| FI `REGIONAL_DEFAULTS`, per currency (inflation targets, return scenarios) | **Planning assumptions** as user data, with sources. Projections run in real terms by default (see below) |
| `domain/agents/jurisdiction.py` `_MARKETS["LK"]` (CSE, ASPI) | Removed. The agent researches market context when it needs it |
| Tax-role enum frozen into the OpenAPI schema from `all_tax_roles()` | A string, checked against the roles in the user's active rule set |
| Golden tests from IRD worked examples | A **conformance suite of fictional jurisdictions** tests the engine. Each real rule set carries its own worked examples as data |
| Skill text and README sections about APIT, AIT, LKR and IRD | Neutral wording and examples |

The statement parsers (CSV, OFX, QIF, MT940, camt.053), the ledger, insurance, debt,
risk and budgets are already generic.

## The engine: a graph of named lines

Tax systems differ in shape, not just in numbers:
- an allowance that tapers away as income rises;
- capital gains taxed in their own bands, but stacked on top of salary;
- capped social contributions;
- formula tariffs;
- rebates with marginal relief;
- joint filing.

A fixed pipeline of bands, then reliefs, then credits can't express those. Adding them
later would mean rewriting the engine and migrating every rule set already saved.

So the engine is general from the start.

**Lines.** A rule set defines **named lines**. Each is an expression over:
- **inputs:** ledger totals by `tax_role`, and answers the user gives, such as their
  filing status;
- **other lines:** the engine evaluates them in dependency order, and rejects cycles;
- **constants.**

**The expression language** is small and safe:
- decimal arithmetic only (never floats), at 28 significant digits with every
  error trapped, plus comparisons, `if`, `min`, `max`, `clamp` and `abs`;
- `choice(answer.x, "a", value, …)` to select by a question's answer;
- `bands(amount, table)` and `band_amount(amount, table, n)` for progressive
  schedules, and `round(x, mode, unit)`;
- no loops, no recursion, no I/O and no host functions;
- a hard limit on how complex an expression can be.

It's parsed by a dedicated grammar, never Python `eval`.

**Building blocks** (`schedule`, `deduction`, `relief`, `credit`, `final_rate`) are
shorthand that compiles to lines. A simple jurisdiction stays simple to write, and a
complex one can drop to expressions where it needs to.

**The result** is every line with its key, label, amount and the expression behind it.
That's enough to explain each figure ("this came from this band, applied to this
total") and to fill forms. The result records which rule-set version produced it.

### The rule set

A rule set is a JSON document validated against a published JSON Schema
(`GET /v1/tax/schema`), so an agent can produce one reliably. An abbreviated
example:

```jsonc
{
  "schema": "salli.tax/1",
  "jurisdiction": { "country": "LK", "region": null },
  "year": { "label": "2025/26", "start": "2025-04-01", "end": "2026-03-31" },
  "currency": "LKR",
  "sources": [{ "id": "act", "url": "https://www.ird.gov.lk/…", "title": "…", "retrieved": "2026-10-10" }],

  // Inputs: what the ledger and the user supply.
  "roles": [
    { "key": "employment_income", "kind": "income", "label": "Employment income" },
    { "key": "foreign_service_income", "kind": "income", "label": "Foreign service income" },
    { "key": "apit_withheld", "kind": "withholding", "label": "APIT deducted by employer" },
    { "key": "foreign_tax_paid", "kind": "withholding", "label": "Foreign tax paid" }
  ],
  "questions": [],

  // Band tables, referred to by schedules and by bands()/band_amount().
  "band_tables": {
    "general": { "bands": [{ "upto": "1000000", "rate": "0.06" }, { "upto": "1500000", "rate": "0.18" },
                           { "upto": null, "rate": "0.36" }],
                 "round": { "mode": "nearest", "unit": "1" }, "source": "act" }
  },

  // Building blocks; each compiles to lines.
  "blocks": [
    { "type": "final_rate", "key": "fsi", "of": "role.foreign_service_income",
      "rate": "0.15", "source": "act" },
    { "type": "relief", "key": "personal_relief",
      "of": "role.employment_income", "amount": "1800000", "source": "act" },
    { "type": "schedule", "key": "general", "of": "line.personal_relief.remaining",
      "table": "general" },
    { "type": "credit", "key": "ftc", "of": "role.foreign_tax_paid",
      "refundable": false, "cap": "line.liability" },
    { "type": "credit", "key": "apit", "of": "role.apit_withheld", "refundable": true }
  ],

  // Expressions, for anything the blocks can't say (an illustrative taper).
  "lines": [
    { "key": "liability", "label": "Tax before credits",
      "expr": "line.general + line.fsi" }
  ],
  // net may be negative: after the final rounding it splits into payable or refund.
  "result": { "net": "line.liability - line.ftc - line.apit", "round": { "mode": "down", "unit": "1" } },

  "deadlines": [{ "key": "return", "label": "Return due", "date": "2026-11-30", "source": "act" }],
  "suggested_accounts": [{ "code": "4110", "name": "APIT withheld", "type": "income",
                           "tax_role": "apit_withheld" }],
  "forms": [{
    "key": "return", "label": "Annual return",
    "fields": [{ "id": "cage_1a", "label": "Employment income", "value": "role.employment_income" }],
    "instructions": "Log in to … and enter each field.", "url": "https://…"
  }],

  // Required: a rule set can't be activated until every example matches.
  "examples": [{
    "name": "Authority's worked example 3", "source": "https://…",
    "inputs": { "employment_income": "4200000", "apit_withheld": "300000" },
    "expected": { "payable": "…", "lines": { "general": "…" } }
  }]
}
```

Every figure can name the source it came from, and validation warns about any that
doesn't.

**Precision is 28 significant digits.** That's Python's default, and today's built-in
engine runs at it. A non-terminating fraction (such as a one-third cap) therefore gives
the same digits in both engines. Literals and inputs with more significant digits are
refused rather than rounded.

The authoritative reference for authors and agents is [`docs/taxrules.md`](../taxrules.md),
which ships with the engine (#29). It is kept in step with the code by tests.

### Coverage: one schema, delivered in stages

The schema and engine above are designed for the whole of personal taxation, and the
schema is frozen as `salli.tax/1` only after the conformance suite passes.

**The conformance suite** is a set of fictional jurisdictions. Each copies the
*structure* of a real-world feature, not its law:

| Fictional jurisdiction | Feature it exercises |
|---|---|
| **Taperland** | an allowance withdrawn as income rises |
| **Jointland** | filing status, and joint versus single schedules |
| **Stackland** | capital gains with their own bands, stacked on ordinary income |
| **Capland** | a social contribution capped at a ceiling |
| **Formulaland** | a formula tariff instead of bands |
| **Rebateland** | a rebate with marginal relief at the threshold |
| **Remitland** | final-rate foreign income outside the bands (today's Sri Lankan shape) |

These tests are the engine's correctness guarantee, and none of them encodes a real
country.

**Coverage arrives in stages:**
1. **Personal income tax.** Everything above except capital gains and social
   contributions.
2. **Capital gains:** lots and holding periods come from the portfolio engine.
3. **Social contributions.**

Later stages add roles, blocks and conformance jurisdictions. They don't change the
format, so existing rule sets keep working.

## Lifecycle and safety

`draft → validated → active → superseded`

**Validated** means the document:
- passes the schema;
- compiles, with no unknown references and no cycles;
- matches **every worked example** exactly, through the engine.

Validation reports each line that differs and the expression behind it.

### Activation is the user's alone, through a channel the agent can't fake

While researching tax rules, an agent reads arbitrary web pages, and any of them may
carry instructions planted to trick it. A confirmation relayed *through the agent*
("the user said yes") is only as trustworthy as the agent. So:
- **A dedicated permission.** Activating a rule set requires the `tax:activate`
  permission. OAuth tokens issued to AI connectors (MCP clients) can never be granted
  it. A user's own session, CLI login or personal access token can.
- **Agents propose.** They can draft, validate and **propose** an activation, never
  perform one.
- **A review before activation.** The user sees:
  - the diff against the active version;
  - every worked example's result;
  - the source behind each changed figure.
- **MCP elicitation, later.** Where a client supports it, Salli can ask the user
  directly instead of through the model. The permission rule still applies.

There is one active rule set per jurisdiction and year.

### Versions and provenance

- **Versions are immutable** once a computation uses them. A change creates a new
  version, with change notes and a diff against the last one.
- **Every stored computation** keeps the version id and a content hash, so an old
  return can always be reproduced, even after the rules change.
- **Every rule set carries its sources** (URLs and dates) and its author (the user, or
  the named agent).
- **Results say where their rules came from:** "computed from rules you or your agent
  entered". Salli doesn't vouch for the law.

### Sharing: imports are untrusted

- **Export and import** use a file or a URL. salli-core neither ships nor depends on
  a catalogue. One can exist outside it (Leaf Monkey Labs could run one separately).
- **An import is data, never code:** JSON validated against the schema.
- **The URL fetch is guarded.** It reuses the SimpleFIN guard against requests to
  internal or private addresses, follows no redirects to them, and enforces size and
  time limits.
- **An import always lands as a draft.** Its examples must pass, and the user
  activates it under the same `tax:activate` rule.
- **Later, optional signing:** a publisher can sign a rule set (for example with
  Sigstore), and Salli shows who signed it.

## How users and agents use it

- **API:**
  - `GET /v1/tax/schema`
  - `GET|POST /v1/tax/rule-sets`
  - `GET /v1/tax/rule-sets/{id}`
  - `POST /v1/tax/rule-sets/{id}/versions`
  - `POST /…/validate`
  - `POST /…/propose`
  - `POST /…/activate`, which needs `tax:activate`
  - `GET /…/diff`
  - `POST /v1/tax/rule-sets/import` (a file or URL)
  - `GET /…/export`
  - `POST /v1/tax/compute` uses the active rule set for the jurisdiction and year.
  - `GET /v1/tax/packs` and `meta.tax_packs` are removed in phase 3.
- **MCP tools:**
  - `get_tax_rule_schema`
  - `list_tax_rule_sets`
  - `draft_tax_rule_set`
  - `validate_tax_rule_set` (returns the lines that differ and why)
  - `propose_tax_rule_set`
  - `explain_tax_line`
- **MCP prompt** `research_tax_rules(country, year)` tells the agent to:
  1. find official sources;
  2. fill in the schema, citing each figure;
  3. include the authority's own worked examples;
  4. validate and fix until every example passes;
  5. propose, and show the user what changed and why.
- **CLI:** `salli tax rules list|show|import|export|validate|propose|activate|diff`.
- **Salli's own agent** uses the same tools; it already has web search.

The **decision lab** follows the same split. Deterministic scenario tools supply the
numbers, and the user's own agent, guided by prompts, supplies the judgement.

## Other local knowledge

- **Jurisdiction:** the user picks their tax residency explicitly, at onboarding or
  later. Salli no longer infers the country from the currency.
- **Tax IDs:** only generic `{scheme, value}` records. The legacy `ird_number` / `nic`
  fields and columns are removed. The web and mobile apps switch to `tax_ids` when the
  hosted product upgrades.
- **Planning assumptions are in real terms by default.**
  - FI projections run *after inflation*. A real-return assumption is broadly the same
    whatever the currency, so **one neutral default** (labelled as a placeholder)
    works anywhere without a per-country table.
  - Inflation and nominal returns are user data with sources, which the user or agent
    sets. Inflation matters only for showing future amounts in nominal currency.
  - Projections never block on missing assumptions. They show that a placeholder is
    in use, and Salli prompts the user or agent to set real ones.
- **Reminders:** filing reminders come from the active rule set's `deadlines`.

## Delivery

There are no real users, so nothing needs migrating and nothing is kept for
compatibility. Each phase is its own PR.

1. **Engine, expression language and conformance suite.** No behaviour change yet.
   - The line graph, the safe expression grammar, the building blocks, the schema and
     validator, and the fictional-jurisdiction suite.
   - Today's Sri Lankan pack, written as a rule set in a test fixture, must reproduce
     the existing golden results **line for line**. This proves the engine can carry
     what exists today. The fixture is deleted in phase 3.
2. **Storage, interfaces and the activation permission.**
   - New tables: `tax_rule_sets` (owner, jurisdiction, year, status) and
     `tax_rule_set_versions` (content JSONB, hash, sources, validation result,
     author).
   - `tax_computations` is reshaped around `rule_set_version_id`, a content hash and
     `lines` JSONB.
   - The new API, MCP and CLI surfaces, with `tax:activate` kept out of
     connector-issued tokens.
3. **Switch and remove, in one go.**
   - Compute uses only the rule-set store.
   - Delete the built-in packs and registry, the hardwired engine fields, the legacy
     computation columns, `_RETURN_FORMS`, `REGIONAL_DEFAULTS`, `_MARKETS`, the
     legacy tax-ID constants, fields and columns, the old `/tax/packs` endpoints, and
     the phase 1 fixture.
   - Neutralise skills, docs and tests.
   - Update CLAUDE.md.
   - Migrations drop what's gone. Developer and test databases can be recreated from
     scratch.

### Hosted Salli

The hosted product pins salli-core at `v0.1.0`, from before the 2026-10 rebuild. It
picks all of this up when it upgrades to the new core, a project with its own plan
that also moves the web and mobile apps onto the new API. Its test accounts start
fresh. If the hosted product wants to offer Sri Lankan rules to its users, it does so
as data, through the same interfaces anyone else uses.

### CLAUDE.md changes, in phase 3

| Invariant | Today | Becomes |
|---|---|---|
| Tax packs | "Tax packs are versioned `(country, year, version)` in `domain/tax/packs/` and need a chartered accountant's review." | "Tax rule sets are user data. They are versioned and immutable once used. Every stored computation records the rule-set version and content hash. A rule set can't be activated until its worked examples pass, and only the user can activate one; AI connectors never hold `tax:activate`." |
| Adding a new tax pack | A how-to for developers | Replaced by the rule-set schema docs, the conformance suite and the `research_tax_rules` prompt |

## Risks

- **Wrong rules.** A user or agent can enter the law incorrectly. Mitigations:
  - worked examples are required before activation;
  - figures are cited;
  - every change is diffed;
  - each result states plainly where its rules came from.

  This is honest: today's built-in pack is also unreviewed by an accountant, and it
  ages silently.
- **Prompt injection during research.** Agents can't activate. Activation needs a
  permission that connector tokens never hold, and the review shows sources and
  diffs.
- **Agent hallucination.** Validation fails without official worked examples, and
  sources are shown next to every changed figure.
- **The expression language as an attack surface.** A dedicated grammar, no `eval`,
  no host functions, no loops, decimal arithmetic only, and complexity limits.
  Fuzz-tested.
- **Coverage gaps.** Anything the schema can't express fails validation with a clear
  message rather than computing something wrong.
- **API churn.** The web and mobile apps use `/tax/packs`, the fixed computation
  fields and the legacy tax-ID fields. They move to the new API with the hosted
  upgrade. The TypeScript CLI and SDK move in phase 3, regenerated from the spec.

## Decisions (2026-10-10)

| # | Question | Decision |
|---|---|---|
| 1 | Scope | A general engine from the start: a line graph with a safe expression language, plus building blocks. Proven by the fictional-jurisdiction conformance suite before `salli.tax/1` is frozen. Coverage arrives in stages: personal income tax, then capital gains, then social contributions. |
| 2 | Who activates | The user only. It needs `tax:activate`, which AI-connector tokens can never hold. Agents draft, validate and propose. The user reviews diffs, examples and sources first. MCP elicitation comes later, where supported. |
| 3 | Sharing | File and URL import and export, treated as untrusted: guarded fetch, data only, lands as a draft, user activation. No catalogue in salli-core. Optional signing later. |
| 4 | Planning assumptions | Projections in real terms, with one neutral placeholder default that is always labelled as such. Users or agents set real figures with sources. Projections never block on missing assumptions. |
| 5 | Migrating existing users | Not needed: there are no real users yet. No data migration, no running two engines side by side, no deprecation windows. The old code goes in phase 3, once the new engine reproduces today's results line for line in phase 1. |
