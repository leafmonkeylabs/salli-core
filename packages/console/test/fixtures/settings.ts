/**
 * What a real server answers the console's settings (docs/design/console.md,
 * section 5) on the golden household (tests/golden/household.py, as of Oct
 * 11, 2026, in euros): two personal access tokens and an Anthropic key kept
 * before the reads, a weekly digest set up and sent on Monday Oct 5; then
 * the console's writes, after every read: a token made with tax:activate
 * (its secret shown this once, a fixture's, never a real one), the same
 * asked for by a console sign-in whose password is six minutes old (the
 * step-up answer), and a key the provider refuses. No secret here opens
 * anything.
 *
 * Written by tests/console_fixtures.py (`uv run python -m tests.console_fixtures`):
 * tests/contract/test_console_fixtures.py fails while it differs from what
 * the server answers. Don't edit it by hand.
 */
import type { AiSettings, DigestDeliveries, DigestPreview, LlmKeys, NewPersonalAccessToken, NotificationPreferences, PersonalAccessToken, ProblemDetails } from '@leafmonkeylabs/salli-sdk';

export const TOKENS: PersonalAccessToken[] = [
  {
    "id": "00002334-5a11-4000-8000-000000009012",
    "name": "Spreadsheet",
    "prefix": "salli_pat_fixt",
    "permissions": [],
    "created_at": "2026-10-01T08:00:00Z",
    "expires_at": null,
    "last_used_at": null
  },
  {
    "id": "00002331-5a11-4000-8000-000000009009",
    "name": "Backups",
    "prefix": "salli_pat_fixt",
    "permissions": [],
    "created_at": "2026-09-01T09:00:00Z",
    "expires_at": "2026-11-30T09:00:00Z",
    "last_used_at": null
  }
];

export const LLM_KEYS: LlmKeys = {
  "available": true,
  "keys": [
    {
      "provider": "anthropic",
      "last4": "7f3a",
      "validated_at": "2026-09-15T20:00:00+00:00",
      "readable": true
    }
  ]
};

export const AI_SETTINGS: AiSettings = {
  "provider": "auto",
  "active": {
    "provider": "anthropic",
    "source": "user"
  },
  "keys": [
    "anthropic"
  ],
  "chatgpt": null,
  "chatgpt_available": false,
  "platform_key": false,
  "models": {}
};

export const PREFERENCES: NotificationPreferences = {
  "enabled": true,
  "cadence": "weekly",
  "weekday": "monday",
  "hour": 8,
  "items": [
    "decision_review_due",
    "reminder_due",
    "filing_deadline",
    "cash_below_zero_ahead"
  ],
  "time_zone": "Europe/Lisbon",
  "next_at": "2026-10-12T08:00:00+01:00",
  "sender_enabled": true
};

/**
 * The digest as it would go now.
 */
export const PREVIEW: DigestPreview = {
  "period": "2026-W41",
  "as_of": "2026-10-11",
  "time_zone": "Europe/Lisbon",
  "digest": {
    "id": "b1b467fafcbe7684ec3ac5ea258e79fb0aa1d7b25c926269d22d3ac902da41c8",
    "kind": "digest",
    "period": "2026-W41",
    "subject": "Salli: what is waiting, week of Oct 5, 2026",
    "text": "What is waiting for you in Salli, as of Oct 11, 2026:\n\n- 1 decision ready for review (since Sep 30, 2026)\n- 1 reminder due on Oct 5, 2026\n\nOpen Salli, or run `salli status`, to see them.\n\nYou asked for this digest every week. To change it or turn it off: salli notifications set\n",
    "items": [
      {
        "kind": "decision_review_due",
        "title": "1 decision ready for review (since Sep 30, 2026)",
        "count": 1,
        "date": "2026-09-30"
      },
      {
        "kind": "reminder_due",
        "title": "1 reminder due on Oct 5, 2026",
        "count": 1,
        "date": "2026-10-05"
      }
    ],
    "link": null
  },
  "note": "This is the digest that would go if it went now."
};

/**
 * The digest sent on Monday.
 */
export const DELIVERIES: DigestDeliveries = {
  "deliveries": [
    {
      "id": "b1b467fafcbe7684ec3ac5ea258e79fb0aa1d7b25c926269d22d3ac902da41c8",
      "period": "2026-W41",
      "status": "sent",
      "attempts": 1,
      "items": [
        {
          "kind": "decision_review_due",
          "count": 1,
          "date": "2026-09-30"
        },
        {
          "kind": "reminder_due",
          "count": 1,
          "date": "2026-10-05"
        }
      ],
      "hash": "sha256:64c73b7a55d65e526147ef047f58d3cb1ff3515ba060b433f1a2788e30c7efbf",
      "created_at": "2026-10-05T07:00:00+00:00",
      "last_attempt_at": "2026-10-05T07:00:00+00:00",
      "sent_at": "2026-10-05T07:00:00+00:00"
    }
  ]
};

/**
 * The ledger as a Beancount file.
 */
