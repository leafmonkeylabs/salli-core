# A country-neutral core: tax rules and local knowledge as user data

Status: **proposal, awaiting sign-off.** Nothing here is built yet.

## Why

Salli's core ships one country's tax law. Sri Lanka's 2025/26 income tax lives in
`domain/tax/packs/lk_2025_26.py`, and about a dozen other places fall back to "LK" or
"LKR". Tax law changes every year, in every country. If the developers keep it in the
codebase, Salli is tied to whichever countries they have time to follow. It's also
always a release behind the law.

This proposal is that **nothing country-specific is kept in salli-core**.
- **The code provides:** generic, deterministic engines and the interfaces to feed
  them.
- **The country knowledge:** tax rules, filing forms and dates, tax-ID schemes,
  planning assumptions. It becomes **data the user owns**, written by the user or
  by the AI agent they use (with web access). It is versioned, cited, and checked
  against worked examples before Salli computes with it.

The rule that matters most still holds: **the LLM never computes money or tax.** An
agent may *write rules*. Only Salli's engine *applies* them.

## What moves out of the code

From the survey of `main` (5186f88):

| Today, in code | Becomes |
|---|---|
| `TaxPack` and `lk_2025_26.py` (bands, relief, qualifying payments, foreign service income, the filing calendar, withholding kinds, starter accounts, rounding "nearest_rupee") | A **tax rule set**: user data, using the schema below |
| `registry.py` (`_REGISTRY`, `country_for_currency`, roles) | A per-user store of rule sets. No inference of country from currency |
| Engine's hardwired Sri Lankan buckets: `CREDITED_KINDS`, the fixed fields on `LedgerView` and `TaxComputation` (`fsi_tax`, `apit_credit`, …) | Income kinds, deductions and credits the rule set declares, keyed by account `tax_role` |
| Return workflow's `_RETURN_FORMS`, `_map_to_cages` (RAMIS cages), and the instructions for `ramis.ird.gov.lk` | **Form definitions** inside the rule set: fields mapped to computation lines, plus filing instructions |
| `LK_TIN` / `LK_NIC`, the legacy `ird_number` / `nic` fields, and `_LEGACY_TAX_ID_COUNTRY = "LK"` | Only the generic `tax_ids` (`scheme`, `value`). A rule set may suggest schemes |
| FI `REGIONAL_DEFAULTS`, per currency (inflation targets, return scenarios) | **Planning assumptions** as user data, with sources. One neutral fallback stays in code |
| `domain/agents/jurisdiction.py` `_MARKETS["LK"]` (CSE, ASPI) | Removed. The agent researches market context when it needs it |
| Tax-role enum frozen into the OpenAPI schema from `all_tax_roles()` | A string, checked against the roles in the user's active rule set |
| Golden tests from IRD worked examples | Engine tests against a **fictional jurisdiction**. Each real rule set carries its own worked examples as data |
| Skill text and README sections about APIT, AIT, LKR and IRD | Neutral wording and examples |

The statement parsers (CSV, OFX, QIF, MT940, camt.053), the ledger, insurance, debt,
risk and budgets are already generic.

## The tax rule set

A rule set is a JSON document validated against a published JSON Schema
(`GET /v1/tax/schema`), so an agent can produce one reliably. An abbreviated
example:

