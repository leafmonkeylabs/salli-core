/**
 * The mock server's principles and decision journal (`/v1/principles`,
 * `/v1/decisions`), kept in memory and typed with the SDK's generated types.
 *
 * The fixtures are what the real server answered for the household ledger
 * (tests/golden/household.py), with each option's projection cut to its
 * first four months to keep this file short; its hashes are the real ones
 * from before the cut, which the CLI never recomputes. A principle whose
 * check names "nonsense" is refused as the server refuses an unknown
 * figure.
 *
 * The journal's entries keep the engine version that recorded them. FIGURES
 * and PRINCIPLE_CHECK are what the server answers today, written in place by
 * tests/cli_fixtures.py (`uv run python -m tests.cli_fixtures`), which
 * tests/contract/test_cli_fixtures.py holds them to.
 */
import type {
  Decision,
  DecisionFigures,
  DecisionJournal,
  DecisionNote,
  DecisionReview,
  DecisionSummary,
  DueReviews,
  Principle,
  PrinciplesCheck,
} from '@leafmonkeylabs/salli-sdk';
import { uid } from './fixtures';
import { AFFORD_IT, AFFORD_IT_START, EMERGENCY_FUND, EMERGENCY_FUND_START, RENT_OR_BUY, RENT_OR_BUY_START, TEMPLATE_LIST } from './templates';

type Reply = { status: number; body?: unknown; headers?: Record<string, string>; raw?: string };

export interface DecisionsRequest {
  method: string;
  path: string;
  query: URLSearchParams;
  json?: unknown;
}

export const PRINCIPLES: Principle[] = [
  {
    "schema": "salli.principle/1",
    "id": "00000709-5a11-4000-8000-000000001801",
    "label": "Six months of essentials in cash",
    "check": "emergency_months >= 6",
    "account": null,
    "note": null,
    "version": 1,
    "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a",
    "author": "user",
    "agent": null,
    "status": "active",
    "created_at": "2026-10-11T15:14:15.984772+00:00",
    "updated_at": "2026-10-11T15:14:15.984772+00:00",
    "archived_at": null
  },
  {
    "schema": "salli.principle/1",
    "id": "0000070a-5a11-4000-8000-000000001802",
    "label": "Checking above 5,000",
    "check": "account_lowest >= 5000",
    "account": "chk",
    "note": null,
    "version": 1,
    "hash": "sha256:8cca43c951b264ef898bd2cdfbf10a78c0e4d2121d268685499c218b6434dd79",
    "author": "user",
    "agent": null,
    "status": "active",
    "created_at": "2026-10-11T15:14:15.985733+00:00",
    "updated_at": "2026-10-11T15:14:15.985733+00:00",
    "archived_at": null
  }
];

