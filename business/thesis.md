# Commercial thesis: a Sri Lanka launch

_One page. Every price, segment and number below is a hypothesis to test
with design partners; none is a result._

## The bet

People who already keep track of their money, and now ask an AI about it,
want the AI's answers to be right. Salli computes every figure on a
double-entry ledger and lets any AI client quote it over MCP, never
calculate it. Sri Lanka is the first market because the team is there,
statements are still largely PDF and CSV (Salli's import path), household
finances often span currencies (remittances, foreign savings), and there
is no established personal-finance tool that keeps the books properly and
works with the person's own AI.

## Who pays

| Segment | Why they might pay | Status |
|---|---|---|
| Salaried professionals in Colombo and other cities, keeping their own books today in spreadsheets | Time saved importing and categorising; a tax-year view from rules they activate | _Hypothesis_ |
| Households with money in two currencies (a family member abroad, foreign savings) | One net worth across currencies at published rates | _Hypothesis_ |
| People in the diaspora with obligations at home | The same, priced in USD | _Hypothesis_ |
| Accountants and bookkeepers serving individuals | Read-only access to a client's books (shared access between members) instead of spreadsheets by email | _Hypothesis_; the closed edition's territory if it grows past what members' access grants cover |

## What is sold

- **The hosted service (paid).** Salli run for you: backups, upgrades,
  HTTPS, the phone app's server, AI features with keys we hold, support.
  Its billing lives in a closed extension, never in the open core.
- **The self-hosted open core (free).** The server and console under
  AGPL-3.0, the CLI and SDK under Apache-2.0. It is the trust story (anyone
  can read how the figures are made) and the developer channel.
- **A commercial licence** for organisations that want to embed or modify
  the AGPL parts without sharing their changes
  ([commercial-licence.md](commercial-licence.md)).

## Pricing hypotheses

| Plan | LKR | USD | Notes |
|---|---|---|---|
| Hosted, one person | 900 to 1,500 a month | 4 to 7 a month | _Hypothesis_; test two price points in the pilot |
| Hosted, a household (up to four members, with shared read access) | 1,500 to 2,500 a month | 7 to 12 a month | _Hypothesis_ |
| Annual | about two months free | about two months free | _Hypothesis_ |
| Self-hosted | free | free | AGPL-3.0 |
| Commercial licence | quoted | from 5,000 a year | _Hypothesis_; see the offer |

The LKR and USD columns are separate guesses for separate buyers, not a
conversion of each other.

## The design-partner pilot

- 20 to 30 households, recruited by invitation; no payment during the pilot.
- Three months on the hosted service, free, then the first paid month at the
  lower price point, which they may decline.
- In return: an onboarding session, a short call every two weeks, and
  consent to the counts in [metrics.md](metrics.md) (never their figures).
- What we learn: whether they import a second month unprompted (activation),
  whether they come back weekly, whether they would pay, and at which of the
  two prices.
- Success, as a _Hypothesis_ to test: at least half activated, a third still
  active weekly in month three, and a quarter willing to pay.

## The regulatory position to obtain

Before charging anyone, with Sri Lankan counsel (to confirm, not settled):

1. **Not investment advice.** A written opinion that Salli, which computes
   from the person's own data, names no product and ranks no option, is
   not giving investment advice under the Securities and Exchange
   Commission of Sri Lanka Act, No. 19 of 2021, so no investment adviser
   licence is needed. The product's guardrails (no ranking, no products,
   "a licensed professional" for regulated choices) are the evidence.
2. **Personal data.** Registration and compliance as a controller under the
   Personal Data Protection Act, No. 9 of 2022, for the hosted service:
   the privacy notice (docs/privacy.md is the start), the data protection
   officer, cross-border transfer terms for the hosting region and the AI
   providers, and the erasure and export Salli already does.
3. **No money moves.** Confirmation that a service which never holds or
   moves funds needs no payment-service authorisation from the Central
   Bank; the subscription itself is taken through a licensed processor.
4. **Tax rules are the person's.** Salli carries no country's tax law; the
   rule sets a person activates are theirs. Counsel to confirm the wording
   of that disclaimer for tax-year views.

## What would prove this wrong

Design partners who keep using spreadsheets after month one; nobody willing
to pay at the lower price; or counsel finding that a licence is needed
for what Salli already does. Each would change the plan before any
spending on growth.