```jsonc
{
  "schema": "salli.tax/1",
  "jurisdiction": { "country": "LK", "region": null },
  "year": { "label": "2025/26", "start": "2025-04-01", "end": "2026-03-31" },
  "currency": "LKR",
  "sources": [{ "url": "https://www.ird.gov.lk/…", "title": "…", "retrieved": "2026-10-10" }],

  // What the ledger feeds in: account tax_roles grouped into kinds.
  "roles": [
    { "key": "employment_income", "kind": "income", "label": "Employment income" },
    { "key": "foreign_service_income", "kind": "income", "label": "Foreign service income" },
    { "key": "apit_withheld", "kind": "withholding", "label": "APIT deducted by employer" }
  ],
  "income": [
    { "key": "general", "roles": ["employment_income", "business_income"] },
    { "key": "foreign_service", "roles": ["foreign_service_income"] }
  ],

  // Applied in order to the income they name.
  "deductions": [
    { "key": "personal_relief", "type": "fixed", "amount": "1800000", "from": ["general"] },
    { "key": "qualifying_payments", "type": "capped_share", "roles": ["qualifying_payment"],
      "share_of": "taxable", "fraction": "0.3333", "cap": "1200000" }
  ],
  "schedules": [
    { "key": "general", "income": ["general"],
      "bands": [{ "upto": "1000000", "rate": "0.06" }, { "upto": "1500000", "rate": "0.18" },
                { "upto": null, "rate": "0.36" }] }
  ],
  "final_rates": [
    { "key": "fsi", "income": "foreign_service", "rate": "0.15",
      "note": "Remitted through a bank" }
  ],
  "credits": [
    { "key": "foreign_tax", "roles": ["foreign_tax_paid"], "refundable": false, "cap": "liability" },
    { "key": "apit", "roles": ["apit_withheld"], "refundable": true }
  ],
  "rounding": { "lines": { "mode": "nearest", "unit": "1" }, "final": { "mode": "down", "unit": "1" } },

  "deadlines": [{ "key": "return", "label": "Return due", "date": "2026-11-30" }],
  "suggested_accounts": [{ "code": "4110", "name": "APIT withheld", "type": "income",
                           "tax_role": "apit_withheld" }],
  "forms": [{
    "key": "return", "label": "Annual return",
    "fields": [{ "id": "cage_1a", "label": "Employment income", "value": "income.general" }],
    "instructions": "Log in to … and enter each field.", "url": "https://…"
  }],

  // A rule set can't be activated until every example produces its expected result.
  "examples": [{
    "name": "IRD worked example 3", "source": "https://…",
    "inputs": { "employment_income": "4200000", "apit_withheld": "300000" },
    "expected": { "tax_payable": "…", "lines": { "schedule.general": "…" } }
  }]
}
```

**The engine applies these steps, always in the same order:**
1. Total each income kind from the ledger, by tax role.
2. Carve out the income taxed at final rates.
3. Apply the deductions, in order, each to the income it names.
4. Run the band schedules.
5. Compute the final-rate tax.
6. Apply the non-refundable credits, capped as declared.
7. Apply the refundable credits.
8. Round, then split the result into payable or refund.

Every figure becomes a **line** with a key, a label and an amount. The result records
which rule-set version produced it.

**What v1 covers:** band-based personal income tax with reliefs, capped deductions,
flat or final-rate income and credits. That's the shape of Sri Lanka's tax today, and
of many others.

**What v1 doesn't cover:**
- phase-outs;
- formula tariffs such as Germany's;
- joint filing;
- social contributions with caps;
- capital-gains regimes.

Those need a **small, safe expression language** in v2. It would compute in Decimal,
with no loops and no I/O; CEL or a minimal arithmetic grammar would do. The schema is
versioned (`salli.tax/1`) so that v2 can add it without breaking v1 rule sets.

## Lifecycle and safety

`draft → validated → active → superseded`

- **Validated:** the document passes the schema, and **every worked example** runs
  through the engine and matches its expected result. Validation reports each line
  that differs.
- **Active:** only the user can activate a rule set, from the API, the CLI or a client.
  There is one active rule set per jurisdiction and year. An agent can draft, validate
  and *propose*, but never activate. This is the same human gate the return workflow
  already has.
- **Versions are immutable** once a computation uses them. A change creates a new
  version, with change notes and a diff against the last one. Every stored
  computation keeps the version id and a content hash, so an old return can always be
  reproduced, even after the rules change.
- **Provenance:**
  - every rule set carries its sources (URLs and dates) and its author (the user,
    or the named agent);
  - results always say "computed from rules you or your agent entered";
  - Salli doesn't vouch for the law.
- **Sharing is optional and outside the core.** A rule set can be exported or
  imported as a file or a URL. Before activating an imported one, its examples must
  pass and the user must activate it. A community catalogue could exist somewhere,
  but salli-core neither ships one nor depends on one.

## How users and agents use it

- **API:**
  - `GET /v1/tax/schema`
  - `GET|POST /v1/tax/rule-sets`
  - `GET /v1/tax/rule-sets/{id}`
  - `POST /v1/tax/rule-sets/{id}/versions`
  - `POST /…/validate`
  - `POST /…/activate`
  - `GET /…/diff`
  - `POST /v1/tax/compute` uses the active rule set for the jurisdiction and year.
  - `GET /v1/tax/packs` and `meta.tax_packs` are removed after a deprecation window.
- **MCP tools:**
  - `get_tax_rule_schema`
  - `list_tax_rule_sets`
  - `draft_tax_rule_set`
  - `validate_tax_rule_set` (returns the lines that differ)
  - `propose_tax_rule_set` (asks the user to activate)
- **MCP prompt** `research_tax_rules(country, year)` tells the agent to:
  1. find official sources;
  2. fill in the schema, citing each figure;
  3. include the authority's own worked examples;
  4. validate;
  5. show the user what changed.