export const FIGURES: DecisionFigures = {
  "figures": [
    {
      "name": "lowest_cash",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "nominal",
      "group": "cash",
      "description": "The lowest the cash accounts together get, on any day of the as-of month and the twelve after it."
    },
    {
      "name": "cash_in_12_months",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "nominal",
      "group": "cash",
      "description": "The cash accounts together at the end of the twelfth month after the as-of month."
    },
    {
      "name": "safe_to_spend",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "nominal",
      "group": "cash",
      "description": "What could go out on the as-of date without cash dropping below zero before money next comes in."
    },
    {
      "name": "account_lowest",
      "kind": "amount",
      "unit": "the account's own currency",
      "terms": "nominal",
      "group": "cash",
      "description": "The lowest the principle's own account (its `account`, one of your cash accounts) gets over the same thirteen months, in that account's currency."
    },
    {
      "name": "any_account_below_zero",
      "kind": "boolean",
      "unit": "true or false",
      "terms": "none",
      "group": "cash",
      "description": "Whether any cash account goes below zero over the same thirteen months."
    },
    {
      "name": "monthly_spending",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "resilience",
      "description": "The monthly spending the emergency months are counted in: essential spending when your spending carries need tags, all of it otherwise."
    },
    {
      "name": "emergency_months",
      "kind": "months",
      "unit": "months of spending",
      "terms": "none",
      "group": "resilience",
      "description": "The months of that spending your cash and savings cover at its lowest over the same thirteen months."
    },
    {
      "name": "emergency_months_in_12_months",
      "kind": "months",
      "unit": "months of spending",
      "terms": "none",
      "group": "resilience",
      "description": "The months of that spending your cash and savings cover at the end of the twelfth month."
    },
    {
      "name": "net_worth_1y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Net worth (cash and investments and other assets, less debts and other liabilities) at the end of the month 1 year after the as-of month, in today's money."
    },
    {
      "name": "net_worth_5y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Net worth (cash and investments and other assets, less debts and other liabilities) at the end of the month 5 years after the as-of month, in today's money."
    },
    {
      "name": "net_worth_10y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Net worth (cash and investments and other assets, less debts and other liabilities) at the end of the month 10 years after the as-of month, in today's money."
    },
    {
      "name": "net_worth_20y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Net worth (cash and investments and other assets, less debts and other liabilities) at the end of the month 20 years after the as-of month, in today's money."
    },
    {
      "name": "cash_1y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Cash (the cash accounts together, a card's balance against them) at the end of the month 1 year after the as-of month, in today's money."
    },
    {
      "name": "cash_5y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Cash (the cash accounts together, a card's balance against them) at the end of the month 5 years after the as-of month, in today's money."
    },
    {
      "name": "cash_10y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Cash (the cash accounts together, a card's balance against them) at the end of the month 10 years after the as-of month, in today's money."
    },
    {
      "name": "cash_20y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Cash (the cash accounts together, a card's balance against them) at the end of the month 20 years after the as-of month, in today's money."
    },
    {
      "name": "investments_1y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Investments (grown at the real return) at the end of the month 1 year after the as-of month, in today's money."
    },
    {
      "name": "investments_5y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Investments (grown at the real return) at the end of the month 5 years after the as-of month, in today's money."
    },
    {
      "name": "investments_10y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Investments (grown at the real return) at the end of the month 10 years after the as-of month, in today's money."
    },
    {
      "name": "investments_20y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "Investments (grown at the real return) at the end of the month 20 years after the as-of month, in today's money."
    },
    {
      "name": "debts_1y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "What the debts with terms (and the option's loans) still owe at the end of the month 1 year after the as-of month, in today's money."
    },
    {
      "name": "debts_5y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "What the debts with terms (and the option's loans) still owe at the end of the month 5 years after the as-of month, in today's money."
    },
    {
      "name": "debts_10y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "What the debts with terms (and the option's loans) still owe at the end of the month 10 years after the as-of month, in today's money."
    },
    {
      "name": "debts_20y",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "monthly",
      "description": "What the debts with terms (and the option's loans) still owe at the end of the month 20 years after the as-of month, in today's money."
    },
    {
      "name": "total_interest",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "nominal",
      "group": "debts",
      "description": "The interest every debt (and the option's loans) costs over its schedule, each payment in its own money."
    },
    {
      "name": "debt_free_months",
      "kind": "count",
      "unit": "months",
      "terms": "none",
      "group": "debts",
      "description": "Months from the as-of month to the month the last debt is paid off; 0 when nothing is owed."
    },
    {
      "name": "max_debt_rate",
      "kind": "rate",
      "unit": "a yearly fraction (0.07 is 7%)",
      "terms": "none",
      "group": "debts",
      "description": "The highest yearly rate of any debt owed at any month's end in the next 50 years (the option's loans included); 0 when nothing is owed."
    },
    {
      "name": "max_debt_rate_while_investing",
      "kind": "rate",
      "unit": "a yearly fraction (0.07 is 7%)",
      "terms": "none",
      "group": "debts",
      "description": "The highest yearly rate of any debt still owed at the end of a month in which money moves into investments (the share of the surplus you invest, or an invest change); 0 when no debt is owed while you invest."
    },
    {
      "name": "borrowed",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "nominal",
      "group": "debts",
      "description": "What the option borrows: its loans' principal together (0 for the baseline)."
    },
    {
      "name": "fi_number",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "real",
      "group": "fi",
      "description": "A year of the spending you would live on, over your safe withdrawal rate."
    },
    {
      "name": "fi_months",
      "kind": "count",
      "unit": "months",
      "terms": "none",
      "group": "fi",
      "description": "Months from the as-of month to the month you reach the FI number."
    },
    {
      "name": "fi_months_gained",
      "kind": "count",
      "unit": "months",
      "terms": "none",
      "group": "fi",
      "description": "Months sooner (positive) or later (negative) the option reaches FI than the baseline does; 0 for the baseline."
    },
    {
      "name": "tax_change_this_year",
      "kind": "amount",
      "unit": "the base currency",
      "terms": "nominal",
      "group": "tax",
      "description": "The change in the as-of date's tax year's tax (its `net`, after credits) the option makes, computed with your active tax rules from its changes tagged with a tax role; more tax is positive. 0 for the baseline and when nothing in the year is tagged; missing when the tax isn't computed (no active rules, say)."
    }
  ]
};

export const PRINCIPLE_CHECK: PrinciplesCheck = {
  "as_of": "2026-10-11",
  "currency": "EUR",
  "principles": [
    {
      "id": "00000709-5a11-4000-8000-000000001801",
      "label": "Six months of essentials in cash",
      "check": "emergency_months >= 6",
      "account": null,
      "version": 1,
      "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
    },
    {
      "id": "0000070a-5a11-4000-8000-000000001802",
      "label": "Checking above 5,000",
      "check": "account_lowest >= 5000",
      "account": "chk",
      "version": 1,
      "hash": "sha256:8cca43c951b264ef898bd2cdfbf10a78c0e4d2121d268685499c218b6434dd79"
    }
  ],
  "baseline": {
    "figures": {
      "lowest_cash": "13998.91",
      "cash_in_12_months": "15801.47",
      "safe_to_spend": "15316.35",
      "any_account_below_zero": false,
      "monthly_spending": "1898.32",
      "emergency_months": "7.37",
      "emergency_months_in_12_months": "8.32",
      "net_worth_1y": "366266.13",
      "net_worth_5y": "485551.81",
      "net_worth_10y": "664379.50",
      "net_worth_20y": "1149349.20",
      "cash_1y": "15801.47",
      "cash_5y": "15801.47",
      "cash_10y": "15801.47",
      "cash_20y": "15801.47",
      "investments_1y": "63546.81",
      "investments_5y": "171707.25",
      "investments_10y": "348578.03",
      "investments_20y": "833547.73",
      "debts_1y": "13082.15",
      "debts_5y": "1956.91",
      "debts_10y": "0.00",
      "debts_20y": "0.00",
      "total_interest": "2009.25",
      "debt_free_months": 77,
      "max_debt_rate": "0.059",
      "max_debt_rate_while_investing": "0.059",
      "borrowed": "0.00",
      "fi_number": "714042.04",
      "fi_months": 214,
      "fi_months_gained": 0,
      "tax_change_this_year": "0.00"
    },
    "unavailable": {},
    "results": [
      {
        "principle_id": "00000709-5a11-4000-8000-000000001801",
        "label": "Six months of essentials in cash",
        "status": "keeps",
        "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
        "figures": {
          "emergency_months": "7.37"
        }
      },
      {
        "principle_id": "0000070a-5a11-4000-8000-000000001802",
        "label": "Checking above 5,000",
        "status": "keeps",
        "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
        "figures": {
          "account_lowest": "6063.46"
        }
      }
    ]
  },
  "options": [
    {
      "figures": {
        "lowest_cash": "11598.91",
        "cash_in_12_months": "13401.47",
        "safe_to_spend": "15316.35",
        "any_account_below_zero": false,
        "monthly_spending": "1898.32",
        "emergency_months": "6.11",
        "emergency_months_in_12_months": "7.06",
        "net_worth_1y": "363866.13",
        "net_worth_5y": "483151.81",
        "net_worth_10y": "661979.50",
        "net_worth_20y": "1146949.20",
        "cash_1y": "13401.47",
        "cash_5y": "13401.47",
        "cash_10y": "13401.47",
        "cash_20y": "13401.47",
        "investments_1y": "63546.81",
        "investments_5y": "171707.25",
        "investments_10y": "348578.03",
        "investments_20y": "833547.73",
        "debts_1y": "13082.15",
        "debts_5y": "1956.91",
        "debts_10y": "0.00",
        "debts_20y": "0.00",
        "total_interest": "2009.25",
        "debt_free_months": 77,
        "max_debt_rate": "0.059",
        "max_debt_rate_while_investing": "0.059",
        "borrowed": "0.00",
        "fi_number": "714042.04",
        "fi_months": 215,
        "fi_months_gained": -1,
        "tax_change_this_year": "0.00"
      },
      "unavailable": {},
      "results": [
        {
          "principle_id": "00000709-5a11-4000-8000-000000001801",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 6.11.",
          "figures": {
            "emergency_months": "6.11"
          }
        },
        {
          "principle_id": "0000070a-5a11-4000-8000-000000001802",
          "label": "Checking above 5,000",
          "status": "breaks",
          "reason": "account_lowest >= 5000 doesn't hold: account_lowest is 4883.77.",
          "figures": {
            "account_lowest": "4883.77"
          }
        }
      ],
      "label": "Pay cash",
      "scenario_hash": "sha256:408fa3f4fce9cdb8a30b6f6f42614c4386db98b1e12a812baf31440423871a10"
    },
    {
      "figures": {
        "lowest_cash": "13821.01",
        "cash_in_12_months": "15801.47",
        "safe_to_spend": "15316.35",
        "any_account_below_zero": false,
        "monthly_spending": "1898.32",
        "emergency_months": "7.28",
        "emergency_months_in_12_months": "8.32",
        "net_worth_1y": "363738.21",
        "net_worth_5y": "482585.47",
        "net_worth_10y": "660757.60",
        "net_worth_20y": "1143949.56",
        "cash_1y": "15801.47",
        "cash_5y": "15801.47",
        "cash_10y": "15801.47",
        "cash_20y": "15801.47",
        "investments_1y": "61225.33",
        "investments_5y": "168740.91",
        "investments_10y": "344956.13",
        "investments_20y": "828148.09",
        "debts_1y": "13288.59",
        "debts_5y": "1956.91",
        "debts_10y": "0.00",
        "debts_20y": "0.00",
        "total_interest": "2099.93",
        "debt_free_months": 77,
        "max_debt_rate": "0.069",
        "max_debt_rate_while_investing": "0.069",
        "borrowed": "2400.00",
        "fi_number": "714042.04",
        "fi_months": 215,
        "fi_months_gained": -1,
        "tax_change_this_year": "0.00"
      },
      "unavailable": {},
      "results": [
        {
          "principle_id": "00000709-5a11-4000-8000-000000001801",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 7.28.",
          "figures": {
            "emergency_months": "7.28"
          }
        },
        {
          "principle_id": "0000070a-5a11-4000-8000-000000001802",
          "label": "Checking above 5,000",
          "status": "keeps",
          "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
          "figures": {
            "account_lowest": "6063.46"
          }
        }
      ],
      "label": "Instalments",
      "scenario_hash": "sha256:eb453270fd80d4b311555618ab998bc9a1ab86a9bb8d1dc4a19bab13a7bc38a4"
    }
  ],
  "placeholders": [
    "real_return",
    "safe_withdrawal_rate",
    "surplus_invested",
    "drawdown_horizon",
    "inflation"
  ],
  "data_as_of": "2026-10-09"
};

export const DECISION: Decision = {
  "id": "00000713-5a11-4000-8000-000000001811",
  "hash": "sha256:0ab93fae3bec040653792110a8d322537fc3ba8bf5507983352d4fc4d958c445",
  "verified": true,
  "status": "review_due",
  "entry": {
    "schema": "salli.decision/1",
    "id": "00000713-5a11-4000-8000-000000001811",
    "recorded_at": "2026-10-11T09:00:00+00:00",
    "recorded_via": {
      "channel": "api"
    },
    "question": "Laptop: pay cash or spread it?",
    "as_of": "2026-10-11",
    "currency": "EUR",
    "basis": {
      "baseline_fingerprint": "sha256:fe55137cc10e6e8ba8755f3dd88b73cc841a15c22299f66902518cb3de71d4ab",
      "versions": {
        "schema": "salli.scenario/1",
        "engine": "2",
        "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
        "fire_strategy": null,
        "rule_sets": []
      },
      "assumptions": {
        "status": "placeholder",
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested"
        ],
        "message": "Using placeholder assumptions for the real return, the safe withdrawal rate and the share of your monthly surplus invested: round figures, not forecasts. Set your own, with a source, to replace them. Figures are in today's money; set your inflation to see them in future money too.",
        "real_return": {
          "value": "0.04",
          "origin": "placeholder",
          "source": "Placeholder: a round 4% a year after inflation, not a forecast and not any country's figure. Set your own, with its source.",
          "note": null
        },
        "safe_withdrawal_rate": {
          "value": "0.04",
          "origin": "placeholder",
          "source": "Placeholder: a round 4%, the rule of thumb most writing on financial independence starts from. Not a recommendation: the rate that lasts differs between markets and periods. Set your own, with its source.",
          "note": null
        },
        "surplus_invested": {
          "value": "1",
          "origin": "placeholder",
          "source": "Placeholder: all of your monthly surplus is assumed invested at the real return; set what you actually invest.",
          "note": null
        },
        "inflation": null,
        "nominal_return": null,
        "real_returns": {
          "conservative": "0.02",
          "base": "0.04",
          "growth": "0.06"
        },
        "nominal_returns": null
      },
      "placeholders": [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "inflation"
      ],
      "data_as_of": "2026-10-09",
      "is_stale": false
    },
    "principles": [
      {
        "id": "00000709-5a11-4000-8000-000000001801",
        "label": "Six months of essentials in cash",
        "check": "emergency_months >= 6",
        "account": null,
        "version": 1,
        "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
      },
      {
        "id": "0000070a-5a11-4000-8000-000000001802",
        "label": "Checking above 5,000",
        "check": "account_lowest >= 5000",
        "account": "chk",
        "version": 1,
        "hash": "sha256:8cca43c951b264ef898bd2cdfbf10a78c0e4d2121d268685499c218b6434dd79"
      }
    ],
    "baseline": {
      "figures": {
        "lowest_cash": "13998.91",
        "cash_in_12_months": "15801.47",
        "safe_to_spend": "15727.02",
        "any_account_below_zero": false,
        "monthly_spending": "1898.32",
        "emergency_months": "7.37",
        "emergency_months_in_12_months": "8.32",
        "net_worth_1y": "366266.13",
        "net_worth_5y": "485551.81",
        "net_worth_10y": "664379.50",
        "net_worth_20y": "1149349.20",
        "cash_1y": "15801.47",
        "cash_5y": "15801.47",
        "cash_10y": "15801.47",
        "cash_20y": "15801.47",
        "investments_1y": "63546.81",
        "investments_5y": "171707.25",
        "investments_10y": "348578.03",
        "investments_20y": "833547.73",
        "debts_1y": "13082.15",
        "debts_5y": "1956.91",
        "debts_10y": "0.00",
        "debts_20y": "0.00",
        "total_interest": "2009.25",
        "debt_free_months": 77,
        "max_debt_rate": "0.059",
        "max_debt_rate_while_investing": "0.059",
        "borrowed": "0.00",
        "fi_number": "611127.00",
        "fi_months": 187,
        "fi_months_gained": 0
      },
      "unavailable": {},
      "principles": [
        {
          "principle_id": "00000709-5a11-4000-8000-000000001801",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
          "figures": {
            "emergency_months": "7.37"
          }
        },
        {
          "principle_id": "0000070a-5a11-4000-8000-000000001802",
          "label": "Checking above 5,000",
          "status": "keeps",
          "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
          "figures": {
            "account_lowest": "6063.46"
          }
        }
      ]
    },
    "options": [
      {
        "label": "Pay cash",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Pay cash",
          "as_of": "2026-10-11",
          "horizon_years": 20,
          "changes": [
            {
              "type": "one_off",
              "date": "2026-11-02",
              "amount": "-2400.00",
              "account": "chk",
              "label": "Laptop"
            }
          ]
        },
        "scenario_hash": "sha256:6eba5c2a1c0decdd49e00f7eede1a1558e2e4b33df51e650105c79662c1d30a9",
        "figures": {
          "lowest_cash": "11598.91",
          "cash_in_12_months": "13401.47",
          "safe_to_spend": "15727.02",
          "any_account_below_zero": false,
          "monthly_spending": "1898.32",
          "emergency_months": "6.11",
          "emergency_months_in_12_months": "7.06",
          "net_worth_1y": "363866.13",
          "net_worth_5y": "483151.81",
          "net_worth_10y": "661979.50",
          "net_worth_20y": "1146949.20",
          "cash_1y": "13401.47",
          "cash_5y": "13401.47",
          "cash_10y": "13401.47",
          "cash_20y": "13401.47",
          "investments_1y": "63546.81",
          "investments_5y": "171707.25",
          "investments_10y": "348578.03",
          "investments_20y": "833547.73",
          "debts_1y": "13082.15",
          "debts_5y": "1956.91",
          "debts_10y": "0.00",
          "debts_20y": "0.00",
          "total_interest": "2009.25",
          "debt_free_months": 77,
          "max_debt_rate": "0.059",
          "max_debt_rate_while_investing": "0.059",
          "borrowed": "0.00",
          "fi_number": "611127.00",
          "fi_months": 188,
          "fi_months_gained": -1
        },
        "unavailable": {},
        "principles": [
          {
            "principle_id": "00000709-5a11-4000-8000-000000001801",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 6.11.",
            "figures": {
              "emergency_months": "6.11"
            }
          },
          {
            "principle_id": "0000070a-5a11-4000-8000-000000001802",
            "label": "Checking above 5,000",
            "status": "breaks",
            "reason": "account_lowest >= 5000 doesn't hold: account_lowest is 4883.77.",
            "figures": {
              "account_lowest": "4883.77"
            }
          }
        ],
        "projection": [
          {
            "month": "2026-10",
            "date": "2026-10-11",
            "cash": "15801.47",
            "investments": "38000.00",
            "owed": "17900.00",
            "net_worth": "335901.47",
            "spending": null
          },
          {
            "month": "2026-10",
            "date": "2026-10-31",
            "cash": "15801.47",
            "investments": "41545.47",
            "owed": "17900.00",
            "net_worth": "339446.94",
            "spending": null
          },
          {
            "month": "2026-11",
            "date": "2026-11-30",
            "cash": "13401.47",
            "investments": "43345.54",
            "owed": "17508.68",
            "net_worth": "339238.33",
            "spending": "2037.09"
          },
          {
            "month": "2026-12",
            "date": "2026-12-31",
            "cash": "13401.47",
            "investments": "45151.62",
            "owed": "17115.53",
            "net_worth": "341437.56",
            "spending": "2037.09"
          }
        ],
        "notes": []
      },
      {
        "label": "Instalments",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Instalments",
          "as_of": "2026-10-11",
          "horizon_years": 20,
          "changes": [
            {
              "type": "one_off",
              "date": "2026-11-02",
              "amount": "-2400.00",
              "account": "chk",
              "label": "Laptop"
            },
            {
              "type": "loan",
              "principal": "2400.00",
              "annual_rate": "0.069",
              "term_months": 12,
              "start": "2026-11-02",
              "into": "chk",
              "label": "Instalments"
            }
          ]
        },
        "scenario_hash": "sha256:db11507c805e733ac1b8f18195d7529d71acf66596cd5b01194ee508c2b7384c",
        "figures": {
          "lowest_cash": "13821.01",
          "cash_in_12_months": "15801.47",
          "safe_to_spend": "15727.02",
          "any_account_below_zero": false,
          "monthly_spending": "1898.32",
          "emergency_months": "7.28",
          "emergency_months_in_12_months": "8.32",
          "net_worth_1y": "363738.21",
          "net_worth_5y": "482585.47",
          "net_worth_10y": "660757.60",
          "net_worth_20y": "1143949.56",
          "cash_1y": "15801.47",
          "cash_5y": "15801.47",
          "cash_10y": "15801.47",
          "cash_20y": "15801.47",
          "investments_1y": "61225.33",
          "investments_5y": "168740.91",
          "investments_10y": "344956.13",
          "investments_20y": "828148.09",
          "debts_1y": "13288.59",
          "debts_5y": "1956.91",
          "debts_10y": "0.00",
          "debts_20y": "0.00",
          "total_interest": "2099.93",
          "debt_free_months": 77,
          "max_debt_rate": "0.069",
          "max_debt_rate_while_investing": "0.069",
          "borrowed": "2400.00",
          "fi_number": "611127.00",
          "fi_months": 189,
          "fi_months_gained": -2
        },
        "unavailable": {},
        "principles": [
          {
            "principle_id": "00000709-5a11-4000-8000-000000001801",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.28.",
            "figures": {
              "emergency_months": "7.28"
            }
          },
          {
            "principle_id": "0000070a-5a11-4000-8000-000000001802",
            "label": "Checking above 5,000",
            "status": "keeps",
            "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
            "figures": {
              "account_lowest": "6063.46"
            }
          }
        ],
        "projection": [
          {
            "month": "2026-10",
            "date": "2026-10-11",
            "cash": "15801.47",
            "investments": "38000.00",
            "owed": "17900.00",
            "net_worth": "335901.47",
            "spending": null
          },
          {
            "month": "2026-10",
            "date": "2026-10-31",
            "cash": "15801.47",
            "investments": "41545.47",
            "owed": "17900.00",
            "net_worth": "339446.94",
            "spending": null
          },
          {
            "month": "2026-11",
            "date": "2026-11-30",
            "cash": "15801.47",
            "investments": "43345.54",
            "owed": "19908.68",
            "net_worth": "339238.33",
            "spending": "2037.09"
          },
          {
            "month": "2026-12",
            "date": "2026-12-31",
            "cash": "15801.47",
            "investments": "44944.07",
            "owed": "19321.78",
            "net_worth": "341423.76",
            "spending": "2037.09"
          }
        ],
        "notes": []
      }
    ],
    "chosen": "Pay cash",
    "reasons": "I'd rather not owe anything.",
    "agent_summary": {
      "text": "Paying cash costs no interest but takes the low point to 11,598.91.",
      "author": "agent",
      "agent": "Claude"
    },
    "review_on": "2027-04-11"
  },
  "notes": [],
  "reviews": []
};

