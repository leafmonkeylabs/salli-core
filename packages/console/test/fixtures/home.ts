/**
 * What a real server answers Home's eight reads (docs/design/console.md,
 * section 5) on the golden household ledger (tests/golden/household.py,
 * as of Oct 11, 2026, in euros), with two reminders of the person's own
 * and a decision recorded in August that is due for review.
 *
 * Written by tests/console_fixtures.py (`uv run python -m tests.console_fixtures`):
 * tests/contract/test_console_fixtures.py fails while it differs from what
 * the server answers. Don't edit it by hand.
 */
import type { BalanceSheet, DueReviews, FiScore, FinanceSignals, IncomeStatement, NetWorthByMonth, ReminderList, SafeToSpend } from '@leafmonkeylabs/salli-sdk';

export const BALANCE_SHEET: BalanceSheet = {
  "currency": "EUR",
  "assets": [
    {
      "account_id": "chk",
      "code": "1000",
      "name": "Checking",
      "balance": "6543.15"
    },
    {
      "account_id": "sav",
      "code": "1100",
      "name": "Savings",
      "balance": "7800.00"
    },
    {
      "account_id": "usd",
      "code": "1200",
      "name": "Dollar account",
      "balance": "2150.00"
    },
    {
      "account_id": "brk",
      "code": "1300",
      "name": "Brokerage",
      "balance": "13000.00"
    },
    {
      "account_id": "pen",
      "code": "1400",
      "name": "Pension fund",
      "balance": "25000.00"
    },
    {
      "account_id": "flat",
      "code": "1500",
      "name": "Flat",
      "balance": "300000.00"
    }
  ],
  "liabilities": [
    {
      "account_id": "card",
      "code": "2000",
      "name": "Credit card",
      "balance": "691.68"
    },
    {
      "account_id": "loan",
      "code": "2100",
      "name": "Car loan",
      "balance": "9900.00"
    },
    {
      "account_id": null,
      "code": "",
      "name": "Student loan",
      "balance": "8000.00"
    }
  ],
  "equity": [
    {
      "account_id": "eq",
      "code": "3000",
      "name": "Opening equity",
      "balance": "334000.00"
    },
    {
      "account_id": null,
      "code": "",
      "name": "Current-year earnings",
      "balance": "10026.47"
    }
  ],
  "total_assets": "354493.15",
  "total_liabilities": "18591.68",
  "total_equity": "344026.47",
  "net_worth": "335901.47",
  "as_of": "2026-10-11",
  "unrealised_fx": {
    "as_of": "2026-10-11",
    "currency": "EUR",
    "total": "-125.00",
    "posted": "0.00",
    "unposted": "-125.00",
    "lines": [
      {
        "account_id": "usd",
        "code": "1200",
        "name": "Dollar account",
        "account_currency": "USD",
        "balance": "2500.00",
        "rate": "0.86",
        "cost": "2275.00",
        "value": "2150.00",
        "gain": "-125.00"
      }
    ],
    "notes": []
  },
  "notes": []
};

/**
 * October 1 to 11, 2026: the month so far on the household's date.
 */
export const INCOME_STATEMENT: IncomeStatement = {
  "from_date": "2026-10-01",
  "to_date": "2026-10-11",
  "currency": "EUR",
  "income": {},
  "expenses": {
    "Rent": "1500.00",
    "Groceries": "188.00",
    "Loan interest": "50.00",
    "Streaming": "12.99"
  },
  "total_income": "0.00",
  "total_expenses": "1750.99",
  "net_income": "-1750.99",
  "lines": [
    {
      "account_id": "rent",
      "code": "5000",
      "name": "Rent",
      "type": "expense",
      "amount": "1500.00",
      "is_active": true
    },
    {
      "account_id": "food",
      "code": "5100",
      "name": "Groceries",
      "type": "expense",
      "amount": "188.00",
      "is_active": true
    },
    {
      "account_id": "int",
      "code": "5300",
      "name": "Loan interest",
      "type": "expense",
      "amount": "50.00",
      "is_active": true
    },
    {
      "account_id": "tv",
      "code": "5400",
      "name": "Streaming",
      "type": "expense",
      "amount": "12.99",
      "is_active": true
    }
  ],
  "unrealised_fx": null,
  "notes": [
    "No USD→EUR rate for 2026-09-30: accounts in USD are left out."
  ]
};