export const BEANCOUNT: string = "; Exported from Salli. Every transaction carries its Salli id (salli-id).\noption \"operating_currency\" \"EUR\"\n\n2026-03-31 open Assets:Brokerage\n  asset-role: \"investment\"\n2026-03-31 open Assets:Checking\n  asset-role: \"cash\"\n2026-03-31 open Assets:DollarAccount\n  asset-role: \"cash\"\n2026-03-31 open Assets:Flat\n  asset-role: \"other\"\n2026-03-31 open Assets:PensionFund\n  asset-role: \"investment\"\n2026-03-31 open Assets:Savings\n  asset-role: \"cash\"\n2026-03-31 open Equity:OpeningEquity\n2026-03-31 open Expenses:EatingOut\n2026-03-31 open Expenses:Groceries\n2026-03-31 open Expenses:LoanInterest\n2026-03-31 open Expenses:Rent\n2026-03-31 open Expenses:Streaming\n2026-03-31 open Income:Salary\n2026-03-31 open Liabilities:CarLoan\n2026-03-31 open Liabilities:CreditCard\n\n2026-03-31 ! \"Opening balance\"\n  salli-id: \"e001\"\n  source: \"manual\"\n  Assets:Checking  3200.00 EUR\n  Equity:OpeningEquity  -3200.00 EUR\n\n2026-03-31 ! \"Opening balance\"\n  salli-id: \"e002\"\n  source: \"manual\"\n  Assets:Savings  6000.00 EUR\n  Equity:OpeningEquity  -6000.00 EUR\n\n2026-03-31 ! \"Opening balance\"\n  salli-id: \"e003\"\n  source: \"manual\"\n  Assets:Brokerage  10000.00 EUR\n  Equity:OpeningEquity  -10000.00 EUR\n\n2026-03-31 ! \"Opening balance\"\n  salli-id: \"e004\"\n  source: \"manual\"\n  Assets:PensionFund  25000.00 EUR\n  Equity:OpeningEquity  -25000.00 EUR\n\n2026-03-31 ! \"Opening balance\"\n  salli-id: \"e005\"\n  source: \"manual\"\n  Assets:Flat  300000.00 EUR\n  Equity:OpeningEquity  -300000.00 EUR\n\n2026-03-31 ! \"Opening balance\"\n  salli-id: \"e006\"\n  source: \"manual\"\n  Assets:DollarAccount  2000.00 USD @ 0.9 EUR\n  Equity:OpeningEquity  -1800.00 EUR\n\n2026-03-31 ! \"Opening balance\"\n  salli-id: \"e007\"\n  source: \"manual\"\n  Equity:OpeningEquity  12000.00 EUR\n  Liabilities:CarLoan  -12000.00 EUR\n\n2026-04-01 ! \"CITY LETTINGS RENT\"\n  salli-id: \"e008\"\n  source: \"statement\"\n  Expenses:Rent  1500.00 EUR\n    need: \"essential\"\n  Assets:Checking  -1500.00 EUR\n\n2026-04-05 ! \"AUTOFIN CAR LOAN\"\n  salli-id: \"e009\"\n  source: \"statement\"\n  Liabilities:CarLoan  300.00 EUR\n  Expenses:LoanInterest  50.00 EUR\n  Assets:Checking  -350.00 EUR\n\n2026-04-08 ! \"STREAMFLIX\"\n  salli-id: \"e010\"\n  source: \"statement\"\n  Expenses:Streaming  12.99 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -12.99 EUR\n\n2026-04-09 ! \"FRESHMART\"\n  salli-id: \"e011\"\n  source: \"statement\"\n  Expenses:Groceries  182.40 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -182.40 EUR\n\n2026-04-18 ! \"BISTRO NOVO\"\n  salli-id: \"e013\"\n  source: \"statement\"\n  Expenses:EatingOut  64.00 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -64.00 EUR\n\n2026-04-21 ! \"FRESHMART\"\n  salli-id: \"e012\"\n  source: \"statement\"\n  Expenses:Groceries  211.60 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -211.60 EUR\n\n2026-04-25 ! \"ACME LTD SALARY\"\n  salli-id: \"e014\"\n  source: \"statement\"\n  Assets:Checking  4000.00 EUR\n  Income:Salary  -4000.00 EUR\n\n2026-04-26 ! \"TO BROKERAGE\"\n  salli-id: \"e015\"\n  source: \"statement\"\n  Assets:Brokerage  500.00 EUR\n  Assets:Checking  -500.00 EUR\n\n2026-04-26 ! \"TO SAVINGS\"\n  salli-id: \"e016\"\n  source: \"statement\"\n  Assets:Savings  300.00 EUR\n  Assets:Checking  -300.00 EUR\n\n2026-05-01 ! \"CITY LETTINGS RENT\"\n  salli-id: \"e017\"\n  source: \"statement\"\n  Expenses:Rent  1500.00 EUR\n    need: \"essential\"\n  Assets:Checking  -1500.00 EUR\n\n2026-05-05 ! \"AUTOFIN CAR LOAN\"\n  salli-id: \"e018\"\n  source: \"statement\"\n  Liabilities:CarLoan  300.00 EUR\n  Expenses:LoanInterest  50.00 EUR\n  Assets:Checking  -350.00 EUR\n\n2026-05-08 ! \"STREAMFLIX\"\n  salli-id: \"e019\"\n  source: \"statement\"\n  Expenses:Streaming  12.99 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -12.99 EUR\n\n2026-05-09 ! \"FRESHMART\"\n  salli-id: \"e020\"\n  source: \"statement\"\n  Expenses:Groceries  176.10 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -176.10 EUR\n\n2026-05-15 ! \"CARD PAYMENT THANK YOU\"\n  salli-id: \"e021\"\n  source: \"statement\"\n  Liabilities:CreditCard  470.99 EUR\n  Assets:Checking  -470.99 EUR\n\n2026-05-18 ! \"BISTRO NOVO\"\n  salli-id: \"e023\"\n  source: \"statement\"\n  Expenses:EatingOut  88.50 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -88.50 EUR\n\n2026-05-21 ! \"FRESHMART\"\n  salli-id: \"e022\"\n  source: \"statement\"\n  Expenses:Groceries  224.30 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -224.30 EUR\n\n2026-05-25 ! \"ACME LTD SALARY\"\n  salli-id: \"e024\"\n  source: \"statement\"\n  Assets:Checking  4000.00 EUR\n  Income:Salary  -4000.00 EUR\n\n2026-05-25 ! \"ACME LTD SALARY\"\n  salli-id: \"e071\"\n  source: \"statement\"\n  Assets:Checking  4000.00 EUR\n  Income:Salary  -4000.00 EUR\n\n2026-05-25 ! \"REVERSAL: ACME LTD SALARY\"\n  salli-id: \"e072\"\n  source: \"system\"\n  external-ref: \"e071\"\n  Assets:Checking  -4000.00 EUR\n  Income:Salary  4000.00 EUR\n\n2026-05-26 ! \"TO BROKERAGE\"\n  salli-id: \"e025\"\n  source: \"statement\"\n  Assets:Brokerage  500.00 EUR\n  Assets:Checking  -500.00 EUR\n\n2026-05-26 ! \"TO SAVINGS\"\n  salli-id: \"e026\"\n  source: \"statement\"\n  Assets:Savings  300.00 EUR\n  Assets:Checking  -300.00 EUR\n\n2026-06-01 ! \"CITY LETTINGS RENT\"\n  salli-id: \"e027\"\n  source: \"statement\"\n  Expenses:Rent  1500.00 EUR\n    need: \"essential\"\n  Assets:Checking  -1500.00 EUR\n\n2026-06-05 ! \"AUTOFIN CAR LOAN\"\n  salli-id: \"e028\"\n  source: \"statement\"\n  Liabilities:CarLoan  300.00 EUR\n  Expenses:LoanInterest  50.00 EUR\n  Assets:Checking  -350.00 EUR\n\n2026-06-08 ! \"STREAMFLIX\"\n  salli-id: \"e029\"\n  source: \"statement\"\n  Expenses:Streaming  12.99 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -12.99 EUR\n\n2026-06-09 ! \"FRESHMART\"\n  salli-id: \"e030\"\n  source: \"statement\"\n  Expenses:Groceries  190.00 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -190.00 EUR\n\n2026-06-12 ! \"FRESHMART\"\n  salli-id: \"e073\"\n  source: \"statement\"\n  Expenses:Groceries  150.00 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -150.00 EUR\n\n2026-06-12 ! \"REVERSAL: FRESHMART\"\n  salli-id: \"e074\"\n  source: \"system\"\n  external-ref: \"e073\"\n  Expenses:Groceries  -150.00 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  150.00 EUR\n\n2026-06-15 ! \"CARD PAYMENT THANK YOU\"\n  salli-id: \"e031\"\n  source: \"statement\"\n  Liabilities:CreditCard  501.89 EUR\n  Assets:Checking  -501.89 EUR\n\n2026-06-18 ! \"BISTRO NOVO\"\n  salli-id: \"e033\"\n  source: \"statement\"\n  Expenses:EatingOut  71.20 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -71.20 EUR\n\n2026-06-21 ! \"FRESHMART\"\n  salli-id: \"e032\"\n  source: \"statement\"\n  Expenses:Groceries  205.50 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -205.50 EUR\n\n2026-06-25 ! \"ACME LTD SALARY\"\n  salli-id: \"e034\"\n  source: \"statement\"\n  Assets:Checking  4000.00 EUR\n  Income:Salary  -4000.00 EUR\n\n2026-06-26 ! \"TO BROKERAGE\"\n  salli-id: \"e035\"\n  source: \"statement\"\n  Assets:Brokerage  500.00 EUR\n  Assets:Checking  -500.00 EUR\n\n2026-06-26 ! \"TO SAVINGS\"\n  salli-id: \"e036\"\n  source: \"statement\"\n  Assets:Savings  300.00 EUR\n  Assets:Checking  -300.00 EUR\n\n2026-07-01 ! \"CITY LETTINGS RENT\"\n  salli-id: \"e037\"\n  source: \"statement\"\n  Expenses:Rent  1500.00 EUR\n    need: \"essential\"\n  Assets:Checking  -1500.00 EUR\n\n2026-07-05 ! \"AUTOFIN CAR LOAN\"\n  salli-id: \"e038\"\n  source: \"statement\"\n  Liabilities:CarLoan  300.00 EUR\n  Expenses:LoanInterest  50.00 EUR\n  Assets:Checking  -350.00 EUR\n\n2026-07-08 ! \"STREAMFLIX\"\n  salli-id: \"e039\"\n  source: \"statement\"\n  Expenses:Streaming  12.99 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -12.99 EUR\n\n2026-07-09 ! \"FRESHMART\"\n  salli-id: \"e040\"\n  source: \"statement\"\n  Expenses:Groceries  168.80 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -168.80 EUR\n\n2026-07-15 ! \"CARD PAYMENT THANK YOU\"\n  salli-id: \"e041\"\n  source: \"statement\"\n  Liabilities:CreditCard  479.69 EUR\n  Assets:Checking  -479.69 EUR\n\n2026-07-15 ! \"TO DOLLAR ACCOUNT\"\n  salli-id: \"e075\"\n  source: \"statement\"\n  Assets:DollarAccount  500.00 USD @ 0.95 EUR\n  Assets:Checking  -475.00 EUR\n\n2026-07-18 ! \"BISTRO NOVO\"\n  salli-id: \"e043\"\n  source: \"statement\"\n  Expenses:EatingOut  95.00 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -95.00 EUR\n\n2026-07-21 ! \"FRESHMART\"\n  salli-id: \"e042\"\n  source: \"statement\"\n  Expenses:Groceries  231.20 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -231.20 EUR\n\n2026-07-25 ! \"ACME LTD SALARY\"\n  salli-id: \"e044\"\n  source: \"statement\"\n  Assets:Checking  4000.00 EUR\n  Income:Salary  -4000.00 EUR\n\n2026-07-26 ! \"TO BROKERAGE\"\n  salli-id: \"e045\"\n  source: \"statement\"\n  Assets:Brokerage  500.00 EUR\n  Assets:Checking  -500.00 EUR\n\n2026-07-26 ! \"TO SAVINGS\"\n  salli-id: \"e046\"\n  source: \"statement\"\n  Assets:Savings  300.00 EUR\n  Assets:Checking  -300.00 EUR\n\n2026-08-01 ! \"CITY LETTINGS RENT\"\n  salli-id: \"e047\"\n  source: \"statement\"\n  Expenses:Rent  1500.00 EUR\n    need: \"essential\"\n  Assets:Checking  -1500.00 EUR\n\n2026-08-05 ! \"AUTOFIN CAR LOAN\"\n  salli-id: \"e048\"\n  source: \"statement\"\n  Liabilities:CarLoan  300.00 EUR\n  Expenses:LoanInterest  50.00 EUR\n  Assets:Checking  -350.00 EUR\n\n2026-08-08 ! \"STREAMFLIX\"\n  salli-id: \"e049\"\n  source: \"statement\"\n  Expenses:Streaming  12.99 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -12.99 EUR\n\n2026-08-09 ! \"FRESHMART\"\n  salli-id: \"e050\"\n  source: \"statement\"\n  Expenses:Groceries  185.25 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -185.25 EUR\n\n2026-08-15 ! \"CARD PAYMENT THANK YOU\"\n  salli-id: \"e051\"\n  source: \"statement\"\n  Liabilities:CreditCard  507.99 EUR\n  Assets:Checking  -507.99 EUR\n\n2026-08-18 ! \"BISTRO NOVO\"\n  salli-id: \"e053\"\n  source: \"statement\"\n  Expenses:EatingOut  58.30 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -58.30 EUR\n\n2026-08-21 ! \"FRESHMART\"\n  salli-id: \"e052\"\n  source: \"statement\"\n  Expenses:Groceries  214.75 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -214.75 EUR\n\n2026-08-25 ! \"ACME LTD SALARY\"\n  salli-id: \"e054\"\n  source: \"statement\"\n  Assets:Checking  4000.00 EUR\n  Income:Salary  -4000.00 EUR\n\n2026-08-26 ! \"TO BROKERAGE\"\n  salli-id: \"e055\"\n  source: \"statement\"\n  Assets:Brokerage  500.00 EUR\n  Assets:Checking  -500.00 EUR\n\n2026-08-26 ! \"TO SAVINGS\"\n  salli-id: \"e056\"\n  source: \"statement\"\n  Assets:Savings  300.00 EUR\n  Assets:Checking  -300.00 EUR\n\n2026-09-01 ! \"CITY LETTINGS RENT\"\n  salli-id: \"e057\"\n  source: \"statement\"\n  Expenses:Rent  1500.00 EUR\n    need: \"essential\"\n  Assets:Checking  -1500.00 EUR\n\n2026-09-05 ! \"AUTOFIN CAR LOAN\"\n  salli-id: \"e058\"\n  source: \"statement\"\n  Liabilities:CarLoan  300.00 EUR\n  Expenses:LoanInterest  50.00 EUR\n  Assets:Checking  -350.00 EUR\n\n2026-09-08 ! \"STREAMFLIX\"\n  salli-id: \"e059\"\n  source: \"statement\"\n  Expenses:Streaming  12.99 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -12.99 EUR\n\n2026-09-09 ! \"FRESHMART\"\n  salli-id: \"e060\"\n  source: \"statement\"\n  Expenses:Groceries  179.90 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -179.90 EUR\n\n2026-09-15 ! \"CARD PAYMENT THANK YOU\"\n  salli-id: \"e061\"\n  source: \"statement\"\n  Liabilities:CreditCard  471.29 EUR\n  Assets:Checking  -471.29 EUR\n\n2026-09-18 ! \"BISTRO NOVO\"\n  salli-id: \"e063\"\n  source: \"statement\"\n  Expenses:EatingOut  77.70 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -77.70 EUR\n\n2026-09-21 ! \"FRESHMART\"\n  salli-id: \"e062\"\n  source: \"statement\"\n  Expenses:Groceries  220.10 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -220.10 EUR\n\n2026-09-25 ! \"ACME LTD SALARY\"\n  salli-id: \"e064\"\n  source: \"statement\"\n  Assets:Checking  4000.00 EUR\n  Income:Salary  -4000.00 EUR\n\n2026-09-26 ! \"TO BROKERAGE\"\n  salli-id: \"e065\"\n  source: \"statement\"\n  Assets:Brokerage  500.00 EUR\n  Assets:Checking  -500.00 EUR\n\n2026-09-26 ! \"TO SAVINGS\"\n  salli-id: \"e066\"\n  source: \"statement\"\n  Assets:Savings  300.00 EUR\n  Assets:Checking  -300.00 EUR\n\n2026-10-01 ! \"CITY LETTINGS RENT\"\n  salli-id: \"e067\"\n  source: \"statement\"\n  Expenses:Rent  1500.00 EUR\n    need: \"essential\"\n  Assets:Checking  -1500.00 EUR\n\n2026-10-05 ! \"AUTOFIN CAR LOAN\"\n  salli-id: \"e068\"\n  source: \"statement\"\n  Liabilities:CarLoan  300.00 EUR\n  Expenses:LoanInterest  50.00 EUR\n  Assets:Checking  -350.00 EUR\n\n2026-10-08 ! \"STREAMFLIX\"\n  salli-id: \"e069\"\n  source: \"statement\"\n  Expenses:Streaming  12.99 EUR\n    need: \"discretionary\"\n  Liabilities:CreditCard  -12.99 EUR\n\n2026-10-09 ! \"FRESHMART\"\n  salli-id: \"e070\"\n  source: \"statement\"\n  Expenses:Groceries  188.00 EUR\n    need: \"essential\"\n  Liabilities:CreditCard  -188.00 EUR\n";