export const DUE: DueReviews = {
  "as_of": "2027-04-12",
  "reviews": [
    {
      "id": "00000713-5a11-4000-8000-000000001811",
      "question": "Laptop: pay cash or spread it?",
      "chosen": "Pay cash",
      "currency": "EUR",
      "as_of": "2026-10-11",
      "review_on": "2027-04-11",
      "recorded_at": "2026-10-11T09:00:00+00:00",
      "hash": "sha256:0ab93fae3bec040653792110a8d322537fc3ba8bf5507983352d4fc4d958c445",
      "notes": 0,
      "reviews": 0,
      "last_reviewed_at": null,
      "status": "review_due",
      "reasons": "I'd rather not owe anything.",
      "comparison": {
        "option": "Pay cash",
        "at": "2027-03-31",
        "month": "2027-03",
        "currency": "EUR",
        "terms": "nominal",
        "figures": [
          {
            "figure": "cash",
            "projected": "13401.47",
            "actual": "14343.15",
            "difference": "941.68"
          },
          {
            "figure": "investments",
            "projected": "50606.04",
            "actual": "38000.00",
            "difference": "-12606.04"
          },
          {
            "figure": "owed",
            "projected": "15925.09",
            "actual": "18591.68",
            "difference": "2666.59"
          },
          {
            "figure": "net_worth",
            "projected": "348082.42",
            "actual": "333751.47",
            "difference": "-14330.95"
          }
        ],
        "spending": {
          "months": [
            "2026-11",
            "2026-12",
            "2027-01",
            "2027-02",
            "2027-03"
          ],
          "projected": "2037.09",
          "actual": "0.00",
          "difference": "-2037.09"
        },
        "others": [
          {
            "option": "Instalments",
            "cash": "15801.47",
            "investments": "49771.68",
            "owed": "17543.39",
            "net_worth": "348029.76"
          }
        ],
        "baseline_fingerprint": "sha256:592b22f187cf38ca23d84f7ceb2f2bb9ba7361167ac77ea4f3ad507efb65eca5",
        "data_as_of": "2026-10-09",
        "is_stale": true,
        "notes": [
          "Your ledger's newest entry is from 2026-10-09: what happened is only what it shows, so bring it up to date before reading these differences.",
          "Dollar account: no published USD rate for 2027-03-31, so it is left out of the totals in EUR"
        ]
      }
    }
  ]
};

