# Tax rule sets (`salli.tax/1`)

A **tax rule set** is a JSON document that says how one jurisdiction taxes one
year. A user writes it, or their AI agent does (citing official sources), and
Salli's engine applies it. The agent may *write* rules; only the engine
*computes* with them. This is the format and the language, for authors and for
agents. The design behind it is `docs/design/country-neutral-core.md`.

> **Status: phase 1.** The engine, the language, the schema and the validator
> exist (`src/salli/domain/taxrules/`), proven by a conformance suite of
> fictional jurisdictions. Nothing in the app uses them yet: tax is still
> computed by the built-in pack in `salli.domain.tax`. Storage, the API, MCP
> tools and activation come in phase 2.

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
default context, which the built-in engine has always used), installed fresh
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
   non-refundable credit with no cap.
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
