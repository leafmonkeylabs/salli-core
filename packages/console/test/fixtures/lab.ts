/**
 * What a real server answers the decision lab's reads and writes
 * (docs/design/console.md, section 5) on the golden household ledger
 * (tests/golden/household.py, as of Oct 11, 2026, in euros), after what
 * Home's fixtures (home.ts) rest on: three principles (one archived), a
 * laptop weighed with the afford-it template and recorded on Oct 11 with a
 * note, beside the August decision that is due for review. The writes at
 * the end (a principle added and edited, the August decision reviewed)
 * come after every read, so the reads are what the console sees first.
 *
 * Written by tests/console_fixtures.py (`uv run python -m tests.console_fixtures`):
 * tests/contract/test_console_fixtures.py fails while it differs from what
 * the server answers. Don't edit it by hand.
 */
import type { Account, Baseline, DebtList, Decision, DecisionFigures, DecisionJournal, DecisionList, DecisionNote, DecisionReview, DecisionStart, DecisionTemplate, DecisionTemplateList, HoldingList, Principle, PrincipleList, PrinciplesCheck, ProblemDetails, RecurringPayments, ScenarioComparison, ScenarioRun } from '@leafmonkeylabs/salli-sdk';

export const BASELINE: Baseline = {
  "as_of": "2026-10-11",
  "currency": "EUR",
  "months_observed": [
    "2026-04",
    "2026-05",
    "2026-06",
    "2026-07",
    "2026-08",
    "2026-09"
  ],
  "flows": {
    "monthly_income": "4000.00",
    "monthly_expenses": "2037.09",
    "monthly_surplus": "1962.91",
    "savings_rate": "0.4907",
    "essential_monthly": "1898.32",
    "need_coverage": "0.9755",
    "by_month": [
      {
        "month": "2026-04",
        "income": "4000.00",
        "expenses": "2020.99",
        "net": "1979.01",
        "essential": "1894.00"
      },
      {
        "month": "2026-05",
        "income": "4000.00",
        "expenses": "2051.89",
        "net": "1948.11",
        "essential": "1900.40"
      },
      {
        "month": "2026-06",
        "income": "4000.00",
        "expenses": "2029.69",
        "net": "1970.31",
        "essential": "1895.50"
      },
      {
        "month": "2026-07",
        "income": "4000.00",
        "expenses": "2057.99",
        "net": "1942.01",
        "essential": "1900.00"
      },
      {
        "month": "2026-08",
        "income": "4000.00",
        "expenses": "2021.29",
        "net": "1978.71",
        "essential": "1900.00"
      },
      {
        "month": "2026-09",
        "income": "4000.00",
        "expenses": "2040.69",
        "net": "1959.31",
        "essential": "1900.00"
      }
    ]
  },
  "rates": [
    {
      "currency": "USD",
      "rate": "0.86",
      "source": "ecb",
      "as_of": "2026-10-09"
    }
  ],
  "balances": [
    {
      "account_id": "chk",
      "code": "1000",
      "name": "Checking",
      "role": "cash",
      "currency": "EUR",
      "amount": "6543.15",
      "value": "6543.15",
      "in_cash": true,
      "debt_id": null
    },
    {
      "account_id": "sav",
      "code": "1100",
      "name": "Savings",
      "role": "cash",
      "currency": "EUR",
      "amount": "7800.00",
      "value": "7800.00",
      "in_cash": true,
      "debt_id": null
    },
    {
      "account_id": "usd",
      "code": "1200",
      "name": "Dollar account",
      "role": "cash",
      "currency": "USD",
      "amount": "2500.00",
      "value": "2150.00",
      "in_cash": true,
      "debt_id": null
    },
    {
      "account_id": "brk",
      "code": "1300",
      "name": "Brokerage",
      "role": "investment",
      "currency": "EUR",
      "amount": "13000.00",
      "value": "13000.00",
      "in_cash": false,
      "debt_id": null
    },
    {
      "account_id": "pen",
      "code": "1400",
      "name": "Pension fund",
      "role": "investment",
      "currency": "EUR",
      "amount": "25000.00",
      "value": "25000.00",
      "in_cash": false,
      "debt_id": null
    },
    {
      "account_id": "flat",
      "code": "1500",
      "name": "Flat",
      "role": "other_asset",
      "currency": "EUR",
      "amount": "300000.00",
      "value": "300000.00",
      "in_cash": false,
      "debt_id": null
    },
    {
      "account_id": "card",
      "code": "2000",
      "name": "Credit card",
      "role": "liability",
      "currency": "EUR",
      "amount": "-691.68",
      "value": "-691.68",
      "in_cash": true,
      "debt_id": null
    },
    {
      "account_id": "loan",
      "code": "2100",
      "name": "Car loan",
      "role": "liability",
      "currency": "EUR",
      "amount": "-9900.00",
      "value": "-9900.00",
      "in_cash": false,
      "debt_id": "debt-car"
    }
  ],
  "totals": {
    "cash": "15801.47",
    "savings": "0.00",
    "liquid": "16493.15",
    "investments": "38000.00",
    "other_assets": "300000.00",
    "debts": "17900.00",
    "other_liabilities": "0.00",
    "total_assets": "354493.15",
    "total_liabilities": "18591.68",
    "net_worth": "335901.47"
  },
  "debts": [
    {
      "debt_id": "debt-car",
      "name": "Car loan",
      "source": "account",
      "account_id": "loan",
      "balance": "9900.00",
      "apr": "0.059",
      "minimum_payment": "350.00",
      "already_paid": "48.68",
      "paid_off": "2029-05",
      "total_interest": "786.13"
    },
    {
      "debt_id": "debt-student",
      "name": "Student loan",
      "source": "declared",
      "account_id": null,
      "balance": "8000.00",
      "apr": "0.045",
      "minimum_payment": "120.00",
      "already_paid": "120.00",
      "paid_off": "2033-03",
      "total_interest": "1223.12"
    }
  ],
  "debt_free": "2033-03",
  "cash": {
    "start": "2026-10-11",
    "end": "2027-10-31",
    "today": "15801.47",
    "lowest": "13998.91",
    "lowest_date": "2027-02-24",
    "month_ends": [
      {
        "month": "2026-10",
        "cash": "15801.47",
        "unscheduled": "34.11",
        "invested": "3459.66"
      },
      {
        "month": "2026-11",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      },
      {
        "month": "2026-12",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      },
      {
        "month": "2027-01",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      },
      {
        "month": "2027-02",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      },
      {
        "month": "2027-03",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      },
      {
        "month": "2027-04",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      },
      {
        "month": "2027-05",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      },
      {
        "month": "2027-06",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      },
      {
        "month": "2027-07",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      },
      {
        "month": "2027-08",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      },
      {
        "month": "2027-09",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      },
      {
        "month": "2027-10",
        "cash": "15801.47",
        "unscheduled": "-250.97",
        "invested": "1661.59"
      }
    ],
    "daily": [
      {
        "date": "2026-10-11",
        "balance": "15803.09"
      },
      {
        "date": "2026-10-12",
        "balance": "15804.72"
      },
      {
        "date": "2026-10-13",
        "balance": "15806.34"
      },
      {
        "date": "2026-10-14",
        "balance": "15807.97"
      },
      {
        "date": "2026-10-15",
        "balance": "15809.59"
      },
      {
        "date": "2026-10-16",
        "balance": "15811.22"
      },
      {
        "date": "2026-10-17",
        "balance": "15812.84"
      },
      {
        "date": "2026-10-18",
        "balance": "15740.01"
      },
      {
        "date": "2026-10-19",
        "balance": "15741.64"
      },
      {
        "date": "2026-10-20",
        "balance": "15743.26"
      },
      {
        "date": "2026-10-21",
        "balance": "15744.89"
      },
      {
        "date": "2026-10-22",
        "balance": "15746.51"
      },
      {
        "date": "2026-10-23",
        "balance": "15748.14"
      },
      {
        "date": "2026-10-24",
        "balance": "15749.76"
      },
      {
        "date": "2026-10-25",
        "balance": "19751.38"
      },
      {
        "date": "2026-10-26",
        "balance": "19253.01"
      },
      {
        "date": "2026-10-27",
        "balance": "19254.63"
      },
      {
        "date": "2026-10-28",
        "balance": "19256.26"
      },
      {
        "date": "2026-10-29",
        "balance": "19257.88"
      },
      {
        "date": "2026-10-30",
        "balance": "19259.51"
      },
      {
        "date": "2026-10-31",
        "balance": "15801.47"
      },
      {
        "date": "2026-11-01",
        "balance": "14293.10"
      },
      {
        "date": "2026-11-02",
        "balance": "14284.74"
      },
      {
        "date": "2026-11-03",
        "balance": "14276.37"
      },
      {
        "date": "2026-11-04",
        "balance": "14268.01"
      },
      {
        "date": "2026-11-05",
        "balance": "14259.64"
      },
      {
        "date": "2026-11-06",
        "balance": "14251.28"
      },
      {
        "date": "2026-11-07",
        "balance": "14242.91"
      },
      {
        "date": "2026-11-08",
        "balance": "14221.55"
      },
      {
        "date": "2026-11-09",
        "balance": "14213.19"
      },
      {
        "date": "2026-11-10",
        "balance": "14204.82"
      },
      {
        "date": "2026-11-11",
        "balance": "14196.46"
      },
      {
        "date": "2026-11-12",
        "balance": "14188.09"
      },
      {
        "date": "2026-11-13",
        "balance": "14179.73"
      },
      {
        "date": "2026-11-14",
        "balance": "14171.36"
      },
      {
        "date": "2026-11-15",
        "balance": "14162.99"
      },
      {
        "date": "2026-11-16",
        "balance": "14154.63"
      },
      {
        "date": "2026-11-17",
        "balance": "14146.26"
      },
      {
        "date": "2026-11-18",
        "balance": "14063.45"
      },
      {
        "date": "2026-11-19",
        "balance": "14055.08"
      },
      {
        "date": "2026-11-20",
        "balance": "14046.72"
      },
      {
        "date": "2026-11-21",
        "balance": "14038.35"
      },
      {
        "date": "2026-11-22",
        "balance": "14029.99"
      },
      {
        "date": "2026-11-23",
        "balance": "14021.62"
      },
      {
        "date": "2026-11-24",
        "balance": "14013.25"
      },
      {
        "date": "2026-11-25",
        "balance": "18004.89"
      },
      {
        "date": "2026-11-26",
        "balance": "17496.52"
      },
      {
        "date": "2026-11-27",
        "balance": "17488.16"
      },
      {
        "date": "2026-11-28",
        "balance": "17479.79"
      },
      {
        "date": "2026-11-29",
        "balance": "17471.43"
      },
      {
        "date": "2026-11-30",
        "balance": "15801.47"
      },
      {
        "date": "2026-12-01",
        "balance": "14293.37"
      },
      {
        "date": "2026-12-02",
        "balance": "14285.28"
      },
      {
        "date": "2026-12-03",
        "balance": "14277.18"
      },
      {
        "date": "2026-12-04",
        "balance": "14269.09"
      },
      {
        "date": "2026-12-05",
        "balance": "14260.99"
      },
      {
        "date": "2026-12-06",
        "balance": "14252.90"
      },
      {
        "date": "2026-12-07",
        "balance": "14244.80"
      },
      {
        "date": "2026-12-08",
        "balance": "14223.71"
      },
      {
        "date": "2026-12-09",
        "balance": "14215.62"
      },
      {
        "date": "2026-12-10",
        "balance": "14207.52"
      },
      {
        "date": "2026-12-11",
        "balance": "14199.43"
      },
      {
        "date": "2026-12-12",
        "balance": "14191.33"
      },
      {
        "date": "2026-12-13",
        "balance": "14183.23"
      },
      {
        "date": "2026-12-14",
        "balance": "14175.14"
      },
      {
        "date": "2026-12-15",
        "balance": "14167.04"
      },
      {
        "date": "2026-12-16",
        "balance": "14158.95"
      },
      {
        "date": "2026-12-17",
        "balance": "14150.85"
      },
      {
        "date": "2026-12-18",
        "balance": "14068.31"
      },
      {
        "date": "2026-12-19",
        "balance": "14060.21"
      },
      {
        "date": "2026-12-20",
        "balance": "14052.11"
      },
      {
        "date": "2026-12-21",
        "balance": "14044.02"
      },
      {
        "date": "2026-12-22",
        "balance": "14035.92"
      },
      {
        "date": "2026-12-23",
        "balance": "14027.83"
      },
      {
        "date": "2026-12-24",
        "balance": "14019.73"
      },
      {
        "date": "2026-12-25",
        "balance": "18011.63"
      },
      {
        "date": "2026-12-26",
        "balance": "17503.54"
      },
      {
        "date": "2026-12-27",
        "balance": "17495.44"
      },
      {
        "date": "2026-12-28",
        "balance": "17487.35"
      },
      {
        "date": "2026-12-29",
        "balance": "17479.25"
      },
      {
        "date": "2026-12-30",
        "balance": "17471.16"
      },
      {
        "date": "2026-12-31",
        "balance": "15801.47"
      },
      {
        "date": "2027-01-01",
        "balance": "14293.37"
      },
      {
        "date": "2027-01-02",
        "balance": "14285.28"
      },
      {
        "date": "2027-01-03",
        "balance": "14277.18"
      },
      {
        "date": "2027-01-04",
        "balance": "14269.09"
      },
      {
        "date": "2027-01-05",
        "balance": "14260.99"
      },
      {
        "date": "2027-01-06",
        "balance": "14252.90"
      },
      {
        "date": "2027-01-07",
        "balance": "14244.80"
      },
      {
        "date": "2027-01-08",
        "balance": "14223.71"
      },
      {
        "date": "2027-01-09",
        "balance": "14215.62"
      },
      {
        "date": "2027-01-10",
        "balance": "14207.52"
      },
      {
        "date": "2027-01-11",
        "balance": "14199.43"
      },
      {
        "date": "2027-01-12",
        "balance": "14191.33"
      },
      {
        "date": "2027-01-13",
        "balance": "14183.23"
      },
      {
        "date": "2027-01-14",
        "balance": "14175.14"
      },
      {
        "date": "2027-01-15",
        "balance": "14167.04"
      },
      {
        "date": "2027-01-16",
        "balance": "14158.95"
      },
      {
        "date": "2027-01-17",
        "balance": "14150.85"
      },
      {
        "date": "2027-01-18",
        "balance": "14068.31"
      },
      {
        "date": "2027-01-19",
        "balance": "14060.21"
      },
      {
        "date": "2027-01-20",
        "balance": "14052.11"
      },
      {
        "date": "2027-01-21",
        "balance": "14044.02"
      },
      {
        "date": "2027-01-22",
        "balance": "14035.92"
      },
      {
        "date": "2027-01-23",
        "balance": "14027.83"
      },
      {
        "date": "2027-01-24",
        "balance": "14019.73"
      },
      {
        "date": "2027-01-25",
        "balance": "18011.63"
      },
      {
        "date": "2027-01-26",
        "balance": "17503.54"
      },
      {
        "date": "2027-01-27",
        "balance": "17495.44"
      },
      {
        "date": "2027-01-28",
        "balance": "17487.35"
      },
      {
        "date": "2027-01-29",
        "balance": "17479.25"
      },
      {
        "date": "2027-01-30",
        "balance": "17471.16"
      },
      {
        "date": "2027-01-31",
        "balance": "15801.47"
      },
      {
        "date": "2027-02-01",
        "balance": "14292.51"
      },
      {
        "date": "2027-02-02",
        "balance": "14283.54"
      },
      {
        "date": "2027-02-03",
        "balance": "14274.58"
      },
      {
        "date": "2027-02-04",
        "balance": "14265.62"
      },
      {
        "date": "2027-02-05",
        "balance": "14256.65"
      },
      {
        "date": "2027-02-06",
        "balance": "14247.69"
      },
      {
        "date": "2027-02-07",
        "balance": "14238.73"
      },
      {
        "date": "2027-02-08",
        "balance": "14216.77"
      },
      {
        "date": "2027-02-09",
        "balance": "14207.81"
      },
      {
        "date": "2027-02-10",
        "balance": "14198.85"
      },
      {
        "date": "2027-02-11",
        "balance": "14189.88"
      },
      {
        "date": "2027-02-12",
        "balance": "14180.92"
      },
      {
        "date": "2027-02-13",
        "balance": "14171.96"
      },
      {
        "date": "2027-02-14",
        "balance": "14162.99"
      },
      {
        "date": "2027-02-15",
        "balance": "14154.03"
      },
      {
        "date": "2027-02-16",
        "balance": "14145.07"
      },
      {
        "date": "2027-02-17",
        "balance": "14136.11"
      },
      {
        "date": "2027-02-18",
        "balance": "14052.69"
      },
      {
        "date": "2027-02-19",
        "balance": "14043.73"
      },
      {
        "date": "2027-02-20",
        "balance": "14034.77"
      },
      {
        "date": "2027-02-21",
        "balance": "14025.80"
      },
      {
        "date": "2027-02-22",
        "balance": "14016.84"
      },
      {
        "date": "2027-02-23",
        "balance": "14007.88"
      },
      {
        "date": "2027-02-24",
        "balance": "13998.91"
      },
      {
        "date": "2027-02-25",
        "balance": "17989.95"
      },
      {
        "date": "2027-02-26",
        "balance": "17480.99"
      },
      {
        "date": "2027-02-27",
        "balance": "17472.02"
      },
      {
        "date": "2027-02-28",
        "balance": "15801.47"
      },
      {
        "date": "2027-03-01",
        "balance": "14293.37"
      },
      {
        "date": "2027-03-02",
        "balance": "14285.28"
      },
      {
        "date": "2027-03-03",
        "balance": "14277.18"
      },
      {
        "date": "2027-03-04",
        "balance": "14269.09"
      },
      {
        "date": "2027-03-05",
        "balance": "14260.99"
      },
      {
        "date": "2027-03-06",
        "balance": "14252.90"
      },
      {
        "date": "2027-03-07",
        "balance": "14244.80"
      },
      {
        "date": "2027-03-08",
        "balance": "14223.71"
      },
      {
        "date": "2027-03-09",
        "balance": "14215.62"
      },
      {
        "date": "2027-03-10",
        "balance": "14207.52"
      },
      {
        "date": "2027-03-11",
        "balance": "14199.43"
      },
      {
        "date": "2027-03-12",
        "balance": "14191.33"
      },
      {
        "date": "2027-03-13",
        "balance": "14183.23"
      },
      {
        "date": "2027-03-14",
        "balance": "14175.14"
      },
      {
        "date": "2027-03-15",
        "balance": "14167.04"
      },
      {
        "date": "2027-03-16",
        "balance": "14158.95"
      },
      {
        "date": "2027-03-17",
        "balance": "14150.85"
      },
      {
        "date": "2027-03-18",
        "balance": "14068.31"
      },
      {
        "date": "2027-03-19",
        "balance": "14060.21"
      },
      {
        "date": "2027-03-20",
        "balance": "14052.11"
      },
      {
        "date": "2027-03-21",
        "balance": "14044.02"
      },
      {
        "date": "2027-03-22",
        "balance": "14035.92"
      },
      {
        "date": "2027-03-23",
        "balance": "14027.83"
      },
      {
        "date": "2027-03-24",
        "balance": "14019.73"
      },
      {
        "date": "2027-03-25",
        "balance": "18011.63"
      },
      {
        "date": "2027-03-26",
        "balance": "17503.54"
      },
      {
        "date": "2027-03-27",
        "balance": "17495.44"
      },
      {
        "date": "2027-03-28",
        "balance": "17487.35"
      },
      {
        "date": "2027-03-29",
        "balance": "17479.25"
      },
      {
        "date": "2027-03-30",
        "balance": "17471.16"
      },
      {
        "date": "2027-03-31",
        "balance": "15801.47"
      },
      {
        "date": "2027-04-01",
        "balance": "14293.10"
      },
      {
        "date": "2027-04-02",
        "balance": "14284.74"
      },
      {
        "date": "2027-04-03",
        "balance": "14276.37"
      },
      {
        "date": "2027-04-04",
        "balance": "14268.01"
      },
      {
        "date": "2027-04-05",
        "balance": "14259.64"
      },
      {
        "date": "2027-04-06",
        "balance": "14251.28"
      },
      {
        "date": "2027-04-07",
        "balance": "14242.91"
      },
      {
        "date": "2027-04-08",
        "balance": "14221.55"
      },
      {
        "date": "2027-04-09",
        "balance": "14213.19"
      },
      {
        "date": "2027-04-10",
        "balance": "14204.82"
      },
      {
        "date": "2027-04-11",
        "balance": "14196.46"
      },
      {
        "date": "2027-04-12",
        "balance": "14188.09"
      },
      {
        "date": "2027-04-13",
        "balance": "14179.73"
      },
      {
        "date": "2027-04-14",
        "balance": "14171.36"
      },
      {
        "date": "2027-04-15",
        "balance": "14162.99"
      },
      {
        "date": "2027-04-16",
        "balance": "14154.63"
      },
      {
        "date": "2027-04-17",
        "balance": "14146.26"
      },
      {
        "date": "2027-04-18",
        "balance": "14063.45"
      },
      {
        "date": "2027-04-19",
        "balance": "14055.08"
      },
      {
        "date": "2027-04-20",
        "balance": "14046.72"
      },
      {
        "date": "2027-04-21",
        "balance": "14038.35"
      },
      {
        "date": "2027-04-22",
        "balance": "14029.99"
      },
      {
        "date": "2027-04-23",
        "balance": "14021.62"
      },
      {
        "date": "2027-04-24",
        "balance": "14013.25"
      },
      {
        "date": "2027-04-25",
        "balance": "18004.89"
      },
      {
        "date": "2027-04-26",
        "balance": "17496.52"
      },
      {
        "date": "2027-04-27",
        "balance": "17488.16"
      },
      {
        "date": "2027-04-28",
        "balance": "17479.79"
      },
      {
        "date": "2027-04-29",
        "balance": "17471.43"
      },
      {
        "date": "2027-04-30",
        "balance": "15801.47"
      },
      {
        "date": "2027-05-01",
        "balance": "14293.37"
      },
      {
        "date": "2027-05-02",
        "balance": "14285.28"
      },
      {
        "date": "2027-05-03",
        "balance": "14277.18"
      },
      {
        "date": "2027-05-04",
        "balance": "14269.09"
      },
      {
        "date": "2027-05-05",
        "balance": "14260.99"
      },
      {
        "date": "2027-05-06",
        "balance": "14252.90"
      },
      {
        "date": "2027-05-07",
        "balance": "14244.80"
      },
      {
        "date": "2027-05-08",
        "balance": "14223.71"
      },
      {
        "date": "2027-05-09",
        "balance": "14215.62"
      },
      {
        "date": "2027-05-10",
        "balance": "14207.52"
      },
      {
        "date": "2027-05-11",
        "balance": "14199.43"
      },
      {
        "date": "2027-05-12",
        "balance": "14191.33"
      },
      {
        "date": "2027-05-13",
        "balance": "14183.23"
      },
      {
        "date": "2027-05-14",
        "balance": "14175.14"
      },
      {
        "date": "2027-05-15",
        "balance": "14167.04"
      },
      {
        "date": "2027-05-16",
        "balance": "14158.95"
      },
      {
        "date": "2027-05-17",
        "balance": "14150.85"
      },
      {
        "date": "2027-05-18",
        "balance": "14068.31"
      },
      {
        "date": "2027-05-19",
        "balance": "14060.21"
      },
      {
        "date": "2027-05-20",
        "balance": "14052.11"
      },
      {
        "date": "2027-05-21",
        "balance": "14044.02"
      },
      {
        "date": "2027-05-22",
        "balance": "14035.92"
      },
      {
        "date": "2027-05-23",
        "balance": "14027.83"
      },
      {
        "date": "2027-05-24",
        "balance": "14019.73"
      },
      {
        "date": "2027-05-25",
        "balance": "18011.63"
      },
      {
        "date": "2027-05-26",
        "balance": "17503.54"
      },
      {
        "date": "2027-05-27",
        "balance": "17495.44"
      },
      {
        "date": "2027-05-28",
        "balance": "17487.35"
      },
      {
        "date": "2027-05-29",
        "balance": "17479.25"
      },
      {
        "date": "2027-05-30",
        "balance": "17471.16"
      },
      {
        "date": "2027-05-31",
        "balance": "15801.47"
      },
      {
        "date": "2027-06-01",
        "balance": "14293.10"
      },
      {
        "date": "2027-06-02",
        "balance": "14284.74"
      },
      {
        "date": "2027-06-03",
        "balance": "14276.37"
      },
      {
        "date": "2027-06-04",
        "balance": "14268.01"
      },
      {
        "date": "2027-06-05",
        "balance": "14259.64"
      },
      {
        "date": "2027-06-06",
        "balance": "14251.28"
      },
      {
        "date": "2027-06-07",
        "balance": "14242.91"
      },
      {
        "date": "2027-06-08",
        "balance": "14221.55"
      },
      {
        "date": "2027-06-09",
        "balance": "14213.19"
      },
      {
        "date": "2027-06-10",
        "balance": "14204.82"
      },
      {
        "date": "2027-06-11",
        "balance": "14196.46"
      },
      {
        "date": "2027-06-12",
        "balance": "14188.09"
      },
      {
        "date": "2027-06-13",
        "balance": "14179.73"
      },
      {
        "date": "2027-06-14",
        "balance": "14171.36"
      },
      {
        "date": "2027-06-15",
        "balance": "14162.99"
      },
      {
        "date": "2027-06-16",
        "balance": "14154.63"
      },
      {
        "date": "2027-06-17",
        "balance": "14146.26"
      },
      {
        "date": "2027-06-18",
        "balance": "14063.45"
      },
      {
        "date": "2027-06-19",
        "balance": "14055.08"
      },
      {
        "date": "2027-06-20",
        "balance": "14046.72"
      },
      {
        "date": "2027-06-21",
        "balance": "14038.35"
      },
      {
        "date": "2027-06-22",
        "balance": "14029.99"
      },
      {
        "date": "2027-06-23",
        "balance": "14021.62"
      },
      {
        "date": "2027-06-24",
        "balance": "14013.25"
      },
      {
        "date": "2027-06-25",
        "balance": "18004.89"
      },
      {
        "date": "2027-06-26",
        "balance": "17496.52"
      },
      {
        "date": "2027-06-27",
        "balance": "17488.16"
      },
      {
        "date": "2027-06-28",
        "balance": "17479.79"
      },
      {
        "date": "2027-06-29",
        "balance": "17471.43"
      },
      {
        "date": "2027-06-30",
        "balance": "15801.47"
      },
      {
        "date": "2027-07-01",
        "balance": "14293.37"
      },
      {
        "date": "2027-07-02",
        "balance": "14285.28"
      },
      {
        "date": "2027-07-03",
        "balance": "14277.18"
      },
      {
        "date": "2027-07-04",
        "balance": "14269.09"
      },
      {
        "date": "2027-07-05",
        "balance": "14260.99"
      },
      {
        "date": "2027-07-06",
        "balance": "14252.90"
      },
      {
        "date": "2027-07-07",
        "balance": "14244.80"
      },
      {
        "date": "2027-07-08",
        "balance": "14223.71"
      },
      {
        "date": "2027-07-09",
        "balance": "14215.62"
      },
      {
        "date": "2027-07-10",
        "balance": "14207.52"
      },
      {
        "date": "2027-07-11",
        "balance": "14199.43"
      },
      {
        "date": "2027-07-12",
        "balance": "14191.33"
      },
      {
        "date": "2027-07-13",
        "balance": "14183.23"
      },
      {
        "date": "2027-07-14",
        "balance": "14175.14"
      },
      {
        "date": "2027-07-15",
        "balance": "14167.04"
      },
      {
        "date": "2027-07-16",
        "balance": "14158.95"
      },
      {
        "date": "2027-07-17",
        "balance": "14150.85"
      },
      {
        "date": "2027-07-18",
        "balance": "14068.31"
      },
      {
        "date": "2027-07-19",
        "balance": "14060.21"
      },
      {
        "date": "2027-07-20",
        "balance": "14052.11"
      },
      {
        "date": "2027-07-21",
        "balance": "14044.02"
      },
      {
        "date": "2027-07-22",
        "balance": "14035.92"
      },
      {
        "date": "2027-07-23",
        "balance": "14027.83"
      },
      {
        "date": "2027-07-24",
        "balance": "14019.73"
      },
      {
        "date": "2027-07-25",
        "balance": "18011.63"
      },
      {
        "date": "2027-07-26",
        "balance": "17503.54"
      },
      {
        "date": "2027-07-27",
        "balance": "17495.44"
      },
      {
        "date": "2027-07-28",
        "balance": "17487.35"
      },
      {
        "date": "2027-07-29",
        "balance": "17479.25"
      },
      {
        "date": "2027-07-30",
        "balance": "17471.16"
      },
      {
        "date": "2027-07-31",
        "balance": "15801.47"
      },
      {
        "date": "2027-08-01",
        "balance": "14293.37"
      },
      {
        "date": "2027-08-02",
        "balance": "14285.28"
      },
      {
        "date": "2027-08-03",
        "balance": "14277.18"
      },
      {
        "date": "2027-08-04",
        "balance": "14269.09"
      },
      {
        "date": "2027-08-05",
        "balance": "14260.99"
      },
      {
        "date": "2027-08-06",
        "balance": "14252.90"
      },
      {
        "date": "2027-08-07",
        "balance": "14244.80"
      },
      {
        "date": "2027-08-08",
        "balance": "14223.71"
      },
      {
        "date": "2027-08-09",
        "balance": "14215.62"
      },
      {
        "date": "2027-08-10",
        "balance": "14207.52"
      },
      {
        "date": "2027-08-11",
        "balance": "14199.43"
      },
      {
        "date": "2027-08-12",
        "balance": "14191.33"
      },
      {
        "date": "2027-08-13",
        "balance": "14183.23"
      },
      {
        "date": "2027-08-14",
        "balance": "14175.14"
      },
      {
        "date": "2027-08-15",
        "balance": "14167.04"
      },
      {
        "date": "2027-08-16",
        "balance": "14158.95"
      },
      {
        "date": "2027-08-17",
        "balance": "14150.85"
      },
      {
        "date": "2027-08-18",
        "balance": "14068.31"
      },
      {
        "date": "2027-08-19",
        "balance": "14060.21"
      },
      {
        "date": "2027-08-20",
        "balance": "14052.11"
      },
      {
        "date": "2027-08-21",
        "balance": "14044.02"
      },
      {
        "date": "2027-08-22",
        "balance": "14035.92"
      },
      {
        "date": "2027-08-23",
        "balance": "14027.83"
      },
      {
        "date": "2027-08-24",
        "balance": "14019.73"
      },
      {
        "date": "2027-08-25",
        "balance": "18011.63"
      },
      {
        "date": "2027-08-26",
        "balance": "17503.54"
      },
      {
        "date": "2027-08-27",
        "balance": "17495.44"
      },
      {
        "date": "2027-08-28",
        "balance": "17487.35"
      },
      {
        "date": "2027-08-29",
        "balance": "17479.25"
      },
      {
        "date": "2027-08-30",
        "balance": "17471.16"
      },
      {
        "date": "2027-08-31",
        "balance": "15801.47"
      },
      {
        "date": "2027-09-01",
        "balance": "14293.10"
      },
      {
        "date": "2027-09-02",
        "balance": "14284.74"
      },
      {
        "date": "2027-09-03",
        "balance": "14276.37"
      },
      {
        "date": "2027-09-04",
        "balance": "14268.01"
      },
      {
        "date": "2027-09-05",
        "balance": "14259.64"
      },
      {
        "date": "2027-09-06",
        "balance": "14251.28"
      },
      {
        "date": "2027-09-07",
        "balance": "14242.91"
      },
      {
        "date": "2027-09-08",
        "balance": "14221.55"
      },
      {
        "date": "2027-09-09",
        "balance": "14213.19"
      },
      {
        "date": "2027-09-10",
        "balance": "14204.82"
      },
      {
        "date": "2027-09-11",
        "balance": "14196.46"
      },
      {
        "date": "2027-09-12",
        "balance": "14188.09"
      },
      {
        "date": "2027-09-13",
        "balance": "14179.73"
      },
      {
        "date": "2027-09-14",
        "balance": "14171.36"
      },
      {
        "date": "2027-09-15",
        "balance": "14162.99"
      },
      {
        "date": "2027-09-16",
        "balance": "14154.63"
      },
      {
        "date": "2027-09-17",
        "balance": "14146.26"
      },
      {
        "date": "2027-09-18",
        "balance": "14063.45"
      },
      {
        "date": "2027-09-19",
        "balance": "14055.08"
      },
      {
        "date": "2027-09-20",
        "balance": "14046.72"
      },
      {
        "date": "2027-09-21",
        "balance": "14038.35"
      },
      {
        "date": "2027-09-22",
        "balance": "14029.99"
      },
      {
        "date": "2027-09-23",
        "balance": "14021.62"
      },
      {
        "date": "2027-09-24",
        "balance": "14013.25"
      },
      {
        "date": "2027-09-25",
        "balance": "18004.89"
      },
      {
        "date": "2027-09-26",
        "balance": "17496.52"
      },
      {
        "date": "2027-09-27",
        "balance": "17488.16"
      },
      {
        "date": "2027-09-28",
        "balance": "17479.79"
      },
      {
        "date": "2027-09-29",
        "balance": "17471.43"
      },
      {
        "date": "2027-09-30",
        "balance": "15801.47"
      },
      {
        "date": "2027-10-01",
        "balance": "14293.37"
      },
      {
        "date": "2027-10-02",
        "balance": "14285.28"
      },
      {
        "date": "2027-10-03",
        "balance": "14277.18"
      },
      {
        "date": "2027-10-04",
        "balance": "14269.09"
      },
      {
        "date": "2027-10-05",
        "balance": "14260.99"
      },
      {
        "date": "2027-10-06",
        "balance": "14252.90"
      },
      {
        "date": "2027-10-07",
        "balance": "14244.80"
      },
      {
        "date": "2027-10-08",
        "balance": "14223.71"
      },
      {
        "date": "2027-10-09",
        "balance": "14215.62"
      },
      {
        "date": "2027-10-10",
        "balance": "14207.52"
      },
      {
        "date": "2027-10-11",
        "balance": "14199.43"
      },
      {
        "date": "2027-10-12",
        "balance": "14191.33"
      },
      {
        "date": "2027-10-13",
        "balance": "14183.23"
      },
      {
        "date": "2027-10-14",
        "balance": "14175.14"
      },
      {
        "date": "2027-10-15",
        "balance": "14167.04"
      },
      {
        "date": "2027-10-16",
        "balance": "14158.95"
      },
      {
        "date": "2027-10-17",
        "balance": "14150.85"
      },
      {
        "date": "2027-10-18",
        "balance": "14068.31"
      },
      {
        "date": "2027-10-19",
        "balance": "14060.21"
      },
      {
        "date": "2027-10-20",
        "balance": "14052.11"
      },
      {
        "date": "2027-10-21",
        "balance": "14044.02"
      },
      {
        "date": "2027-10-22",
        "balance": "14035.92"
      },
      {
        "date": "2027-10-23",
        "balance": "14027.83"
      },
      {
        "date": "2027-10-24",
        "balance": "14019.73"
      },
      {
        "date": "2027-10-25",
        "balance": "18011.63"
      },
      {
        "date": "2027-10-26",
        "balance": "17503.54"
      },
      {
        "date": "2027-10-27",
        "balance": "17495.44"
      },
      {
        "date": "2027-10-28",
        "balance": "17487.35"
      },
      {
        "date": "2027-10-29",
        "balance": "17479.25"
      },
      {
        "date": "2027-10-30",
        "balance": "17471.16"
      },
      {
        "date": "2027-10-31",
        "balance": "15801.47"
      }
    ]
  },
  "monthly": {
    "horizon_years": 30,
    "real_return": "0.04",
    "surplus_invested": "1",
    "inflation": null,
    "points": [
      {
        "month": "2026-10",
        "date": "2026-10-11",
        "cash": "15801.47",
        "investments": "38000.00",
        "other_assets": "300000.00",
        "debts": "17900.00",
        "other_liabilities": "0.00",
        "net_worth": "335901.47"
      },
      {
        "month": "2026-10",
        "date": "2026-10-31",
        "cash": "15801.47",
        "investments": "41545.47",
        "other_assets": "300000.00",
        "debts": "17900.00",
        "other_liabilities": "0.00",
        "net_worth": "339446.94"
      },
      {
        "month": "2026-11",
        "date": "2026-11-30",
        "cash": "15801.47",
        "investments": "43345.54",
        "other_assets": "300000.00",
        "debts": "17508.68",
        "other_liabilities": "0.00",
        "net_worth": "341638.33"
      },
      {
        "month": "2026-12",
        "date": "2026-12-31",
        "cash": "15801.47",
        "investments": "45151.62",
        "other_assets": "300000.00",
        "debts": "17115.53",
        "other_liabilities": "0.00",
        "net_worth": "343837.56"
      },
      {
        "month": "2027-01",
        "date": "2027-01-31",
        "cash": "15801.47",
        "investments": "46963.71",
        "other_assets": "300000.00",
        "debts": "16720.55",
        "other_liabilities": "0.00",
        "net_worth": "346044.63"
      },
      {
        "month": "2027-02",
        "date": "2027-02-28",
        "cash": "15801.47",
        "investments": "48781.85",
        "other_assets": "300000.00",
        "debts": "16323.74",
        "other_liabilities": "0.00",
        "net_worth": "348259.58"
      },
      {
        "month": "2027-03",
        "date": "2027-03-31",
        "cash": "15801.47",
        "investments": "50606.04",
        "other_assets": "300000.00",
        "debts": "15925.09",
        "other_liabilities": "0.00",
        "net_worth": "350482.42"
      },
      {
        "month": "2027-04",
        "date": "2027-04-30",
        "cash": "15801.47",
        "investments": "52436.32",
        "other_assets": "300000.00",
        "debts": "15524.58",
        "other_liabilities": "0.00",
        "net_worth": "352713.21"
      },
      {
        "month": "2027-05",
        "date": "2027-05-31",
        "cash": "15801.47",
        "investments": "54272.70",
        "other_assets": "300000.00",
        "debts": "15122.22",
        "other_liabilities": "0.00",
        "net_worth": "354951.95"
      },
      {
        "month": "2027-06",
        "date": "2027-06-30",
        "cash": "15801.47",
        "investments": "56115.20",
        "other_assets": "300000.00",
        "debts": "14717.98",
        "other_liabilities": "0.00",
        "net_worth": "357198.69"
      },
      {
        "month": "2027-07",
        "date": "2027-07-31",
        "cash": "15801.47",
        "investments": "57963.84",
        "other_assets": "300000.00",
        "debts": "14311.86",
        "other_liabilities": "0.00",
        "net_worth": "359453.45"
      },
      {
        "month": "2027-08",
        "date": "2027-08-31",
        "cash": "15801.47",
        "investments": "59818.64",
        "other_assets": "300000.00",
        "debts": "13903.86",
        "other_liabilities": "0.00",
        "net_worth": "361716.25"
      },
      {
        "month": "2027-09",
        "date": "2027-09-30",
        "cash": "15801.47",
        "investments": "61679.63",
        "other_assets": "300000.00",
        "debts": "13493.96",
        "other_liabilities": "0.00",
        "net_worth": "363987.14"
      },
      {
        "month": "2027-10",
        "date": "2027-10-31",
        "cash": "15801.47",
        "investments": "63546.81",
        "other_assets": "300000.00",
        "debts": "13082.15",
        "other_liabilities": "0.00",
        "net_worth": "366266.13"
      },
      {
        "month": "2027-11",
        "date": "2027-11-30",
        "cash": "15801.47",
        "investments": "65420.23",
        "other_assets": "300000.00",
        "debts": "12668.43",
        "other_liabilities": "0.00",
        "net_worth": "368553.27"
      },
      {
        "month": "2027-12",
        "date": "2027-12-31",
        "cash": "15801.47",
        "investments": "67299.89",
        "other_assets": "300000.00",
        "debts": "12252.78",
        "other_liabilities": "0.00",
        "net_worth": "370848.58"
      },
      {
        "month": "2028-01",
        "date": "2028-01-31",
        "cash": "15801.47",
        "investments": "69185.81",
        "other_assets": "300000.00",
        "debts": "11835.20",
        "other_liabilities": "0.00",
        "net_worth": "373152.08"
      },
      {
        "month": "2028-02",
        "date": "2028-02-29",
        "cash": "15801.47",
        "investments": "71078.02",
        "other_assets": "300000.00",
        "debts": "11415.67",
        "other_liabilities": "0.00",
        "net_worth": "375463.82"
      },
      {
        "month": "2028-03",
        "date": "2028-03-31",
        "cash": "15801.47",
        "investments": "72976.53",
        "other_assets": "300000.00",
        "debts": "10994.20",
        "other_liabilities": "0.00",
        "net_worth": "377783.80"
      },
      {
        "month": "2028-04",
        "date": "2028-04-30",
        "cash": "15801.47",
        "investments": "74881.38",
        "other_assets": "300000.00",
        "debts": "10570.76",
        "other_liabilities": "0.00",
        "net_worth": "380112.09"
      },
      {
        "month": "2028-05",
        "date": "2028-05-31",
        "cash": "15801.47",
        "investments": "76792.57",
        "other_assets": "300000.00",
        "debts": "10145.35",
        "other_liabilities": "0.00",
        "net_worth": "382448.69"
      },
      {
        "month": "2028-06",
        "date": "2028-06-30",
        "cash": "15801.47",
        "investments": "78710.14",
        "other_assets": "300000.00",
        "debts": "9717.97",
        "other_liabilities": "0.00",
        "net_worth": "384793.64"
      },
      {
        "month": "2028-07",
        "date": "2028-07-31",
        "cash": "15801.47",
        "investments": "80634.10",
        "other_assets": "300000.00",
        "debts": "9288.59",
        "other_liabilities": "0.00",
        "net_worth": "387146.98"
      },
      {
        "month": "2028-08",
        "date": "2028-08-31",
        "cash": "15801.47",
        "investments": "82564.47",
        "other_assets": "300000.00",
        "debts": "8857.21",
        "other_liabilities": "0.00",
        "net_worth": "389508.73"
      },
      {
        "month": "2028-09",
        "date": "2028-09-30",
        "cash": "15801.47",
        "investments": "84501.27",
        "other_assets": "300000.00",
        "debts": "8423.83",
        "other_liabilities": "0.00",
        "net_worth": "391878.91"
      },
      {
        "month": "2028-10",
        "date": "2028-10-31",
        "cash": "15801.47",
        "investments": "86444.53",
        "other_assets": "300000.00",
        "debts": "7988.43",
        "other_liabilities": "0.00",
        "net_worth": "394257.57"
      },
      {
        "month": "2028-11",
        "date": "2028-11-30",
        "cash": "15801.47",
        "investments": "88394.27",
        "other_assets": "300000.00",
        "debts": "7551.00",
        "other_liabilities": "0.00",
        "net_worth": "396644.74"
      },
      {
        "month": "2028-12",
        "date": "2028-12-31",
        "cash": "15801.47",
        "investments": "90350.51",
        "other_assets": "300000.00",
        "debts": "7111.54",
        "other_liabilities": "0.00",
        "net_worth": "399040.44"
      },
      {
        "month": "2029-01",
        "date": "2029-01-31",
        "cash": "15801.47",
        "investments": "92313.27",
        "other_assets": "300000.00",
        "debts": "6670.03",
        "other_liabilities": "0.00",
        "net_worth": "401444.71"
      },
      {
        "month": "2029-02",
        "date": "2029-02-28",
        "cash": "15801.47",
        "investments": "94282.57",
        "other_assets": "300000.00",
        "debts": "6226.47",
        "other_liabilities": "0.00",
        "net_worth": "403857.57"
      },
      {
        "month": "2029-03",
        "date": "2029-03-31",
        "cash": "15801.47",
        "investments": "96258.43",
        "other_assets": "300000.00",
        "debts": "5780.85",
        "other_liabilities": "0.00",
        "net_worth": "406279.05"
      },
      {
        "month": "2029-04",
        "date": "2029-04-30",
        "cash": "15801.47",
        "investments": "98240.88",
        "other_assets": "300000.00",
        "debts": "5333.15",
        "other_liabilities": "0.00",
        "net_worth": "408709.20"
      },
      {
        "month": "2029-05",
        "date": "2029-05-31",
        "cash": "15801.47",
        "investments": "100393.81",
        "other_assets": "300000.00",
        "debts": "5047.23",
        "other_liabilities": "0.00",
        "net_worth": "411148.05"
      },
      {
        "month": "2029-06",
        "date": "2029-06-30",
        "cash": "15801.47",
        "investments": "102740.05",
        "other_assets": "300000.00",
        "debts": "4946.16",
        "other_liabilities": "0.00",
        "net_worth": "413595.36"
      },
      {
        "month": "2029-07",
        "date": "2029-07-31",
        "cash": "15801.47",
        "investments": "105094.11",
        "other_assets": "300000.00",
        "debts": "4844.71",
        "other_liabilities": "0.00",
        "net_worth": "416050.87"
      },
      {
        "month": "2029-08",
        "date": "2029-08-31",
        "cash": "15801.47",
        "investments": "107456.01",
        "other_assets": "300000.00",
        "debts": "4742.88",
        "other_liabilities": "0.00",
        "net_worth": "418514.60"
      },
      {
        "month": "2029-09",
        "date": "2029-09-30",
        "cash": "15801.47",
        "investments": "109825.79",
        "other_assets": "300000.00",
        "debts": "4640.67",
        "other_liabilities": "0.00",
        "net_worth": "420986.59"
      },
      {
        "month": "2029-10",
        "date": "2029-10-31",
        "cash": "15801.47",
        "investments": "112203.46",
        "other_assets": "300000.00",
        "debts": "4538.07",
        "other_liabilities": "0.00",
        "net_worth": "423466.86"
      },
      {
        "month": "2029-11",
        "date": "2029-11-30",
        "cash": "15801.47",
        "investments": "114589.06",
        "other_assets": "300000.00",
        "debts": "4435.09",
        "other_liabilities": "0.00",
        "net_worth": "425955.44"
      },
      {
        "month": "2029-12",
        "date": "2029-12-31",
        "cash": "15801.47",
        "investments": "116982.62",
        "other_assets": "300000.00",
        "debts": "4331.72",
        "other_liabilities": "0.00",
        "net_worth": "428452.37"
      },
      {
        "month": "2030-01",
        "date": "2030-01-31",
        "cash": "15801.47",
        "investments": "119384.15",
        "other_assets": "300000.00",
        "debts": "4227.96",
        "other_liabilities": "0.00",
        "net_worth": "430957.66"
      },
      {
        "month": "2030-02",
        "date": "2030-02-28",
        "cash": "15801.47",
        "investments": "121793.69",
        "other_assets": "300000.00",
        "debts": "4123.81",
        "other_liabilities": "0.00",
        "net_worth": "433471.35"
      },
      {
        "month": "2030-03",
        "date": "2030-03-31",
        "cash": "15801.47",
        "investments": "124211.26",
        "other_assets": "300000.00",
        "debts": "4019.27",
        "other_liabilities": "0.00",
        "net_worth": "435993.46"
      },
      {
        "month": "2030-04",
        "date": "2030-04-30",
        "cash": "15801.47",
        "investments": "126636.88",
        "other_assets": "300000.00",
        "debts": "3914.34",
        "other_liabilities": "0.00",
        "net_worth": "438524.01"
      },
      {
        "month": "2030-05",
        "date": "2030-05-31",
        "cash": "15801.47",
        "investments": "129070.60",
        "other_assets": "300000.00",
        "debts": "3809.02",
        "other_liabilities": "0.00",
        "net_worth": "441063.05"
      },
      {
        "month": "2030-06",
        "date": "2030-06-30",
        "cash": "15801.47",
        "investments": "131512.42",
        "other_assets": "300000.00",
        "debts": "3703.30",
        "other_liabilities": "0.00",
        "net_worth": "443610.59"
      },
      {
        "month": "2030-07",
        "date": "2030-07-31",
        "cash": "15801.47",
        "investments": "133962.39",
        "other_assets": "300000.00",
        "debts": "3597.19",
        "other_liabilities": "0.00",
        "net_worth": "446166.67"
      },
      {
        "month": "2030-08",
        "date": "2030-08-31",
        "cash": "15801.47",
        "investments": "136420.52",
        "other_assets": "300000.00",
        "debts": "3490.68",
        "other_liabilities": "0.00",
        "net_worth": "448731.31"
      },
      {
        "month": "2030-09",
        "date": "2030-09-30",
        "cash": "15801.47",
        "investments": "138886.84",
        "other_assets": "300000.00",
        "debts": "3383.77",
        "other_liabilities": "0.00",
        "net_worth": "451304.54"
      },
      {
        "month": "2030-10",
        "date": "2030-10-31",
        "cash": "15801.47",
        "investments": "141361.39",
        "other_assets": "300000.00",
        "debts": "3276.46",
        "other_liabilities": "0.00",
        "net_worth": "453886.40"
      },
      {
        "month": "2030-11",
        "date": "2030-11-30",
        "cash": "15801.47",
        "investments": "143844.18",
        "other_assets": "300000.00",
        "debts": "3168.75",
        "other_liabilities": "0.00",
        "net_worth": "456476.90"
      },
      {
        "month": "2030-12",
        "date": "2030-12-31",
        "cash": "15801.47",
        "investments": "146335.25",
        "other_assets": "300000.00",
        "debts": "3060.63",
        "other_liabilities": "0.00",
        "net_worth": "459076.09"
      },
      {
        "month": "2031-01",
        "date": "2031-01-31",
        "cash": "15801.47",
        "investments": "148834.63",
        "other_assets": "300000.00",
        "debts": "2952.11",
        "other_liabilities": "0.00",
        "net_worth": "461683.99"
      },
      {
        "month": "2031-02",
        "date": "2031-02-28",
        "cash": "15801.47",
        "investments": "151342.33",
        "other_assets": "300000.00",
        "debts": "2843.18",
        "other_liabilities": "0.00",
        "net_worth": "464300.62"
      },
      {
        "month": "2031-03",
        "date": "2031-03-31",
        "cash": "15801.47",
        "investments": "153858.40",
        "other_assets": "300000.00",
        "debts": "2733.84",
        "other_liabilities": "0.00",
        "net_worth": "466926.03"
      },
      {
        "month": "2031-04",
        "date": "2031-04-30",
        "cash": "15801.47",
        "investments": "156382.85",
        "other_assets": "300000.00",
        "debts": "2624.09",
        "other_liabilities": "0.00",
        "net_worth": "469560.23"
      },
      {
        "month": "2031-05",
        "date": "2031-05-31",
        "cash": "15801.47",
        "investments": "158915.72",
        "other_assets": "300000.00",
        "debts": "2513.93",
        "other_liabilities": "0.00",
        "net_worth": "472203.26"
      },
      {
        "month": "2031-06",
        "date": "2031-06-30",
        "cash": "15801.47",
        "investments": "161457.03",
        "other_assets": "300000.00",
        "debts": "2403.36",
        "other_liabilities": "0.00",
        "net_worth": "474855.14"
      },
      {
        "month": "2031-07",
        "date": "2031-07-31",
        "cash": "15801.47",
        "investments": "164006.81",
        "other_assets": "300000.00",
        "debts": "2292.37",
        "other_liabilities": "0.00",
        "net_worth": "477515.91"
      },
      {
        "month": "2031-08",
        "date": "2031-08-31",
        "cash": "15801.47",
        "investments": "166565.08",
        "other_assets": "300000.00",
        "debts": "2180.97",
        "other_liabilities": "0.00",
        "net_worth": "480185.58"
      },
      {
        "month": "2031-09",
        "date": "2031-09-30",
        "cash": "15801.47",
        "investments": "169131.89",
        "other_assets": "300000.00",
        "debts": "2069.15",
        "other_liabilities": "0.00",
        "net_worth": "482864.21"
      },
      {
        "month": "2031-10",
        "date": "2031-10-31",
        "cash": "15801.47",
        "investments": "171707.25",
        "other_assets": "300000.00",
        "debts": "1956.91",
        "other_liabilities": "0.00",
        "net_worth": "485551.81"
      },
      {
        "month": "2031-11",
        "date": "2031-11-30",
        "cash": "15801.47",
        "investments": "174291.20",
        "other_assets": "300000.00",
        "debts": "1844.25",
        "other_liabilities": "0.00",
        "net_worth": "488248.42"
      },
      {
        "month": "2031-12",
        "date": "2031-12-31",
        "cash": "15801.47",
        "investments": "176883.76",
        "other_assets": "300000.00",
        "debts": "1731.17",
        "other_liabilities": "0.00",
        "net_worth": "490954.06"
      },
      {
        "month": "2032-01",
        "date": "2032-01-31",
        "cash": "15801.47",
        "investments": "179484.97",
        "other_assets": "300000.00",
        "debts": "1617.66",
        "other_liabilities": "0.00",
        "net_worth": "493668.78"
      },
      {
        "month": "2032-02",
        "date": "2032-02-29",
        "cash": "15801.47",
        "investments": "182094.84",
        "other_assets": "300000.00",
        "debts": "1503.73",
        "other_liabilities": "0.00",
        "net_worth": "496392.58"
      },
      {
        "month": "2032-03",
        "date": "2032-03-31",
        "cash": "15801.47",
        "investments": "184713.41",
        "other_assets": "300000.00",
        "debts": "1389.37",
        "other_liabilities": "0.00",
        "net_worth": "499125.51"
      },
      {
        "month": "2032-04",
        "date": "2032-04-30",
        "cash": "15801.47",
        "investments": "187340.71",
        "other_assets": "300000.00",
        "debts": "1274.58",
        "other_liabilities": "0.00",
        "net_worth": "501867.60"
      },
      {
        "month": "2032-05",
        "date": "2032-05-31",
        "cash": "15801.47",
        "investments": "189976.77",
        "other_assets": "300000.00",
        "debts": "1159.36",
        "other_liabilities": "0.00",
        "net_worth": "504618.88"
      },
      {
        "month": "2032-06",
        "date": "2032-06-30",
        "cash": "15801.47",
        "investments": "192621.62",
        "other_assets": "300000.00",
        "debts": "1043.71",
        "other_liabilities": "0.00",
        "net_worth": "507379.38"
      },
      {
        "month": "2032-07",
        "date": "2032-07-31",
        "cash": "15801.47",
        "investments": "195275.28",
        "other_assets": "300000.00",
        "debts": "927.62",
        "other_liabilities": "0.00",
        "net_worth": "510149.13"
      },
      {
        "month": "2032-08",
        "date": "2032-08-31",
        "cash": "15801.47",
        "investments": "197937.79",
        "other_assets": "300000.00",
        "debts": "811.10",
        "other_liabilities": "0.00",
        "net_worth": "512928.16"
      },
      {
        "month": "2032-09",
        "date": "2032-09-30",
        "cash": "15801.47",
        "investments": "200609.17",
        "other_assets": "300000.00",
        "debts": "694.14",
        "other_liabilities": "0.00",
        "net_worth": "515716.50"
      },
      {
        "month": "2032-10",
        "date": "2032-10-31",
        "cash": "15801.47",
        "investments": "203289.46",
        "other_assets": "300000.00",
        "debts": "576.74",
        "other_liabilities": "0.00",
        "net_worth": "518514.19"
      },
      {
        "month": "2032-11",
        "date": "2032-11-30",
        "cash": "15801.47",
        "investments": "205978.68",
        "other_assets": "300000.00",
        "debts": "458.90",
        "other_liabilities": "0.00",
        "net_worth": "521321.25"
      },
      {
        "month": "2032-12",
        "date": "2032-12-31",
        "cash": "15801.47",
        "investments": "208676.86",
        "other_assets": "300000.00",
        "debts": "340.62",
        "other_liabilities": "0.00",
        "net_worth": "524137.71"
      },
      {
        "month": "2033-01",
        "date": "2033-01-31",
        "cash": "15801.47",
        "investments": "211384.04",
        "other_assets": "300000.00",
        "debts": "221.90",
        "other_liabilities": "0.00",
        "net_worth": "526963.61"
      },
      {
        "month": "2033-02",
        "date": "2033-02-28",
        "cash": "15801.47",
        "investments": "214100.25",
        "other_assets": "300000.00",
        "debts": "102.73",
        "other_liabilities": "0.00",
        "net_worth": "529798.99"
      },
      {
        "month": "2033-03",
        "date": "2033-03-31",
        "cash": "15801.47",
        "investments": "216842.38",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "532643.85"
      },
      {
        "month": "2033-04",
        "date": "2033-04-30",
        "cash": "15801.47",
        "investments": "219696.78",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "535498.25"
      },
      {
        "month": "2033-05",
        "date": "2033-05-31",
        "cash": "15801.47",
        "investments": "222560.70",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "538362.17"
      },
      {
        "month": "2033-06",
        "date": "2033-06-30",
        "cash": "15801.47",
        "investments": "225434.15",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "541235.62"
      },
      {
        "month": "2033-07",
        "date": "2033-07-31",
        "cash": "15801.47",
        "investments": "228317.19",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "544118.66"
      },
      {
        "month": "2033-08",
        "date": "2033-08-31",
        "cash": "15801.47",
        "investments": "231209.84",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "547011.31"
      },
      {
        "month": "2033-09",
        "date": "2033-09-30",
        "cash": "15801.47",
        "investments": "234112.13",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "549913.60"
      },
      {
        "month": "2033-10",
        "date": "2033-10-31",
        "cash": "15801.47",
        "investments": "237024.09",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "552825.56"
      },
      {
        "month": "2033-11",
        "date": "2033-11-30",
        "cash": "15801.47",
        "investments": "239945.76",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "555747.23"
      },
      {
        "month": "2033-12",
        "date": "2033-12-31",
        "cash": "15801.47",
        "investments": "242877.17",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "558678.64"
      },
      {
        "month": "2034-01",
        "date": "2034-01-31",
        "cash": "15801.47",
        "investments": "245818.35",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "561619.82"
      },
      {
        "month": "2034-02",
        "date": "2034-02-28",
        "cash": "15801.47",
        "investments": "248769.34",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "564570.81"
      },
      {
        "month": "2034-03",
        "date": "2034-03-31",
        "cash": "15801.47",
        "investments": "251730.16",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "567531.63"
      },
      {
        "month": "2034-04",
        "date": "2034-04-30",
        "cash": "15801.47",
        "investments": "254700.85",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "570502.32"
      },
      {
        "month": "2034-05",
        "date": "2034-05-31",
        "cash": "15801.47",
        "investments": "257681.44",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "573482.91"
      },
      {
        "month": "2034-06",
        "date": "2034-06-30",
        "cash": "15801.47",
        "investments": "260671.97",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "576473.44"
      },
      {
        "month": "2034-07",
        "date": "2034-07-31",
        "cash": "15801.47",
        "investments": "263672.47",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "579473.94"
      },
      {
        "month": "2034-08",
        "date": "2034-08-31",
        "cash": "15801.47",
        "investments": "266682.96",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "582484.43"
      },
      {
        "month": "2034-09",
        "date": "2034-09-30",
        "cash": "15801.47",
        "investments": "269703.50",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "585504.97"
      },
      {
        "month": "2034-10",
        "date": "2034-10-31",
        "cash": "15801.47",
        "investments": "272734.10",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "588535.57"
      },
      {
        "month": "2034-11",
        "date": "2034-11-30",
        "cash": "15801.47",
        "investments": "275774.80",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "591576.27"
      },
      {
        "month": "2034-12",
        "date": "2034-12-31",
        "cash": "15801.47",
        "investments": "278825.64",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "594627.11"
      },
      {
        "month": "2035-01",
        "date": "2035-01-31",
        "cash": "15801.47",
        "investments": "281886.65",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "597688.12"
      },
      {
        "month": "2035-02",
        "date": "2035-02-28",
        "cash": "15801.47",
        "investments": "284957.86",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "600759.33"
      },
      {
        "month": "2035-03",
        "date": "2035-03-31",
        "cash": "15801.47",
        "investments": "288039.31",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "603840.78"
      },
      {
        "month": "2035-04",
        "date": "2035-04-30",
        "cash": "15801.47",
        "investments": "291131.03",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "606932.50"
      },
      {
        "month": "2035-05",
        "date": "2035-05-31",
        "cash": "15801.47",
        "investments": "294233.06",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "610034.53"
      },
      {
        "month": "2035-06",
        "date": "2035-06-30",
        "cash": "15801.47",
        "investments": "297345.43",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "613146.90"
      },
      {
        "month": "2035-07",
        "date": "2035-07-31",
        "cash": "15801.47",
        "investments": "300468.17",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "616269.64"
      },
      {
        "month": "2035-08",
        "date": "2035-08-31",
        "cash": "15801.47",
        "investments": "303601.32",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "619402.79"
      },
      {
        "month": "2035-09",
        "date": "2035-09-30",
        "cash": "15801.47",
        "investments": "306744.91",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "622546.38"
      },
      {
        "month": "2035-10",
        "date": "2035-10-31",
        "cash": "15801.47",
        "investments": "309898.99",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "625700.46"
      },
      {
        "month": "2035-11",
        "date": "2035-11-30",
        "cash": "15801.47",
        "investments": "313063.57",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "628865.04"
      },
      {
        "month": "2035-12",
        "date": "2035-12-31",
        "cash": "15801.47",
        "investments": "316238.71",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "632040.18"
      },
      {
        "month": "2036-01",
        "date": "2036-01-31",
        "cash": "15801.47",
        "investments": "319424.43",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "635225.90"
      },
      {
        "month": "2036-02",
        "date": "2036-02-29",
        "cash": "15801.47",
        "investments": "322620.77",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "638422.24"
      },
      {
        "month": "2036-03",
        "date": "2036-03-31",
        "cash": "15801.47",
        "investments": "325827.76",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "641629.23"
      },
      {
        "month": "2036-04",
        "date": "2036-04-30",
        "cash": "15801.47",
        "investments": "329045.44",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "644846.91"
      },
      {
        "month": "2036-05",
        "date": "2036-05-31",
        "cash": "15801.47",
        "investments": "332273.85",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "648075.32"
      },
      {
        "month": "2036-06",
        "date": "2036-06-30",
        "cash": "15801.47",
        "investments": "335513.02",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "651314.49"
      },
      {
        "month": "2036-07",
        "date": "2036-07-31",
        "cash": "15801.47",
        "investments": "338762.99",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "654564.46"
      },
      {
        "month": "2036-08",
        "date": "2036-08-31",
        "cash": "15801.47",
        "investments": "342023.78",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "657825.25"
      },
      {
        "month": "2036-09",
        "date": "2036-09-30",
        "cash": "15801.47",
        "investments": "345295.45",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "661096.92"
      },
      {
        "month": "2036-10",
        "date": "2036-10-31",
        "cash": "15801.47",
        "investments": "348578.03",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "664379.50"
      },
      {
        "month": "2036-11",
        "date": "2036-11-30",
        "cash": "15801.47",
        "investments": "351871.55",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "667673.02"
      },
      {
        "month": "2036-12",
        "date": "2036-12-31",
        "cash": "15801.47",
        "investments": "355176.04",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "670977.51"
      },
      {
        "month": "2037-01",
        "date": "2037-01-31",
        "cash": "15801.47",
        "investments": "358491.55",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "674293.02"
      },
      {
        "month": "2037-02",
        "date": "2037-02-28",
        "cash": "15801.47",
        "investments": "361818.11",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "677619.58"
      },
      {
        "month": "2037-03",
        "date": "2037-03-31",
        "cash": "15801.47",
        "investments": "365155.76",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "680957.23"
      },
      {
        "month": "2037-04",
        "date": "2037-04-30",
        "cash": "15801.47",
        "investments": "368504.54",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "684306.01"
      },
      {
        "month": "2037-05",
        "date": "2037-05-31",
        "cash": "15801.47",
        "investments": "371864.48",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "687665.95"
      },
      {
        "month": "2037-06",
        "date": "2037-06-30",
        "cash": "15801.47",
        "investments": "375235.62",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "691037.09"
      },
      {
        "month": "2037-07",
        "date": "2037-07-31",
        "cash": "15801.47",
        "investments": "378617.99",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "694419.46"
      },
      {
        "month": "2037-08",
        "date": "2037-08-31",
        "cash": "15801.47",
        "investments": "382011.64",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "697813.11"
      },
      {
        "month": "2037-09",
        "date": "2037-09-30",
        "cash": "15801.47",
        "investments": "385416.60",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "701218.07"
      },
      {
        "month": "2037-10",
        "date": "2037-10-31",
        "cash": "15801.47",
        "investments": "388832.92",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "704634.39"
      },
      {
        "month": "2037-11",
        "date": "2037-11-30",
        "cash": "15801.47",
        "investments": "392260.62",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "708062.09"
      },
      {
        "month": "2037-12",
        "date": "2037-12-31",
        "cash": "15801.47",
        "investments": "395699.74",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "711501.21"
      },
      {
        "month": "2038-01",
        "date": "2038-01-31",
        "cash": "15801.47",
        "investments": "399150.33",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "714951.80"
      },
      {
        "month": "2038-02",
        "date": "2038-02-28",
        "cash": "15801.47",
        "investments": "402612.42",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "718413.89"
      },
      {
        "month": "2038-03",
        "date": "2038-03-31",
        "cash": "15801.47",
        "investments": "406086.05",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "721887.52"
      },
      {
        "month": "2038-04",
        "date": "2038-04-30",
        "cash": "15801.47",
        "investments": "409571.26",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "725372.73"
      },
      {
        "month": "2038-05",
        "date": "2038-05-31",
        "cash": "15801.47",
        "investments": "413068.09",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "728869.56"
      },
      {
        "month": "2038-06",
        "date": "2038-06-30",
        "cash": "15801.47",
        "investments": "416576.57",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "732378.04"
      },
      {
        "month": "2038-07",
        "date": "2038-07-31",
        "cash": "15801.47",
        "investments": "420096.75",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "735898.22"
      },
      {
        "month": "2038-08",
        "date": "2038-08-31",
        "cash": "15801.47",
        "investments": "423628.66",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "739430.13"
      },
      {
        "month": "2038-09",
        "date": "2038-09-30",
        "cash": "15801.47",
        "investments": "427172.35",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "742973.82"
      },
      {
        "month": "2038-10",
        "date": "2038-10-31",
        "cash": "15801.47",
        "investments": "430727.85",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "746529.32"
      },
      {
        "month": "2038-11",
        "date": "2038-11-30",
        "cash": "15801.47",
        "investments": "434295.20",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "750096.67"
      },
      {
        "month": "2038-12",
        "date": "2038-12-31",
        "cash": "15801.47",
        "investments": "437874.44",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "753675.91"
      },
      {
        "month": "2039-01",
        "date": "2039-01-31",
        "cash": "15801.47",
        "investments": "441465.61",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "757267.08"
      },
      {
        "month": "2039-02",
        "date": "2039-02-28",
        "cash": "15801.47",
        "investments": "445068.75",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "760870.22"
      },
      {
        "month": "2039-03",
        "date": "2039-03-31",
        "cash": "15801.47",
        "investments": "448683.90",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "764485.37"
      },
      {
        "month": "2039-04",
        "date": "2039-04-30",
        "cash": "15801.47",
        "investments": "452311.11",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "768112.58"
      },
      {
        "month": "2039-05",
        "date": "2039-05-31",
        "cash": "15801.47",
        "investments": "455950.40",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "771751.87"
      },
      {
        "month": "2039-06",
        "date": "2039-06-30",
        "cash": "15801.47",
        "investments": "459601.83",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "775403.30"
      },
      {
        "month": "2039-07",
        "date": "2039-07-31",
        "cash": "15801.47",
        "investments": "463265.42",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "779066.89"
      },
      {
        "month": "2039-08",
        "date": "2039-08-31",
        "cash": "15801.47",
        "investments": "466941.23",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "782742.70"
      },
      {
        "month": "2039-09",
        "date": "2039-09-30",
        "cash": "15801.47",
        "investments": "470629.29",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "786430.76"
      },
      {
        "month": "2039-10",
        "date": "2039-10-31",
        "cash": "15801.47",
        "investments": "474329.64",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "790131.11"
      },
      {
        "month": "2039-11",
        "date": "2039-11-30",
        "cash": "15801.47",
        "investments": "478042.33",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "793843.80"
      },
      {
        "month": "2039-12",
        "date": "2039-12-31",
        "cash": "15801.47",
        "investments": "481767.40",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "797568.87"
      },
      {
        "month": "2040-01",
        "date": "2040-01-31",
        "cash": "15801.47",
        "investments": "485504.88",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "801306.35"
      },
      {
        "month": "2040-02",
        "date": "2040-02-29",
        "cash": "15801.47",
        "investments": "489254.82",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "805056.29"
      },
      {
        "month": "2040-03",
        "date": "2040-03-31",
        "cash": "15801.47",
        "investments": "493017.26",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "808818.73"
      },
      {
        "month": "2040-04",
        "date": "2040-04-30",
        "cash": "15801.47",
        "investments": "496792.24",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "812593.71"
      },
      {
        "month": "2040-05",
        "date": "2040-05-31",
        "cash": "15801.47",
        "investments": "500579.80",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "816381.27"
      },
      {
        "month": "2040-06",
        "date": "2040-06-30",
        "cash": "15801.47",
        "investments": "504379.99",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "820181.46"
      },
      {
        "month": "2040-07",
        "date": "2040-07-31",
        "cash": "15801.47",
        "investments": "508192.85",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "823994.32"
      },
      {
        "month": "2040-08",
        "date": "2040-08-31",
        "cash": "15801.47",
        "investments": "512018.42",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "827819.89"
      },
      {
        "month": "2040-09",
        "date": "2040-09-30",
        "cash": "15801.47",
        "investments": "515856.73",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "831658.20"
      },
      {
        "month": "2040-10",
        "date": "2040-10-31",
        "cash": "15801.47",
        "investments": "519707.85",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "835509.32"
      },
      {
        "month": "2040-11",
        "date": "2040-11-30",
        "cash": "15801.47",
        "investments": "523571.80",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "839373.27"
      },
      {
        "month": "2040-12",
        "date": "2040-12-31",
        "cash": "15801.47",
        "investments": "527448.62",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "843250.09"
      },
      {
        "month": "2041-01",
        "date": "2041-01-31",
        "cash": "15801.47",
        "investments": "531338.38",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "847139.85"
      },
      {
        "month": "2041-02",
        "date": "2041-02-28",
        "cash": "15801.47",
        "investments": "535241.09",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "851042.56"
      },
      {
        "month": "2041-03",
        "date": "2041-03-31",
        "cash": "15801.47",
        "investments": "539156.82",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "854958.29"
      },
      {
        "month": "2041-04",
        "date": "2041-04-30",
        "cash": "15801.47",
        "investments": "543085.60",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "858887.07"
      },
      {
        "month": "2041-05",
        "date": "2041-05-31",
        "cash": "15801.47",
        "investments": "547027.48",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "862828.95"
      },
      {
        "month": "2041-06",
        "date": "2041-06-30",
        "cash": "15801.47",
        "investments": "550982.49",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "866783.96"
      },
      {
        "month": "2041-07",
        "date": "2041-07-31",
        "cash": "15801.47",
        "investments": "554950.69",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "870752.16"
      },
      {
        "month": "2041-08",
        "date": "2041-08-31",
        "cash": "15801.47",
        "investments": "558932.12",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "874733.59"
      },
      {
        "month": "2041-09",
        "date": "2041-09-30",
        "cash": "15801.47",
        "investments": "562926.81",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "878728.28"
      },
      {
        "month": "2041-10",
        "date": "2041-10-31",
        "cash": "15801.47",
        "investments": "566934.83",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "882736.30"
      },
      {
        "month": "2041-11",
        "date": "2041-11-30",
        "cash": "15801.47",
        "investments": "570956.20",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "886757.67"
      },
      {
        "month": "2041-12",
        "date": "2041-12-31",
        "cash": "15801.47",
        "investments": "574990.98",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "890792.45"
      },
      {
        "month": "2042-01",
        "date": "2042-01-31",
        "cash": "15801.47",
        "investments": "579039.20",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "894840.67"
      },
      {
        "month": "2042-02",
        "date": "2042-02-28",
        "cash": "15801.47",
        "investments": "583100.92",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "898902.39"
      },
      {
        "month": "2042-03",
        "date": "2042-03-31",
        "cash": "15801.47",
        "investments": "587176.18",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "902977.65"
      },
      {
        "month": "2042-04",
        "date": "2042-04-30",
        "cash": "15801.47",
        "investments": "591265.03",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "907066.50"
      },
      {
        "month": "2042-05",
        "date": "2042-05-31",
        "cash": "15801.47",
        "investments": "595367.50",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "911168.97"
      },
      {
        "month": "2042-06",
        "date": "2042-06-30",
        "cash": "15801.47",
        "investments": "599483.65",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "915285.12"
      },
      {
        "month": "2042-07",
        "date": "2042-07-31",
        "cash": "15801.47",
        "investments": "603613.52",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "919414.99"
      },
      {
        "month": "2042-08",
        "date": "2042-08-31",
        "cash": "15801.47",
        "investments": "607757.15",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "923558.62"
      },
      {
        "month": "2042-09",
        "date": "2042-09-30",
        "cash": "15801.47",
        "investments": "611914.60",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "927716.07"
      },
      {
        "month": "2042-10",
        "date": "2042-10-31",
        "cash": "15801.47",
        "investments": "616085.90",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "931887.37"
      },
      {
        "month": "2042-11",
        "date": "2042-11-30",
        "cash": "15801.47",
        "investments": "620271.11",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "936072.58"
      },
      {
        "month": "2042-12",
        "date": "2042-12-31",
        "cash": "15801.47",
        "investments": "624470.27",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "940271.74"
      },
      {
        "month": "2043-01",
        "date": "2043-01-31",
        "cash": "15801.47",
        "investments": "628683.43",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "944484.90"
      },
      {
        "month": "2043-02",
        "date": "2043-02-28",
        "cash": "15801.47",
        "investments": "632910.63",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "948712.10"
      },
      {
        "month": "2043-03",
        "date": "2043-03-31",
        "cash": "15801.47",
        "investments": "637151.93",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "952953.40"
      },
      {
        "month": "2043-04",
        "date": "2043-04-30",
        "cash": "15801.47",
        "investments": "641407.36",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "957208.83"
      },
      {
        "month": "2043-05",
        "date": "2043-05-31",
        "cash": "15801.47",
        "investments": "645676.97",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "961478.44"
      },
      {
        "month": "2043-06",
        "date": "2043-06-30",
        "cash": "15801.47",
        "investments": "649960.82",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "965762.29"
      },
      {
        "month": "2043-07",
        "date": "2043-07-31",
        "cash": "15801.47",
        "investments": "654258.94",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "970060.41"
      },
      {
        "month": "2043-08",
        "date": "2043-08-31",
        "cash": "15801.47",
        "investments": "658571.40",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "974372.87"
      },
      {
        "month": "2043-09",
        "date": "2043-09-30",
        "cash": "15801.47",
        "investments": "662898.22",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "978699.69"
      },
      {
        "month": "2043-10",
        "date": "2043-10-31",
        "cash": "15801.47",
        "investments": "667239.47",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "983040.94"
      },
      {
        "month": "2043-11",
        "date": "2043-11-30",
        "cash": "15801.47",
        "investments": "671595.20",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "987396.67"
      },
      {
        "month": "2043-12",
        "date": "2043-12-31",
        "cash": "15801.47",
        "investments": "675965.44",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "991766.91"
      },
      {
        "month": "2044-01",
        "date": "2044-01-31",
        "cash": "15801.47",
        "investments": "680350.24",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "996151.71"
      },
      {
        "month": "2044-02",
        "date": "2044-02-29",
        "cash": "15801.47",
        "investments": "684749.67",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1000551.14"
      },
      {
        "month": "2044-03",
        "date": "2044-03-31",
        "cash": "15801.47",
        "investments": "689163.76",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1004965.23"
      },
      {
        "month": "2044-04",
        "date": "2044-04-30",
        "cash": "15801.47",
        "investments": "693592.56",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1009394.03"
      },
      {
        "month": "2044-05",
        "date": "2044-05-31",
        "cash": "15801.47",
        "investments": "698036.13",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1013837.60"
      },
      {
        "month": "2044-06",
        "date": "2044-06-30",
        "cash": "15801.47",
        "investments": "702494.50",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1018295.97"
      },
      {
        "month": "2044-07",
        "date": "2044-07-31",
        "cash": "15801.47",
        "investments": "706967.74",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1022769.21"
      },
      {
        "month": "2044-08",
        "date": "2044-08-31",
        "cash": "15801.47",
        "investments": "711455.89",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1027257.36"
      },
      {
        "month": "2044-09",
        "date": "2044-09-30",
        "cash": "15801.47",
        "investments": "715959.00",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1031760.47"
      },
      {
        "month": "2044-10",
        "date": "2044-10-31",
        "cash": "15801.47",
        "investments": "720477.12",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1036278.59"
      },
      {
        "month": "2044-11",
        "date": "2044-11-30",
        "cash": "15801.47",
        "investments": "725010.30",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1040811.77"
      },
      {
        "month": "2044-12",
        "date": "2044-12-31",
        "cash": "15801.47",
        "investments": "729558.59",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1045360.06"
      },
      {
        "month": "2045-01",
        "date": "2045-01-31",
        "cash": "15801.47",
        "investments": "734122.04",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1049923.51"
      },
      {
        "month": "2045-02",
        "date": "2045-02-28",
        "cash": "15801.47",
        "investments": "738700.71",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1054502.18"
      },
      {
        "month": "2045-03",
        "date": "2045-03-31",
        "cash": "15801.47",
        "investments": "743294.63",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1059096.10"
      },
      {
        "month": "2045-04",
        "date": "2045-04-30",
        "cash": "15801.47",
        "investments": "747903.87",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1063705.34"
      },
      {
        "month": "2045-05",
        "date": "2045-05-31",
        "cash": "15801.47",
        "investments": "752528.47",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1068329.94"
      },
      {
        "month": "2045-06",
        "date": "2045-06-30",
        "cash": "15801.47",
        "investments": "757168.49",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1072969.96"
      },
      {
        "month": "2045-07",
        "date": "2045-07-31",
        "cash": "15801.47",
        "investments": "761823.98",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1077625.45"
      },
      {
        "month": "2045-08",
        "date": "2045-08-31",
        "cash": "15801.47",
        "investments": "766494.98",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1082296.45"
      },
      {
        "month": "2045-09",
        "date": "2045-09-30",
        "cash": "15801.47",
        "investments": "771181.55",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1086983.02"
      },
      {
        "month": "2045-10",
        "date": "2045-10-31",
        "cash": "15801.47",
        "investments": "775883.75",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1091685.22"
      },
      {
        "month": "2045-11",
        "date": "2045-11-30",
        "cash": "15801.47",
        "investments": "780601.62",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1096403.09"
      },
      {
        "month": "2045-12",
        "date": "2045-12-31",
        "cash": "15801.47",
        "investments": "785335.21",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1101136.68"
      },
      {
        "month": "2046-01",
        "date": "2046-01-31",
        "cash": "15801.47",
        "investments": "790084.59",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1105886.06"
      },
      {
        "month": "2046-02",
        "date": "2046-02-28",
        "cash": "15801.47",
        "investments": "794849.79",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1110651.26"
      },
      {
        "month": "2046-03",
        "date": "2046-03-31",
        "cash": "15801.47",
        "investments": "799630.88",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1115432.35"
      },
      {
        "month": "2046-04",
        "date": "2046-04-30",
        "cash": "15801.47",
        "investments": "804427.91",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1120229.38"
      },
      {
        "month": "2046-05",
        "date": "2046-05-31",
        "cash": "15801.47",
        "investments": "809240.92",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1125042.39"
      },
      {
        "month": "2046-06",
        "date": "2046-06-30",
        "cash": "15801.47",
        "investments": "814069.98",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1129871.45"
      },
      {
        "month": "2046-07",
        "date": "2046-07-31",
        "cash": "15801.47",
        "investments": "818915.14",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1134716.61"
      },
      {
        "month": "2046-08",
        "date": "2046-08-31",
        "cash": "15801.47",
        "investments": "823776.45",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1139577.92"
      },
      {
        "month": "2046-09",
        "date": "2046-09-30",
        "cash": "15801.47",
        "investments": "828653.96",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1144455.43"
      },
      {
        "month": "2046-10",
        "date": "2046-10-31",
        "cash": "15801.47",
        "investments": "833547.73",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1149349.20"
      },
      {
        "month": "2046-11",
        "date": "2046-11-30",
        "cash": "15801.47",
        "investments": "838457.81",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1154259.28"
      },
      {
        "month": "2046-12",
        "date": "2046-12-31",
        "cash": "15801.47",
        "investments": "843384.26",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1159185.73"
      },
      {
        "month": "2047-01",
        "date": "2047-01-31",
        "cash": "15801.47",
        "investments": "848327.13",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1164128.60"
      },
      {
        "month": "2047-02",
        "date": "2047-02-28",
        "cash": "15801.47",
        "investments": "853286.48",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1169087.95"
      },
      {
        "month": "2047-03",
        "date": "2047-03-31",
        "cash": "15801.47",
        "investments": "858262.36",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1174063.83"
      },
      {
        "month": "2047-04",
        "date": "2047-04-30",
        "cash": "15801.47",
        "investments": "863254.82",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1179056.29"
      },
      {
        "month": "2047-05",
        "date": "2047-05-31",
        "cash": "15801.47",
        "investments": "868263.93",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1184065.40"
      },
      {
        "month": "2047-06",
        "date": "2047-06-30",
        "cash": "15801.47",
        "investments": "873289.73",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1189091.20"
      },
      {
        "month": "2047-07",
        "date": "2047-07-31",
        "cash": "15801.47",
        "investments": "878332.29",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1194133.76"
      },
      {
        "month": "2047-08",
        "date": "2047-08-31",
        "cash": "15801.47",
        "investments": "883391.65",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1199193.12"
      },
      {
        "month": "2047-09",
        "date": "2047-09-30",
        "cash": "15801.47",
        "investments": "888467.88",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1204269.35"
      },
      {
        "month": "2047-10",
        "date": "2047-10-31",
        "cash": "15801.47",
        "investments": "893561.03",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1209362.50"
      },
      {
        "month": "2047-11",
        "date": "2047-11-30",
        "cash": "15801.47",
        "investments": "898671.16",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1214472.63"
      },
      {
        "month": "2047-12",
        "date": "2047-12-31",
        "cash": "15801.47",
        "investments": "903798.32",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1219599.79"
      },
      {
        "month": "2048-01",
        "date": "2048-01-31",
        "cash": "15801.47",
        "investments": "908942.57",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1224744.04"
      },
      {
        "month": "2048-02",
        "date": "2048-02-29",
        "cash": "15801.47",
        "investments": "914103.97",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1229905.44"
      },
      {
        "month": "2048-03",
        "date": "2048-03-31",
        "cash": "15801.47",
        "investments": "919282.57",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1235084.04"
      },
      {
        "month": "2048-04",
        "date": "2048-04-30",
        "cash": "15801.47",
        "investments": "924478.43",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1240279.90"
      },
      {
        "month": "2048-05",
        "date": "2048-05-31",
        "cash": "15801.47",
        "investments": "929691.62",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1245493.09"
      },
      {
        "month": "2048-06",
        "date": "2048-06-30",
        "cash": "15801.47",
        "investments": "934922.18",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1250723.65"
      },
      {
        "month": "2048-07",
        "date": "2048-07-31",
        "cash": "15801.47",
        "investments": "940170.18",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1255971.65"
      },
      {
        "month": "2048-08",
        "date": "2048-08-31",
        "cash": "15801.47",
        "investments": "945435.67",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1261237.14"
      },
      {
        "month": "2048-09",
        "date": "2048-09-30",
        "cash": "15801.47",
        "investments": "950718.71",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1266520.18"
      },
      {
        "month": "2048-10",
        "date": "2048-10-31",
        "cash": "15801.47",
        "investments": "956019.36",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1271820.83"
      },
      {
        "month": "2048-11",
        "date": "2048-11-30",
        "cash": "15801.47",
        "investments": "961337.69",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1277139.16"
      },
      {
        "month": "2048-12",
        "date": "2048-12-31",
        "cash": "15801.47",
        "investments": "966673.73",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1282475.20"
      },
      {
        "month": "2049-01",
        "date": "2049-01-31",
        "cash": "15801.47",
        "investments": "972027.57",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1287829.04"
      },
      {
        "month": "2049-02",
        "date": "2049-02-28",
        "cash": "15801.47",
        "investments": "977399.25",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1293200.72"
      },
      {
        "month": "2049-03",
        "date": "2049-03-31",
        "cash": "15801.47",
        "investments": "982788.84",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1298590.31"
      },
      {
        "month": "2049-04",
        "date": "2049-04-30",
        "cash": "15801.47",
        "investments": "988196.39",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1303997.86"
      },
      {
        "month": "2049-05",
        "date": "2049-05-31",
        "cash": "15801.47",
        "investments": "993621.97",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1309423.44"
      },
      {
        "month": "2049-06",
        "date": "2049-06-30",
        "cash": "15801.47",
        "investments": "999065.63",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1314867.10"
      },
      {
        "month": "2049-07",
        "date": "2049-07-31",
        "cash": "15801.47",
        "investments": "1004527.44",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1320328.91"
      },
      {
        "month": "2049-08",
        "date": "2049-08-31",
        "cash": "15801.47",
        "investments": "1010007.46",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1325808.93"
      },
      {
        "month": "2049-09",
        "date": "2049-09-30",
        "cash": "15801.47",
        "investments": "1015505.74",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1331307.21"
      },
      {
        "month": "2049-10",
        "date": "2049-10-31",
        "cash": "15801.47",
        "investments": "1021022.35",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1336823.82"
      },
      {
        "month": "2049-11",
        "date": "2049-11-30",
        "cash": "15801.47",
        "investments": "1026557.35",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1342358.82"
      },
      {
        "month": "2049-12",
        "date": "2049-12-31",
        "cash": "15801.47",
        "investments": "1032110.79",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1347912.26"
      },
      {
        "month": "2050-01",
        "date": "2050-01-31",
        "cash": "15801.47",
        "investments": "1037682.75",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1353484.22"
      },
      {
        "month": "2050-02",
        "date": "2050-02-28",
        "cash": "15801.47",
        "investments": "1043273.29",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1359074.76"
      },
      {
        "month": "2050-03",
        "date": "2050-03-31",
        "cash": "15801.47",
        "investments": "1048882.45",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1364683.92"
      },
      {
        "month": "2050-04",
        "date": "2050-04-30",
        "cash": "15801.47",
        "investments": "1054510.32",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1370311.79"
      },
      {
        "month": "2050-05",
        "date": "2050-05-31",
        "cash": "15801.47",
        "investments": "1060156.94",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1375958.41"
      },
      {
        "month": "2050-06",
        "date": "2050-06-30",
        "cash": "15801.47",
        "investments": "1065822.39",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1381623.86"
      },
      {
        "month": "2050-07",
        "date": "2050-07-31",
        "cash": "15801.47",
        "investments": "1071506.72",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1387308.19"
      },
      {
        "month": "2050-08",
        "date": "2050-08-31",
        "cash": "15801.47",
        "investments": "1077210.00",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1393011.47"
      },
      {
        "month": "2050-09",
        "date": "2050-09-30",
        "cash": "15801.47",
        "investments": "1082932.29",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1398733.76"
      },
      {
        "month": "2050-10",
        "date": "2050-10-31",
        "cash": "15801.47",
        "investments": "1088673.65",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1404475.12"
      },
      {
        "month": "2050-11",
        "date": "2050-11-30",
        "cash": "15801.47",
        "investments": "1094434.16",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1410235.63"
      },
      {
        "month": "2050-12",
        "date": "2050-12-31",
        "cash": "15801.47",
        "investments": "1100213.86",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1416015.33"
      },
      {
        "month": "2051-01",
        "date": "2051-01-31",
        "cash": "15801.47",
        "investments": "1106012.83",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1421814.30"
      },
      {
        "month": "2051-02",
        "date": "2051-02-28",
        "cash": "15801.47",
        "investments": "1111831.13",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1427632.60"
      },
      {
        "month": "2051-03",
        "date": "2051-03-31",
        "cash": "15801.47",
        "investments": "1117668.82",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1433470.29"
      },
      {
        "month": "2051-04",
        "date": "2051-04-30",
        "cash": "15801.47",
        "investments": "1123525.97",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1439327.44"
      },
      {
        "month": "2051-05",
        "date": "2051-05-31",
        "cash": "15801.47",
        "investments": "1129402.65",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1445204.12"
      },
      {
        "month": "2051-06",
        "date": "2051-06-30",
        "cash": "15801.47",
        "investments": "1135298.92",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1451100.39"
      },
      {
        "month": "2051-07",
        "date": "2051-07-31",
        "cash": "15801.47",
        "investments": "1141214.84",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1457016.31"
      },
      {
        "month": "2051-08",
        "date": "2051-08-31",
        "cash": "15801.47",
        "investments": "1147150.48",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1462951.95"
      },
      {
        "month": "2051-09",
        "date": "2051-09-30",
        "cash": "15801.47",
        "investments": "1153105.90",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1468907.37"
      },
      {
        "month": "2051-10",
        "date": "2051-10-31",
        "cash": "15801.47",
        "investments": "1159081.18",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1474882.65"
      },
      {
        "month": "2051-11",
        "date": "2051-11-30",
        "cash": "15801.47",
        "investments": "1165076.37",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1480877.84"
      },
      {
        "month": "2051-12",
        "date": "2051-12-31",
        "cash": "15801.47",
        "investments": "1171091.55",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1486893.02"
      },
      {
        "month": "2052-01",
        "date": "2052-01-31",
        "cash": "15801.47",
        "investments": "1177126.78",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1492928.25"
      },
      {
        "month": "2052-02",
        "date": "2052-02-29",
        "cash": "15801.47",
        "investments": "1183182.12",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1498983.59"
      },
      {
        "month": "2052-03",
        "date": "2052-03-31",
        "cash": "15801.47",
        "investments": "1189257.65",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1505059.12"
      },
      {
        "month": "2052-04",
        "date": "2052-04-30",
        "cash": "15801.47",
        "investments": "1195353.44",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1511154.91"
      },
      {
        "month": "2052-05",
        "date": "2052-05-31",
        "cash": "15801.47",
        "investments": "1201469.54",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1517271.01"
      },
      {
        "month": "2052-06",
        "date": "2052-06-30",
        "cash": "15801.47",
        "investments": "1207606.03",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1523407.50"
      },
      {
        "month": "2052-07",
        "date": "2052-07-31",
        "cash": "15801.47",
        "investments": "1213762.97",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1529564.44"
      },
      {
        "month": "2052-08",
        "date": "2052-08-31",
        "cash": "15801.47",
        "investments": "1219940.44",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1535741.91"
      },
      {
        "month": "2052-09",
        "date": "2052-09-30",
        "cash": "15801.47",
        "investments": "1226138.49",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1541939.96"
      },
      {
        "month": "2052-10",
        "date": "2052-10-31",
        "cash": "15801.47",
        "investments": "1232357.21",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1548158.68"
      },
      {
        "month": "2052-11",
        "date": "2052-11-30",
        "cash": "15801.47",
        "investments": "1238596.66",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1554398.13"
      },
      {
        "month": "2052-12",
        "date": "2052-12-31",
        "cash": "15801.47",
        "investments": "1244856.91",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1560658.38"
      },
      {
        "month": "2053-01",
        "date": "2053-01-31",
        "cash": "15801.47",
        "investments": "1251138.02",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1566939.49"
      },
      {
        "month": "2053-02",
        "date": "2053-02-28",
        "cash": "15801.47",
        "investments": "1257440.07",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1573241.54"
      },
      {
        "month": "2053-03",
        "date": "2053-03-31",
        "cash": "15801.47",
        "investments": "1263763.13",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1579564.60"
      },
      {
        "month": "2053-04",
        "date": "2053-04-30",
        "cash": "15801.47",
        "investments": "1270107.26",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1585908.73"
      },
      {
        "month": "2053-05",
        "date": "2053-05-31",
        "cash": "15801.47",
        "investments": "1276472.54",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1592274.01"
      },
      {
        "month": "2053-06",
        "date": "2053-06-30",
        "cash": "15801.47",
        "investments": "1282859.04",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1598660.51"
      },
      {
        "month": "2053-07",
        "date": "2053-07-31",
        "cash": "15801.47",
        "investments": "1289266.83",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1605068.30"
      },
      {
        "month": "2053-08",
        "date": "2053-08-31",
        "cash": "15801.47",
        "investments": "1295695.97",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1611497.44"
      },
      {
        "month": "2053-09",
        "date": "2053-09-30",
        "cash": "15801.47",
        "investments": "1302146.55",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1617948.02"
      },
      {
        "month": "2053-10",
        "date": "2053-10-31",
        "cash": "15801.47",
        "investments": "1308618.63",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1624420.10"
      },
      {
        "month": "2053-11",
        "date": "2053-11-30",
        "cash": "15801.47",
        "investments": "1315112.28",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1630913.75"
      },
      {
        "month": "2053-12",
        "date": "2053-12-31",
        "cash": "15801.47",
        "investments": "1321627.58",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1637429.05"
      },
      {
        "month": "2054-01",
        "date": "2054-01-31",
        "cash": "15801.47",
        "investments": "1328164.59",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1643966.06"
      },
      {
        "month": "2054-02",
        "date": "2054-02-28",
        "cash": "15801.47",
        "investments": "1334723.40",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1650524.87"
      },
      {
        "month": "2054-03",
        "date": "2054-03-31",
        "cash": "15801.47",
        "investments": "1341304.06",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1657105.53"
      },
      {
        "month": "2054-04",
        "date": "2054-04-30",
        "cash": "15801.47",
        "investments": "1347906.67",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1663708.14"
      },
      {
        "month": "2054-05",
        "date": "2054-05-31",
        "cash": "15801.47",
        "investments": "1354531.28",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1670332.75"
      },
      {
        "month": "2054-06",
        "date": "2054-06-30",
        "cash": "15801.47",
        "investments": "1361177.97",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1676979.44"
      },
      {
        "month": "2054-07",
        "date": "2054-07-31",
        "cash": "15801.47",
        "investments": "1367846.82",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1683648.29"
      },
      {
        "month": "2054-08",
        "date": "2054-08-31",
        "cash": "15801.47",
        "investments": "1374537.90",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1690339.37"
      },
      {
        "month": "2054-09",
        "date": "2054-09-30",
        "cash": "15801.47",
        "investments": "1381251.29",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1697052.76"
      },
      {
        "month": "2054-10",
        "date": "2054-10-31",
        "cash": "15801.47",
        "investments": "1387987.05",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1703788.52"
      },
      {
        "month": "2054-11",
        "date": "2054-11-30",
        "cash": "15801.47",
        "investments": "1394745.26",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1710546.73"
      },
      {
        "month": "2054-12",
        "date": "2054-12-31",
        "cash": "15801.47",
        "investments": "1401526.00",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1717327.47"
      },
      {
        "month": "2055-01",
        "date": "2055-01-31",
        "cash": "15801.47",
        "investments": "1408329.35",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1724130.82"
      },
      {
        "month": "2055-02",
        "date": "2055-02-28",
        "cash": "15801.47",
        "investments": "1415155.37",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1730956.84"
      },
      {
        "month": "2055-03",
        "date": "2055-03-31",
        "cash": "15801.47",
        "investments": "1422004.14",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1737805.61"
      },
      {
        "month": "2055-04",
        "date": "2055-04-30",
        "cash": "15801.47",
        "investments": "1428875.75",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1744677.22"
      },
      {
        "month": "2055-05",
        "date": "2055-05-31",
        "cash": "15801.47",
        "investments": "1435770.25",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1751571.72"
      },
      {
        "month": "2055-06",
        "date": "2055-06-30",
        "cash": "15801.47",
        "investments": "1442687.75",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1758489.22"
      },
      {
        "month": "2055-07",
        "date": "2055-07-31",
        "cash": "15801.47",
        "investments": "1449628.29",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1765429.76"
      },
      {
        "month": "2055-08",
        "date": "2055-08-31",
        "cash": "15801.47",
        "investments": "1456591.98",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1772393.45"
      },
      {
        "month": "2055-09",
        "date": "2055-09-30",
        "cash": "15801.47",
        "investments": "1463578.88",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1779380.35"
      },
      {
        "month": "2055-10",
        "date": "2055-10-31",
        "cash": "15801.47",
        "investments": "1470589.06",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1786390.53"
      },
      {
        "month": "2055-11",
        "date": "2055-11-30",
        "cash": "15801.47",
        "investments": "1477622.62",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1793424.09"
      },
      {
        "month": "2055-12",
        "date": "2055-12-31",
        "cash": "15801.47",
        "investments": "1484679.61",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1800481.08"
      },
      {
        "month": "2056-01",
        "date": "2056-01-31",
        "cash": "15801.47",
        "investments": "1491760.14",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1807561.61"
      },
      {
        "month": "2056-02",
        "date": "2056-02-29",
        "cash": "15801.47",
        "investments": "1498864.26",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1814665.73"
      },
      {
        "month": "2056-03",
        "date": "2056-03-31",
        "cash": "15801.47",
        "investments": "1505992.06",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1821793.53"
      },
      {
        "month": "2056-04",
        "date": "2056-04-30",
        "cash": "15801.47",
        "investments": "1513143.63",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1828945.10"
      },
      {
        "month": "2056-05",
        "date": "2056-05-31",
        "cash": "15801.47",
        "investments": "1520319.03",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1836120.50"
      },
      {
        "month": "2056-06",
        "date": "2056-06-30",
        "cash": "15801.47",
        "investments": "1527518.35",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1843319.82"
      },
      {
        "month": "2056-07",
        "date": "2056-07-31",
        "cash": "15801.47",
        "investments": "1534741.67",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1850543.14"
      },
      {
        "month": "2056-08",
        "date": "2056-08-31",
        "cash": "15801.47",
        "investments": "1541989.06",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1857790.53"
      },
      {
        "month": "2056-09",
        "date": "2056-09-30",
        "cash": "15801.47",
        "investments": "1549260.62",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1865062.09"
      },
      {
        "month": "2056-10",
        "date": "2056-10-31",
        "cash": "15801.47",
        "investments": "1556556.41",
        "other_assets": "300000.00",
        "debts": "0.00",
        "other_liabilities": "0.00",
        "net_worth": "1872357.88"
      }
    ]
  },
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
    "nominal_returns": null,
    "cma": null
  },
  "placeholders": [
    "real_return",
    "safe_withdrawal_rate",
    "surplus_invested",
    "drawdown_horizon",
    "inflation"
  ],
  "rule_sets": [],
  "fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
  "notes": []
};

export const ACCOUNTS: Account[] = [
  {
    "id": "chk",
    "code": "1000",
    "name": "Checking",
    "type": "asset",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": "cash",
    "equity_role": null
  },
  {
    "id": "sav",
    "code": "1100",
    "name": "Savings",
    "type": "asset",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": "cash",
    "equity_role": null
  },
  {
    "id": "usd",
    "code": "1200",
    "name": "Dollar account",
    "type": "asset",
    "currency": "USD",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": "cash",
    "equity_role": null
  },
  {
    "id": "brk",
    "code": "1300",
    "name": "Brokerage",
    "type": "asset",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": "investment",
    "equity_role": null
  },
  {
    "id": "pen",
    "code": "1400",
    "name": "Pension fund",
    "type": "asset",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": "investment",
    "equity_role": null
  },
  {
    "id": "flat",
    "code": "1500",
    "name": "Flat",
    "type": "asset",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": "other",
    "equity_role": null
  },
  {
    "id": "card",
    "code": "2000",
    "name": "Credit card",
    "type": "liability",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": null,
    "equity_role": null
  },
  {
    "id": "loan",
    "code": "2100",
    "name": "Car loan",
    "type": "liability",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": null,
    "equity_role": null
  },
  {
    "id": "eq",
    "code": "3000",
    "name": "Opening equity",
    "type": "equity",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": null,
    "equity_role": null
  },
  {
    "id": "sal",
    "code": "4000",
    "name": "Salary",
    "type": "income",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": null,
    "equity_role": null
  },
  {
    "id": "rent",
    "code": "5000",
    "name": "Rent",
    "type": "expense",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": null,
    "equity_role": null
  },
  {
    "id": "food",
    "code": "5100",
    "name": "Groceries",
    "type": "expense",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": null,
    "equity_role": null
  },
  {
    "id": "out",
    "code": "5200",
    "name": "Eating out",
    "type": "expense",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": null,
    "equity_role": null
  },
  {
    "id": "int",
    "code": "5300",
    "name": "Loan interest",
    "type": "expense",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": null,
    "equity_role": null
  },
  {
    "id": "tv",
    "code": "5400",
    "name": "Streaming",
    "type": "expense",
    "currency": "EUR",
    "parent_id": null,
    "is_active": true,
    "tax_role": null,
    "asset_role": null,
    "equity_role": null
  }
];

export const DEBTS: DebtList = {
  "debts": [
    {
      "id": "debt-car",
      "name": "Car loan",
      "currency": "EUR",
      "principal": "10200.00",
      "apr": "0.0590",
      "minimum_payment": "350.00",
      "is_active": true,
      "account_id": "loan",
      "created_at": "2026-04-01T00:00:00+00:00",
      "updated_at": "2026-04-01T00:00:00+00:00"
    },
    {
      "id": "debt-student",
      "name": "Student loan",
      "currency": "EUR",
      "principal": "8000.00",
      "apr": "0.0450",
      "minimum_payment": "120.00",
      "is_active": true,
      "account_id": null,
      "created_at": "2026-04-01T00:00:00+00:00",
      "updated_at": "2026-04-01T00:00:00+00:00"
    }
  ],
  "total_balance": "17900.00",
  "total_minimum_payments": "470.00"
};

export const HOLDINGS: HoldingList = {
  "holdings": []
};

export const RECURRING: RecurringPayments = {
  "items": [
    {
      "payee": "Thank",
      "key": "thank",
      "cadence": "monthly",
      "typical_amount": "479.69",
      "varies": false,
      "currency": "EUR",
      "account_id": "card",
      "occurrences": 5,
      "last_date": "2026-09-15",
      "next_expected": "2026-10-15",
      "examples": [
        "CARD PAYMENT THANK YOU"
      ],
      "tracked": false,
      "subscription_id": null
    },
    {
      "payee": "Bistro Novo",
      "key": "bistro",
      "cadence": "monthly",
      "typical_amount": "74.45",
      "varies": true,
      "currency": "EUR",
      "account_id": "out",
      "occurrences": 6,
      "last_date": "2026-09-18",
      "next_expected": "2026-10-18",
      "examples": [
        "BISTRO NOVO"
      ],
      "tracked": false,
      "subscription_id": null
    },
    {
      "payee": "Brokerage",
      "key": "brokerage",
      "cadence": "monthly",
      "typical_amount": "500.00",
      "varies": false,
      "currency": "EUR",
      "account_id": "brk",
      "occurrences": 6,
      "last_date": "2026-09-26",
      "next_expected": "2026-10-26",
      "examples": [
        "TO BROKERAGE"
      ],
      "tracked": false,
      "subscription_id": null
    },
    {
      "payee": "Savings",
      "key": "savings",
      "cadence": "monthly",
      "typical_amount": "300.00",
      "varies": false,
      "currency": "EUR",
      "account_id": "sav",
      "occurrences": 6,
      "last_date": "2026-09-26",
      "next_expected": "2026-10-26",
      "examples": [
        "TO SAVINGS"
      ],
      "tracked": false,
      "subscription_id": null
    },
    {
      "payee": "City Lettings Rent",
      "key": "city",
      "cadence": "monthly",
      "typical_amount": "1500.00",
      "varies": false,
      "currency": "EUR",
      "account_id": "rent",
      "occurrences": 7,
      "last_date": "2026-10-01",
      "next_expected": "2026-11-01",
      "examples": [
        "CITY LETTINGS RENT"
      ],
      "tracked": false,
      "subscription_id": null
    },
    {
      "payee": "Streamflix",
      "key": "streamflix",
      "cadence": "monthly",
      "typical_amount": "12.99",
      "varies": false,
      "currency": "EUR",
      "account_id": "tv",
      "occurrences": 7,
      "last_date": "2026-10-08",
      "next_expected": "2026-11-08",
      "examples": [
        "STREAMFLIX"
      ],
      "tracked": false,
      "subscription_id": null
    }
  ]
};

export const TEMPLATES: DecisionTemplateList = {
  "templates": [
    {
      "schema": "salli.template/1",
      "id": "afford-it",
      "title": "Afford it",
      "summary": "Whether a purchase fits, and how you might pay for it: cash, spread over months, or wait and save.",
      "builds": [
        "Pay cash: the price out of cash on the day",
        "Spread it: the same, borrowed back at your rate and repaid over your months",
        "Wait and save: bought later, with what you set aside each month until then"
      ]
    },
    {
      "schema": "salli.template/1",
      "id": "debt-or-invest",
      "title": "Debt or invest",
      "summary": "The same money onto a debt, or invested, or split between them: once, or every month.",
      "builds": [
        "Pay down the debt: the money onto it on top of its payments",
        "Invest it: the same money moved into your investments",
        "Split: the part you say onto the debt, the rest invested"
      ]
    },
    {
      "schema": "salli.template/1",
      "id": "windfall",
      "title": "Use a windfall or surplus",
      "summary": "A sum (a bonus, a gift, savings built up) shared out the ways you propose, across debts, investing and cash.",
      "builds": [
        "Each split you propose: amounts onto debts and into investments, the rest kept in cash"
      ]
    },
    {
      "schema": "salli.template/1",
      "id": "big-change",
      "title": "Big recurring change",
      "summary": "A new flat, a new job, a car: what changes month after month, and what it costs at the start, against things as they are.",
      "builds": [
        "As things are: your baseline",
        "The change: its costs and income each month from the start, and anything paid once"
      ]
    },
    {
      "schema": "salli.template/1",
      "id": "borrow",
      "title": "Borrow or refinance",
      "summary": "Loans side by side, each with its payment and total interest, and what it does to your cash and FI: for new borrowing, or to replace a debt you have.",
      "builds": [
        "Each loan you compare: its payments, interest and effect on cash and FI",
        "Don't borrow, or keep the debt as it is: your baseline"
      ]
    },
    {
      "schema": "salli.template/1",
      "id": "emergency-fund",
      "title": "Emergency fund",
      "summary": "How many months of spending your cash covers now, and when it would cover your target, as things are and with each amount you could set aside.",
      "builds": [
        "As things are: your baseline",
        "Set aside each amount you say, every month: kept in cash rather than invested"
      ]
    },
    {
      "schema": "salli.template/1",
      "id": "rent-or-buy",
      "title": "Rent or buy",
      "summary": "Keep renting, or buy a home with each mortgage you compare: laid out as consequences, with the house-price growth at which the answer turns.",
      "builds": [
        "Keep renting: your rent goes on, rising at the rent's growth",
        "Buy, with each mortgage: the home from cash and the mortgage, buying and owning costs, and the rent stopped"
      ]
    }
  ]
};

export const AFFORD_IT: DecisionTemplate = {
  "schema": "salli.template/1",
  "id": "afford-it",
  "title": "Afford it",
  "summary": "Whether a purchase fits, and how you might pay for it: cash, spread over months, or wait and save.",
  "builds": [
    "Pay cash: the price out of cash on the day",
    "Spread it: the same, borrowed back at your rate and repaid over your months",
    "Wait and save: bought later, with what you set aside each month until then"
  ],
  "questions": [
    {
      "id": "price",
      "type": "amount",
      "prompt": "What does it cost?",
      "help": "In your base currency.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "what",
      "type": "text",
      "prompt": "What is it?",
      "help": "A few words: what the options call it.",
      "required": false,
      "when": null,
      "default": {
        "value": "The purchase",
        "source": "salli",
        "note": "a plain name for it"
      },
      "default_rule": "“The purchase”",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "date",
      "type": "date",
      "prompt": "When would you pay?",
      "help": "The day the money would go out, if you pay cash.",
      "required": false,
      "when": null,
      "default": {
        "value": "2026-10-11",
        "source": "as_of",
        "note": "the as-of date (today, unless you chose a day)"
      },
      "default_rule": "the as-of date",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "account",
      "type": "account",
      "prompt": "Which cash account would it come out of?",
      "help": "Leave it out to take it from your cash as a whole.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "instalment_months",
      "type": "months",
      "prompt": "Could you spread it? Over how many months?",
      "help": "Leave it out if spreading it isn't on offer.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": 1,
      "maximum": 600,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "instalment_rate",
      "type": "rate",
      "prompt": "At what yearly rate?",
      "help": "As a fraction: \"0.069\" is 6.9%, \"0\" an interest-free offer. Ask the lender for the rate it would charge you.",
      "required": true,
      "when": {
        "question": "instalment_months",
        "equals": null
      },
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "wait_months",
      "type": "months",
      "prompt": "Could you wait? For how many months?",
      "help": "Leave it out if waiting isn't an option.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": 1,
      "maximum": 120,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "save_monthly",
      "type": "amount",
      "prompt": "How much of your monthly surplus would you set aside while you wait?",
      "help": "Kept in cash each month until you buy, rather than invested. Leave it out to wait without setting anything aside.",
      "required": false,
      "when": {
        "question": "wait_months",
        "equals": null
      },
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "horizon_years",
      "type": "years",
      "prompt": "How many years ahead do you want the long-run figures to run?",
      "help": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall.",
      "required": false,
      "when": null,
      "default": {
        "value": 20,
        "source": "salli",
        "note": "Salli's usual horizon for long-run figures"
      },
      "default_rule": "20 years",
      "choices": [],
      "minimum": 1,
      "maximum": 50,
      "min_items": null,
      "max_items": null
    }
  ],
  "answers_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Answers to the Afford it template (salli.template/1)",
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "price": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "In your base currency.",
        "title": "What does it cost?"
      },
      "what": {
        "type": "string",
        "minLength": 1,
        "maxLength": 120,
        "title": "What is it?",
        "description": "A few words: what the options call it."
      },
      "date": {
        "type": "string",
        "format": "date",
        "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        "title": "When would you pay?",
        "description": "The day the money would go out, if you pay cash."
      },
      "account": {
        "type": "string",
        "description": "Leave it out to take it from your cash as a whole.",
        "enum": [
          "chk",
          "sav"
        ],
        "title": "Which cash account would it come out of?"
      },
      "instalment_months": {
        "type": "integer",
        "minimum": 1,
        "maximum": 600,
        "title": "Could you spread it? Over how many months?",
        "description": "Leave it out if spreading it isn't on offer."
      },
      "instalment_rate": {
        "type": "string",
        "pattern": "^[0-9]+(\\.[0-9]+)?$",
        "description": "As a fraction: \"0.069\" is 6.9%, \"0\" an interest-free offer. Ask the lender for the rate it would charge you.",
        "title": "At what yearly rate?"
      },
      "wait_months": {
        "type": "integer",
        "minimum": 1,
        "maximum": 120,
        "title": "Could you wait? For how many months?",
        "description": "Leave it out if waiting isn't an option."
      },
      "save_monthly": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "Kept in cash each month until you buy, rather than invested. Leave it out to wait without setting anything aside.",
        "title": "How much of your monthly surplus would you set aside while you wait?"
      },
      "horizon_years": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "title": "How many years ahead do you want the long-run figures to run?",
        "description": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall."
      }
    }
  },
  "notes": []
};

export const DEBT_OR_INVEST: DecisionTemplate = {
  "schema": "salli.template/1",
  "id": "debt-or-invest",
  "title": "Debt or invest",
  "summary": "The same money onto a debt, or invested, or split between them: once, or every month.",
  "builds": [
    "Pay down the debt: the money onto it on top of its payments",
    "Invest it: the same money moved into your investments",
    "Split: the part you say onto the debt, the rest invested"
  ],
  "questions": [
    {
      "id": "debt",
      "type": "debt",
      "prompt": "Which debt?",
      "help": "One of your debts with terms (salli debts list).",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": "your only debt, when you have one",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "amount",
      "type": "amount",
      "prompt": "How much?",
      "help": "In your base currency.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "how",
      "type": "choice",
      "prompt": "Once, or every month?",
      "help": "A sum you have now, or an amount you could put towards it each month.",
      "required": false,
      "when": null,
      "default": {
        "value": "once",
        "source": "salli",
        "note": "a single sum"
      },
      "default_rule": "once",
      "choices": [
        {
          "value": "once",
          "label": "Once"
        },
        {
          "value": "monthly",
          "label": "Every month"
        }
      ],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "months",
      "type": "months",
      "prompt": "For how many months?",
      "help": "How long you would keep it up.",
      "required": true,
      "when": {
        "question": "how",
        "equals": "monthly"
      },
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": 1,
      "maximum": 48,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "start",
      "type": "date",
      "prompt": "From when?",
      "help": "The day the first payment goes onto the debt, or is invested: both start together. In this month, a payment onto the debt lands at the month's end, before its next scheduled payment.",
      "required": false,
      "when": null,
      "default": {
        "value": "2026-11-01",
        "source": "next_month",
        "note": "the first of next month"
      },
      "default_rule": "the first of next month",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "split_on_debt",
      "type": "amount",
      "prompt": "To compare a split too: how much of it would go on the debt?",
      "help": "The rest is invested. Leave it out to compare the two alone.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "holding",
      "type": "holding",
      "prompt": "Into one of your holdings?",
      "help": "One of your own holdings (salli holdings list), to see the units the money buys at its last recorded price. Leave it out to invest into your investments as a whole. Salli never picks one.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "horizon_years",
      "type": "years",
      "prompt": "How many years ahead do you want the long-run figures to run?",
      "help": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall.",
      "required": false,
      "when": null,
      "default": {
        "value": 20,
        "source": "salli",
        "note": "Salli's usual horizon for long-run figures"
      },
      "default_rule": "20 years",
      "choices": [],
      "minimum": 1,
      "maximum": 50,
      "min_items": null,
      "max_items": null
    }
  ],
  "answers_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Answers to the Debt or invest template (salli.template/1)",
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "debt": {
        "type": "string",
        "description": "One of your debts with terms (salli debts list).",
        "enum": [
          "debt-car",
          "debt-student"
        ],
        "title": "Which debt?"
      },
      "amount": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "In your base currency.",
        "title": "How much?"
      },
      "how": {
        "type": "string",
        "enum": [
          "once",
          "monthly"
        ],
        "title": "Once, or every month?",
        "description": "A sum you have now, or an amount you could put towards it each month."
      },
      "months": {
        "type": "integer",
        "minimum": 1,
        "maximum": 48,
        "title": "For how many months?",
        "description": "How long you would keep it up."
      },
      "start": {
        "type": "string",
        "format": "date",
        "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        "title": "From when?",
        "description": "The day the first payment goes onto the debt, or is invested: both start together. In this month, a payment onto the debt lands at the month's end, before its next scheduled payment."
      },
      "split_on_debt": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "The rest is invested. Leave it out to compare the two alone.",
        "title": "To compare a split too: how much of it would go on the debt?"
      },
      "holding": {
        "type": "string",
        "description": "One of your own holdings (salli holdings list), to see the units the money buys at its last recorded price. Leave it out to invest into your investments as a whole. Salli never picks one.",
        "title": "Into one of your holdings?"
      },
      "horizon_years": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "title": "How many years ahead do you want the long-run figures to run?",
        "description": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall."
      }
    }
  },
  "notes": []
};

export const WINDFALL: DecisionTemplate = {
  "schema": "salli.template/1",
  "id": "windfall",
  "title": "Use a windfall or surplus",
  "summary": "A sum (a bonus, a gift, savings built up) shared out the ways you propose, across debts, investing and cash.",
  "builds": [
    "Each split you propose: amounts onto debts and into investments, the rest kept in cash"
  ],
  "questions": [
    {
      "id": "amount",
      "type": "amount",
      "prompt": "How much is it?",
      "help": "In your base currency.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "arrives",
      "type": "choice",
      "prompt": "Is it new money, or already in your cash?",
      "help": "New money arrives on the day (a bonus, a gift); a surplus is already in your cash.",
      "required": false,
      "when": null,
      "default": {
        "value": "new",
        "source": "salli",
        "note": "new money arriving"
      },
      "default_rule": "new money",
      "choices": [
        {
          "value": "new",
          "label": "New money: it arrives on the day"
        },
        {
          "value": "in_cash",
          "label": "Already in my cash"
        }
      ],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "tax_role",
      "type": "tax_role",
      "prompt": "Is it taxable? In which of your tax rules' roles?",
      "help": "Leave it out if the amount is what reaches you. If it is taxable before it reaches you (a bonus, say), name the role your active tax rules count it in: the amount is then before tax, and Salli works out the tax with your rules.",
      "required": false,
      "when": {
        "question": "arrives",
        "equals": "new"
      },
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "date",
      "type": "date",
      "prompt": "When does it arrive, or when would you use it?",
      "help": "Money is invested on this day, and a payment onto a debt lands in its month: in this month, at the month's end, before the debt's next scheduled payment.",
      "required": false,
      "when": null,
      "default": {
        "value": "2026-10-11",
        "source": "as_of",
        "note": "the as-of date (today, unless you chose a day)"
      },
      "default_rule": "the as-of date",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "account",
      "type": "account",
      "prompt": "Which cash account does it arrive in, or come from?",
      "help": "Leave it out to use your cash as a whole.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "splits",
      "type": "splits",
      "prompt": "How would you share it out?",
      "help": "Two to five ways, each with a label: amounts onto your debts, an amount invested. What a split doesn't put to work stays in cash.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": 2,
      "max_items": 5
    },
    {
      "id": "holding",
      "type": "holding",
      "prompt": "Into one of your holdings?",
      "help": "One of your own holdings (salli holdings list), to see the units the money buys at its last recorded price. Leave it out to invest into your investments as a whole. Salli never picks one.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "horizon_years",
      "type": "years",
      "prompt": "How many years ahead do you want the long-run figures to run?",
      "help": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall.",
      "required": false,
      "when": null,
      "default": {
        "value": 20,
        "source": "salli",
        "note": "Salli's usual horizon for long-run figures"
      },
      "default_rule": "20 years",
      "choices": [],
      "minimum": 1,
      "maximum": 50,
      "min_items": null,
      "max_items": null
    }
  ],
  "answers_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Answers to the Use a windfall or surplus template (salli.template/1)",
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "amount": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "In your base currency.",
        "title": "How much is it?"
      },
      "arrives": {
        "type": "string",
        "enum": [
          "new",
          "in_cash"
        ],
        "title": "Is it new money, or already in your cash?",
        "description": "New money arrives on the day (a bonus, a gift); a surplus is already in your cash."
      },
      "tax_role": {
        "type": "string",
        "description": "Leave it out if the amount is what reaches you. If it is taxable before it reaches you (a bonus, say), name the role your active tax rules count it in: the amount is then before tax, and Salli works out the tax with your rules.",
        "title": "Is it taxable? In which of your tax rules' roles?"
      },
      "date": {
        "type": "string",
        "format": "date",
        "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        "title": "When does it arrive, or when would you use it?",
        "description": "Money is invested on this day, and a payment onto a debt lands in its month: in this month, at the month's end, before the debt's next scheduled payment."
      },
      "account": {
        "type": "string",
        "description": "Leave it out to use your cash as a whole.",
        "enum": [
          "chk",
          "sav"
        ],
        "title": "Which cash account does it arrive in, or come from?"
      },
      "splits": {
        "type": "array",
        "minItems": 2,
        "maxItems": 5,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "label"
          ],
          "properties": {
            "label": {
              "type": "string",
              "minLength": 1,
              "maxLength": 120
            },
            "debts": {
              "type": "array",
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": [
                  "debt",
                  "amount"
                ],
                "properties": {
                  "debt": {
                    "type": "string",
                    "description": "One of your debts, by its id.",
                    "enum": [
                      "debt-car",
                      "debt-student"
                    ]
                  },
                  "amount": {
                    "type": "string",
                    "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
                    "description": "An amount above zero in your base currency, as a decimal string: \"2400.00\"."
                  }
                }
              }
            },
            "invest": {
              "type": "string",
              "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
              "description": "An amount above zero in your base currency, as a decimal string: \"2400.00\"."
            }
          }
        },
        "title": "How would you share it out?",
        "description": "Two to five ways, each with a label: amounts onto your debts, an amount invested. What a split doesn't put to work stays in cash."
      },
      "holding": {
        "type": "string",
        "description": "One of your own holdings (salli holdings list), to see the units the money buys at its last recorded price. Leave it out to invest into your investments as a whole. Salli never picks one.",
        "title": "Into one of your holdings?"
      },
      "horizon_years": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "title": "How many years ahead do you want the long-run figures to run?",
        "description": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall."
      }
    }
  },
  "notes": []
};

export const BIG_CHANGE: DecisionTemplate = {
  "schema": "salli.template/1",
  "id": "big-change",
  "title": "Big recurring change",
  "summary": "A new flat, a new job, a car: what changes month after month, and what it costs at the start, against things as they are.",
  "builds": [
    "As things are: your baseline",
    "The change: its costs and income each month from the start, and anything paid once"
  ],
  "questions": [
    {
      "id": "label",
      "type": "text",
      "prompt": "What is the change?",
      "help": "A few words: “New flat”, “New job”, “A car”.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "start",
      "type": "date",
      "prompt": "When would it start?",
      "help": "The day the first month's costs or pay change.",
      "required": false,
      "when": null,
      "default": {
        "value": "2026-11-01",
        "source": "next_month",
        "note": "the first of next month"
      },
      "default_rule": "the first of next month",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "monthly_costs",
      "type": "signed_amount",
      "prompt": "How much more would you spend a month?",
      "help": "In your base currency: \"+450\" more, \"-200\" less. Leave it out if spending stays the same.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "monthly_income",
      "type": "signed_amount",
      "prompt": "How much more would you take home a month?",
      "help": "In your base currency: \"+600\" more, \"-300\" less. After tax, unless you name the tax role it is paid in (next): then before tax. Leave it out if it stays the same.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "income_tax_role",
      "type": "tax_role",
      "prompt": "Is that pay before tax? In which of your tax rules' roles?",
      "help": "Leave it out if the amount is take-home pay. If it is before tax, name the role your active tax rules count it in (your salary's, say): Salli then works out the tax with your rules.",
      "required": false,
      "when": {
        "question": "monthly_income",
        "equals": null
      },
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "upfront",
      "type": "amount",
      "prompt": "Anything to pay once at the start?",
      "help": "A deposit, moving costs, a down payment. Leave it out if there's none.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "end",
      "type": "date",
      "prompt": "Does it end? On what day?",
      "help": "Leave it out if it goes on.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "account",
      "type": "account",
      "prompt": "Which cash account would the costs come out of?",
      "help": "Leave it out to use your cash as a whole.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "horizon_years",
      "type": "years",
      "prompt": "How many years ahead do you want the long-run figures to run?",
      "help": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall.",
      "required": false,
      "when": null,
      "default": {
        "value": 20,
        "source": "salli",
        "note": "Salli's usual horizon for long-run figures"
      },
      "default_rule": "20 years",
      "choices": [],
      "minimum": 1,
      "maximum": 50,
      "min_items": null,
      "max_items": null
    }
  ],
  "answers_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Answers to the Big recurring change template (salli.template/1)",
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "label": {
        "type": "string",
        "minLength": 1,
        "maxLength": 120,
        "title": "What is the change?",
        "description": "A few words: “New flat”, “New job”, “A car”."
      },
      "start": {
        "type": "string",
        "format": "date",
        "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        "title": "When would it start?",
        "description": "The day the first month's costs or pay change."
      },
      "monthly_costs": {
        "type": "string",
        "pattern": "^[+-]?[0-9]+(\\.[0-9]+)?$",
        "description": "In your base currency: \"+450\" more, \"-200\" less. Leave it out if spending stays the same.",
        "title": "How much more would you spend a month?"
      },
      "monthly_income": {
        "type": "string",
        "pattern": "^[+-]?[0-9]+(\\.[0-9]+)?$",
        "description": "In your base currency: \"+600\" more, \"-300\" less. After tax, unless you name the tax role it is paid in (next): then before tax. Leave it out if it stays the same.",
        "title": "How much more would you take home a month?"
      },
      "income_tax_role": {
        "type": "string",
        "description": "Leave it out if the amount is take-home pay. If it is before tax, name the role your active tax rules count it in (your salary's, say): Salli then works out the tax with your rules.",
        "title": "Is that pay before tax? In which of your tax rules' roles?"
      },
      "upfront": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "A deposit, moving costs, a down payment. Leave it out if there's none.",
        "title": "Anything to pay once at the start?"
      },
      "end": {
        "type": "string",
        "format": "date",
        "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        "title": "Does it end? On what day?",
        "description": "Leave it out if it goes on."
      },
      "account": {
        "type": "string",
        "description": "Leave it out to use your cash as a whole.",
        "enum": [
          "chk",
          "sav"
        ],
        "title": "Which cash account would the costs come out of?"
      },
      "horizon_years": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "title": "How many years ahead do you want the long-run figures to run?",
        "description": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall."
      }
    }
  },
  "notes": []
};

export const BORROW: DecisionTemplate = {
  "schema": "salli.template/1",
  "id": "borrow",
  "title": "Borrow or refinance",
  "summary": "Loans side by side, each with its payment and total interest, and what it does to your cash and FI: for new borrowing, or to replace a debt you have.",
  "builds": [
    "Each loan you compare: its payments, interest and effect on cash and FI",
    "Don't borrow, or keep the debt as it is: your baseline"
  ],
  "questions": [
    {
      "id": "purpose",
      "type": "choice",
      "prompt": "New borrowing, or replacing a debt you have?",
      "help": "Refinancing pays one of your debts off with the new loan.",
      "required": false,
      "when": null,
      "default": {
        "value": "borrow",
        "source": "salli",
        "note": "new borrowing"
      },
      "default_rule": "new borrowing",
      "choices": [
        {
          "value": "borrow",
          "label": "New borrowing"
        },
        {
          "value": "refinance",
          "label": "Refinance a debt"
        }
      ],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "debt",
      "type": "debt",
      "prompt": "Which debt would it replace?",
      "help": "One of your debts with terms (salli debts list).",
      "required": true,
      "when": {
        "question": "purpose",
        "equals": "refinance"
      },
      "default": null,
      "default_rule": "your only debt, when you have one",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "principal",
      "type": "amount",
      "prompt": "How much would you borrow?",
      "help": "In your base currency. To refinance, what the debt owes now, unless you say otherwise.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": "to refinance: what the debt owes now",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "start",
      "type": "date",
      "prompt": "When would you take it out?",
      "help": "The day the money arrives. To refinance, the old debt is paid off with it in that month: in this month, at the month's end, before its next payment.",
      "required": false,
      "when": null,
      "default": {
        "value": "2026-10-11",
        "source": "as_of",
        "note": "the as-of date (today, unless you chose a day)"
      },
      "default_rule": "the as-of date; to refinance, the first of next month",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "into",
      "type": "account",
      "prompt": "Which cash account would the money go into?",
      "help": "Leave it out to use your cash as a whole.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "spent",
      "type": "choice",
      "prompt": "Is the money spent on the day, or kept in cash?",
      "help": "Spent on what you borrow it for, or kept as cash.",
      "required": false,
      "when": {
        "question": "purpose",
        "equals": "borrow"
      },
      "default": {
        "value": "spent",
        "source": "salli",
        "note": "spent on what it is for"
      },
      "default_rule": "spent",
      "choices": [
        {
          "value": "spent",
          "label": "Spent on the day"
        },
        {
          "value": "kept",
          "label": "Kept in cash"
        }
      ],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "what",
      "type": "text",
      "prompt": "What is it for?",
      "help": "A few words: what the purchase is called in the options.",
      "required": false,
      "when": {
        "question": "spent",
        "equals": "spent"
      },
      "default": {
        "value": "What it pays for",
        "source": "salli",
        "note": "a plain name for it"
      },
      "default_rule": "“What it pays for”",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "fee",
      "type": "amount",
      "prompt": "Any fee to pay when you take it out?",
      "help": "An arrangement fee, paid from cash. Leave it out if there's none.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "loans",
      "type": "loans",
      "prompt": "Which loans would you compare?",
      "help": "One to four, each with its yearly rate and its term in months, and a label if you like. Use the rates the lenders would charge you.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": 1,
      "max_items": 4
    },
    {
      "id": "horizon_years",
      "type": "years",
      "prompt": "How many years ahead do you want the long-run figures to run?",
      "help": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall.",
      "required": false,
      "when": null,
      "default": {
        "value": 20,
        "source": "salli",
        "note": "Salli's usual horizon for long-run figures"
      },
      "default_rule": "20 years",
      "choices": [],
      "minimum": 1,
      "maximum": 50,
      "min_items": null,
      "max_items": null
    }
  ],
  "answers_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Answers to the Borrow or refinance template (salli.template/1)",
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "purpose": {
        "type": "string",
        "enum": [
          "borrow",
          "refinance"
        ],
        "title": "New borrowing, or replacing a debt you have?",
        "description": "Refinancing pays one of your debts off with the new loan."
      },
      "debt": {
        "type": "string",
        "description": "One of your debts with terms (salli debts list).",
        "enum": [
          "debt-car",
          "debt-student"
        ],
        "title": "Which debt would it replace?"
      },
      "principal": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "In your base currency. To refinance, what the debt owes now, unless you say otherwise.",
        "title": "How much would you borrow?"
      },
      "start": {
        "type": "string",
        "format": "date",
        "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        "title": "When would you take it out?",
        "description": "The day the money arrives. To refinance, the old debt is paid off with it in that month: in this month, at the month's end, before its next payment."
      },
      "into": {
        "type": "string",
        "description": "Leave it out to use your cash as a whole.",
        "enum": [
          "chk",
          "sav"
        ],
        "title": "Which cash account would the money go into?"
      },
      "spent": {
        "type": "string",
        "enum": [
          "spent",
          "kept"
        ],
        "title": "Is the money spent on the day, or kept in cash?",
        "description": "Spent on what you borrow it for, or kept as cash."
      },
      "what": {
        "type": "string",
        "minLength": 1,
        "maxLength": 120,
        "title": "What is it for?",
        "description": "A few words: what the purchase is called in the options."
      },
      "fee": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "An arrangement fee, paid from cash. Leave it out if there's none.",
        "title": "Any fee to pay when you take it out?"
      },
      "loans": {
        "type": "array",
        "minItems": 1,
        "maxItems": 4,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "annual_rate",
            "term_months"
          ],
          "properties": {
            "annual_rate": {
              "type": "string",
              "pattern": "^[0-9]+(\\.[0-9]+)?$",
              "description": "A yearly rate as a fraction, a decimal string: \"0.069\" is 6.9%."
            },
            "term_months": {
              "type": "integer",
              "minimum": 1,
              "maximum": 600
            },
            "label": {
              "type": "string",
              "minLength": 1,
              "maxLength": 120
            }
          }
        },
        "title": "Which loans would you compare?",
        "description": "One to four, each with its yearly rate and its term in months, and a label if you like. Use the rates the lenders would charge you."
      },
      "horizon_years": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "title": "How many years ahead do you want the long-run figures to run?",
        "description": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall."
      }
    }
  },
  "notes": []
};

export const EMERGENCY_FUND: DecisionTemplate = {
  "schema": "salli.template/1",
  "id": "emergency-fund",
  "title": "Emergency fund",
  "summary": "How many months of spending your cash covers now, and when it would cover your target, as things are and with each amount you could set aside.",
  "builds": [
    "As things are: your baseline",
    "Set aside each amount you say, every month: kept in cash rather than invested"
  ],
  "questions": [
    {
      "id": "target_months",
      "type": "number",
      "prompt": "How many months of spending do you want your cash to cover?",
      "help": "Counted in your essential spending when your spending carries need tags, all of it otherwise. Yours to choose.",
      "required": true,
      "when": null,
      "default": {
        "value": "6",
        "source": "your_principles",
        "note": "from your principle “Six months of essentials in cash”"
      },
      "default_rule": "the months your principle asks for, when you have one",
      "choices": [],
      "minimum": null,
      "maximum": 120,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "set_aside",
      "type": "amounts",
      "prompt": "How much could you set aside each month?",
      "help": "One to four amounts to compare, each kept in cash out of your monthly surplus rather than invested.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": 1,
      "max_items": 4
    },
    {
      "id": "start",
      "type": "date",
      "prompt": "From when?",
      "help": "The month you would start setting it aside.",
      "required": false,
      "when": null,
      "default": {
        "value": "2026-11-01",
        "source": "next_month",
        "note": "the first of next month"
      },
      "default_rule": "the first of next month",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "months",
      "type": "months",
      "prompt": "For how many months?",
      "help": "Leave it out to keep going.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": 1,
      "maximum": 600,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "horizon_years",
      "type": "years",
      "prompt": "How many years ahead do you want the long-run figures to run?",
      "help": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall.",
      "required": false,
      "when": null,
      "default": {
        "value": 20,
        "source": "salli",
        "note": "Salli's usual horizon for long-run figures"
      },
      "default_rule": "20 years",
      "choices": [],
      "minimum": 1,
      "maximum": 50,
      "min_items": null,
      "max_items": null
    }
  ],
  "answers_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Answers to the Emergency fund template (salli.template/1)",
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "target_months": {
        "type": "string",
        "pattern": "^[0-9]+(\\.[0-9]+)?$",
        "description": "Counted in your essential spending when your spending carries need tags, all of it otherwise. Yours to choose.",
        "title": "How many months of spending do you want your cash to cover?"
      },
      "set_aside": {
        "type": "array",
        "items": {
          "type": "string",
          "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
          "description": "An amount above zero in your base currency, as a decimal string: \"2400.00\"."
        },
        "minItems": 1,
        "maxItems": 4,
        "title": "How much could you set aside each month?",
        "description": "One to four amounts to compare, each kept in cash out of your monthly surplus rather than invested."
      },
      "start": {
        "type": "string",
        "format": "date",
        "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        "title": "From when?",
        "description": "The month you would start setting it aside."
      },
      "months": {
        "type": "integer",
        "minimum": 1,
        "maximum": 600,
        "title": "For how many months?",
        "description": "Leave it out to keep going."
      },
      "horizon_years": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "title": "How many years ahead do you want the long-run figures to run?",
        "description": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall."
      }
    }
  },
  "notes": [
    "Cash earns nothing in Salli's figures, so what you set aside instead of investing shows in the long-run figures too."
  ]
};

export const RENT_OR_BUY: DecisionTemplate = {
  "schema": "salli.template/1",
  "id": "rent-or-buy",
  "title": "Rent or buy",
  "summary": "Keep renting, or buy a home with each mortgage you compare: laid out as consequences, with the house-price growth at which the answer turns.",
  "builds": [
    "Keep renting: your rent goes on, rising at the rent's growth",
    "Buy, with each mortgage: the home from cash and the mortgage, buying and owning costs, and the rent stopped"
  ],
  "questions": [
    {
      "id": "price",
      "type": "amount",
      "prompt": "What would the home cost?",
      "help": "In your base currency.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "date",
      "type": "date",
      "prompt": "When would you buy?",
      "help": "The day the price leaves cash and the mortgage arrives; the rent stops from it.",
      "required": false,
      "when": null,
      "default": {
        "value": "2026-11-01",
        "source": "next_month",
        "note": "the first of next month"
      },
      "default_rule": "the first of next month",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "deposit",
      "type": "amount",
      "prompt": "How much would you put down?",
      "help": "Out of your cash. The mortgage is the price less it.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "account",
      "type": "account",
      "prompt": "Which cash account would the money come out of?",
      "help": "The deposit, buying costs and owning costs. Leave it out to use your cash as a whole.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "mortgages",
      "type": "loans",
      "prompt": "Which mortgages would you compare?",
      "help": "One to three, each with its yearly rate and its term in months (up to 600), and a label if you like. Use the rates the lenders would offer you: each is held fixed for its whole term.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": 1,
      "max_items": 3
    },
    {
      "id": "buying_costs",
      "type": "amount_or_zero",
      "prompt": "What would buying cost, once (fees, and any tax on buying)?",
      "help": "Paid from cash on the day; \"0\" if nothing. A tax on buying is yours to give, from your own rules: Salli knows no country's.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "owning_costs",
      "type": "amount_or_zero",
      "prompt": "What would owning cost a month (maintenance, insurance, service charges, property taxes)?",
      "help": "In today's money, from the day you buy; \"0\" if nothing. Leaving them low flatters buying.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "rent",
      "type": "recurring",
      "prompt": "Which of your recurring payments is your rent?",
      "help": "By its key (salli insights recurring): it goes on if you keep renting, and stops if you buy. Leave it out if your ledger doesn't show your rent, and give rent_monthly.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "rent_monthly",
      "type": "amount_or_zero",
      "prompt": "If your ledger doesn't show your rent: what is it a month?",
      "help": "In today's money; \"0\" if you pay none. Keeping renting then adds it as a new cost.",
      "required": false,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "rent_growth",
      "type": "growth",
      "prompt": "How fast do you expect your rent to grow beyond inflation, a year?",
      "help": "A signed fraction: \"0.01\" is 1% a year more than prices, \"-0.005\" half a percent less. Your own view; left out, 0 (it rises with inflation), labelled a placeholder.",
      "required": false,
      "when": null,
      "default": {
        "value": "0",
        "source": "placeholder",
        "note": "a placeholder, not a forecast: set your own view"
      },
      "default_rule": "0, a placeholder",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "home_growth",
      "type": "growth",
      "prompt": "How fast do you expect the home's value to grow beyond inflation, a year?",
      "help": "A signed fraction, as for the rent. Your own view; left out, 0 (it keeps its value in today's money), labelled a placeholder. The break-even says what growth would change the answer.",
      "required": false,
      "when": null,
      "default": {
        "value": "0",
        "source": "placeholder",
        "note": "a placeholder, not a forecast: set your own view"
      },
      "default_rule": "0, a placeholder",
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "selling_costs",
      "type": "rate",
      "prompt": "What would selling the home cost, as a share of its value?",
      "help": "\"0.03\" is 3%: agents' fees and any tax on selling; \"0\" is an answer. The home counts in net worth at its value less them.",
      "required": true,
      "when": null,
      "default": null,
      "default_rule": null,
      "choices": [],
      "minimum": null,
      "maximum": null,
      "min_items": null,
      "max_items": null
    },
    {
      "id": "horizon_years",
      "type": "years",
      "prompt": "How many years ahead do you want the long-run figures to run?",
      "help": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall.",
      "required": false,
      "when": null,
      "default": {
        "value": 20,
        "source": "salli",
        "note": "Salli's usual horizon for long-run figures"
      },
      "default_rule": "20 years",
      "choices": [],
      "minimum": 1,
      "maximum": 50,
      "min_items": null,
      "max_items": null
    }
  ],
  "answers_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Answers to the Rent or buy template (salli.template/1)",
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "price": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "In your base currency.",
        "title": "What would the home cost?"
      },
      "date": {
        "type": "string",
        "format": "date",
        "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        "title": "When would you buy?",
        "description": "The day the price leaves cash and the mortgage arrives; the rent stops from it."
      },
      "deposit": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "Out of your cash. The mortgage is the price less it.",
        "title": "How much would you put down?"
      },
      "account": {
        "type": "string",
        "description": "The deposit, buying costs and owning costs. Leave it out to use your cash as a whole.",
        "enum": [
          "chk",
          "sav"
        ],
        "title": "Which cash account would the money come out of?"
      },
      "mortgages": {
        "type": "array",
        "minItems": 1,
        "maxItems": 3,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "annual_rate",
            "term_months"
          ],
          "properties": {
            "annual_rate": {
              "type": "string",
              "pattern": "^[0-9]+(\\.[0-9]+)?$",
              "description": "A yearly rate as a fraction, a decimal string: \"0.069\" is 6.9%."
            },
            "term_months": {
              "type": "integer",
              "minimum": 1,
              "maximum": 600
            },
            "label": {
              "type": "string",
              "minLength": 1,
              "maxLength": 120
            }
          }
        },
        "title": "Which mortgages would you compare?",
        "description": "One to three, each with its yearly rate and its term in months (up to 600), and a label if you like. Use the rates the lenders would offer you: each is held fixed for its whole term."
      },
      "buying_costs": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "Paid from cash on the day; \"0\" if nothing. A tax on buying is yours to give, from your own rules: Salli knows no country's.",
        "title": "What would buying cost, once (fees, and any tax on buying)?"
      },
      "owning_costs": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "In today's money, from the day you buy; \"0\" if nothing. Leaving them low flatters buying.",
        "title": "What would owning cost a month (maintenance, insurance, service charges, property taxes)?"
      },
      "rent": {
        "type": "string",
        "description": "By its key (salli insights recurring): it goes on if you keep renting, and stops if you buy. Leave it out if your ledger doesn't show your rent, and give rent_monthly.",
        "enum": [
          "bistro",
          "city",
          "streamflix"
        ],
        "title": "Which of your recurring payments is your rent?"
      },
      "rent_monthly": {
        "type": "string",
        "pattern": "^\\+?[0-9]+(\\.[0-9]+)?$",
        "description": "In today's money; \"0\" if you pay none. Keeping renting then adds it as a new cost.",
        "title": "If your ledger doesn't show your rent: what is it a month?"
      },
      "rent_growth": {
        "type": "string",
        "pattern": "^[+-]?[0-9]+(\\.[0-9]+)?$",
        "description": "A signed fraction: \"0.01\" is 1% a year more than prices, \"-0.005\" half a percent less. Your own view; left out, 0 (it rises with inflation), labelled a placeholder.",
        "title": "How fast do you expect your rent to grow beyond inflation, a year?"
      },
      "home_growth": {
        "type": "string",
        "pattern": "^[+-]?[0-9]+(\\.[0-9]+)?$",
        "description": "A signed fraction, as for the rent. Your own view; left out, 0 (it keeps its value in today's money), labelled a placeholder. The break-even says what growth would change the answer.",
        "title": "How fast do you expect the home's value to grow beyond inflation, a year?"
      },
      "selling_costs": {
        "type": "string",
        "pattern": "^[0-9]+(\\.[0-9]+)?$",
        "description": "\"0.03\" is 3%: agents' fees and any tax on selling; \"0\" is an answer. The home counts in net worth at its value less them.",
        "title": "What would selling the home cost, as a share of its value?"
      },
      "horizon_years": {
        "type": "integer",
        "minimum": 1,
        "maximum": 50,
        "title": "How many years ahead do you want the long-run figures to run?",
        "description": "Net worth and the break-evens are read at this horizon, in today's money. Payoff dates and the FI month are found wherever they fall."
      }
    }
  },
  "notes": [
    "The growth of the home's value and of the rent is your own view, or a labelled 0% beyond inflation, never a forecast: the house-price growth at which the answer turns (the asset_growth break-even) is the figure that matters.",
    "Each mortgage's rate is held fixed for its term: resets aren't modelled.",
    "A home is one asset, illiquid and undiversified: the comparison doesn't price that risk.",
    "Owning costs are what you give: leaving them low flatters buying.",
    "Tax on buying, owning or selling a home comes only from your own rules: a tax on buying is a buying cost you give; nothing else about a home's tax is modelled.",
    "Salli knows nothing about any local property market: research behind your figures needs its sources.",
    "The home counts in net worth at what it would fetch, its value less its selling costs, so buying starts behind by them; like any other asset it funds no withdrawals in FI."
  ]
};

/**
 * The laptop: 2,400.00 on Nov 2, paid at once, over 12 months at 6.9%, or
 * after six months of setting 400.00 aside; over five years.
 */
export const AFFORD_IT_START: DecisionStart = {
  "schema": "salli.decision-start/1",
  "template": {
    "id": "afford-it",
    "title": "Afford it"
  },
  "as_of": "2026-10-11",
  "currency": "EUR",
  "horizon_years": 5,
  "question": "Can I afford Laptop (2400.00 EUR), and how would I pay for it?",
  "answers": [
    {
      "id": "price",
      "value": "2400.00",
      "source": "given",
      "note": null
    },
    {
      "id": "what",
      "value": "Laptop",
      "source": "given",
      "note": null
    },
    {
      "id": "date",
      "value": "2026-11-02",
      "source": "given",
      "note": null
    },
    {
      "id": "account",
      "value": "chk",
      "source": "given",
      "note": null
    },
    {
      "id": "instalment_months",
      "value": 12,
      "source": "given",
      "note": null
    },
    {
      "id": "instalment_rate",
      "value": "0.069",
      "source": "given",
      "note": null
    },
    {
      "id": "wait_months",
      "value": 6,
      "source": "given",
      "note": null
    },
    {
      "id": "save_monthly",
      "value": "400.00",
      "source": "given",
      "note": null
    },
    {
      "id": "horizon_years",
      "value": 5,
      "source": "given",
      "note": null
    }
  ],
  "options": [
    {
      "label": "Pay cash",
      "describes": "2400.00 EUR out of cash on 2026-11-02.",
      "scenario": {
        "schema": "salli.scenario/1",
        "label": "Pay cash",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "one_off",
            "date": "2026-11-02",
            "amount": "-2400.00",
            "account": "chk",
            "tax_role": null,
            "label": "Laptop"
          }
        ],
        "tax": null
      },
      "scenario_hash": "sha256:9b094ea3ce715a3e72c3351d3125a932f6182e9a6d202e422b1facc0787702e4"
    },
    {
      "label": "Spread over 12 months",
      "describes": "The same 2400.00 EUR out on 2026-11-02, borrowed at 6.9% a year and repaid in monthly payments over 12 months.",
      "scenario": {
        "schema": "salli.scenario/1",
        "label": "Spread over 12 months",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "one_off",
            "date": "2026-11-02",
            "amount": "-2400.00",
            "account": "chk",
            "tax_role": null,
            "label": "Laptop"
          },
          {
            "type": "loan",
            "principal": "2400.00",
            "annual_rate": "0.069",
            "term_months": 12,
            "start": "2026-11-02",
            "into": "chk",
            "label": "Laptop, over 12 months"
          }
        ],
        "tax": null
      },
      "scenario_hash": "sha256:65aea5213bff9c2365ddf72f441301d3eebd8e577b5afbaa316f4a26e6f28a00"
    },
    {
      "label": "Wait 6 months",
      "describes": "2400.00 EUR out of cash on 2027-05-02, with 400.00 EUR of each month's surplus kept in cash until then rather than invested.",
      "scenario": {
        "schema": "salli.scenario/1",
        "label": "Wait 6 months",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "set_aside",
            "monthly": "400.00",
            "from": "2026-11-02",
            "to": "2027-04-30",
            "label": "Saving for Laptop"
          },
          {
            "type": "one_off",
            "date": "2027-05-02",
            "amount": "-2400.00",
            "account": "chk",
            "tax_role": null,
            "label": "Laptop"
          }
        ],
        "tax": null
      },
      "scenario_hash": "sha256:54f663454d40513a0b7efa5cbf3f89feb77e7b9ca2e20370ac312603d0e27dcd"
    }
  ],
  "comparison": {
    "as_of": "2026-10-11",
    "horizon_years": 5,
    "currency": "EUR",
    "labels": [
      "Pay cash",
      "Spread over 12 months",
      "Wait 6 months"
    ],
    "options": [
      {
        "schema": "salli.scenario/1",
        "label": "Pay cash",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "currency": "EUR",
        "hash": "sha256:9b094ea3ce715a3e72c3351d3125a932f6182e9a6d202e422b1facc0787702e4",
        "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Pay cash",
          "as_of": "2026-10-11",
          "horizon_years": 5,
          "changes": [
            {
              "type": "one_off",
              "date": "2026-11-02",
              "amount": "-2400.00",
              "account": "chk",
              "tax_role": null,
              "label": "Laptop"
            }
          ],
          "tax": null
        },
        "changes": [
          {
            "index": 0,
            "type": "one_off",
            "label": "Laptop",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": null,
            "for_good": null,
            "stopped": [],
            "holding": null
          }
        ],
        "cash": {
          "start": "2026-10-11",
          "end": "2027-10-31",
          "lowest": {
            "baseline": "13998.91",
            "scenario": "11598.91",
            "delta": "-2400.00"
          },
          "lowest_date": {
            "baseline": "2027-02-24",
            "scenario": "2027-02-24",
            "delta_days": 0
          },
          "at_end": {
            "baseline": "15801.47",
            "scenario": "13401.47",
            "delta": "-2400.00"
          },
          "safe_to_spend": {
            "baseline": "15316.35",
            "scenario": "15316.35",
            "delta": "0.00"
          },
          "safe_until": "2026-10-25",
          "accounts": [
            {
              "account_id": "chk",
              "name": "Checking",
              "currency": "EUR",
              "lowest": {
                "baseline": "6063.46",
                "scenario": "4883.77",
                "delta": "-1179.69"
              },
              "lowest_date": {
                "baseline": "2026-10-15",
                "scenario": "2026-11-15",
                "delta_days": 31
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "sav",
              "name": "Savings",
              "currency": "EUR",
              "lowest": {
                "baseline": "7800.00",
                "scenario": "7800.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "usd",
              "name": "Dollar account",
              "currency": "USD",
              "lowest": {
                "baseline": "2500.00",
                "scenario": "2500.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            }
          ],
          "below_zero": {
            "baseline": [],
            "scenario": []
          }
        },
        "monthly": [
          {
            "years": 1,
            "month": "2027-10",
            "date": "2027-10-31",
            "net_worth": {
              "baseline": "366266.13",
              "scenario": "363866.13",
              "delta": "-2400.00"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "investments": {
              "baseline": "63546.81",
              "scenario": "63546.81",
              "delta": "0.00"
            },
            "debts": {
              "baseline": "13082.15",
              "scenario": "13082.15",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          },
          {
            "years": 5,
            "month": "2031-10",
            "date": "2031-10-31",
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "483151.81",
              "delta": "-2400.00"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "171707.25",
              "delta": "0.00"
            },
            "debts": {
              "baseline": "1956.91",
              "scenario": "1956.91",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          }
        ],
        "debts": {
          "items": [
            {
              "debt_id": "debt-car",
              "name": "Car loan",
              "source": "account",
              "paid_off": {
                "baseline": "2029-05",
                "scenario": "2029-05",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "786.13",
                "scenario": "786.13",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "debt-student",
              "name": "Student loan",
              "source": "declared",
              "paid_off": {
                "baseline": "2033-03",
                "scenario": "2033-03",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "1223.12",
                "scenario": "1223.12",
                "delta": "0.00"
              }
            }
          ],
          "total_interest": {
            "baseline": "2009.25",
            "scenario": "2009.25",
            "delta": "0.00"
          },
          "debt_free": {
            "baseline": "2033-03",
            "scenario": "2033-03",
            "delta_months": 0
          }
        },
        "resilience": {
          "basis": "essential",
          "monthly_spending": "1898.32",
          "lowest": {
            "baseline": "7.37",
            "scenario": "6.11",
            "delta": "-1.26"
          },
          "at_end": {
            "baseline": "8.32",
            "scenario": "7.06",
            "delta": "-1.26"
          }
        },
        "fi": {
          "fi_number": {
            "baseline": "714042.04",
            "scenario": "714042.04",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2044-08",
            "scenario": "2044-09",
            "delta_months": 1
          },
          "months_gained": -1
        },
        "break_evens": [],
        "tax": {
          "status": "none",
          "reason": null,
          "years": [],
          "this_year": null,
          "change_this_year": "0.00",
          "total_change": "0.00",
          "carried_forward": false
        },
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
          "nominal_returns": null,
          "cma": null
        },
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon",
          "inflation"
        ],
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": [],
        "timeline": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Spread over 12 months",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "currency": "EUR",
        "hash": "sha256:65aea5213bff9c2365ddf72f441301d3eebd8e577b5afbaa316f4a26e6f28a00",
        "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Spread over 12 months",
          "as_of": "2026-10-11",
          "horizon_years": 5,
          "changes": [
            {
              "type": "one_off",
              "date": "2026-11-02",
              "amount": "-2400.00",
              "account": "chk",
              "tax_role": null,
              "label": "Laptop"
            },
            {
              "type": "loan",
              "principal": "2400.00",
              "annual_rate": "0.069",
              "term_months": 12,
              "start": "2026-11-02",
              "into": "chk",
              "label": "Laptop, over 12 months"
            }
          ],
          "tax": null
        },
        "changes": [
          {
            "index": 0,
            "type": "one_off",
            "label": "Laptop",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": null,
            "for_good": null,
            "stopped": [],
            "holding": null
          },
          {
            "index": 1,
            "type": "loan",
            "label": "Laptop, over 12 months",
            "debt_id": "scenario-loan-2",
            "payment": "207.55",
            "first_payment": "2026-12",
            "monthly": null,
            "for_good": null,
            "stopped": [],
            "holding": null
          }
        ],
        "cash": {
          "start": "2026-10-11",
          "end": "2027-10-31",
          "lowest": {
            "baseline": "13998.91",
            "scenario": "13821.01",
            "delta": "-177.90"
          },
          "lowest_date": {
            "baseline": "2027-02-24",
            "scenario": "2027-02-24",
            "delta_days": 0
          },
          "at_end": {
            "baseline": "15801.47",
            "scenario": "15801.47",
            "delta": "0.00"
          },
          "safe_to_spend": {
            "baseline": "15316.35",
            "scenario": "15316.35",
            "delta": "0.00"
          },
          "safe_until": "2026-10-25",
          "accounts": [
            {
              "account_id": "chk",
              "name": "Checking",
              "currency": "EUR",
              "lowest": {
                "baseline": "6063.46",
                "scenario": "6063.46",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-15",
                "scenario": "2026-10-15",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "sav",
              "name": "Savings",
              "currency": "EUR",
              "lowest": {
                "baseline": "7800.00",
                "scenario": "7800.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "usd",
              "name": "Dollar account",
              "currency": "USD",
              "lowest": {
                "baseline": "2500.00",
                "scenario": "2500.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            }
          ],
          "below_zero": {
            "baseline": [],
            "scenario": []
          }
        },
        "monthly": [
          {
            "years": 1,
            "month": "2027-10",
            "date": "2027-10-31",
            "net_worth": {
              "baseline": "366266.13",
              "scenario": "363738.21",
              "delta": "-2527.92"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "63546.81",
              "scenario": "61225.33",
              "delta": "-2321.48"
            },
            "debts": {
              "baseline": "13082.15",
              "scenario": "13288.59",
              "delta": "206.44"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          },
          {
            "years": 5,
            "month": "2031-10",
            "date": "2031-10-31",
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "482585.47",
              "delta": "-2966.34"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "168740.91",
              "delta": "-2966.34"
            },
            "debts": {
              "baseline": "1956.91",
              "scenario": "1956.91",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          }
        ],
        "debts": {
          "items": [
            {
              "debt_id": "debt-car",
              "name": "Car loan",
              "source": "account",
              "paid_off": {
                "baseline": "2029-05",
                "scenario": "2029-05",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "786.13",
                "scenario": "786.13",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "debt-student",
              "name": "Student loan",
              "source": "declared",
              "paid_off": {
                "baseline": "2033-03",
                "scenario": "2033-03",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "1223.12",
                "scenario": "1223.12",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "scenario-loan-2",
              "name": "Laptop, over 12 months",
              "source": "scenario",
              "paid_off": {
                "baseline": null,
                "scenario": "2027-11",
                "delta_months": null
              },
              "total_interest": {
                "baseline": "0.00",
                "scenario": "90.68",
                "delta": "90.68"
              }
            }
          ],
          "total_interest": {
            "baseline": "2009.25",
            "scenario": "2099.93",
            "delta": "90.68"
          },
          "debt_free": {
            "baseline": "2033-03",
            "scenario": "2033-03",
            "delta_months": 0
          }
        },
        "resilience": {
          "basis": "essential",
          "monthly_spending": "1898.32",
          "lowest": {
            "baseline": "7.37",
            "scenario": "7.28",
            "delta": "-0.09"
          },
          "at_end": {
            "baseline": "8.32",
            "scenario": "8.32",
            "delta": "0.00"
          }
        },
        "fi": {
          "fi_number": {
            "baseline": "714042.04",
            "scenario": "714042.04",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2044-08",
            "scenario": "2044-09",
            "delta_months": 1
          },
          "months_gained": -1
        },
        "break_evens": [],
        "tax": {
          "status": "none",
          "reason": null,
          "years": [],
          "this_year": null,
          "change_this_year": "0.00",
          "total_change": "0.00",
          "carried_forward": false
        },
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
          "nominal_returns": null,
          "cma": null
        },
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon",
          "inflation"
        ],
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": [],
        "timeline": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Wait 6 months",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "currency": "EUR",
        "hash": "sha256:54f663454d40513a0b7efa5cbf3f89feb77e7b9ca2e20370ac312603d0e27dcd",
        "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Wait 6 months",
          "as_of": "2026-10-11",
          "horizon_years": 5,
          "changes": [
            {
              "type": "set_aside",
              "monthly": "400.00",
              "from": "2026-11-02",
              "to": "2027-04-30",
              "label": "Saving for Laptop"
            },
            {
              "type": "one_off",
              "date": "2027-05-02",
              "amount": "-2400.00",
              "account": "chk",
              "tax_role": null,
              "label": "Laptop"
            }
          ],
          "tax": null
        },
        "changes": [
          {
            "index": 0,
            "type": "set_aside",
            "label": "Saving for Laptop",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": "400.00",
            "for_good": false,
            "stopped": [],
            "holding": null
          },
          {
            "index": 1,
            "type": "one_off",
            "label": "Laptop",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": null,
            "for_good": null,
            "stopped": [],
            "holding": null
          }
        ],
        "cash": {
          "start": "2026-10-11",
          "end": "2027-10-31",
          "lowest": {
            "baseline": "13998.91",
            "scenario": "14013.25",
            "delta": "14.34"
          },
          "lowest_date": {
            "baseline": "2027-02-24",
            "scenario": "2026-11-24",
            "delta_days": -92
          },
          "at_end": {
            "baseline": "15801.47",
            "scenario": "15801.47",
            "delta": "0.00"
          },
          "safe_to_spend": {
            "baseline": "15316.35",
            "scenario": "15316.35",
            "delta": "0.00"
          },
          "safe_until": "2026-10-25",
          "accounts": [
            {
              "account_id": "chk",
              "name": "Checking",
              "currency": "EUR",
              "lowest": {
                "baseline": "6063.46",
                "scenario": "6063.46",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-15",
                "scenario": "2026-10-15",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "sav",
              "name": "Savings",
              "currency": "EUR",
              "lowest": {
                "baseline": "7800.00",
                "scenario": "7800.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "usd",
              "name": "Dollar account",
              "currency": "USD",
              "lowest": {
                "baseline": "2500.00",
                "scenario": "2500.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            }
          ],
          "below_zero": {
            "baseline": [],
            "scenario": []
          }
        },
        "monthly": [
          {
            "years": 1,
            "month": "2027-10",
            "date": "2027-10-31",
            "net_worth": {
              "baseline": "366266.13",
              "scenario": "363797.24",
              "delta": "-2468.90"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "63546.81",
              "scenario": "61077.92",
              "delta": "-2468.90"
            },
            "debts": {
              "baseline": "13082.15",
              "scenario": "13082.15",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          },
          {
            "years": 5,
            "month": "2031-10",
            "date": "2031-10-31",
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "482655.31",
              "delta": "-2896.51"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "168810.75",
              "delta": "-2896.51"
            },
            "debts": {
              "baseline": "1956.91",
              "scenario": "1956.91",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          }
        ],
        "debts": {
          "items": [
            {
              "debt_id": "debt-car",
              "name": "Car loan",
              "source": "account",
              "paid_off": {
                "baseline": "2029-05",
                "scenario": "2029-05",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "786.13",
                "scenario": "786.13",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "debt-student",
              "name": "Student loan",
              "source": "declared",
              "paid_off": {
                "baseline": "2033-03",
                "scenario": "2033-03",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "1223.12",
                "scenario": "1223.12",
                "delta": "0.00"
              }
            }
          ],
          "total_interest": {
            "baseline": "2009.25",
            "scenario": "2009.25",
            "delta": "0.00"
          },
          "debt_free": {
            "baseline": "2033-03",
            "scenario": "2033-03",
            "delta_months": 0
          }
        },
        "resilience": {
          "basis": "essential",
          "monthly_spending": "1898.32",
          "lowest": {
            "baseline": "7.37",
            "scenario": "7.38",
            "delta": "0.01"
          },
          "at_end": {
            "baseline": "8.32",
            "scenario": "8.32",
            "delta": "0.00"
          }
        },
        "fi": {
          "fi_number": {
            "baseline": "714042.04",
            "scenario": "714042.04",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2044-08",
            "scenario": "2044-09",
            "delta_months": 1
          },
          "months_gained": -1
        },
        "break_evens": [],
        "tax": {
          "status": "none",
          "reason": null,
          "years": [],
          "this_year": null,
          "change_this_year": "0.00",
          "total_change": "0.00",
          "carried_forward": false
        },
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
          "nominal_returns": null,
          "cma": null
        },
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon",
          "inflation"
        ],
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": [],
        "timeline": null
      }
    ],
    "trade": [
      {
        "option": "Pay cash",
        "against": "Spread over 12 months",
        "gains": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "363866.13",
            "other": "363738.21",
            "delta": "127.92"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "63546.81",
            "other": "61225.33",
            "delta": "2321.48"
          },
          {
            "figure": "monthly.1y.debts",
            "unit": "amount",
            "this": "13082.15",
            "other": "13288.59",
            "delta": "-206.44"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "483151.81",
            "other": "482585.47",
            "delta": "566.34"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "171707.25",
            "other": "168740.91",
            "delta": "2966.34"
          },
          {
            "figure": "debts.total_interest",
            "unit": "amount",
            "this": "2009.25",
            "other": "2099.93",
            "delta": "-90.68"
          }
        ],
        "gives_up": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "11598.91",
            "other": "13821.01",
            "delta": "-2222.10"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "6.11",
            "other": "7.28",
            "delta": "-1.17"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "13401.47",
            "other": "15801.47",
            "delta": "-2400.00"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "13401.47",
            "other": "15801.47",
            "delta": "-2400.00"
          }
        ]
      },
      {
        "option": "Pay cash",
        "against": "Wait 6 months",
        "gains": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "363866.13",
            "other": "363797.24",
            "delta": "68.90"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "63546.81",
            "other": "61077.92",
            "delta": "2468.90"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "483151.81",
            "other": "482655.31",
            "delta": "496.51"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "171707.25",
            "other": "168810.75",
            "delta": "2896.51"
          }
        ],
        "gives_up": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "11598.91",
            "other": "14013.25",
            "delta": "-2414.34"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "6.11",
            "other": "7.38",
            "delta": "-1.27"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "13401.47",
            "other": "15801.47",
            "delta": "-2400.00"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "13401.47",
            "other": "15801.47",
            "delta": "-2400.00"
          }
        ]
      },
      {
        "option": "Spread over 12 months",
        "against": "Pay cash",
        "gains": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "13821.01",
            "other": "11598.91",
            "delta": "2222.10"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "7.28",
            "other": "6.11",
            "delta": "1.17"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "13401.47",
            "delta": "2400.00"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "13401.47",
            "delta": "2400.00"
          }
        ],
        "gives_up": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "363738.21",
            "other": "363866.13",
            "delta": "-127.92"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "61225.33",
            "other": "63546.81",
            "delta": "-2321.48"
          },
          {
            "figure": "monthly.1y.debts",
            "unit": "amount",
            "this": "13288.59",
            "other": "13082.15",
            "delta": "206.44"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "482585.47",
            "other": "483151.81",
            "delta": "-566.34"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "168740.91",
            "other": "171707.25",
            "delta": "-2966.34"
          },
          {
            "figure": "debts.total_interest",
            "unit": "amount",
            "this": "2099.93",
            "other": "2009.25",
            "delta": "90.68"
          }
        ]
      },
      {
        "option": "Spread over 12 months",
        "against": "Wait 6 months",
        "gains": [
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "61225.33",
            "other": "61077.92",
            "delta": "147.41"
          }
        ],
        "gives_up": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "13821.01",
            "other": "14013.25",
            "delta": "-192.24"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "7.28",
            "other": "7.38",
            "delta": "-0.10"
          },
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "363738.21",
            "other": "363797.24",
            "delta": "-59.03"
          },
          {
            "figure": "monthly.1y.debts",
            "unit": "amount",
            "this": "13288.59",
            "other": "13082.15",
            "delta": "206.44"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "482585.47",
            "other": "482655.31",
            "delta": "-69.84"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "168740.91",
            "other": "168810.75",
            "delta": "-69.84"
          },
          {
            "figure": "debts.total_interest",
            "unit": "amount",
            "this": "2099.93",
            "other": "2009.25",
            "delta": "90.68"
          }
        ]
      },
      {
        "option": "Wait 6 months",
        "against": "Pay cash",
        "gains": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "14013.25",
            "other": "11598.91",
            "delta": "2414.34"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "7.38",
            "other": "6.11",
            "delta": "1.27"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "13401.47",
            "delta": "2400.00"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "13401.47",
            "delta": "2400.00"
          }
        ],
        "gives_up": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "363797.24",
            "other": "363866.13",
            "delta": "-68.90"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "61077.92",
            "other": "63546.81",
            "delta": "-2468.90"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "482655.31",
            "other": "483151.81",
            "delta": "-496.51"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "168810.75",
            "other": "171707.25",
            "delta": "-2896.51"
          }
        ]
      },
      {
        "option": "Wait 6 months",
        "against": "Spread over 12 months",
        "gains": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "14013.25",
            "other": "13821.01",
            "delta": "192.24"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "7.38",
            "other": "7.28",
            "delta": "0.10"
          },
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "363797.24",
            "other": "363738.21",
            "delta": "59.03"
          },
          {
            "figure": "monthly.1y.debts",
            "unit": "amount",
            "this": "13082.15",
            "other": "13288.59",
            "delta": "-206.44"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "482655.31",
            "other": "482585.47",
            "delta": "69.84"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "168810.75",
            "other": "168740.91",
            "delta": "69.84"
          },
          {
            "figure": "debts.total_interest",
            "unit": "amount",
            "this": "2009.25",
            "other": "2099.93",
            "delta": "-90.68"
          }
        ],
        "gives_up": [
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "61077.92",
            "other": "61225.33",
            "delta": "-147.41"
          }
        ]
      }
    ],
    "sensitivity": {
      "real_returns": {
        "conservative": "0.02",
        "base": "0.04",
        "growth": "0.06"
      },
      "options": [
        {
          "option": "Pay cash",
          "conservative": {
            "net_worth": {
              "baseline": "475029.43",
              "scenario": "472629.43",
              "delta": "-2400.00"
            },
            "investments": {
              "baseline": "161184.87",
              "scenario": "161184.87",
              "delta": "0.00"
            },
            "fi_month": {
              "baseline": "2048-01",
              "scenario": "2048-02",
              "delta_months": 1
            },
            "months_gained": -1
          },
          "base": {
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "483151.81",
              "delta": "-2400.00"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "171707.25",
              "delta": "0.00"
            },
            "fi_month": {
              "baseline": "2044-08",
              "scenario": "2044-09",
              "delta_months": 1
            },
            "months_gained": -1
          },
          "growth": {
            "net_worth": {
              "baseline": "496953.13",
              "scenario": "494553.13",
              "delta": "-2400.00"
            },
            "investments": {
              "baseline": "183108.57",
              "scenario": "183108.57",
              "delta": "0.00"
            },
            "fi_month": {
              "baseline": "2042-04",
              "scenario": "2042-04",
              "delta_months": 0
            },
            "months_gained": 0
          }
        },
        {
          "option": "Spread over 12 months",
          "conservative": {
            "net_worth": {
              "baseline": "475029.43",
              "scenario": "472311.15",
              "delta": "-2718.28"
            },
            "investments": {
              "baseline": "161184.87",
              "scenario": "158466.59",
              "delta": "-2718.28"
            },
            "fi_month": {
              "baseline": "2048-01",
              "scenario": "2048-02",
              "delta_months": 1
            },
            "months_gained": -1
          },
          "base": {
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "482585.47",
              "delta": "-2966.34"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "168740.91",
              "delta": "-2966.34"
            },
            "fi_month": {
              "baseline": "2044-08",
              "scenario": "2044-09",
              "delta_months": 1
            },
            "months_gained": -1
          },
          "growth": {
            "net_worth": {
              "baseline": "496953.13",
              "scenario": "493716.45",
              "delta": "-3236.68"
            },
            "investments": {
              "baseline": "183108.57",
              "scenario": "179871.89",
              "delta": "-3236.68"
            },
            "fi_month": {
              "baseline": "2042-04",
              "scenario": "2042-05",
              "delta_months": 1
            },
            "months_gained": -1
          }
        },
        {
          "option": "Wait 6 months",
          "conservative": {
            "net_worth": {
              "baseline": "475029.43",
              "scenario": "472392.64",
              "delta": "-2636.79"
            },
            "investments": {
              "baseline": "161184.87",
              "scenario": "158548.08",
              "delta": "-2636.79"
            },
            "fi_month": {
              "baseline": "2048-01",
              "scenario": "2048-02",
              "delta_months": 1
            },
            "months_gained": -1
          },
          "base": {
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "482655.31",
              "delta": "-2896.51"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "168810.75",
              "delta": "-2896.51"
            },
            "fi_month": {
              "baseline": "2044-08",
              "scenario": "2044-09",
              "delta_months": 1
            },
            "months_gained": -1
          },
          "growth": {
            "net_worth": {
              "baseline": "496953.13",
              "scenario": "493771.80",
              "delta": "-3181.34"
            },
            "investments": {
              "baseline": "183108.57",
              "scenario": "179927.24",
              "delta": "-3181.34"
            },
            "fi_month": {
              "baseline": "2042-04",
              "scenario": "2042-05",
              "delta_months": 1
            },
            "months_gained": -1
          }
        }
      ]
    },
    "break_evens": [
      {
        "kind": "loan_rate",
        "options": [
          "Pay cash",
          "Spread over 12 months"
        ],
        "option": "Spread over 12 months",
        "change": 1,
        "status": "none_in_range",
        "unit": "rate",
        "value": null,
        "low": "0",
        "high": "1",
        "ahead": "Pay cash",
        "says": "Pay cash ends the horizon with more net worth than Spread over 12 months at every loan rate from 0% to 100%."
      },
      {
        "kind": "loan_rate",
        "options": [
          "Spread over 12 months",
          "Wait 6 months"
        ],
        "option": "Spread over 12 months",
        "change": 1,
        "status": "found",
        "unit": "rate",
        "value": "0.0245",
        "low": "0",
        "high": "1",
        "ahead": null,
        "says": "At a loan rate of 2.45% or less, Spread over 12 months ends the horizon with at least Wait 6 months's net worth; above it, Wait 6 months costs less."
      }
    ]
  },
  "principles": {
    "principles": [
      {
        "id": "00002331-5a11-4000-8000-000000009009",
        "label": "Six months of essentials in cash",
        "check": "emergency_months >= 6",
        "account": null,
        "version": 1,
        "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
      },
      {
        "id": "00002333-5a11-4000-8000-000000009011",
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
          "principle_id": "00002331-5a11-4000-8000-000000009009",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
          "figures": {
            "emergency_months": "7.37"
          }
        },
        {
          "principle_id": "00002333-5a11-4000-8000-000000009011",
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
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 6.11.",
            "figures": {
              "emergency_months": "6.11"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
            "label": "Checking above 5,000",
            "status": "breaks",
            "reason": "account_lowest >= 5000 doesn't hold: account_lowest is 4883.77.",
            "figures": {
              "account_lowest": "4883.77"
            }
          }
        ],
        "label": "Pay cash",
        "scenario_hash": "sha256:9b094ea3ce715a3e72c3351d3125a932f6182e9a6d202e422b1facc0787702e4"
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
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.28.",
            "figures": {
              "emergency_months": "7.28"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
            "label": "Checking above 5,000",
            "status": "keeps",
            "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
            "figures": {
              "account_lowest": "6063.46"
            }
          }
        ],
        "label": "Spread over 12 months",
        "scenario_hash": "sha256:65aea5213bff9c2365ddf72f441301d3eebd8e577b5afbaa316f4a26e6f28a00"
      },
      {
        "figures": {
          "lowest_cash": "14013.25",
          "cash_in_12_months": "15801.47",
          "safe_to_spend": "15316.35",
          "any_account_below_zero": false,
          "monthly_spending": "1898.32",
          "emergency_months": "7.38",
          "emergency_months_in_12_months": "8.32",
          "net_worth_1y": "363797.24",
          "net_worth_5y": "482655.31",
          "net_worth_10y": "660842.88",
          "net_worth_20y": "1144076.69",
          "cash_1y": "15801.47",
          "cash_5y": "15801.47",
          "cash_10y": "15801.47",
          "cash_20y": "15801.47",
          "investments_1y": "61077.92",
          "investments_5y": "168810.75",
          "investments_10y": "345041.41",
          "investments_20y": "828275.22",
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
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.38.",
            "figures": {
              "emergency_months": "7.38"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
            "label": "Checking above 5,000",
            "status": "keeps",
            "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
            "figures": {
              "account_lowest": "6063.46"
            }
          }
        ],
        "label": "Wait 6 months",
        "scenario_hash": "sha256:54f663454d40513a0b7efa5cbf3f89feb77e7b9ca2e20370ac312603d0e27dcd"
      }
    ]
  },
  "cover": null,
  "level": null,
  "odds": null,
  "placeholders": [
    "real_return",
    "safe_withdrawal_rate",
    "surplus_invested",
    "drawdown_horizon",
    "inflation"
  ],
  "data_as_of": "2026-10-09",
  "is_stale": false,
  "notes": [],
  "record": {
    "question": "Can I afford Laptop (2400.00 EUR), and how would I pay for it?",
    "options": [
      {
        "schema": "salli.scenario/1",
        "label": "Pay cash",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "one_off",
            "date": "2026-11-02",
            "amount": "-2400.00",
            "account": "chk",
            "tax_role": null,
            "label": "Laptop"
          }
        ],
        "tax": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Spread over 12 months",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "one_off",
            "date": "2026-11-02",
            "amount": "-2400.00",
            "account": "chk",
            "tax_role": null,
            "label": "Laptop"
          },
          {
            "type": "loan",
            "principal": "2400.00",
            "annual_rate": "0.069",
            "term_months": 12,
            "start": "2026-11-02",
            "into": "chk",
            "label": "Laptop, over 12 months"
          }
        ],
        "tax": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Wait 6 months",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "set_aside",
            "monthly": "400.00",
            "from": "2026-11-02",
            "to": "2027-04-30",
            "label": "Saving for Laptop"
          },
          {
            "type": "one_off",
            "date": "2027-05-02",
            "amount": "-2400.00",
            "account": "chk",
            "tax_role": null,
            "label": "Laptop"
          }
        ],
        "tax": null
      }
    ],
    "labels": [
      "Pay cash",
      "Spread over 12 months",
      "Wait 6 months"
    ],
    "earliest_review": "2026-10-31"
  },
  "says": "Salli computed every figure here and ranks none of the options: what matters most is the person's to weigh. To record what they choose, call record_decision (POST /v1/decisions) with `record.question` (theirs to change), `record.options`, the label they chose, their reasons in their own words and a review date, once they confirm."
};

/**
 * Keep renting from City Lettings, or buy a home for 350,000.00 with
 * 70,000.00 down on either of two mortgages.
 */
export const RENT_OR_BUY_START: DecisionStart = {
  "schema": "salli.decision-start/1",
  "template": {
    "id": "rent-or-buy",
    "title": "Rent or buy"
  },
  "as_of": "2026-10-11",
  "currency": "EUR",
  "horizon_years": 20,
  "question": "Keep renting, or buy a home for 350000.00 EUR?",
  "answers": [
    {
      "id": "price",
      "value": "350000.00",
      "source": "given",
      "note": null
    },
    {
      "id": "date",
      "value": "2026-11-01",
      "source": "next_month",
      "note": "the first of next month"
    },
    {
      "id": "deposit",
      "value": "70000.00",
      "source": "given",
      "note": null
    },
    {
      "id": "account",
      "value": "chk",
      "source": "given",
      "note": null
    },
    {
      "id": "mortgages",
      "value": [
        {
          "annual_rate": "0.042",
          "term_months": 300
        },
        {
          "annual_rate": "0.039",
          "term_months": 240,
          "label": "Shorter"
        }
      ],
      "source": "given",
      "note": null
    },
    {
      "id": "buying_costs",
      "value": "9000.00",
      "source": "given",
      "note": null
    },
    {
      "id": "owning_costs",
      "value": "250.00",
      "source": "given",
      "note": null
    },
    {
      "id": "rent",
      "value": "city",
      "source": "given",
      "note": null
    },
    {
      "id": "rent_growth",
      "value": "0",
      "source": "placeholder",
      "note": "a placeholder, not a forecast: set your own view"
    },
    {
      "id": "home_growth",
      "value": "0",
      "source": "placeholder",
      "note": "a placeholder, not a forecast: set your own view"
    },
    {
      "id": "selling_costs",
      "value": "0.03",
      "source": "given",
      "note": null
    },
    {
      "id": "horizon_years",
      "value": 20,
      "source": "salli",
      "note": "Salli's usual horizon for long-run figures"
    }
  ],
  "options": [
    {
      "label": "Keep renting",
      "describes": "Rent to City Lettings Rent goes on: 1500.00 EUR a month from 2026-11-01, growing 0% a year beyond inflation (a placeholder).",
      "scenario": {
        "schema": "salli.scenario/1",
        "label": "Keep renting",
        "as_of": "2026-10-11",
        "horizon_years": 20,
        "changes": [
          {
            "type": "stop_recurring",
            "key": "city",
            "from": "2026-11-01",
            "label": "Rent as it is"
          },
          {
            "type": "recurring",
            "amount": "-1500.00",
            "cadence": "monthly",
            "start": "2026-11-01",
            "end": null,
            "account": "chk",
            "tax_role": null,
            "real_growth": null,
            "label": "Rent: City Lettings Rent"
          }
        ],
        "tax": null
      },
      "scenario_hash": "sha256:a38af0bb404f2972faa76d45ea52e0d9dc177924d5ef50d5f98a2109a3fce5e2"
    },
    {
      "label": "Buy, 4.2% over 300 months",
      "describes": "350000.00 EUR on 2026-11-01: 70000.00 EUR down from cash and a mortgage of 280000.00 EUR at 4.2% a year over 300 months; 9000.00 EUR of buying costs once and 250.00 EUR a month of owning costs; the home growing 0% a year beyond inflation (a placeholder), counted at its value less 3% selling costs; the rent stopped from that day.",
      "scenario": {
        "schema": "salli.scenario/1",
        "label": "Buy, 4.2% over 300 months",
        "as_of": "2026-10-11",
        "horizon_years": 20,
        "changes": [
          {
            "type": "asset",
            "price": "350000.00",
            "date": "2026-11-01",
            "from": "chk",
            "real_growth": null,
            "selling_costs": "0.03",
            "label": "The home"
          },
          {
            "type": "loan",
            "principal": "280000.00",
            "annual_rate": "0.042",
            "term_months": 300,
            "start": "2026-11-01",
            "into": "chk",
            "label": "Mortgage, 4.2% over 300 months"
          },
          {
            "type": "one_off",
            "date": "2026-11-01",
            "amount": "-9000.00",
            "account": "chk",
            "tax_role": null,
            "label": "Buying costs"
          },
          {
            "type": "recurring",
            "amount": "-250.00",
            "cadence": "monthly",
            "start": "2026-11-01",
            "end": null,
            "account": "chk",
            "tax_role": null,
            "real_growth": null,
            "label": "Owning costs"
          },
          {
            "type": "stop_recurring",
            "key": "city",
            "from": "2026-11-01",
            "label": "Rent stopped"
          }
        ],
        "tax": null
      },
      "scenario_hash": "sha256:0af1ac5745d12490dbd159af6a6910e6d52c8b3db2f78c4f3f8a280fcb9edb76"
    },
    {
      "label": "Buy, Shorter",
      "describes": "350000.00 EUR on 2026-11-01: 70000.00 EUR down from cash and a mortgage of 280000.00 EUR at 3.9% a year over 240 months; 9000.00 EUR of buying costs once and 250.00 EUR a month of owning costs; the home growing 0% a year beyond inflation (a placeholder), counted at its value less 3% selling costs; the rent stopped from that day.",
      "scenario": {
        "schema": "salli.scenario/1",
        "label": "Buy, Shorter",
        "as_of": "2026-10-11",
        "horizon_years": 20,
        "changes": [
          {
            "type": "asset",
            "price": "350000.00",
            "date": "2026-11-01",
            "from": "chk",
            "real_growth": null,
            "selling_costs": "0.03",
            "label": "The home"
          },
          {
            "type": "loan",
            "principal": "280000.00",
            "annual_rate": "0.039",
            "term_months": 240,
            "start": "2026-11-01",
            "into": "chk",
            "label": "Shorter"
          },
          {
            "type": "one_off",
            "date": "2026-11-01",
            "amount": "-9000.00",
            "account": "chk",
            "tax_role": null,
            "label": "Buying costs"
          },
          {
            "type": "recurring",
            "amount": "-250.00",
            "cadence": "monthly",
            "start": "2026-11-01",
            "end": null,
            "account": "chk",
            "tax_role": null,
            "real_growth": null,
            "label": "Owning costs"
          },
          {
            "type": "stop_recurring",
            "key": "city",
            "from": "2026-11-01",
            "label": "Rent stopped"
          }
        ],
        "tax": null
      },
      "scenario_hash": "sha256:5b9235fada31e82c65a399683f460ef60632ca23a2e83c17a468f123c9809e38"
    }
  ],
  "comparison": {
    "as_of": "2026-10-11",
    "horizon_years": 20,
    "currency": "EUR",
    "labels": [
      "Keep renting",
      "Buy, 4.2% over 300 months",
      "Buy, Shorter"
    ],
    "options": [
      {
        "schema": "salli.scenario/1",
        "label": "Keep renting",
        "as_of": "2026-10-11",
        "horizon_years": 20,
        "currency": "EUR",
        "hash": "sha256:a38af0bb404f2972faa76d45ea52e0d9dc177924d5ef50d5f98a2109a3fce5e2",
        "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Keep renting",
          "as_of": "2026-10-11",
          "horizon_years": 20,
          "changes": [
            {
              "type": "stop_recurring",
              "key": "city",
              "from": "2026-11-01",
              "label": "Rent as it is"
            },
            {
              "type": "recurring",
              "amount": "-1500.00",
              "cadence": "monthly",
              "start": "2026-11-01",
              "end": null,
              "account": "chk",
              "tax_role": null,
              "real_growth": null,
              "label": "Rent: City Lettings Rent"
            }
          ],
          "tax": null
        },
        "changes": [
          {
            "index": 0,
            "type": "stop_recurring",
            "label": "Rent as it is",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": "1500.00",
            "for_good": true,
            "stopped": [
              {
                "payee": "City Lettings Rent",
                "cadence": "monthly",
                "amount": "-1500.00",
                "currency": "EUR"
              }
            ],
            "holding": null
          },
          {
            "index": 1,
            "type": "recurring",
            "label": "Rent: City Lettings Rent",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": "-1500.00",
            "for_good": true,
            "stopped": [],
            "holding": null
          }
        ],
        "cash": {
          "start": "2026-10-11",
          "end": "2027-10-31",
          "lowest": {
            "baseline": "13998.91",
            "scenario": "13998.91",
            "delta": "0.00"
          },
          "lowest_date": {
            "baseline": "2027-02-24",
            "scenario": "2027-02-24",
            "delta_days": 0
          },
          "at_end": {
            "baseline": "15801.47",
            "scenario": "15801.47",
            "delta": "0.00"
          },
          "safe_to_spend": {
            "baseline": "15316.35",
            "scenario": "15316.35",
            "delta": "0.00"
          },
          "safe_until": "2026-10-25",
          "accounts": [
            {
              "account_id": "chk",
              "name": "Checking",
              "currency": "EUR",
              "lowest": {
                "baseline": "6063.46",
                "scenario": "6063.46",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-15",
                "scenario": "2026-10-15",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "sav",
              "name": "Savings",
              "currency": "EUR",
              "lowest": {
                "baseline": "7800.00",
                "scenario": "7800.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "usd",
              "name": "Dollar account",
              "currency": "USD",
              "lowest": {
                "baseline": "2500.00",
                "scenario": "2500.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            }
          ],
          "below_zero": {
            "baseline": [],
            "scenario": []
          }
        },
        "monthly": [
          {
            "years": 1,
            "month": "2027-10",
            "date": "2027-10-31",
            "net_worth": {
              "baseline": "366266.13",
              "scenario": "366266.13",
              "delta": "0.00"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "63546.81",
              "scenario": "63546.81",
              "delta": "0.00"
            },
            "debts": {
              "baseline": "13082.15",
              "scenario": "13082.15",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          },
          {
            "years": 5,
            "month": "2031-10",
            "date": "2031-10-31",
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "485551.81",
              "delta": "0.00"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "171707.25",
              "delta": "0.00"
            },
            "debts": {
              "baseline": "1956.91",
              "scenario": "1956.91",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          },
          {
            "years": 10,
            "month": "2036-10",
            "date": "2036-10-31",
            "net_worth": {
              "baseline": "664379.50",
              "scenario": "664379.50",
              "delta": "0.00"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "348578.03",
              "scenario": "348578.03",
              "delta": "0.00"
            },
            "debts": {
              "baseline": "0.00",
              "scenario": "0.00",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          },
          {
            "years": 20,
            "month": "2046-10",
            "date": "2046-10-31",
            "net_worth": {
              "baseline": "1149349.20",
              "scenario": "1149349.20",
              "delta": "0.00"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "833547.73",
              "scenario": "833547.73",
              "delta": "0.00"
            },
            "debts": {
              "baseline": "0.00",
              "scenario": "0.00",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          }
        ],
        "debts": {
          "items": [
            {
              "debt_id": "debt-car",
              "name": "Car loan",
              "source": "account",
              "paid_off": {
                "baseline": "2029-05",
                "scenario": "2029-05",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "786.13",
                "scenario": "786.13",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "debt-student",
              "name": "Student loan",
              "source": "declared",
              "paid_off": {
                "baseline": "2033-03",
                "scenario": "2033-03",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "1223.12",
                "scenario": "1223.12",
                "delta": "0.00"
              }
            }
          ],
          "total_interest": {
            "baseline": "2009.25",
            "scenario": "2009.25",
            "delta": "0.00"
          },
          "debt_free": {
            "baseline": "2033-03",
            "scenario": "2033-03",
            "delta_months": 0
          }
        },
        "resilience": {
          "basis": "essential",
          "monthly_spending": "1898.32",
          "lowest": {
            "baseline": "7.37",
            "scenario": "7.37",
            "delta": "0.00"
          },
          "at_end": {
            "baseline": "8.32",
            "scenario": "8.32",
            "delta": "0.00"
          }
        },
        "fi": {
          "fi_number": {
            "baseline": "714042.04",
            "scenario": "714042.04",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2044-08",
            "scenario": "2044-08",
            "delta_months": 0
          },
          "months_gained": 0
        },
        "break_evens": [],
        "tax": {
          "status": "none",
          "reason": null,
          "years": [],
          "this_year": null,
          "change_this_year": "0.00",
          "total_change": "0.00",
          "carried_forward": false
        },
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
          "nominal_returns": null,
          "cma": null
        },
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon",
          "inflation"
        ],
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": [],
        "timeline": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Buy, 4.2% over 300 months",
        "as_of": "2026-10-11",
        "horizon_years": 20,
        "currency": "EUR",
        "hash": "sha256:0af1ac5745d12490dbd159af6a6910e6d52c8b3db2f78c4f3f8a280fcb9edb76",
        "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Buy, 4.2% over 300 months",
          "as_of": "2026-10-11",
          "horizon_years": 20,
          "changes": [
            {
              "type": "asset",
              "price": "350000.00",
              "date": "2026-11-01",
              "from": "chk",
              "real_growth": null,
              "selling_costs": "0.03",
              "label": "The home"
            },
            {
              "type": "loan",
              "principal": "280000.00",
              "annual_rate": "0.042",
              "term_months": 300,
              "start": "2026-11-01",
              "into": "chk",
              "label": "Mortgage, 4.2% over 300 months"
            },
            {
              "type": "one_off",
              "date": "2026-11-01",
              "amount": "-9000.00",
              "account": "chk",
              "tax_role": null,
              "label": "Buying costs"
            },
            {
              "type": "recurring",
              "amount": "-250.00",
              "cadence": "monthly",
              "start": "2026-11-01",
              "end": null,
              "account": "chk",
              "tax_role": null,
              "real_growth": null,
              "label": "Owning costs"
            },
            {
              "type": "stop_recurring",
              "key": "city",
              "from": "2026-11-01",
              "label": "Rent stopped"
            }
          ],
          "tax": null
        },
        "changes": [
          {
            "index": 0,
            "type": "asset",
            "label": "The home",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": null,
            "for_good": null,
            "stopped": [],
            "holding": null
          },
          {
            "index": 1,
            "type": "loan",
            "label": "Mortgage, 4.2% over 300 months",
            "debt_id": "scenario-loan-2",
            "payment": "1509.04",
            "first_payment": "2026-12",
            "monthly": null,
            "for_good": null,
            "stopped": [],
            "holding": null
          },
          {
            "index": 2,
            "type": "one_off",
            "label": "Buying costs",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": null,
            "for_good": null,
            "stopped": [],
            "holding": null
          },
          {
            "index": 3,
            "type": "recurring",
            "label": "Owning costs",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": "-250.00",
            "for_good": true,
            "stopped": [],
            "holding": null
          },
          {
            "index": 4,
            "type": "stop_recurring",
            "label": "Rent stopped",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": "1500.00",
            "for_good": true,
            "stopped": [
              {
                "payee": "City Lettings Rent",
                "cadence": "monthly",
                "amount": "-1500.00",
                "currency": "EUR"
              }
            ],
            "holding": null
          }
        ],
        "cash": {
          "start": "2026-10-11",
          "end": "2027-10-31",
          "lowest": {
            "baseline": "13998.91",
            "scenario": "-65044.55",
            "delta": "-79043.46"
          },
          "lowest_date": {
            "baseline": "2027-02-24",
            "scenario": "2027-02-24",
            "delta_days": 0
          },
          "at_end": {
            "baseline": "15801.47",
            "scenario": "-63198.53",
            "delta": "-79000.00"
          },
          "safe_to_spend": {
            "baseline": "15316.35",
            "scenario": "15316.35",
            "delta": "0.00"
          },
          "safe_until": "2026-10-25",
          "accounts": [
            {
              "account_id": "chk",
              "name": "Checking",
              "currency": "EUR",
              "lowest": {
                "baseline": "6063.46",
                "scenario": "-70466.23",
                "delta": "-76529.69"
              },
              "lowest_date": {
                "baseline": "2026-10-15",
                "scenario": "2026-11-15",
                "delta_days": 31
              },
              "below_zero": {
                "baseline": false,
                "scenario": true
              }
            },
            {
              "account_id": "sav",
              "name": "Savings",
              "currency": "EUR",
              "lowest": {
                "baseline": "7800.00",
                "scenario": "7800.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "usd",
              "name": "Dollar account",
              "currency": "USD",
              "lowest": {
                "baseline": "2500.00",
                "scenario": "2500.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            }
          ],
          "below_zero": {
            "baseline": [],
            "scenario": [
              "chk"
            ]
          }
        },
        "monthly": [
          {
            "years": 1,
            "month": "2027-10",
            "date": "2027-10-31",
            "net_worth": {
              "baseline": "366266.13",
              "scenario": "351087.69",
              "delta": "-15178.44"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "-63198.53",
              "delta": "-79000.00"
            },
            "investments": {
              "baseline": "63546.81",
              "scenario": "61946.01",
              "delta": "-1600.80"
            },
            "debts": {
              "baseline": "13082.15",
              "scenario": "287159.79",
              "delta": "274077.64"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "639500.00",
              "delta": "339500.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "650000.00",
              "delta": "350000.00"
            }
          },
          {
            "years": 5,
            "month": "2031-10",
            "date": "2031-10-31",
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "485317.06",
              "delta": "-234.76"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "-63198.53",
              "delta": "-79000.00"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "156369.58",
              "delta": "-15337.68"
            },
            "debts": {
              "baseline": "1956.91",
              "scenario": "247353.99",
              "delta": "245397.08"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "639500.00",
              "delta": "339500.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "650000.00",
              "delta": "350000.00"
            }
          },
          {
            "years": 10,
            "month": "2036-10",
            "date": "2036-10-31",
            "net_worth": {
              "baseline": "664379.50",
              "scenario": "686904.46",
              "delta": "22524.96"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "-63198.53",
              "delta": "-79000.00"
            },
            "investments": {
              "baseline": "348578.03",
              "scenario": "312676.69",
              "delta": "-35901.34"
            },
            "debts": {
              "baseline": "0.00",
              "scenario": "202073.70",
              "delta": "202073.70"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "639500.00",
              "delta": "339500.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "650000.00",
              "delta": "350000.00"
            }
          },
          {
            "years": 20,
            "month": "2046-10",
            "date": "2046-10-31",
            "net_worth": {
              "baseline": "1149349.20",
              "scenario": "1235424.78",
              "delta": "86075.58"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "-63198.53",
              "delta": "-79000.00"
            },
            "investments": {
              "baseline": "833547.73",
              "scenario": "741881.25",
              "delta": "-91666.48"
            },
            "debts": {
              "baseline": "0.00",
              "scenario": "82757.94",
              "delta": "82757.94"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "639500.00",
              "delta": "339500.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "650000.00",
              "delta": "350000.00"
            }
          }
        ],
        "debts": {
          "items": [
            {
              "debt_id": "debt-car",
              "name": "Car loan",
              "source": "account",
              "paid_off": {
                "baseline": "2029-05",
                "scenario": "2029-05",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "786.13",
                "scenario": "786.13",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "debt-student",
              "name": "Student loan",
              "source": "declared",
              "paid_off": {
                "baseline": "2033-03",
                "scenario": "2033-03",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "1223.12",
                "scenario": "1223.12",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "scenario-loan-2",
              "name": "Mortgage, 4.2% over 300 months",
              "source": "scenario",
              "paid_off": {
                "baseline": null,
                "scenario": "2051-11",
                "delta_months": null
              },
              "total_interest": {
                "baseline": "0.00",
                "scenario": "172711.09",
                "delta": "172711.09"
              }
            }
          ],
          "total_interest": {
            "baseline": "2009.25",
            "scenario": "174720.34",
            "delta": "172711.09"
          },
          "debt_free": {
            "baseline": "2033-03",
            "scenario": "2051-11",
            "delta_months": 224
          }
        },
        "resilience": {
          "basis": "essential",
          "monthly_spending": "1898.32",
          "lowest": {
            "baseline": "7.37",
            "scenario": "-34.26",
            "delta": "-41.64"
          },
          "at_end": {
            "baseline": "8.32",
            "scenario": "-33.29",
            "delta": "-41.62"
          }
        },
        "fi": {
          "fi_number": {
            "baseline": "714042.04",
            "scenario": "236335.03",
            "delta": "-477707.01"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "787.09",
            "delta": "-1250.00"
          },
          "fi_month": {
            "baseline": "2044-08",
            "scenario": "2040-12",
            "delta_months": -44
          },
          "months_gained": 44
        },
        "break_evens": [
          {
            "kind": "recurring_cash_floor",
            "options": [
              "Buy, 4.2% over 300 months"
            ],
            "option": "Buy, 4.2% over 300 months",
            "change": 3,
            "status": "none_in_range",
            "unit": "amount",
            "value": null,
            "low": "0.00",
            "high": "250.00",
            "ahead": null,
            "says": "Cash goes below zero in the next twelve months even without this cost."
          }
        ],
        "tax": {
          "status": "none",
          "reason": null,
          "years": [],
          "this_year": null,
          "change_this_year": "0.00",
          "total_change": "0.00",
          "carried_forward": false
        },
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
          "nominal_returns": null,
          "cma": null
        },
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon",
          "inflation",
          "asset_growth"
        ],
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": [
          "Cash is below zero from the end of 2026-11: what the regular surplus doesn't cover, and what is paid from cash, is drawn from cash, never from your investments, so cash is left below zero rather than investments sold.",
          "The home counts at what it would fetch: its value less its selling costs, so net worth is lower by them from the month it is bought (other_assets_value is its value before them)."
        ],
        "timeline": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Buy, Shorter",
        "as_of": "2026-10-11",
        "horizon_years": 20,
        "currency": "EUR",
        "hash": "sha256:5b9235fada31e82c65a399683f460ef60632ca23a2e83c17a468f123c9809e38",
        "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Buy, Shorter",
          "as_of": "2026-10-11",
          "horizon_years": 20,
          "changes": [
            {
              "type": "asset",
              "price": "350000.00",
              "date": "2026-11-01",
              "from": "chk",
              "real_growth": null,
              "selling_costs": "0.03",
              "label": "The home"
            },
            {
              "type": "loan",
              "principal": "280000.00",
              "annual_rate": "0.039",
              "term_months": 240,
              "start": "2026-11-01",
              "into": "chk",
              "label": "Shorter"
            },
            {
              "type": "one_off",
              "date": "2026-11-01",
              "amount": "-9000.00",
              "account": "chk",
              "tax_role": null,
              "label": "Buying costs"
            },
            {
              "type": "recurring",
              "amount": "-250.00",
              "cadence": "monthly",
              "start": "2026-11-01",
              "end": null,
              "account": "chk",
              "tax_role": null,
              "real_growth": null,
              "label": "Owning costs"
            },
            {
              "type": "stop_recurring",
              "key": "city",
              "from": "2026-11-01",
              "label": "Rent stopped"
            }
          ],
          "tax": null
        },
        "changes": [
          {
            "index": 0,
            "type": "asset",
            "label": "The home",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": null,
            "for_good": null,
            "stopped": [],
            "holding": null
          },
          {
            "index": 1,
            "type": "loan",
            "label": "Shorter",
            "debt_id": "scenario-loan-2",
            "payment": "1682.03",
            "first_payment": "2026-12",
            "monthly": null,
            "for_good": null,
            "stopped": [],
            "holding": null
          },
          {
            "index": 2,
            "type": "one_off",
            "label": "Buying costs",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": null,
            "for_good": null,
            "stopped": [],
            "holding": null
          },
          {
            "index": 3,
            "type": "recurring",
            "label": "Owning costs",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": "-250.00",
            "for_good": true,
            "stopped": [],
            "holding": null
          },
          {
            "index": 4,
            "type": "stop_recurring",
            "label": "Rent stopped",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": "1500.00",
            "for_good": true,
            "stopped": [
              {
                "payee": "City Lettings Rent",
                "cadence": "monthly",
                "amount": "-1500.00",
                "currency": "EUR"
              }
            ],
            "holding": null
          }
        ],
        "cash": {
          "start": "2026-10-11",
          "end": "2027-10-31",
          "lowest": {
            "baseline": "13998.91",
            "scenario": "-65192.83",
            "delta": "-79191.74"
          },
          "lowest_date": {
            "baseline": "2027-02-24",
            "scenario": "2027-02-24",
            "delta_days": 0
          },
          "at_end": {
            "baseline": "15801.47",
            "scenario": "-63198.53",
            "delta": "-79000.00"
          },
          "safe_to_spend": {
            "baseline": "15316.35",
            "scenario": "15316.35",
            "delta": "0.00"
          },
          "safe_until": "2026-10-25",
          "accounts": [
            {
              "account_id": "chk",
              "name": "Checking",
              "currency": "EUR",
              "lowest": {
                "baseline": "6063.46",
                "scenario": "-70466.23",
                "delta": "-76529.69"
              },
              "lowest_date": {
                "baseline": "2026-10-15",
                "scenario": "2026-11-15",
                "delta_days": 31
              },
              "below_zero": {
                "baseline": false,
                "scenario": true
              }
            },
            {
              "account_id": "sav",
              "name": "Savings",
              "currency": "EUR",
              "lowest": {
                "baseline": "7800.00",
                "scenario": "7800.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "usd",
              "name": "Dollar account",
              "currency": "USD",
              "lowest": {
                "baseline": "2500.00",
                "scenario": "2500.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            }
          ],
          "below_zero": {
            "baseline": [],
            "scenario": [
              "chk"
            ]
          }
        },
        "monthly": [
          {
            "years": 1,
            "month": "2027-10",
            "date": "2027-10-31",
            "net_worth": {
              "baseline": "366266.13",
              "scenario": "351862.11",
              "delta": "-14404.03"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "-63198.53",
              "delta": "-79000.00"
            },
            "investments": {
              "baseline": "63546.81",
              "scenario": "60011.09",
              "delta": "-3535.73"
            },
            "debts": {
              "baseline": "13082.15",
              "scenario": "284450.45",
              "delta": "271368.30"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "639500.00",
              "delta": "339500.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "650000.00",
              "delta": "350000.00"
            }
          },
          {
            "years": 5,
            "month": "2031-10",
            "date": "2031-10-31",
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "489576.06",
              "delta": "4024.24"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "-63198.53",
              "delta": "-79000.00"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "145111.04",
              "delta": "-26596.22"
            },
            "debts": {
              "baseline": "1956.91",
              "scenario": "231836.45",
              "delta": "229879.54"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "639500.00",
              "delta": "339500.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "650000.00",
              "delta": "350000.00"
            }
          },
          {
            "years": 10,
            "month": "2036-10",
            "date": "2036-10-31",
            "net_worth": {
              "baseline": "664379.50",
              "scenario": "695710.48",
              "delta": "31330.98"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "-63198.53",
              "delta": "-79000.00"
            },
            "investments": {
              "baseline": "348578.03",
              "scenario": "287460.99",
              "delta": "-61117.04"
            },
            "debts": {
              "baseline": "0.00",
              "scenario": "168051.98",
              "delta": "168051.98"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "639500.00",
              "delta": "339500.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "650000.00",
              "delta": "350000.00"
            }
          },
          {
            "years": 20,
            "month": "2046-10",
            "date": "2046-10-31",
            "net_worth": {
              "baseline": "1149349.20",
              "scenario": "1253442.02",
              "delta": "104092.82"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "-63198.53",
              "delta": "-79000.00"
            },
            "investments": {
              "baseline": "833547.73",
              "scenario": "678816.12",
              "delta": "-154731.61"
            },
            "debts": {
              "baseline": "0.00",
              "scenario": "1675.57",
              "delta": "1675.57"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "639500.00",
              "delta": "339500.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "650000.00",
              "delta": "350000.00"
            }
          }
        ],
        "debts": {
          "items": [
            {
              "debt_id": "debt-car",
              "name": "Car loan",
              "source": "account",
              "paid_off": {
                "baseline": "2029-05",
                "scenario": "2029-05",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "786.13",
                "scenario": "786.13",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "debt-student",
              "name": "Student loan",
              "source": "declared",
              "paid_off": {
                "baseline": "2033-03",
                "scenario": "2033-03",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "1223.12",
                "scenario": "1223.12",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "scenario-loan-2",
              "name": "Shorter",
              "source": "scenario",
              "paid_off": {
                "baseline": null,
                "scenario": "2046-11",
                "delta_months": null
              },
              "total_interest": {
                "baseline": "0.00",
                "scenario": "123686.19",
                "delta": "123686.19"
              }
            }
          ],
          "total_interest": {
            "baseline": "2009.25",
            "scenario": "125695.44",
            "delta": "123686.19"
          },
          "debt_free": {
            "baseline": "2033-03",
            "scenario": "2046-11",
            "delta_months": 164
          }
        },
        "resilience": {
          "basis": "essential",
          "monthly_spending": "1898.32",
          "lowest": {
            "baseline": "7.37",
            "scenario": "-34.34",
            "delta": "-41.72"
          },
          "at_end": {
            "baseline": "8.32",
            "scenario": "-33.29",
            "delta": "-41.62"
          }
        },
        "fi": {
          "fi_number": {
            "baseline": "714042.04",
            "scenario": "236335.03",
            "delta": "-477707.01"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "787.09",
            "delta": "-1250.00"
          },
          "fi_month": {
            "baseline": "2044-08",
            "scenario": "2040-09",
            "delta_months": -47
          },
          "months_gained": 47
        },
        "break_evens": [
          {
            "kind": "recurring_cash_floor",
            "options": [
              "Buy, Shorter"
            ],
            "option": "Buy, Shorter",
            "change": 3,
            "status": "none_in_range",
            "unit": "amount",
            "value": null,
            "low": "0.00",
            "high": "250.00",
            "ahead": null,
            "says": "Cash goes below zero in the next twelve months even without this cost."
          }
        ],
        "tax": {
          "status": "none",
          "reason": null,
          "years": [],
          "this_year": null,
          "change_this_year": "0.00",
          "total_change": "0.00",
          "carried_forward": false
        },
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
          "nominal_returns": null,
          "cma": null
        },
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon",
          "inflation",
          "asset_growth"
        ],
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": [
          "Cash is below zero from the end of 2026-11: what the regular surplus doesn't cover, and what is paid from cash, is drawn from cash, never from your investments, so cash is left below zero rather than investments sold.",
          "The home counts at what it would fetch: its value less its selling costs, so net worth is lower by them from the month it is bought (other_assets_value is its value before them)."
        ],
        "timeline": null
      }
    ],
    "trade": [
      {
        "option": "Keep renting",
        "against": "Buy, 4.2% over 300 months",
        "gains": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "13998.91",
            "other": "-65044.55",
            "delta": "79043.46"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "7.37",
            "other": "-34.26",
            "delta": "41.64"
          },
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "366266.13",
            "other": "351087.69",
            "delta": "15178.44"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "-63198.53",
            "delta": "79000.00"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "63546.81",
            "other": "61946.01",
            "delta": "1600.80"
          },
          {
            "figure": "monthly.1y.debts",
            "unit": "amount",
            "this": "13082.15",
            "other": "287159.79",
            "delta": "-274077.64"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "485551.81",
            "other": "485317.06",
            "delta": "234.76"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "-63198.53",
            "delta": "79000.00"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "171707.25",
            "other": "156369.58",
            "delta": "15337.68"
          },
          {
            "figure": "monthly.5y.debts",
            "unit": "amount",
            "this": "1956.91",
            "other": "247353.99",
            "delta": "-245397.08"
          },
          {
            "figure": "monthly.10y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "-63198.53",
            "delta": "79000.00"
          },
          {
            "figure": "monthly.10y.investments",
            "unit": "amount",
            "this": "348578.03",
            "other": "312676.69",
            "delta": "35901.34"
          },
          {
            "figure": "monthly.10y.debts",
            "unit": "amount",
            "this": "0.00",
            "other": "202073.70",
            "delta": "-202073.70"
          },
          {
            "figure": "monthly.20y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "-63198.53",
            "delta": "79000.00"
          },
          {
            "figure": "monthly.20y.investments",
            "unit": "amount",
            "this": "833547.73",
            "other": "741881.25",
            "delta": "91666.48"
          },
          {
            "figure": "monthly.20y.debts",
            "unit": "amount",
            "this": "0.00",
            "other": "82757.94",
            "delta": "-82757.94"
          },
          {
            "figure": "debts.total_interest",
            "unit": "amount",
            "this": "2009.25",
            "other": "174720.34",
            "delta": "-172711.09"
          },
          {
            "figure": "debts.debt_free",
            "unit": "month",
            "this": "2033-03",
            "other": "2051-11",
            "delta": -224
          }
        ],
        "gives_up": [
          {
            "figure": "monthly.1y.other_assets",
            "unit": "amount",
            "this": "300000.00",
            "other": "639500.00",
            "delta": "-339500.00"
          },
          {
            "figure": "monthly.5y.other_assets",
            "unit": "amount",
            "this": "300000.00",
            "other": "639500.00",
            "delta": "-339500.00"
          },
          {
            "figure": "monthly.10y.net_worth",
            "unit": "amount",
            "this": "664379.50",
            "other": "686904.46",
            "delta": "-22524.96"
          },
          {
            "figure": "monthly.10y.other_assets",
            "unit": "amount",
            "this": "300000.00",
            "other": "639500.00",
            "delta": "-339500.00"
          },
          {
            "figure": "monthly.20y.net_worth",
            "unit": "amount",
            "this": "1149349.20",
            "other": "1235424.78",
            "delta": "-86075.58"
          },
          {
            "figure": "monthly.20y.other_assets",
            "unit": "amount",
            "this": "300000.00",
            "other": "639500.00",
            "delta": "-339500.00"
          },
          {
            "figure": "fi.fi_number",
            "unit": "amount",
            "this": "714042.04",
            "other": "236335.03",
            "delta": "477707.01"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2044-08",
            "other": "2040-12",
            "delta": 44
          }
        ]
      },
      {
        "option": "Keep renting",
        "against": "Buy, Shorter",
        "gains": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "13998.91",
            "other": "-65192.83",
            "delta": "79191.74"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "7.37",
            "other": "-34.34",
            "delta": "41.72"
          },
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "366266.13",
            "other": "351862.11",
            "delta": "14404.03"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "-63198.53",
            "delta": "79000.00"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "63546.81",
            "other": "60011.09",
            "delta": "3535.73"
          },
          {
            "figure": "monthly.1y.debts",
            "unit": "amount",
            "this": "13082.15",
            "other": "284450.45",
            "delta": "-271368.30"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "-63198.53",
            "delta": "79000.00"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "171707.25",
            "other": "145111.04",
            "delta": "26596.22"
          },
          {
            "figure": "monthly.5y.debts",
            "unit": "amount",
            "this": "1956.91",
            "other": "231836.45",
            "delta": "-229879.54"
          },
          {
            "figure": "monthly.10y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "-63198.53",
            "delta": "79000.00"
          },
          {
            "figure": "monthly.10y.investments",
            "unit": "amount",
            "this": "348578.03",
            "other": "287460.99",
            "delta": "61117.04"
          },
          {
            "figure": "monthly.10y.debts",
            "unit": "amount",
            "this": "0.00",
            "other": "168051.98",
            "delta": "-168051.98"
          },
          {
            "figure": "monthly.20y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "-63198.53",
            "delta": "79000.00"
          },
          {
            "figure": "monthly.20y.investments",
            "unit": "amount",
            "this": "833547.73",
            "other": "678816.12",
            "delta": "154731.61"
          },
          {
            "figure": "monthly.20y.debts",
            "unit": "amount",
            "this": "0.00",
            "other": "1675.57",
            "delta": "-1675.57"
          },
          {
            "figure": "debts.total_interest",
            "unit": "amount",
            "this": "2009.25",
            "other": "125695.44",
            "delta": "-123686.19"
          },
          {
            "figure": "debts.debt_free",
            "unit": "month",
            "this": "2033-03",
            "other": "2046-11",
            "delta": -164
          }
        ],
        "gives_up": [
          {
            "figure": "monthly.1y.other_assets",
            "unit": "amount",
            "this": "300000.00",
            "other": "639500.00",
            "delta": "-339500.00"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "485551.81",
            "other": "489576.06",
            "delta": "-4024.24"
          },
          {
            "figure": "monthly.5y.other_assets",
            "unit": "amount",
            "this": "300000.00",
            "other": "639500.00",
            "delta": "-339500.00"
          },
          {
            "figure": "monthly.10y.net_worth",
            "unit": "amount",
            "this": "664379.50",
            "other": "695710.48",
            "delta": "-31330.98"
          },
          {
            "figure": "monthly.10y.other_assets",
            "unit": "amount",
            "this": "300000.00",
            "other": "639500.00",
            "delta": "-339500.00"
          },
          {
            "figure": "monthly.20y.net_worth",
            "unit": "amount",
            "this": "1149349.20",
            "other": "1253442.02",
            "delta": "-104092.82"
          },
          {
            "figure": "monthly.20y.other_assets",
            "unit": "amount",
            "this": "300000.00",
            "other": "639500.00",
            "delta": "-339500.00"
          },
          {
            "figure": "fi.fi_number",
            "unit": "amount",
            "this": "714042.04",
            "other": "236335.03",
            "delta": "477707.01"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2044-08",
            "other": "2040-09",
            "delta": 47
          }
        ]
      },
      {
        "option": "Buy, 4.2% over 300 months",
        "against": "Keep renting",
        "gains": [
          {
            "figure": "monthly.1y.other_assets",
            "unit": "amount",
            "this": "639500.00",
            "other": "300000.00",
            "delta": "339500.00"
          },
          {
            "figure": "monthly.5y.other_assets",
            "unit": "amount",
            "this": "639500.00",
            "other": "300000.00",
            "delta": "339500.00"
          },
          {
            "figure": "monthly.10y.net_worth",
            "unit": "amount",
            "this": "686904.46",
            "other": "664379.50",
            "delta": "22524.96"
          },
          {
            "figure": "monthly.10y.other_assets",
            "unit": "amount",
            "this": "639500.00",
            "other": "300000.00",
            "delta": "339500.00"
          },
          {
            "figure": "monthly.20y.net_worth",
            "unit": "amount",
            "this": "1235424.78",
            "other": "1149349.20",
            "delta": "86075.58"
          },
          {
            "figure": "monthly.20y.other_assets",
            "unit": "amount",
            "this": "639500.00",
            "other": "300000.00",
            "delta": "339500.00"
          },
          {
            "figure": "fi.fi_number",
            "unit": "amount",
            "this": "236335.03",
            "other": "714042.04",
            "delta": "-477707.01"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2040-12",
            "other": "2044-08",
            "delta": -44
          }
        ],
        "gives_up": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "-65044.55",
            "other": "13998.91",
            "delta": "-79043.46"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "-34.26",
            "other": "7.37",
            "delta": "-41.64"
          },
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "351087.69",
            "other": "366266.13",
            "delta": "-15178.44"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "-63198.53",
            "other": "15801.47",
            "delta": "-79000.00"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "61946.01",
            "other": "63546.81",
            "delta": "-1600.80"
          },
          {
            "figure": "monthly.1y.debts",
            "unit": "amount",
            "this": "287159.79",
            "other": "13082.15",
            "delta": "274077.64"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "485317.06",
            "other": "485551.81",
            "delta": "-234.76"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "-63198.53",
            "other": "15801.47",
            "delta": "-79000.00"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "156369.58",
            "other": "171707.25",
            "delta": "-15337.68"
          },
          {
            "figure": "monthly.5y.debts",
            "unit": "amount",
            "this": "247353.99",
            "other": "1956.91",
            "delta": "245397.08"
          },
          {
            "figure": "monthly.10y.cash",
            "unit": "amount",
            "this": "-63198.53",
            "other": "15801.47",
            "delta": "-79000.00"
          },
          {
            "figure": "monthly.10y.investments",
            "unit": "amount",
            "this": "312676.69",
            "other": "348578.03",
            "delta": "-35901.34"
          },
          {
            "figure": "monthly.10y.debts",
            "unit": "amount",
            "this": "202073.70",
            "other": "0.00",
            "delta": "202073.70"
          },
          {
            "figure": "monthly.20y.cash",
            "unit": "amount",
            "this": "-63198.53",
            "other": "15801.47",
            "delta": "-79000.00"
          },
          {
            "figure": "monthly.20y.investments",
            "unit": "amount",
            "this": "741881.25",
            "other": "833547.73",
            "delta": "-91666.48"
          },
          {
            "figure": "monthly.20y.debts",
            "unit": "amount",
            "this": "82757.94",
            "other": "0.00",
            "delta": "82757.94"
          },
          {
            "figure": "debts.total_interest",
            "unit": "amount",
            "this": "174720.34",
            "other": "2009.25",
            "delta": "172711.09"
          },
          {
            "figure": "debts.debt_free",
            "unit": "month",
            "this": "2051-11",
            "other": "2033-03",
            "delta": 224
          }
        ]
      },
      {
        "option": "Buy, 4.2% over 300 months",
        "against": "Buy, Shorter",
        "gains": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "-65044.55",
            "other": "-65192.83",
            "delta": "148.28"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "-34.26",
            "other": "-34.34",
            "delta": "0.08"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "61946.01",
            "other": "60011.09",
            "delta": "1934.92"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "156369.58",
            "other": "145111.04",
            "delta": "11258.54"
          },
          {
            "figure": "monthly.10y.investments",
            "unit": "amount",
            "this": "312676.69",
            "other": "287460.99",
            "delta": "25215.70"
          },
          {
            "figure": "monthly.20y.investments",
            "unit": "amount",
            "this": "741881.25",
            "other": "678816.12",
            "delta": "63065.14"
          }
        ],
        "gives_up": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "351087.69",
            "other": "351862.11",
            "delta": "-774.42"
          },
          {
            "figure": "monthly.1y.debts",
            "unit": "amount",
            "this": "287159.79",
            "other": "284450.45",
            "delta": "2709.34"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "485317.06",
            "other": "489576.06",
            "delta": "-4259.00"
          },
          {
            "figure": "monthly.5y.debts",
            "unit": "amount",
            "this": "247353.99",
            "other": "231836.45",
            "delta": "15517.54"
          },
          {
            "figure": "monthly.10y.net_worth",
            "unit": "amount",
            "this": "686904.46",
            "other": "695710.48",
            "delta": "-8806.02"
          },
          {
            "figure": "monthly.10y.debts",
            "unit": "amount",
            "this": "202073.70",
            "other": "168051.98",
            "delta": "34021.72"
          },
          {
            "figure": "monthly.20y.net_worth",
            "unit": "amount",
            "this": "1235424.78",
            "other": "1253442.02",
            "delta": "-18017.23"
          },
          {
            "figure": "monthly.20y.debts",
            "unit": "amount",
            "this": "82757.94",
            "other": "1675.57",
            "delta": "81082.37"
          },
          {
            "figure": "debts.total_interest",
            "unit": "amount",
            "this": "174720.34",
            "other": "125695.44",
            "delta": "49024.90"
          },
          {
            "figure": "debts.debt_free",
            "unit": "month",
            "this": "2051-11",
            "other": "2046-11",
            "delta": 60
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2040-12",
            "other": "2040-09",
            "delta": 3
          }
        ]
      },
      {
        "option": "Buy, Shorter",
        "against": "Keep renting",
        "gains": [
          {
            "figure": "monthly.1y.other_assets",
            "unit": "amount",
            "this": "639500.00",
            "other": "300000.00",
            "delta": "339500.00"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "489576.06",
            "other": "485551.81",
            "delta": "4024.24"
          },
          {
            "figure": "monthly.5y.other_assets",
            "unit": "amount",
            "this": "639500.00",
            "other": "300000.00",
            "delta": "339500.00"
          },
          {
            "figure": "monthly.10y.net_worth",
            "unit": "amount",
            "this": "695710.48",
            "other": "664379.50",
            "delta": "31330.98"
          },
          {
            "figure": "monthly.10y.other_assets",
            "unit": "amount",
            "this": "639500.00",
            "other": "300000.00",
            "delta": "339500.00"
          },
          {
            "figure": "monthly.20y.net_worth",
            "unit": "amount",
            "this": "1253442.02",
            "other": "1149349.20",
            "delta": "104092.82"
          },
          {
            "figure": "monthly.20y.other_assets",
            "unit": "amount",
            "this": "639500.00",
            "other": "300000.00",
            "delta": "339500.00"
          },
          {
            "figure": "fi.fi_number",
            "unit": "amount",
            "this": "236335.03",
            "other": "714042.04",
            "delta": "-477707.01"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2040-09",
            "other": "2044-08",
            "delta": -47
          }
        ],
        "gives_up": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "-65192.83",
            "other": "13998.91",
            "delta": "-79191.74"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "-34.34",
            "other": "7.37",
            "delta": "-41.72"
          },
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "351862.11",
            "other": "366266.13",
            "delta": "-14404.03"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "-63198.53",
            "other": "15801.47",
            "delta": "-79000.00"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "60011.09",
            "other": "63546.81",
            "delta": "-3535.73"
          },
          {
            "figure": "monthly.1y.debts",
            "unit": "amount",
            "this": "284450.45",
            "other": "13082.15",
            "delta": "271368.30"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "-63198.53",
            "other": "15801.47",
            "delta": "-79000.00"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "145111.04",
            "other": "171707.25",
            "delta": "-26596.22"
          },
          {
            "figure": "monthly.5y.debts",
            "unit": "amount",
            "this": "231836.45",
            "other": "1956.91",
            "delta": "229879.54"
          },
          {
            "figure": "monthly.10y.cash",
            "unit": "amount",
            "this": "-63198.53",
            "other": "15801.47",
            "delta": "-79000.00"
          },
          {
            "figure": "monthly.10y.investments",
            "unit": "amount",
            "this": "287460.99",
            "other": "348578.03",
            "delta": "-61117.04"
          },
          {
            "figure": "monthly.10y.debts",
            "unit": "amount",
            "this": "168051.98",
            "other": "0.00",
            "delta": "168051.98"
          },
          {
            "figure": "monthly.20y.cash",
            "unit": "amount",
            "this": "-63198.53",
            "other": "15801.47",
            "delta": "-79000.00"
          },
          {
            "figure": "monthly.20y.investments",
            "unit": "amount",
            "this": "678816.12",
            "other": "833547.73",
            "delta": "-154731.61"
          },
          {
            "figure": "monthly.20y.debts",
            "unit": "amount",
            "this": "1675.57",
            "other": "0.00",
            "delta": "1675.57"
          },
          {
            "figure": "debts.total_interest",
            "unit": "amount",
            "this": "125695.44",
            "other": "2009.25",
            "delta": "123686.19"
          },
          {
            "figure": "debts.debt_free",
            "unit": "month",
            "this": "2046-11",
            "other": "2033-03",
            "delta": 164
          }
        ]
      },
      {
        "option": "Buy, Shorter",
        "against": "Buy, 4.2% over 300 months",
        "gains": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "351862.11",
            "other": "351087.69",
            "delta": "774.42"
          },
          {
            "figure": "monthly.1y.debts",
            "unit": "amount",
            "this": "284450.45",
            "other": "287159.79",
            "delta": "-2709.34"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "489576.06",
            "other": "485317.06",
            "delta": "4259.00"
          },
          {
            "figure": "monthly.5y.debts",
            "unit": "amount",
            "this": "231836.45",
            "other": "247353.99",
            "delta": "-15517.54"
          },
          {
            "figure": "monthly.10y.net_worth",
            "unit": "amount",
            "this": "695710.48",
            "other": "686904.46",
            "delta": "8806.02"
          },
          {
            "figure": "monthly.10y.debts",
            "unit": "amount",
            "this": "168051.98",
            "other": "202073.70",
            "delta": "-34021.72"
          },
          {
            "figure": "monthly.20y.net_worth",
            "unit": "amount",
            "this": "1253442.02",
            "other": "1235424.78",
            "delta": "18017.23"
          },
          {
            "figure": "monthly.20y.debts",
            "unit": "amount",
            "this": "1675.57",
            "other": "82757.94",
            "delta": "-81082.37"
          },
          {
            "figure": "debts.total_interest",
            "unit": "amount",
            "this": "125695.44",
            "other": "174720.34",
            "delta": "-49024.90"
          },
          {
            "figure": "debts.debt_free",
            "unit": "month",
            "this": "2046-11",
            "other": "2051-11",
            "delta": -60
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2040-09",
            "other": "2040-12",
            "delta": -3
          }
        ],
        "gives_up": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "-65192.83",
            "other": "-65044.55",
            "delta": "-148.28"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "-34.34",
            "other": "-34.26",
            "delta": "-0.08"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "60011.09",
            "other": "61946.01",
            "delta": "-1934.92"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "145111.04",
            "other": "156369.58",
            "delta": "-11258.54"
          },
          {
            "figure": "monthly.10y.investments",
            "unit": "amount",
            "this": "287460.99",
            "other": "312676.69",
            "delta": "-25215.70"
          },
          {
            "figure": "monthly.20y.investments",
            "unit": "amount",
            "this": "678816.12",
            "other": "741881.25",
            "delta": "-63065.14"
          }
        ]
      }
    ],
    "sensitivity": {
      "real_returns": {
        "conservative": "0.02",
        "base": "0.04",
        "growth": "0.06"
      },
      "options": [
        {
          "option": "Keep renting",
          "conservative": {
            "net_worth": {
              "baseline": "977656.19",
              "scenario": "977656.19",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "661854.72",
              "scenario": "661854.72",
              "delta": "0.00"
            },
            "fi_month": {
              "baseline": "2048-01",
              "scenario": "2048-01",
              "delta_months": 0
            },
            "months_gained": 0
          },
          "base": {
            "net_worth": {
              "baseline": "1149349.20",
              "scenario": "1149349.20",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "833547.73",
              "scenario": "833547.73",
              "delta": "0.00"
            },
            "fi_month": {
              "baseline": "2044-08",
              "scenario": "2044-08",
              "delta_months": 0
            },
            "months_gained": 0
          },
          "growth": {
            "net_worth": {
              "baseline": "1380323.33",
              "scenario": "1380323.33",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "1064521.86",
              "scenario": "1064521.86",
              "delta": "0.00"
            },
            "fi_month": {
              "baseline": "2042-04",
              "scenario": "2042-04",
              "delta_months": 0
            },
            "months_gained": 0
          }
        },
        {
          "option": "Buy, 4.2% over 300 months",
          "conservative": {
            "net_worth": {
              "baseline": "977656.19",
              "scenario": "1081280.81",
              "delta": "103624.62"
            },
            "investments": {
              "baseline": "661854.72",
              "scenario": "587737.28",
              "delta": "-74117.44"
            },
            "fi_month": {
              "baseline": "2048-01",
              "scenario": "2042-08",
              "delta_months": -65
            },
            "months_gained": 65
          },
          "base": {
            "net_worth": {
              "baseline": "1149349.20",
              "scenario": "1235424.78",
              "delta": "86075.58"
            },
            "investments": {
              "baseline": "833547.73",
              "scenario": "741881.25",
              "delta": "-91666.48"
            },
            "fi_month": {
              "baseline": "2044-08",
              "scenario": "2040-12",
              "delta_months": -44
            },
            "months_gained": 44
          },
          "growth": {
            "net_worth": {
              "baseline": "1380323.33",
              "scenario": "1443348.70",
              "delta": "63025.37"
            },
            "investments": {
              "baseline": "1064521.86",
              "scenario": "949805.17",
              "delta": "-114716.69"
            },
            "fi_month": {
              "baseline": "2042-04",
              "scenario": "2039-08",
              "delta_months": -32
            },
            "months_gained": 32
          }
        },
        {
          "option": "Buy, Shorter",
          "conservative": {
            "net_worth": {
              "baseline": "977656.19",
              "scenario": "1111623.83",
              "delta": "133967.64"
            },
            "investments": {
              "baseline": "661854.72",
              "scenario": "536997.93",
              "delta": "-124856.79"
            },
            "fi_month": {
              "baseline": "2048-01",
              "scenario": "2042-02",
              "delta_months": -71
            },
            "months_gained": 71
          },
          "base": {
            "net_worth": {
              "baseline": "1149349.20",
              "scenario": "1253442.02",
              "delta": "104092.82"
            },
            "investments": {
              "baseline": "833547.73",
              "scenario": "678816.12",
              "delta": "-154731.61"
            },
            "fi_month": {
              "baseline": "2044-08",
              "scenario": "2040-09",
              "delta_months": -47
            },
            "months_gained": 47
          },
          "growth": {
            "net_worth": {
              "baseline": "1380323.33",
              "scenario": "1445072.40",
              "delta": "64749.06"
            },
            "investments": {
              "baseline": "1064521.86",
              "scenario": "870446.50",
              "delta": "-194075.37"
            },
            "fi_month": {
              "baseline": "2042-04",
              "scenario": "2039-07",
              "delta_months": -33
            },
            "months_gained": 33
          }
        }
      ]
    },
    "break_evens": [
      {
        "kind": "asset_growth",
        "options": [
          "Buy, 4.2% over 300 months",
          "Keep renting"
        ],
        "option": "Buy, 4.2% over 300 months",
        "change": 0,
        "status": "found",
        "unit": "rate",
        "value": "-0.0146",
        "low": "-0.05",
        "high": "0.1",
        "ahead": null,
        "says": "At a growth of -1.46% a year beyond inflation or more in the value of Buy, 4.2% over 300 months's asset, Buy, 4.2% over 300 months ends the horizon with at least Keep renting's net worth; below it, Keep renting ends with more."
      },
      {
        "kind": "asset_growth",
        "options": [
          "Buy, Shorter",
          "Keep renting"
        ],
        "option": "Buy, Shorter",
        "change": 0,
        "status": "found",
        "unit": "rate",
        "value": "-0.0183",
        "low": "-0.05",
        "high": "0.1",
        "ahead": null,
        "says": "At a growth of -1.83% a year beyond inflation or more in the value of Buy, Shorter's asset, Buy, Shorter ends the horizon with at least Keep renting's net worth; below it, Keep renting ends with more."
      },
      {
        "kind": "loan_rate",
        "options": [
          "Buy, 4.2% over 300 months",
          "Buy, Shorter"
        ],
        "option": "Buy, 4.2% over 300 months",
        "change": 1,
        "status": "found",
        "unit": "rate",
        "value": "0.0391",
        "low": "0",
        "high": "1",
        "ahead": null,
        "says": "At a loan rate of 3.91% or less, Buy, 4.2% over 300 months ends the horizon with at least Buy, Shorter's net worth; above it, Buy, Shorter costs less."
      },
      {
        "kind": "loan_rate",
        "options": [
          "Buy, 4.2% over 300 months",
          "Buy, Shorter"
        ],
        "option": "Buy, Shorter",
        "change": 1,
        "status": "found",
        "unit": "rate",
        "value": "0.0423",
        "low": "0",
        "high": "1",
        "ahead": null,
        "says": "At a loan rate of 4.23% or less, Buy, Shorter ends the horizon with at least Buy, 4.2% over 300 months's net worth; above it, Buy, 4.2% over 300 months costs less."
      },
      {
        "kind": "loan_rate",
        "options": [
          "Buy, 4.2% over 300 months",
          "Keep renting"
        ],
        "option": "Buy, 4.2% over 300 months",
        "change": 1,
        "status": "found",
        "unit": "rate",
        "value": "0.0551",
        "low": "0",
        "high": "1",
        "ahead": null,
        "says": "At a loan rate of 5.51% or less, Buy, 4.2% over 300 months ends the horizon with at least Keep renting's net worth; above it, Keep renting costs less."
      },
      {
        "kind": "loan_rate",
        "options": [
          "Buy, Shorter",
          "Keep renting"
        ],
        "option": "Buy, Shorter",
        "change": 1,
        "status": "found",
        "unit": "rate",
        "value": "0.0575",
        "low": "0",
        "high": "1",
        "ahead": null,
        "says": "At a loan rate of 5.75% or less, Buy, Shorter ends the horizon with at least Keep renting's net worth; above it, Keep renting costs less."
      },
      {
        "kind": "recurring_cash_floor",
        "options": [
          "Buy, 4.2% over 300 months"
        ],
        "option": "Buy, 4.2% over 300 months",
        "change": 3,
        "status": "none_in_range",
        "unit": "amount",
        "value": null,
        "low": "0.00",
        "high": "250.00",
        "ahead": null,
        "says": "Cash goes below zero in the next twelve months even without this cost."
      },
      {
        "kind": "recurring_cash_floor",
        "options": [
          "Buy, Shorter"
        ],
        "option": "Buy, Shorter",
        "change": 3,
        "status": "none_in_range",
        "unit": "amount",
        "value": null,
        "low": "0.00",
        "high": "250.00",
        "ahead": null,
        "says": "Cash goes below zero in the next twelve months even without this cost."
      }
    ]
  },
  "principles": {
    "principles": [
      {
        "id": "00002331-5a11-4000-8000-000000009009",
        "label": "Six months of essentials in cash",
        "check": "emergency_months >= 6",
        "account": null,
        "version": 1,
        "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
      },
      {
        "id": "00002333-5a11-4000-8000-000000009011",
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
          "principle_id": "00002331-5a11-4000-8000-000000009009",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
          "figures": {
            "emergency_months": "7.37"
          }
        },
        {
          "principle_id": "00002333-5a11-4000-8000-000000009011",
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
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
            "figures": {
              "emergency_months": "7.37"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
            "label": "Checking above 5,000",
            "status": "keeps",
            "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
            "figures": {
              "account_lowest": "6063.46"
            }
          }
        ],
        "label": "Keep renting",
        "scenario_hash": "sha256:a38af0bb404f2972faa76d45ea52e0d9dc177924d5ef50d5f98a2109a3fce5e2"
      },
      {
        "figures": {
          "lowest_cash": "-65044.55",
          "cash_in_12_months": "-63198.53",
          "safe_to_spend": "15316.35",
          "any_account_below_zero": true,
          "monthly_spending": "1898.32",
          "emergency_months": "-34.26",
          "emergency_months_in_12_months": "-33.29",
          "net_worth_1y": "351087.69",
          "net_worth_5y": "485317.06",
          "net_worth_10y": "686904.46",
          "net_worth_20y": "1235424.78",
          "cash_1y": "-63198.53",
          "cash_5y": "-63198.53",
          "cash_10y": "-63198.53",
          "cash_20y": "-63198.53",
          "investments_1y": "61946.01",
          "investments_5y": "156369.58",
          "investments_10y": "312676.69",
          "investments_20y": "741881.25",
          "debts_1y": "287159.79",
          "debts_5y": "247353.99",
          "debts_10y": "202073.70",
          "debts_20y": "82757.94",
          "total_interest": "174720.34",
          "debt_free_months": 301,
          "max_debt_rate": "0.059",
          "max_debt_rate_while_investing": "0.059",
          "borrowed": "280000.00",
          "fi_number": "236335.03",
          "fi_months": 170,
          "fi_months_gained": 44,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "breaks",
            "reason": "emergency_months >= 6 doesn't hold: emergency_months is -34.26.",
            "figures": {
              "emergency_months": "-34.26"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
            "label": "Checking above 5,000",
            "status": "breaks",
            "reason": "account_lowest >= 5000 doesn't hold: account_lowest is -70466.23.",
            "figures": {
              "account_lowest": "-70466.23"
            }
          }
        ],
        "label": "Buy, 4.2% over 300 months",
        "scenario_hash": "sha256:0af1ac5745d12490dbd159af6a6910e6d52c8b3db2f78c4f3f8a280fcb9edb76"
      },
      {
        "figures": {
          "lowest_cash": "-65192.83",
          "cash_in_12_months": "-63198.53",
          "safe_to_spend": "15316.35",
          "any_account_below_zero": true,
          "monthly_spending": "1898.32",
          "emergency_months": "-34.34",
          "emergency_months_in_12_months": "-33.29",
          "net_worth_1y": "351862.11",
          "net_worth_5y": "489576.06",
          "net_worth_10y": "695710.48",
          "net_worth_20y": "1253442.02",
          "cash_1y": "-63198.53",
          "cash_5y": "-63198.53",
          "cash_10y": "-63198.53",
          "cash_20y": "-63198.53",
          "investments_1y": "60011.09",
          "investments_5y": "145111.04",
          "investments_10y": "287460.99",
          "investments_20y": "678816.12",
          "debts_1y": "284450.45",
          "debts_5y": "231836.45",
          "debts_10y": "168051.98",
          "debts_20y": "1675.57",
          "total_interest": "125695.44",
          "debt_free_months": 241,
          "max_debt_rate": "0.059",
          "max_debt_rate_while_investing": "0.059",
          "borrowed": "280000.00",
          "fi_number": "236335.03",
          "fi_months": 167,
          "fi_months_gained": 47,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "breaks",
            "reason": "emergency_months >= 6 doesn't hold: emergency_months is -34.34.",
            "figures": {
              "emergency_months": "-34.34"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
            "label": "Checking above 5,000",
            "status": "breaks",
            "reason": "account_lowest >= 5000 doesn't hold: account_lowest is -70466.23.",
            "figures": {
              "account_lowest": "-70466.23"
            }
          }
        ],
        "label": "Buy, Shorter",
        "scenario_hash": "sha256:5b9235fada31e82c65a399683f460ef60632ca23a2e83c17a468f123c9809e38"
      }
    ]
  },
  "cover": null,
  "level": {
    "against": "Keep renting",
    "from": "2026-11",
    "to": "2046-10",
    "options": [
      {
        "option": "Buy, 4.2% over 300 months",
        "month": "2031-11",
        "months": 60,
        "net_worth_then": "105.23",
        "net_worth_at_horizon": "86075.58"
      },
      {
        "option": "Buy, Shorter",
        "month": "2031-01",
        "months": 50,
        "net_worth_then": "354.06",
        "net_worth_at_horizon": "104092.82"
      }
    ],
    "says": "The first month-end from 2026-11 on from which the option's net worth, in today's money, is at least Keep renting's at every month-end to 2046-10; null when it is behind at the horizon. `months` counts from the purchase's month, and the net worth figures are the option's less Keep renting's."
  },
  "odds": null,
  "placeholders": [
    "real_return",
    "safe_withdrawal_rate",
    "surplus_invested",
    "drawdown_horizon",
    "inflation",
    "asset_growth",
    "rent_growth"
  ],
  "data_as_of": "2026-10-09",
  "is_stale": false,
  "notes": [
    "The home's growth beyond inflation is 0%, a placeholder, not a forecast: set your own view. The asset_growth break-even says what growth would change the answer.",
    "The rent's growth beyond inflation is 0% (it rises with inflation), a placeholder, not a forecast: set your own view.",
    "`level` reads, for each way of buying, the first month-end from the purchase on from which its net worth is at least keeping renting's at every month-end to the horizon: how long the home must be kept for buying to have drawn level, on these assumptions.",
    "The growth of the home's value and of the rent is your own view, or a labelled 0% beyond inflation, never a forecast: the house-price growth at which the answer turns (the asset_growth break-even) is the figure that matters.",
    "Each mortgage's rate is held fixed for its term: resets aren't modelled.",
    "A home is one asset, illiquid and undiversified: the comparison doesn't price that risk.",
    "Owning costs are what you give: leaving them low flatters buying.",
    "Tax on buying, owning or selling a home comes only from your own rules: a tax on buying is a buying cost you give; nothing else about a home's tax is modelled.",
    "Salli knows nothing about any local property market: research behind your figures needs its sources.",
    "The home counts in net worth at what it would fetch, its value less its selling costs, so buying starts behind by them; like any other asset it funds no withdrawals in FI."
  ],
  "record": {
    "question": "Keep renting, or buy a home for 350000.00 EUR?",
    "options": [
      {
        "schema": "salli.scenario/1",
        "label": "Keep renting",
        "as_of": "2026-10-11",
        "horizon_years": 20,
        "changes": [
          {
            "type": "stop_recurring",
            "key": "city",
            "from": "2026-11-01",
            "label": "Rent as it is"
          },
          {
            "type": "recurring",
            "amount": "-1500.00",
            "cadence": "monthly",
            "start": "2026-11-01",
            "end": null,
            "account": "chk",
            "tax_role": null,
            "real_growth": null,
            "label": "Rent: City Lettings Rent"
          }
        ],
        "tax": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Buy, 4.2% over 300 months",
        "as_of": "2026-10-11",
        "horizon_years": 20,
        "changes": [
          {
            "type": "asset",
            "price": "350000.00",
            "date": "2026-11-01",
            "from": "chk",
            "real_growth": null,
            "selling_costs": "0.03",
            "label": "The home"
          },
          {
            "type": "loan",
            "principal": "280000.00",
            "annual_rate": "0.042",
            "term_months": 300,
            "start": "2026-11-01",
            "into": "chk",
            "label": "Mortgage, 4.2% over 300 months"
          },
          {
            "type": "one_off",
            "date": "2026-11-01",
            "amount": "-9000.00",
            "account": "chk",
            "tax_role": null,
            "label": "Buying costs"
          },
          {
            "type": "recurring",
            "amount": "-250.00",
            "cadence": "monthly",
            "start": "2026-11-01",
            "end": null,
            "account": "chk",
            "tax_role": null,
            "real_growth": null,
            "label": "Owning costs"
          },
          {
            "type": "stop_recurring",
            "key": "city",
            "from": "2026-11-01",
            "label": "Rent stopped"
          }
        ],
        "tax": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Buy, Shorter",
        "as_of": "2026-10-11",
        "horizon_years": 20,
        "changes": [
          {
            "type": "asset",
            "price": "350000.00",
            "date": "2026-11-01",
            "from": "chk",
            "real_growth": null,
            "selling_costs": "0.03",
            "label": "The home"
          },
          {
            "type": "loan",
            "principal": "280000.00",
            "annual_rate": "0.039",
            "term_months": 240,
            "start": "2026-11-01",
            "into": "chk",
            "label": "Shorter"
          },
          {
            "type": "one_off",
            "date": "2026-11-01",
            "amount": "-9000.00",
            "account": "chk",
            "tax_role": null,
            "label": "Buying costs"
          },
          {
            "type": "recurring",
            "amount": "-250.00",
            "cadence": "monthly",
            "start": "2026-11-01",
            "end": null,
            "account": "chk",
            "tax_role": null,
            "real_growth": null,
            "label": "Owning costs"
          },
          {
            "type": "stop_recurring",
            "key": "city",
            "from": "2026-11-01",
            "label": "Rent stopped"
          }
        ],
        "tax": null
      }
    ],
    "labels": [
      "Keep renting",
      "Buy, 4.2% over 300 months",
      "Buy, Shorter"
    ],
    "earliest_review": "2026-10-31"
  },
  "says": "Salli computed every figure here and ranks none of the options: what matters most is the person's to weigh. To record what they choose, call record_decision (POST /v1/decisions) with `record.question` (theirs to change), `record.options`, the label they chose, their reasons in their own words and a review date, once they confirm."
};

/**
 * Nine months of spending in cash, setting aside 200.00 or 500.00 a month.
 */
export const EMERGENCY_FUND_START: DecisionStart = {
  "schema": "salli.decision-start/1",
  "template": {
    "id": "emergency-fund",
    "title": "Emergency fund"
  },
  "as_of": "2026-10-11",
  "currency": "EUR",
  "horizon_years": 5,
  "question": "How to build cash to cover 9 months of spending?",
  "answers": [
    {
      "id": "target_months",
      "value": "9",
      "source": "given",
      "note": null
    },
    {
      "id": "set_aside",
      "value": [
        "200.00",
        "500.00"
      ],
      "source": "given",
      "note": null
    },
    {
      "id": "start",
      "value": "2026-11-01",
      "source": "next_month",
      "note": "the first of next month"
    },
    {
      "id": "horizon_years",
      "value": 5,
      "source": "given",
      "note": null
    }
  ],
  "options": [
    {
      "label": "As things are",
      "describes": "No change: your baseline.",
      "scenario": {
        "schema": "salli.scenario/1",
        "label": "As things are",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [],
        "tax": null
      },
      "scenario_hash": "sha256:320825bf753f48e80af05c9be4c48e32b584ca827d7ea2fb4ee1f557ae99ec2e"
    },
    {
      "label": "Set aside 200.00 a month",
      "describes": "200.00 EUR of each month's surplus kept in cash, from 2026-11, for good, rather than invested.",
      "scenario": {
        "schema": "salli.scenario/1",
        "label": "Set aside 200.00 a month",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "set_aside",
            "monthly": "200.00",
            "from": "2026-11-01",
            "to": null,
            "label": "Emergency fund"
          }
        ],
        "tax": null
      },
      "scenario_hash": "sha256:603e2ee2a8206b030aea9bdc9c2aed278788d165f0c29c29c26f88ceb374ffe9"
    },
    {
      "label": "Set aside 500.00 a month",
      "describes": "500.00 EUR of each month's surplus kept in cash, from 2026-11, for good, rather than invested.",
      "scenario": {
        "schema": "salli.scenario/1",
        "label": "Set aside 500.00 a month",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "set_aside",
            "monthly": "500.00",
            "from": "2026-11-01",
            "to": null,
            "label": "Emergency fund"
          }
        ],
        "tax": null
      },
      "scenario_hash": "sha256:50a28c566b978a2e6ccaa27a483852dbcfc805a6f18d5d347f7b7f7ee6495c79"
    }
  ],
  "comparison": {
    "as_of": "2026-10-11",
    "horizon_years": 5,
    "currency": "EUR",
    "labels": [
      "As things are",
      "Set aside 200.00 a month",
      "Set aside 500.00 a month"
    ],
    "options": [
      {
        "schema": "salli.scenario/1",
        "label": "As things are",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "currency": "EUR",
        "hash": "sha256:320825bf753f48e80af05c9be4c48e32b584ca827d7ea2fb4ee1f557ae99ec2e",
        "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "As things are",
          "as_of": "2026-10-11",
          "horizon_years": 5,
          "changes": [],
          "tax": null
        },
        "changes": [],
        "cash": {
          "start": "2026-10-11",
          "end": "2027-10-31",
          "lowest": {
            "baseline": "13998.91",
            "scenario": "13998.91",
            "delta": "0.00"
          },
          "lowest_date": {
            "baseline": "2027-02-24",
            "scenario": "2027-02-24",
            "delta_days": 0
          },
          "at_end": {
            "baseline": "15801.47",
            "scenario": "15801.47",
            "delta": "0.00"
          },
          "safe_to_spend": {
            "baseline": "15316.35",
            "scenario": "15316.35",
            "delta": "0.00"
          },
          "safe_until": "2026-10-25",
          "accounts": [
            {
              "account_id": "chk",
              "name": "Checking",
              "currency": "EUR",
              "lowest": {
                "baseline": "6063.46",
                "scenario": "6063.46",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-15",
                "scenario": "2026-10-15",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "sav",
              "name": "Savings",
              "currency": "EUR",
              "lowest": {
                "baseline": "7800.00",
                "scenario": "7800.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "usd",
              "name": "Dollar account",
              "currency": "USD",
              "lowest": {
                "baseline": "2500.00",
                "scenario": "2500.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            }
          ],
          "below_zero": {
            "baseline": [],
            "scenario": []
          }
        },
        "monthly": [
          {
            "years": 1,
            "month": "2027-10",
            "date": "2027-10-31",
            "net_worth": {
              "baseline": "366266.13",
              "scenario": "366266.13",
              "delta": "0.00"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "63546.81",
              "scenario": "63546.81",
              "delta": "0.00"
            },
            "debts": {
              "baseline": "13082.15",
              "scenario": "13082.15",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          },
          {
            "years": 5,
            "month": "2031-10",
            "date": "2031-10-31",
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "485551.81",
              "delta": "0.00"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "171707.25",
              "delta": "0.00"
            },
            "debts": {
              "baseline": "1956.91",
              "scenario": "1956.91",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          }
        ],
        "debts": {
          "items": [
            {
              "debt_id": "debt-car",
              "name": "Car loan",
              "source": "account",
              "paid_off": {
                "baseline": "2029-05",
                "scenario": "2029-05",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "786.13",
                "scenario": "786.13",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "debt-student",
              "name": "Student loan",
              "source": "declared",
              "paid_off": {
                "baseline": "2033-03",
                "scenario": "2033-03",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "1223.12",
                "scenario": "1223.12",
                "delta": "0.00"
              }
            }
          ],
          "total_interest": {
            "baseline": "2009.25",
            "scenario": "2009.25",
            "delta": "0.00"
          },
          "debt_free": {
            "baseline": "2033-03",
            "scenario": "2033-03",
            "delta_months": 0
          }
        },
        "resilience": {
          "basis": "essential",
          "monthly_spending": "1898.32",
          "lowest": {
            "baseline": "7.37",
            "scenario": "7.37",
            "delta": "0.00"
          },
          "at_end": {
            "baseline": "8.32",
            "scenario": "8.32",
            "delta": "0.00"
          }
        },
        "fi": {
          "fi_number": {
            "baseline": "714042.04",
            "scenario": "714042.04",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2044-08",
            "scenario": "2044-08",
            "delta_months": 0
          },
          "months_gained": 0
        },
        "break_evens": [],
        "tax": {
          "status": "none",
          "reason": null,
          "years": [],
          "this_year": null,
          "change_this_year": "0.00",
          "total_change": "0.00",
          "carried_forward": false
        },
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
          "nominal_returns": null,
          "cma": null
        },
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon",
          "inflation"
        ],
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": [],
        "timeline": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Set aside 200.00 a month",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "currency": "EUR",
        "hash": "sha256:603e2ee2a8206b030aea9bdc9c2aed278788d165f0c29c29c26f88ceb374ffe9",
        "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Set aside 200.00 a month",
          "as_of": "2026-10-11",
          "horizon_years": 5,
          "changes": [
            {
              "type": "set_aside",
              "monthly": "200.00",
              "from": "2026-11-01",
              "to": null,
              "label": "Emergency fund"
            }
          ],
          "tax": null
        },
        "changes": [
          {
            "index": 0,
            "type": "set_aside",
            "label": "Emergency fund",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": "200.00",
            "for_good": true,
            "stopped": [],
            "holding": null
          }
        ],
        "cash": {
          "start": "2026-10-11",
          "end": "2027-10-31",
          "lowest": {
            "baseline": "13998.91",
            "scenario": "14013.25",
            "delta": "14.34"
          },
          "lowest_date": {
            "baseline": "2027-02-24",
            "scenario": "2026-11-24",
            "delta_days": -92
          },
          "at_end": {
            "baseline": "15801.47",
            "scenario": "18201.47",
            "delta": "2400.00"
          },
          "safe_to_spend": {
            "baseline": "15316.35",
            "scenario": "15316.35",
            "delta": "0.00"
          },
          "safe_until": "2026-10-25",
          "accounts": [
            {
              "account_id": "chk",
              "name": "Checking",
              "currency": "EUR",
              "lowest": {
                "baseline": "6063.46",
                "scenario": "6063.46",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-15",
                "scenario": "2026-10-15",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "sav",
              "name": "Savings",
              "currency": "EUR",
              "lowest": {
                "baseline": "7800.00",
                "scenario": "7800.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "usd",
              "name": "Dollar account",
              "currency": "USD",
              "lowest": {
                "baseline": "2500.00",
                "scenario": "2500.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            }
          ],
          "below_zero": {
            "baseline": [],
            "scenario": []
          }
        },
        "monthly": [
          {
            "years": 1,
            "month": "2027-10",
            "date": "2027-10-31",
            "net_worth": {
              "baseline": "366266.13",
              "scenario": "366221.64",
              "delta": "-44.49"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "18201.47",
              "delta": "2400.00"
            },
            "investments": {
              "baseline": "63546.81",
              "scenario": "61102.32",
              "delta": "-2444.49"
            },
            "debts": {
              "baseline": "13082.15",
              "scenario": "13082.15",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          },
          {
            "years": 5,
            "month": "2031-10",
            "date": "2031-10-31",
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "484292.02",
              "delta": "-1259.80"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "27801.47",
              "delta": "12000.00"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "158447.46",
              "delta": "-13259.80"
            },
            "debts": {
              "baseline": "1956.91",
              "scenario": "1956.91",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          }
        ],
        "debts": {
          "items": [
            {
              "debt_id": "debt-car",
              "name": "Car loan",
              "source": "account",
              "paid_off": {
                "baseline": "2029-05",
                "scenario": "2029-05",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "786.13",
                "scenario": "786.13",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "debt-student",
              "name": "Student loan",
              "source": "declared",
              "paid_off": {
                "baseline": "2033-03",
                "scenario": "2033-03",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "1223.12",
                "scenario": "1223.12",
                "delta": "0.00"
              }
            }
          ],
          "total_interest": {
            "baseline": "2009.25",
            "scenario": "2009.25",
            "delta": "0.00"
          },
          "debt_free": {
            "baseline": "2033-03",
            "scenario": "2033-03",
            "delta_months": 0
          }
        },
        "resilience": {
          "basis": "essential",
          "monthly_spending": "1898.32",
          "lowest": {
            "baseline": "7.37",
            "scenario": "7.38",
            "delta": "0.01"
          },
          "at_end": {
            "baseline": "8.32",
            "scenario": "9.59",
            "delta": "1.26"
          }
        },
        "fi": {
          "fi_number": {
            "baseline": "714042.04",
            "scenario": "714042.04",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2044-08",
            "scenario": "2045-01",
            "delta_months": 5
          },
          "months_gained": -5
        },
        "break_evens": [],
        "tax": {
          "status": "none",
          "reason": null,
          "years": [],
          "this_year": null,
          "change_this_year": "0.00",
          "total_change": "0.00",
          "carried_forward": false
        },
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
          "nominal_returns": null,
          "cma": null
        },
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon",
          "inflation"
        ],
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": [],
        "timeline": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Set aside 500.00 a month",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "currency": "EUR",
        "hash": "sha256:50a28c566b978a2e6ccaa27a483852dbcfc805a6f18d5d347f7b7f7ee6495c79",
        "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Set aside 500.00 a month",
          "as_of": "2026-10-11",
          "horizon_years": 5,
          "changes": [
            {
              "type": "set_aside",
              "monthly": "500.00",
              "from": "2026-11-01",
              "to": null,
              "label": "Emergency fund"
            }
          ],
          "tax": null
        },
        "changes": [
          {
            "index": 0,
            "type": "set_aside",
            "label": "Emergency fund",
            "debt_id": null,
            "payment": null,
            "first_payment": null,
            "monthly": "500.00",
            "for_good": true,
            "stopped": [],
            "holding": null
          }
        ],
        "cash": {
          "start": "2026-10-11",
          "end": "2027-10-31",
          "lowest": {
            "baseline": "13998.91",
            "scenario": "14013.25",
            "delta": "14.34"
          },
          "lowest_date": {
            "baseline": "2027-02-24",
            "scenario": "2026-11-24",
            "delta_days": -92
          },
          "at_end": {
            "baseline": "15801.47",
            "scenario": "21801.47",
            "delta": "6000.00"
          },
          "safe_to_spend": {
            "baseline": "15316.35",
            "scenario": "15316.35",
            "delta": "0.00"
          },
          "safe_until": "2026-10-25",
          "accounts": [
            {
              "account_id": "chk",
              "name": "Checking",
              "currency": "EUR",
              "lowest": {
                "baseline": "6063.46",
                "scenario": "6063.46",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-15",
                "scenario": "2026-10-15",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "sav",
              "name": "Savings",
              "currency": "EUR",
              "lowest": {
                "baseline": "7800.00",
                "scenario": "7800.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            },
            {
              "account_id": "usd",
              "name": "Dollar account",
              "currency": "USD",
              "lowest": {
                "baseline": "2500.00",
                "scenario": "2500.00",
                "delta": "0.00"
              },
              "lowest_date": {
                "baseline": "2026-10-11",
                "scenario": "2026-10-11",
                "delta_days": 0
              },
              "below_zero": {
                "baseline": false,
                "scenario": false
              }
            }
          ],
          "below_zero": {
            "baseline": [],
            "scenario": []
          }
        },
        "monthly": [
          {
            "years": 1,
            "month": "2027-10",
            "date": "2027-10-31",
            "net_worth": {
              "baseline": "366266.13",
              "scenario": "366154.90",
              "delta": "-111.23"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "21801.47",
              "delta": "6000.00"
            },
            "investments": {
              "baseline": "63546.81",
              "scenario": "57435.58",
              "delta": "-6111.23"
            },
            "debts": {
              "baseline": "13082.15",
              "scenario": "13082.15",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          },
          {
            "years": 5,
            "month": "2031-10",
            "date": "2031-10-31",
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "482402.33",
              "delta": "-3149.49"
            },
            "cash": {
              "baseline": "15801.47",
              "scenario": "45801.47",
              "delta": "30000.00"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "138557.77",
              "delta": "-33149.49"
            },
            "debts": {
              "baseline": "1956.91",
              "scenario": "1956.91",
              "delta": "0.00"
            },
            "other_assets": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            },
            "other_assets_value": {
              "baseline": "300000.00",
              "scenario": "300000.00",
              "delta": "0.00"
            }
          }
        ],
        "debts": {
          "items": [
            {
              "debt_id": "debt-car",
              "name": "Car loan",
              "source": "account",
              "paid_off": {
                "baseline": "2029-05",
                "scenario": "2029-05",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "786.13",
                "scenario": "786.13",
                "delta": "0.00"
              }
            },
            {
              "debt_id": "debt-student",
              "name": "Student loan",
              "source": "declared",
              "paid_off": {
                "baseline": "2033-03",
                "scenario": "2033-03",
                "delta_months": 0
              },
              "total_interest": {
                "baseline": "1223.12",
                "scenario": "1223.12",
                "delta": "0.00"
              }
            }
          ],
          "total_interest": {
            "baseline": "2009.25",
            "scenario": "2009.25",
            "delta": "0.00"
          },
          "debt_free": {
            "baseline": "2033-03",
            "scenario": "2033-03",
            "delta_months": 0
          }
        },
        "resilience": {
          "basis": "essential",
          "monthly_spending": "1898.32",
          "lowest": {
            "baseline": "7.37",
            "scenario": "7.38",
            "delta": "0.01"
          },
          "at_end": {
            "baseline": "8.32",
            "scenario": "11.48",
            "delta": "3.16"
          }
        },
        "fi": {
          "fi_number": {
            "baseline": "714042.04",
            "scenario": "714042.04",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2044-08",
            "scenario": "2045-08",
            "delta_months": 12
          },
          "months_gained": -12
        },
        "break_evens": [],
        "tax": {
          "status": "none",
          "reason": null,
          "years": [],
          "this_year": null,
          "change_this_year": "0.00",
          "total_change": "0.00",
          "carried_forward": false
        },
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
          "nominal_returns": null,
          "cma": null
        },
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon",
          "inflation"
        ],
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": [],
        "timeline": null
      }
    ],
    "trade": [
      {
        "option": "As things are",
        "against": "Set aside 200.00 a month",
        "gains": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "366266.13",
            "other": "366221.64",
            "delta": "44.49"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "63546.81",
            "other": "61102.32",
            "delta": "2444.49"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "485551.81",
            "other": "484292.02",
            "delta": "1259.80"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "171707.25",
            "other": "158447.46",
            "delta": "13259.80"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2044-08",
            "other": "2045-01",
            "delta": -5
          }
        ],
        "gives_up": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "13998.91",
            "other": "14013.25",
            "delta": "-14.34"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "7.37",
            "other": "7.38",
            "delta": "-0.01"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "18201.47",
            "delta": "-2400.00"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "27801.47",
            "delta": "-12000.00"
          }
        ]
      },
      {
        "option": "As things are",
        "against": "Set aside 500.00 a month",
        "gains": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "366266.13",
            "other": "366154.90",
            "delta": "111.23"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "63546.81",
            "other": "57435.58",
            "delta": "6111.23"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "485551.81",
            "other": "482402.33",
            "delta": "3149.49"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "171707.25",
            "other": "138557.77",
            "delta": "33149.49"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2044-08",
            "other": "2045-08",
            "delta": -12
          }
        ],
        "gives_up": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "13998.91",
            "other": "14013.25",
            "delta": "-14.34"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "7.37",
            "other": "7.38",
            "delta": "-0.01"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "21801.47",
            "delta": "-6000.00"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "15801.47",
            "other": "45801.47",
            "delta": "-30000.00"
          }
        ]
      },
      {
        "option": "Set aside 200.00 a month",
        "against": "As things are",
        "gains": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "14013.25",
            "other": "13998.91",
            "delta": "14.34"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "7.38",
            "other": "7.37",
            "delta": "0.01"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "18201.47",
            "other": "15801.47",
            "delta": "2400.00"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "27801.47",
            "other": "15801.47",
            "delta": "12000.00"
          }
        ],
        "gives_up": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "366221.64",
            "other": "366266.13",
            "delta": "-44.49"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "61102.32",
            "other": "63546.81",
            "delta": "-2444.49"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "484292.02",
            "other": "485551.81",
            "delta": "-1259.80"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "158447.46",
            "other": "171707.25",
            "delta": "-13259.80"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2045-01",
            "other": "2044-08",
            "delta": 5
          }
        ]
      },
      {
        "option": "Set aside 200.00 a month",
        "against": "Set aside 500.00 a month",
        "gains": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "366221.64",
            "other": "366154.90",
            "delta": "66.74"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "61102.32",
            "other": "57435.58",
            "delta": "3666.74"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "484292.02",
            "other": "482402.33",
            "delta": "1889.69"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "158447.46",
            "other": "138557.77",
            "delta": "19889.69"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2045-01",
            "other": "2045-08",
            "delta": -7
          }
        ],
        "gives_up": [
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "18201.47",
            "other": "21801.47",
            "delta": "-3600.00"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "27801.47",
            "other": "45801.47",
            "delta": "-18000.00"
          }
        ]
      },
      {
        "option": "Set aside 500.00 a month",
        "against": "As things are",
        "gains": [
          {
            "figure": "cash.lowest",
            "unit": "amount",
            "this": "14013.25",
            "other": "13998.91",
            "delta": "14.34"
          },
          {
            "figure": "resilience.lowest",
            "unit": "months_of_spending",
            "this": "7.38",
            "other": "7.37",
            "delta": "0.01"
          },
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "21801.47",
            "other": "15801.47",
            "delta": "6000.00"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "45801.47",
            "other": "15801.47",
            "delta": "30000.00"
          }
        ],
        "gives_up": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "366154.90",
            "other": "366266.13",
            "delta": "-111.23"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "57435.58",
            "other": "63546.81",
            "delta": "-6111.23"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "482402.33",
            "other": "485551.81",
            "delta": "-3149.49"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "138557.77",
            "other": "171707.25",
            "delta": "-33149.49"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2045-08",
            "other": "2044-08",
            "delta": 12
          }
        ]
      },
      {
        "option": "Set aside 500.00 a month",
        "against": "Set aside 200.00 a month",
        "gains": [
          {
            "figure": "monthly.1y.cash",
            "unit": "amount",
            "this": "21801.47",
            "other": "18201.47",
            "delta": "3600.00"
          },
          {
            "figure": "monthly.5y.cash",
            "unit": "amount",
            "this": "45801.47",
            "other": "27801.47",
            "delta": "18000.00"
          }
        ],
        "gives_up": [
          {
            "figure": "monthly.1y.net_worth",
            "unit": "amount",
            "this": "366154.90",
            "other": "366221.64",
            "delta": "-66.74"
          },
          {
            "figure": "monthly.1y.investments",
            "unit": "amount",
            "this": "57435.58",
            "other": "61102.32",
            "delta": "-3666.74"
          },
          {
            "figure": "monthly.5y.net_worth",
            "unit": "amount",
            "this": "482402.33",
            "other": "484292.02",
            "delta": "-1889.69"
          },
          {
            "figure": "monthly.5y.investments",
            "unit": "amount",
            "this": "138557.77",
            "other": "158447.46",
            "delta": "-19889.69"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2045-08",
            "other": "2045-01",
            "delta": 7
          }
        ]
      }
    ],
    "sensitivity": {
      "real_returns": {
        "conservative": "0.02",
        "base": "0.04",
        "growth": "0.06"
      },
      "options": [
        {
          "option": "As things are",
          "conservative": {
            "net_worth": {
              "baseline": "475029.43",
              "scenario": "475029.43",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "161184.87",
              "scenario": "161184.87",
              "delta": "0.00"
            },
            "fi_month": {
              "baseline": "2048-01",
              "scenario": "2048-01",
              "delta_months": 0
            },
            "months_gained": 0
          },
          "base": {
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "485551.81",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "171707.25",
              "delta": "0.00"
            },
            "fi_month": {
              "baseline": "2044-08",
              "scenario": "2044-08",
              "delta_months": 0
            },
            "months_gained": 0
          },
          "growth": {
            "net_worth": {
              "baseline": "496953.13",
              "scenario": "496953.13",
              "delta": "0.00"
            },
            "investments": {
              "baseline": "183108.57",
              "scenario": "183108.57",
              "delta": "0.00"
            },
            "fi_month": {
              "baseline": "2042-04",
              "scenario": "2042-04",
              "delta_months": 0
            },
            "months_gained": 0
          }
        },
        {
          "option": "Set aside 200.00 a month",
          "conservative": {
            "net_worth": {
              "baseline": "475029.43",
              "scenario": "474419.96",
              "delta": "-609.47"
            },
            "investments": {
              "baseline": "161184.87",
              "scenario": "148575.40",
              "delta": "-12609.47"
            },
            "fi_month": {
              "baseline": "2048-01",
              "scenario": "2048-05",
              "delta_months": 4
            },
            "months_gained": -4
          },
          "base": {
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "484292.02",
              "delta": "-1259.80"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "158447.46",
              "delta": "-13259.80"
            },
            "fi_month": {
              "baseline": "2044-08",
              "scenario": "2045-01",
              "delta_months": 5
            },
            "months_gained": -5
          },
          "growth": {
            "net_worth": {
              "baseline": "496953.13",
              "scenario": "494999.13",
              "delta": "-1954.01"
            },
            "investments": {
              "baseline": "183108.57",
              "scenario": "169154.57",
              "delta": "-13954.01"
            },
            "fi_month": {
              "baseline": "2042-04",
              "scenario": "2042-08",
              "delta_months": 4
            },
            "months_gained": -4
          }
        },
        {
          "option": "Set aside 500.00 a month",
          "conservative": {
            "net_worth": {
              "baseline": "475029.43",
              "scenario": "473505.75",
              "delta": "-1523.68"
            },
            "investments": {
              "baseline": "161184.87",
              "scenario": "129661.19",
              "delta": "-31523.68"
            },
            "fi_month": {
              "baseline": "2048-01",
              "scenario": "2048-11",
              "delta_months": 10
            },
            "months_gained": -10
          },
          "base": {
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "482402.33",
              "delta": "-3149.49"
            },
            "investments": {
              "baseline": "171707.25",
              "scenario": "138557.77",
              "delta": "-33149.49"
            },
            "fi_month": {
              "baseline": "2044-08",
              "scenario": "2045-08",
              "delta_months": 12
            },
            "months_gained": -12
          },
          "growth": {
            "net_worth": {
              "baseline": "496953.13",
              "scenario": "492068.12",
              "delta": "-4885.02"
            },
            "investments": {
              "baseline": "183108.57",
              "scenario": "148223.56",
              "delta": "-34885.02"
            },
            "fi_month": {
              "baseline": "2042-04",
              "scenario": "2043-04",
              "delta_months": 12
            },
            "months_gained": -12
          }
        }
      ]
    },
    "break_evens": []
  },
  "principles": {
    "principles": [
      {
        "id": "00002331-5a11-4000-8000-000000009009",
        "label": "Six months of essentials in cash",
        "check": "emergency_months >= 6",
        "account": null,
        "version": 1,
        "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
      },
      {
        "id": "00002333-5a11-4000-8000-000000009011",
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
          "principle_id": "00002331-5a11-4000-8000-000000009009",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
          "figures": {
            "emergency_months": "7.37"
          }
        },
        {
          "principle_id": "00002333-5a11-4000-8000-000000009011",
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
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
            "figures": {
              "emergency_months": "7.37"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
            "label": "Checking above 5,000",
            "status": "keeps",
            "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
            "figures": {
              "account_lowest": "6063.46"
            }
          }
        ],
        "label": "As things are",
        "scenario_hash": "sha256:320825bf753f48e80af05c9be4c48e32b584ca827d7ea2fb4ee1f557ae99ec2e"
      },
      {
        "figures": {
          "lowest_cash": "14013.25",
          "cash_in_12_months": "18201.47",
          "safe_to_spend": "15316.35",
          "any_account_below_zero": false,
          "monthly_spending": "1898.32",
          "emergency_months": "7.38",
          "emergency_months_in_12_months": "9.59",
          "net_worth_1y": "366221.64",
          "net_worth_5y": "484292.02",
          "net_worth_10y": "658929.54",
          "net_worth_20y": "1123994.27",
          "cash_1y": "18201.47",
          "cash_5y": "27801.47",
          "cash_10y": "39801.47",
          "cash_20y": "63801.47",
          "investments_1y": "61102.32",
          "investments_5y": "158447.46",
          "investments_10y": "319128.07",
          "investments_20y": "760192.80",
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
          "fi_months": 219,
          "fi_months_gained": -5,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.38.",
            "figures": {
              "emergency_months": "7.38"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
            "label": "Checking above 5,000",
            "status": "keeps",
            "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
            "figures": {
              "account_lowest": "6063.46"
            }
          }
        ],
        "label": "Set aside 200.00 a month",
        "scenario_hash": "sha256:603e2ee2a8206b030aea9bdc9c2aed278788d165f0c29c29c26f88ceb374ffe9"
      },
      {
        "figures": {
          "lowest_cash": "14013.25",
          "cash_in_12_months": "21801.47",
          "safe_to_spend": "15316.35",
          "any_account_below_zero": false,
          "monthly_spending": "1898.32",
          "emergency_months": "7.38",
          "emergency_months_in_12_months": "11.48",
          "net_worth_1y": "366154.90",
          "net_worth_5y": "482402.33",
          "net_worth_10y": "650754.60",
          "net_worth_20y": "1085961.89",
          "cash_1y": "21801.47",
          "cash_5y": "45801.47",
          "cash_10y": "75801.47",
          "cash_20y": "135801.47",
          "investments_1y": "57435.58",
          "investments_5y": "138557.77",
          "investments_10y": "274953.13",
          "investments_20y": "650160.42",
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
          "fi_months": 226,
          "fi_months_gained": -12,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.38.",
            "figures": {
              "emergency_months": "7.38"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
            "label": "Checking above 5,000",
            "status": "keeps",
            "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
            "figures": {
              "account_lowest": "6063.46"
            }
          }
        ],
        "label": "Set aside 500.00 a month",
        "scenario_hash": "sha256:50a28c566b978a2e6ccaa27a483852dbcfc805a6f18d5d347f7b7f7ee6495c79"
      }
    ]
  },
  "cover": {
    "target_months": "9",
    "basis": "essential",
    "monthly_spending": "1898.32",
    "target": "17084.88",
    "now": "8.32",
    "baseline": {
      "month": null,
      "months": null
    },
    "options": [
      {
        "month": null,
        "months": null,
        "option": "As things are",
        "delta_months": null
      },
      {
        "month": "2027-05",
        "months": 7,
        "option": "Set aside 200.00 a month",
        "delta_months": null
      },
      {
        "month": "2027-01",
        "months": 3,
        "option": "Set aside 500.00 a month",
        "delta_months": null
      }
    ],
    "says": "The first month at whose end cash, in today's money, covers the target; null when it doesn't within 50 years. Cash covers `now` months today."
  },
  "level": null,
  "odds": null,
  "placeholders": [
    "real_return",
    "safe_withdrawal_rate",
    "surplus_invested",
    "drawdown_horizon",
    "inflation"
  ],
  "data_as_of": "2026-10-09",
  "is_stale": false,
  "notes": [
    "Cash earns nothing in Salli's figures, so what you set aside instead of investing shows in the long-run figures too."
  ],
  "record": {
    "question": "How to build cash to cover 9 months of spending?",
    "options": [
      {
        "schema": "salli.scenario/1",
        "label": "As things are",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [],
        "tax": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Set aside 200.00 a month",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "set_aside",
            "monthly": "200.00",
            "from": "2026-11-01",
            "to": null,
            "label": "Emergency fund"
          }
        ],
        "tax": null
      },
      {
        "schema": "salli.scenario/1",
        "label": "Set aside 500.00 a month",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "set_aside",
            "monthly": "500.00",
            "from": "2026-11-01",
            "to": null,
            "label": "Emergency fund"
          }
        ],
        "tax": null
      }
    ],
    "labels": [
      "As things are",
      "Set aside 200.00 a month",
      "Set aside 500.00 a month"
    ],
    "earliest_review": "2026-10-31"
  },
  "says": "Salli computed every figure here and ranks none of the options: what matters most is the person's to weigh. To record what they choose, call record_decision (POST /v1/decisions) with `record.question` (theirs to change), `record.options`, the label they chose, their reasons in their own words and a review date, once they confirm."
};

/**
 * The laptop paid at once, with both timelines.
 */
export const SCENARIO_RUN: ScenarioRun = {
  "schema": "salli.scenario/1",
  "label": "Pay cash",
  "as_of": "2026-10-11",
  "horizon_years": 5,
  "currency": "EUR",
  "hash": "sha256:9b094ea3ce715a3e72c3351d3125a932f6182e9a6d202e422b1facc0787702e4",
  "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
  "scenario": {
    "schema": "salli.scenario/1",
    "label": "Pay cash",
    "as_of": "2026-10-11",
    "horizon_years": 5,
    "changes": [
      {
        "type": "one_off",
        "date": "2026-11-02",
        "amount": "-2400.00",
        "account": "chk",
        "tax_role": null,
        "label": "Laptop"
      }
    ],
    "tax": null
  },
  "changes": [
    {
      "index": 0,
      "type": "one_off",
      "label": "Laptop",
      "debt_id": null,
      "payment": null,
      "first_payment": null,
      "monthly": null,
      "for_good": null,
      "stopped": [],
      "holding": null
    }
  ],
  "cash": {
    "start": "2026-10-11",
    "end": "2027-10-31",
    "lowest": {
      "baseline": "13998.91",
      "scenario": "11598.91",
      "delta": "-2400.00"
    },
    "lowest_date": {
      "baseline": "2027-02-24",
      "scenario": "2027-02-24",
      "delta_days": 0
    },
    "at_end": {
      "baseline": "15801.47",
      "scenario": "13401.47",
      "delta": "-2400.00"
    },
    "safe_to_spend": {
      "baseline": "15316.35",
      "scenario": "15316.35",
      "delta": "0.00"
    },
    "safe_until": "2026-10-25",
    "accounts": [
      {
        "account_id": "chk",
        "name": "Checking",
        "currency": "EUR",
        "lowest": {
          "baseline": "6063.46",
          "scenario": "4883.77",
          "delta": "-1179.69"
        },
        "lowest_date": {
          "baseline": "2026-10-15",
          "scenario": "2026-11-15",
          "delta_days": 31
        },
        "below_zero": {
          "baseline": false,
          "scenario": false
        }
      },
      {
        "account_id": "sav",
        "name": "Savings",
        "currency": "EUR",
        "lowest": {
          "baseline": "7800.00",
          "scenario": "7800.00",
          "delta": "0.00"
        },
        "lowest_date": {
          "baseline": "2026-10-11",
          "scenario": "2026-10-11",
          "delta_days": 0
        },
        "below_zero": {
          "baseline": false,
          "scenario": false
        }
      },
      {
        "account_id": "usd",
        "name": "Dollar account",
        "currency": "USD",
        "lowest": {
          "baseline": "2500.00",
          "scenario": "2500.00",
          "delta": "0.00"
        },
        "lowest_date": {
          "baseline": "2026-10-11",
          "scenario": "2026-10-11",
          "delta_days": 0
        },
        "below_zero": {
          "baseline": false,
          "scenario": false
        }
      }
    ],
    "below_zero": {
      "baseline": [],
      "scenario": []
    }
  },
  "monthly": [
    {
      "years": 1,
      "month": "2027-10",
      "date": "2027-10-31",
      "net_worth": {
        "baseline": "366266.13",
        "scenario": "363866.13",
        "delta": "-2400.00"
      },
      "cash": {
        "baseline": "15801.47",
        "scenario": "13401.47",
        "delta": "-2400.00"
      },
      "investments": {
        "baseline": "63546.81",
        "scenario": "63546.81",
        "delta": "0.00"
      },
      "debts": {
        "baseline": "13082.15",
        "scenario": "13082.15",
        "delta": "0.00"
      },
      "other_assets": {
        "baseline": "300000.00",
        "scenario": "300000.00",
        "delta": "0.00"
      },
      "other_assets_value": {
        "baseline": "300000.00",
        "scenario": "300000.00",
        "delta": "0.00"
      }
    },
    {
      "years": 5,
      "month": "2031-10",
      "date": "2031-10-31",
      "net_worth": {
        "baseline": "485551.81",
        "scenario": "483151.81",
        "delta": "-2400.00"
      },
      "cash": {
        "baseline": "15801.47",
        "scenario": "13401.47",
        "delta": "-2400.00"
      },
      "investments": {
        "baseline": "171707.25",
        "scenario": "171707.25",
        "delta": "0.00"
      },
      "debts": {
        "baseline": "1956.91",
        "scenario": "1956.91",
        "delta": "0.00"
      },
      "other_assets": {
        "baseline": "300000.00",
        "scenario": "300000.00",
        "delta": "0.00"
      },
      "other_assets_value": {
        "baseline": "300000.00",
        "scenario": "300000.00",
        "delta": "0.00"
      }
    }
  ],
  "debts": {
    "items": [
      {
        "debt_id": "debt-car",
        "name": "Car loan",
        "source": "account",
        "paid_off": {
          "baseline": "2029-05",
          "scenario": "2029-05",
          "delta_months": 0
        },
        "total_interest": {
          "baseline": "786.13",
          "scenario": "786.13",
          "delta": "0.00"
        }
      },
      {
        "debt_id": "debt-student",
        "name": "Student loan",
        "source": "declared",
        "paid_off": {
          "baseline": "2033-03",
          "scenario": "2033-03",
          "delta_months": 0
        },
        "total_interest": {
          "baseline": "1223.12",
          "scenario": "1223.12",
          "delta": "0.00"
        }
      }
    ],
    "total_interest": {
      "baseline": "2009.25",
      "scenario": "2009.25",
      "delta": "0.00"
    },
    "debt_free": {
      "baseline": "2033-03",
      "scenario": "2033-03",
      "delta_months": 0
    }
  },
  "resilience": {
    "basis": "essential",
    "monthly_spending": "1898.32",
    "lowest": {
      "baseline": "7.37",
      "scenario": "6.11",
      "delta": "-1.26"
    },
    "at_end": {
      "baseline": "8.32",
      "scenario": "7.06",
      "delta": "-1.26"
    }
  },
  "fi": {
    "fi_number": {
      "baseline": "714042.04",
      "scenario": "714042.04",
      "delta": "0.00"
    },
    "monthly_spending": {
      "baseline": "2037.09",
      "scenario": "2037.09",
      "delta": "0.00"
    },
    "fi_month": {
      "baseline": "2044-08",
      "scenario": "2044-09",
      "delta_months": 1
    },
    "months_gained": -1
  },
  "break_evens": [],
  "tax": {
    "status": "none",
    "reason": null,
    "years": [],
    "this_year": null,
    "change_this_year": "0.00",
    "total_change": "0.00",
    "carried_forward": false
  },
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
    "nominal_returns": null,
    "cma": null
  },
  "placeholders": [
    "real_return",
    "safe_withdrawal_rate",
    "surplus_invested",
    "drawdown_horizon",
    "inflation"
  ],
  "versions": {
    "schema": "salli.scenario/1",
    "engine": "4",
    "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
    "rule_sets": []
  },
  "data_as_of": "2026-10-09",
  "is_stale": false,
  "notes": [],
  "timeline": {
    "daily": [
      {
        "date": "2026-10-11",
        "baseline": "15803.09",
        "scenario": "15803.09"
      },
      {
        "date": "2026-10-12",
        "baseline": "15804.72",
        "scenario": "15804.72"
      },
      {
        "date": "2026-10-13",
        "baseline": "15806.34",
        "scenario": "15806.34"
      },
      {
        "date": "2026-10-14",
        "baseline": "15807.97",
        "scenario": "15807.97"
      },
      {
        "date": "2026-10-15",
        "baseline": "15809.59",
        "scenario": "15809.59"
      },
      {
        "date": "2026-10-16",
        "baseline": "15811.22",
        "scenario": "15811.22"
      },
      {
        "date": "2026-10-17",
        "baseline": "15812.84",
        "scenario": "15812.84"
      },
      {
        "date": "2026-10-18",
        "baseline": "15740.01",
        "scenario": "15740.01"
      },
      {
        "date": "2026-10-19",
        "baseline": "15741.64",
        "scenario": "15741.64"
      },
      {
        "date": "2026-10-20",
        "baseline": "15743.26",
        "scenario": "15743.26"
      },
      {
        "date": "2026-10-21",
        "baseline": "15744.89",
        "scenario": "15744.89"
      },
      {
        "date": "2026-10-22",
        "baseline": "15746.51",
        "scenario": "15746.51"
      },
      {
        "date": "2026-10-23",
        "baseline": "15748.14",
        "scenario": "15748.14"
      },
      {
        "date": "2026-10-24",
        "baseline": "15749.76",
        "scenario": "15749.76"
      },
      {
        "date": "2026-10-25",
        "baseline": "19751.38",
        "scenario": "19751.38"
      },
      {
        "date": "2026-10-26",
        "baseline": "19253.01",
        "scenario": "19253.01"
      },
      {
        "date": "2026-10-27",
        "baseline": "19254.63",
        "scenario": "19254.63"
      },
      {
        "date": "2026-10-28",
        "baseline": "19256.26",
        "scenario": "19256.26"
      },
      {
        "date": "2026-10-29",
        "baseline": "19257.88",
        "scenario": "19257.88"
      },
      {
        "date": "2026-10-30",
        "baseline": "19259.51",
        "scenario": "19259.51"
      },
      {
        "date": "2026-10-31",
        "baseline": "15801.47",
        "scenario": "15801.47"
      },
      {
        "date": "2026-11-01",
        "baseline": "14293.10",
        "scenario": "14293.10"
      },
      {
        "date": "2026-11-02",
        "baseline": "14284.74",
        "scenario": "11884.74"
      },
      {
        "date": "2026-11-03",
        "baseline": "14276.37",
        "scenario": "11876.37"
      },
      {
        "date": "2026-11-04",
        "baseline": "14268.01",
        "scenario": "11868.01"
      },
      {
        "date": "2026-11-05",
        "baseline": "14259.64",
        "scenario": "11859.64"
      },
      {
        "date": "2026-11-06",
        "baseline": "14251.28",
        "scenario": "11851.28"
      },
      {
        "date": "2026-11-07",
        "baseline": "14242.91",
        "scenario": "11842.91"
      },
      {
        "date": "2026-11-08",
        "baseline": "14221.55",
        "scenario": "11821.55"
      },
      {
        "date": "2026-11-09",
        "baseline": "14213.19",
        "scenario": "11813.19"
      },
      {
        "date": "2026-11-10",
        "baseline": "14204.82",
        "scenario": "11804.82"
      },
      {
        "date": "2026-11-11",
        "baseline": "14196.46",
        "scenario": "11796.46"
      },
      {
        "date": "2026-11-12",
        "baseline": "14188.09",
        "scenario": "11788.09"
      },
      {
        "date": "2026-11-13",
        "baseline": "14179.73",
        "scenario": "11779.73"
      },
      {
        "date": "2026-11-14",
        "baseline": "14171.36",
        "scenario": "11771.36"
      },
      {
        "date": "2026-11-15",
        "baseline": "14162.99",
        "scenario": "11762.99"
      },
      {
        "date": "2026-11-16",
        "baseline": "14154.63",
        "scenario": "11754.63"
      },
      {
        "date": "2026-11-17",
        "baseline": "14146.26",
        "scenario": "11746.26"
      },
      {
        "date": "2026-11-18",
        "baseline": "14063.45",
        "scenario": "11663.45"
      },
      {
        "date": "2026-11-19",
        "baseline": "14055.08",
        "scenario": "11655.08"
      },
      {
        "date": "2026-11-20",
        "baseline": "14046.72",
        "scenario": "11646.72"
      },
      {
        "date": "2026-11-21",
        "baseline": "14038.35",
        "scenario": "11638.35"
      },
      {
        "date": "2026-11-22",
        "baseline": "14029.99",
        "scenario": "11629.99"
      },
      {
        "date": "2026-11-23",
        "baseline": "14021.62",
        "scenario": "11621.62"
      },
      {
        "date": "2026-11-24",
        "baseline": "14013.25",
        "scenario": "11613.25"
      },
      {
        "date": "2026-11-25",
        "baseline": "18004.89",
        "scenario": "15604.89"
      },
      {
        "date": "2026-11-26",
        "baseline": "17496.52",
        "scenario": "15096.52"
      },
      {
        "date": "2026-11-27",
        "baseline": "17488.16",
        "scenario": "15088.16"
      },
      {
        "date": "2026-11-28",
        "baseline": "17479.79",
        "scenario": "15079.79"
      },
      {
        "date": "2026-11-29",
        "baseline": "17471.43",
        "scenario": "15071.43"
      },
      {
        "date": "2026-11-30",
        "baseline": "15801.47",
        "scenario": "13401.47"
      },
      {
        "date": "2026-12-01",
        "baseline": "14293.37",
        "scenario": "11893.37"
      },
      {
        "date": "2026-12-02",
        "baseline": "14285.28",
        "scenario": "11885.28"
      },
      {
        "date": "2026-12-03",
        "baseline": "14277.18",
        "scenario": "11877.18"
      },
      {
        "date": "2026-12-04",
        "baseline": "14269.09",
        "scenario": "11869.09"
      },
      {
        "date": "2026-12-05",
        "baseline": "14260.99",
        "scenario": "11860.99"
      },
      {
        "date": "2026-12-06",
        "baseline": "14252.90",
        "scenario": "11852.90"
      },
      {
        "date": "2026-12-07",
        "baseline": "14244.80",
        "scenario": "11844.80"
      },
      {
        "date": "2026-12-08",
        "baseline": "14223.71",
        "scenario": "11823.71"
      },
      {
        "date": "2026-12-09",
        "baseline": "14215.62",
        "scenario": "11815.62"
      },
      {
        "date": "2026-12-10",
        "baseline": "14207.52",
        "scenario": "11807.52"
      },
      {
        "date": "2026-12-11",
        "baseline": "14199.43",
        "scenario": "11799.43"
      },
      {
        "date": "2026-12-12",
        "baseline": "14191.33",
        "scenario": "11791.33"
      },
      {
        "date": "2026-12-13",
        "baseline": "14183.23",
        "scenario": "11783.23"
      },
      {
        "date": "2026-12-14",
        "baseline": "14175.14",
        "scenario": "11775.14"
      },
      {
        "date": "2026-12-15",
        "baseline": "14167.04",
        "scenario": "11767.04"
      },
      {
        "date": "2026-12-16",
        "baseline": "14158.95",
        "scenario": "11758.95"
      },
      {
        "date": "2026-12-17",
        "baseline": "14150.85",
        "scenario": "11750.85"
      },
      {
        "date": "2026-12-18",
        "baseline": "14068.31",
        "scenario": "11668.31"
      },
      {
        "date": "2026-12-19",
        "baseline": "14060.21",
        "scenario": "11660.21"
      },
      {
        "date": "2026-12-20",
        "baseline": "14052.11",
        "scenario": "11652.11"
      },
      {
        "date": "2026-12-21",
        "baseline": "14044.02",
        "scenario": "11644.02"
      },
      {
        "date": "2026-12-22",
        "baseline": "14035.92",
        "scenario": "11635.92"
      },
      {
        "date": "2026-12-23",
        "baseline": "14027.83",
        "scenario": "11627.83"
      },
      {
        "date": "2026-12-24",
        "baseline": "14019.73",
        "scenario": "11619.73"
      },
      {
        "date": "2026-12-25",
        "baseline": "18011.63",
        "scenario": "15611.63"
      },
      {
        "date": "2026-12-26",
        "baseline": "17503.54",
        "scenario": "15103.54"
      },
      {
        "date": "2026-12-27",
        "baseline": "17495.44",
        "scenario": "15095.44"
      },
      {
        "date": "2026-12-28",
        "baseline": "17487.35",
        "scenario": "15087.35"
      },
      {
        "date": "2026-12-29",
        "baseline": "17479.25",
        "scenario": "15079.25"
      },
      {
        "date": "2026-12-30",
        "baseline": "17471.16",
        "scenario": "15071.16"
      },
      {
        "date": "2026-12-31",
        "baseline": "15801.47",
        "scenario": "13401.47"
      },
      {
        "date": "2027-01-01",
        "baseline": "14293.37",
        "scenario": "11893.37"
      },
      {
        "date": "2027-01-02",
        "baseline": "14285.28",
        "scenario": "11885.28"
      },
      {
        "date": "2027-01-03",
        "baseline": "14277.18",
        "scenario": "11877.18"
      },
      {
        "date": "2027-01-04",
        "baseline": "14269.09",
        "scenario": "11869.09"
      },
      {
        "date": "2027-01-05",
        "baseline": "14260.99",
        "scenario": "11860.99"
      },
      {
        "date": "2027-01-06",
        "baseline": "14252.90",
        "scenario": "11852.90"
      },
      {
        "date": "2027-01-07",
        "baseline": "14244.80",
        "scenario": "11844.80"
      },
      {
        "date": "2027-01-08",
        "baseline": "14223.71",
        "scenario": "11823.71"
      },
      {
        "date": "2027-01-09",
        "baseline": "14215.62",
        "scenario": "11815.62"
      },
      {
        "date": "2027-01-10",
        "baseline": "14207.52",
        "scenario": "11807.52"
      },
      {
        "date": "2027-01-11",
        "baseline": "14199.43",
        "scenario": "11799.43"
      },
      {
        "date": "2027-01-12",
        "baseline": "14191.33",
        "scenario": "11791.33"
      },
      {
        "date": "2027-01-13",
        "baseline": "14183.23",
        "scenario": "11783.23"
      },
      {
        "date": "2027-01-14",
        "baseline": "14175.14",
        "scenario": "11775.14"
      },
      {
        "date": "2027-01-15",
        "baseline": "14167.04",
        "scenario": "11767.04"
      },
      {
        "date": "2027-01-16",
        "baseline": "14158.95",
        "scenario": "11758.95"
      },
      {
        "date": "2027-01-17",
        "baseline": "14150.85",
        "scenario": "11750.85"
      },
      {
        "date": "2027-01-18",
        "baseline": "14068.31",
        "scenario": "11668.31"
      },
      {
        "date": "2027-01-19",
        "baseline": "14060.21",
        "scenario": "11660.21"
      },
      {
        "date": "2027-01-20",
        "baseline": "14052.11",
        "scenario": "11652.11"
      },
      {
        "date": "2027-01-21",
        "baseline": "14044.02",
        "scenario": "11644.02"
      },
      {
        "date": "2027-01-22",
        "baseline": "14035.92",
        "scenario": "11635.92"
      },
      {
        "date": "2027-01-23",
        "baseline": "14027.83",
        "scenario": "11627.83"
      },
      {
        "date": "2027-01-24",
        "baseline": "14019.73",
        "scenario": "11619.73"
      },
      {
        "date": "2027-01-25",
        "baseline": "18011.63",
        "scenario": "15611.63"
      },
      {
        "date": "2027-01-26",
        "baseline": "17503.54",
        "scenario": "15103.54"
      },
      {
        "date": "2027-01-27",
        "baseline": "17495.44",
        "scenario": "15095.44"
      },
      {
        "date": "2027-01-28",
        "baseline": "17487.35",
        "scenario": "15087.35"
      },
      {
        "date": "2027-01-29",
        "baseline": "17479.25",
        "scenario": "15079.25"
      },
      {
        "date": "2027-01-30",
        "baseline": "17471.16",
        "scenario": "15071.16"
      },
      {
        "date": "2027-01-31",
        "baseline": "15801.47",
        "scenario": "13401.47"
      },
      {
        "date": "2027-02-01",
        "baseline": "14292.51",
        "scenario": "11892.51"
      },
      {
        "date": "2027-02-02",
        "baseline": "14283.54",
        "scenario": "11883.54"
      },
      {
        "date": "2027-02-03",
        "baseline": "14274.58",
        "scenario": "11874.58"
      },
      {
        "date": "2027-02-04",
        "baseline": "14265.62",
        "scenario": "11865.62"
      },
      {
        "date": "2027-02-05",
        "baseline": "14256.65",
        "scenario": "11856.65"
      },
      {
        "date": "2027-02-06",
        "baseline": "14247.69",
        "scenario": "11847.69"
      },
      {
        "date": "2027-02-07",
        "baseline": "14238.73",
        "scenario": "11838.73"
      },
      {
        "date": "2027-02-08",
        "baseline": "14216.77",
        "scenario": "11816.77"
      },
      {
        "date": "2027-02-09",
        "baseline": "14207.81",
        "scenario": "11807.81"
      },
      {
        "date": "2027-02-10",
        "baseline": "14198.85",
        "scenario": "11798.85"
      },
      {
        "date": "2027-02-11",
        "baseline": "14189.88",
        "scenario": "11789.88"
      },
      {
        "date": "2027-02-12",
        "baseline": "14180.92",
        "scenario": "11780.92"
      },
      {
        "date": "2027-02-13",
        "baseline": "14171.96",
        "scenario": "11771.96"
      },
      {
        "date": "2027-02-14",
        "baseline": "14162.99",
        "scenario": "11762.99"
      },
      {
        "date": "2027-02-15",
        "baseline": "14154.03",
        "scenario": "11754.03"
      },
      {
        "date": "2027-02-16",
        "baseline": "14145.07",
        "scenario": "11745.07"
      },
      {
        "date": "2027-02-17",
        "baseline": "14136.11",
        "scenario": "11736.11"
      },
      {
        "date": "2027-02-18",
        "baseline": "14052.69",
        "scenario": "11652.69"
      },
      {
        "date": "2027-02-19",
        "baseline": "14043.73",
        "scenario": "11643.73"
      },
      {
        "date": "2027-02-20",
        "baseline": "14034.77",
        "scenario": "11634.77"
      },
      {
        "date": "2027-02-21",
        "baseline": "14025.80",
        "scenario": "11625.80"
      },
      {
        "date": "2027-02-22",
        "baseline": "14016.84",
        "scenario": "11616.84"
      },
      {
        "date": "2027-02-23",
        "baseline": "14007.88",
        "scenario": "11607.88"
      },
      {
        "date": "2027-02-24",
        "baseline": "13998.91",
        "scenario": "11598.91"
      },
      {
        "date": "2027-02-25",
        "baseline": "17989.95",
        "scenario": "15589.95"
      },
      {
        "date": "2027-02-26",
        "baseline": "17480.99",
        "scenario": "15080.99"
      },
      {
        "date": "2027-02-27",
        "baseline": "17472.02",
        "scenario": "15072.02"
      },
      {
        "date": "2027-02-28",
        "baseline": "15801.47",
        "scenario": "13401.47"
      },
      {
        "date": "2027-03-01",
        "baseline": "14293.37",
        "scenario": "11893.37"
      },
      {
        "date": "2027-03-02",
        "baseline": "14285.28",
        "scenario": "11885.28"
      },
      {
        "date": "2027-03-03",
        "baseline": "14277.18",
        "scenario": "11877.18"
      },
      {
        "date": "2027-03-04",
        "baseline": "14269.09",
        "scenario": "11869.09"
      },
      {
        "date": "2027-03-05",
        "baseline": "14260.99",
        "scenario": "11860.99"
      },
      {
        "date": "2027-03-06",
        "baseline": "14252.90",
        "scenario": "11852.90"
      },
      {
        "date": "2027-03-07",
        "baseline": "14244.80",
        "scenario": "11844.80"
      },
      {
        "date": "2027-03-08",
        "baseline": "14223.71",
        "scenario": "11823.71"
      },
      {
        "date": "2027-03-09",
        "baseline": "14215.62",
        "scenario": "11815.62"
      },
      {
        "date": "2027-03-10",
        "baseline": "14207.52",
        "scenario": "11807.52"
      },
      {
        "date": "2027-03-11",
        "baseline": "14199.43",
        "scenario": "11799.43"
      },
      {
        "date": "2027-03-12",
        "baseline": "14191.33",
        "scenario": "11791.33"
      },
      {
        "date": "2027-03-13",
        "baseline": "14183.23",
        "scenario": "11783.23"
      },
      {
        "date": "2027-03-14",
        "baseline": "14175.14",
        "scenario": "11775.14"
      },
      {
        "date": "2027-03-15",
        "baseline": "14167.04",
        "scenario": "11767.04"
      },
      {
        "date": "2027-03-16",
        "baseline": "14158.95",
        "scenario": "11758.95"
      },
      {
        "date": "2027-03-17",
        "baseline": "14150.85",
        "scenario": "11750.85"
      },
      {
        "date": "2027-03-18",
        "baseline": "14068.31",
        "scenario": "11668.31"
      },
      {
        "date": "2027-03-19",
        "baseline": "14060.21",
        "scenario": "11660.21"
      },
      {
        "date": "2027-03-20",
        "baseline": "14052.11",
        "scenario": "11652.11"
      },
      {
        "date": "2027-03-21",
        "baseline": "14044.02",
        "scenario": "11644.02"
      },
      {
        "date": "2027-03-22",
        "baseline": "14035.92",
        "scenario": "11635.92"
      },
      {
        "date": "2027-03-23",
        "baseline": "14027.83",
        "scenario": "11627.83"
      },
      {
        "date": "2027-03-24",
        "baseline": "14019.73",
        "scenario": "11619.73"
      },
      {
        "date": "2027-03-25",
        "baseline": "18011.63",
        "scenario": "15611.63"
      },
      {
        "date": "2027-03-26",
        "baseline": "17503.54",
        "scenario": "15103.54"
      },
      {
        "date": "2027-03-27",
        "baseline": "17495.44",
        "scenario": "15095.44"
      },
      {
        "date": "2027-03-28",
        "baseline": "17487.35",
        "scenario": "15087.35"
      },
      {
        "date": "2027-03-29",
        "baseline": "17479.25",
        "scenario": "15079.25"
      },
      {
        "date": "2027-03-30",
        "baseline": "17471.16",
        "scenario": "15071.16"
      },
      {
        "date": "2027-03-31",
        "baseline": "15801.47",
        "scenario": "13401.47"
      },
      {
        "date": "2027-04-01",
        "baseline": "14293.10",
        "scenario": "11893.10"
      },
      {
        "date": "2027-04-02",
        "baseline": "14284.74",
        "scenario": "11884.74"
      },
      {
        "date": "2027-04-03",
        "baseline": "14276.37",
        "scenario": "11876.37"
      },
      {
        "date": "2027-04-04",
        "baseline": "14268.01",
        "scenario": "11868.01"
      },
      {
        "date": "2027-04-05",
        "baseline": "14259.64",
        "scenario": "11859.64"
      },
      {
        "date": "2027-04-06",
        "baseline": "14251.28",
        "scenario": "11851.28"
      },
      {
        "date": "2027-04-07",
        "baseline": "14242.91",
        "scenario": "11842.91"
      },
      {
        "date": "2027-04-08",
        "baseline": "14221.55",
        "scenario": "11821.55"
      },
      {
        "date": "2027-04-09",
        "baseline": "14213.19",
        "scenario": "11813.19"
      },
      {
        "date": "2027-04-10",
        "baseline": "14204.82",
        "scenario": "11804.82"
      },
      {
        "date": "2027-04-11",
        "baseline": "14196.46",
        "scenario": "11796.46"
      },
      {
        "date": "2027-04-12",
        "baseline": "14188.09",
        "scenario": "11788.09"
      },
      {
        "date": "2027-04-13",
        "baseline": "14179.73",
        "scenario": "11779.73"
      },
      {
        "date": "2027-04-14",
        "baseline": "14171.36",
        "scenario": "11771.36"
      },
      {
        "date": "2027-04-15",
        "baseline": "14162.99",
        "scenario": "11762.99"
      },
      {
        "date": "2027-04-16",
        "baseline": "14154.63",
        "scenario": "11754.63"
      },
      {
        "date": "2027-04-17",
        "baseline": "14146.26",
        "scenario": "11746.26"
      },
      {
        "date": "2027-04-18",
        "baseline": "14063.45",
        "scenario": "11663.45"
      },
      {
        "date": "2027-04-19",
        "baseline": "14055.08",
        "scenario": "11655.08"
      },
      {
        "date": "2027-04-20",
        "baseline": "14046.72",
        "scenario": "11646.72"
      },
      {
        "date": "2027-04-21",
        "baseline": "14038.35",
        "scenario": "11638.35"
      },
      {
        "date": "2027-04-22",
        "baseline": "14029.99",
        "scenario": "11629.99"
      },
      {
        "date": "2027-04-23",
        "baseline": "14021.62",
        "scenario": "11621.62"
      },
      {
        "date": "2027-04-24",
        "baseline": "14013.25",
        "scenario": "11613.25"
      },
      {
        "date": "2027-04-25",
        "baseline": "18004.89",
        "scenario": "15604.89"
      },
      {
        "date": "2027-04-26",
        "baseline": "17496.52",
        "scenario": "15096.52"
      },
      {
        "date": "2027-04-27",
        "baseline": "17488.16",
        "scenario": "15088.16"
      },
      {
        "date": "2027-04-28",
        "baseline": "17479.79",
        "scenario": "15079.79"
      },
      {
        "date": "2027-04-29",
        "baseline": "17471.43",
        "scenario": "15071.43"
      },
      {
        "date": "2027-04-30",
        "baseline": "15801.47",
        "scenario": "13401.47"
      },
      {
        "date": "2027-05-01",
        "baseline": "14293.37",
        "scenario": "11893.37"
      },
      {
        "date": "2027-05-02",
        "baseline": "14285.28",
        "scenario": "11885.28"
      },
      {
        "date": "2027-05-03",
        "baseline": "14277.18",
        "scenario": "11877.18"
      },
      {
        "date": "2027-05-04",
        "baseline": "14269.09",
        "scenario": "11869.09"
      },
      {
        "date": "2027-05-05",
        "baseline": "14260.99",
        "scenario": "11860.99"
      },
      {
        "date": "2027-05-06",
        "baseline": "14252.90",
        "scenario": "11852.90"
      },
      {
        "date": "2027-05-07",
        "baseline": "14244.80",
        "scenario": "11844.80"
      },
      {
        "date": "2027-05-08",
        "baseline": "14223.71",
        "scenario": "11823.71"
      },
      {
        "date": "2027-05-09",
        "baseline": "14215.62",
        "scenario": "11815.62"
      },
      {
        "date": "2027-05-10",
        "baseline": "14207.52",
        "scenario": "11807.52"
      },
      {
        "date": "2027-05-11",
        "baseline": "14199.43",
        "scenario": "11799.43"
      },
      {
        "date": "2027-05-12",
        "baseline": "14191.33",
        "scenario": "11791.33"
      },
      {
        "date": "2027-05-13",
        "baseline": "14183.23",
        "scenario": "11783.23"
      },
      {
        "date": "2027-05-14",
        "baseline": "14175.14",
        "scenario": "11775.14"
      },
      {
        "date": "2027-05-15",
        "baseline": "14167.04",
        "scenario": "11767.04"
      },
      {
        "date": "2027-05-16",
        "baseline": "14158.95",
        "scenario": "11758.95"
      },
      {
        "date": "2027-05-17",
        "baseline": "14150.85",
        "scenario": "11750.85"
      },
      {
        "date": "2027-05-18",
        "baseline": "14068.31",
        "scenario": "11668.31"
      },
      {
        "date": "2027-05-19",
        "baseline": "14060.21",
        "scenario": "11660.21"
      },
      {
        "date": "2027-05-20",
        "baseline": "14052.11",
        "scenario": "11652.11"
      },
      {
        "date": "2027-05-21",
        "baseline": "14044.02",
        "scenario": "11644.02"
      },
      {
        "date": "2027-05-22",
        "baseline": "14035.92",
        "scenario": "11635.92"
      },
      {
        "date": "2027-05-23",
        "baseline": "14027.83",
        "scenario": "11627.83"
      },
      {
        "date": "2027-05-24",
        "baseline": "14019.73",
        "scenario": "11619.73"
      },
      {
        "date": "2027-05-25",
        "baseline": "18011.63",
        "scenario": "15611.63"
      },
      {
        "date": "2027-05-26",
        "baseline": "17503.54",
        "scenario": "15103.54"
      },
      {
        "date": "2027-05-27",
        "baseline": "17495.44",
        "scenario": "15095.44"
      },
      {
        "date": "2027-05-28",
        "baseline": "17487.35",
        "scenario": "15087.35"
      },
      {
        "date": "2027-05-29",
        "baseline": "17479.25",
        "scenario": "15079.25"
      },
      {
        "date": "2027-05-30",
        "baseline": "17471.16",
        "scenario": "15071.16"
      },
      {
        "date": "2027-05-31",
        "baseline": "15801.47",
        "scenario": "13401.47"
      },
      {
        "date": "2027-06-01",
        "baseline": "14293.10",
        "scenario": "11893.10"
      },
      {
        "date": "2027-06-02",
        "baseline": "14284.74",
        "scenario": "11884.74"
      },
      {
        "date": "2027-06-03",
        "baseline": "14276.37",
        "scenario": "11876.37"
      },
      {
        "date": "2027-06-04",
        "baseline": "14268.01",
        "scenario": "11868.01"
      },
      {
        "date": "2027-06-05",
        "baseline": "14259.64",
        "scenario": "11859.64"
      },
      {
        "date": "2027-06-06",
        "baseline": "14251.28",
        "scenario": "11851.28"
      },
      {
        "date": "2027-06-07",
        "baseline": "14242.91",
        "scenario": "11842.91"
      },
      {
        "date": "2027-06-08",
        "baseline": "14221.55",
        "scenario": "11821.55"
      },
      {
        "date": "2027-06-09",
        "baseline": "14213.19",
        "scenario": "11813.19"
      },
      {
        "date": "2027-06-10",
        "baseline": "14204.82",
        "scenario": "11804.82"
      },
      {
        "date": "2027-06-11",
        "baseline": "14196.46",
        "scenario": "11796.46"
      },
      {
        "date": "2027-06-12",
        "baseline": "14188.09",
        "scenario": "11788.09"
      },
      {
        "date": "2027-06-13",
        "baseline": "14179.73",
        "scenario": "11779.73"
      },
      {
        "date": "2027-06-14",
        "baseline": "14171.36",
        "scenario": "11771.36"
      },
      {
        "date": "2027-06-15",
        "baseline": "14162.99",
        "scenario": "11762.99"
      },
      {
        "date": "2027-06-16",
        "baseline": "14154.63",
        "scenario": "11754.63"
      },
      {
        "date": "2027-06-17",
        "baseline": "14146.26",
        "scenario": "11746.26"
      },
      {
        "date": "2027-06-18",
        "baseline": "14063.45",
        "scenario": "11663.45"
      },
      {
        "date": "2027-06-19",
        "baseline": "14055.08",
        "scenario": "11655.08"
      },
      {
        "date": "2027-06-20",
        "baseline": "14046.72",
        "scenario": "11646.72"
      },
      {
        "date": "2027-06-21",
        "baseline": "14038.35",
        "scenario": "11638.35"
      },
      {
        "date": "2027-06-22",
        "baseline": "14029.99",
        "scenario": "11629.99"
      },
      {
        "date": "2027-06-23",
        "baseline": "14021.62",
        "scenario": "11621.62"
      },
      {
        "date": "2027-06-24",
        "baseline": "14013.25",
        "scenario": "11613.25"
      },
      {
        "date": "2027-06-25",
        "baseline": "18004.89",
        "scenario": "15604.89"
      },
      {
        "date": "2027-06-26",
        "baseline": "17496.52",
        "scenario": "15096.52"
      },
      {
        "date": "2027-06-27",
        "baseline": "17488.16",
        "scenario": "15088.16"
      },
      {
        "date": "2027-06-28",
        "baseline": "17479.79",
        "scenario": "15079.79"
      },
      {
        "date": "2027-06-29",
        "baseline": "17471.43",
        "scenario": "15071.43"
      },
      {
        "date": "2027-06-30",
        "baseline": "15801.47",
        "scenario": "13401.47"
      },
      {
        "date": "2027-07-01",
        "baseline": "14293.37",
        "scenario": "11893.37"
      },
      {
        "date": "2027-07-02",
        "baseline": "14285.28",
        "scenario": "11885.28"
      },
      {
        "date": "2027-07-03",
        "baseline": "14277.18",
        "scenario": "11877.18"
      },
      {
        "date": "2027-07-04",
        "baseline": "14269.09",
        "scenario": "11869.09"
      },
      {
        "date": "2027-07-05",
        "baseline": "14260.99",
        "scenario": "11860.99"
      },
      {
        "date": "2027-07-06",
        "baseline": "14252.90",
        "scenario": "11852.90"
      },
      {
        "date": "2027-07-07",
        "baseline": "14244.80",
        "scenario": "11844.80"
      },
      {
        "date": "2027-07-08",
        "baseline": "14223.71",
        "scenario": "11823.71"
      },
      {
        "date": "2027-07-09",
        "baseline": "14215.62",
        "scenario": "11815.62"
      },
      {
        "date": "2027-07-10",
        "baseline": "14207.52",
        "scenario": "11807.52"
      },
      {
        "date": "2027-07-11",
        "baseline": "14199.43",
        "scenario": "11799.43"
      },
      {
        "date": "2027-07-12",
        "baseline": "14191.33",
        "scenario": "11791.33"
      },
      {
        "date": "2027-07-13",
        "baseline": "14183.23",
        "scenario": "11783.23"
      },
      {
        "date": "2027-07-14",
        "baseline": "14175.14",
        "scenario": "11775.14"
      },
      {
        "date": "2027-07-15",
        "baseline": "14167.04",
        "scenario": "11767.04"
      },
      {
        "date": "2027-07-16",
        "baseline": "14158.95",
        "scenario": "11758.95"
      },
      {
        "date": "2027-07-17",
        "baseline": "14150.85",
        "scenario": "11750.85"
      },
      {
        "date": "2027-07-18",
        "baseline": "14068.31",
        "scenario": "11668.31"
      },
      {
        "date": "2027-07-19",
        "baseline": "14060.21",
        "scenario": "11660.21"
      },
      {
        "date": "2027-07-20",
        "baseline": "14052.11",
        "scenario": "11652.11"
      },
      {
        "date": "2027-07-21",
        "baseline": "14044.02",
        "scenario": "11644.02"
      },
      {
        "date": "2027-07-22",
        "baseline": "14035.92",
        "scenario": "11635.92"
      },
      {
        "date": "2027-07-23",
        "baseline": "14027.83",
        "scenario": "11627.83"
      },
      {
        "date": "2027-07-24",
        "baseline": "14019.73",
        "scenario": "11619.73"
      },
      {
        "date": "2027-07-25",
        "baseline": "18011.63",
        "scenario": "15611.63"
      },
      {
        "date": "2027-07-26",
        "baseline": "17503.54",
        "scenario": "15103.54"
      },
      {
        "date": "2027-07-27",
        "baseline": "17495.44",
        "scenario": "15095.44"
      },
      {
        "date": "2027-07-28",
        "baseline": "17487.35",
        "scenario": "15087.35"
      },
      {
        "date": "2027-07-29",
        "baseline": "17479.25",
        "scenario": "15079.25"
      },
      {
        "date": "2027-07-30",
        "baseline": "17471.16",
        "scenario": "15071.16"
      },
      {
        "date": "2027-07-31",
        "baseline": "15801.47",
        "scenario": "13401.47"
      },
      {
        "date": "2027-08-01",
        "baseline": "14293.37",
        "scenario": "11893.37"
      },
      {
        "date": "2027-08-02",
        "baseline": "14285.28",
        "scenario": "11885.28"
      },
      {
        "date": "2027-08-03",
        "baseline": "14277.18",
        "scenario": "11877.18"
      },
      {
        "date": "2027-08-04",
        "baseline": "14269.09",
        "scenario": "11869.09"
      },
      {
        "date": "2027-08-05",
        "baseline": "14260.99",
        "scenario": "11860.99"
      },
      {
        "date": "2027-08-06",
        "baseline": "14252.90",
        "scenario": "11852.90"
      },
      {
        "date": "2027-08-07",
        "baseline": "14244.80",
        "scenario": "11844.80"
      },
      {
        "date": "2027-08-08",
        "baseline": "14223.71",
        "scenario": "11823.71"
      },
      {
        "date": "2027-08-09",
        "baseline": "14215.62",
        "scenario": "11815.62"
      },
      {
        "date": "2027-08-10",
        "baseline": "14207.52",
        "scenario": "11807.52"
      },
      {
        "date": "2027-08-11",
        "baseline": "14199.43",
        "scenario": "11799.43"
      },
      {
        "date": "2027-08-12",
        "baseline": "14191.33",
        "scenario": "11791.33"
      },
      {
        "date": "2027-08-13",
        "baseline": "14183.23",
        "scenario": "11783.23"
      },
      {
        "date": "2027-08-14",
        "baseline": "14175.14",
        "scenario": "11775.14"
      },
      {
        "date": "2027-08-15",
        "baseline": "14167.04",
        "scenario": "11767.04"
      },
      {
        "date": "2027-08-16",
        "baseline": "14158.95",
        "scenario": "11758.95"
      },
      {
        "date": "2027-08-17",
        "baseline": "14150.85",
        "scenario": "11750.85"
      },
      {
        "date": "2027-08-18",
        "baseline": "14068.31",
        "scenario": "11668.31"
      },
      {
        "date": "2027-08-19",
        "baseline": "14060.21",
        "scenario": "11660.21"
      },
      {
        "date": "2027-08-20",
        "baseline": "14052.11",
        "scenario": "11652.11"
      },
      {
        "date": "2027-08-21",
        "baseline": "14044.02",
        "scenario": "11644.02"
      },
      {
        "date": "2027-08-22",
        "baseline": "14035.92",
        "scenario": "11635.92"
      },
      {
        "date": "2027-08-23",
        "baseline": "14027.83",
        "scenario": "11627.83"
      },
      {
        "date": "2027-08-24",
        "baseline": "14019.73",
        "scenario": "11619.73"
      },
      {
        "date": "2027-08-25",
        "baseline": "18011.63",
        "scenario": "15611.63"
      },
      {
        "date": "2027-08-26",
        "baseline": "17503.54",
        "scenario": "15103.54"
      },
      {
        "date": "2027-08-27",
        "baseline": "17495.44",
        "scenario": "15095.44"
      },
      {
        "date": "2027-08-28",
        "baseline": "17487.35",
        "scenario": "15087.35"
      },
      {
        "date": "2027-08-29",
        "baseline": "17479.25",
        "scenario": "15079.25"
      },
      {
        "date": "2027-08-30",
        "baseline": "17471.16",
        "scenario": "15071.16"
      },
      {
        "date": "2027-08-31",
        "baseline": "15801.47",
        "scenario": "13401.47"
      },
      {
        "date": "2027-09-01",
        "baseline": "14293.10",
        "scenario": "11893.10"
      },
      {
        "date": "2027-09-02",
        "baseline": "14284.74",
        "scenario": "11884.74"
      },
      {
        "date": "2027-09-03",
        "baseline": "14276.37",
        "scenario": "11876.37"
      },
      {
        "date": "2027-09-04",
        "baseline": "14268.01",
        "scenario": "11868.01"
      },
      {
        "date": "2027-09-05",
        "baseline": "14259.64",
        "scenario": "11859.64"
      },
      {
        "date": "2027-09-06",
        "baseline": "14251.28",
        "scenario": "11851.28"
      },
      {
        "date": "2027-09-07",
        "baseline": "14242.91",
        "scenario": "11842.91"
      },
      {
        "date": "2027-09-08",
        "baseline": "14221.55",
        "scenario": "11821.55"
      },
      {
        "date": "2027-09-09",
        "baseline": "14213.19",
        "scenario": "11813.19"
      },
      {
        "date": "2027-09-10",
        "baseline": "14204.82",
        "scenario": "11804.82"
      },
      {
        "date": "2027-09-11",
        "baseline": "14196.46",
        "scenario": "11796.46"
      },
      {
        "date": "2027-09-12",
        "baseline": "14188.09",
        "scenario": "11788.09"
      },
      {
        "date": "2027-09-13",
        "baseline": "14179.73",
        "scenario": "11779.73"
      },
      {
        "date": "2027-09-14",
        "baseline": "14171.36",
        "scenario": "11771.36"
      },
      {
        "date": "2027-09-15",
        "baseline": "14162.99",
        "scenario": "11762.99"
      },
      {
        "date": "2027-09-16",
        "baseline": "14154.63",
        "scenario": "11754.63"
      },
      {
        "date": "2027-09-17",
        "baseline": "14146.26",
        "scenario": "11746.26"
      },
      {
        "date": "2027-09-18",
        "baseline": "14063.45",
        "scenario": "11663.45"
      },
      {
        "date": "2027-09-19",
        "baseline": "14055.08",
        "scenario": "11655.08"
      },
      {
        "date": "2027-09-20",
        "baseline": "14046.72",
        "scenario": "11646.72"
      },
      {
        "date": "2027-09-21",
        "baseline": "14038.35",
        "scenario": "11638.35"
      },
      {
        "date": "2027-09-22",
        "baseline": "14029.99",
        "scenario": "11629.99"
      },
      {
        "date": "2027-09-23",
        "baseline": "14021.62",
        "scenario": "11621.62"
      },
      {
        "date": "2027-09-24",
        "baseline": "14013.25",
        "scenario": "11613.25"
      },
      {
        "date": "2027-09-25",
        "baseline": "18004.89",
        "scenario": "15604.89"
      },
      {
        "date": "2027-09-26",
        "baseline": "17496.52",
        "scenario": "15096.52"
      },
      {
        "date": "2027-09-27",
        "baseline": "17488.16",
        "scenario": "15088.16"
      },
      {
        "date": "2027-09-28",
        "baseline": "17479.79",
        "scenario": "15079.79"
      },
      {
        "date": "2027-09-29",
        "baseline": "17471.43",
        "scenario": "15071.43"
      },
      {
        "date": "2027-09-30",
        "baseline": "15801.47",
        "scenario": "13401.47"
      },
      {
        "date": "2027-10-01",
        "baseline": "14293.37",
        "scenario": "11893.37"
      },
      {
        "date": "2027-10-02",
        "baseline": "14285.28",
        "scenario": "11885.28"
      },
      {
        "date": "2027-10-03",
        "baseline": "14277.18",
        "scenario": "11877.18"
      },
      {
        "date": "2027-10-04",
        "baseline": "14269.09",
        "scenario": "11869.09"
      },
      {
        "date": "2027-10-05",
        "baseline": "14260.99",
        "scenario": "11860.99"
      },
      {
        "date": "2027-10-06",
        "baseline": "14252.90",
        "scenario": "11852.90"
      },
      {
        "date": "2027-10-07",
        "baseline": "14244.80",
        "scenario": "11844.80"
      },
      {
        "date": "2027-10-08",
        "baseline": "14223.71",
        "scenario": "11823.71"
      },
      {
        "date": "2027-10-09",
        "baseline": "14215.62",
        "scenario": "11815.62"
      },
      {
        "date": "2027-10-10",
        "baseline": "14207.52",
        "scenario": "11807.52"
      },
      {
        "date": "2027-10-11",
        "baseline": "14199.43",
        "scenario": "11799.43"
      },
      {
        "date": "2027-10-12",
        "baseline": "14191.33",
        "scenario": "11791.33"
      },
      {
        "date": "2027-10-13",
        "baseline": "14183.23",
        "scenario": "11783.23"
      },
      {
        "date": "2027-10-14",
        "baseline": "14175.14",
        "scenario": "11775.14"
      },
      {
        "date": "2027-10-15",
        "baseline": "14167.04",
        "scenario": "11767.04"
      },
      {
        "date": "2027-10-16",
        "baseline": "14158.95",
        "scenario": "11758.95"
      },
      {
        "date": "2027-10-17",
        "baseline": "14150.85",
        "scenario": "11750.85"
      },
      {
        "date": "2027-10-18",
        "baseline": "14068.31",
        "scenario": "11668.31"
      },
      {
        "date": "2027-10-19",
        "baseline": "14060.21",
        "scenario": "11660.21"
      },
      {
        "date": "2027-10-20",
        "baseline": "14052.11",
        "scenario": "11652.11"
      },
      {
        "date": "2027-10-21",
        "baseline": "14044.02",
        "scenario": "11644.02"
      },
      {
        "date": "2027-10-22",
        "baseline": "14035.92",
        "scenario": "11635.92"
      },
      {
        "date": "2027-10-23",
        "baseline": "14027.83",
        "scenario": "11627.83"
      },
      {
        "date": "2027-10-24",
        "baseline": "14019.73",
        "scenario": "11619.73"
      },
      {
        "date": "2027-10-25",
        "baseline": "18011.63",
        "scenario": "15611.63"
      },
      {
        "date": "2027-10-26",
        "baseline": "17503.54",
        "scenario": "15103.54"
      },
      {
        "date": "2027-10-27",
        "baseline": "17495.44",
        "scenario": "15095.44"
      },
      {
        "date": "2027-10-28",
        "baseline": "17487.35",
        "scenario": "15087.35"
      },
      {
        "date": "2027-10-29",
        "baseline": "17479.25",
        "scenario": "15079.25"
      },
      {
        "date": "2027-10-30",
        "baseline": "17471.16",
        "scenario": "15071.16"
      },
      {
        "date": "2027-10-31",
        "baseline": "15801.47",
        "scenario": "13401.47"
      }
    ],
    "monthly": [
      {
        "month": "2026-10",
        "date": "2026-10-11",
        "cash": {
          "baseline": "15801.47",
          "scenario": "15801.47",
          "delta": "0.00"
        },
        "net_worth": {
          "baseline": "335901.47",
          "scenario": "335901.47",
          "delta": "0.00"
        }
      },
      {
        "month": "2026-10",
        "date": "2026-10-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "15801.47",
          "delta": "0.00"
        },
        "net_worth": {
          "baseline": "339446.94",
          "scenario": "339446.94",
          "delta": "0.00"
        }
      },
      {
        "month": "2026-11",
        "date": "2026-11-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "341638.33",
          "scenario": "339238.33",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2026-12",
        "date": "2026-12-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "343837.56",
          "scenario": "341437.56",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-01",
        "date": "2027-01-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "346044.63",
          "scenario": "343644.63",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-02",
        "date": "2027-02-28",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "348259.58",
          "scenario": "345859.58",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-03",
        "date": "2027-03-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "350482.42",
          "scenario": "348082.42",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-04",
        "date": "2027-04-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "352713.21",
          "scenario": "350313.21",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-05",
        "date": "2027-05-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "354951.95",
          "scenario": "352551.95",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-06",
        "date": "2027-06-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "357198.69",
          "scenario": "354798.69",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-07",
        "date": "2027-07-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "359453.45",
          "scenario": "357053.45",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-08",
        "date": "2027-08-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "361716.25",
          "scenario": "359316.25",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-09",
        "date": "2027-09-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "363987.14",
          "scenario": "361587.14",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-10",
        "date": "2027-10-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "366266.13",
          "scenario": "363866.13",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-11",
        "date": "2027-11-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "368553.27",
          "scenario": "366153.27",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2027-12",
        "date": "2027-12-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "370848.58",
          "scenario": "368448.58",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-01",
        "date": "2028-01-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "373152.08",
          "scenario": "370752.08",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-02",
        "date": "2028-02-29",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "375463.82",
          "scenario": "373063.82",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-03",
        "date": "2028-03-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "377783.80",
          "scenario": "375383.80",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-04",
        "date": "2028-04-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "380112.09",
          "scenario": "377712.09",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-05",
        "date": "2028-05-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "382448.69",
          "scenario": "380048.69",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-06",
        "date": "2028-06-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "384793.64",
          "scenario": "382393.64",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-07",
        "date": "2028-07-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "387146.98",
          "scenario": "384746.98",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-08",
        "date": "2028-08-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "389508.73",
          "scenario": "387108.73",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-09",
        "date": "2028-09-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "391878.91",
          "scenario": "389478.91",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-10",
        "date": "2028-10-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "394257.57",
          "scenario": "391857.57",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-11",
        "date": "2028-11-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "396644.74",
          "scenario": "394244.74",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2028-12",
        "date": "2028-12-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "399040.44",
          "scenario": "396640.44",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-01",
        "date": "2029-01-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "401444.71",
          "scenario": "399044.71",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-02",
        "date": "2029-02-28",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "403857.57",
          "scenario": "401457.57",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-03",
        "date": "2029-03-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "406279.05",
          "scenario": "403879.05",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-04",
        "date": "2029-04-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "408709.20",
          "scenario": "406309.20",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-05",
        "date": "2029-05-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "411148.05",
          "scenario": "408748.05",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-06",
        "date": "2029-06-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "413595.36",
          "scenario": "411195.36",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-07",
        "date": "2029-07-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "416050.87",
          "scenario": "413650.87",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-08",
        "date": "2029-08-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "418514.60",
          "scenario": "416114.60",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-09",
        "date": "2029-09-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "420986.59",
          "scenario": "418586.59",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-10",
        "date": "2029-10-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "423466.86",
          "scenario": "421066.86",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-11",
        "date": "2029-11-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "425955.44",
          "scenario": "423555.44",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2029-12",
        "date": "2029-12-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "428452.37",
          "scenario": "426052.37",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-01",
        "date": "2030-01-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "430957.66",
          "scenario": "428557.66",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-02",
        "date": "2030-02-28",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "433471.35",
          "scenario": "431071.35",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-03",
        "date": "2030-03-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "435993.46",
          "scenario": "433593.46",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-04",
        "date": "2030-04-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "438524.01",
          "scenario": "436124.01",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-05",
        "date": "2030-05-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "441063.05",
          "scenario": "438663.05",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-06",
        "date": "2030-06-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "443610.59",
          "scenario": "441210.59",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-07",
        "date": "2030-07-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "446166.67",
          "scenario": "443766.67",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-08",
        "date": "2030-08-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "448731.31",
          "scenario": "446331.31",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-09",
        "date": "2030-09-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "451304.54",
          "scenario": "448904.54",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-10",
        "date": "2030-10-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "453886.40",
          "scenario": "451486.40",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-11",
        "date": "2030-11-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "456476.90",
          "scenario": "454076.90",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2030-12",
        "date": "2030-12-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "459076.09",
          "scenario": "456676.09",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2031-01",
        "date": "2031-01-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "461683.99",
          "scenario": "459283.99",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2031-02",
        "date": "2031-02-28",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "464300.62",
          "scenario": "461900.62",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2031-03",
        "date": "2031-03-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "466926.03",
          "scenario": "464526.03",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2031-04",
        "date": "2031-04-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "469560.23",
          "scenario": "467160.23",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2031-05",
        "date": "2031-05-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "472203.26",
          "scenario": "469803.26",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2031-06",
        "date": "2031-06-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "474855.14",
          "scenario": "472455.14",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2031-07",
        "date": "2031-07-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "477515.91",
          "scenario": "475115.91",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2031-08",
        "date": "2031-08-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "480185.58",
          "scenario": "477785.58",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2031-09",
        "date": "2031-09-30",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "482864.21",
          "scenario": "480464.21",
          "delta": "-2400.00"
        }
      },
      {
        "month": "2031-10",
        "date": "2031-10-31",
        "cash": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "net_worth": {
          "baseline": "485551.81",
          "scenario": "483151.81",
          "delta": "-2400.00"
        }
      }
    ]
  }
};

/**
 * Paying cash against instalments, with each option's timelines.
 */
export const SCENARIO_COMPARISON: ScenarioComparison = {
  "as_of": "2026-10-11",
  "horizon_years": 5,
  "currency": "EUR",
  "labels": [
    "Pay cash",
    "Instalments"
  ],
  "options": [
    {
      "schema": "salli.scenario/1",
      "label": "Pay cash",
      "as_of": "2026-10-11",
      "horizon_years": 5,
      "currency": "EUR",
      "hash": "sha256:9b094ea3ce715a3e72c3351d3125a932f6182e9a6d202e422b1facc0787702e4",
      "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
      "scenario": {
        "schema": "salli.scenario/1",
        "label": "Pay cash",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "one_off",
            "date": "2026-11-02",
            "amount": "-2400.00",
            "account": "chk",
            "tax_role": null,
            "label": "Laptop"
          }
        ],
        "tax": null
      },
      "changes": [
        {
          "index": 0,
          "type": "one_off",
          "label": "Laptop",
          "debt_id": null,
          "payment": null,
          "first_payment": null,
          "monthly": null,
          "for_good": null,
          "stopped": [],
          "holding": null
        }
      ],
      "cash": {
        "start": "2026-10-11",
        "end": "2027-10-31",
        "lowest": {
          "baseline": "13998.91",
          "scenario": "11598.91",
          "delta": "-2400.00"
        },
        "lowest_date": {
          "baseline": "2027-02-24",
          "scenario": "2027-02-24",
          "delta_days": 0
        },
        "at_end": {
          "baseline": "15801.47",
          "scenario": "13401.47",
          "delta": "-2400.00"
        },
        "safe_to_spend": {
          "baseline": "15316.35",
          "scenario": "15316.35",
          "delta": "0.00"
        },
        "safe_until": "2026-10-25",
        "accounts": [
          {
            "account_id": "chk",
            "name": "Checking",
            "currency": "EUR",
            "lowest": {
              "baseline": "6063.46",
              "scenario": "4883.77",
              "delta": "-1179.69"
            },
            "lowest_date": {
              "baseline": "2026-10-15",
              "scenario": "2026-11-15",
              "delta_days": 31
            },
            "below_zero": {
              "baseline": false,
              "scenario": false
            }
          },
          {
            "account_id": "sav",
            "name": "Savings",
            "currency": "EUR",
            "lowest": {
              "baseline": "7800.00",
              "scenario": "7800.00",
              "delta": "0.00"
            },
            "lowest_date": {
              "baseline": "2026-10-11",
              "scenario": "2026-10-11",
              "delta_days": 0
            },
            "below_zero": {
              "baseline": false,
              "scenario": false
            }
          },
          {
            "account_id": "usd",
            "name": "Dollar account",
            "currency": "USD",
            "lowest": {
              "baseline": "2500.00",
              "scenario": "2500.00",
              "delta": "0.00"
            },
            "lowest_date": {
              "baseline": "2026-10-11",
              "scenario": "2026-10-11",
              "delta_days": 0
            },
            "below_zero": {
              "baseline": false,
              "scenario": false
            }
          }
        ],
        "below_zero": {
          "baseline": [],
          "scenario": []
        }
      },
      "monthly": [
        {
          "years": 1,
          "month": "2027-10",
          "date": "2027-10-31",
          "net_worth": {
            "baseline": "366266.13",
            "scenario": "363866.13",
            "delta": "-2400.00"
          },
          "cash": {
            "baseline": "15801.47",
            "scenario": "13401.47",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "63546.81",
            "scenario": "63546.81",
            "delta": "0.00"
          },
          "debts": {
            "baseline": "13082.15",
            "scenario": "13082.15",
            "delta": "0.00"
          },
          "other_assets": {
            "baseline": "300000.00",
            "scenario": "300000.00",
            "delta": "0.00"
          },
          "other_assets_value": {
            "baseline": "300000.00",
            "scenario": "300000.00",
            "delta": "0.00"
          }
        },
        {
          "years": 5,
          "month": "2031-10",
          "date": "2031-10-31",
          "net_worth": {
            "baseline": "485551.81",
            "scenario": "483151.81",
            "delta": "-2400.00"
          },
          "cash": {
            "baseline": "15801.47",
            "scenario": "13401.47",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "171707.25",
            "scenario": "171707.25",
            "delta": "0.00"
          },
          "debts": {
            "baseline": "1956.91",
            "scenario": "1956.91",
            "delta": "0.00"
          },
          "other_assets": {
            "baseline": "300000.00",
            "scenario": "300000.00",
            "delta": "0.00"
          },
          "other_assets_value": {
            "baseline": "300000.00",
            "scenario": "300000.00",
            "delta": "0.00"
          }
        }
      ],
      "debts": {
        "items": [
          {
            "debt_id": "debt-car",
            "name": "Car loan",
            "source": "account",
            "paid_off": {
              "baseline": "2029-05",
              "scenario": "2029-05",
              "delta_months": 0
            },
            "total_interest": {
              "baseline": "786.13",
              "scenario": "786.13",
              "delta": "0.00"
            }
          },
          {
            "debt_id": "debt-student",
            "name": "Student loan",
            "source": "declared",
            "paid_off": {
              "baseline": "2033-03",
              "scenario": "2033-03",
              "delta_months": 0
            },
            "total_interest": {
              "baseline": "1223.12",
              "scenario": "1223.12",
              "delta": "0.00"
            }
          }
        ],
        "total_interest": {
          "baseline": "2009.25",
          "scenario": "2009.25",
          "delta": "0.00"
        },
        "debt_free": {
          "baseline": "2033-03",
          "scenario": "2033-03",
          "delta_months": 0
        }
      },
      "resilience": {
        "basis": "essential",
        "monthly_spending": "1898.32",
        "lowest": {
          "baseline": "7.37",
          "scenario": "6.11",
          "delta": "-1.26"
        },
        "at_end": {
          "baseline": "8.32",
          "scenario": "7.06",
          "delta": "-1.26"
        }
      },
      "fi": {
        "fi_number": {
          "baseline": "714042.04",
          "scenario": "714042.04",
          "delta": "0.00"
        },
        "monthly_spending": {
          "baseline": "2037.09",
          "scenario": "2037.09",
          "delta": "0.00"
        },
        "fi_month": {
          "baseline": "2044-08",
          "scenario": "2044-09",
          "delta_months": 1
        },
        "months_gained": -1
      },
      "break_evens": [],
      "tax": {
        "status": "none",
        "reason": null,
        "years": [],
        "this_year": null,
        "change_this_year": "0.00",
        "total_change": "0.00",
        "carried_forward": false
      },
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
        "nominal_returns": null,
        "cma": null
      },
      "placeholders": [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "drawdown_horizon",
        "inflation"
      ],
      "versions": {
        "schema": "salli.scenario/1",
        "engine": "4",
        "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
        "rule_sets": []
      },
      "data_as_of": "2026-10-09",
      "is_stale": false,
      "notes": [],
      "timeline": {
        "daily": [
          {
            "date": "2026-10-11",
            "baseline": "15803.09",
            "scenario": "15803.09"
          },
          {
            "date": "2026-10-12",
            "baseline": "15804.72",
            "scenario": "15804.72"
          },
          {
            "date": "2026-10-13",
            "baseline": "15806.34",
            "scenario": "15806.34"
          },
          {
            "date": "2026-10-14",
            "baseline": "15807.97",
            "scenario": "15807.97"
          },
          {
            "date": "2026-10-15",
            "baseline": "15809.59",
            "scenario": "15809.59"
          },
          {
            "date": "2026-10-16",
            "baseline": "15811.22",
            "scenario": "15811.22"
          },
          {
            "date": "2026-10-17",
            "baseline": "15812.84",
            "scenario": "15812.84"
          },
          {
            "date": "2026-10-18",
            "baseline": "15740.01",
            "scenario": "15740.01"
          },
          {
            "date": "2026-10-19",
            "baseline": "15741.64",
            "scenario": "15741.64"
          },
          {
            "date": "2026-10-20",
            "baseline": "15743.26",
            "scenario": "15743.26"
          },
          {
            "date": "2026-10-21",
            "baseline": "15744.89",
            "scenario": "15744.89"
          },
          {
            "date": "2026-10-22",
            "baseline": "15746.51",
            "scenario": "15746.51"
          },
          {
            "date": "2026-10-23",
            "baseline": "15748.14",
            "scenario": "15748.14"
          },
          {
            "date": "2026-10-24",
            "baseline": "15749.76",
            "scenario": "15749.76"
          },
          {
            "date": "2026-10-25",
            "baseline": "19751.38",
            "scenario": "19751.38"
          },
          {
            "date": "2026-10-26",
            "baseline": "19253.01",
            "scenario": "19253.01"
          },
          {
            "date": "2026-10-27",
            "baseline": "19254.63",
            "scenario": "19254.63"
          },
          {
            "date": "2026-10-28",
            "baseline": "19256.26",
            "scenario": "19256.26"
          },
          {
            "date": "2026-10-29",
            "baseline": "19257.88",
            "scenario": "19257.88"
          },
          {
            "date": "2026-10-30",
            "baseline": "19259.51",
            "scenario": "19259.51"
          },
          {
            "date": "2026-10-31",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2026-11-01",
            "baseline": "14293.10",
            "scenario": "14293.10"
          },
          {
            "date": "2026-11-02",
            "baseline": "14284.74",
            "scenario": "11884.74"
          },
          {
            "date": "2026-11-03",
            "baseline": "14276.37",
            "scenario": "11876.37"
          },
          {
            "date": "2026-11-04",
            "baseline": "14268.01",
            "scenario": "11868.01"
          },
          {
            "date": "2026-11-05",
            "baseline": "14259.64",
            "scenario": "11859.64"
          },
          {
            "date": "2026-11-06",
            "baseline": "14251.28",
            "scenario": "11851.28"
          },
          {
            "date": "2026-11-07",
            "baseline": "14242.91",
            "scenario": "11842.91"
          },
          {
            "date": "2026-11-08",
            "baseline": "14221.55",
            "scenario": "11821.55"
          },
          {
            "date": "2026-11-09",
            "baseline": "14213.19",
            "scenario": "11813.19"
          },
          {
            "date": "2026-11-10",
            "baseline": "14204.82",
            "scenario": "11804.82"
          },
          {
            "date": "2026-11-11",
            "baseline": "14196.46",
            "scenario": "11796.46"
          },
          {
            "date": "2026-11-12",
            "baseline": "14188.09",
            "scenario": "11788.09"
          },
          {
            "date": "2026-11-13",
            "baseline": "14179.73",
            "scenario": "11779.73"
          },
          {
            "date": "2026-11-14",
            "baseline": "14171.36",
            "scenario": "11771.36"
          },
          {
            "date": "2026-11-15",
            "baseline": "14162.99",
            "scenario": "11762.99"
          },
          {
            "date": "2026-11-16",
            "baseline": "14154.63",
            "scenario": "11754.63"
          },
          {
            "date": "2026-11-17",
            "baseline": "14146.26",
            "scenario": "11746.26"
          },
          {
            "date": "2026-11-18",
            "baseline": "14063.45",
            "scenario": "11663.45"
          },
          {
            "date": "2026-11-19",
            "baseline": "14055.08",
            "scenario": "11655.08"
          },
          {
            "date": "2026-11-20",
            "baseline": "14046.72",
            "scenario": "11646.72"
          },
          {
            "date": "2026-11-21",
            "baseline": "14038.35",
            "scenario": "11638.35"
          },
          {
            "date": "2026-11-22",
            "baseline": "14029.99",
            "scenario": "11629.99"
          },
          {
            "date": "2026-11-23",
            "baseline": "14021.62",
            "scenario": "11621.62"
          },
          {
            "date": "2026-11-24",
            "baseline": "14013.25",
            "scenario": "11613.25"
          },
          {
            "date": "2026-11-25",
            "baseline": "18004.89",
            "scenario": "15604.89"
          },
          {
            "date": "2026-11-26",
            "baseline": "17496.52",
            "scenario": "15096.52"
          },
          {
            "date": "2026-11-27",
            "baseline": "17488.16",
            "scenario": "15088.16"
          },
          {
            "date": "2026-11-28",
            "baseline": "17479.79",
            "scenario": "15079.79"
          },
          {
            "date": "2026-11-29",
            "baseline": "17471.43",
            "scenario": "15071.43"
          },
          {
            "date": "2026-11-30",
            "baseline": "15801.47",
            "scenario": "13401.47"
          },
          {
            "date": "2026-12-01",
            "baseline": "14293.37",
            "scenario": "11893.37"
          },
          {
            "date": "2026-12-02",
            "baseline": "14285.28",
            "scenario": "11885.28"
          },
          {
            "date": "2026-12-03",
            "baseline": "14277.18",
            "scenario": "11877.18"
          },
          {
            "date": "2026-12-04",
            "baseline": "14269.09",
            "scenario": "11869.09"
          },
          {
            "date": "2026-12-05",
            "baseline": "14260.99",
            "scenario": "11860.99"
          },
          {
            "date": "2026-12-06",
            "baseline": "14252.90",
            "scenario": "11852.90"
          },
          {
            "date": "2026-12-07",
            "baseline": "14244.80",
            "scenario": "11844.80"
          },
          {
            "date": "2026-12-08",
            "baseline": "14223.71",
            "scenario": "11823.71"
          },
          {
            "date": "2026-12-09",
            "baseline": "14215.62",
            "scenario": "11815.62"
          },
          {
            "date": "2026-12-10",
            "baseline": "14207.52",
            "scenario": "11807.52"
          },
          {
            "date": "2026-12-11",
            "baseline": "14199.43",
            "scenario": "11799.43"
          },
          {
            "date": "2026-12-12",
            "baseline": "14191.33",
            "scenario": "11791.33"
          },
          {
            "date": "2026-12-13",
            "baseline": "14183.23",
            "scenario": "11783.23"
          },
          {
            "date": "2026-12-14",
            "baseline": "14175.14",
            "scenario": "11775.14"
          },
          {
            "date": "2026-12-15",
            "baseline": "14167.04",
            "scenario": "11767.04"
          },
          {
            "date": "2026-12-16",
            "baseline": "14158.95",
            "scenario": "11758.95"
          },
          {
            "date": "2026-12-17",
            "baseline": "14150.85",
            "scenario": "11750.85"
          },
          {
            "date": "2026-12-18",
            "baseline": "14068.31",
            "scenario": "11668.31"
          },
          {
            "date": "2026-12-19",
            "baseline": "14060.21",
            "scenario": "11660.21"
          },
          {
            "date": "2026-12-20",
            "baseline": "14052.11",
            "scenario": "11652.11"
          },
          {
            "date": "2026-12-21",
            "baseline": "14044.02",
            "scenario": "11644.02"
          },
          {
            "date": "2026-12-22",
            "baseline": "14035.92",
            "scenario": "11635.92"
          },
          {
            "date": "2026-12-23",
            "baseline": "14027.83",
            "scenario": "11627.83"
          },
          {
            "date": "2026-12-24",
            "baseline": "14019.73",
            "scenario": "11619.73"
          },
          {
            "date": "2026-12-25",
            "baseline": "18011.63",
            "scenario": "15611.63"
          },
          {
            "date": "2026-12-26",
            "baseline": "17503.54",
            "scenario": "15103.54"
          },
          {
            "date": "2026-12-27",
            "baseline": "17495.44",
            "scenario": "15095.44"
          },
          {
            "date": "2026-12-28",
            "baseline": "17487.35",
            "scenario": "15087.35"
          },
          {
            "date": "2026-12-29",
            "baseline": "17479.25",
            "scenario": "15079.25"
          },
          {
            "date": "2026-12-30",
            "baseline": "17471.16",
            "scenario": "15071.16"
          },
          {
            "date": "2026-12-31",
            "baseline": "15801.47",
            "scenario": "13401.47"
          },
          {
            "date": "2027-01-01",
            "baseline": "14293.37",
            "scenario": "11893.37"
          },
          {
            "date": "2027-01-02",
            "baseline": "14285.28",
            "scenario": "11885.28"
          },
          {
            "date": "2027-01-03",
            "baseline": "14277.18",
            "scenario": "11877.18"
          },
          {
            "date": "2027-01-04",
            "baseline": "14269.09",
            "scenario": "11869.09"
          },
          {
            "date": "2027-01-05",
            "baseline": "14260.99",
            "scenario": "11860.99"
          },
          {
            "date": "2027-01-06",
            "baseline": "14252.90",
            "scenario": "11852.90"
          },
          {
            "date": "2027-01-07",
            "baseline": "14244.80",
            "scenario": "11844.80"
          },
          {
            "date": "2027-01-08",
            "baseline": "14223.71",
            "scenario": "11823.71"
          },
          {
            "date": "2027-01-09",
            "baseline": "14215.62",
            "scenario": "11815.62"
          },
          {
            "date": "2027-01-10",
            "baseline": "14207.52",
            "scenario": "11807.52"
          },
          {
            "date": "2027-01-11",
            "baseline": "14199.43",
            "scenario": "11799.43"
          },
          {
            "date": "2027-01-12",
            "baseline": "14191.33",
            "scenario": "11791.33"
          },
          {
            "date": "2027-01-13",
            "baseline": "14183.23",
            "scenario": "11783.23"
          },
          {
            "date": "2027-01-14",
            "baseline": "14175.14",
            "scenario": "11775.14"
          },
          {
            "date": "2027-01-15",
            "baseline": "14167.04",
            "scenario": "11767.04"
          },
          {
            "date": "2027-01-16",
            "baseline": "14158.95",
            "scenario": "11758.95"
          },
          {
            "date": "2027-01-17",
            "baseline": "14150.85",
            "scenario": "11750.85"
          },
          {
            "date": "2027-01-18",
            "baseline": "14068.31",
            "scenario": "11668.31"
          },
          {
            "date": "2027-01-19",
            "baseline": "14060.21",
            "scenario": "11660.21"
          },
          {
            "date": "2027-01-20",
            "baseline": "14052.11",
            "scenario": "11652.11"
          },
          {
            "date": "2027-01-21",
            "baseline": "14044.02",
            "scenario": "11644.02"
          },
          {
            "date": "2027-01-22",
            "baseline": "14035.92",
            "scenario": "11635.92"
          },
          {
            "date": "2027-01-23",
            "baseline": "14027.83",
            "scenario": "11627.83"
          },
          {
            "date": "2027-01-24",
            "baseline": "14019.73",
            "scenario": "11619.73"
          },
          {
            "date": "2027-01-25",
            "baseline": "18011.63",
            "scenario": "15611.63"
          },
          {
            "date": "2027-01-26",
            "baseline": "17503.54",
            "scenario": "15103.54"
          },
          {
            "date": "2027-01-27",
            "baseline": "17495.44",
            "scenario": "15095.44"
          },
          {
            "date": "2027-01-28",
            "baseline": "17487.35",
            "scenario": "15087.35"
          },
          {
            "date": "2027-01-29",
            "baseline": "17479.25",
            "scenario": "15079.25"
          },
          {
            "date": "2027-01-30",
            "baseline": "17471.16",
            "scenario": "15071.16"
          },
          {
            "date": "2027-01-31",
            "baseline": "15801.47",
            "scenario": "13401.47"
          },
          {
            "date": "2027-02-01",
            "baseline": "14292.51",
            "scenario": "11892.51"
          },
          {
            "date": "2027-02-02",
            "baseline": "14283.54",
            "scenario": "11883.54"
          },
          {
            "date": "2027-02-03",
            "baseline": "14274.58",
            "scenario": "11874.58"
          },
          {
            "date": "2027-02-04",
            "baseline": "14265.62",
            "scenario": "11865.62"
          },
          {
            "date": "2027-02-05",
            "baseline": "14256.65",
            "scenario": "11856.65"
          },
          {
            "date": "2027-02-06",
            "baseline": "14247.69",
            "scenario": "11847.69"
          },
          {
            "date": "2027-02-07",
            "baseline": "14238.73",
            "scenario": "11838.73"
          },
          {
            "date": "2027-02-08",
            "baseline": "14216.77",
            "scenario": "11816.77"
          },
          {
            "date": "2027-02-09",
            "baseline": "14207.81",
            "scenario": "11807.81"
          },
          {
            "date": "2027-02-10",
            "baseline": "14198.85",
            "scenario": "11798.85"
          },
          {
            "date": "2027-02-11",
            "baseline": "14189.88",
            "scenario": "11789.88"
          },
          {
            "date": "2027-02-12",
            "baseline": "14180.92",
            "scenario": "11780.92"
          },
          {
            "date": "2027-02-13",
            "baseline": "14171.96",
            "scenario": "11771.96"
          },
          {
            "date": "2027-02-14",
            "baseline": "14162.99",
            "scenario": "11762.99"
          },
          {
            "date": "2027-02-15",
            "baseline": "14154.03",
            "scenario": "11754.03"
          },
          {
            "date": "2027-02-16",
            "baseline": "14145.07",
            "scenario": "11745.07"
          },
          {
            "date": "2027-02-17",
            "baseline": "14136.11",
            "scenario": "11736.11"
          },
          {
            "date": "2027-02-18",
            "baseline": "14052.69",
            "scenario": "11652.69"
          },
          {
            "date": "2027-02-19",
            "baseline": "14043.73",
            "scenario": "11643.73"
          },
          {
            "date": "2027-02-20",
            "baseline": "14034.77",
            "scenario": "11634.77"
          },
          {
            "date": "2027-02-21",
            "baseline": "14025.80",
            "scenario": "11625.80"
          },
          {
            "date": "2027-02-22",
            "baseline": "14016.84",
            "scenario": "11616.84"
          },
          {
            "date": "2027-02-23",
            "baseline": "14007.88",
            "scenario": "11607.88"
          },
          {
            "date": "2027-02-24",
            "baseline": "13998.91",
            "scenario": "11598.91"
          },
          {
            "date": "2027-02-25",
            "baseline": "17989.95",
            "scenario": "15589.95"
          },
          {
            "date": "2027-02-26",
            "baseline": "17480.99",
            "scenario": "15080.99"
          },
          {
            "date": "2027-02-27",
            "baseline": "17472.02",
            "scenario": "15072.02"
          },
          {
            "date": "2027-02-28",
            "baseline": "15801.47",
            "scenario": "13401.47"
          },
          {
            "date": "2027-03-01",
            "baseline": "14293.37",
            "scenario": "11893.37"
          },
          {
            "date": "2027-03-02",
            "baseline": "14285.28",
            "scenario": "11885.28"
          },
          {
            "date": "2027-03-03",
            "baseline": "14277.18",
            "scenario": "11877.18"
          },
          {
            "date": "2027-03-04",
            "baseline": "14269.09",
            "scenario": "11869.09"
          },
          {
            "date": "2027-03-05",
            "baseline": "14260.99",
            "scenario": "11860.99"
          },
          {
            "date": "2027-03-06",
            "baseline": "14252.90",
            "scenario": "11852.90"
          },
          {
            "date": "2027-03-07",
            "baseline": "14244.80",
            "scenario": "11844.80"
          },
          {
            "date": "2027-03-08",
            "baseline": "14223.71",
            "scenario": "11823.71"
          },
          {
            "date": "2027-03-09",
            "baseline": "14215.62",
            "scenario": "11815.62"
          },
          {
            "date": "2027-03-10",
            "baseline": "14207.52",
            "scenario": "11807.52"
          },
          {
            "date": "2027-03-11",
            "baseline": "14199.43",
            "scenario": "11799.43"
          },
          {
            "date": "2027-03-12",
            "baseline": "14191.33",
            "scenario": "11791.33"
          },
          {
            "date": "2027-03-13",
            "baseline": "14183.23",
            "scenario": "11783.23"
          },
          {
            "date": "2027-03-14",
            "baseline": "14175.14",
            "scenario": "11775.14"
          },
          {
            "date": "2027-03-15",
            "baseline": "14167.04",
            "scenario": "11767.04"
          },
          {
            "date": "2027-03-16",
            "baseline": "14158.95",
            "scenario": "11758.95"
          },
          {
            "date": "2027-03-17",
            "baseline": "14150.85",
            "scenario": "11750.85"
          },
          {
            "date": "2027-03-18",
            "baseline": "14068.31",
            "scenario": "11668.31"
          },
          {
            "date": "2027-03-19",
            "baseline": "14060.21",
            "scenario": "11660.21"
          },
          {
            "date": "2027-03-20",
            "baseline": "14052.11",
            "scenario": "11652.11"
          },
          {
            "date": "2027-03-21",
            "baseline": "14044.02",
            "scenario": "11644.02"
          },
          {
            "date": "2027-03-22",
            "baseline": "14035.92",
            "scenario": "11635.92"
          },
          {
            "date": "2027-03-23",
            "baseline": "14027.83",
            "scenario": "11627.83"
          },
          {
            "date": "2027-03-24",
            "baseline": "14019.73",
            "scenario": "11619.73"
          },
          {
            "date": "2027-03-25",
            "baseline": "18011.63",
            "scenario": "15611.63"
          },
          {
            "date": "2027-03-26",
            "baseline": "17503.54",
            "scenario": "15103.54"
          },
          {
            "date": "2027-03-27",
            "baseline": "17495.44",
            "scenario": "15095.44"
          },
          {
            "date": "2027-03-28",
            "baseline": "17487.35",
            "scenario": "15087.35"
          },
          {
            "date": "2027-03-29",
            "baseline": "17479.25",
            "scenario": "15079.25"
          },
          {
            "date": "2027-03-30",
            "baseline": "17471.16",
            "scenario": "15071.16"
          },
          {
            "date": "2027-03-31",
            "baseline": "15801.47",
            "scenario": "13401.47"
          },
          {
            "date": "2027-04-01",
            "baseline": "14293.10",
            "scenario": "11893.10"
          },
          {
            "date": "2027-04-02",
            "baseline": "14284.74",
            "scenario": "11884.74"
          },
          {
            "date": "2027-04-03",
            "baseline": "14276.37",
            "scenario": "11876.37"
          },
          {
            "date": "2027-04-04",
            "baseline": "14268.01",
            "scenario": "11868.01"
          },
          {
            "date": "2027-04-05",
            "baseline": "14259.64",
            "scenario": "11859.64"
          },
          {
            "date": "2027-04-06",
            "baseline": "14251.28",
            "scenario": "11851.28"
          },
          {
            "date": "2027-04-07",
            "baseline": "14242.91",
            "scenario": "11842.91"
          },
          {
            "date": "2027-04-08",
            "baseline": "14221.55",
            "scenario": "11821.55"
          },
          {
            "date": "2027-04-09",
            "baseline": "14213.19",
            "scenario": "11813.19"
          },
          {
            "date": "2027-04-10",
            "baseline": "14204.82",
            "scenario": "11804.82"
          },
          {
            "date": "2027-04-11",
            "baseline": "14196.46",
            "scenario": "11796.46"
          },
          {
            "date": "2027-04-12",
            "baseline": "14188.09",
            "scenario": "11788.09"
          },
          {
            "date": "2027-04-13",
            "baseline": "14179.73",
            "scenario": "11779.73"
          },
          {
            "date": "2027-04-14",
            "baseline": "14171.36",
            "scenario": "11771.36"
          },
          {
            "date": "2027-04-15",
            "baseline": "14162.99",
            "scenario": "11762.99"
          },
          {
            "date": "2027-04-16",
            "baseline": "14154.63",
            "scenario": "11754.63"
          },
          {
            "date": "2027-04-17",
            "baseline": "14146.26",
            "scenario": "11746.26"
          },
          {
            "date": "2027-04-18",
            "baseline": "14063.45",
            "scenario": "11663.45"
          },
          {
            "date": "2027-04-19",
            "baseline": "14055.08",
            "scenario": "11655.08"
          },
          {
            "date": "2027-04-20",
            "baseline": "14046.72",
            "scenario": "11646.72"
          },
          {
            "date": "2027-04-21",
            "baseline": "14038.35",
            "scenario": "11638.35"
          },
          {
            "date": "2027-04-22",
            "baseline": "14029.99",
            "scenario": "11629.99"
          },
          {
            "date": "2027-04-23",
            "baseline": "14021.62",
            "scenario": "11621.62"
          },
          {
            "date": "2027-04-24",
            "baseline": "14013.25",
            "scenario": "11613.25"
          },
          {
            "date": "2027-04-25",
            "baseline": "18004.89",
            "scenario": "15604.89"
          },
          {
            "date": "2027-04-26",
            "baseline": "17496.52",
            "scenario": "15096.52"
          },
          {
            "date": "2027-04-27",
            "baseline": "17488.16",
            "scenario": "15088.16"
          },
          {
            "date": "2027-04-28",
            "baseline": "17479.79",
            "scenario": "15079.79"
          },
          {
            "date": "2027-04-29",
            "baseline": "17471.43",
            "scenario": "15071.43"
          },
          {
            "date": "2027-04-30",
            "baseline": "15801.47",
            "scenario": "13401.47"
          },
          {
            "date": "2027-05-01",
            "baseline": "14293.37",
            "scenario": "11893.37"
          },
          {
            "date": "2027-05-02",
            "baseline": "14285.28",
            "scenario": "11885.28"
          },
          {
            "date": "2027-05-03",
            "baseline": "14277.18",
            "scenario": "11877.18"
          },
          {
            "date": "2027-05-04",
            "baseline": "14269.09",
            "scenario": "11869.09"
          },
          {
            "date": "2027-05-05",
            "baseline": "14260.99",
            "scenario": "11860.99"
          },
          {
            "date": "2027-05-06",
            "baseline": "14252.90",
            "scenario": "11852.90"
          },
          {
            "date": "2027-05-07",
            "baseline": "14244.80",
            "scenario": "11844.80"
          },
          {
            "date": "2027-05-08",
            "baseline": "14223.71",
            "scenario": "11823.71"
          },
          {
            "date": "2027-05-09",
            "baseline": "14215.62",
            "scenario": "11815.62"
          },
          {
            "date": "2027-05-10",
            "baseline": "14207.52",
            "scenario": "11807.52"
          },
          {
            "date": "2027-05-11",
            "baseline": "14199.43",
            "scenario": "11799.43"
          },
          {
            "date": "2027-05-12",
            "baseline": "14191.33",
            "scenario": "11791.33"
          },
          {
            "date": "2027-05-13",
            "baseline": "14183.23",
            "scenario": "11783.23"
          },
          {
            "date": "2027-05-14",
            "baseline": "14175.14",
            "scenario": "11775.14"
          },
          {
            "date": "2027-05-15",
            "baseline": "14167.04",
            "scenario": "11767.04"
          },
          {
            "date": "2027-05-16",
            "baseline": "14158.95",
            "scenario": "11758.95"
          },
          {
            "date": "2027-05-17",
            "baseline": "14150.85",
            "scenario": "11750.85"
          },
          {
            "date": "2027-05-18",
            "baseline": "14068.31",
            "scenario": "11668.31"
          },
          {
            "date": "2027-05-19",
            "baseline": "14060.21",
            "scenario": "11660.21"
          },
          {
            "date": "2027-05-20",
            "baseline": "14052.11",
            "scenario": "11652.11"
          },
          {
            "date": "2027-05-21",
            "baseline": "14044.02",
            "scenario": "11644.02"
          },
          {
            "date": "2027-05-22",
            "baseline": "14035.92",
            "scenario": "11635.92"
          },
          {
            "date": "2027-05-23",
            "baseline": "14027.83",
            "scenario": "11627.83"
          },
          {
            "date": "2027-05-24",
            "baseline": "14019.73",
            "scenario": "11619.73"
          },
          {
            "date": "2027-05-25",
            "baseline": "18011.63",
            "scenario": "15611.63"
          },
          {
            "date": "2027-05-26",
            "baseline": "17503.54",
            "scenario": "15103.54"
          },
          {
            "date": "2027-05-27",
            "baseline": "17495.44",
            "scenario": "15095.44"
          },
          {
            "date": "2027-05-28",
            "baseline": "17487.35",
            "scenario": "15087.35"
          },
          {
            "date": "2027-05-29",
            "baseline": "17479.25",
            "scenario": "15079.25"
          },
          {
            "date": "2027-05-30",
            "baseline": "17471.16",
            "scenario": "15071.16"
          },
          {
            "date": "2027-05-31",
            "baseline": "15801.47",
            "scenario": "13401.47"
          },
          {
            "date": "2027-06-01",
            "baseline": "14293.10",
            "scenario": "11893.10"
          },
          {
            "date": "2027-06-02",
            "baseline": "14284.74",
            "scenario": "11884.74"
          },
          {
            "date": "2027-06-03",
            "baseline": "14276.37",
            "scenario": "11876.37"
          },
          {
            "date": "2027-06-04",
            "baseline": "14268.01",
            "scenario": "11868.01"
          },
          {
            "date": "2027-06-05",
            "baseline": "14259.64",
            "scenario": "11859.64"
          },
          {
            "date": "2027-06-06",
            "baseline": "14251.28",
            "scenario": "11851.28"
          },
          {
            "date": "2027-06-07",
            "baseline": "14242.91",
            "scenario": "11842.91"
          },
          {
            "date": "2027-06-08",
            "baseline": "14221.55",
            "scenario": "11821.55"
          },
          {
            "date": "2027-06-09",
            "baseline": "14213.19",
            "scenario": "11813.19"
          },
          {
            "date": "2027-06-10",
            "baseline": "14204.82",
            "scenario": "11804.82"
          },
          {
            "date": "2027-06-11",
            "baseline": "14196.46",
            "scenario": "11796.46"
          },
          {
            "date": "2027-06-12",
            "baseline": "14188.09",
            "scenario": "11788.09"
          },
          {
            "date": "2027-06-13",
            "baseline": "14179.73",
            "scenario": "11779.73"
          },
          {
            "date": "2027-06-14",
            "baseline": "14171.36",
            "scenario": "11771.36"
          },
          {
            "date": "2027-06-15",
            "baseline": "14162.99",
            "scenario": "11762.99"
          },
          {
            "date": "2027-06-16",
            "baseline": "14154.63",
            "scenario": "11754.63"
          },
          {
            "date": "2027-06-17",
            "baseline": "14146.26",
            "scenario": "11746.26"
          },
          {
            "date": "2027-06-18",
            "baseline": "14063.45",
            "scenario": "11663.45"
          },
          {
            "date": "2027-06-19",
            "baseline": "14055.08",
            "scenario": "11655.08"
          },
          {
            "date": "2027-06-20",
            "baseline": "14046.72",
            "scenario": "11646.72"
          },
          {
            "date": "2027-06-21",
            "baseline": "14038.35",
            "scenario": "11638.35"
          },
          {
            "date": "2027-06-22",
            "baseline": "14029.99",
            "scenario": "11629.99"
          },
          {
            "date": "2027-06-23",
            "baseline": "14021.62",
            "scenario": "11621.62"
          },
          {
            "date": "2027-06-24",
            "baseline": "14013.25",
            "scenario": "11613.25"
          },
          {
            "date": "2027-06-25",
            "baseline": "18004.89",
            "scenario": "15604.89"
          },
          {
            "date": "2027-06-26",
            "baseline": "17496.52",
            "scenario": "15096.52"
          },
          {
            "date": "2027-06-27",
            "baseline": "17488.16",
            "scenario": "15088.16"
          },
          {
            "date": "2027-06-28",
            "baseline": "17479.79",
            "scenario": "15079.79"
          },
          {
            "date": "2027-06-29",
            "baseline": "17471.43",
            "scenario": "15071.43"
          },
          {
            "date": "2027-06-30",
            "baseline": "15801.47",
            "scenario": "13401.47"
          },
          {
            "date": "2027-07-01",
            "baseline": "14293.37",
            "scenario": "11893.37"
          },
          {
            "date": "2027-07-02",
            "baseline": "14285.28",
            "scenario": "11885.28"
          },
          {
            "date": "2027-07-03",
            "baseline": "14277.18",
            "scenario": "11877.18"
          },
          {
            "date": "2027-07-04",
            "baseline": "14269.09",
            "scenario": "11869.09"
          },
          {
            "date": "2027-07-05",
            "baseline": "14260.99",
            "scenario": "11860.99"
          },
          {
            "date": "2027-07-06",
            "baseline": "14252.90",
            "scenario": "11852.90"
          },
          {
            "date": "2027-07-07",
            "baseline": "14244.80",
            "scenario": "11844.80"
          },
          {
            "date": "2027-07-08",
            "baseline": "14223.71",
            "scenario": "11823.71"
          },
          {
            "date": "2027-07-09",
            "baseline": "14215.62",
            "scenario": "11815.62"
          },
          {
            "date": "2027-07-10",
            "baseline": "14207.52",
            "scenario": "11807.52"
          },
          {
            "date": "2027-07-11",
            "baseline": "14199.43",
            "scenario": "11799.43"
          },
          {
            "date": "2027-07-12",
            "baseline": "14191.33",
            "scenario": "11791.33"
          },
          {
            "date": "2027-07-13",
            "baseline": "14183.23",
            "scenario": "11783.23"
          },
          {
            "date": "2027-07-14",
            "baseline": "14175.14",
            "scenario": "11775.14"
          },
          {
            "date": "2027-07-15",
            "baseline": "14167.04",
            "scenario": "11767.04"
          },
          {
            "date": "2027-07-16",
            "baseline": "14158.95",
            "scenario": "11758.95"
          },
          {
            "date": "2027-07-17",
            "baseline": "14150.85",
            "scenario": "11750.85"
          },
          {
            "date": "2027-07-18",
            "baseline": "14068.31",
            "scenario": "11668.31"
          },
          {
            "date": "2027-07-19",
            "baseline": "14060.21",
            "scenario": "11660.21"
          },
          {
            "date": "2027-07-20",
            "baseline": "14052.11",
            "scenario": "11652.11"
          },
          {
            "date": "2027-07-21",
            "baseline": "14044.02",
            "scenario": "11644.02"
          },
          {
            "date": "2027-07-22",
            "baseline": "14035.92",
            "scenario": "11635.92"
          },
          {
            "date": "2027-07-23",
            "baseline": "14027.83",
            "scenario": "11627.83"
          },
          {
            "date": "2027-07-24",
            "baseline": "14019.73",
            "scenario": "11619.73"
          },
          {
            "date": "2027-07-25",
            "baseline": "18011.63",
            "scenario": "15611.63"
          },
          {
            "date": "2027-07-26",
            "baseline": "17503.54",
            "scenario": "15103.54"
          },
          {
            "date": "2027-07-27",
            "baseline": "17495.44",
            "scenario": "15095.44"
          },
          {
            "date": "2027-07-28",
            "baseline": "17487.35",
            "scenario": "15087.35"
          },
          {
            "date": "2027-07-29",
            "baseline": "17479.25",
            "scenario": "15079.25"
          },
          {
            "date": "2027-07-30",
            "baseline": "17471.16",
            "scenario": "15071.16"
          },
          {
            "date": "2027-07-31",
            "baseline": "15801.47",
            "scenario": "13401.47"
          },
          {
            "date": "2027-08-01",
            "baseline": "14293.37",
            "scenario": "11893.37"
          },
          {
            "date": "2027-08-02",
            "baseline": "14285.28",
            "scenario": "11885.28"
          },
          {
            "date": "2027-08-03",
            "baseline": "14277.18",
            "scenario": "11877.18"
          },
          {
            "date": "2027-08-04",
            "baseline": "14269.09",
            "scenario": "11869.09"
          },
          {
            "date": "2027-08-05",
            "baseline": "14260.99",
            "scenario": "11860.99"
          },
          {
            "date": "2027-08-06",
            "baseline": "14252.90",
            "scenario": "11852.90"
          },
          {
            "date": "2027-08-07",
            "baseline": "14244.80",
            "scenario": "11844.80"
          },
          {
            "date": "2027-08-08",
            "baseline": "14223.71",
            "scenario": "11823.71"
          },
          {
            "date": "2027-08-09",
            "baseline": "14215.62",
            "scenario": "11815.62"
          },
          {
            "date": "2027-08-10",
            "baseline": "14207.52",
            "scenario": "11807.52"
          },
          {
            "date": "2027-08-11",
            "baseline": "14199.43",
            "scenario": "11799.43"
          },
          {
            "date": "2027-08-12",
            "baseline": "14191.33",
            "scenario": "11791.33"
          },
          {
            "date": "2027-08-13",
            "baseline": "14183.23",
            "scenario": "11783.23"
          },
          {
            "date": "2027-08-14",
            "baseline": "14175.14",
            "scenario": "11775.14"
          },
          {
            "date": "2027-08-15",
            "baseline": "14167.04",
            "scenario": "11767.04"
          },
          {
            "date": "2027-08-16",
            "baseline": "14158.95",
            "scenario": "11758.95"
          },
          {
            "date": "2027-08-17",
            "baseline": "14150.85",
            "scenario": "11750.85"
          },
          {
            "date": "2027-08-18",
            "baseline": "14068.31",
            "scenario": "11668.31"
          },
          {
            "date": "2027-08-19",
            "baseline": "14060.21",
            "scenario": "11660.21"
          },
          {
            "date": "2027-08-20",
            "baseline": "14052.11",
            "scenario": "11652.11"
          },
          {
            "date": "2027-08-21",
            "baseline": "14044.02",
            "scenario": "11644.02"
          },
          {
            "date": "2027-08-22",
            "baseline": "14035.92",
            "scenario": "11635.92"
          },
          {
            "date": "2027-08-23",
            "baseline": "14027.83",
            "scenario": "11627.83"
          },
          {
            "date": "2027-08-24",
            "baseline": "14019.73",
            "scenario": "11619.73"
          },
          {
            "date": "2027-08-25",
            "baseline": "18011.63",
            "scenario": "15611.63"
          },
          {
            "date": "2027-08-26",
            "baseline": "17503.54",
            "scenario": "15103.54"
          },
          {
            "date": "2027-08-27",
            "baseline": "17495.44",
            "scenario": "15095.44"
          },
          {
            "date": "2027-08-28",
            "baseline": "17487.35",
            "scenario": "15087.35"
          },
          {
            "date": "2027-08-29",
            "baseline": "17479.25",
            "scenario": "15079.25"
          },
          {
            "date": "2027-08-30",
            "baseline": "17471.16",
            "scenario": "15071.16"
          },
          {
            "date": "2027-08-31",
            "baseline": "15801.47",
            "scenario": "13401.47"
          },
          {
            "date": "2027-09-01",
            "baseline": "14293.10",
            "scenario": "11893.10"
          },
          {
            "date": "2027-09-02",
            "baseline": "14284.74",
            "scenario": "11884.74"
          },
          {
            "date": "2027-09-03",
            "baseline": "14276.37",
            "scenario": "11876.37"
          },
          {
            "date": "2027-09-04",
            "baseline": "14268.01",
            "scenario": "11868.01"
          },
          {
            "date": "2027-09-05",
            "baseline": "14259.64",
            "scenario": "11859.64"
          },
          {
            "date": "2027-09-06",
            "baseline": "14251.28",
            "scenario": "11851.28"
          },
          {
            "date": "2027-09-07",
            "baseline": "14242.91",
            "scenario": "11842.91"
          },
          {
            "date": "2027-09-08",
            "baseline": "14221.55",
            "scenario": "11821.55"
          },
          {
            "date": "2027-09-09",
            "baseline": "14213.19",
            "scenario": "11813.19"
          },
          {
            "date": "2027-09-10",
            "baseline": "14204.82",
            "scenario": "11804.82"
          },
          {
            "date": "2027-09-11",
            "baseline": "14196.46",
            "scenario": "11796.46"
          },
          {
            "date": "2027-09-12",
            "baseline": "14188.09",
            "scenario": "11788.09"
          },
          {
            "date": "2027-09-13",
            "baseline": "14179.73",
            "scenario": "11779.73"
          },
          {
            "date": "2027-09-14",
            "baseline": "14171.36",
            "scenario": "11771.36"
          },
          {
            "date": "2027-09-15",
            "baseline": "14162.99",
            "scenario": "11762.99"
          },
          {
            "date": "2027-09-16",
            "baseline": "14154.63",
            "scenario": "11754.63"
          },
          {
            "date": "2027-09-17",
            "baseline": "14146.26",
            "scenario": "11746.26"
          },
          {
            "date": "2027-09-18",
            "baseline": "14063.45",
            "scenario": "11663.45"
          },
          {
            "date": "2027-09-19",
            "baseline": "14055.08",
            "scenario": "11655.08"
          },
          {
            "date": "2027-09-20",
            "baseline": "14046.72",
            "scenario": "11646.72"
          },
          {
            "date": "2027-09-21",
            "baseline": "14038.35",
            "scenario": "11638.35"
          },
          {
            "date": "2027-09-22",
            "baseline": "14029.99",
            "scenario": "11629.99"
          },
          {
            "date": "2027-09-23",
            "baseline": "14021.62",
            "scenario": "11621.62"
          },
          {
            "date": "2027-09-24",
            "baseline": "14013.25",
            "scenario": "11613.25"
          },
          {
            "date": "2027-09-25",
            "baseline": "18004.89",
            "scenario": "15604.89"
          },
          {
            "date": "2027-09-26",
            "baseline": "17496.52",
            "scenario": "15096.52"
          },
          {
            "date": "2027-09-27",
            "baseline": "17488.16",
            "scenario": "15088.16"
          },
          {
            "date": "2027-09-28",
            "baseline": "17479.79",
            "scenario": "15079.79"
          },
          {
            "date": "2027-09-29",
            "baseline": "17471.43",
            "scenario": "15071.43"
          },
          {
            "date": "2027-09-30",
            "baseline": "15801.47",
            "scenario": "13401.47"
          },
          {
            "date": "2027-10-01",
            "baseline": "14293.37",
            "scenario": "11893.37"
          },
          {
            "date": "2027-10-02",
            "baseline": "14285.28",
            "scenario": "11885.28"
          },
          {
            "date": "2027-10-03",
            "baseline": "14277.18",
            "scenario": "11877.18"
          },
          {
            "date": "2027-10-04",
            "baseline": "14269.09",
            "scenario": "11869.09"
          },
          {
            "date": "2027-10-05",
            "baseline": "14260.99",
            "scenario": "11860.99"
          },
          {
            "date": "2027-10-06",
            "baseline": "14252.90",
            "scenario": "11852.90"
          },
          {
            "date": "2027-10-07",
            "baseline": "14244.80",
            "scenario": "11844.80"
          },
          {
            "date": "2027-10-08",
            "baseline": "14223.71",
            "scenario": "11823.71"
          },
          {
            "date": "2027-10-09",
            "baseline": "14215.62",
            "scenario": "11815.62"
          },
          {
            "date": "2027-10-10",
            "baseline": "14207.52",
            "scenario": "11807.52"
          },
          {
            "date": "2027-10-11",
            "baseline": "14199.43",
            "scenario": "11799.43"
          },
          {
            "date": "2027-10-12",
            "baseline": "14191.33",
            "scenario": "11791.33"
          },
          {
            "date": "2027-10-13",
            "baseline": "14183.23",
            "scenario": "11783.23"
          },
          {
            "date": "2027-10-14",
            "baseline": "14175.14",
            "scenario": "11775.14"
          },
          {
            "date": "2027-10-15",
            "baseline": "14167.04",
            "scenario": "11767.04"
          },
          {
            "date": "2027-10-16",
            "baseline": "14158.95",
            "scenario": "11758.95"
          },
          {
            "date": "2027-10-17",
            "baseline": "14150.85",
            "scenario": "11750.85"
          },
          {
            "date": "2027-10-18",
            "baseline": "14068.31",
            "scenario": "11668.31"
          },
          {
            "date": "2027-10-19",
            "baseline": "14060.21",
            "scenario": "11660.21"
          },
          {
            "date": "2027-10-20",
            "baseline": "14052.11",
            "scenario": "11652.11"
          },
          {
            "date": "2027-10-21",
            "baseline": "14044.02",
            "scenario": "11644.02"
          },
          {
            "date": "2027-10-22",
            "baseline": "14035.92",
            "scenario": "11635.92"
          },
          {
            "date": "2027-10-23",
            "baseline": "14027.83",
            "scenario": "11627.83"
          },
          {
            "date": "2027-10-24",
            "baseline": "14019.73",
            "scenario": "11619.73"
          },
          {
            "date": "2027-10-25",
            "baseline": "18011.63",
            "scenario": "15611.63"
          },
          {
            "date": "2027-10-26",
            "baseline": "17503.54",
            "scenario": "15103.54"
          },
          {
            "date": "2027-10-27",
            "baseline": "17495.44",
            "scenario": "15095.44"
          },
          {
            "date": "2027-10-28",
            "baseline": "17487.35",
            "scenario": "15087.35"
          },
          {
            "date": "2027-10-29",
            "baseline": "17479.25",
            "scenario": "15079.25"
          },
          {
            "date": "2027-10-30",
            "baseline": "17471.16",
            "scenario": "15071.16"
          },
          {
            "date": "2027-10-31",
            "baseline": "15801.47",
            "scenario": "13401.47"
          }
        ],
        "monthly": [
          {
            "month": "2026-10",
            "date": "2026-10-11",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "335901.47",
              "scenario": "335901.47",
              "delta": "0.00"
            }
          },
          {
            "month": "2026-10",
            "date": "2026-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "339446.94",
              "scenario": "339446.94",
              "delta": "0.00"
            }
          },
          {
            "month": "2026-11",
            "date": "2026-11-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "341638.33",
              "scenario": "339238.33",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2026-12",
            "date": "2026-12-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "343837.56",
              "scenario": "341437.56",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-01",
            "date": "2027-01-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "346044.63",
              "scenario": "343644.63",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-02",
            "date": "2027-02-28",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "348259.58",
              "scenario": "345859.58",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-03",
            "date": "2027-03-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "350482.42",
              "scenario": "348082.42",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-04",
            "date": "2027-04-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "352713.21",
              "scenario": "350313.21",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-05",
            "date": "2027-05-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "354951.95",
              "scenario": "352551.95",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-06",
            "date": "2027-06-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "357198.69",
              "scenario": "354798.69",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-07",
            "date": "2027-07-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "359453.45",
              "scenario": "357053.45",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-08",
            "date": "2027-08-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "361716.25",
              "scenario": "359316.25",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-09",
            "date": "2027-09-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "363987.14",
              "scenario": "361587.14",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-10",
            "date": "2027-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "366266.13",
              "scenario": "363866.13",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-11",
            "date": "2027-11-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "368553.27",
              "scenario": "366153.27",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2027-12",
            "date": "2027-12-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "370848.58",
              "scenario": "368448.58",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-01",
            "date": "2028-01-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "373152.08",
              "scenario": "370752.08",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-02",
            "date": "2028-02-29",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "375463.82",
              "scenario": "373063.82",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-03",
            "date": "2028-03-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "377783.80",
              "scenario": "375383.80",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-04",
            "date": "2028-04-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "380112.09",
              "scenario": "377712.09",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-05",
            "date": "2028-05-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "382448.69",
              "scenario": "380048.69",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-06",
            "date": "2028-06-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "384793.64",
              "scenario": "382393.64",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-07",
            "date": "2028-07-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "387146.98",
              "scenario": "384746.98",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-08",
            "date": "2028-08-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "389508.73",
              "scenario": "387108.73",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-09",
            "date": "2028-09-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "391878.91",
              "scenario": "389478.91",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-10",
            "date": "2028-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "394257.57",
              "scenario": "391857.57",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-11",
            "date": "2028-11-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "396644.74",
              "scenario": "394244.74",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2028-12",
            "date": "2028-12-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "399040.44",
              "scenario": "396640.44",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-01",
            "date": "2029-01-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "401444.71",
              "scenario": "399044.71",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-02",
            "date": "2029-02-28",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "403857.57",
              "scenario": "401457.57",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-03",
            "date": "2029-03-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "406279.05",
              "scenario": "403879.05",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-04",
            "date": "2029-04-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "408709.20",
              "scenario": "406309.20",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-05",
            "date": "2029-05-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "411148.05",
              "scenario": "408748.05",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-06",
            "date": "2029-06-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "413595.36",
              "scenario": "411195.36",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-07",
            "date": "2029-07-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "416050.87",
              "scenario": "413650.87",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-08",
            "date": "2029-08-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "418514.60",
              "scenario": "416114.60",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-09",
            "date": "2029-09-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "420986.59",
              "scenario": "418586.59",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-10",
            "date": "2029-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "423466.86",
              "scenario": "421066.86",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-11",
            "date": "2029-11-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "425955.44",
              "scenario": "423555.44",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2029-12",
            "date": "2029-12-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "428452.37",
              "scenario": "426052.37",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-01",
            "date": "2030-01-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "430957.66",
              "scenario": "428557.66",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-02",
            "date": "2030-02-28",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "433471.35",
              "scenario": "431071.35",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-03",
            "date": "2030-03-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "435993.46",
              "scenario": "433593.46",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-04",
            "date": "2030-04-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "438524.01",
              "scenario": "436124.01",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-05",
            "date": "2030-05-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "441063.05",
              "scenario": "438663.05",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-06",
            "date": "2030-06-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "443610.59",
              "scenario": "441210.59",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-07",
            "date": "2030-07-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "446166.67",
              "scenario": "443766.67",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-08",
            "date": "2030-08-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "448731.31",
              "scenario": "446331.31",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-09",
            "date": "2030-09-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "451304.54",
              "scenario": "448904.54",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-10",
            "date": "2030-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "453886.40",
              "scenario": "451486.40",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-11",
            "date": "2030-11-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "456476.90",
              "scenario": "454076.90",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2030-12",
            "date": "2030-12-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "459076.09",
              "scenario": "456676.09",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2031-01",
            "date": "2031-01-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "461683.99",
              "scenario": "459283.99",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2031-02",
            "date": "2031-02-28",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "464300.62",
              "scenario": "461900.62",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2031-03",
            "date": "2031-03-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "466926.03",
              "scenario": "464526.03",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2031-04",
            "date": "2031-04-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "469560.23",
              "scenario": "467160.23",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2031-05",
            "date": "2031-05-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "472203.26",
              "scenario": "469803.26",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2031-06",
            "date": "2031-06-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "474855.14",
              "scenario": "472455.14",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2031-07",
            "date": "2031-07-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "477515.91",
              "scenario": "475115.91",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2031-08",
            "date": "2031-08-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "480185.58",
              "scenario": "477785.58",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2031-09",
            "date": "2031-09-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "482864.21",
              "scenario": "480464.21",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2031-10",
            "date": "2031-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "13401.47",
              "delta": "-2400.00"
            },
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "483151.81",
              "delta": "-2400.00"
            }
          }
        ]
      }
    },
    {
      "schema": "salli.scenario/1",
      "label": "Instalments",
      "as_of": "2026-10-11",
      "horizon_years": 5,
      "currency": "EUR",
      "hash": "sha256:6ee0e3d2f4c5ccb067625dbdf7a6b9280101ec8c82458024f18dd70c8d710b0f",
      "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
      "scenario": {
        "schema": "salli.scenario/1",
        "label": "Instalments",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "changes": [
          {
            "type": "one_off",
            "date": "2026-11-02",
            "amount": "-2400.00",
            "account": "chk",
            "tax_role": null,
            "label": "Laptop"
          },
          {
            "type": "loan",
            "principal": "2400.00",
            "annual_rate": "0.069",
            "term_months": 12,
            "start": "2026-11-02",
            "into": "chk",
            "label": "Laptop instalments"
          }
        ],
        "tax": null
      },
      "changes": [
        {
          "index": 0,
          "type": "one_off",
          "label": "Laptop",
          "debt_id": null,
          "payment": null,
          "first_payment": null,
          "monthly": null,
          "for_good": null,
          "stopped": [],
          "holding": null
        },
        {
          "index": 1,
          "type": "loan",
          "label": "Laptop instalments",
          "debt_id": "scenario-loan-2",
          "payment": "207.55",
          "first_payment": "2026-12",
          "monthly": null,
          "for_good": null,
          "stopped": [],
          "holding": null
        }
      ],
      "cash": {
        "start": "2026-10-11",
        "end": "2027-10-31",
        "lowest": {
          "baseline": "13998.91",
          "scenario": "13821.01",
          "delta": "-177.90"
        },
        "lowest_date": {
          "baseline": "2027-02-24",
          "scenario": "2027-02-24",
          "delta_days": 0
        },
        "at_end": {
          "baseline": "15801.47",
          "scenario": "15801.47",
          "delta": "0.00"
        },
        "safe_to_spend": {
          "baseline": "15316.35",
          "scenario": "15316.35",
          "delta": "0.00"
        },
        "safe_until": "2026-10-25",
        "accounts": [
          {
            "account_id": "chk",
            "name": "Checking",
            "currency": "EUR",
            "lowest": {
              "baseline": "6063.46",
              "scenario": "6063.46",
              "delta": "0.00"
            },
            "lowest_date": {
              "baseline": "2026-10-15",
              "scenario": "2026-10-15",
              "delta_days": 0
            },
            "below_zero": {
              "baseline": false,
              "scenario": false
            }
          },
          {
            "account_id": "sav",
            "name": "Savings",
            "currency": "EUR",
            "lowest": {
              "baseline": "7800.00",
              "scenario": "7800.00",
              "delta": "0.00"
            },
            "lowest_date": {
              "baseline": "2026-10-11",
              "scenario": "2026-10-11",
              "delta_days": 0
            },
            "below_zero": {
              "baseline": false,
              "scenario": false
            }
          },
          {
            "account_id": "usd",
            "name": "Dollar account",
            "currency": "USD",
            "lowest": {
              "baseline": "2500.00",
              "scenario": "2500.00",
              "delta": "0.00"
            },
            "lowest_date": {
              "baseline": "2026-10-11",
              "scenario": "2026-10-11",
              "delta_days": 0
            },
            "below_zero": {
              "baseline": false,
              "scenario": false
            }
          }
        ],
        "below_zero": {
          "baseline": [],
          "scenario": []
        }
      },
      "monthly": [
        {
          "years": 1,
          "month": "2027-10",
          "date": "2027-10-31",
          "net_worth": {
            "baseline": "366266.13",
            "scenario": "363738.21",
            "delta": "-2527.92"
          },
          "cash": {
            "baseline": "15801.47",
            "scenario": "15801.47",
            "delta": "0.00"
          },
          "investments": {
            "baseline": "63546.81",
            "scenario": "61225.33",
            "delta": "-2321.48"
          },
          "debts": {
            "baseline": "13082.15",
            "scenario": "13288.59",
            "delta": "206.44"
          },
          "other_assets": {
            "baseline": "300000.00",
            "scenario": "300000.00",
            "delta": "0.00"
          },
          "other_assets_value": {
            "baseline": "300000.00",
            "scenario": "300000.00",
            "delta": "0.00"
          }
        },
        {
          "years": 5,
          "month": "2031-10",
          "date": "2031-10-31",
          "net_worth": {
            "baseline": "485551.81",
            "scenario": "482585.47",
            "delta": "-2966.34"
          },
          "cash": {
            "baseline": "15801.47",
            "scenario": "15801.47",
            "delta": "0.00"
          },
          "investments": {
            "baseline": "171707.25",
            "scenario": "168740.91",
            "delta": "-2966.34"
          },
          "debts": {
            "baseline": "1956.91",
            "scenario": "1956.91",
            "delta": "0.00"
          },
          "other_assets": {
            "baseline": "300000.00",
            "scenario": "300000.00",
            "delta": "0.00"
          },
          "other_assets_value": {
            "baseline": "300000.00",
            "scenario": "300000.00",
            "delta": "0.00"
          }
        }
      ],
      "debts": {
        "items": [
          {
            "debt_id": "debt-car",
            "name": "Car loan",
            "source": "account",
            "paid_off": {
              "baseline": "2029-05",
              "scenario": "2029-05",
              "delta_months": 0
            },
            "total_interest": {
              "baseline": "786.13",
              "scenario": "786.13",
              "delta": "0.00"
            }
          },
          {
            "debt_id": "debt-student",
            "name": "Student loan",
            "source": "declared",
            "paid_off": {
              "baseline": "2033-03",
              "scenario": "2033-03",
              "delta_months": 0
            },
            "total_interest": {
              "baseline": "1223.12",
              "scenario": "1223.12",
              "delta": "0.00"
            }
          },
          {
            "debt_id": "scenario-loan-2",
            "name": "Laptop instalments",
            "source": "scenario",
            "paid_off": {
              "baseline": null,
              "scenario": "2027-11",
              "delta_months": null
            },
            "total_interest": {
              "baseline": "0.00",
              "scenario": "90.68",
              "delta": "90.68"
            }
          }
        ],
        "total_interest": {
          "baseline": "2009.25",
          "scenario": "2099.93",
          "delta": "90.68"
        },
        "debt_free": {
          "baseline": "2033-03",
          "scenario": "2033-03",
          "delta_months": 0
        }
      },
      "resilience": {
        "basis": "essential",
        "monthly_spending": "1898.32",
        "lowest": {
          "baseline": "7.37",
          "scenario": "7.28",
          "delta": "-0.09"
        },
        "at_end": {
          "baseline": "8.32",
          "scenario": "8.32",
          "delta": "0.00"
        }
      },
      "fi": {
        "fi_number": {
          "baseline": "714042.04",
          "scenario": "714042.04",
          "delta": "0.00"
        },
        "monthly_spending": {
          "baseline": "2037.09",
          "scenario": "2037.09",
          "delta": "0.00"
        },
        "fi_month": {
          "baseline": "2044-08",
          "scenario": "2044-09",
          "delta_months": 1
        },
        "months_gained": -1
      },
      "break_evens": [],
      "tax": {
        "status": "none",
        "reason": null,
        "years": [],
        "this_year": null,
        "change_this_year": "0.00",
        "total_change": "0.00",
        "carried_forward": false
      },
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
        "nominal_returns": null,
        "cma": null
      },
      "placeholders": [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "drawdown_horizon",
        "inflation"
      ],
      "versions": {
        "schema": "salli.scenario/1",
        "engine": "4",
        "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
        "rule_sets": []
      },
      "data_as_of": "2026-10-09",
      "is_stale": false,
      "notes": [],
      "timeline": {
        "daily": [
          {
            "date": "2026-10-11",
            "baseline": "15803.09",
            "scenario": "15803.09"
          },
          {
            "date": "2026-10-12",
            "baseline": "15804.72",
            "scenario": "15804.72"
          },
          {
            "date": "2026-10-13",
            "baseline": "15806.34",
            "scenario": "15806.34"
          },
          {
            "date": "2026-10-14",
            "baseline": "15807.97",
            "scenario": "15807.97"
          },
          {
            "date": "2026-10-15",
            "baseline": "15809.59",
            "scenario": "15809.59"
          },
          {
            "date": "2026-10-16",
            "baseline": "15811.22",
            "scenario": "15811.22"
          },
          {
            "date": "2026-10-17",
            "baseline": "15812.84",
            "scenario": "15812.84"
          },
          {
            "date": "2026-10-18",
            "baseline": "15740.01",
            "scenario": "15740.01"
          },
          {
            "date": "2026-10-19",
            "baseline": "15741.64",
            "scenario": "15741.64"
          },
          {
            "date": "2026-10-20",
            "baseline": "15743.26",
            "scenario": "15743.26"
          },
          {
            "date": "2026-10-21",
            "baseline": "15744.89",
            "scenario": "15744.89"
          },
          {
            "date": "2026-10-22",
            "baseline": "15746.51",
            "scenario": "15746.51"
          },
          {
            "date": "2026-10-23",
            "baseline": "15748.14",
            "scenario": "15748.14"
          },
          {
            "date": "2026-10-24",
            "baseline": "15749.76",
            "scenario": "15749.76"
          },
          {
            "date": "2026-10-25",
            "baseline": "19751.38",
            "scenario": "19751.38"
          },
          {
            "date": "2026-10-26",
            "baseline": "19253.01",
            "scenario": "19253.01"
          },
          {
            "date": "2026-10-27",
            "baseline": "19254.63",
            "scenario": "19254.63"
          },
          {
            "date": "2026-10-28",
            "baseline": "19256.26",
            "scenario": "19256.26"
          },
          {
            "date": "2026-10-29",
            "baseline": "19257.88",
            "scenario": "19257.88"
          },
          {
            "date": "2026-10-30",
            "baseline": "19259.51",
            "scenario": "19259.51"
          },
          {
            "date": "2026-10-31",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2026-11-01",
            "baseline": "14293.10",
            "scenario": "14293.10"
          },
          {
            "date": "2026-11-02",
            "baseline": "14284.74",
            "scenario": "14284.74"
          },
          {
            "date": "2026-11-03",
            "baseline": "14276.37",
            "scenario": "14276.37"
          },
          {
            "date": "2026-11-04",
            "baseline": "14268.01",
            "scenario": "14268.01"
          },
          {
            "date": "2026-11-05",
            "baseline": "14259.64",
            "scenario": "14259.64"
          },
          {
            "date": "2026-11-06",
            "baseline": "14251.28",
            "scenario": "14251.28"
          },
          {
            "date": "2026-11-07",
            "baseline": "14242.91",
            "scenario": "14242.91"
          },
          {
            "date": "2026-11-08",
            "baseline": "14221.55",
            "scenario": "14221.55"
          },
          {
            "date": "2026-11-09",
            "baseline": "14213.19",
            "scenario": "14213.19"
          },
          {
            "date": "2026-11-10",
            "baseline": "14204.82",
            "scenario": "14204.82"
          },
          {
            "date": "2026-11-11",
            "baseline": "14196.46",
            "scenario": "14196.46"
          },
          {
            "date": "2026-11-12",
            "baseline": "14188.09",
            "scenario": "14188.09"
          },
          {
            "date": "2026-11-13",
            "baseline": "14179.73",
            "scenario": "14179.73"
          },
          {
            "date": "2026-11-14",
            "baseline": "14171.36",
            "scenario": "14171.36"
          },
          {
            "date": "2026-11-15",
            "baseline": "14162.99",
            "scenario": "14162.99"
          },
          {
            "date": "2026-11-16",
            "baseline": "14154.63",
            "scenario": "14154.63"
          },
          {
            "date": "2026-11-17",
            "baseline": "14146.26",
            "scenario": "14146.26"
          },
          {
            "date": "2026-11-18",
            "baseline": "14063.45",
            "scenario": "14063.45"
          },
          {
            "date": "2026-11-19",
            "baseline": "14055.08",
            "scenario": "14055.08"
          },
          {
            "date": "2026-11-20",
            "baseline": "14046.72",
            "scenario": "14046.72"
          },
          {
            "date": "2026-11-21",
            "baseline": "14038.35",
            "scenario": "14038.35"
          },
          {
            "date": "2026-11-22",
            "baseline": "14029.99",
            "scenario": "14029.99"
          },
          {
            "date": "2026-11-23",
            "baseline": "14021.62",
            "scenario": "14021.62"
          },
          {
            "date": "2026-11-24",
            "baseline": "14013.25",
            "scenario": "14013.25"
          },
          {
            "date": "2026-11-25",
            "baseline": "18004.89",
            "scenario": "18004.89"
          },
          {
            "date": "2026-11-26",
            "baseline": "17496.52",
            "scenario": "17496.52"
          },
          {
            "date": "2026-11-27",
            "baseline": "17488.16",
            "scenario": "17488.16"
          },
          {
            "date": "2026-11-28",
            "baseline": "17479.79",
            "scenario": "17479.79"
          },
          {
            "date": "2026-11-29",
            "baseline": "17471.43",
            "scenario": "17471.43"
          },
          {
            "date": "2026-11-30",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2026-12-01",
            "baseline": "14293.37",
            "scenario": "14286.68"
          },
          {
            "date": "2026-12-02",
            "baseline": "14285.28",
            "scenario": "14271.89"
          },
          {
            "date": "2026-12-03",
            "baseline": "14277.18",
            "scenario": "14257.10"
          },
          {
            "date": "2026-12-04",
            "baseline": "14269.09",
            "scenario": "14242.31"
          },
          {
            "date": "2026-12-05",
            "baseline": "14260.99",
            "scenario": "14227.52"
          },
          {
            "date": "2026-12-06",
            "baseline": "14252.90",
            "scenario": "14212.72"
          },
          {
            "date": "2026-12-07",
            "baseline": "14244.80",
            "scenario": "14197.93"
          },
          {
            "date": "2026-12-08",
            "baseline": "14223.71",
            "scenario": "14170.15"
          },
          {
            "date": "2026-12-09",
            "baseline": "14215.62",
            "scenario": "14155.36"
          },
          {
            "date": "2026-12-10",
            "baseline": "14207.52",
            "scenario": "14140.57"
          },
          {
            "date": "2026-12-11",
            "baseline": "14199.43",
            "scenario": "14125.78"
          },
          {
            "date": "2026-12-12",
            "baseline": "14191.33",
            "scenario": "14110.99"
          },
          {
            "date": "2026-12-13",
            "baseline": "14183.23",
            "scenario": "14096.20"
          },
          {
            "date": "2026-12-14",
            "baseline": "14175.14",
            "scenario": "14081.41"
          },
          {
            "date": "2026-12-15",
            "baseline": "14167.04",
            "scenario": "14066.62"
          },
          {
            "date": "2026-12-16",
            "baseline": "14158.95",
            "scenario": "14051.82"
          },
          {
            "date": "2026-12-17",
            "baseline": "14150.85",
            "scenario": "14037.03"
          },
          {
            "date": "2026-12-18",
            "baseline": "14068.31",
            "scenario": "13947.79"
          },
          {
            "date": "2026-12-19",
            "baseline": "14060.21",
            "scenario": "13933.00"
          },
          {
            "date": "2026-12-20",
            "baseline": "14052.11",
            "scenario": "13918.21"
          },
          {
            "date": "2026-12-21",
            "baseline": "14044.02",
            "scenario": "13903.42"
          },
          {
            "date": "2026-12-22",
            "baseline": "14035.92",
            "scenario": "13888.63"
          },
          {
            "date": "2026-12-23",
            "baseline": "14027.83",
            "scenario": "13873.84"
          },
          {
            "date": "2026-12-24",
            "baseline": "14019.73",
            "scenario": "13859.05"
          },
          {
            "date": "2026-12-25",
            "baseline": "18011.63",
            "scenario": "17844.26"
          },
          {
            "date": "2026-12-26",
            "baseline": "17503.54",
            "scenario": "17329.46"
          },
          {
            "date": "2026-12-27",
            "baseline": "17495.44",
            "scenario": "17314.67"
          },
          {
            "date": "2026-12-28",
            "baseline": "17487.35",
            "scenario": "17299.88"
          },
          {
            "date": "2026-12-29",
            "baseline": "17479.25",
            "scenario": "17285.09"
          },
          {
            "date": "2026-12-30",
            "baseline": "17471.16",
            "scenario": "17270.30"
          },
          {
            "date": "2026-12-31",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2027-01-01",
            "baseline": "14293.37",
            "scenario": "14286.68"
          },
          {
            "date": "2027-01-02",
            "baseline": "14285.28",
            "scenario": "14271.89"
          },
          {
            "date": "2027-01-03",
            "baseline": "14277.18",
            "scenario": "14257.10"
          },
          {
            "date": "2027-01-04",
            "baseline": "14269.09",
            "scenario": "14242.31"
          },
          {
            "date": "2027-01-05",
            "baseline": "14260.99",
            "scenario": "14227.52"
          },
          {
            "date": "2027-01-06",
            "baseline": "14252.90",
            "scenario": "14212.72"
          },
          {
            "date": "2027-01-07",
            "baseline": "14244.80",
            "scenario": "14197.93"
          },
          {
            "date": "2027-01-08",
            "baseline": "14223.71",
            "scenario": "14170.15"
          },
          {
            "date": "2027-01-09",
            "baseline": "14215.62",
            "scenario": "14155.36"
          },
          {
            "date": "2027-01-10",
            "baseline": "14207.52",
            "scenario": "14140.57"
          },
          {
            "date": "2027-01-11",
            "baseline": "14199.43",
            "scenario": "14125.78"
          },
          {
            "date": "2027-01-12",
            "baseline": "14191.33",
            "scenario": "14110.99"
          },
          {
            "date": "2027-01-13",
            "baseline": "14183.23",
            "scenario": "14096.20"
          },
          {
            "date": "2027-01-14",
            "baseline": "14175.14",
            "scenario": "14081.41"
          },
          {
            "date": "2027-01-15",
            "baseline": "14167.04",
            "scenario": "14066.62"
          },
          {
            "date": "2027-01-16",
            "baseline": "14158.95",
            "scenario": "14051.82"
          },
          {
            "date": "2027-01-17",
            "baseline": "14150.85",
            "scenario": "14037.03"
          },
          {
            "date": "2027-01-18",
            "baseline": "14068.31",
            "scenario": "13947.79"
          },
          {
            "date": "2027-01-19",
            "baseline": "14060.21",
            "scenario": "13933.00"
          },
          {
            "date": "2027-01-20",
            "baseline": "14052.11",
            "scenario": "13918.21"
          },
          {
            "date": "2027-01-21",
            "baseline": "14044.02",
            "scenario": "13903.42"
          },
          {
            "date": "2027-01-22",
            "baseline": "14035.92",
            "scenario": "13888.63"
          },
          {
            "date": "2027-01-23",
            "baseline": "14027.83",
            "scenario": "13873.84"
          },
          {
            "date": "2027-01-24",
            "baseline": "14019.73",
            "scenario": "13859.05"
          },
          {
            "date": "2027-01-25",
            "baseline": "18011.63",
            "scenario": "17844.26"
          },
          {
            "date": "2027-01-26",
            "baseline": "17503.54",
            "scenario": "17329.46"
          },
          {
            "date": "2027-01-27",
            "baseline": "17495.44",
            "scenario": "17314.67"
          },
          {
            "date": "2027-01-28",
            "baseline": "17487.35",
            "scenario": "17299.88"
          },
          {
            "date": "2027-01-29",
            "baseline": "17479.25",
            "scenario": "17285.09"
          },
          {
            "date": "2027-01-30",
            "baseline": "17471.16",
            "scenario": "17270.30"
          },
          {
            "date": "2027-01-31",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2027-02-01",
            "baseline": "14292.51",
            "scenario": "14285.09"
          },
          {
            "date": "2027-02-02",
            "baseline": "14283.54",
            "scenario": "14268.72"
          },
          {
            "date": "2027-02-03",
            "baseline": "14274.58",
            "scenario": "14252.34"
          },
          {
            "date": "2027-02-04",
            "baseline": "14265.62",
            "scenario": "14235.97"
          },
          {
            "date": "2027-02-05",
            "baseline": "14256.65",
            "scenario": "14219.59"
          },
          {
            "date": "2027-02-06",
            "baseline": "14247.69",
            "scenario": "14203.22"
          },
          {
            "date": "2027-02-07",
            "baseline": "14238.73",
            "scenario": "14186.84"
          },
          {
            "date": "2027-02-08",
            "baseline": "14216.77",
            "scenario": "14157.47"
          },
          {
            "date": "2027-02-09",
            "baseline": "14207.81",
            "scenario": "14141.10"
          },
          {
            "date": "2027-02-10",
            "baseline": "14198.85",
            "scenario": "14124.72"
          },
          {
            "date": "2027-02-11",
            "baseline": "14189.88",
            "scenario": "14108.35"
          },
          {
            "date": "2027-02-12",
            "baseline": "14180.92",
            "scenario": "14091.97"
          },
          {
            "date": "2027-02-13",
            "baseline": "14171.96",
            "scenario": "14075.60"
          },
          {
            "date": "2027-02-14",
            "baseline": "14162.99",
            "scenario": "14059.22"
          },
          {
            "date": "2027-02-15",
            "baseline": "14154.03",
            "scenario": "14042.84"
          },
          {
            "date": "2027-02-16",
            "baseline": "14145.07",
            "scenario": "14026.47"
          },
          {
            "date": "2027-02-17",
            "baseline": "14136.11",
            "scenario": "14010.09"
          },
          {
            "date": "2027-02-18",
            "baseline": "14052.69",
            "scenario": "13919.27"
          },
          {
            "date": "2027-02-19",
            "baseline": "14043.73",
            "scenario": "13902.89"
          },
          {
            "date": "2027-02-20",
            "baseline": "14034.77",
            "scenario": "13886.52"
          },
          {
            "date": "2027-02-21",
            "baseline": "14025.80",
            "scenario": "13870.14"
          },
          {
            "date": "2027-02-22",
            "baseline": "14016.84",
            "scenario": "13853.76"
          },
          {
            "date": "2027-02-23",
            "baseline": "14007.88",
            "scenario": "13837.39"
          },
          {
            "date": "2027-02-24",
            "baseline": "13998.91",
            "scenario": "13821.01"
          },
          {
            "date": "2027-02-25",
            "baseline": "17989.95",
            "scenario": "17804.64"
          },
          {
            "date": "2027-02-26",
            "baseline": "17480.99",
            "scenario": "17288.26"
          },
          {
            "date": "2027-02-27",
            "baseline": "17472.02",
            "scenario": "17271.89"
          },
          {
            "date": "2027-02-28",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2027-03-01",
            "baseline": "14293.37",
            "scenario": "14286.68"
          },
          {
            "date": "2027-03-02",
            "baseline": "14285.28",
            "scenario": "14271.89"
          },
          {
            "date": "2027-03-03",
            "baseline": "14277.18",
            "scenario": "14257.10"
          },
          {
            "date": "2027-03-04",
            "baseline": "14269.09",
            "scenario": "14242.31"
          },
          {
            "date": "2027-03-05",
            "baseline": "14260.99",
            "scenario": "14227.52"
          },
          {
            "date": "2027-03-06",
            "baseline": "14252.90",
            "scenario": "14212.72"
          },
          {
            "date": "2027-03-07",
            "baseline": "14244.80",
            "scenario": "14197.93"
          },
          {
            "date": "2027-03-08",
            "baseline": "14223.71",
            "scenario": "14170.15"
          },
          {
            "date": "2027-03-09",
            "baseline": "14215.62",
            "scenario": "14155.36"
          },
          {
            "date": "2027-03-10",
            "baseline": "14207.52",
            "scenario": "14140.57"
          },
          {
            "date": "2027-03-11",
            "baseline": "14199.43",
            "scenario": "14125.78"
          },
          {
            "date": "2027-03-12",
            "baseline": "14191.33",
            "scenario": "14110.99"
          },
          {
            "date": "2027-03-13",
            "baseline": "14183.23",
            "scenario": "14096.20"
          },
          {
            "date": "2027-03-14",
            "baseline": "14175.14",
            "scenario": "14081.41"
          },
          {
            "date": "2027-03-15",
            "baseline": "14167.04",
            "scenario": "14066.62"
          },
          {
            "date": "2027-03-16",
            "baseline": "14158.95",
            "scenario": "14051.82"
          },
          {
            "date": "2027-03-17",
            "baseline": "14150.85",
            "scenario": "14037.03"
          },
          {
            "date": "2027-03-18",
            "baseline": "14068.31",
            "scenario": "13947.79"
          },
          {
            "date": "2027-03-19",
            "baseline": "14060.21",
            "scenario": "13933.00"
          },
          {
            "date": "2027-03-20",
            "baseline": "14052.11",
            "scenario": "13918.21"
          },
          {
            "date": "2027-03-21",
            "baseline": "14044.02",
            "scenario": "13903.42"
          },
          {
            "date": "2027-03-22",
            "baseline": "14035.92",
            "scenario": "13888.63"
          },
          {
            "date": "2027-03-23",
            "baseline": "14027.83",
            "scenario": "13873.84"
          },
          {
            "date": "2027-03-24",
            "baseline": "14019.73",
            "scenario": "13859.05"
          },
          {
            "date": "2027-03-25",
            "baseline": "18011.63",
            "scenario": "17844.26"
          },
          {
            "date": "2027-03-26",
            "baseline": "17503.54",
            "scenario": "17329.46"
          },
          {
            "date": "2027-03-27",
            "baseline": "17495.44",
            "scenario": "17314.67"
          },
          {
            "date": "2027-03-28",
            "baseline": "17487.35",
            "scenario": "17299.88"
          },
          {
            "date": "2027-03-29",
            "baseline": "17479.25",
            "scenario": "17285.09"
          },
          {
            "date": "2027-03-30",
            "baseline": "17471.16",
            "scenario": "17270.30"
          },
          {
            "date": "2027-03-31",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2027-04-01",
            "baseline": "14293.10",
            "scenario": "14286.19"
          },
          {
            "date": "2027-04-02",
            "baseline": "14284.74",
            "scenario": "14270.90"
          },
          {
            "date": "2027-04-03",
            "baseline": "14276.37",
            "scenario": "14255.62"
          },
          {
            "date": "2027-04-04",
            "baseline": "14268.01",
            "scenario": "14240.33"
          },
          {
            "date": "2027-04-05",
            "baseline": "14259.64",
            "scenario": "14225.05"
          },
          {
            "date": "2027-04-06",
            "baseline": "14251.28",
            "scenario": "14209.77"
          },
          {
            "date": "2027-04-07",
            "baseline": "14242.91",
            "scenario": "14194.48"
          },
          {
            "date": "2027-04-08",
            "baseline": "14221.55",
            "scenario": "14166.21"
          },
          {
            "date": "2027-04-09",
            "baseline": "14213.19",
            "scenario": "14150.92"
          },
          {
            "date": "2027-04-10",
            "baseline": "14204.82",
            "scenario": "14135.64"
          },
          {
            "date": "2027-04-11",
            "baseline": "14196.46",
            "scenario": "14120.36"
          },
          {
            "date": "2027-04-12",
            "baseline": "14188.09",
            "scenario": "14105.07"
          },
          {
            "date": "2027-04-13",
            "baseline": "14179.73",
            "scenario": "14089.79"
          },
          {
            "date": "2027-04-14",
            "baseline": "14171.36",
            "scenario": "14074.50"
          },
          {
            "date": "2027-04-15",
            "baseline": "14162.99",
            "scenario": "14059.22"
          },
          {
            "date": "2027-04-16",
            "baseline": "14154.63",
            "scenario": "14043.94"
          },
          {
            "date": "2027-04-17",
            "baseline": "14146.26",
            "scenario": "14028.65"
          },
          {
            "date": "2027-04-18",
            "baseline": "14063.45",
            "scenario": "13938.92"
          },
          {
            "date": "2027-04-19",
            "baseline": "14055.08",
            "scenario": "13923.63"
          },
          {
            "date": "2027-04-20",
            "baseline": "14046.72",
            "scenario": "13908.35"
          },
          {
            "date": "2027-04-21",
            "baseline": "14038.35",
            "scenario": "13893.07"
          },
          {
            "date": "2027-04-22",
            "baseline": "14029.99",
            "scenario": "13877.78"
          },
          {
            "date": "2027-04-23",
            "baseline": "14021.62",
            "scenario": "13862.50"
          },
          {
            "date": "2027-04-24",
            "baseline": "14013.25",
            "scenario": "13847.21"
          },
          {
            "date": "2027-04-25",
            "baseline": "18004.89",
            "scenario": "17831.93"
          },
          {
            "date": "2027-04-26",
            "baseline": "17496.52",
            "scenario": "17316.65"
          },
          {
            "date": "2027-04-27",
            "baseline": "17488.16",
            "scenario": "17301.36"
          },
          {
            "date": "2027-04-28",
            "baseline": "17479.79",
            "scenario": "17286.08"
          },
          {
            "date": "2027-04-29",
            "baseline": "17471.43",
            "scenario": "17270.79"
          },
          {
            "date": "2027-04-30",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2027-05-01",
            "baseline": "14293.37",
            "scenario": "14286.68"
          },
          {
            "date": "2027-05-02",
            "baseline": "14285.28",
            "scenario": "14271.89"
          },
          {
            "date": "2027-05-03",
            "baseline": "14277.18",
            "scenario": "14257.10"
          },
          {
            "date": "2027-05-04",
            "baseline": "14269.09",
            "scenario": "14242.31"
          },
          {
            "date": "2027-05-05",
            "baseline": "14260.99",
            "scenario": "14227.52"
          },
          {
            "date": "2027-05-06",
            "baseline": "14252.90",
            "scenario": "14212.72"
          },
          {
            "date": "2027-05-07",
            "baseline": "14244.80",
            "scenario": "14197.93"
          },
          {
            "date": "2027-05-08",
            "baseline": "14223.71",
            "scenario": "14170.15"
          },
          {
            "date": "2027-05-09",
            "baseline": "14215.62",
            "scenario": "14155.36"
          },
          {
            "date": "2027-05-10",
            "baseline": "14207.52",
            "scenario": "14140.57"
          },
          {
            "date": "2027-05-11",
            "baseline": "14199.43",
            "scenario": "14125.78"
          },
          {
            "date": "2027-05-12",
            "baseline": "14191.33",
            "scenario": "14110.99"
          },
          {
            "date": "2027-05-13",
            "baseline": "14183.23",
            "scenario": "14096.20"
          },
          {
            "date": "2027-05-14",
            "baseline": "14175.14",
            "scenario": "14081.41"
          },
          {
            "date": "2027-05-15",
            "baseline": "14167.04",
            "scenario": "14066.62"
          },
          {
            "date": "2027-05-16",
            "baseline": "14158.95",
            "scenario": "14051.82"
          },
          {
            "date": "2027-05-17",
            "baseline": "14150.85",
            "scenario": "14037.03"
          },
          {
            "date": "2027-05-18",
            "baseline": "14068.31",
            "scenario": "13947.79"
          },
          {
            "date": "2027-05-19",
            "baseline": "14060.21",
            "scenario": "13933.00"
          },
          {
            "date": "2027-05-20",
            "baseline": "14052.11",
            "scenario": "13918.21"
          },
          {
            "date": "2027-05-21",
            "baseline": "14044.02",
            "scenario": "13903.42"
          },
          {
            "date": "2027-05-22",
            "baseline": "14035.92",
            "scenario": "13888.63"
          },
          {
            "date": "2027-05-23",
            "baseline": "14027.83",
            "scenario": "13873.84"
          },
          {
            "date": "2027-05-24",
            "baseline": "14019.73",
            "scenario": "13859.05"
          },
          {
            "date": "2027-05-25",
            "baseline": "18011.63",
            "scenario": "17844.26"
          },
          {
            "date": "2027-05-26",
            "baseline": "17503.54",
            "scenario": "17329.46"
          },
          {
            "date": "2027-05-27",
            "baseline": "17495.44",
            "scenario": "17314.67"
          },
          {
            "date": "2027-05-28",
            "baseline": "17487.35",
            "scenario": "17299.88"
          },
          {
            "date": "2027-05-29",
            "baseline": "17479.25",
            "scenario": "17285.09"
          },
          {
            "date": "2027-05-30",
            "baseline": "17471.16",
            "scenario": "17270.30"
          },
          {
            "date": "2027-05-31",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2027-06-01",
            "baseline": "14293.10",
            "scenario": "14286.19"
          },
          {
            "date": "2027-06-02",
            "baseline": "14284.74",
            "scenario": "14270.90"
          },
          {
            "date": "2027-06-03",
            "baseline": "14276.37",
            "scenario": "14255.62"
          },
          {
            "date": "2027-06-04",
            "baseline": "14268.01",
            "scenario": "14240.33"
          },
          {
            "date": "2027-06-05",
            "baseline": "14259.64",
            "scenario": "14225.05"
          },
          {
            "date": "2027-06-06",
            "baseline": "14251.28",
            "scenario": "14209.77"
          },
          {
            "date": "2027-06-07",
            "baseline": "14242.91",
            "scenario": "14194.48"
          },
          {
            "date": "2027-06-08",
            "baseline": "14221.55",
            "scenario": "14166.21"
          },
          {
            "date": "2027-06-09",
            "baseline": "14213.19",
            "scenario": "14150.92"
          },
          {
            "date": "2027-06-10",
            "baseline": "14204.82",
            "scenario": "14135.64"
          },
          {
            "date": "2027-06-11",
            "baseline": "14196.46",
            "scenario": "14120.36"
          },
          {
            "date": "2027-06-12",
            "baseline": "14188.09",
            "scenario": "14105.07"
          },
          {
            "date": "2027-06-13",
            "baseline": "14179.73",
            "scenario": "14089.79"
          },
          {
            "date": "2027-06-14",
            "baseline": "14171.36",
            "scenario": "14074.50"
          },
          {
            "date": "2027-06-15",
            "baseline": "14162.99",
            "scenario": "14059.22"
          },
          {
            "date": "2027-06-16",
            "baseline": "14154.63",
            "scenario": "14043.94"
          },
          {
            "date": "2027-06-17",
            "baseline": "14146.26",
            "scenario": "14028.65"
          },
          {
            "date": "2027-06-18",
            "baseline": "14063.45",
            "scenario": "13938.92"
          },
          {
            "date": "2027-06-19",
            "baseline": "14055.08",
            "scenario": "13923.63"
          },
          {
            "date": "2027-06-20",
            "baseline": "14046.72",
            "scenario": "13908.35"
          },
          {
            "date": "2027-06-21",
            "baseline": "14038.35",
            "scenario": "13893.07"
          },
          {
            "date": "2027-06-22",
            "baseline": "14029.99",
            "scenario": "13877.78"
          },
          {
            "date": "2027-06-23",
            "baseline": "14021.62",
            "scenario": "13862.50"
          },
          {
            "date": "2027-06-24",
            "baseline": "14013.25",
            "scenario": "13847.21"
          },
          {
            "date": "2027-06-25",
            "baseline": "18004.89",
            "scenario": "17831.93"
          },
          {
            "date": "2027-06-26",
            "baseline": "17496.52",
            "scenario": "17316.65"
          },
          {
            "date": "2027-06-27",
            "baseline": "17488.16",
            "scenario": "17301.36"
          },
          {
            "date": "2027-06-28",
            "baseline": "17479.79",
            "scenario": "17286.08"
          },
          {
            "date": "2027-06-29",
            "baseline": "17471.43",
            "scenario": "17270.79"
          },
          {
            "date": "2027-06-30",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2027-07-01",
            "baseline": "14293.37",
            "scenario": "14286.68"
          },
          {
            "date": "2027-07-02",
            "baseline": "14285.28",
            "scenario": "14271.89"
          },
          {
            "date": "2027-07-03",
            "baseline": "14277.18",
            "scenario": "14257.10"
          },
          {
            "date": "2027-07-04",
            "baseline": "14269.09",
            "scenario": "14242.31"
          },
          {
            "date": "2027-07-05",
            "baseline": "14260.99",
            "scenario": "14227.52"
          },
          {
            "date": "2027-07-06",
            "baseline": "14252.90",
            "scenario": "14212.72"
          },
          {
            "date": "2027-07-07",
            "baseline": "14244.80",
            "scenario": "14197.93"
          },
          {
            "date": "2027-07-08",
            "baseline": "14223.71",
            "scenario": "14170.15"
          },
          {
            "date": "2027-07-09",
            "baseline": "14215.62",
            "scenario": "14155.36"
          },
          {
            "date": "2027-07-10",
            "baseline": "14207.52",
            "scenario": "14140.57"
          },
          {
            "date": "2027-07-11",
            "baseline": "14199.43",
            "scenario": "14125.78"
          },
          {
            "date": "2027-07-12",
            "baseline": "14191.33",
            "scenario": "14110.99"
          },
          {
            "date": "2027-07-13",
            "baseline": "14183.23",
            "scenario": "14096.20"
          },
          {
            "date": "2027-07-14",
            "baseline": "14175.14",
            "scenario": "14081.41"
          },
          {
            "date": "2027-07-15",
            "baseline": "14167.04",
            "scenario": "14066.62"
          },
          {
            "date": "2027-07-16",
            "baseline": "14158.95",
            "scenario": "14051.82"
          },
          {
            "date": "2027-07-17",
            "baseline": "14150.85",
            "scenario": "14037.03"
          },
          {
            "date": "2027-07-18",
            "baseline": "14068.31",
            "scenario": "13947.79"
          },
          {
            "date": "2027-07-19",
            "baseline": "14060.21",
            "scenario": "13933.00"
          },
          {
            "date": "2027-07-20",
            "baseline": "14052.11",
            "scenario": "13918.21"
          },
          {
            "date": "2027-07-21",
            "baseline": "14044.02",
            "scenario": "13903.42"
          },
          {
            "date": "2027-07-22",
            "baseline": "14035.92",
            "scenario": "13888.63"
          },
          {
            "date": "2027-07-23",
            "baseline": "14027.83",
            "scenario": "13873.84"
          },
          {
            "date": "2027-07-24",
            "baseline": "14019.73",
            "scenario": "13859.05"
          },
          {
            "date": "2027-07-25",
            "baseline": "18011.63",
            "scenario": "17844.26"
          },
          {
            "date": "2027-07-26",
            "baseline": "17503.54",
            "scenario": "17329.46"
          },
          {
            "date": "2027-07-27",
            "baseline": "17495.44",
            "scenario": "17314.67"
          },
          {
            "date": "2027-07-28",
            "baseline": "17487.35",
            "scenario": "17299.88"
          },
          {
            "date": "2027-07-29",
            "baseline": "17479.25",
            "scenario": "17285.09"
          },
          {
            "date": "2027-07-30",
            "baseline": "17471.16",
            "scenario": "17270.30"
          },
          {
            "date": "2027-07-31",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2027-08-01",
            "baseline": "14293.37",
            "scenario": "14286.68"
          },
          {
            "date": "2027-08-02",
            "baseline": "14285.28",
            "scenario": "14271.89"
          },
          {
            "date": "2027-08-03",
            "baseline": "14277.18",
            "scenario": "14257.10"
          },
          {
            "date": "2027-08-04",
            "baseline": "14269.09",
            "scenario": "14242.31"
          },
          {
            "date": "2027-08-05",
            "baseline": "14260.99",
            "scenario": "14227.52"
          },
          {
            "date": "2027-08-06",
            "baseline": "14252.90",
            "scenario": "14212.72"
          },
          {
            "date": "2027-08-07",
            "baseline": "14244.80",
            "scenario": "14197.93"
          },
          {
            "date": "2027-08-08",
            "baseline": "14223.71",
            "scenario": "14170.15"
          },
          {
            "date": "2027-08-09",
            "baseline": "14215.62",
            "scenario": "14155.36"
          },
          {
            "date": "2027-08-10",
            "baseline": "14207.52",
            "scenario": "14140.57"
          },
          {
            "date": "2027-08-11",
            "baseline": "14199.43",
            "scenario": "14125.78"
          },
          {
            "date": "2027-08-12",
            "baseline": "14191.33",
            "scenario": "14110.99"
          },
          {
            "date": "2027-08-13",
            "baseline": "14183.23",
            "scenario": "14096.20"
          },
          {
            "date": "2027-08-14",
            "baseline": "14175.14",
            "scenario": "14081.41"
          },
          {
            "date": "2027-08-15",
            "baseline": "14167.04",
            "scenario": "14066.62"
          },
          {
            "date": "2027-08-16",
            "baseline": "14158.95",
            "scenario": "14051.82"
          },
          {
            "date": "2027-08-17",
            "baseline": "14150.85",
            "scenario": "14037.03"
          },
          {
            "date": "2027-08-18",
            "baseline": "14068.31",
            "scenario": "13947.79"
          },
          {
            "date": "2027-08-19",
            "baseline": "14060.21",
            "scenario": "13933.00"
          },
          {
            "date": "2027-08-20",
            "baseline": "14052.11",
            "scenario": "13918.21"
          },
          {
            "date": "2027-08-21",
            "baseline": "14044.02",
            "scenario": "13903.42"
          },
          {
            "date": "2027-08-22",
            "baseline": "14035.92",
            "scenario": "13888.63"
          },
          {
            "date": "2027-08-23",
            "baseline": "14027.83",
            "scenario": "13873.84"
          },
          {
            "date": "2027-08-24",
            "baseline": "14019.73",
            "scenario": "13859.05"
          },
          {
            "date": "2027-08-25",
            "baseline": "18011.63",
            "scenario": "17844.26"
          },
          {
            "date": "2027-08-26",
            "baseline": "17503.54",
            "scenario": "17329.46"
          },
          {
            "date": "2027-08-27",
            "baseline": "17495.44",
            "scenario": "17314.67"
          },
          {
            "date": "2027-08-28",
            "baseline": "17487.35",
            "scenario": "17299.88"
          },
          {
            "date": "2027-08-29",
            "baseline": "17479.25",
            "scenario": "17285.09"
          },
          {
            "date": "2027-08-30",
            "baseline": "17471.16",
            "scenario": "17270.30"
          },
          {
            "date": "2027-08-31",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2027-09-01",
            "baseline": "14293.10",
            "scenario": "14286.19"
          },
          {
            "date": "2027-09-02",
            "baseline": "14284.74",
            "scenario": "14270.90"
          },
          {
            "date": "2027-09-03",
            "baseline": "14276.37",
            "scenario": "14255.62"
          },
          {
            "date": "2027-09-04",
            "baseline": "14268.01",
            "scenario": "14240.33"
          },
          {
            "date": "2027-09-05",
            "baseline": "14259.64",
            "scenario": "14225.05"
          },
          {
            "date": "2027-09-06",
            "baseline": "14251.28",
            "scenario": "14209.77"
          },
          {
            "date": "2027-09-07",
            "baseline": "14242.91",
            "scenario": "14194.48"
          },
          {
            "date": "2027-09-08",
            "baseline": "14221.55",
            "scenario": "14166.21"
          },
          {
            "date": "2027-09-09",
            "baseline": "14213.19",
            "scenario": "14150.92"
          },
          {
            "date": "2027-09-10",
            "baseline": "14204.82",
            "scenario": "14135.64"
          },
          {
            "date": "2027-09-11",
            "baseline": "14196.46",
            "scenario": "14120.36"
          },
          {
            "date": "2027-09-12",
            "baseline": "14188.09",
            "scenario": "14105.07"
          },
          {
            "date": "2027-09-13",
            "baseline": "14179.73",
            "scenario": "14089.79"
          },
          {
            "date": "2027-09-14",
            "baseline": "14171.36",
            "scenario": "14074.50"
          },
          {
            "date": "2027-09-15",
            "baseline": "14162.99",
            "scenario": "14059.22"
          },
          {
            "date": "2027-09-16",
            "baseline": "14154.63",
            "scenario": "14043.94"
          },
          {
            "date": "2027-09-17",
            "baseline": "14146.26",
            "scenario": "14028.65"
          },
          {
            "date": "2027-09-18",
            "baseline": "14063.45",
            "scenario": "13938.92"
          },
          {
            "date": "2027-09-19",
            "baseline": "14055.08",
            "scenario": "13923.63"
          },
          {
            "date": "2027-09-20",
            "baseline": "14046.72",
            "scenario": "13908.35"
          },
          {
            "date": "2027-09-21",
            "baseline": "14038.35",
            "scenario": "13893.07"
          },
          {
            "date": "2027-09-22",
            "baseline": "14029.99",
            "scenario": "13877.78"
          },
          {
            "date": "2027-09-23",
            "baseline": "14021.62",
            "scenario": "13862.50"
          },
          {
            "date": "2027-09-24",
            "baseline": "14013.25",
            "scenario": "13847.21"
          },
          {
            "date": "2027-09-25",
            "baseline": "18004.89",
            "scenario": "17831.93"
          },
          {
            "date": "2027-09-26",
            "baseline": "17496.52",
            "scenario": "17316.65"
          },
          {
            "date": "2027-09-27",
            "baseline": "17488.16",
            "scenario": "17301.36"
          },
          {
            "date": "2027-09-28",
            "baseline": "17479.79",
            "scenario": "17286.08"
          },
          {
            "date": "2027-09-29",
            "baseline": "17471.43",
            "scenario": "17270.79"
          },
          {
            "date": "2027-09-30",
            "baseline": "15801.47",
            "scenario": "15801.47"
          },
          {
            "date": "2027-10-01",
            "baseline": "14293.37",
            "scenario": "14286.68"
          },
          {
            "date": "2027-10-02",
            "baseline": "14285.28",
            "scenario": "14271.89"
          },
          {
            "date": "2027-10-03",
            "baseline": "14277.18",
            "scenario": "14257.10"
          },
          {
            "date": "2027-10-04",
            "baseline": "14269.09",
            "scenario": "14242.31"
          },
          {
            "date": "2027-10-05",
            "baseline": "14260.99",
            "scenario": "14227.52"
          },
          {
            "date": "2027-10-06",
            "baseline": "14252.90",
            "scenario": "14212.72"
          },
          {
            "date": "2027-10-07",
            "baseline": "14244.80",
            "scenario": "14197.93"
          },
          {
            "date": "2027-10-08",
            "baseline": "14223.71",
            "scenario": "14170.15"
          },
          {
            "date": "2027-10-09",
            "baseline": "14215.62",
            "scenario": "14155.36"
          },
          {
            "date": "2027-10-10",
            "baseline": "14207.52",
            "scenario": "14140.57"
          },
          {
            "date": "2027-10-11",
            "baseline": "14199.43",
            "scenario": "14125.78"
          },
          {
            "date": "2027-10-12",
            "baseline": "14191.33",
            "scenario": "14110.99"
          },
          {
            "date": "2027-10-13",
            "baseline": "14183.23",
            "scenario": "14096.20"
          },
          {
            "date": "2027-10-14",
            "baseline": "14175.14",
            "scenario": "14081.41"
          },
          {
            "date": "2027-10-15",
            "baseline": "14167.04",
            "scenario": "14066.62"
          },
          {
            "date": "2027-10-16",
            "baseline": "14158.95",
            "scenario": "14051.82"
          },
          {
            "date": "2027-10-17",
            "baseline": "14150.85",
            "scenario": "14037.03"
          },
          {
            "date": "2027-10-18",
            "baseline": "14068.31",
            "scenario": "13947.79"
          },
          {
            "date": "2027-10-19",
            "baseline": "14060.21",
            "scenario": "13933.00"
          },
          {
            "date": "2027-10-20",
            "baseline": "14052.11",
            "scenario": "13918.21"
          },
          {
            "date": "2027-10-21",
            "baseline": "14044.02",
            "scenario": "13903.42"
          },
          {
            "date": "2027-10-22",
            "baseline": "14035.92",
            "scenario": "13888.63"
          },
          {
            "date": "2027-10-23",
            "baseline": "14027.83",
            "scenario": "13873.84"
          },
          {
            "date": "2027-10-24",
            "baseline": "14019.73",
            "scenario": "13859.05"
          },
          {
            "date": "2027-10-25",
            "baseline": "18011.63",
            "scenario": "17844.26"
          },
          {
            "date": "2027-10-26",
            "baseline": "17503.54",
            "scenario": "17329.46"
          },
          {
            "date": "2027-10-27",
            "baseline": "17495.44",
            "scenario": "17314.67"
          },
          {
            "date": "2027-10-28",
            "baseline": "17487.35",
            "scenario": "17299.88"
          },
          {
            "date": "2027-10-29",
            "baseline": "17479.25",
            "scenario": "17285.09"
          },
          {
            "date": "2027-10-30",
            "baseline": "17471.16",
            "scenario": "17270.30"
          },
          {
            "date": "2027-10-31",
            "baseline": "15801.47",
            "scenario": "15801.47"
          }
        ],
        "monthly": [
          {
            "month": "2026-10",
            "date": "2026-10-11",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "335901.47",
              "scenario": "335901.47",
              "delta": "0.00"
            }
          },
          {
            "month": "2026-10",
            "date": "2026-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "339446.94",
              "scenario": "339446.94",
              "delta": "0.00"
            }
          },
          {
            "month": "2026-11",
            "date": "2026-11-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "341638.33",
              "scenario": "339238.33",
              "delta": "-2400.00"
            }
          },
          {
            "month": "2026-12",
            "date": "2026-12-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "343837.56",
              "scenario": "341423.76",
              "delta": "-2413.80"
            }
          },
          {
            "month": "2027-01",
            "date": "2027-01-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "346044.63",
              "scenario": "343617.45",
              "delta": "-2427.18"
            }
          },
          {
            "month": "2027-02",
            "date": "2027-02-28",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "348259.58",
              "scenario": "345819.44",
              "delta": "-2440.14"
            }
          },
          {
            "month": "2027-03",
            "date": "2027-03-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "350482.42",
              "scenario": "348029.76",
              "delta": "-2452.66"
            }
          },
          {
            "month": "2027-04",
            "date": "2027-04-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "352713.21",
              "scenario": "350248.46",
              "delta": "-2464.75"
            }
          },
          {
            "month": "2027-05",
            "date": "2027-05-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "354951.95",
              "scenario": "352475.54",
              "delta": "-2476.40"
            }
          },
          {
            "month": "2027-06",
            "date": "2027-06-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "357198.69",
              "scenario": "354711.08",
              "delta": "-2487.61"
            }
          },
          {
            "month": "2027-07",
            "date": "2027-07-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "359453.45",
              "scenario": "356955.08",
              "delta": "-2498.37"
            }
          },
          {
            "month": "2027-08",
            "date": "2027-08-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "361716.25",
              "scenario": "359207.57",
              "delta": "-2508.68"
            }
          },
          {
            "month": "2027-09",
            "date": "2027-09-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "363987.14",
              "scenario": "361468.61",
              "delta": "-2518.53"
            }
          },
          {
            "month": "2027-10",
            "date": "2027-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "366266.13",
              "scenario": "363738.21",
              "delta": "-2527.92"
            }
          },
          {
            "month": "2027-11",
            "date": "2027-11-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "368553.27",
              "scenario": "366016.42",
              "delta": "-2536.85"
            }
          },
          {
            "month": "2027-12",
            "date": "2027-12-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "370848.58",
              "scenario": "368303.27",
              "delta": "-2545.31"
            }
          },
          {
            "month": "2028-01",
            "date": "2028-01-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "373152.08",
              "scenario": "370598.29",
              "delta": "-2553.79"
            }
          },
          {
            "month": "2028-02",
            "date": "2028-02-29",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "375463.82",
              "scenario": "372901.51",
              "delta": "-2562.31"
            }
          },
          {
            "month": "2028-03",
            "date": "2028-03-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "377783.80",
              "scenario": "375212.96",
              "delta": "-2570.85"
            }
          },
          {
            "month": "2028-04",
            "date": "2028-04-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "380112.09",
              "scenario": "377532.67",
              "delta": "-2579.42"
            }
          },
          {
            "month": "2028-05",
            "date": "2028-05-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "382448.69",
              "scenario": "379860.68",
              "delta": "-2588.01"
            }
          },
          {
            "month": "2028-06",
            "date": "2028-06-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "384793.64",
              "scenario": "382197.00",
              "delta": "-2596.64"
            }
          },
          {
            "month": "2028-07",
            "date": "2028-07-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "387146.98",
              "scenario": "384541.68",
              "delta": "-2605.30"
            }
          },
          {
            "month": "2028-08",
            "date": "2028-08-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "389508.73",
              "scenario": "386894.75",
              "delta": "-2613.98"
            }
          },
          {
            "month": "2028-09",
            "date": "2028-09-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "391878.91",
              "scenario": "389256.22",
              "delta": "-2622.69"
            }
          },
          {
            "month": "2028-10",
            "date": "2028-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "394257.57",
              "scenario": "391626.14",
              "delta": "-2631.44"
            }
          },
          {
            "month": "2028-11",
            "date": "2028-11-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "396644.74",
              "scenario": "394004.53",
              "delta": "-2640.21"
            }
          },
          {
            "month": "2028-12",
            "date": "2028-12-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "399040.44",
              "scenario": "396391.43",
              "delta": "-2649.01"
            }
          },
          {
            "month": "2029-01",
            "date": "2029-01-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "401444.71",
              "scenario": "398786.87",
              "delta": "-2657.84"
            }
          },
          {
            "month": "2029-02",
            "date": "2029-02-28",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "403857.57",
              "scenario": "401190.87",
              "delta": "-2666.70"
            }
          },
          {
            "month": "2029-03",
            "date": "2029-03-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "406279.05",
              "scenario": "403603.47",
              "delta": "-2675.59"
            }
          },
          {
            "month": "2029-04",
            "date": "2029-04-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "408709.20",
              "scenario": "406024.70",
              "delta": "-2684.51"
            }
          },
          {
            "month": "2029-05",
            "date": "2029-05-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "411148.05",
              "scenario": "408454.60",
              "delta": "-2693.45"
            }
          },
          {
            "month": "2029-06",
            "date": "2029-06-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "413595.36",
              "scenario": "410892.93",
              "delta": "-2702.43"
            }
          },
          {
            "month": "2029-07",
            "date": "2029-07-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "416050.87",
              "scenario": "413339.43",
              "delta": "-2711.44"
            }
          },
          {
            "month": "2029-08",
            "date": "2029-08-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "418514.60",
              "scenario": "415794.12",
              "delta": "-2720.48"
            }
          },
          {
            "month": "2029-09",
            "date": "2029-09-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "420986.59",
              "scenario": "418257.04",
              "delta": "-2729.55"
            }
          },
          {
            "month": "2029-10",
            "date": "2029-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "423466.86",
              "scenario": "420728.22",
              "delta": "-2738.64"
            }
          },
          {
            "month": "2029-11",
            "date": "2029-11-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "425955.44",
              "scenario": "423207.67",
              "delta": "-2747.77"
            }
          },
          {
            "month": "2029-12",
            "date": "2029-12-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "428452.37",
              "scenario": "425695.44",
              "delta": "-2756.93"
            }
          },
          {
            "month": "2030-01",
            "date": "2030-01-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "430957.66",
              "scenario": "428191.54",
              "delta": "-2766.12"
            }
          },
          {
            "month": "2030-02",
            "date": "2030-02-28",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "433471.35",
              "scenario": "430696.00",
              "delta": "-2775.34"
            }
          },
          {
            "month": "2030-03",
            "date": "2030-03-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "435993.46",
              "scenario": "433208.86",
              "delta": "-2784.59"
            }
          },
          {
            "month": "2030-04",
            "date": "2030-04-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "438524.01",
              "scenario": "435730.14",
              "delta": "-2793.88"
            }
          },
          {
            "month": "2030-05",
            "date": "2030-05-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "441063.05",
              "scenario": "438259.86",
              "delta": "-2803.19"
            }
          },
          {
            "month": "2030-06",
            "date": "2030-06-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "443610.59",
              "scenario": "440798.06",
              "delta": "-2812.53"
            }
          },
          {
            "month": "2030-07",
            "date": "2030-07-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "446166.67",
              "scenario": "443344.76",
              "delta": "-2821.91"
            }
          },
          {
            "month": "2030-08",
            "date": "2030-08-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "448731.31",
              "scenario": "445899.99",
              "delta": "-2831.31"
            }
          },
          {
            "month": "2030-09",
            "date": "2030-09-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "451304.54",
              "scenario": "448463.79",
              "delta": "-2840.75"
            }
          },
          {
            "month": "2030-10",
            "date": "2030-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "453886.40",
              "scenario": "451036.18",
              "delta": "-2850.22"
            }
          },
          {
            "month": "2030-11",
            "date": "2030-11-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "456476.90",
              "scenario": "453617.18",
              "delta": "-2859.72"
            }
          },
          {
            "month": "2030-12",
            "date": "2030-12-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "459076.09",
              "scenario": "456206.84",
              "delta": "-2869.25"
            }
          },
          {
            "month": "2031-01",
            "date": "2031-01-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "461683.99",
              "scenario": "458805.17",
              "delta": "-2878.82"
            }
          },
          {
            "month": "2031-02",
            "date": "2031-02-28",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "464300.62",
              "scenario": "461412.21",
              "delta": "-2888.41"
            }
          },
          {
            "month": "2031-03",
            "date": "2031-03-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "466926.03",
              "scenario": "464027.99",
              "delta": "-2898.04"
            }
          },
          {
            "month": "2031-04",
            "date": "2031-04-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "469560.23",
              "scenario": "466652.53",
              "delta": "-2907.70"
            }
          },
          {
            "month": "2031-05",
            "date": "2031-05-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "472203.26",
              "scenario": "469285.86",
              "delta": "-2917.40"
            }
          },
          {
            "month": "2031-06",
            "date": "2031-06-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "474855.14",
              "scenario": "471928.02",
              "delta": "-2927.12"
            }
          },
          {
            "month": "2031-07",
            "date": "2031-07-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "477515.91",
              "scenario": "474579.03",
              "delta": "-2936.88"
            }
          },
          {
            "month": "2031-08",
            "date": "2031-08-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "480185.58",
              "scenario": "477238.92",
              "delta": "-2946.67"
            }
          },
          {
            "month": "2031-09",
            "date": "2031-09-30",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "482864.21",
              "scenario": "479907.72",
              "delta": "-2956.49"
            }
          },
          {
            "month": "2031-10",
            "date": "2031-10-31",
            "cash": {
              "baseline": "15801.47",
              "scenario": "15801.47",
              "delta": "0.00"
            },
            "net_worth": {
              "baseline": "485551.81",
              "scenario": "482585.47",
              "delta": "-2966.34"
            }
          }
        ]
      }
    }
  ],
  "trade": [
    {
      "option": "Pay cash",
      "against": "Instalments",
      "gains": [
        {
          "figure": "monthly.1y.net_worth",
          "unit": "amount",
          "this": "363866.13",
          "other": "363738.21",
          "delta": "127.92"
        },
        {
          "figure": "monthly.1y.investments",
          "unit": "amount",
          "this": "63546.81",
          "other": "61225.33",
          "delta": "2321.48"
        },
        {
          "figure": "monthly.1y.debts",
          "unit": "amount",
          "this": "13082.15",
          "other": "13288.59",
          "delta": "-206.44"
        },
        {
          "figure": "monthly.5y.net_worth",
          "unit": "amount",
          "this": "483151.81",
          "other": "482585.47",
          "delta": "566.34"
        },
        {
          "figure": "monthly.5y.investments",
          "unit": "amount",
          "this": "171707.25",
          "other": "168740.91",
          "delta": "2966.34"
        },
        {
          "figure": "debts.total_interest",
          "unit": "amount",
          "this": "2009.25",
          "other": "2099.93",
          "delta": "-90.68"
        }
      ],
      "gives_up": [
        {
          "figure": "cash.lowest",
          "unit": "amount",
          "this": "11598.91",
          "other": "13821.01",
          "delta": "-2222.10"
        },
        {
          "figure": "resilience.lowest",
          "unit": "months_of_spending",
          "this": "6.11",
          "other": "7.28",
          "delta": "-1.17"
        },
        {
          "figure": "monthly.1y.cash",
          "unit": "amount",
          "this": "13401.47",
          "other": "15801.47",
          "delta": "-2400.00"
        },
        {
          "figure": "monthly.5y.cash",
          "unit": "amount",
          "this": "13401.47",
          "other": "15801.47",
          "delta": "-2400.00"
        }
      ]
    },
    {
      "option": "Instalments",
      "against": "Pay cash",
      "gains": [
        {
          "figure": "cash.lowest",
          "unit": "amount",
          "this": "13821.01",
          "other": "11598.91",
          "delta": "2222.10"
        },
        {
          "figure": "resilience.lowest",
          "unit": "months_of_spending",
          "this": "7.28",
          "other": "6.11",
          "delta": "1.17"
        },
        {
          "figure": "monthly.1y.cash",
          "unit": "amount",
          "this": "15801.47",
          "other": "13401.47",
          "delta": "2400.00"
        },
        {
          "figure": "monthly.5y.cash",
          "unit": "amount",
          "this": "15801.47",
          "other": "13401.47",
          "delta": "2400.00"
        }
      ],
      "gives_up": [
        {
          "figure": "monthly.1y.net_worth",
          "unit": "amount",
          "this": "363738.21",
          "other": "363866.13",
          "delta": "-127.92"
        },
        {
          "figure": "monthly.1y.investments",
          "unit": "amount",
          "this": "61225.33",
          "other": "63546.81",
          "delta": "-2321.48"
        },
        {
          "figure": "monthly.1y.debts",
          "unit": "amount",
          "this": "13288.59",
          "other": "13082.15",
          "delta": "206.44"
        },
        {
          "figure": "monthly.5y.net_worth",
          "unit": "amount",
          "this": "482585.47",
          "other": "483151.81",
          "delta": "-566.34"
        },
        {
          "figure": "monthly.5y.investments",
          "unit": "amount",
          "this": "168740.91",
          "other": "171707.25",
          "delta": "-2966.34"
        },
        {
          "figure": "debts.total_interest",
          "unit": "amount",
          "this": "2099.93",
          "other": "2009.25",
          "delta": "90.68"
        }
      ]
    }
  ],
  "sensitivity": {
    "real_returns": {
      "conservative": "0.02",
      "base": "0.04",
      "growth": "0.06"
    },
    "options": [
      {
        "option": "Pay cash",
        "conservative": {
          "net_worth": {
            "baseline": "475029.43",
            "scenario": "472629.43",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "161184.87",
            "scenario": "161184.87",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2048-01",
            "scenario": "2048-02",
            "delta_months": 1
          },
          "months_gained": -1
        },
        "base": {
          "net_worth": {
            "baseline": "485551.81",
            "scenario": "483151.81",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "171707.25",
            "scenario": "171707.25",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2044-08",
            "scenario": "2044-09",
            "delta_months": 1
          },
          "months_gained": -1
        },
        "growth": {
          "net_worth": {
            "baseline": "496953.13",
            "scenario": "494553.13",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "183108.57",
            "scenario": "183108.57",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2042-04",
            "scenario": "2042-04",
            "delta_months": 0
          },
          "months_gained": 0
        }
      },
      {
        "option": "Instalments",
        "conservative": {
          "net_worth": {
            "baseline": "475029.43",
            "scenario": "472311.15",
            "delta": "-2718.28"
          },
          "investments": {
            "baseline": "161184.87",
            "scenario": "158466.59",
            "delta": "-2718.28"
          },
          "fi_month": {
            "baseline": "2048-01",
            "scenario": "2048-02",
            "delta_months": 1
          },
          "months_gained": -1
        },
        "base": {
          "net_worth": {
            "baseline": "485551.81",
            "scenario": "482585.47",
            "delta": "-2966.34"
          },
          "investments": {
            "baseline": "171707.25",
            "scenario": "168740.91",
            "delta": "-2966.34"
          },
          "fi_month": {
            "baseline": "2044-08",
            "scenario": "2044-09",
            "delta_months": 1
          },
          "months_gained": -1
        },
        "growth": {
          "net_worth": {
            "baseline": "496953.13",
            "scenario": "493716.45",
            "delta": "-3236.68"
          },
          "investments": {
            "baseline": "183108.57",
            "scenario": "179871.89",
            "delta": "-3236.68"
          },
          "fi_month": {
            "baseline": "2042-04",
            "scenario": "2042-05",
            "delta_months": 1
          },
          "months_gained": -1
        }
      }
    ]
  },
  "break_evens": [
    {
      "kind": "loan_rate",
      "options": [
        "Instalments",
        "Pay cash"
      ],
      "option": "Instalments",
      "change": 1,
      "status": "none_in_range",
      "unit": "rate",
      "value": null,
      "low": "0",
      "high": "1",
      "ahead": "Pay cash",
      "says": "Pay cash ends the horizon with more net worth than Instalments at every loan rate from 0% to 100%."
    }
  ]
};

export const PRINCIPLES: PrincipleList = {
  "principles": [
    {
      "schema": "salli.principle/1",
      "id": "00002331-5a11-4000-8000-000000009009",
      "label": "Six months of essentials in cash",
      "check": "emergency_months >= 6",
      "account": null,
      "note": null,
      "version": 1,
      "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a",
      "author": "user",
      "agent": null,
      "status": "active",
      "created_at": "2026-10-11T10:00:00+00:00",
      "updated_at": "2026-10-11T10:00:00+00:00",
      "archived_at": null
    },
    {
      "schema": "salli.principle/1",
      "id": "00002333-5a11-4000-8000-000000009011",
      "label": "Checking above 5,000",
      "check": "account_lowest >= 5000",
      "account": "chk",
      "note": "The rent and the card come out of it.",
      "version": 1,
      "hash": "sha256:8cca43c951b264ef898bd2cdfbf10a78c0e4d2121d268685499c218b6434dd79",
      "author": "user",
      "agent": null,
      "status": "active",
      "created_at": "2026-10-11T10:00:00+00:00",
      "updated_at": "2026-10-11T10:00:00+00:00",
      "archived_at": null
    },
    {
      "schema": "salli.principle/1",
      "id": "00002335-5a11-4000-8000-000000009013",
      "label": "Clear debt above 7% before investing",
      "check": "max_debt_rate_while_investing <= 0.07",
      "account": null,
      "note": null,
      "version": 1,
      "hash": "sha256:65a71dc269ee5e33888c4c26f1f920d1d509d2b67c135e207d68b39cb28ada0c",
      "author": "user",
      "agent": null,
      "status": "archived",
      "created_at": "2026-10-11T10:00:00+00:00",
      "updated_at": "2026-10-11T10:00:00+00:00",
      "archived_at": "2026-10-11T10:00:00+00:00"
    }
  ]
};

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

/**
 * The principles in use, checked on the baseline alone.
 */
export const BASELINE_CHECK: PrinciplesCheck = {
  "as_of": "2026-10-11",
  "currency": "EUR",
  "principles": [
    {
      "id": "00002331-5a11-4000-8000-000000009009",
      "label": "Six months of essentials in cash",
      "check": "emergency_months >= 6",
      "account": null,
      "version": 1,
      "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
    },
    {
      "id": "00002333-5a11-4000-8000-000000009011",
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
        "principle_id": "00002331-5a11-4000-8000-000000009009",
        "label": "Six months of essentials in cash",
        "status": "keeps",
        "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
        "figures": {
          "emergency_months": "7.37"
        }
      },
      {
        "principle_id": "00002333-5a11-4000-8000-000000009011",
        "label": "Checking above 5,000",
        "status": "keeps",
        "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
        "figures": {
          "account_lowest": "6063.46"
        }
      }
    ]
  },
  "options": [],
  "placeholders": [
    "real_return",
    "safe_withdrawal_rate",
    "surplus_invested",
    "drawdown_horizon",
    "inflation"
  ],
  "data_as_of": "2026-10-09"
};

/**
 * The principles in use, checked on paying cash and on instalments.
 */
export const PRINCIPLE_CHECK: PrinciplesCheck = {
  "as_of": "2026-10-11",
  "currency": "EUR",
  "principles": [
    {
      "id": "00002331-5a11-4000-8000-000000009009",
      "label": "Six months of essentials in cash",
      "check": "emergency_months >= 6",
      "account": null,
      "version": 1,
      "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
    },
    {
      "id": "00002333-5a11-4000-8000-000000009011",
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
        "principle_id": "00002331-5a11-4000-8000-000000009009",
        "label": "Six months of essentials in cash",
        "status": "keeps",
        "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
        "figures": {
          "emergency_months": "7.37"
        }
      },
      {
        "principle_id": "00002333-5a11-4000-8000-000000009011",
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
          "principle_id": "00002331-5a11-4000-8000-000000009009",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 6.11.",
          "figures": {
            "emergency_months": "6.11"
          }
        },
        {
          "principle_id": "00002333-5a11-4000-8000-000000009011",
          "label": "Checking above 5,000",
          "status": "breaks",
          "reason": "account_lowest >= 5000 doesn't hold: account_lowest is 4883.77.",
          "figures": {
            "account_lowest": "4883.77"
          }
        }
      ],
      "label": "Pay cash",
      "scenario_hash": "sha256:9b094ea3ce715a3e72c3351d3125a932f6182e9a6d202e422b1facc0787702e4"
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
          "principle_id": "00002331-5a11-4000-8000-000000009009",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 7.28.",
          "figures": {
            "emergency_months": "7.28"
          }
        },
        {
          "principle_id": "00002333-5a11-4000-8000-000000009011",
          "label": "Checking above 5,000",
          "status": "keeps",
          "reason": "account_lowest >= 5000 holds: account_lowest is 6063.46.",
          "figures": {
            "account_lowest": "6063.46"
          }
        }
      ],
      "label": "Instalments",
      "scenario_hash": "sha256:6ee0e3d2f4c5ccb067625dbdf7a6b9280101ec8c82458024f18dd70c8d710b0f"
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

export const DECISIONS: DecisionList = {
  "decisions": [
    {
      "id": "00002339-5a11-4000-8000-000000009017",
      "question": "Laptop: pay cash, spread it or wait?",
      "chosen": "Pay cash",
      "currency": "EUR",
      "as_of": "2026-10-11",
      "review_on": "2027-04-30",
      "recorded_at": "2026-10-11T10:00:00+00:00",
      "hash": "sha256:bbe9a3256c663ce1f948d87d2a4c155a74491f611221c4373b8c8c10952b8628",
      "notes": 1,
      "reviews": 0,
      "last_reviewed_at": null,
      "status": "awaiting_review"
    },
    {
      "id": "0000232e-5a11-4000-8000-000000009006",
      "question": "Change anything?",
      "chosen": "Keep as is",
      "currency": "EUR",
      "as_of": "2026-08-11",
      "review_on": "2026-09-30",
      "recorded_at": "2026-08-11T09:00:00+00:00",
      "hash": "sha256:89c4e9c86e53767f40162995b37ec28b9c9de1bddd6ef4682b11f0c0ed1efb1e",
      "notes": 0,
      "reviews": 0,
      "last_reviewed_at": null,
      "status": "review_due"
    }
  ]
};

/**
 * The laptop, with its note.
 */
export const DECISION: Decision = {
  "id": "00002339-5a11-4000-8000-000000009017",
  "hash": "sha256:bbe9a3256c663ce1f948d87d2a4c155a74491f611221c4373b8c8c10952b8628",
  "verified": true,
  "status": "awaiting_review",
  "entry": {
    "schema": "salli.decision/1",
    "id": "00002339-5a11-4000-8000-000000009017",
    "recorded_at": "2026-10-11T10:00:00+00:00",
    "recorded_via": {
      "channel": "api"
    },
    "question": "Laptop: pay cash, spread it or wait?",
    "as_of": "2026-10-11",
    "currency": "EUR",
    "basis": {
      "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
      "versions": {
        "schema": "salli.scenario/1",
        "engine": "4",
        "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
        "rule_sets": []
      },
      "assumptions": {
        "status": "placeholder",
        "headline_status": "placeholder",
        "headline": "Rests on placeholders for the real return, the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon"
        ],
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
      "placeholders": [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "drawdown_horizon",
        "inflation"
      ],
      "data_as_of": "2026-10-09",
      "is_stale": false
    },
    "principles": [
      {
        "id": "00002331-5a11-4000-8000-000000009009",
        "label": "Six months of essentials in cash",
        "check": "emergency_months >= 6",
        "account": null,
        "version": 1,
        "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
      },
      {
        "id": "00002333-5a11-4000-8000-000000009011",
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
      "principles": [
        {
          "principle_id": "00002331-5a11-4000-8000-000000009009",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
          "figures": {
            "emergency_months": "7.37"
          }
        },
        {
          "principle_id": "00002333-5a11-4000-8000-000000009011",
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
          "horizon_years": 5,
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
        "scenario_hash": "sha256:9b094ea3ce715a3e72c3351d3125a932f6182e9a6d202e422b1facc0787702e4",
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
        "principles": [
          {
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 6.11.",
            "figures": {
              "emergency_months": "6.11"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
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
          },
          {
            "month": "2027-01",
            "date": "2027-01-31",
            "cash": "13401.47",
            "investments": "46963.71",
            "owed": "16720.55",
            "net_worth": "343644.63",
            "spending": "2037.09"
          },
          {
            "month": "2027-02",
            "date": "2027-02-28",
            "cash": "13401.47",
            "investments": "48781.85",
            "owed": "16323.74",
            "net_worth": "345859.58",
            "spending": "2037.09"
          },
          {
            "month": "2027-03",
            "date": "2027-03-31",
            "cash": "13401.47",
            "investments": "50606.04",
            "owed": "15925.09",
            "net_worth": "348082.42",
            "spending": "2037.09"
          },
          {
            "month": "2027-04",
            "date": "2027-04-30",
            "cash": "13401.47",
            "investments": "52436.32",
            "owed": "15524.58",
            "net_worth": "350313.21",
            "spending": "2037.09"
          },
          {
            "month": "2027-05",
            "date": "2027-05-31",
            "cash": "13401.47",
            "investments": "54272.70",
            "owed": "15122.22",
            "net_worth": "352551.95",
            "spending": "2037.09"
          },
          {
            "month": "2027-06",
            "date": "2027-06-30",
            "cash": "13401.47",
            "investments": "56115.20",
            "owed": "14717.98",
            "net_worth": "354798.69",
            "spending": "2037.09"
          },
          {
            "month": "2027-07",
            "date": "2027-07-31",
            "cash": "13401.47",
            "investments": "57963.84",
            "owed": "14311.86",
            "net_worth": "357053.45",
            "spending": "2037.09"
          },
          {
            "month": "2027-08",
            "date": "2027-08-31",
            "cash": "13401.47",
            "investments": "59818.64",
            "owed": "13903.86",
            "net_worth": "359316.25",
            "spending": "2037.09"
          },
          {
            "month": "2027-09",
            "date": "2027-09-30",
            "cash": "13401.47",
            "investments": "61679.63",
            "owed": "13493.96",
            "net_worth": "361587.14",
            "spending": "2037.09"
          },
          {
            "month": "2027-10",
            "date": "2027-10-31",
            "cash": "13401.47",
            "investments": "63546.81",
            "owed": "13082.15",
            "net_worth": "363866.13",
            "spending": "2037.09"
          },
          {
            "month": "2027-11",
            "date": "2027-11-30",
            "cash": "13401.47",
            "investments": "65420.23",
            "owed": "12668.43",
            "net_worth": "366153.27",
            "spending": "2037.09"
          },
          {
            "month": "2027-12",
            "date": "2027-12-31",
            "cash": "13401.47",
            "investments": "67299.89",
            "owed": "12252.78",
            "net_worth": "368448.58",
            "spending": "2037.09"
          },
          {
            "month": "2028-01",
            "date": "2028-01-31",
            "cash": "13401.47",
            "investments": "69185.81",
            "owed": "11835.20",
            "net_worth": "370752.08",
            "spending": "2037.09"
          },
          {
            "month": "2028-02",
            "date": "2028-02-29",
            "cash": "13401.47",
            "investments": "71078.02",
            "owed": "11415.67",
            "net_worth": "373063.82",
            "spending": "2037.09"
          },
          {
            "month": "2028-03",
            "date": "2028-03-31",
            "cash": "13401.47",
            "investments": "72976.53",
            "owed": "10994.20",
            "net_worth": "375383.80",
            "spending": "2037.09"
          },
          {
            "month": "2028-04",
            "date": "2028-04-30",
            "cash": "13401.47",
            "investments": "74881.38",
            "owed": "10570.76",
            "net_worth": "377712.09",
            "spending": "2037.09"
          }
        ],
        "notes": []
      },
      {
        "label": "Spread over 12 months",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Spread over 12 months",
          "as_of": "2026-10-11",
          "horizon_years": 5,
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
              "label": "Laptop, over 12 months"
            }
          ]
        },
        "scenario_hash": "sha256:65aea5213bff9c2365ddf72f441301d3eebd8e577b5afbaa316f4a26e6f28a00",
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
        "principles": [
          {
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.28.",
            "figures": {
              "emergency_months": "7.28"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
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
          },
          {
            "month": "2027-01",
            "date": "2027-01-31",
            "cash": "15801.47",
            "investments": "46547.92",
            "owed": "18731.94",
            "net_worth": "343617.45",
            "spending": "2037.09"
          },
          {
            "month": "2027-02",
            "date": "2027-02-28",
            "cash": "15801.47",
            "investments": "48157.12",
            "owed": "18139.15",
            "net_worth": "345819.44",
            "spending": "2037.09"
          },
          {
            "month": "2027-03",
            "date": "2027-03-31",
            "cash": "15801.47",
            "investments": "49771.68",
            "owed": "17543.39",
            "net_worth": "348029.76",
            "spending": "2037.09"
          },
          {
            "month": "2027-04",
            "date": "2027-04-30",
            "cash": "15801.47",
            "investments": "51391.63",
            "owed": "16944.64",
            "net_worth": "350248.46",
            "spending": "2037.09"
          },
          {
            "month": "2027-05",
            "date": "2027-05-31",
            "cash": "15801.47",
            "investments": "53016.97",
            "owed": "16342.90",
            "net_worth": "352475.54",
            "spending": "2037.09"
          },
          {
            "month": "2027-06",
            "date": "2027-06-30",
            "cash": "15801.47",
            "investments": "54647.74",
            "owed": "15738.13",
            "net_worth": "354711.08",
            "spending": "2037.09"
          },
          {
            "month": "2027-07",
            "date": "2027-07-31",
            "cash": "15801.47",
            "investments": "56283.94",
            "owed": "15130.33",
            "net_worth": "356955.08",
            "spending": "2037.09"
          },
          {
            "month": "2027-08",
            "date": "2027-08-31",
            "cash": "15801.47",
            "investments": "57925.59",
            "owed": "14519.49",
            "net_worth": "359207.57",
            "spending": "2037.09"
          },
          {
            "month": "2027-09",
            "date": "2027-09-30",
            "cash": "15801.47",
            "investments": "59572.72",
            "owed": "13905.58",
            "net_worth": "361468.61",
            "spending": "2037.09"
          },
          {
            "month": "2027-10",
            "date": "2027-10-31",
            "cash": "15801.47",
            "investments": "61225.33",
            "owed": "13288.59",
            "net_worth": "363738.21",
            "spending": "2037.09"
          },
          {
            "month": "2027-11",
            "date": "2027-11-30",
            "cash": "15801.47",
            "investments": "62883.38",
            "owed": "12668.43",
            "net_worth": "366016.42",
            "spending": "2037.09"
          },
          {
            "month": "2027-12",
            "date": "2027-12-31",
            "cash": "15801.47",
            "investments": "64754.58",
            "owed": "12252.78",
            "net_worth": "368303.27",
            "spending": "2037.09"
          },
          {
            "month": "2028-01",
            "date": "2028-01-31",
            "cash": "15801.47",
            "investments": "66632.02",
            "owed": "11835.20",
            "net_worth": "370598.29",
            "spending": "2037.09"
          },
          {
            "month": "2028-02",
            "date": "2028-02-29",
            "cash": "15801.47",
            "investments": "68515.71",
            "owed": "11415.67",
            "net_worth": "372901.51",
            "spending": "2037.09"
          },
          {
            "month": "2028-03",
            "date": "2028-03-31",
            "cash": "15801.47",
            "investments": "70405.69",
            "owed": "10994.20",
            "net_worth": "375212.96",
            "spending": "2037.09"
          },
          {
            "month": "2028-04",
            "date": "2028-04-30",
            "cash": "15801.47",
            "investments": "72301.96",
            "owed": "10570.76",
            "net_worth": "377532.67",
            "spending": "2037.09"
          }
        ],
        "notes": []
      },
      {
        "label": "Wait 6 months",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Wait 6 months",
          "as_of": "2026-10-11",
          "horizon_years": 5,
          "changes": [
            {
              "type": "set_aside",
              "monthly": "400.00",
              "from": "2026-11-02",
              "to": "2027-04-30",
              "label": "Saving for Laptop"
            },
            {
              "type": "one_off",
              "date": "2027-05-02",
              "amount": "-2400.00",
              "account": "chk",
              "label": "Laptop"
            }
          ]
        },
        "scenario_hash": "sha256:54f663454d40513a0b7efa5cbf3f89feb77e7b9ca2e20370ac312603d0e27dcd",
        "figures": {
          "lowest_cash": "14013.25",
          "cash_in_12_months": "15801.47",
          "safe_to_spend": "15316.35",
          "any_account_below_zero": false,
          "monthly_spending": "1898.32",
          "emergency_months": "7.38",
          "emergency_months_in_12_months": "8.32",
          "net_worth_1y": "363797.24",
          "net_worth_5y": "482655.31",
          "net_worth_10y": "660842.88",
          "net_worth_20y": "1144076.69",
          "cash_1y": "15801.47",
          "cash_5y": "15801.47",
          "cash_10y": "15801.47",
          "cash_20y": "15801.47",
          "investments_1y": "61077.92",
          "investments_5y": "168810.75",
          "investments_10y": "345041.41",
          "investments_20y": "828275.22",
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
        "principles": [
          {
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.38.",
            "figures": {
              "emergency_months": "7.38"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
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
            "cash": "16201.47",
            "investments": "42945.54",
            "owed": "17508.68",
            "net_worth": "341638.33",
            "spending": "2037.09"
          },
          {
            "month": "2026-12",
            "date": "2026-12-31",
            "cash": "16601.47",
            "investments": "44350.28",
            "owed": "17115.53",
            "net_worth": "343836.22",
            "spending": "2037.09"
          },
          {
            "month": "2027-01",
            "date": "2027-01-31",
            "cash": "17001.47",
            "investments": "45759.71",
            "owed": "16720.55",
            "net_worth": "346040.63",
            "spending": "2037.09"
          },
          {
            "month": "2027-02",
            "date": "2027-02-28",
            "cash": "17401.47",
            "investments": "47173.83",
            "owed": "16323.74",
            "net_worth": "348251.56",
            "spending": "2037.09"
          },
          {
            "month": "2027-03",
            "date": "2027-03-31",
            "cash": "17801.47",
            "investments": "48592.67",
            "owed": "15925.09",
            "net_worth": "350469.05",
            "spending": "2037.09"
          },
          {
            "month": "2027-04",
            "date": "2027-04-30",
            "cash": "18201.47",
            "investments": "50016.23",
            "owed": "15524.58",
            "net_worth": "352693.12",
            "spending": "2037.09"
          },
          {
            "month": "2027-05",
            "date": "2027-05-31",
            "cash": "15801.47",
            "investments": "51844.54",
            "owed": "15122.22",
            "net_worth": "352523.79",
            "spending": "2037.09"
          },
          {
            "month": "2027-06",
            "date": "2027-06-30",
            "cash": "15801.47",
            "investments": "53678.95",
            "owed": "14717.98",
            "net_worth": "354762.44",
            "spending": "2037.09"
          },
          {
            "month": "2027-07",
            "date": "2027-07-31",
            "cash": "15801.47",
            "investments": "55519.47",
            "owed": "14311.86",
            "net_worth": "357009.08",
            "spending": "2037.09"
          },
          {
            "month": "2027-08",
            "date": "2027-08-31",
            "cash": "15801.47",
            "investments": "57366.12",
            "owed": "13903.86",
            "net_worth": "359263.73",
            "spending": "2037.09"
          },
          {
            "month": "2027-09",
            "date": "2027-09-30",
            "cash": "15801.47",
            "investments": "59218.93",
            "owed": "13493.96",
            "net_worth": "361526.44",
            "spending": "2037.09"
          },
          {
            "month": "2027-10",
            "date": "2027-10-31",
            "cash": "15801.47",
            "investments": "61077.92",
            "owed": "13082.15",
            "net_worth": "363797.24",
            "spending": "2037.09"
          },
          {
            "month": "2027-11",
            "date": "2027-11-30",
            "cash": "15801.47",
            "investments": "62943.10",
            "owed": "12668.43",
            "net_worth": "366076.14",
            "spending": "2037.09"
          },
          {
            "month": "2027-12",
            "date": "2027-12-31",
            "cash": "15801.47",
            "investments": "64814.50",
            "owed": "12252.78",
            "net_worth": "368363.19",
            "spending": "2037.09"
          },
          {
            "month": "2028-01",
            "date": "2028-01-31",
            "cash": "15801.47",
            "investments": "66692.14",
            "owed": "11835.20",
            "net_worth": "370658.41",
            "spending": "2037.09"
          },
          {
            "month": "2028-02",
            "date": "2028-02-29",
            "cash": "15801.47",
            "investments": "68576.04",
            "owed": "11415.67",
            "net_worth": "372961.84",
            "spending": "2037.09"
          },
          {
            "month": "2028-03",
            "date": "2028-03-31",
            "cash": "15801.47",
            "investments": "70466.21",
            "owed": "10994.20",
            "net_worth": "375273.48",
            "spending": "2037.09"
          },
          {
            "month": "2028-04",
            "date": "2028-04-30",
            "cash": "15801.47",
            "investments": "72362.69",
            "owed": "10570.76",
            "net_worth": "377593.40",
            "spending": "2037.09"
          }
        ],
        "notes": []
      }
    ],
    "chosen": "Pay cash",
    "reasons": "The old one is failing, and I would rather not owe anything.",
    "agent_summary": null,
    "review_on": "2027-04-30"
  },
  "notes": [
    {
      "note": {
        "schema": "salli.decision-note/1",
        "id": "0000233c-5a11-4000-8000-000000009020",
        "decision_id": "00002339-5a11-4000-8000-000000009017",
        "entry_hash": "sha256:bbe9a3256c663ce1f948d87d2a4c155a74491f611221c4373b8c8c10952b8628",
        "at": "2026-10-11T10:00:00+00:00",
        "text": "The shop held the price until November.",
        "author": "user",
        "agent": null
      },
      "hash": "sha256:fc92b5344d4a0407fb74750291e9dd78c98ad12434b4b222c9c20a7bcfb7096f",
      "verified": true
    }
  ],
  "reviews": []
};

/**
 * The August decision, due for review.
 */
export const DECISION_DUE: Decision = {
  "id": "0000232e-5a11-4000-8000-000000009006",
  "hash": "sha256:89c4e9c86e53767f40162995b37ec28b9c9de1bddd6ef4682b11f0c0ed1efb1e",
  "verified": true,
  "status": "review_due",
  "entry": {
    "schema": "salli.decision/1",
    "id": "0000232e-5a11-4000-8000-000000009006",
    "recorded_at": "2026-08-11T09:00:00+00:00",
    "recorded_via": {
      "channel": "api"
    },
    "question": "Change anything?",
    "as_of": "2026-08-11",
    "currency": "EUR",
    "basis": {
      "baseline_fingerprint": "sha256:6c039c9c7f41e2cc30a1b4516f69e3c5054a83e8563692d281b9f87fdd083fee",
      "versions": {
        "schema": "salli.scenario/1",
        "engine": "4",
        "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
        "rule_sets": []
      },
      "assumptions": {
        "status": "placeholder",
        "headline_status": "placeholder",
        "headline": "Rests on placeholders for the real return, the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon"
        ],
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
      "placeholders": [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "drawdown_horizon",
        "inflation"
      ],
      "data_as_of": "2026-08-09",
      "is_stale": false
    },
    "principles": [],
    "baseline": {
      "figures": {
        "lowest_cash": "9512.79",
        "cash_in_12_months": "11316.20",
        "safe_to_spend": "10826.46",
        "any_account_below_zero": false,
        "monthly_spending": "1897.48",
        "emergency_months": "5.01",
        "emergency_months_in_12_months": "5.96",
        "net_worth_1y": "360096.23",
        "net_worth_5y": "479060.97",
        "net_worth_10y": "657438.80",
        "net_worth_20y": "1141188.58",
        "cash_1y": "11316.20",
        "cash_5y": "11316.20",
        "cash_10y": "11316.20",
        "cash_20y": "11316.20",
        "investments_1y": "62498.54",
        "investments_5y": "169701.68",
        "investments_10y": "346122.60",
        "investments_20y": "829872.38",
        "debts_1y": "13718.51",
        "debts_5y": "1956.91",
        "debts_10y": "0.00",
        "debts_20y": "0.00",
        "total_interest": "2111.31",
        "debt_free_months": 77,
        "max_debt_rate": "0.059",
        "max_debt_rate_while_investing": "0.059",
        "borrowed": "0.00",
        "fi_number": "714080.25",
        "fi_months": 216,
        "fi_months_gained": 0,
        "tax_change_this_year": "0.00"
      },
      "unavailable": {},
      "principles": []
    },
    "options": [
      {
        "label": "Keep as is",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Keep as is",
          "as_of": "2026-08-11",
          "horizon_years": 20,
          "changes": []
        },
        "scenario_hash": "sha256:261f716d1eec826e987eec2e389236965848996fa2bf245b3a48707e7015b597",
        "figures": {
          "lowest_cash": "9512.79",
          "cash_in_12_months": "11316.20",
          "safe_to_spend": "10826.46",
          "any_account_below_zero": false,
          "monthly_spending": "1897.48",
          "emergency_months": "5.01",
          "emergency_months_in_12_months": "5.96",
          "net_worth_1y": "360096.23",
          "net_worth_5y": "479060.97",
          "net_worth_10y": "657438.80",
          "net_worth_20y": "1141188.58",
          "cash_1y": "11316.20",
          "cash_5y": "11316.20",
          "cash_10y": "11316.20",
          "cash_20y": "11316.20",
          "investments_1y": "62498.54",
          "investments_5y": "169701.68",
          "investments_10y": "346122.60",
          "investments_20y": "829872.38",
          "debts_1y": "13718.51",
          "debts_5y": "1956.91",
          "debts_10y": "0.00",
          "debts_20y": "0.00",
          "total_interest": "2111.31",
          "debt_free_months": 77,
          "max_debt_rate": "0.059",
          "max_debt_rate_while_investing": "0.059",
          "borrowed": "0.00",
          "fi_number": "714080.25",
          "fi_months": 216,
          "fi_months_gained": 0,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "principles": [],
        "projection": [
          {
            "month": "2026-08",
            "date": "2026-08-11",
            "cash": "11316.20",
            "investments": "37000.00",
            "owed": "18500.00",
            "net_worth": "329816.20",
            "spending": null
          },
          {
            "month": "2026-08",
            "date": "2026-08-31",
            "cash": "11316.20",
            "investments": "40539.40",
            "owed": "18500.00",
            "net_worth": "333355.60",
            "spending": null
          },
          {
            "month": "2026-09",
            "date": "2026-09-30",
            "cash": "11316.20",
            "investments": "42336.02",
            "owed": "18111.63",
            "net_worth": "335540.59",
            "spending": "2040.14"
          },
          {
            "month": "2026-10",
            "date": "2026-10-31",
            "cash": "11316.20",
            "investments": "44138.63",
            "owed": "17721.45",
            "net_worth": "337733.38",
            "spending": "2040.14"
          },
          {
            "month": "2026-11",
            "date": "2026-11-30",
            "cash": "11316.20",
            "investments": "45947.25",
            "owed": "17329.45",
            "net_worth": "339934.00",
            "spending": "2040.14"
          },
          {
            "month": "2026-12",
            "date": "2026-12-31",
            "cash": "11316.20",
            "investments": "47761.90",
            "owed": "16935.63",
            "net_worth": "342142.47",
            "spending": "2040.14"
          },
          {
            "month": "2027-01",
            "date": "2027-01-31",
            "cash": "11316.20",
            "investments": "49582.59",
            "owed": "16539.98",
            "net_worth": "344358.81",
            "spending": "2040.14"
          },
          {
            "month": "2027-02",
            "date": "2027-02-28",
            "cash": "11316.20",
            "investments": "51409.36",
            "owed": "16142.50",
            "net_worth": "346583.06",
            "spending": "2040.14"
          },
          {
            "month": "2027-03",
            "date": "2027-03-31",
            "cash": "11316.20",
            "investments": "53242.21",
            "owed": "15743.17",
            "net_worth": "348815.24",
            "spending": "2040.14"
          },
          {
            "month": "2027-04",
            "date": "2027-04-30",
            "cash": "11316.20",
            "investments": "55081.18",
            "owed": "15341.98",
            "net_worth": "351055.40",
            "spending": "2040.14"
          },
          {
            "month": "2027-05",
            "date": "2027-05-31",
            "cash": "11316.20",
            "investments": "56926.27",
            "owed": "14938.92",
            "net_worth": "353303.55",
            "spending": "2040.14"
          },
          {
            "month": "2027-06",
            "date": "2027-06-30",
            "cash": "11316.20",
            "investments": "58777.51",
            "owed": "14534.00",
            "net_worth": "355559.71",
            "spending": "2040.14"
          },
          {
            "month": "2027-07",
            "date": "2027-07-31",
            "cash": "11316.20",
            "investments": "60634.93",
            "owed": "14127.20",
            "net_worth": "357823.93",
            "spending": "2040.14"
          },
          {
            "month": "2027-08",
            "date": "2027-08-31",
            "cash": "11316.20",
            "investments": "62498.54",
            "owed": "13718.51",
            "net_worth": "360096.23",
            "spending": "2040.14"
          },
          {
            "month": "2027-09",
            "date": "2027-09-30",
            "cash": "11316.20",
            "investments": "64368.35",
            "owed": "13307.92",
            "net_worth": "362376.63",
            "spending": "2040.14"
          }
        ],
        "notes": [
          "Dollar account: no published USD rate for 2026-08-11, so it is left out of the totals in EUR"
        ]
      }
    ],
    "chosen": "Keep as is",
    "reasons": "It works.",
    "agent_summary": null,
    "review_on": "2026-09-30"
  },
  "notes": [],
  "reviews": []
};

export const JOURNAL: DecisionJournal = {
  "schema": "salli.decision-journal/1",
  "exported_at": "2026-10-11T10:00:00+00:00",
  "verify": "Each hash is the SHA-256 of the document's canonical JSON: keys sorted, no whitespace, ASCII only (non-ASCII as \\u escapes), numbers as decimal strings. Recompute it over `entry` (or `note`, `review`) and compare.",
  "entries": [
    {
      "entry": {
        "schema": "salli.decision/1",
        "id": "0000232e-5a11-4000-8000-000000009006",
        "recorded_at": "2026-08-11T09:00:00+00:00",
        "recorded_via": {
          "channel": "api"
        },
        "question": "Change anything?",
        "as_of": "2026-08-11",
        "currency": "EUR",
        "basis": {
          "baseline_fingerprint": "sha256:6c039c9c7f41e2cc30a1b4516f69e3c5054a83e8563692d281b9f87fdd083fee",
          "versions": {
            "schema": "salli.scenario/1",
            "engine": "4",
            "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
            "rule_sets": []
          },
          "assumptions": {
            "status": "placeholder",
            "headline_status": "placeholder",
            "headline": "Rests on placeholders for the real return, the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
            "placeholders": [
              "real_return",
              "safe_withdrawal_rate",
              "surplus_invested",
              "drawdown_horizon"
            ],
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
          "placeholders": [
            "real_return",
            "safe_withdrawal_rate",
            "surplus_invested",
            "drawdown_horizon",
            "inflation"
          ],
          "data_as_of": "2026-08-09",
          "is_stale": false
        },
        "principles": [],
        "baseline": {
          "figures": {
            "lowest_cash": "9512.79",
            "cash_in_12_months": "11316.20",
            "safe_to_spend": "10826.46",
            "any_account_below_zero": false,
            "monthly_spending": "1897.48",
            "emergency_months": "5.01",
            "emergency_months_in_12_months": "5.96",
            "net_worth_1y": "360096.23",
            "net_worth_5y": "479060.97",
            "net_worth_10y": "657438.80",
            "net_worth_20y": "1141188.58",
            "cash_1y": "11316.20",
            "cash_5y": "11316.20",
            "cash_10y": "11316.20",
            "cash_20y": "11316.20",
            "investments_1y": "62498.54",
            "investments_5y": "169701.68",
            "investments_10y": "346122.60",
            "investments_20y": "829872.38",
            "debts_1y": "13718.51",
            "debts_5y": "1956.91",
            "debts_10y": "0.00",
            "debts_20y": "0.00",
            "total_interest": "2111.31",
            "debt_free_months": 77,
            "max_debt_rate": "0.059",
            "max_debt_rate_while_investing": "0.059",
            "borrowed": "0.00",
            "fi_number": "714080.25",
            "fi_months": 216,
            "fi_months_gained": 0,
            "tax_change_this_year": "0.00"
          },
          "unavailable": {},
          "principles": []
        },
        "options": [
          {
            "label": "Keep as is",
            "scenario": {
              "schema": "salli.scenario/1",
              "label": "Keep as is",
              "as_of": "2026-08-11",
              "horizon_years": 20,
              "changes": []
            },
            "scenario_hash": "sha256:261f716d1eec826e987eec2e389236965848996fa2bf245b3a48707e7015b597",
            "figures": {
              "lowest_cash": "9512.79",
              "cash_in_12_months": "11316.20",
              "safe_to_spend": "10826.46",
              "any_account_below_zero": false,
              "monthly_spending": "1897.48",
              "emergency_months": "5.01",
              "emergency_months_in_12_months": "5.96",
              "net_worth_1y": "360096.23",
              "net_worth_5y": "479060.97",
              "net_worth_10y": "657438.80",
              "net_worth_20y": "1141188.58",
              "cash_1y": "11316.20",
              "cash_5y": "11316.20",
              "cash_10y": "11316.20",
              "cash_20y": "11316.20",
              "investments_1y": "62498.54",
              "investments_5y": "169701.68",
              "investments_10y": "346122.60",
              "investments_20y": "829872.38",
              "debts_1y": "13718.51",
              "debts_5y": "1956.91",
              "debts_10y": "0.00",
              "debts_20y": "0.00",
              "total_interest": "2111.31",
              "debt_free_months": 77,
              "max_debt_rate": "0.059",
              "max_debt_rate_while_investing": "0.059",
              "borrowed": "0.00",
              "fi_number": "714080.25",
              "fi_months": 216,
              "fi_months_gained": 0,
              "tax_change_this_year": "0.00"
            },
            "unavailable": {},
            "principles": [],
            "projection": [
              {
                "month": "2026-08",
                "date": "2026-08-11",
                "cash": "11316.20",
                "investments": "37000.00",
                "owed": "18500.00",
                "net_worth": "329816.20",
                "spending": null
              },
              {
                "month": "2026-08",
                "date": "2026-08-31",
                "cash": "11316.20",
                "investments": "40539.40",
                "owed": "18500.00",
                "net_worth": "333355.60",
                "spending": null
              },
              {
                "month": "2026-09",
                "date": "2026-09-30",
                "cash": "11316.20",
                "investments": "42336.02",
                "owed": "18111.63",
                "net_worth": "335540.59",
                "spending": "2040.14"
              },
              {
                "month": "2026-10",
                "date": "2026-10-31",
                "cash": "11316.20",
                "investments": "44138.63",
                "owed": "17721.45",
                "net_worth": "337733.38",
                "spending": "2040.14"
              },
              {
                "month": "2026-11",
                "date": "2026-11-30",
                "cash": "11316.20",
                "investments": "45947.25",
                "owed": "17329.45",
                "net_worth": "339934.00",
                "spending": "2040.14"
              },
              {
                "month": "2026-12",
                "date": "2026-12-31",
                "cash": "11316.20",
                "investments": "47761.90",
                "owed": "16935.63",
                "net_worth": "342142.47",
                "spending": "2040.14"
              },
              {
                "month": "2027-01",
                "date": "2027-01-31",
                "cash": "11316.20",
                "investments": "49582.59",
                "owed": "16539.98",
                "net_worth": "344358.81",
                "spending": "2040.14"
              },
              {
                "month": "2027-02",
                "date": "2027-02-28",
                "cash": "11316.20",
                "investments": "51409.36",
                "owed": "16142.50",
                "net_worth": "346583.06",
                "spending": "2040.14"
              },
              {
                "month": "2027-03",
                "date": "2027-03-31",
                "cash": "11316.20",
                "investments": "53242.21",
                "owed": "15743.17",
                "net_worth": "348815.24",
                "spending": "2040.14"
              },
              {
                "month": "2027-04",
                "date": "2027-04-30",
                "cash": "11316.20",
                "investments": "55081.18",
                "owed": "15341.98",
                "net_worth": "351055.40",
                "spending": "2040.14"
              },
              {
                "month": "2027-05",
                "date": "2027-05-31",
                "cash": "11316.20",
                "investments": "56926.27",
                "owed": "14938.92",
                "net_worth": "353303.55",
                "spending": "2040.14"
              },
              {
                "month": "2027-06",
                "date": "2027-06-30",
                "cash": "11316.20",
                "investments": "58777.51",
                "owed": "14534.00",
                "net_worth": "355559.71",
                "spending": "2040.14"
              },
              {
                "month": "2027-07",
                "date": "2027-07-31",
                "cash": "11316.20",
                "investments": "60634.93",
                "owed": "14127.20",
                "net_worth": "357823.93",
                "spending": "2040.14"
              },
              {
                "month": "2027-08",
                "date": "2027-08-31",
                "cash": "11316.20",
                "investments": "62498.54",
                "owed": "13718.51",
                "net_worth": "360096.23",
                "spending": "2040.14"
              },
              {
                "month": "2027-09",
                "date": "2027-09-30",
                "cash": "11316.20",
                "investments": "64368.35",
                "owed": "13307.92",
                "net_worth": "362376.63",
                "spending": "2040.14"
              }
            ],
            "notes": [
              "Dollar account: no published USD rate for 2026-08-11, so it is left out of the totals in EUR"
            ]
          }
        ],
        "chosen": "Keep as is",
        "reasons": "It works.",
        "agent_summary": null,
        "review_on": "2026-09-30"
      },
      "hash": "sha256:89c4e9c86e53767f40162995b37ec28b9c9de1bddd6ef4682b11f0c0ed1efb1e",
      "notes": [],
      "reviews": []
    },
    {
      "entry": {
        "schema": "salli.decision/1",
        "id": "00002339-5a11-4000-8000-000000009017",
        "recorded_at": "2026-10-11T10:00:00+00:00",
        "recorded_via": {
          "channel": "api"
        },
        "question": "Laptop: pay cash, spread it or wait?",
        "as_of": "2026-10-11",
        "currency": "EUR",
        "basis": {
          "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
          "versions": {
            "schema": "salli.scenario/1",
            "engine": "4",
            "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
            "rule_sets": []
          },
          "assumptions": {
            "status": "placeholder",
            "headline_status": "placeholder",
            "headline": "Rests on placeholders for the real return, the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
            "placeholders": [
              "real_return",
              "safe_withdrawal_rate",
              "surplus_invested",
              "drawdown_horizon"
            ],
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
          "placeholders": [
            "real_return",
            "safe_withdrawal_rate",
            "surplus_invested",
            "drawdown_horizon",
            "inflation"
          ],
          "data_as_of": "2026-10-09",
          "is_stale": false
        },
        "principles": [
          {
            "id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "check": "emergency_months >= 6",
            "account": null,
            "version": 1,
            "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
          },
          {
            "id": "00002333-5a11-4000-8000-000000009011",
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
          "principles": [
            {
              "principle_id": "00002331-5a11-4000-8000-000000009009",
              "label": "Six months of essentials in cash",
              "status": "keeps",
              "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
              "figures": {
                "emergency_months": "7.37"
              }
            },
            {
              "principle_id": "00002333-5a11-4000-8000-000000009011",
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
              "horizon_years": 5,
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
            "scenario_hash": "sha256:9b094ea3ce715a3e72c3351d3125a932f6182e9a6d202e422b1facc0787702e4",
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
            "principles": [
              {
                "principle_id": "00002331-5a11-4000-8000-000000009009",
                "label": "Six months of essentials in cash",
                "status": "keeps",
                "reason": "emergency_months >= 6 holds: emergency_months is 6.11.",
                "figures": {
                  "emergency_months": "6.11"
                }
              },
              {
                "principle_id": "00002333-5a11-4000-8000-000000009011",
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
              },
              {
                "month": "2027-01",
                "date": "2027-01-31",
                "cash": "13401.47",
                "investments": "46963.71",
                "owed": "16720.55",
                "net_worth": "343644.63",
                "spending": "2037.09"
              },
              {
                "month": "2027-02",
                "date": "2027-02-28",
                "cash": "13401.47",
                "investments": "48781.85",
                "owed": "16323.74",
                "net_worth": "345859.58",
                "spending": "2037.09"
              },
              {
                "month": "2027-03",
                "date": "2027-03-31",
                "cash": "13401.47",
                "investments": "50606.04",
                "owed": "15925.09",
                "net_worth": "348082.42",
                "spending": "2037.09"
              },
              {
                "month": "2027-04",
                "date": "2027-04-30",
                "cash": "13401.47",
                "investments": "52436.32",
                "owed": "15524.58",
                "net_worth": "350313.21",
                "spending": "2037.09"
              },
              {
                "month": "2027-05",
                "date": "2027-05-31",
                "cash": "13401.47",
                "investments": "54272.70",
                "owed": "15122.22",
                "net_worth": "352551.95",
                "spending": "2037.09"
              },
              {
                "month": "2027-06",
                "date": "2027-06-30",
                "cash": "13401.47",
                "investments": "56115.20",
                "owed": "14717.98",
                "net_worth": "354798.69",
                "spending": "2037.09"
              },
              {
                "month": "2027-07",
                "date": "2027-07-31",
                "cash": "13401.47",
                "investments": "57963.84",
                "owed": "14311.86",
                "net_worth": "357053.45",
                "spending": "2037.09"
              },
              {
                "month": "2027-08",
                "date": "2027-08-31",
                "cash": "13401.47",
                "investments": "59818.64",
                "owed": "13903.86",
                "net_worth": "359316.25",
                "spending": "2037.09"
              },
              {
                "month": "2027-09",
                "date": "2027-09-30",
                "cash": "13401.47",
                "investments": "61679.63",
                "owed": "13493.96",
                "net_worth": "361587.14",
                "spending": "2037.09"
              },
              {
                "month": "2027-10",
                "date": "2027-10-31",
                "cash": "13401.47",
                "investments": "63546.81",
                "owed": "13082.15",
                "net_worth": "363866.13",
                "spending": "2037.09"
              },
              {
                "month": "2027-11",
                "date": "2027-11-30",
                "cash": "13401.47",
                "investments": "65420.23",
                "owed": "12668.43",
                "net_worth": "366153.27",
                "spending": "2037.09"
              },
              {
                "month": "2027-12",
                "date": "2027-12-31",
                "cash": "13401.47",
                "investments": "67299.89",
                "owed": "12252.78",
                "net_worth": "368448.58",
                "spending": "2037.09"
              },
              {
                "month": "2028-01",
                "date": "2028-01-31",
                "cash": "13401.47",
                "investments": "69185.81",
                "owed": "11835.20",
                "net_worth": "370752.08",
                "spending": "2037.09"
              },
              {
                "month": "2028-02",
                "date": "2028-02-29",
                "cash": "13401.47",
                "investments": "71078.02",
                "owed": "11415.67",
                "net_worth": "373063.82",
                "spending": "2037.09"
              },
              {
                "month": "2028-03",
                "date": "2028-03-31",
                "cash": "13401.47",
                "investments": "72976.53",
                "owed": "10994.20",
                "net_worth": "375383.80",
                "spending": "2037.09"
              },
              {
                "month": "2028-04",
                "date": "2028-04-30",
                "cash": "13401.47",
                "investments": "74881.38",
                "owed": "10570.76",
                "net_worth": "377712.09",
                "spending": "2037.09"
              }
            ],
            "notes": []
          },
          {
            "label": "Spread over 12 months",
            "scenario": {
              "schema": "salli.scenario/1",
              "label": "Spread over 12 months",
              "as_of": "2026-10-11",
              "horizon_years": 5,
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
                  "label": "Laptop, over 12 months"
                }
              ]
            },
            "scenario_hash": "sha256:65aea5213bff9c2365ddf72f441301d3eebd8e577b5afbaa316f4a26e6f28a00",
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
            "principles": [
              {
                "principle_id": "00002331-5a11-4000-8000-000000009009",
                "label": "Six months of essentials in cash",
                "status": "keeps",
                "reason": "emergency_months >= 6 holds: emergency_months is 7.28.",
                "figures": {
                  "emergency_months": "7.28"
                }
              },
              {
                "principle_id": "00002333-5a11-4000-8000-000000009011",
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
              },
              {
                "month": "2027-01",
                "date": "2027-01-31",
                "cash": "15801.47",
                "investments": "46547.92",
                "owed": "18731.94",
                "net_worth": "343617.45",
                "spending": "2037.09"
              },
              {
                "month": "2027-02",
                "date": "2027-02-28",
                "cash": "15801.47",
                "investments": "48157.12",
                "owed": "18139.15",
                "net_worth": "345819.44",
                "spending": "2037.09"
              },
              {
                "month": "2027-03",
                "date": "2027-03-31",
                "cash": "15801.47",
                "investments": "49771.68",
                "owed": "17543.39",
                "net_worth": "348029.76",
                "spending": "2037.09"
              },
              {
                "month": "2027-04",
                "date": "2027-04-30",
                "cash": "15801.47",
                "investments": "51391.63",
                "owed": "16944.64",
                "net_worth": "350248.46",
                "spending": "2037.09"
              },
              {
                "month": "2027-05",
                "date": "2027-05-31",
                "cash": "15801.47",
                "investments": "53016.97",
                "owed": "16342.90",
                "net_worth": "352475.54",
                "spending": "2037.09"
              },
              {
                "month": "2027-06",
                "date": "2027-06-30",
                "cash": "15801.47",
                "investments": "54647.74",
                "owed": "15738.13",
                "net_worth": "354711.08",
                "spending": "2037.09"
              },
              {
                "month": "2027-07",
                "date": "2027-07-31",
                "cash": "15801.47",
                "investments": "56283.94",
                "owed": "15130.33",
                "net_worth": "356955.08",
                "spending": "2037.09"
              },
              {
                "month": "2027-08",
                "date": "2027-08-31",
                "cash": "15801.47",
                "investments": "57925.59",
                "owed": "14519.49",
                "net_worth": "359207.57",
                "spending": "2037.09"
              },
              {
                "month": "2027-09",
                "date": "2027-09-30",
                "cash": "15801.47",
                "investments": "59572.72",
                "owed": "13905.58",
                "net_worth": "361468.61",
                "spending": "2037.09"
              },
              {
                "month": "2027-10",
                "date": "2027-10-31",
                "cash": "15801.47",
                "investments": "61225.33",
                "owed": "13288.59",
                "net_worth": "363738.21",
                "spending": "2037.09"
              },
              {
                "month": "2027-11",
                "date": "2027-11-30",
                "cash": "15801.47",
                "investments": "62883.38",
                "owed": "12668.43",
                "net_worth": "366016.42",
                "spending": "2037.09"
              },
              {
                "month": "2027-12",
                "date": "2027-12-31",
                "cash": "15801.47",
                "investments": "64754.58",
                "owed": "12252.78",
                "net_worth": "368303.27",
                "spending": "2037.09"
              },
              {
                "month": "2028-01",
                "date": "2028-01-31",
                "cash": "15801.47",
                "investments": "66632.02",
                "owed": "11835.20",
                "net_worth": "370598.29",
                "spending": "2037.09"
              },
              {
                "month": "2028-02",
                "date": "2028-02-29",
                "cash": "15801.47",
                "investments": "68515.71",
                "owed": "11415.67",
                "net_worth": "372901.51",
                "spending": "2037.09"
              },
              {
                "month": "2028-03",
                "date": "2028-03-31",
                "cash": "15801.47",
                "investments": "70405.69",
                "owed": "10994.20",
                "net_worth": "375212.96",
                "spending": "2037.09"
              },
              {
                "month": "2028-04",
                "date": "2028-04-30",
                "cash": "15801.47",
                "investments": "72301.96",
                "owed": "10570.76",
                "net_worth": "377532.67",
                "spending": "2037.09"
              }
            ],
            "notes": []
          },
          {
            "label": "Wait 6 months",
            "scenario": {
              "schema": "salli.scenario/1",
              "label": "Wait 6 months",
              "as_of": "2026-10-11",
              "horizon_years": 5,
              "changes": [
                {
                  "type": "set_aside",
                  "monthly": "400.00",
                  "from": "2026-11-02",
                  "to": "2027-04-30",
                  "label": "Saving for Laptop"
                },
                {
                  "type": "one_off",
                  "date": "2027-05-02",
                  "amount": "-2400.00",
                  "account": "chk",
                  "label": "Laptop"
                }
              ]
            },
            "scenario_hash": "sha256:54f663454d40513a0b7efa5cbf3f89feb77e7b9ca2e20370ac312603d0e27dcd",
            "figures": {
              "lowest_cash": "14013.25",
              "cash_in_12_months": "15801.47",
              "safe_to_spend": "15316.35",
              "any_account_below_zero": false,
              "monthly_spending": "1898.32",
              "emergency_months": "7.38",
              "emergency_months_in_12_months": "8.32",
              "net_worth_1y": "363797.24",
              "net_worth_5y": "482655.31",
              "net_worth_10y": "660842.88",
              "net_worth_20y": "1144076.69",
              "cash_1y": "15801.47",
              "cash_5y": "15801.47",
              "cash_10y": "15801.47",
              "cash_20y": "15801.47",
              "investments_1y": "61077.92",
              "investments_5y": "168810.75",
              "investments_10y": "345041.41",
              "investments_20y": "828275.22",
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
            "principles": [
              {
                "principle_id": "00002331-5a11-4000-8000-000000009009",
                "label": "Six months of essentials in cash",
                "status": "keeps",
                "reason": "emergency_months >= 6 holds: emergency_months is 7.38.",
                "figures": {
                  "emergency_months": "7.38"
                }
              },
              {
                "principle_id": "00002333-5a11-4000-8000-000000009011",
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
                "cash": "16201.47",
                "investments": "42945.54",
                "owed": "17508.68",
                "net_worth": "341638.33",
                "spending": "2037.09"
              },
              {
                "month": "2026-12",
                "date": "2026-12-31",
                "cash": "16601.47",
                "investments": "44350.28",
                "owed": "17115.53",
                "net_worth": "343836.22",
                "spending": "2037.09"
              },
              {
                "month": "2027-01",
                "date": "2027-01-31",
                "cash": "17001.47",
                "investments": "45759.71",
                "owed": "16720.55",
                "net_worth": "346040.63",
                "spending": "2037.09"
              },
              {
                "month": "2027-02",
                "date": "2027-02-28",
                "cash": "17401.47",
                "investments": "47173.83",
                "owed": "16323.74",
                "net_worth": "348251.56",
                "spending": "2037.09"
              },
              {
                "month": "2027-03",
                "date": "2027-03-31",
                "cash": "17801.47",
                "investments": "48592.67",
                "owed": "15925.09",
                "net_worth": "350469.05",
                "spending": "2037.09"
              },
              {
                "month": "2027-04",
                "date": "2027-04-30",
                "cash": "18201.47",
                "investments": "50016.23",
                "owed": "15524.58",
                "net_worth": "352693.12",
                "spending": "2037.09"
              },
              {
                "month": "2027-05",
                "date": "2027-05-31",
                "cash": "15801.47",
                "investments": "51844.54",
                "owed": "15122.22",
                "net_worth": "352523.79",
                "spending": "2037.09"
              },
              {
                "month": "2027-06",
                "date": "2027-06-30",
                "cash": "15801.47",
                "investments": "53678.95",
                "owed": "14717.98",
                "net_worth": "354762.44",
                "spending": "2037.09"
              },
              {
                "month": "2027-07",
                "date": "2027-07-31",
                "cash": "15801.47",
                "investments": "55519.47",
                "owed": "14311.86",
                "net_worth": "357009.08",
                "spending": "2037.09"
              },
              {
                "month": "2027-08",
                "date": "2027-08-31",
                "cash": "15801.47",
                "investments": "57366.12",
                "owed": "13903.86",
                "net_worth": "359263.73",
                "spending": "2037.09"
              },
              {
                "month": "2027-09",
                "date": "2027-09-30",
                "cash": "15801.47",
                "investments": "59218.93",
                "owed": "13493.96",
                "net_worth": "361526.44",
                "spending": "2037.09"
              },
              {
                "month": "2027-10",
                "date": "2027-10-31",
                "cash": "15801.47",
                "investments": "61077.92",
                "owed": "13082.15",
                "net_worth": "363797.24",
                "spending": "2037.09"
              },
              {
                "month": "2027-11",
                "date": "2027-11-30",
                "cash": "15801.47",
                "investments": "62943.10",
                "owed": "12668.43",
                "net_worth": "366076.14",
                "spending": "2037.09"
              },
              {
                "month": "2027-12",
                "date": "2027-12-31",
                "cash": "15801.47",
                "investments": "64814.50",
                "owed": "12252.78",
                "net_worth": "368363.19",
                "spending": "2037.09"
              },
              {
                "month": "2028-01",
                "date": "2028-01-31",
                "cash": "15801.47",
                "investments": "66692.14",
                "owed": "11835.20",
                "net_worth": "370658.41",
                "spending": "2037.09"
              },
              {
                "month": "2028-02",
                "date": "2028-02-29",
                "cash": "15801.47",
                "investments": "68576.04",
                "owed": "11415.67",
                "net_worth": "372961.84",
                "spending": "2037.09"
              },
              {
                "month": "2028-03",
                "date": "2028-03-31",
                "cash": "15801.47",
                "investments": "70466.21",
                "owed": "10994.20",
                "net_worth": "375273.48",
                "spending": "2037.09"
              },
              {
                "month": "2028-04",
                "date": "2028-04-30",
                "cash": "15801.47",
                "investments": "72362.69",
                "owed": "10570.76",
                "net_worth": "377593.40",
                "spending": "2037.09"
              }
            ],
            "notes": []
          }
        ],
        "chosen": "Pay cash",
        "reasons": "The old one is failing, and I would rather not owe anything.",
        "agent_summary": null,
        "review_on": "2027-04-30"
      },
      "hash": "sha256:bbe9a3256c663ce1f948d87d2a4c155a74491f611221c4373b8c8c10952b8628",
      "notes": [
        {
          "note": {
            "schema": "salli.decision-note/1",
            "id": "0000233c-5a11-4000-8000-000000009020",
            "decision_id": "00002339-5a11-4000-8000-000000009017",
            "entry_hash": "sha256:bbe9a3256c663ce1f948d87d2a4c155a74491f611221c4373b8c8c10952b8628",
            "at": "2026-10-11T10:00:00+00:00",
            "text": "The shop held the price until November.",
            "author": "user",
            "agent": null
          },
          "hash": "sha256:fc92b5344d4a0407fb74750291e9dd78c98ad12434b4b222c9c20a7bcfb7096f",
          "verified": true
        }
      ],
      "reviews": []
    }
  ]
};

export const JOURNAL_MARKDOWN: string = "# Decision journal\n\nExported 2026-10-11T10:00:00+00:00. Every figure is Salli's, as recorded; the JSON export holds each document exactly, and its hash shows it is unchanged. Each hash is the SHA-256 of the document's canonical JSON: keys sorted, no whitespace, ASCII only (non-ASCII as \\u escapes), numbers as decimal strings. Recompute it over `entry` (or `note`, `review`) and compare.\n\n## Change anything?\n\nRecorded 2026-08-11, as of 2026-08-11, in EUR. Chosen: **Keep as is**. Review on 2026-09-30.\n\n**Reasons, in the person's words**\n\n> It works.\n\n### The options\n\n| Figure | Baseline | Keep as is |\n|---|---|---|\n| Lowest cash, next 12 months | 9512.79 | 9512.79 |\n| Emergency months at the low | 5.01 | 5.01 |\n| Net worth in 1 year (today's money) | 360096.23 | 360096.23 |\n| Net worth in 5 years (today's money) | 479060.97 | 479060.97 |\n| Net worth in 10 years (today's money) | 657438.80 | 657438.80 |\n| Interest on debts | 2111.31 | 2111.31 |\n| Months to debt-free | 77 | 77 |\n| Months to FI | 216 | 216 |\n\n- **Keep as is**: 0 changes; scenario hash `sha256:261f716d1eec826e987eec2e389236965848996fa2bf245b3a48707e7015b597`\n\nAssumptions that were placeholders: real_return, safe_withdrawal_rate, surplus_invested, drawdown_horizon, inflation. Engine 4; baseline `sha256:6c039c9c7f41e2cc30a1b4516f69e3c5054a83e8563692d281b9f87fdd083fee`; the ledger's newest entry was from 2026-08-09.\n\nEntry hash `sha256:89c4e9c86e53767f40162995b37ec28b9c9de1bddd6ef4682b11f0c0ed1efb1e`\n\n## Laptop: pay cash, spread it or wait?\n\nRecorded 2026-10-11, as of 2026-10-11, in EUR. Chosen: **Pay cash**. Review on 2027-04-30.\n\n**Reasons, in the person's words**\n\n> The old one is failing, and I would rather not owe anything.\n\n### The options\n\n| Figure | Baseline | Pay cash | Spread over 12 months | Wait 6 months |\n|---|---|---|---|---|\n| Lowest cash, next 12 months | 13998.91 | 11598.91 | 13821.01 | 14013.25 |\n| Emergency months at the low | 7.37 | 6.11 | 7.28 | 7.38 |\n| Net worth in 1 year (today's money) | 366266.13 | 363866.13 | 363738.21 | 363797.24 |\n| Net worth in 5 years (today's money) | 485551.81 | 483151.81 | 482585.47 | 482655.31 |\n| Net worth in 10 years (today's money) | 664379.50 | 661979.50 | 660757.60 | 660842.88 |\n| Interest on debts | 2009.25 | 2009.25 | 2099.93 | 2009.25 |\n| Months to debt-free | 77 | 77 | 77 | 77 |\n| Months to FI | 214 | 215 | 215 | 215 |\n\n- **Pay cash**: 1 change; scenario hash `sha256:9b094ea3ce715a3e72c3351d3125a932f6182e9a6d202e422b1facc0787702e4`\n- **Spread over 12 months**: 2 changes; scenario hash `sha256:65aea5213bff9c2365ddf72f441301d3eebd8e577b5afbaa316f4a26e6f28a00`\n- **Wait 6 months**: 2 changes; scenario hash `sha256:54f663454d40513a0b7efa5cbf3f89feb77e7b9ca2e20370ac312603d0e27dcd`\n\n### Principles\n\n| Principle | Baseline | Pay cash | Spread over 12 months | Wait 6 months |\n|---|---|---|---|---|\n| Six months of essentials in cash (`emergency_months >= 6`) | keeps | keeps | keeps | keeps |\n| Checking above 5,000 (`account_lowest >= 5000`) | keeps | breaks | keeps | keeps |\n\nAssumptions that were placeholders: real_return, safe_withdrawal_rate, surplus_invested, drawdown_horizon, inflation. Engine 4; baseline `sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b`; the ledger's newest entry was from 2026-10-09.\n\n### Notes\n\n- 2026-10-11 (the person): The shop held the price until November.\n\nEntry hash `sha256:bbe9a3256c663ce1f948d87d2a4c155a74491f611221c4373b8c8c10952b8628`\n";

/**
 * The answer to recording the laptop.
 */
export const RECORDED: Decision = {
  "id": "00002339-5a11-4000-8000-000000009017",
  "hash": "sha256:bbe9a3256c663ce1f948d87d2a4c155a74491f611221c4373b8c8c10952b8628",
  "verified": true,
  "status": "awaiting_review",
  "entry": {
    "schema": "salli.decision/1",
    "id": "00002339-5a11-4000-8000-000000009017",
    "recorded_at": "2026-10-11T10:00:00+00:00",
    "recorded_via": {
      "channel": "api"
    },
    "question": "Laptop: pay cash, spread it or wait?",
    "as_of": "2026-10-11",
    "currency": "EUR",
    "basis": {
      "baseline_fingerprint": "sha256:b1df0d109c1ec4f660804d5fce4738a5a92705290532b6eafe5e871c6714668b",
      "versions": {
        "schema": "salli.scenario/1",
        "engine": "4",
        "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
        "rule_sets": []
      },
      "assumptions": {
        "status": "placeholder",
        "headline_status": "placeholder",
        "headline": "Rests on placeholders for the real return, the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon"
        ],
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
      "placeholders": [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "drawdown_horizon",
        "inflation"
      ],
      "data_as_of": "2026-10-09",
      "is_stale": false
    },
    "principles": [
      {
        "id": "00002331-5a11-4000-8000-000000009009",
        "label": "Six months of essentials in cash",
        "check": "emergency_months >= 6",
        "account": null,
        "version": 1,
        "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
      },
      {
        "id": "00002333-5a11-4000-8000-000000009011",
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
      "principles": [
        {
          "principle_id": "00002331-5a11-4000-8000-000000009009",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
          "figures": {
            "emergency_months": "7.37"
          }
        },
        {
          "principle_id": "00002333-5a11-4000-8000-000000009011",
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
          "horizon_years": 5,
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
        "scenario_hash": "sha256:9b094ea3ce715a3e72c3351d3125a932f6182e9a6d202e422b1facc0787702e4",
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
        "principles": [
          {
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 6.11.",
            "figures": {
              "emergency_months": "6.11"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
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
          },
          {
            "month": "2027-01",
            "date": "2027-01-31",
            "cash": "13401.47",
            "investments": "46963.71",
            "owed": "16720.55",
            "net_worth": "343644.63",
            "spending": "2037.09"
          },
          {
            "month": "2027-02",
            "date": "2027-02-28",
            "cash": "13401.47",
            "investments": "48781.85",
            "owed": "16323.74",
            "net_worth": "345859.58",
            "spending": "2037.09"
          },
          {
            "month": "2027-03",
            "date": "2027-03-31",
            "cash": "13401.47",
            "investments": "50606.04",
            "owed": "15925.09",
            "net_worth": "348082.42",
            "spending": "2037.09"
          },
          {
            "month": "2027-04",
            "date": "2027-04-30",
            "cash": "13401.47",
            "investments": "52436.32",
            "owed": "15524.58",
            "net_worth": "350313.21",
            "spending": "2037.09"
          },
          {
            "month": "2027-05",
            "date": "2027-05-31",
            "cash": "13401.47",
            "investments": "54272.70",
            "owed": "15122.22",
            "net_worth": "352551.95",
            "spending": "2037.09"
          },
          {
            "month": "2027-06",
            "date": "2027-06-30",
            "cash": "13401.47",
            "investments": "56115.20",
            "owed": "14717.98",
            "net_worth": "354798.69",
            "spending": "2037.09"
          },
          {
            "month": "2027-07",
            "date": "2027-07-31",
            "cash": "13401.47",
            "investments": "57963.84",
            "owed": "14311.86",
            "net_worth": "357053.45",
            "spending": "2037.09"
          },
          {
            "month": "2027-08",
            "date": "2027-08-31",
            "cash": "13401.47",
            "investments": "59818.64",
            "owed": "13903.86",
            "net_worth": "359316.25",
            "spending": "2037.09"
          },
          {
            "month": "2027-09",
            "date": "2027-09-30",
            "cash": "13401.47",
            "investments": "61679.63",
            "owed": "13493.96",
            "net_worth": "361587.14",
            "spending": "2037.09"
          },
          {
            "month": "2027-10",
            "date": "2027-10-31",
            "cash": "13401.47",
            "investments": "63546.81",
            "owed": "13082.15",
            "net_worth": "363866.13",
            "spending": "2037.09"
          },
          {
            "month": "2027-11",
            "date": "2027-11-30",
            "cash": "13401.47",
            "investments": "65420.23",
            "owed": "12668.43",
            "net_worth": "366153.27",
            "spending": "2037.09"
          },
          {
            "month": "2027-12",
            "date": "2027-12-31",
            "cash": "13401.47",
            "investments": "67299.89",
            "owed": "12252.78",
            "net_worth": "368448.58",
            "spending": "2037.09"
          },
          {
            "month": "2028-01",
            "date": "2028-01-31",
            "cash": "13401.47",
            "investments": "69185.81",
            "owed": "11835.20",
            "net_worth": "370752.08",
            "spending": "2037.09"
          },
          {
            "month": "2028-02",
            "date": "2028-02-29",
            "cash": "13401.47",
            "investments": "71078.02",
            "owed": "11415.67",
            "net_worth": "373063.82",
            "spending": "2037.09"
          },
          {
            "month": "2028-03",
            "date": "2028-03-31",
            "cash": "13401.47",
            "investments": "72976.53",
            "owed": "10994.20",
            "net_worth": "375383.80",
            "spending": "2037.09"
          },
          {
            "month": "2028-04",
            "date": "2028-04-30",
            "cash": "13401.47",
            "investments": "74881.38",
            "owed": "10570.76",
            "net_worth": "377712.09",
            "spending": "2037.09"
          }
        ],
        "notes": []
      },
      {
        "label": "Spread over 12 months",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Spread over 12 months",
          "as_of": "2026-10-11",
          "horizon_years": 5,
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
              "label": "Laptop, over 12 months"
            }
          ]
        },
        "scenario_hash": "sha256:65aea5213bff9c2365ddf72f441301d3eebd8e577b5afbaa316f4a26e6f28a00",
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
        "principles": [
          {
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.28.",
            "figures": {
              "emergency_months": "7.28"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
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
          },
          {
            "month": "2027-01",
            "date": "2027-01-31",
            "cash": "15801.47",
            "investments": "46547.92",
            "owed": "18731.94",
            "net_worth": "343617.45",
            "spending": "2037.09"
          },
          {
            "month": "2027-02",
            "date": "2027-02-28",
            "cash": "15801.47",
            "investments": "48157.12",
            "owed": "18139.15",
            "net_worth": "345819.44",
            "spending": "2037.09"
          },
          {
            "month": "2027-03",
            "date": "2027-03-31",
            "cash": "15801.47",
            "investments": "49771.68",
            "owed": "17543.39",
            "net_worth": "348029.76",
            "spending": "2037.09"
          },
          {
            "month": "2027-04",
            "date": "2027-04-30",
            "cash": "15801.47",
            "investments": "51391.63",
            "owed": "16944.64",
            "net_worth": "350248.46",
            "spending": "2037.09"
          },
          {
            "month": "2027-05",
            "date": "2027-05-31",
            "cash": "15801.47",
            "investments": "53016.97",
            "owed": "16342.90",
            "net_worth": "352475.54",
            "spending": "2037.09"
          },
          {
            "month": "2027-06",
            "date": "2027-06-30",
            "cash": "15801.47",
            "investments": "54647.74",
            "owed": "15738.13",
            "net_worth": "354711.08",
            "spending": "2037.09"
          },
          {
            "month": "2027-07",
            "date": "2027-07-31",
            "cash": "15801.47",
            "investments": "56283.94",
            "owed": "15130.33",
            "net_worth": "356955.08",
            "spending": "2037.09"
          },
          {
            "month": "2027-08",
            "date": "2027-08-31",
            "cash": "15801.47",
            "investments": "57925.59",
            "owed": "14519.49",
            "net_worth": "359207.57",
            "spending": "2037.09"
          },
          {
            "month": "2027-09",
            "date": "2027-09-30",
            "cash": "15801.47",
            "investments": "59572.72",
            "owed": "13905.58",
            "net_worth": "361468.61",
            "spending": "2037.09"
          },
          {
            "month": "2027-10",
            "date": "2027-10-31",
            "cash": "15801.47",
            "investments": "61225.33",
            "owed": "13288.59",
            "net_worth": "363738.21",
            "spending": "2037.09"
          },
          {
            "month": "2027-11",
            "date": "2027-11-30",
            "cash": "15801.47",
            "investments": "62883.38",
            "owed": "12668.43",
            "net_worth": "366016.42",
            "spending": "2037.09"
          },
          {
            "month": "2027-12",
            "date": "2027-12-31",
            "cash": "15801.47",
            "investments": "64754.58",
            "owed": "12252.78",
            "net_worth": "368303.27",
            "spending": "2037.09"
          },
          {
            "month": "2028-01",
            "date": "2028-01-31",
            "cash": "15801.47",
            "investments": "66632.02",
            "owed": "11835.20",
            "net_worth": "370598.29",
            "spending": "2037.09"
          },
          {
            "month": "2028-02",
            "date": "2028-02-29",
            "cash": "15801.47",
            "investments": "68515.71",
            "owed": "11415.67",
            "net_worth": "372901.51",
            "spending": "2037.09"
          },
          {
            "month": "2028-03",
            "date": "2028-03-31",
            "cash": "15801.47",
            "investments": "70405.69",
            "owed": "10994.20",
            "net_worth": "375212.96",
            "spending": "2037.09"
          },
          {
            "month": "2028-04",
            "date": "2028-04-30",
            "cash": "15801.47",
            "investments": "72301.96",
            "owed": "10570.76",
            "net_worth": "377532.67",
            "spending": "2037.09"
          }
        ],
        "notes": []
      },
      {
        "label": "Wait 6 months",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Wait 6 months",
          "as_of": "2026-10-11",
          "horizon_years": 5,
          "changes": [
            {
              "type": "set_aside",
              "monthly": "400.00",
              "from": "2026-11-02",
              "to": "2027-04-30",
              "label": "Saving for Laptop"
            },
            {
              "type": "one_off",
              "date": "2027-05-02",
              "amount": "-2400.00",
              "account": "chk",
              "label": "Laptop"
            }
          ]
        },
        "scenario_hash": "sha256:54f663454d40513a0b7efa5cbf3f89feb77e7b9ca2e20370ac312603d0e27dcd",
        "figures": {
          "lowest_cash": "14013.25",
          "cash_in_12_months": "15801.47",
          "safe_to_spend": "15316.35",
          "any_account_below_zero": false,
          "monthly_spending": "1898.32",
          "emergency_months": "7.38",
          "emergency_months_in_12_months": "8.32",
          "net_worth_1y": "363797.24",
          "net_worth_5y": "482655.31",
          "net_worth_10y": "660842.88",
          "net_worth_20y": "1144076.69",
          "cash_1y": "15801.47",
          "cash_5y": "15801.47",
          "cash_10y": "15801.47",
          "cash_20y": "15801.47",
          "investments_1y": "61077.92",
          "investments_5y": "168810.75",
          "investments_10y": "345041.41",
          "investments_20y": "828275.22",
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
        "principles": [
          {
            "principle_id": "00002331-5a11-4000-8000-000000009009",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.38.",
            "figures": {
              "emergency_months": "7.38"
            }
          },
          {
            "principle_id": "00002333-5a11-4000-8000-000000009011",
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
            "cash": "16201.47",
            "investments": "42945.54",
            "owed": "17508.68",
            "net_worth": "341638.33",
            "spending": "2037.09"
          },
          {
            "month": "2026-12",
            "date": "2026-12-31",
            "cash": "16601.47",
            "investments": "44350.28",
            "owed": "17115.53",
            "net_worth": "343836.22",
            "spending": "2037.09"
          },
          {
            "month": "2027-01",
            "date": "2027-01-31",
            "cash": "17001.47",
            "investments": "45759.71",
            "owed": "16720.55",
            "net_worth": "346040.63",
            "spending": "2037.09"
          },
          {
            "month": "2027-02",
            "date": "2027-02-28",
            "cash": "17401.47",
            "investments": "47173.83",
            "owed": "16323.74",
            "net_worth": "348251.56",
            "spending": "2037.09"
          },
          {
            "month": "2027-03",
            "date": "2027-03-31",
            "cash": "17801.47",
            "investments": "48592.67",
            "owed": "15925.09",
            "net_worth": "350469.05",
            "spending": "2037.09"
          },
          {
            "month": "2027-04",
            "date": "2027-04-30",
            "cash": "18201.47",
            "investments": "50016.23",
            "owed": "15524.58",
            "net_worth": "352693.12",
            "spending": "2037.09"
          },
          {
            "month": "2027-05",
            "date": "2027-05-31",
            "cash": "15801.47",
            "investments": "51844.54",
            "owed": "15122.22",
            "net_worth": "352523.79",
            "spending": "2037.09"
          },
          {
            "month": "2027-06",
            "date": "2027-06-30",
            "cash": "15801.47",
            "investments": "53678.95",
            "owed": "14717.98",
            "net_worth": "354762.44",
            "spending": "2037.09"
          },
          {
            "month": "2027-07",
            "date": "2027-07-31",
            "cash": "15801.47",
            "investments": "55519.47",
            "owed": "14311.86",
            "net_worth": "357009.08",
            "spending": "2037.09"
          },
          {
            "month": "2027-08",
            "date": "2027-08-31",
            "cash": "15801.47",
            "investments": "57366.12",
            "owed": "13903.86",
            "net_worth": "359263.73",
            "spending": "2037.09"
          },
          {
            "month": "2027-09",
            "date": "2027-09-30",
            "cash": "15801.47",
            "investments": "59218.93",
            "owed": "13493.96",
            "net_worth": "361526.44",
            "spending": "2037.09"
          },
          {
            "month": "2027-10",
            "date": "2027-10-31",
            "cash": "15801.47",
            "investments": "61077.92",
            "owed": "13082.15",
            "net_worth": "363797.24",
            "spending": "2037.09"
          },
          {
            "month": "2027-11",
            "date": "2027-11-30",
            "cash": "15801.47",
            "investments": "62943.10",
            "owed": "12668.43",
            "net_worth": "366076.14",
            "spending": "2037.09"
          },
          {
            "month": "2027-12",
            "date": "2027-12-31",
            "cash": "15801.47",
            "investments": "64814.50",
            "owed": "12252.78",
            "net_worth": "368363.19",
            "spending": "2037.09"
          },
          {
            "month": "2028-01",
            "date": "2028-01-31",
            "cash": "15801.47",
            "investments": "66692.14",
            "owed": "11835.20",
            "net_worth": "370658.41",
            "spending": "2037.09"
          },
          {
            "month": "2028-02",
            "date": "2028-02-29",
            "cash": "15801.47",
            "investments": "68576.04",
            "owed": "11415.67",
            "net_worth": "372961.84",
            "spending": "2037.09"
          },
          {
            "month": "2028-03",
            "date": "2028-03-31",
            "cash": "15801.47",
            "investments": "70466.21",
            "owed": "10994.20",
            "net_worth": "375273.48",
            "spending": "2037.09"
          },
          {
            "month": "2028-04",
            "date": "2028-04-30",
            "cash": "15801.47",
            "investments": "72362.69",
            "owed": "10570.76",
            "net_worth": "377593.40",
            "spending": "2037.09"
          }
        ],
        "notes": []
      }
    ],
    "chosen": "Pay cash",
    "reasons": "The old one is failing, and I would rather not owe anything.",
    "agent_summary": null,
    "review_on": "2027-04-30"
  },
  "notes": [],
  "reviews": []
};

/**
 * The answer to the laptop's note.
 */
export const NOTE: DecisionNote = {
  "note": {
    "schema": "salli.decision-note/1",
    "id": "0000233c-5a11-4000-8000-000000009020",
    "decision_id": "00002339-5a11-4000-8000-000000009017",
    "entry_hash": "sha256:bbe9a3256c663ce1f948d87d2a4c155a74491f611221c4373b8c8c10952b8628",
    "at": "2026-10-11T10:00:00+00:00",
    "text": "The shop held the price until November.",
    "author": "user",
    "agent": null
  },
  "hash": "sha256:fc92b5344d4a0407fb74750291e9dd78c98ad12434b4b222c9c20a7bcfb7096f",
  "verified": true
};

export const PRINCIPLE_ADDED: Principle = {
  "schema": "salli.principle/1",
  "id": "0000235a-5a11-4000-8000-000000009050",
  "label": "Never below 2,000 in checking",
  "check": "account_lowest >= 2000",
  "account": "chk",
  "note": null,
  "version": 1,
  "hash": "sha256:a5fda9fff12216c6656dc4b221b67fa6a60779b1f4890b6658e84c062c438e63",
  "author": "user",
  "agent": null,
  "status": "active",
  "created_at": "2026-10-11T10:00:00+00:00",
  "updated_at": "2026-10-11T10:00:00+00:00",
  "archived_at": null
};

export const PRINCIPLE_EDITED: Principle = {
  "schema": "salli.principle/1",
  "id": "00002331-5a11-4000-8000-000000009009",
  "label": "Nine months of essentials in cash",
  "check": "emergency_months >= 9",
  "account": null,
  "note": null,
  "version": 2,
  "hash": "sha256:e5f20fda0ec866d363b15b6c28095ec9a328f1b7da63628205b96030a5665234",
  "author": "user",
  "agent": null,
  "status": "active",
  "created_at": "2026-10-11T10:00:00+00:00",
  "updated_at": "2026-10-11T10:00:00+00:00",
  "archived_at": null
};

/**
 * A check naming a figure that doesn't exist, refused with where and why.
 */
export const PRINCIPLE_REFUSED: ProblemDetails = {
  "type": "/problems/invalid-principle",
  "title": "Not a principle Salli can keep",
  "status": 422,
  "detail": [
    {
      "loc": [
        "body",
        "check"
      ],
      "msg": "There is no figure 'emergency_month'. Did you mean emergency_months? The figures are listed by GET /v1/principles/figures (`salli principles figures`).",
      "snippet": "emergency_month >= 6\n^"
    }
  ]
};

/**
 * Afford it with no price and a rate that isn't one, refused at their paths.
 */
export const START_REFUSED: ProblemDetails = {
  "type": "/problems/invalid-answers",
  "title": "Not answers Salli can build options from",
  "status": 422,
  "detail": [
    {
      "loc": [
        "body",
        "answers",
        "price"
      ],
      "msg": "is required: What does it cost?"
    },
    {
      "loc": [
        "body",
        "answers",
        "instalment_rate"
      ],
      "msg": "'6.9%' is not a yearly fraction, like \"0.069\" for 6.9%"
    }
  ]
};

/**
 * The answer to reviewing the August decision.
 */
export const REVIEWED: DecisionReview = {
  "review": {
    "schema": "salli.decision-review/1",
    "id": "0000235d-5a11-4000-8000-000000009053",
    "decision_id": "0000232e-5a11-4000-8000-000000009006",
    "entry_hash": "sha256:89c4e9c86e53767f40162995b37ec28b9c9de1bddd6ef4682b11f0c0ed1efb1e",
    "at": "2026-10-11T10:00:00+00:00",
    "as_of": "2026-10-11",
    "reflection": "Nothing needed changing, and nothing did.",
    "author": "user",
    "agent": null,
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
      "baseline_fingerprint": "sha256:99da6b61743dc278133f3204b498f5d6c0affc71a98e31765f97886ce7e417de",
      "data_as_of": "2026-09-26",
      "is_stale": false,
      "notes": [
        "Dollar account: no published USD rate for 2026-09-30, so it is left out of the totals in EUR"
      ]
    }
  },
  "hash": "sha256:f38c9092d61006d5cfffacc979adfbdb15cdc540afbb7994dd328d9fdf44d1de",
  "verified": true
};

/**
 * The August decision once reviewed.
 */
export const DECISION_REVIEWED: Decision = {
  "id": "0000232e-5a11-4000-8000-000000009006",
  "hash": "sha256:89c4e9c86e53767f40162995b37ec28b9c9de1bddd6ef4682b11f0c0ed1efb1e",
  "verified": true,
  "status": "reviewed",
  "entry": {
    "schema": "salli.decision/1",
    "id": "0000232e-5a11-4000-8000-000000009006",
    "recorded_at": "2026-08-11T09:00:00+00:00",
    "recorded_via": {
      "channel": "api"
    },
    "question": "Change anything?",
    "as_of": "2026-08-11",
    "currency": "EUR",
    "basis": {
      "baseline_fingerprint": "sha256:6c039c9c7f41e2cc30a1b4516f69e3c5054a83e8563692d281b9f87fdd083fee",
      "versions": {
        "schema": "salli.scenario/1",
        "engine": "4",
        "fi_assumptions": "sha256:d88f80280a74ec5a04748ec1a9c473622b741f3f5c1930efb241de7ee25fb038",
        "rule_sets": []
      },
      "assumptions": {
        "status": "placeholder",
        "headline_status": "placeholder",
        "headline": "Rests on placeholders for the real return, the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate",
          "surplus_invested",
          "drawdown_horizon"
        ],
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
      "placeholders": [
        "real_return",
        "safe_withdrawal_rate",
        "surplus_invested",
        "drawdown_horizon",
        "inflation"
      ],
      "data_as_of": "2026-08-09",
      "is_stale": false
    },
    "principles": [],
    "baseline": {
      "figures": {
        "lowest_cash": "9512.79",
        "cash_in_12_months": "11316.20",
        "safe_to_spend": "10826.46",
        "any_account_below_zero": false,
        "monthly_spending": "1897.48",
        "emergency_months": "5.01",
        "emergency_months_in_12_months": "5.96",
        "net_worth_1y": "360096.23",
        "net_worth_5y": "479060.97",
        "net_worth_10y": "657438.80",
        "net_worth_20y": "1141188.58",
        "cash_1y": "11316.20",
        "cash_5y": "11316.20",
        "cash_10y": "11316.20",
        "cash_20y": "11316.20",
        "investments_1y": "62498.54",
        "investments_5y": "169701.68",
        "investments_10y": "346122.60",
        "investments_20y": "829872.38",
        "debts_1y": "13718.51",
        "debts_5y": "1956.91",
        "debts_10y": "0.00",
        "debts_20y": "0.00",
        "total_interest": "2111.31",
        "debt_free_months": 77,
        "max_debt_rate": "0.059",
        "max_debt_rate_while_investing": "0.059",
        "borrowed": "0.00",
        "fi_number": "714080.25",
        "fi_months": 216,
        "fi_months_gained": 0,
        "tax_change_this_year": "0.00"
      },
      "unavailable": {},
      "principles": []
    },
    "options": [
      {
        "label": "Keep as is",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "Keep as is",
          "as_of": "2026-08-11",
          "horizon_years": 20,
          "changes": []
        },
        "scenario_hash": "sha256:261f716d1eec826e987eec2e389236965848996fa2bf245b3a48707e7015b597",
        "figures": {
          "lowest_cash": "9512.79",
          "cash_in_12_months": "11316.20",
          "safe_to_spend": "10826.46",
          "any_account_below_zero": false,
          "monthly_spending": "1897.48",
          "emergency_months": "5.01",
          "emergency_months_in_12_months": "5.96",
          "net_worth_1y": "360096.23",
          "net_worth_5y": "479060.97",
          "net_worth_10y": "657438.80",
          "net_worth_20y": "1141188.58",
          "cash_1y": "11316.20",
          "cash_5y": "11316.20",
          "cash_10y": "11316.20",
          "cash_20y": "11316.20",
          "investments_1y": "62498.54",
          "investments_5y": "169701.68",
          "investments_10y": "346122.60",
          "investments_20y": "829872.38",
          "debts_1y": "13718.51",
          "debts_5y": "1956.91",
          "debts_10y": "0.00",
          "debts_20y": "0.00",
          "total_interest": "2111.31",
          "debt_free_months": 77,
          "max_debt_rate": "0.059",
          "max_debt_rate_while_investing": "0.059",
          "borrowed": "0.00",
          "fi_number": "714080.25",
          "fi_months": 216,
          "fi_months_gained": 0,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "principles": [],
        "projection": [
          {
            "month": "2026-08",
            "date": "2026-08-11",
            "cash": "11316.20",
            "investments": "37000.00",
            "owed": "18500.00",
            "net_worth": "329816.20",
            "spending": null
          },
          {
            "month": "2026-08",
            "date": "2026-08-31",
            "cash": "11316.20",
            "investments": "40539.40",
            "owed": "18500.00",
            "net_worth": "333355.60",
            "spending": null
          },
          {
            "month": "2026-09",
            "date": "2026-09-30",
            "cash": "11316.20",
            "investments": "42336.02",
            "owed": "18111.63",
            "net_worth": "335540.59",
            "spending": "2040.14"
          },
          {
            "month": "2026-10",
            "date": "2026-10-31",
            "cash": "11316.20",
            "investments": "44138.63",
            "owed": "17721.45",
            "net_worth": "337733.38",
            "spending": "2040.14"
          },
          {
            "month": "2026-11",
            "date": "2026-11-30",
            "cash": "11316.20",
            "investments": "45947.25",
            "owed": "17329.45",
            "net_worth": "339934.00",
            "spending": "2040.14"
          },
          {
            "month": "2026-12",
            "date": "2026-12-31",
            "cash": "11316.20",
            "investments": "47761.90",
            "owed": "16935.63",
            "net_worth": "342142.47",
            "spending": "2040.14"
          },
          {
            "month": "2027-01",
            "date": "2027-01-31",
            "cash": "11316.20",
            "investments": "49582.59",
            "owed": "16539.98",
            "net_worth": "344358.81",
            "spending": "2040.14"
          },
          {
            "month": "2027-02",
            "date": "2027-02-28",
            "cash": "11316.20",
            "investments": "51409.36",
            "owed": "16142.50",
            "net_worth": "346583.06",
            "spending": "2040.14"
          },
          {
            "month": "2027-03",
            "date": "2027-03-31",
            "cash": "11316.20",
            "investments": "53242.21",
            "owed": "15743.17",
            "net_worth": "348815.24",
            "spending": "2040.14"
          },
          {
            "month": "2027-04",
            "date": "2027-04-30",
            "cash": "11316.20",
            "investments": "55081.18",
            "owed": "15341.98",
            "net_worth": "351055.40",
            "spending": "2040.14"
          },
          {
            "month": "2027-05",
            "date": "2027-05-31",
            "cash": "11316.20",
            "investments": "56926.27",
            "owed": "14938.92",
            "net_worth": "353303.55",
            "spending": "2040.14"
          },
          {
            "month": "2027-06",
            "date": "2027-06-30",
            "cash": "11316.20",
            "investments": "58777.51",
            "owed": "14534.00",
            "net_worth": "355559.71",
            "spending": "2040.14"
          },
          {
            "month": "2027-07",
            "date": "2027-07-31",
            "cash": "11316.20",
            "investments": "60634.93",
            "owed": "14127.20",
            "net_worth": "357823.93",
            "spending": "2040.14"
          },
          {
            "month": "2027-08",
            "date": "2027-08-31",
            "cash": "11316.20",
            "investments": "62498.54",
            "owed": "13718.51",
            "net_worth": "360096.23",
            "spending": "2040.14"
          },
          {
            "month": "2027-09",
            "date": "2027-09-30",
            "cash": "11316.20",
            "investments": "64368.35",
            "owed": "13307.92",
            "net_worth": "362376.63",
            "spending": "2040.14"
          }
        ],
        "notes": [
          "Dollar account: no published USD rate for 2026-08-11, so it is left out of the totals in EUR"
        ]
      }
    ],
    "chosen": "Keep as is",
    "reasons": "It works.",
    "agent_summary": null,
    "review_on": "2026-09-30"
  },
  "notes": [],
  "reviews": [
    {
      "review": {
        "schema": "salli.decision-review/1",
        "id": "0000235d-5a11-4000-8000-000000009053",
        "decision_id": "0000232e-5a11-4000-8000-000000009006",
        "entry_hash": "sha256:89c4e9c86e53767f40162995b37ec28b9c9de1bddd6ef4682b11f0c0ed1efb1e",
        "at": "2026-10-11T10:00:00+00:00",
        "as_of": "2026-10-11",
        "reflection": "Nothing needed changing, and nothing did.",
        "author": "user",
        "agent": null,
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
          "baseline_fingerprint": "sha256:99da6b61743dc278133f3204b498f5d6c0affc71a98e31765f97886ce7e417de",
          "data_as_of": "2026-09-26",
          "is_stale": false,
          "notes": [
            "Dollar account: no published USD rate for 2026-09-30, so it is left out of the totals in EUR"
          ]
        }
      },
      "hash": "sha256:f38c9092d61006d5cfffacc979adfbdb15cdc540afbb7994dd328d9fdf44d1de",
      "verified": true
    }
  ]
};