export const REVIEW: DecisionReview = {
  "review": {
    "schema": "salli.decision-review/1",
    "id": "0000071d-5a11-4000-8000-000000001821",
    "decision_id": "00000713-5a11-4000-8000-000000001811",
    "entry_hash": "sha256:0ab93fae3bec040653792110a8d322537fc3ba8bf5507983352d4fc4d958c445",
    "at": "2026-10-11T09:00:00+00:00",
    "as_of": "2027-04-12",
    "reflection": "Glad I paid cash.",
    "author": "user",
    "agent": null,
    "comparison": {
      "option": "Pay cash",
      "at": "2027-03-31",
      "month": "2027-03",
      "currency": "EUR",
      "terms": "nominal",
      "figures": [
        {
          "figure": "cash",
          "projected": "13401.47",
          "actual": "14343.15",
          "difference": "941.68"
        },
        {
          "figure": "investments",
          "projected": "50606.04",
          "actual": "38000.00",
          "difference": "-12606.04"
        },
        {
          "figure": "owed",
          "projected": "15925.09",
          "actual": "18591.68",
          "difference": "2666.59"
        },
        {
          "figure": "net_worth",
          "projected": "348082.42",
          "actual": "333751.47",
          "difference": "-14330.95"
        }
      ],
      "spending": {
        "months": [
          "2026-11",
          "2026-12",
          "2027-01",
          "2027-02",
          "2027-03"
        ],
        "projected": "2037.09",
        "actual": "0.00",
        "difference": "-2037.09"
      },
      "others": [
        {
          "option": "Instalments",
          "cash": "15801.47",
          "investments": "49771.68",
          "owed": "17543.39",
          "net_worth": "348029.76"
        }
      ],
      "baseline_fingerprint": "sha256:592b22f187cf38ca23d84f7ceb2f2bb9ba7361167ac77ea4f3ad507efb65eca5",
      "data_as_of": "2026-10-09",
      "is_stale": true,
      "notes": [
        "Your ledger's newest entry is from 2026-10-09: what happened is only what it shows, so bring it up to date before reading these differences.",
        "Dollar account: no published USD rate for 2027-03-31, so it is left out of the totals in EUR"
      ]
    }
  },
  "hash": "sha256:64be5bc59af3a133ba9e2b8bfd7e4eb55f1e3fa85f713075a0ad9158046d0550",
  "verified": true
};