- **CLI:** `salli tax rules list|show|import|export|validate|activate|diff`.
- **Salli's own agent** uses the same tools; it already has web search.

The decision lab follows the same split. Deterministic scenario tools supply the
numbers, and the user's own agent, guided by prompts, supplies the judgement.

## Other local knowledge

- **Jurisdiction:** the user picks their tax residency explicitly, at onboarding or
  later. Salli no longer infers the country from the currency.
- **Tax IDs:** only generic `{scheme, value}` records. The legacy `ird_number` / `nic`
  fields stay readable and writable for one deprecation window, mapped to the generic
  records, because the web and mobile apps still send them.
- **Planning assumptions:**
  - inflation, expected returns and their scenarios become user data with sources,
    which the user or agent sets;
  - one neutral fallback stays in code, clearly labelled as a placeholder;
  - the FI engine is unchanged.
- **Reminders:** filing reminders come from the active rule set's `deadlines`.

## Migration

This changes stored data and the API, so it ships in phases. Each phase is its own PR,
and nothing runs against a production database without a written plan and sign-off.

1. **Engine v2 beside the old one.** No behaviour change.
   - The schema, the validator and the generic engine.
   - Engine tests against a fictional jurisdiction.
   - The current Sri Lankan pack, expressed as a rule set, must reproduce the existing
     golden results line for line. This proves the engine is general enough.
2. **Storage and interfaces.**
   - New tables: `tax_rule_sets` (owner, jurisdiction, year, status) and
     `tax_rule_set_versions` (content JSONB, hash, sources, validation result).
   - `tax_computations` gains `rule_set_version_id` and `lines` JSONB. The legacy
     columns stay.
   - The new API, MCP and CLI surfaces.
   - Compute prefers the user's active rule set and falls back to the built-in pack,
     now deprecated.
3. **Existing users.** This touches production.
   - A data migration gives each user who has stored computations, or LK residency,
     their own copy of the 2025/26 rules as an active rule set. Their history stays
     reproducible and nothing changes for them.
   - The rules are frozen inside the migration as historical data, the way
     `core_0008` already freezes its roles.
   - Before it runs: a dry run on a copy of production, a backup, and a tested down
     migration.
   - Fresh installs get no rule sets.
4. **Removal.**
   - Delete the built-in packs and registry, the hardwired engine fields,
     `_RETURN_FORMS`, `REGIONAL_DEFAULTS`, `_MARKETS` and the legacy tax-ID constants.
   - Neutralise skills, docs and tests.
   - Update CLAUDE.md.
   - Remove the deprecated endpoints once clients have moved.

The hosted product can keep serving Sri Lankan users exactly as before. After phase 3
their rules are their own data, and the hosted side can help them keep those rules
current if it wants to.

### CLAUDE.md changes

| Invariant | Today | Becomes |
|---|---|---|
| Tax packs | "Tax packs are versioned `(country, year, version)` in `domain/tax/packs/` and need a chartered accountant's review." | "Tax rule sets are user data. They are versioned and immutable once used. Every stored computation records the rule-set version and content hash. A rule set can't be activated until its worked examples pass." |
| Adding a new tax pack | A how-to for developers | Replaced by the rule-set schema docs and the `research_tax_rules` prompt |

## Risks

- **Wrong rules.** A user or agent can enter the law incorrectly. Mitigations:
  - worked examples are required before activation;
  - every figure is cited;
  - every change is diffed;
  - each result states plainly where its rules came from.

  This is honest: today's built-in pack is also unreviewed by an accountant, and it
  ages silently.
- **Agent hallucination.** Validation fails without source URLs and official worked
  examples. Activation is the user's alone.
- **Coverage.** v1 can't express every tax system. Unsupported features fail
  validation with a clear message, rather than computing something wrong.
- **API churn.** The web, mobile and TypeScript clients use `/tax/packs`, the fixed
  computation fields and the legacy tax-ID fields. Those keep working, deprecated,
  until the clients move.

## Questions for sign-off

1. **v1 scope:** personal income tax only, or also capital gains and social
   contributions? Either of those pulls the expression language into v1.
2. **Who activates:** the user only, as proposed, or the agent too, with an
   in-chat confirmation?
3. **Sharing:** should Salli support importing rule sets from a URL, so a community
   catalogue can exist outside the core?
4. **Planning assumptions:** keep one neutral fallback in code, or require the user
   or agent to set them before any FI projection runs?
5. **The phase 3 data migration** for existing (Sri Lankan) users: approve the
   approach, so that a detailed runbook can follow before it runs.