/**
 * The ledger as an hledger journal.
 */
export const HLEDGER: string = "; Exported from Salli. Every transaction carries its Salli id (salli-id).\n\naccount Assets:Brokerage  ; type:A, asset-role:investment\naccount Assets:Checking  ; type:A, asset-role:cash\naccount Assets:DollarAccount  ; type:A, asset-role:cash\naccount Assets:Flat  ; type:A, asset-role:other\naccount Assets:PensionFund  ; type:A, asset-role:investment\naccount Assets:Savings  ; type:A, asset-role:cash\naccount Equity:OpeningEquity  ; type:E\naccount Expenses:EatingOut  ; type:X\naccount Expenses:Groceries  ; type:X\naccount Expenses:LoanInterest  ; type:X\naccount Expenses:Rent  ; type:X\naccount Expenses:Streaming  ; type:X\naccount Income:Salary  ; type:R\naccount Liabilities:CarLoan  ; type:L\naccount Liabilities:CreditCard  ; type:L\n\n2026-03-31 ! Opening balance  ; salli-id:e001, source:manual\n    Assets:Checking  3200.00 EUR\n    Equity:OpeningEquity  -3200.00 EUR\n\n2026-03-31 ! Opening balance  ; salli-id:e002, source:manual\n    Assets:Savings  6000.00 EUR\n    Equity:OpeningEquity  -6000.00 EUR\n\n2026-03-31 ! Opening balance  ; salli-id:e003, source:manual\n    Assets:Brokerage  10000.00 EUR\n    Equity:OpeningEquity  -10000.00 EUR\n\n2026-03-31 ! Opening balance  ; salli-id:e004, source:manual\n    Assets:PensionFund  25000.00 EUR\n    Equity:OpeningEquity  -25000.00 EUR\n\n2026-03-31 ! Opening balance  ; salli-id:e005, source:manual\n    Assets:Flat  300000.00 EUR\n    Equity:OpeningEquity  -300000.00 EUR\n\n2026-03-31 ! Opening balance  ; salli-id:e006, source:manual\n    Assets:DollarAccount  2000.00 USD @ 0.9 EUR\n    Equity:OpeningEquity  -1800.00 EUR\n\n2026-03-31 ! Opening balance  ; salli-id:e007, source:manual\n    Equity:OpeningEquity  12000.00 EUR\n    Liabilities:CarLoan  -12000.00 EUR\n\n2026-04-01 ! CITY LETTINGS RENT  ; salli-id:e008, source:statement\n    Expenses:Rent  1500.00 EUR  ; need:essential\n    Assets:Checking  -1500.00 EUR\n\n2026-04-05 ! AUTOFIN CAR LOAN  ; salli-id:e009, source:statement\n    Liabilities:CarLoan  300.00 EUR\n    Expenses:LoanInterest  50.00 EUR\n    Assets:Checking  -350.00 EUR\n\n2026-04-08 ! STREAMFLIX  ; salli-id:e010, source:statement\n    Expenses:Streaming  12.99 EUR  ; need:discretionary\n    Liabilities:CreditCard  -12.99 EUR\n\n2026-04-09 ! FRESHMART  ; salli-id:e011, source:statement\n    Expenses:Groceries  182.40 EUR  ; need:essential\n    Liabilities:CreditCard  -182.40 EUR\n\n2026-04-18 ! BISTRO NOVO  ; salli-id:e013, source:statement\n    Expenses:EatingOut  64.00 EUR  ; need:discretionary\n    Liabilities:CreditCard  -64.00 EUR\n\n2026-04-21 ! FRESHMART  ; salli-id:e012, source:statement\n    Expenses:Groceries  211.60 EUR  ; need:essential\n    Liabilities:CreditCard  -211.60 EUR\n\n2026-04-25 ! ACME LTD SALARY  ; salli-id:e014, source:statement\n    Assets:Checking  4000.00 EUR\n    Income:Salary  -4000.00 EUR\n\n2026-04-26 ! TO BROKERAGE  ; salli-id:e015, source:statement\n    Assets:Brokerage  500.00 EUR\n    Assets:Checking  -500.00 EUR\n\n2026-04-26 ! TO SAVINGS  ; salli-id:e016, source:statement\n    Assets:Savings  300.00 EUR\n    Assets:Checking  -300.00 EUR\n\n2026-05-01 ! CITY LETTINGS RENT  ; salli-id:e017, source:statement\n    Expenses:Rent  1500.00 EUR  ; need:essential\n    Assets:Checking  -1500.00 EUR\n\n2026-05-05 ! AUTOFIN CAR LOAN  ; salli-id:e018, source:statement\n    Liabilities:CarLoan  300.00 EUR\n    Expenses:LoanInterest  50.00 EUR\n    Assets:Checking  -350.00 EUR\n\n2026-05-08 ! STREAMFLIX  ; salli-id:e019, source:statement\n    Expenses:Streaming  12.99 EUR  ; need:discretionary\n    Liabilities:CreditCard  -12.99 EUR\n\n2026-05-09 ! FRESHMART  ; salli-id:e020, source:statement\n    Expenses:Groceries  176.10 EUR  ; need:essential\n    Liabilities:CreditCard  -176.10 EUR\n\n2026-05-15 ! CARD PAYMENT THANK YOU  ; salli-id:e021, source:statement\n    Liabilities:CreditCard  470.99 EUR\n    Assets:Checking  -470.99 EUR\n\n2026-05-18 ! BISTRO NOVO  ; salli-id:e023, source:statement\n    Expenses:EatingOut  88.50 EUR  ; need:discretionary\n    Liabilities:CreditCard  -88.50 EUR\n\n2026-05-21 ! FRESHMART  ; salli-id:e022, source:statement\n    Expenses:Groceries  224.30 EUR  ; need:essential\n    Liabilities:CreditCard  -224.30 EUR\n\n2026-05-25 ! ACME LTD SALARY  ; salli-id:e024, source:statement\n    Assets:Checking  4000.00 EUR\n    Income:Salary  -4000.00 EUR\n\n2026-05-25 ! ACME LTD SALARY  ; salli-id:e071, source:statement\n    Assets:Checking  4000.00 EUR\n    Income:Salary  -4000.00 EUR\n\n2026-05-25 ! REVERSAL: ACME LTD SALARY  ; salli-id:e072, source:system\n    Assets:Checking  -4000.00 EUR\n    Income:Salary  4000.00 EUR\n\n2026-05-26 ! TO BROKERAGE  ; salli-id:e025, source:statement\n    Assets:Brokerage  500.00 EUR\n    Assets:Checking  -500.00 EUR\n\n2026-05-26 ! TO SAVINGS  ; salli-id:e026, source:statement\n    Assets:Savings  300.00 EUR\n    Assets:Checking  -300.00 EUR\n\n2026-06-01 ! CITY LETTINGS RENT  ; salli-id:e027, source:statement\n    Expenses:Rent  1500.00 EUR  ; need:essential\n    Assets:Checking  -1500.00 EUR\n\n2026-06-05 ! AUTOFIN CAR LOAN  ; salli-id:e028, source:statement\n    Liabilities:CarLoan  300.00 EUR\n    Expenses:LoanInterest  50.00 EUR\n    Assets:Checking  -350.00 EUR\n\n2026-06-08 ! STREAMFLIX  ; salli-id:e029, source:statement\n    Expenses:Streaming  12.99 EUR  ; need:discretionary\n    Liabilities:CreditCard  -12.99 EUR\n\n2026-06-09 ! FRESHMART  ; salli-id:e030, source:statement\n    Expenses:Groceries  190.00 EUR  ; need:essential\n    Liabilities:CreditCard  -190.00 EUR\n\n2026-06-12 ! FRESHMART  ; salli-id:e073, source:statement\n    Expenses:Groceries  150.00 EUR  ; need:essential\n    Liabilities:CreditCard  -150.00 EUR\n\n2026-06-12 ! REVERSAL: FRESHMART  ; salli-id:e074, source:system\n    Expenses:Groceries  -150.00 EUR  ; need:essential\n    Liabilities:CreditCard  150.00 EUR\n\n2026-06-15 ! CARD PAYMENT THANK YOU  ; salli-id:e031, source:statement\n    Liabilities:CreditCard  501.89 EUR\n    Assets:Checking  -501.89 EUR\n\n2026-06-18 ! BISTRO NOVO  ; salli-id:e033, source:statement\n    Expenses:EatingOut  71.20 EUR  ; need:discretionary\n    Liabilities:CreditCard  -71.20 EUR\n\n2026-06-21 ! FRESHMART  ; salli-id:e032, source:statement\n    Expenses:Groceries  205.50 EUR  ; need:essential\n    Liabilities:CreditCard  -205.50 EUR\n\n2026-06-25 ! ACME LTD SALARY  ; salli-id:e034, source:statement\n    Assets:Checking  4000.00 EUR\n    Income:Salary  -4000.00 EUR\n\n2026-06-26 ! TO BROKERAGE  ; salli-id:e035, source:statement\n    Assets:Brokerage  500.00 EUR\n    Assets:Checking  -500.00 EUR\n\n2026-06-26 ! TO SAVINGS  ; salli-id:e036, source:statement\n    Assets:Savings  300.00 EUR\n    Assets:Checking  -300.00 EUR\n\n2026-07-01 ! CITY LETTINGS RENT  ; salli-id:e037, source:statement\n    Expenses:Rent  1500.00 EUR  ; need:essential\n    Assets:Checking  -1500.00 EUR\n\n2026-07-05 ! AUTOFIN CAR LOAN  ; salli-id:e038, source:statement\n    Liabilities:CarLoan  300.00 EUR\n    Expenses:LoanInterest  50.00 EUR\n    Assets:Checking  -350.00 EUR\n\n2026-07-08 ! STREAMFLIX  ; salli-id:e039, source:statement\n    Expenses:Streaming  12.99 EUR  ; need:discretionary\n    Liabilities:CreditCard  -12.99 EUR\n\n2026-07-09 ! FRESHMART  ; salli-id:e040, source:statement\n    Expenses:Groceries  168.80 EUR  ; need:essential\n    Liabilities:CreditCard  -168.80 EUR\n\n2026-07-15 ! CARD PAYMENT THANK YOU  ; salli-id:e041, source:statement\n    Liabilities:CreditCard  479.69 EUR\n    Assets:Checking  -479.69 EUR\n\n2026-07-15 ! TO DOLLAR ACCOUNT  ; salli-id:e075, source:statement\n    Assets:DollarAccount  500.00 USD @ 0.95 EUR\n    Assets:Checking  -475.00 EUR\n\n2026-07-18 ! BISTRO NOVO  ; salli-id:e043, source:statement\n    Expenses:EatingOut  95.00 EUR  ; need:discretionary\n    Liabilities:CreditCard  -95.00 EUR\n\n2026-07-21 ! FRESHMART  ; salli-id:e042, source:statement\n    Expenses:Groceries  231.20 EUR  ; need:essential\n    Liabilities:CreditCard  -231.20 EUR\n\n2026-07-25 ! ACME LTD SALARY  ; salli-id:e044, source:statement\n    Assets:Checking  4000.00 EUR\n    Income:Salary  -4000.00 EUR\n\n2026-07-26 ! TO BROKERAGE  ; salli-id:e045, source:statement\n    Assets:Brokerage  500.00 EUR\n    Assets:Checking  -500.00 EUR\n\n2026-07-26 ! TO SAVINGS  ; salli-id:e046, source:statement\n    Assets:Savings  300.00 EUR\n    Assets:Checking  -300.00 EUR\n\n2026-08-01 ! CITY LETTINGS RENT  ; salli-id:e047, source:statement\n    Expenses:Rent  1500.00 EUR  ; need:essential\n    Assets:Checking  -1500.00 EUR\n\n2026-08-05 ! AUTOFIN CAR LOAN  ; salli-id:e048, source:statement\n    Liabilities:CarLoan  300.00 EUR\n    Expenses:LoanInterest  50.00 EUR\n    Assets:Checking  -350.00 EUR\n\n2026-08-08 ! STREAMFLIX  ; salli-id:e049, source:statement\n    Expenses:Streaming  12.99 EUR  ; need:discretionary\n    Liabilities:CreditCard  -12.99 EUR\n\n2026-08-09 ! FRESHMART  ; salli-id:e050, source:statement\n    Expenses:Groceries  185.25 EUR  ; need:essential\n    Liabilities:CreditCard  -185.25 EUR\n\n2026-08-15 ! CARD PAYMENT THANK YOU  ; salli-id:e051, source:statement\n    Liabilities:CreditCard  507.99 EUR\n    Assets:Checking  -507.99 EUR\n\n2026-08-18 ! BISTRO NOVO  ; salli-id:e053, source:statement\n    Expenses:EatingOut  58.30 EUR  ; need:discretionary\n    Liabilities:CreditCard  -58.30 EUR\n\n2026-08-21 ! FRESHMART  ; salli-id:e052, source:statement\n    Expenses:Groceries  214.75 EUR  ; need:essential\n    Liabilities:CreditCard  -214.75 EUR\n\n2026-08-25 ! ACME LTD SALARY  ; salli-id:e054, source:statement\n    Assets:Checking  4000.00 EUR\n    Income:Salary  -4000.00 EUR\n\n2026-08-26 ! TO BROKERAGE  ; salli-id:e055, source:statement\n    Assets:Brokerage  500.00 EUR\n    Assets:Checking  -500.00 EUR\n\n2026-08-26 ! TO SAVINGS  ; salli-id:e056, source:statement\n    Assets:Savings  300.00 EUR\n    Assets:Checking  -300.00 EUR\n\n2026-09-01 ! CITY LETTINGS RENT  ; salli-id:e057, source:statement\n    Expenses:Rent  1500.00 EUR  ; need:essential\n    Assets:Checking  -1500.00 EUR\n\n2026-09-05 ! AUTOFIN CAR LOAN  ; salli-id:e058, source:statement\n    Liabilities:CarLoan  300.00 EUR\n    Expenses:LoanInterest  50.00 EUR\n    Assets:Checking  -350.00 EUR\n\n2026-09-08 ! STREAMFLIX  ; salli-id:e059, source:statement\n    Expenses:Streaming  12.99 EUR  ; need:discretionary\n    Liabilities:CreditCard  -12.99 EUR\n\n2026-09-09 ! FRESHMART  ; salli-id:e060, source:statement\n    Expenses:Groceries  179.90 EUR  ; need:essential\n    Liabilities:CreditCard  -179.90 EUR\n\n2026-09-15 ! CARD PAYMENT THANK YOU  ; salli-id:e061, source:statement\n    Liabilities:CreditCard  471.29 EUR\n    Assets:Checking  -471.29 EUR\n\n2026-09-18 ! BISTRO NOVO  ; salli-id:e063, source:statement\n    Expenses:EatingOut  77.70 EUR  ; need:discretionary\n    Liabilities:CreditCard  -77.70 EUR\n\n2026-09-21 ! FRESHMART  ; salli-id:e062, source:statement\n    Expenses:Groceries  220.10 EUR  ; need:essential\n    Liabilities:CreditCard  -220.10 EUR\n\n2026-09-25 ! ACME LTD SALARY  ; salli-id:e064, source:statement\n    Assets:Checking  4000.00 EUR\n    Income:Salary  -4000.00 EUR\n\n2026-09-26 ! TO BROKERAGE  ; salli-id:e065, source:statement\n    Assets:Brokerage  500.00 EUR\n    Assets:Checking  -500.00 EUR\n\n2026-09-26 ! TO SAVINGS  ; salli-id:e066, source:statement\n    Assets:Savings  300.00 EUR\n    Assets:Checking  -300.00 EUR\n\n2026-10-01 ! CITY LETTINGS RENT  ; salli-id:e067, source:statement\n    Expenses:Rent  1500.00 EUR  ; need:essential\n    Assets:Checking  -1500.00 EUR\n\n2026-10-05 ! AUTOFIN CAR LOAN  ; salli-id:e068, source:statement\n    Liabilities:CarLoan  300.00 EUR\n    Expenses:LoanInterest  50.00 EUR\n    Assets:Checking  -350.00 EUR\n\n2026-10-08 ! STREAMFLIX  ; salli-id:e069, source:statement\n    Expenses:Streaming  12.99 EUR  ; need:discretionary\n    Liabilities:CreditCard  -12.99 EUR\n\n2026-10-09 ! FRESHMART  ; salli-id:e070, source:statement\n    Expenses:Groceries  188.00 EUR  ; need:essential\n    Liabilities:CreditCard  -188.00 EUR\n";