const AT = '2026-10-11T09:00:00+00:00';

function problem(status: number, title: string, detail: unknown, type: string): Reply {
  return {
    status,
    body: { type, title, status, detail },
    headers: { 'Content-Type': 'application/problem+json', 'X-Request-Id': 'req-test-1' },
  };
}

function segments(path: string, prefix: string): string[] | undefined {
  if (path !== prefix && !path.startsWith(`${prefix}/`)) return undefined;
  return path.slice(prefix.length).split('/').filter(Boolean).map(decodeURIComponent);
}

export class DecisionsMock {
  readonly principles: Principle[] = structuredClone(PRINCIPLES);
  readonly decisions: Decision[] = [structuredClone(DECISION)];
  /** Request bodies, in order. */
  readonly bodies: Array<{ method: string; path: string; body: unknown }> = [];
  private seq = 0;

  summary(d: Decision): DecisionSummary {
    const e = d.entry;
    return {
      id: d.id,
      question: e.question,
      chosen: e.chosen,
      currency: e.currency,
      as_of: e.as_of,
      review_on: e.review_on,
      recorded_at: e.recorded_at,
      hash: d.hash,
      notes: d.notes.length,
      reviews: d.reviews.length,
      last_reviewed_at: d.reviews.at(-1)?.review.at ?? null,
      status: d.status,
    };
  }

