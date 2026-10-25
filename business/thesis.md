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

## One company, one wedge

Sri Lankan households prove the product; they are not, alone, the business.
The wedge is **the accountants and planners who serve them**: each pays for
seats and brings in client households, so the consumer side and the paying
side are the same funnel. Agent builders are the second paying segment,
reached through the open core and the MCP directories, and expanded only
once the first works.

| Segment | Why they might pay | Status |
|---|---|---|
| Accountants, bookkeepers and fee-only planners serving individuals and households | Clients' books reconciled and closed on one ledger, read through members' access grants instead of spreadsheets by email; tax-year views from rules they activate | _Hypothesis_; the wedge |
| Salaried professionals and households in Colombo and other cities | Time saved importing and categorising; one net worth across currencies; a budget a couple can run | _Hypothesis_; the proof, mostly arriving through their accountant or planner |
| AI agent builders who need books their agent can quote | A ledger and money engines over MCP with a published fidelity benchmark, instead of a model doing the maths | _Hypothesis_; second segment |

## What is sold: one charge per way of running Salli

A customer pays once for the way they run Salli, never a licence fee on top
of a hosting fee for the same use.

| Way of running it | Who | Charge |
|---|---|---|
| **Self-hosted** | Anyone, including commercial use | Free under AGPL-3.0, provided changes offered over a network are shared |
| **Hosted, one person** | Individuals | Free, capped: one person's books, manual and file imports, no AI features on our keys |
| **Hosted, household and more** | Households, people wanting bank formats or AI features | Paid monthly or yearly |
| **Hosted, for practices** | Accountants and planners | Paid per seat, client books included up to a limit |
| **Hosted, for developers** | Agent builders | Paid by usage (connected ledgers, API and MCP calls), commercial use included; a free sandbox with seed data |
| **Commercial licence** | Organisations embedding or modifying the server without sharing changes | Quoted ([commercial-licence.md](commercial-licence.md)); never charged on top of hosting |

The SDK, CLI, the MCP tool interface and the fidelity benchmark are
Apache-2.0, so builders and model vendors can use and cite them without
taking on the AGPL. Billing for the hosted plans lives in a closed
extension, never in the open core.

## Pricing hypotheses

| Plan | LKR | USD | Notes |
|---|---|---|---|
| Hosted, one person (capped) | free | free | _Hypothesis_; the cap is the test |
| Hosted, household (up to four members, shared access, bank formats) | 1,500 to 2,500 a month | 7 to 12 a month | _Hypothesis_ |
| Hosted, AI features on our keys | added to a paid plan | added to a paid plan | _Hypothesis_; priced on cost |
| Practice seat (accountant or planner) | 5,000 to 10,000 a month | 25 to 50 a month | _Hypothesis_; test with the first three practices |
| Developer hosting | by usage | by usage | _Hypothesis_; a free sandbox first |
| Annual | about two months free | about two months free | _Hypothesis_ |
| Self-hosted | free | free | AGPL-3.0 |
| Commercial licence | quoted | from 5,000 a year | _Hypothesis_; see the offer |

The LKR and USD columns are separate guesses for separate buyers, not a
conversion of each other.

**Hosting must cost less than it earns.** Today's hosted path is one
machine per customer (docs/hosting.md), which costs more than a household
plan brings in. A free capped book and the household prices only work on
shared hosting, so shared hosting comes before charging consumers; the
pilot can run on per-customer machines because it is small and unpaid.

## The design-partner pilot

- **Three accountants or planners**, each bringing in up to ten client
  households; and up to ten households who join directly, all by
  invitation.
- Three months free, then the first paid month at the lower price point,
  which they may decline.
- In return: an onboarding session, a short call every two weeks, and
  consent to the counts in [metrics.md](metrics.md) (never their figures).
- What we learn: whether households import a second month unprompted
  (activation), whether practices close a client's month in Salli, whether
  either pays, and at which price.

## What to prove in 90 days

1. Ten households import a second month without being asked, and five pay
   at the lower household price.
2. Three accountants or planners pay for seats, with 30 or more client
   books between them.
3. Two outside agent builders ship on hosted MCP, and one signs a paid
   developer plan or a commercial licence.
4. The fidelity benchmark published for three or more models, beside a run
   with no Salli.

## What a term sheet needs

_Hypotheses_ for the bar a seed fund would set, from the investor reviews:

- around 300 paying books, 20% or more of trials converting, under 5% of
  paying books leaving a month;
- at least half of new books activated, and 40% of those active weekly;
- 15 paying practices, keeping or growing their spend;
- about USD 150,000 a year in recurring revenue at a gross margin above
  70%, which needs shared hosting;
- a signed legal opinion, a chartered accountant's sign-off on the Sri
  Lankan tax rules, an external pen test, and a co-founder from regulated
  finance.

## The regulatory position to obtain

Before charging anyone, with Sri Lankan counsel (to confirm, not settled):

1. **Not investment advice.** A written opinion that Salli, which computes
   from the person's own data, names no product and ranks no option, is
   not giving investment advice under the Securities and Exchange
   Commission of Sri Lanka Act, No. 19 of 2021, so no investment adviser
   licence is needed. The product's guardrails (no ranking, no products,
   "a licensed professional" for regulated choices) are the evidence; the
   Debts screen's order by interest rate is labelled a fact, not advice.
2. **Personal data.** Registration and compliance as a controller under the
   Personal Data Protection Act, No. 9 of 2022, for the hosted service:
   the privacy notice (docs/privacy.md is the start), the data protection
   officer, cross-border transfer terms for the hosting region and the AI
   providers, and the erasure and export Salli already does. Practices
   reading client books add a processor relationship to set out.
3. **No money moves.** Confirmation that a service which never holds or
   moves funds needs no payment-service authorisation from the Central
   Bank; subscriptions are taken through a licensed processor.
4. **Tax rules are the person's.** Salli carries no country's tax law; the
   rule sets a person activates are theirs. Counsel to confirm the wording
   of that disclaimer for tax-year views.

## Before raising

- **Who owns the code.** Assign the copyright in Salli from the founder to
  Leaf Monkey Labs. Most commits were written with an AI assistant, and
  copyright in AI-assisted code is unsettled; get counsel's view, since a
  commercial licence rests on that copyright.
- **What stays open.** Every release already published stays under its
  licence for good; the plan depends on running and hosting Salli best,
  not on restricting the code.

## What would prove this wrong

Practices that keep their clients in spreadsheets after month one;
households who never import a second month even when it is free; nobody
paying at the lower price; agent builders who try the hosted MCP and leave;
or counsel finding that a licence is needed for what Salli already does.
Each would change the plan before any spending on growth.