/**
 * A token made with tax:activate: its secret, shown this once (a fixture's).
 */
export const TOKEN_MADE: NewPersonalAccessToken = {
  "id": "0000233f-5a11-4000-8000-000000009023",
  "name": "Tax helper",
  "prefix": "salli_pat_fixt",
  "permissions": [
    "tax:activate"
  ],
  "created_at": "2026-10-11T10:00:00Z",
  "expires_at": null,
  "last_used_at": null,
  "token": "salli_pat_fixture-tax-helper-not-a-secret000000000000"
};

/**
 * The same, asked for by a console sign-in six minutes after the password.
 */
export const TOKEN_STEP_UP: ProblemDetails = {
  "type": "/problems/step-up-required",
  "title": "Sign in again",
  "status": 403,
  "detail": "tax:activate needs your password, entered in the last 5 minutes. Sign in again on Salli's sign-in page, then try again.",
  "max_age": 300
};

/**
 * A token with no name.
 */
export const TOKEN_REFUSED: ProblemDetails = {
  "type": "/problems/validation",
  "title": "Request validation failed",
  "status": 422,
  "detail": [
    {
      "type": "string_too_short",
      "loc": [
        "body",
        "name"
      ],
      "msg": "String should have at least 1 character"
    }
  ]
};

/**
 * A key OpenAI refuses.
 */
export const KEY_REFUSED: ProblemDetails = {
  "type": "about:blank",
  "title": "Salli didn't do this",
  "status": 400,
  "detail": {
    "error": "invalid_key",
    "provider": "openai",
    "message": "OpenAI rejected this key. Check you pasted it whole, and that it's still active."
  }
};

/**
 * Monthly instead, at 7.
 */
export const PREFERENCES_SAVED: NotificationPreferences = {
  "enabled": true,
  "cadence": "monthly",
  "weekday": "monday",
  "hour": 7,
  "items": [
    "decision_review_due",
    "reminder_due",
    "filing_deadline",
    "cash_below_zero_ahead"
  ],
  "time_zone": "Europe/Lisbon",
  "next_at": "2026-11-02T07:00:00+00:00",
  "sender_enabled": true
};
