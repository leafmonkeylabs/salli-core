# Market packs

Salli's core knows no country's tax or markets
([docs/design/country-neutral-core.md](../docs/design/country-neutral-core.md)).
A **market pack** is that knowledge for one country, kept as data a user loads
into their own Salli, outside the core:

| File | What it holds | Format |
|---|---|---|
| `tax/<year>.json` | One tax rule set per year of assessment | `salli.tax/1` ([docs/taxrules.md](../docs/taxrules.md)) |
| `cma.json` | Capital-market assumptions for planning: inflation, cash yield, and per asset class a real return, volatility and correlations | `salli.cma/1` |
| `pensions.json` | The country's mandatory pension or provident schemes: contribution rates, payout, tax treatment, how to post them | `salli.pensions/1` |
| `banks/<bank>.json` | Each bank's statement layout, with a synthetic sample statement in `banks/samples/` that the tests read | `salli.bankformat/1` ([docs/books.md](../docs/books.md#imports)) |
| `README.md` | What is in the pack, how to load it, the sources, what is uncertain, and its review status | |

A pack is a starting point. Once loaded, the rules are the user's: they read,
change and activate them like any rule set they wrote.

## The bar to add one

- **Primary sources only** for every figure: the revenue authority's notices,
  tables and guides, the Acts, the central bank, the pension funds. Each file
  names its sources with URL and the date retrieved.
- **Uncertainty is written down, never guessed.** A figure not confirmed from
  a primary source is marked (`uncertain`, or an assumption source) and listed
  in the pack's README.
- **The authority's worked examples are the tests.** Every rule set validates
  with no errors or warnings and every example passes
  (`tests/taxrules/test_market_packs.py` runs every pack's).
- **Nothing outside `markets/`.** No country's terms in `src`, `packages`,
  `openapi`, `benchmark` or `docs` (`tests/contract/test_no_country_knowledge.py`).
- **A review status.** The pack's README says who has reviewed it (a qualified
  local accountant or adviser), or that nobody has yet and what a reviewer
  should check.