  markdown(ds: Decision[]): string {
    return ['# Decision journal', '', ...ds.flatMap((d) => [`## ${d.entry.question}`, '', `Entry hash \`${d.hash}\``, ''])].join('\n');
  }

  route(req: DecisionsRequest): Reply | undefined {
    const { method, path } = req;
    const principles = segments(path, '/v1/principles');
    if (principles) return this.routePrinciples(req, principles);
    const decisions = segments(path, '/v1/decisions');
    if (decisions) return this.routeDecisions(req, decisions);
    void method;
    return undefined;
  }

  private routePrinciples(req: DecisionsRequest, parts: string[]): Reply | undefined {
    const { method, path } = req;
    const body = (req.json ?? {}) as Record<string, unknown>;
    if (method !== 'GET') this.bodies.push({ method, path, body: req.json });
    if (parts.length === 0 && method === 'GET') {
      const all = req.query.get('include_archived') === 'true';
      return { status: 200, body: { principles: this.principles.filter((p) => all || p.status === 'active') } };
    }
    if (parts.length === 0 && method === 'POST') {
      const check = String(body.check ?? '');
      if (check.includes('nonsense')) {
        return problem(
          422,
          'Not a principle Salli can keep',
          [{ loc: ['body', 'check'], msg: "There is no figure 'nonsense'. The figures are listed by GET /v1/principles/figures (`salli principles figures`).", snippet: `${check}\n^` }],
          '/problems/invalid-principle',
        );
      }
      const added: Principle = {
        ...structuredClone(PRINCIPLES[0]!),
        id: uid(1900 + this.seq++),
        label: String(body.label),
        check,
        account: (body.account as string | null | undefined) ?? null,
        note: (body.note as string | null | undefined) ?? null,
      };
      this.principles.push(added);
      return { status: 201, body: added };
    }
    if (parts[0] === 'figures' && method === 'GET') return { status: 200, body: FIGURES };
    if (parts[0] === 'check' && method === 'POST') return { status: 200, body: PRINCIPLE_CHECK };
    const found = this.principles.find((p) => p.id === parts[0]);
    if (!found) return problem(404, 'Not found', `Principle not found: ${parts[0]}`, '/problems/not-found');
    if (parts.length === 1 && method === 'PATCH') {
      Object.assign(found, body, { version: found.version + 1 });
      return { status: 200, body: found };
    }
    if (parts[1] === 'archive' && method === 'POST') {
      found.status = 'archived';
      found.archived_at = AT;
      return { status: 200, body: found };
    }
    return undefined;
  }