export const FI_SCORE: FiScore = {
  "pack_version": "4.0.0",
  "overall_score": "56.42",
  "grade": "On track",
  "currency": "EUR",
  "monthly_income": "4000.00",
  "monthly_expenses": "2037.09",
  "monthly_surplus": "1962.91",
  "savings_rate": "0.4907",
  "swr": "0.0314",
  "annual_expenses": "24445.08",
  "fi_number": "714042.04",
  "net_worth": "335901.47",
  "fi_asset_base": "24691.01",
  "progress_to_fi": "0.0346",
  "emergency_fund_months": "8.10",
  "debt_to_asset": "0.0524",
  "projected_fi_months": 214,
  "projected_fi_month": "2044-08",
  "as_of": "2026-10-11",
  "status": "ok",
  "months_observed": 6,
  "headline_status": "placeholder",
  "headline": "Rests on placeholders for the real return, the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
  "components": [
    {
      "key": "savings_rate",
      "label": "Savings rate",
      "score": "98.15",
      "weight": "0.29",
      "detail": "Saving 49.07% of income"
    },
    {
      "key": "emergency_fund",
      "label": "Emergency fund",
      "score": "100.00",
      "weight": "0.18",
      "detail": "8.10 months of spending covered, against a target of 6"
    },
    {
      "key": "fi_progress",
      "label": "Progress to FI",
      "score": "3.46",
      "weight": "0.41",
      "detail": "3.46% of your FI number"
    },
    {
      "key": "debt",
      "label": "Debt load",
      "score": "72.13",
      "weight": "0.12",
      "detail": "Debts cost 5.27% a year, averaged by balance; payments take 11.75% of income"
    }
  ],
  "assumptions": {
    "status": "placeholder",
    "placeholders": [
      "real_return",
      "safe_withdrawal_rate",
      "surplus_invested",
      "drawdown_horizon"
    ],
    "headline_status": "placeholder",
    "headline": "Rests on placeholders for the real return, the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
    "message": "Using placeholder assumptions for the real return, the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: round figures, not forecasts. Set your own, with a source, to replace them. Figures are in today's money; set your inflation to see them in future money too.",
    "real_return": {
      "value": "0.04",
      "origin": "placeholder",
      "source": "Placeholder: a round 4% a year after inflation, not a forecast and not any country's figure. Set your own, with its source.",
      "note": null
    },
    "safe_withdrawal_rate": {
      "value": "0.0314",
      "origin": "placeholder",
      "source": "Placeholder: the yearly withdrawal 90% of 1000 simulated return paths sustain over 30 years drawn down, on the placeholder pack's returns. Not a recommendation. Set your own rate, or your own returns, with a source.",
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
    "cash_yield": {
      "value": "0",
      "origin": "placeholder",
      "source": "Placeholder: cash earns nothing after inflation. Activate capital-market assumptions with a cash yield to replace it.",
      "note": null
    },
    "drawdown_horizon": {
      "years": 30,
      "origin": "placeholder",
      "source": "Placeholder: 30 years drawn down, without a date of birth to count to a planning age from. Set your date of birth and planning age to replace it."
    },
    "real_returns": {
      "conservative": "0.02",
      "base": "0.04",
      "growth": "0.06"
    },
    "nominal_returns": null
  },
  "inputs_hash": "3d42f94d640ad033f372b923de0647102717f33e30276d4ff2718081cf2cc740"
};

export const REMINDERS: ReminderList = {
  "reminders": [
    {
      "id": "0000232f-5a11-4000-8000-000000009007",
      "kind": "Review your decision: Change anything?",
      "due_date": "2026-09-30",
      "status": "pending",
      "alert_type": "decision_review",
      "source_domain": "decision",
      "source_id": "0000232e-5a11-4000-8000-000000009006",
      "severity": "info",
      "created_at": "2026-10-01T09:00:00+00:00"
    },
    {
      "id": "0000232c-5a11-4000-8000-000000009004",
      "kind": "Send the landlord the signed lease",
      "due_date": "2026-10-05",
      "status": "pending",
      "alert_type": null,
      "source_domain": null,
      "source_id": null,
      "severity": null,
      "created_at": "2026-10-01T09:00:00+00:00"
    },
    {
      "id": "0000232a-5a11-4000-8000-000000009002",
      "kind": "Renew the car's insurance",
      "due_date": "2026-10-20",
      "status": "pending",
      "alert_type": null,
      "source_domain": null,
      "source_id": null,
      "severity": null,
      "created_at": "2026-10-01T09:00:00+00:00"
    }
  ]
};

export const SAFE_TO_SPEND: SafeToSpend = {
  "currency": "EUR",
  "amount": "15316.35",
  "cash_today": "15801.47",
  "low_point": "15520.06",
  "low_point_date": "2026-10-24",
  "everyday_spending": "206.96",
  "cushion": "203.71",
  "held_for_goals": "0.00",
  "until": "2026-10-25",
  "next_income": {
    "date": "2026-10-25",
    "description": "Acme Salary",
    "amount": "4000.00",
    "currency": "EUR"
  },
  "committed": [
    {
      "date": "2026-10-18",
      "description": "Bistro Novo",
      "amount": "-74.45",
      "currency": "EUR"
    }
  ],
  "fx": [
    {
      "currency": "USD",
      "rate": "0.86",
      "source": "ecb",
      "as_of": "2026-10-09"
    }
  ],
  "notes": []
};

export const SIGNALS: FinanceSignals = {
  "signals": [
    {
      "kind": "decision_review_due",
      "severity": "info",
      "title": "A decision is ready for review",
      "detail": "You decided \"Change anything?\" and asked to look back on 2026-09-30: see how it turned out against what Salli projected.",
      "action": "review_decision",
      "amount": null,
      "currency": null,
      "date": "2026-09-30",
      "refs": [
        "0000232e-5a11-4000-8000-000000009006"
      ],
      "rationale": null
    }
  ]
};

export const REVIEWS_DUE: DueReviews = {
  "as_of": "2026-10-11",
  "reviews": [
    {
      "id": "0000232e-5a11-4000-8000-000000009006",
      "question": "Change anything?",
      "chosen": "Keep as is",
      "currency": "EUR",
      "as_of": "2026-08-11",
      "review_on": "2026-09-30",
      "recorded_at": "2026-08-11T09:00:00+00:00",
      "hash": "sha256:a6351417a3cb545e00b27f8090cdcb1e871c898d79b791b25805045c5db30571",
      "notes": 0,
      "reviews": 0,
      "last_reviewed_at": null,
      "status": "review_due",
      "reasons": "It works.",
      "comparison": {
        "option": "Keep as is",
        "at": "2026-09-30",
        "month": "2026-09",
        "currency": "EUR",
        "terms": "nominal",
        "figures": [
          {
            "figure": "cash",
            "projected": "11316.20",
            "actual": "15702.46",
            "difference": "4386.26"
          },
          {
            "figure": "investments",
            "projected": "42336.02",
            "actual": "38000.00",
            "difference": "-4336.02"
          },
          {
            "figure": "owed",
            "projected": "18111.63",
            "actual": "18200.00",
            "difference": "88.37"
          },
          {
            "figure": "net_worth",
            "projected": "335540.59",
            "actual": "335502.46",
            "difference": "-38.13"
          }
        ],
        "spending": {
          "months": [
            "2026-09"
          ],
          "projected": "2040.14",
          "actual": "2040.69",
          "difference": "0.55"
        },
        "others": [],
        "baseline_fingerprint": "sha256:749a823c940d77bc1df719e0c2790a697bd6eea78ebd78047666352c22cc26a3",
        "data_as_of": "2026-09-26",
        "is_stale": false,
        "notes": [
          "Dollar account: no published USD rate for 2026-09-30, so it is left out of the totals in EUR"
        ]
      }
    }
  ]
};

export const NET_WORTH: NetWorthByMonth = {
  "currency": "EUR",
  "points": [
    {
      "month": "2025-11",
      "assets": "0.00",
      "liabilities": "8000.00",
      "net_worth": "-8000.00",
      "notes": [
        "Dollar account: no published USD rate for 2025-11-30, so it is left out of the totals in EUR"
      ]
    },
    {
      "month": "2025-12",
      "assets": "0.00",
      "liabilities": "8000.00",
      "net_worth": "-8000.00",
      "notes": [
        "Dollar account: no published USD rate for 2025-12-31, so it is left out of the totals in EUR"
      ]
    },
    {
      "month": "2026-01",
      "assets": "0.00",
      "liabilities": "8000.00",
      "net_worth": "-8000.00",
      "notes": [
        "Dollar account: no published USD rate for 2026-01-31, so it is left out of the totals in EUR"
      ]
    },
    {
      "month": "2026-02",
      "assets": "0.00",
      "liabilities": "8000.00",
      "net_worth": "-8000.00",
      "notes": [
        "Dollar account: no published USD rate for 2026-02-28, so it is left out of the totals in EUR"
      ]
    },
    {
      "month": "2026-03",
      "assets": "344200.00",
      "liabilities": "20000.00",
      "net_worth": "324200.00",
      "notes": [
        "Dollar account: no published USD rate for 2026-03-31, so it is left out of the totals in EUR"
      ]
    },
    {
      "month": "2026-04",
      "assets": "346350.00",
      "liabilities": "20170.99",
      "net_worth": "326179.01",
      "notes": [
        "Dollar account: no published USD rate for 2026-04-30, so it is left out of the totals in EUR"
      ]
    },
    {
      "month": "2026-05",
      "assets": "348029.01",
      "liabilities": "19901.89",
      "net_worth": "328127.12",
      "notes": [
        "Dollar account: no published USD rate for 2026-05-31, so it is left out of the totals in EUR"
      ]
    },
    {
      "month": "2026-06",
      "assets": "349677.12",
      "liabilities": "19579.69",
      "net_worth": "330097.43",
      "notes": [
        "Dollar account: no published USD rate for 2026-06-30, so it is left out of the totals in EUR"
      ]
    },
    {
      "month": "2026-07",
      "assets": "350872.43",
      "liabilities": "19307.99",
      "net_worth": "331564.44",
      "notes": [
        "Dollar account: no published USD rate for 2026-07-31, so it is left out of the totals in EUR"
      ]
    },
    {
      "month": "2026-08",
      "assets": "352514.44",
      "liabilities": "18971.29",
      "net_worth": "333543.15",
      "notes": [
        "Dollar account: no published USD rate for 2026-08-31, so it is left out of the totals in EUR"
      ]
    },
    {
      "month": "2026-09",
      "assets": "354193.15",
      "liabilities": "18690.69",
      "net_worth": "335502.46",
      "notes": [
        "Dollar account: no published USD rate for 2026-09-30, so it is left out of the totals in EUR"
      ]
    },
    {
      "month": "2026-10",
      "assets": "354493.15",
      "liabilities": "18591.68",
      "net_worth": "335901.47",
      "notes": []
    }
  ]
};