  private routeDecisions(req: DecisionsRequest, parts: string[]): Reply | undefined {
    const { method, path } = req;
    if (method !== 'GET') this.bodies.push({ method, path, body: req.json });
    if (parts.length === 0 && method === 'GET') {
      return { status: 200, body: { decisions: [...this.decisions].reverse().map((d) => this.summary(d)) } };
    }
    if (parts.length === 0 && method === 'POST') {
      const body = req.json as { chosen?: string; question?: string };
      const recorded: Decision = structuredClone(DECISION);
      recorded.id = uid(1950 + this.seq++);
      recorded.status = 'awaiting_review';
      recorded.entry.id = recorded.id;
      recorded.entry.question = body.question ?? recorded.entry.question;
      this.decisions.push(recorded);
      return { status: 201, body: recorded };
    }
    if (parts[0] === 'templates' && method === 'GET') {
      if (parts.length === 1) return { status: 200, body: TEMPLATE_LIST };
      const template = { 'afford-it': AFFORD_IT, 'emergency-fund': EMERGENCY_FUND, 'rent-or-buy': RENT_OR_BUY }[parts[1] ?? ''];
      if (template) return { status: 200, body: template };
      return problem(404, 'Not found', `No decision template '${parts[1]}'; there are: ${TEMPLATE_LIST.templates.map((t) => t.id).join(', ')}`, '/problems/not-found');
    }
    if (parts[0] === 'start' && parts.length === 1 && method === 'POST') {
      const body = req.json as { template?: string; answers?: Record<string, unknown> };
      if (body.answers?.price === '0') {
        return problem(422, 'Not answers Salli can build options from', [{ loc: ['body', 'answers', 'price'], msg: 'must be greater than zero' }], '/problems/invalid-answers');
      }
      const started = { 'emergency-fund': EMERGENCY_FUND_START, 'rent-or-buy': RENT_OR_BUY_START }[body.template ?? ''];
      return { status: 200, body: started ?? AFFORD_IT_START };
    }
    if (parts[0] === 'reviews' && parts.length === 1 && method === 'GET') {
      const due = this.decisions.filter((d) => d.status === 'review_due');
      return {
        status: 200,
        body: {
          as_of: DUE.as_of,
          reviews: due.map((d) => ({ ...this.summary(d), reasons: d.entry.reasons, comparison: DUE.reviews[0]!.comparison })),
        } satisfies DueReviews,
      };
    }
    if (parts[0] === 'export' && parts.length === 1 && method === 'GET') {
      const journal: DecisionJournal = {
        schema: 'salli.decision-journal/1',
        exported_at: AT,
        verify: 'Each hash is the SHA-256 of the document’s canonical JSON.',
        entries: this.decisions.map((d) => ({ entry: d.entry, hash: d.hash, notes: d.notes, reviews: d.reviews })),
      };
      return { status: 200, body: journal };
    }
    if (parts[0] === 'export' && parts[1] === 'markdown' && method === 'GET') {
      return { status: 200, raw: this.markdown(this.decisions), headers: { 'Content-Type': 'text/markdown; charset=utf-8' } };
    }
    const found = this.decisions.find((d) => d.id === parts[0]);
    if (!found) return problem(404, 'Not found', `Decision not found: ${parts[0]}`, '/problems/not-found');
    if (parts.length === 1 && method === 'GET') return { status: 200, body: found };
    if (parts[1] === 'markdown' && method === 'GET') {
      return { status: 200, raw: this.markdown([found]), headers: { 'Content-Type': 'text/markdown; charset=utf-8' } };
    }
    if (parts[1] === 'notes' && method === 'POST') {
      const text = String((req.json as { text?: string }).text ?? '');
      const note: DecisionNote = {
        note: {
          schema: 'salli.decision-note/1',
          id: uid(1990 + this.seq++),
          decision_id: found.id,
          entry_hash: found.hash,
          at: AT,
          text,
          author: 'user',
          agent: null,
        },
        hash: `sha256:${'d'.repeat(64)}`,
        verified: true,
      };
      found.notes.push(note);
      return { status: 201, body: note };
    }
    if (parts[1] === 'review' && method === 'POST') {
      if (found.status !== 'review_due') {
        return problem(
          422,
          'Not something Salli can record in the decision journal',
          [{ loc: ['body', 'as_of'], msg: `is before the review date (${found.entry.review_on}): the decision can be reviewed from then on` }],
          '/problems/invalid-decision',
        );
      }
      const reflection = String((req.json as { reflection?: string }).reflection ?? '');
      const review: DecisionReview = structuredClone(REVIEW);
      review.review.reflection = reflection;
      found.reviews.push(review);
      found.status = 'reviewed';
      return { status: 201, body: review };
    }
    return undefined;
  }
}
