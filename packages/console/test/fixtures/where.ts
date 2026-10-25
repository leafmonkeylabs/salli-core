/**
 * What a real server answers the pages of where you stand (C2: the
 * accounts and the ledger, cash, attention, financial independence;
 * docs/design/console.md, section 5) on the golden household ledger
 * (tests/golden/household.py, as of Oct 11, 2026, in euros), on what
 * Home's fixtures (home.ts) rest on and one reminder of the person's own
 * marked done. The writes at the end (an entry posted and reversed, one
 * posted in dollars, two refused, an FI assumption set and one refused)
 * come after every read, so the reads are what the console sees first.
 *
 * Written by tests/console_fixtures.py (`uv run python -m tests.console_fixtures`):
 * tests/contract/test_console_fixtures.py fails while it differs from what
 * the server answers. Don't edit it by hand.
 */
import type { AccountOverview, CashFlow, CashForecast, EntryProvenance, FiAssumptionsReport, FiProjections, FiScore, FiScoreHistory, JournalEntry, ProblemDetails, Ref, ReminderList, Spending, TrialBalance } from '@leafmonkeylabs/salli-sdk';

export const TRIAL_BALANCE: TrialBalance = {
  "currency": "EUR",
  "balances": {
    "chk": "6543.15",
    "eq": "-334000.00",
    "sav": "7800.00",
    "brk": "13000.00",
    "pen": "25000.00",
    "flat": "300000.00",
    "usd": "2275.00",
    "loan": "-9900.00",
    "rent": "10500.00",
    "int": "350.00",
    "tv": "90.93",
    "card": "-691.68",
    "food": "2577.90",
    "out": "454.70",
    "sal": "-24000.00"
  },
  "net": "0.00"
};

/**
 * Every account's overview: its balances and its entries, each with the
 * running balance after it.
 */
export const OVERVIEWS: AccountOverview[] = [
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "6543.15",
    "balance": "6543.15",
    "transactions": [
      {
        "entry_id": "e001",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "3200.00",
        "running_balance_native": "3200.00"
      },
      {
        "entry_id": "e008",
        "entry_date": "2026-04-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "1700.00",
        "running_balance_native": "1700.00"
      },
      {
        "entry_id": "e009",
        "entry_date": "2026-04-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "1350.00",
        "running_balance_native": "1350.00"
      },
      {
        "entry_id": "e014",
        "entry_date": "2026-04-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "5350.00",
        "running_balance_native": "5350.00"
      },
      {
        "entry_id": "e015",
        "entry_date": "2026-04-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "4850.00",
        "running_balance_native": "4850.00"
      },
      {
        "entry_id": "e016",
        "entry_date": "2026-04-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "4550.00",
        "running_balance_native": "4550.00"
      },
      {
        "entry_id": "e017",
        "entry_date": "2026-05-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "3050.00",
        "running_balance_native": "3050.00"
      },
      {
        "entry_id": "e018",
        "entry_date": "2026-05-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "2700.00",
        "running_balance_native": "2700.00"
      },
      {
        "entry_id": "e021",
        "entry_date": "2026-05-15",
        "description": "CARD PAYMENT THANK YOU",
        "source": "statement",
        "external_ref": null,
        "running_balance": "2229.01",
        "running_balance_native": "2229.01"
      },
      {
        "entry_id": "e024",
        "entry_date": "2026-05-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6229.01",
        "running_balance_native": "6229.01"
      },
      {
        "entry_id": "e071",
        "entry_date": "2026-05-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "10229.01",
        "running_balance_native": "10229.01"
      },
      {
        "entry_id": "e072",
        "entry_date": "2026-05-25",
        "description": "REVERSAL: ACME LTD SALARY",
        "source": "system",
        "external_ref": "e071",
        "running_balance": "6229.01",
        "running_balance_native": "6229.01"
      },
      {
        "entry_id": "e025",
        "entry_date": "2026-05-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "5729.01",
        "running_balance_native": "5729.01"
      },
      {
        "entry_id": "e026",
        "entry_date": "2026-05-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "5429.01",
        "running_balance_native": "5429.01"
      },
      {
        "entry_id": "e027",
        "entry_date": "2026-06-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "3929.01",
        "running_balance_native": "3929.01"
      },
      {
        "entry_id": "e028",
        "entry_date": "2026-06-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "3579.01",
        "running_balance_native": "3579.01"
      },
      {
        "entry_id": "e031",
        "entry_date": "2026-06-15",
        "description": "CARD PAYMENT THANK YOU",
        "source": "statement",
        "external_ref": null,
        "running_balance": "3077.12",
        "running_balance_native": "3077.12"
      },
      {
        "entry_id": "e034",
        "entry_date": "2026-06-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "7077.12",
        "running_balance_native": "7077.12"
      },
      {
        "entry_id": "e035",
        "entry_date": "2026-06-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6577.12",
        "running_balance_native": "6577.12"
      },
      {
        "entry_id": "e036",
        "entry_date": "2026-06-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6277.12",
        "running_balance_native": "6277.12"
      },
      {
        "entry_id": "e037",
        "entry_date": "2026-07-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "4777.12",
        "running_balance_native": "4777.12"
      },
      {
        "entry_id": "e038",
        "entry_date": "2026-07-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "4427.12",
        "running_balance_native": "4427.12"
      },
      {
        "entry_id": "e041",
        "entry_date": "2026-07-15",
        "description": "CARD PAYMENT THANK YOU",
        "source": "statement",
        "external_ref": null,
        "running_balance": "3947.43",
        "running_balance_native": "3947.43"
      },
      {
        "entry_id": "e075",
        "entry_date": "2026-07-15",
        "description": "TO DOLLAR ACCOUNT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "3472.43",
        "running_balance_native": "3472.43"
      },
      {
        "entry_id": "e044",
        "entry_date": "2026-07-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "7472.43",
        "running_balance_native": "7472.43"
      },
      {
        "entry_id": "e045",
        "entry_date": "2026-07-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6972.43",
        "running_balance_native": "6972.43"
      },
      {
        "entry_id": "e046",
        "entry_date": "2026-07-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6672.43",
        "running_balance_native": "6672.43"
      },
      {
        "entry_id": "e047",
        "entry_date": "2026-08-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "5172.43",
        "running_balance_native": "5172.43"
      },
      {
        "entry_id": "e048",
        "entry_date": "2026-08-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "4822.43",
        "running_balance_native": "4822.43"
      },
      {
        "entry_id": "e051",
        "entry_date": "2026-08-15",
        "description": "CARD PAYMENT THANK YOU",
        "source": "statement",
        "external_ref": null,
        "running_balance": "4314.44",
        "running_balance_native": "4314.44"
      },
      {
        "entry_id": "e054",
        "entry_date": "2026-08-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "8314.44",
        "running_balance_native": "8314.44"
      },
      {
        "entry_id": "e055",
        "entry_date": "2026-08-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "7814.44",
        "running_balance_native": "7814.44"
      },
      {
        "entry_id": "e056",
        "entry_date": "2026-08-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "7514.44",
        "running_balance_native": "7514.44"
      },
      {
        "entry_id": "e057",
        "entry_date": "2026-09-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6014.44",
        "running_balance_native": "6014.44"
      },
      {
        "entry_id": "e058",
        "entry_date": "2026-09-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "5664.44",
        "running_balance_native": "5664.44"
      },
      {
        "entry_id": "e061",
        "entry_date": "2026-09-15",
        "description": "CARD PAYMENT THANK YOU",
        "source": "statement",
        "external_ref": null,
        "running_balance": "5193.15",
        "running_balance_native": "5193.15"
      },
      {
        "entry_id": "e064",
        "entry_date": "2026-09-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "9193.15",
        "running_balance_native": "9193.15"
      },
      {
        "entry_id": "e065",
        "entry_date": "2026-09-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "8693.15",
        "running_balance_native": "8693.15"
      },
      {
        "entry_id": "e066",
        "entry_date": "2026-09-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "8393.15",
        "running_balance_native": "8393.15"
      },
      {
        "entry_id": "e067",
        "entry_date": "2026-10-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6893.15",
        "running_balance_native": "6893.15"
      },
      {
        "entry_id": "e068",
        "entry_date": "2026-10-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6543.15",
        "running_balance_native": "6543.15"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "7800.00",
    "balance": "7800.00",
    "transactions": [
      {
        "entry_id": "e002",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "6000.00",
        "running_balance_native": "6000.00"
      },
      {
        "entry_id": "e016",
        "entry_date": "2026-04-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6300.00",
        "running_balance_native": "6300.00"
      },
      {
        "entry_id": "e026",
        "entry_date": "2026-05-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6600.00",
        "running_balance_native": "6600.00"
      },
      {
        "entry_id": "e036",
        "entry_date": "2026-06-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6900.00",
        "running_balance_native": "6900.00"
      },
      {
        "entry_id": "e046",
        "entry_date": "2026-07-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "7200.00",
        "running_balance_native": "7200.00"
      },
      {
        "entry_id": "e056",
        "entry_date": "2026-08-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "7500.00",
        "running_balance_native": "7500.00"
      },
      {
        "entry_id": "e066",
        "entry_date": "2026-09-26",
        "description": "TO SAVINGS",
        "source": "statement",
        "external_ref": null,
        "running_balance": "7800.00",
        "running_balance_native": "7800.00"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "2275.00",
    "balance": "2500.00",
    "transactions": [
      {
        "entry_id": "e006",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "1800.00",
        "running_balance_native": "2000.00"
      },
      {
        "entry_id": "e075",
        "entry_date": "2026-07-15",
        "description": "TO DOLLAR ACCOUNT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "2275.00",
        "running_balance_native": "2500.00"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "13000.00",
    "balance": "13000.00",
    "transactions": [
      {
        "entry_id": "e003",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "10000.00",
        "running_balance_native": "10000.00"
      },
      {
        "entry_id": "e015",
        "entry_date": "2026-04-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "10500.00",
        "running_balance_native": "10500.00"
      },
      {
        "entry_id": "e025",
        "entry_date": "2026-05-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "11000.00",
        "running_balance_native": "11000.00"
      },
      {
        "entry_id": "e035",
        "entry_date": "2026-06-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "11500.00",
        "running_balance_native": "11500.00"
      },
      {
        "entry_id": "e045",
        "entry_date": "2026-07-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "12000.00",
        "running_balance_native": "12000.00"
      },
      {
        "entry_id": "e055",
        "entry_date": "2026-08-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "12500.00",
        "running_balance_native": "12500.00"
      },
      {
        "entry_id": "e065",
        "entry_date": "2026-09-26",
        "description": "TO BROKERAGE",
        "source": "statement",
        "external_ref": null,
        "running_balance": "13000.00",
        "running_balance_native": "13000.00"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "25000.00",
    "balance": "25000.00",
    "transactions": [
      {
        "entry_id": "e004",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "25000.00",
        "running_balance_native": "25000.00"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "300000.00",
    "balance": "300000.00",
    "transactions": [
      {
        "entry_id": "e005",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "300000.00",
        "running_balance_native": "300000.00"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "-691.68",
    "balance": "-691.68",
    "transactions": [
      {
        "entry_id": "e010",
        "entry_date": "2026-04-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-12.99",
        "running_balance_native": "-12.99"
      },
      {
        "entry_id": "e011",
        "entry_date": "2026-04-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-195.39",
        "running_balance_native": "-195.39"
      },
      {
        "entry_id": "e013",
        "entry_date": "2026-04-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-259.39",
        "running_balance_native": "-259.39"
      },
      {
        "entry_id": "e012",
        "entry_date": "2026-04-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-470.99",
        "running_balance_native": "-470.99"
      },
      {
        "entry_id": "e019",
        "entry_date": "2026-05-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-483.98",
        "running_balance_native": "-483.98"
      },
      {
        "entry_id": "e020",
        "entry_date": "2026-05-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-660.08",
        "running_balance_native": "-660.08"
      },
      {
        "entry_id": "e021",
        "entry_date": "2026-05-15",
        "description": "CARD PAYMENT THANK YOU",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-189.09",
        "running_balance_native": "-189.09"
      },
      {
        "entry_id": "e023",
        "entry_date": "2026-05-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-277.59",
        "running_balance_native": "-277.59"
      },
      {
        "entry_id": "e022",
        "entry_date": "2026-05-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-501.89",
        "running_balance_native": "-501.89"
      },
      {
        "entry_id": "e029",
        "entry_date": "2026-06-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-514.88",
        "running_balance_native": "-514.88"
      },
      {
        "entry_id": "e030",
        "entry_date": "2026-06-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-704.88",
        "running_balance_native": "-704.88"
      },
      {
        "entry_id": "e073",
        "entry_date": "2026-06-12",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-854.88",
        "running_balance_native": "-854.88"
      },
      {
        "entry_id": "e074",
        "entry_date": "2026-06-12",
        "description": "REVERSAL: FRESHMART",
        "source": "system",
        "external_ref": "e073",
        "running_balance": "-704.88",
        "running_balance_native": "-704.88"
      },
      {
        "entry_id": "e031",
        "entry_date": "2026-06-15",
        "description": "CARD PAYMENT THANK YOU",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-202.99",
        "running_balance_native": "-202.99"
      },
      {
        "entry_id": "e033",
        "entry_date": "2026-06-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-274.19",
        "running_balance_native": "-274.19"
      },
      {
        "entry_id": "e032",
        "entry_date": "2026-06-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-479.69",
        "running_balance_native": "-479.69"
      },
      {
        "entry_id": "e039",
        "entry_date": "2026-07-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-492.68",
        "running_balance_native": "-492.68"
      },
      {
        "entry_id": "e040",
        "entry_date": "2026-07-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-661.48",
        "running_balance_native": "-661.48"
      },
      {
        "entry_id": "e041",
        "entry_date": "2026-07-15",
        "description": "CARD PAYMENT THANK YOU",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-181.79",
        "running_balance_native": "-181.79"
      },
      {
        "entry_id": "e043",
        "entry_date": "2026-07-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-276.79",
        "running_balance_native": "-276.79"
      },
      {
        "entry_id": "e042",
        "entry_date": "2026-07-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-507.99",
        "running_balance_native": "-507.99"
      },
      {
        "entry_id": "e049",
        "entry_date": "2026-08-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-520.98",
        "running_balance_native": "-520.98"
      },
      {
        "entry_id": "e050",
        "entry_date": "2026-08-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-706.23",
        "running_balance_native": "-706.23"
      },
      {
        "entry_id": "e051",
        "entry_date": "2026-08-15",
        "description": "CARD PAYMENT THANK YOU",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-198.24",
        "running_balance_native": "-198.24"
      },
      {
        "entry_id": "e053",
        "entry_date": "2026-08-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-256.54",
        "running_balance_native": "-256.54"
      },
      {
        "entry_id": "e052",
        "entry_date": "2026-08-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-471.29",
        "running_balance_native": "-471.29"
      },
      {
        "entry_id": "e059",
        "entry_date": "2026-09-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-484.28",
        "running_balance_native": "-484.28"
      },
      {
        "entry_id": "e060",
        "entry_date": "2026-09-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-664.18",
        "running_balance_native": "-664.18"
      },
      {
        "entry_id": "e061",
        "entry_date": "2026-09-15",
        "description": "CARD PAYMENT THANK YOU",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-192.89",
        "running_balance_native": "-192.89"
      },
      {
        "entry_id": "e063",
        "entry_date": "2026-09-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-270.59",
        "running_balance_native": "-270.59"
      },
      {
        "entry_id": "e062",
        "entry_date": "2026-09-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-490.69",
        "running_balance_native": "-490.69"
      },
      {
        "entry_id": "e069",
        "entry_date": "2026-10-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-503.68",
        "running_balance_native": "-503.68"
      },
      {
        "entry_id": "e070",
        "entry_date": "2026-10-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-691.68",
        "running_balance_native": "-691.68"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "-9900.00",
    "balance": "-9900.00",
    "transactions": [
      {
        "entry_id": "e007",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "-12000.00",
        "running_balance_native": "-12000.00"
      },
      {
        "entry_id": "e009",
        "entry_date": "2026-04-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-11700.00",
        "running_balance_native": "-11700.00"
      },
      {
        "entry_id": "e018",
        "entry_date": "2026-05-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-11400.00",
        "running_balance_native": "-11400.00"
      },
      {
        "entry_id": "e028",
        "entry_date": "2026-06-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-11100.00",
        "running_balance_native": "-11100.00"
      },
      {
        "entry_id": "e038",
        "entry_date": "2026-07-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-10800.00",
        "running_balance_native": "-10800.00"
      },
      {
        "entry_id": "e048",
        "entry_date": "2026-08-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-10500.00",
        "running_balance_native": "-10500.00"
      },
      {
        "entry_id": "e058",
        "entry_date": "2026-09-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-10200.00",
        "running_balance_native": "-10200.00"
      },
      {
        "entry_id": "e068",
        "entry_date": "2026-10-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-9900.00",
        "running_balance_native": "-9900.00"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "-334000.00",
    "balance": "-334000.00",
    "transactions": [
      {
        "entry_id": "e001",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "-3200.00",
        "running_balance_native": "-3200.00"
      },
      {
        "entry_id": "e002",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "-9200.00",
        "running_balance_native": "-9200.00"
      },
      {
        "entry_id": "e003",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "-19200.00",
        "running_balance_native": "-19200.00"
      },
      {
        "entry_id": "e004",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "-44200.00",
        "running_balance_native": "-44200.00"
      },
      {
        "entry_id": "e005",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "-344200.00",
        "running_balance_native": "-344200.00"
      },
      {
        "entry_id": "e006",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "-346000.00",
        "running_balance_native": "-346000.00"
      },
      {
        "entry_id": "e007",
        "entry_date": "2026-03-31",
        "description": "Opening balance",
        "source": "manual",
        "external_ref": null,
        "running_balance": "-334000.00",
        "running_balance_native": "-334000.00"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "-24000.00",
    "balance": "-24000.00",
    "transactions": [
      {
        "entry_id": "e014",
        "entry_date": "2026-04-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-4000.00",
        "running_balance_native": "-4000.00"
      },
      {
        "entry_id": "e024",
        "entry_date": "2026-05-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-8000.00",
        "running_balance_native": "-8000.00"
      },
      {
        "entry_id": "e071",
        "entry_date": "2026-05-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-12000.00",
        "running_balance_native": "-12000.00"
      },
      {
        "entry_id": "e072",
        "entry_date": "2026-05-25",
        "description": "REVERSAL: ACME LTD SALARY",
        "source": "system",
        "external_ref": "e071",
        "running_balance": "-8000.00",
        "running_balance_native": "-8000.00"
      },
      {
        "entry_id": "e034",
        "entry_date": "2026-06-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-12000.00",
        "running_balance_native": "-12000.00"
      },
      {
        "entry_id": "e044",
        "entry_date": "2026-07-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-16000.00",
        "running_balance_native": "-16000.00"
      },
      {
        "entry_id": "e054",
        "entry_date": "2026-08-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-20000.00",
        "running_balance_native": "-20000.00"
      },
      {
        "entry_id": "e064",
        "entry_date": "2026-09-25",
        "description": "ACME LTD SALARY",
        "source": "statement",
        "external_ref": null,
        "running_balance": "-24000.00",
        "running_balance_native": "-24000.00"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "10500.00",
    "balance": "10500.00",
    "transactions": [
      {
        "entry_id": "e008",
        "entry_date": "2026-04-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "1500.00",
        "running_balance_native": "1500.00"
      },
      {
        "entry_id": "e017",
        "entry_date": "2026-05-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "3000.00",
        "running_balance_native": "3000.00"
      },
      {
        "entry_id": "e027",
        "entry_date": "2026-06-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "4500.00",
        "running_balance_native": "4500.00"
      },
      {
        "entry_id": "e037",
        "entry_date": "2026-07-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "6000.00",
        "running_balance_native": "6000.00"
      },
      {
        "entry_id": "e047",
        "entry_date": "2026-08-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "7500.00",
        "running_balance_native": "7500.00"
      },
      {
        "entry_id": "e057",
        "entry_date": "2026-09-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "9000.00",
        "running_balance_native": "9000.00"
      },
      {
        "entry_id": "e067",
        "entry_date": "2026-10-01",
        "description": "CITY LETTINGS RENT",
        "source": "statement",
        "external_ref": null,
        "running_balance": "10500.00",
        "running_balance_native": "10500.00"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "2577.90",
    "balance": "2577.90",
    "transactions": [
      {
        "entry_id": "e011",
        "entry_date": "2026-04-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "182.40",
        "running_balance_native": "182.40"
      },
      {
        "entry_id": "e012",
        "entry_date": "2026-04-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "394.00",
        "running_balance_native": "394.00"
      },
      {
        "entry_id": "e020",
        "entry_date": "2026-05-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "570.10",
        "running_balance_native": "570.10"
      },
      {
        "entry_id": "e022",
        "entry_date": "2026-05-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "794.40",
        "running_balance_native": "794.40"
      },
      {
        "entry_id": "e030",
        "entry_date": "2026-06-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "984.40",
        "running_balance_native": "984.40"
      },
      {
        "entry_id": "e073",
        "entry_date": "2026-06-12",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "1134.40",
        "running_balance_native": "1134.40"
      },
      {
        "entry_id": "e074",
        "entry_date": "2026-06-12",
        "description": "REVERSAL: FRESHMART",
        "source": "system",
        "external_ref": "e073",
        "running_balance": "984.40",
        "running_balance_native": "984.40"
      },
      {
        "entry_id": "e032",
        "entry_date": "2026-06-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "1189.90",
        "running_balance_native": "1189.90"
      },
      {
        "entry_id": "e040",
        "entry_date": "2026-07-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "1358.70",
        "running_balance_native": "1358.70"
      },
      {
        "entry_id": "e042",
        "entry_date": "2026-07-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "1589.90",
        "running_balance_native": "1589.90"
      },
      {
        "entry_id": "e050",
        "entry_date": "2026-08-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "1775.15",
        "running_balance_native": "1775.15"
      },
      {
        "entry_id": "e052",
        "entry_date": "2026-08-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "1989.90",
        "running_balance_native": "1989.90"
      },
      {
        "entry_id": "e060",
        "entry_date": "2026-09-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "2169.80",
        "running_balance_native": "2169.80"
      },
      {
        "entry_id": "e062",
        "entry_date": "2026-09-21",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "2389.90",
        "running_balance_native": "2389.90"
      },
      {
        "entry_id": "e070",
        "entry_date": "2026-10-09",
        "description": "FRESHMART",
        "source": "statement",
        "external_ref": null,
        "running_balance": "2577.90",
        "running_balance_native": "2577.90"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "454.70",
    "balance": "454.70",
    "transactions": [
      {
        "entry_id": "e013",
        "entry_date": "2026-04-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "64.00",
        "running_balance_native": "64.00"
      },
      {
        "entry_id": "e023",
        "entry_date": "2026-05-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "152.50",
        "running_balance_native": "152.50"
      },
      {
        "entry_id": "e033",
        "entry_date": "2026-06-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "223.70",
        "running_balance_native": "223.70"
      },
      {
        "entry_id": "e043",
        "entry_date": "2026-07-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "318.70",
        "running_balance_native": "318.70"
      },
      {
        "entry_id": "e053",
        "entry_date": "2026-08-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "377.00",
        "running_balance_native": "377.00"
      },
      {
        "entry_id": "e063",
        "entry_date": "2026-09-18",
        "description": "BISTRO NOVO",
        "source": "statement",
        "external_ref": null,
        "running_balance": "454.70",
        "running_balance_native": "454.70"
      }
    ]
  },
  {
    "account": {
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
    "base_currency": "EUR",
    "current_balance": "350.00",
    "balance": "350.00",
    "transactions": [
      {
        "entry_id": "e009",
        "entry_date": "2026-04-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "50.00",
        "running_balance_native": "50.00"
      },
      {
        "entry_id": "e018",
        "entry_date": "2026-05-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "100.00",
        "running_balance_native": "100.00"
      },
      {
        "entry_id": "e028",
        "entry_date": "2026-06-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "150.00",
        "running_balance_native": "150.00"
      },
      {
        "entry_id": "e038",
        "entry_date": "2026-07-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "200.00",
        "running_balance_native": "200.00"
      },
      {
        "entry_id": "e048",
        "entry_date": "2026-08-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "250.00",
        "running_balance_native": "250.00"
      },
      {
        "entry_id": "e058",
        "entry_date": "2026-09-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "300.00",
        "running_balance_native": "300.00"
      },
      {
        "entry_id": "e068",
        "entry_date": "2026-10-05",
        "description": "AUTOFIN CAR LOAN",
        "source": "statement",
        "external_ref": null,
        "running_balance": "350.00",
        "running_balance_native": "350.00"
      }
    ]
  },
  {
    "account": {
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
    },
    "base_currency": "EUR",
    "current_balance": "90.93",
    "balance": "90.93",
    "transactions": [
      {
        "entry_id": "e010",
        "entry_date": "2026-04-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "12.99",
        "running_balance_native": "12.99"
      },
      {
        "entry_id": "e019",
        "entry_date": "2026-05-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "25.98",
        "running_balance_native": "25.98"
      },
      {
        "entry_id": "e029",
        "entry_date": "2026-06-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "38.97",
        "running_balance_native": "38.97"
      },
      {
        "entry_id": "e039",
        "entry_date": "2026-07-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "51.96",
        "running_balance_native": "51.96"
      },
      {
        "entry_id": "e049",
        "entry_date": "2026-08-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "64.95",
        "running_balance_native": "64.95"
      },
      {
        "entry_id": "e059",
        "entry_date": "2026-09-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "77.94",
        "running_balance_native": "77.94"
      },
      {
        "entry_id": "e069",
        "entry_date": "2026-10-08",
        "description": "STREAMFLIX",
        "source": "statement",
        "external_ref": null,
        "running_balance": "90.93",
        "running_balance_native": "90.93"
      }
    ]
  }
];

/**
 * Every entry, oldest first.
 */
export const ENTRIES: JournalEntry[] = [
  {
    "id": "e001",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e001.1",
        "tags": {},
        "account_id": "chk",
        "direction": 1,
        "amount": "3200.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e001.2",
        "tags": {},
        "account_id": "eq",
        "direction": -1,
        "amount": "3200.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e002",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e002.1",
        "tags": {},
        "account_id": "sav",
        "direction": 1,
        "amount": "6000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e002.2",
        "tags": {},
        "account_id": "eq",
        "direction": -1,
        "amount": "6000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e003",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e003.1",
        "tags": {},
        "account_id": "brk",
        "direction": 1,
        "amount": "10000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e003.2",
        "tags": {},
        "account_id": "eq",
        "direction": -1,
        "amount": "10000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e004",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e004.1",
        "tags": {},
        "account_id": "pen",
        "direction": 1,
        "amount": "25000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e004.2",
        "tags": {},
        "account_id": "eq",
        "direction": -1,
        "amount": "25000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e005",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e005.1",
        "tags": {},
        "account_id": "flat",
        "direction": 1,
        "amount": "300000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e005.2",
        "tags": {},
        "account_id": "eq",
        "direction": -1,
        "amount": "300000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e006",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e006.1",
        "tags": {},
        "account_id": "usd",
        "direction": 1,
        "amount": "2000.00",
        "currency": "USD",
        "fx_rate": "0.90"
      },
      {
        "id": "e006.2",
        "tags": {},
        "account_id": "eq",
        "direction": -1,
        "amount": "1800.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e007",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e007.1",
        "tags": {},
        "account_id": "eq",
        "direction": 1,
        "amount": "12000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e007.2",
        "tags": {},
        "account_id": "loan",
        "direction": -1,
        "amount": "12000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e008",
    "entry_date": "2026-04-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e008.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "rent",
        "direction": 1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e008.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e009",
    "entry_date": "2026-04-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e009.1",
        "tags": {},
        "account_id": "loan",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e009.2",
        "tags": {},
        "account_id": "int",
        "direction": 1,
        "amount": "50.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e009.3",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "350.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e010",
    "entry_date": "2026-04-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e010.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "tv",
        "direction": 1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e010.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e011",
    "entry_date": "2026-04-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e011.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "182.40",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e011.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "182.40",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e013",
    "entry_date": "2026-04-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e013.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "out",
        "direction": 1,
        "amount": "64.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e013.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "64.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e012",
    "entry_date": "2026-04-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e012.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "211.60",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e012.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "211.60",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e014",
    "entry_date": "2026-04-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e014.1",
        "tags": {},
        "account_id": "chk",
        "direction": 1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e014.2",
        "tags": {},
        "account_id": "sal",
        "direction": -1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e015",
    "entry_date": "2026-04-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e015.1",
        "tags": {},
        "account_id": "brk",
        "direction": 1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e015.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e016",
    "entry_date": "2026-04-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e016.1",
        "tags": {},
        "account_id": "sav",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e016.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e017",
    "entry_date": "2026-05-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e017.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "rent",
        "direction": 1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e017.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e018",
    "entry_date": "2026-05-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e018.1",
        "tags": {},
        "account_id": "loan",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e018.2",
        "tags": {},
        "account_id": "int",
        "direction": 1,
        "amount": "50.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e018.3",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "350.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e019",
    "entry_date": "2026-05-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e019.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "tv",
        "direction": 1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e019.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e020",
    "entry_date": "2026-05-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e020.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "176.10",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e020.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "176.10",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e021",
    "entry_date": "2026-05-15",
    "description": "CARD PAYMENT THANK YOU",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e021.1",
        "tags": {},
        "account_id": "card",
        "direction": 1,
        "amount": "470.99",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e021.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "470.99",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e023",
    "entry_date": "2026-05-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e023.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "out",
        "direction": 1,
        "amount": "88.50",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e023.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "88.50",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e022",
    "entry_date": "2026-05-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e022.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "224.30",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e022.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "224.30",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e024",
    "entry_date": "2026-05-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e024.1",
        "tags": {},
        "account_id": "chk",
        "direction": 1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e024.2",
        "tags": {},
        "account_id": "sal",
        "direction": -1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e071",
    "entry_date": "2026-05-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e071.1",
        "tags": {},
        "account_id": "chk",
        "direction": 1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e071.2",
        "tags": {},
        "account_id": "sal",
        "direction": -1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e072",
    "entry_date": "2026-05-25",
    "description": "REVERSAL: ACME LTD SALARY",
    "source": "system",
    "external_ref": "e071",
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e072.1",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e072.2",
        "tags": {},
        "account_id": "sal",
        "direction": 1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e025",
    "entry_date": "2026-05-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e025.1",
        "tags": {},
        "account_id": "brk",
        "direction": 1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e025.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e026",
    "entry_date": "2026-05-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e026.1",
        "tags": {},
        "account_id": "sav",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e026.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e027",
    "entry_date": "2026-06-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e027.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "rent",
        "direction": 1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e027.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e028",
    "entry_date": "2026-06-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e028.1",
        "tags": {},
        "account_id": "loan",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e028.2",
        "tags": {},
        "account_id": "int",
        "direction": 1,
        "amount": "50.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e028.3",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "350.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e029",
    "entry_date": "2026-06-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e029.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "tv",
        "direction": 1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e029.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e030",
    "entry_date": "2026-06-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e030.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "190.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e030.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "190.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e073",
    "entry_date": "2026-06-12",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e073.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "150.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e073.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "150.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e074",
    "entry_date": "2026-06-12",
    "description": "REVERSAL: FRESHMART",
    "source": "system",
    "external_ref": "e073",
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e074.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": -1,
        "amount": "150.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e074.2",
        "tags": {},
        "account_id": "card",
        "direction": 1,
        "amount": "150.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e031",
    "entry_date": "2026-06-15",
    "description": "CARD PAYMENT THANK YOU",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e031.1",
        "tags": {},
        "account_id": "card",
        "direction": 1,
        "amount": "501.89",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e031.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "501.89",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e033",
    "entry_date": "2026-06-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e033.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "out",
        "direction": 1,
        "amount": "71.20",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e033.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "71.20",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e032",
    "entry_date": "2026-06-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e032.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "205.50",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e032.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "205.50",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e034",
    "entry_date": "2026-06-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e034.1",
        "tags": {},
        "account_id": "chk",
        "direction": 1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e034.2",
        "tags": {},
        "account_id": "sal",
        "direction": -1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e035",
    "entry_date": "2026-06-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e035.1",
        "tags": {},
        "account_id": "brk",
        "direction": 1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e035.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e036",
    "entry_date": "2026-06-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e036.1",
        "tags": {},
        "account_id": "sav",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e036.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e037",
    "entry_date": "2026-07-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e037.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "rent",
        "direction": 1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e037.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e038",
    "entry_date": "2026-07-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e038.1",
        "tags": {},
        "account_id": "loan",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e038.2",
        "tags": {},
        "account_id": "int",
        "direction": 1,
        "amount": "50.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e038.3",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "350.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e039",
    "entry_date": "2026-07-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e039.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "tv",
        "direction": 1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e039.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e040",
    "entry_date": "2026-07-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e040.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "168.80",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e040.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "168.80",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e041",
    "entry_date": "2026-07-15",
    "description": "CARD PAYMENT THANK YOU",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e041.1",
        "tags": {},
        "account_id": "card",
        "direction": 1,
        "amount": "479.69",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e041.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "479.69",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e075",
    "entry_date": "2026-07-15",
    "description": "TO DOLLAR ACCOUNT",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e075.1",
        "tags": {},
        "account_id": "usd",
        "direction": 1,
        "amount": "500.00",
        "currency": "USD",
        "fx_rate": "0.95"
      },
      {
        "id": "e075.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "475.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e043",
    "entry_date": "2026-07-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e043.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "out",
        "direction": 1,
        "amount": "95.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e043.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "95.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e042",
    "entry_date": "2026-07-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e042.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "231.20",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e042.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "231.20",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e044",
    "entry_date": "2026-07-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e044.1",
        "tags": {},
        "account_id": "chk",
        "direction": 1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e044.2",
        "tags": {},
        "account_id": "sal",
        "direction": -1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e045",
    "entry_date": "2026-07-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e045.1",
        "tags": {},
        "account_id": "brk",
        "direction": 1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e045.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e046",
    "entry_date": "2026-07-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e046.1",
        "tags": {},
        "account_id": "sav",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e046.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e047",
    "entry_date": "2026-08-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e047.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "rent",
        "direction": 1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e047.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e048",
    "entry_date": "2026-08-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e048.1",
        "tags": {},
        "account_id": "loan",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e048.2",
        "tags": {},
        "account_id": "int",
        "direction": 1,
        "amount": "50.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e048.3",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "350.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e049",
    "entry_date": "2026-08-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e049.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "tv",
        "direction": 1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e049.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e050",
    "entry_date": "2026-08-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e050.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "185.25",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e050.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "185.25",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e051",
    "entry_date": "2026-08-15",
    "description": "CARD PAYMENT THANK YOU",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e051.1",
        "tags": {},
        "account_id": "card",
        "direction": 1,
        "amount": "507.99",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e051.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "507.99",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e053",
    "entry_date": "2026-08-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e053.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "out",
        "direction": 1,
        "amount": "58.30",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e053.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "58.30",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e052",
    "entry_date": "2026-08-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e052.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "214.75",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e052.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "214.75",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e054",
    "entry_date": "2026-08-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e054.1",
        "tags": {},
        "account_id": "chk",
        "direction": 1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e054.2",
        "tags": {},
        "account_id": "sal",
        "direction": -1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e055",
    "entry_date": "2026-08-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e055.1",
        "tags": {},
        "account_id": "brk",
        "direction": 1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e055.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e056",
    "entry_date": "2026-08-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e056.1",
        "tags": {},
        "account_id": "sav",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e056.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e057",
    "entry_date": "2026-09-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e057.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "rent",
        "direction": 1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e057.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e058",
    "entry_date": "2026-09-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e058.1",
        "tags": {},
        "account_id": "loan",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e058.2",
        "tags": {},
        "account_id": "int",
        "direction": 1,
        "amount": "50.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e058.3",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "350.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e059",
    "entry_date": "2026-09-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e059.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "tv",
        "direction": 1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e059.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e060",
    "entry_date": "2026-09-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e060.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "179.90",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e060.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "179.90",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e061",
    "entry_date": "2026-09-15",
    "description": "CARD PAYMENT THANK YOU",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e061.1",
        "tags": {},
        "account_id": "card",
        "direction": 1,
        "amount": "471.29",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e061.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "471.29",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e063",
    "entry_date": "2026-09-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e063.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "out",
        "direction": 1,
        "amount": "77.70",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e063.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "77.70",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e062",
    "entry_date": "2026-09-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e062.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "220.10",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e062.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "220.10",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e064",
    "entry_date": "2026-09-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e064.1",
        "tags": {},
        "account_id": "chk",
        "direction": 1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e064.2",
        "tags": {},
        "account_id": "sal",
        "direction": -1,
        "amount": "4000.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e065",
    "entry_date": "2026-09-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e065.1",
        "tags": {},
        "account_id": "brk",
        "direction": 1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e065.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e066",
    "entry_date": "2026-09-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e066.1",
        "tags": {},
        "account_id": "sav",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e066.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e067",
    "entry_date": "2026-10-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e067.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "rent",
        "direction": 1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e067.2",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "1500.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e068",
    "entry_date": "2026-10-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e068.1",
        "tags": {},
        "account_id": "loan",
        "direction": 1,
        "amount": "300.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e068.2",
        "tags": {},
        "account_id": "int",
        "direction": 1,
        "amount": "50.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e068.3",
        "tags": {},
        "account_id": "chk",
        "direction": -1,
        "amount": "350.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e069",
    "entry_date": "2026-10-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e069.1",
        "tags": {
          "need": "discretionary"
        },
        "account_id": "tv",
        "direction": 1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e069.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "12.99",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  },
  {
    "id": "e070",
    "entry_date": "2026-10-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "reversed_by": null,
    "reverses": null,
    "corrects": null,
    "created_by": null,
    "created_via": null,
    "seq": null,
    "hash": null,
    "postings": [
      {
        "id": "e070.1",
        "tags": {
          "need": "essential"
        },
        "account_id": "food",
        "direction": 1,
        "amount": "188.00",
        "currency": "EUR",
        "fx_rate": "1"
      },
      {
        "id": "e070.2",
        "tags": {},
        "account_id": "card",
        "direction": -1,
        "amount": "188.00",
        "currency": "EUR",
        "fx_rate": "1"
      }
    ]
  }
];

/**
 * Where each entry came from.
 */
export const PROVENANCES: EntryProvenance[] = [
  {
    "entry_id": "e001",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e002",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e003",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e004",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e005",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e006",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e007",
    "entry_date": "2026-03-31",
    "description": "Opening balance",
    "source": "manual",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e008",
    "entry_date": "2026-04-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e009",
    "entry_date": "2026-04-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e010",
    "entry_date": "2026-04-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e011",
    "entry_date": "2026-04-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e013",
    "entry_date": "2026-04-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e012",
    "entry_date": "2026-04-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e014",
    "entry_date": "2026-04-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e015",
    "entry_date": "2026-04-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e016",
    "entry_date": "2026-04-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e017",
    "entry_date": "2026-05-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e018",
    "entry_date": "2026-05-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e019",
    "entry_date": "2026-05-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e020",
    "entry_date": "2026-05-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e021",
    "entry_date": "2026-05-15",
    "description": "CARD PAYMENT THANK YOU",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e023",
    "entry_date": "2026-05-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e022",
    "entry_date": "2026-05-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e024",
    "entry_date": "2026-05-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e071",
    "entry_date": "2026-05-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e072",
    "entry_date": "2026-05-25",
    "description": "REVERSAL: ACME LTD SALARY",
    "source": "system",
    "external_ref": "e071",
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e025",
    "entry_date": "2026-05-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e026",
    "entry_date": "2026-05-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e027",
    "entry_date": "2026-06-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e028",
    "entry_date": "2026-06-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e029",
    "entry_date": "2026-06-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e030",
    "entry_date": "2026-06-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e073",
    "entry_date": "2026-06-12",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e074",
    "entry_date": "2026-06-12",
    "description": "REVERSAL: FRESHMART",
    "source": "system",
    "external_ref": "e073",
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e031",
    "entry_date": "2026-06-15",
    "description": "CARD PAYMENT THANK YOU",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e033",
    "entry_date": "2026-06-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e032",
    "entry_date": "2026-06-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e034",
    "entry_date": "2026-06-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e035",
    "entry_date": "2026-06-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e036",
    "entry_date": "2026-06-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e037",
    "entry_date": "2026-07-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e038",
    "entry_date": "2026-07-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e039",
    "entry_date": "2026-07-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e040",
    "entry_date": "2026-07-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e041",
    "entry_date": "2026-07-15",
    "description": "CARD PAYMENT THANK YOU",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e075",
    "entry_date": "2026-07-15",
    "description": "TO DOLLAR ACCOUNT",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e043",
    "entry_date": "2026-07-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e042",
    "entry_date": "2026-07-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e044",
    "entry_date": "2026-07-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e045",
    "entry_date": "2026-07-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e046",
    "entry_date": "2026-07-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e047",
    "entry_date": "2026-08-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e048",
    "entry_date": "2026-08-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e049",
    "entry_date": "2026-08-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e050",
    "entry_date": "2026-08-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e051",
    "entry_date": "2026-08-15",
    "description": "CARD PAYMENT THANK YOU",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e053",
    "entry_date": "2026-08-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e052",
    "entry_date": "2026-08-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e054",
    "entry_date": "2026-08-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e055",
    "entry_date": "2026-08-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e056",
    "entry_date": "2026-08-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e057",
    "entry_date": "2026-09-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e058",
    "entry_date": "2026-09-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e059",
    "entry_date": "2026-09-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e060",
    "entry_date": "2026-09-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e061",
    "entry_date": "2026-09-15",
    "description": "CARD PAYMENT THANK YOU",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e063",
    "entry_date": "2026-09-18",
    "description": "BISTRO NOVO",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e062",
    "entry_date": "2026-09-21",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e064",
    "entry_date": "2026-09-25",
    "description": "ACME LTD SALARY",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e065",
    "entry_date": "2026-09-26",
    "description": "TO BROKERAGE",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e066",
    "entry_date": "2026-09-26",
    "description": "TO SAVINGS",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e067",
    "entry_date": "2026-10-01",
    "description": "CITY LETTINGS RENT",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e068",
    "entry_date": "2026-10-05",
    "description": "AUTOFIN CAR LOAN",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e069",
    "entry_date": "2026-10-08",
    "description": "STREAMFLIX",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  },
  {
    "entry_id": "e070",
    "entry_date": "2026-10-09",
    "description": "FRESHMART",
    "source": "statement",
    "external_ref": null,
    "corrects": null,
    "statement": null,
    "receipt": null,
    "possible_subscriptions": []
  }
];

/**
 * The next 60 days.
 */
export const FORECAST: CashForecast = {
  "currency": "EUR",
  "start": "2026-10-11",
  "end": "2026-12-10",
  "today": "15801.47",
  "end_balance": "19626.59",
  "lowest": "15727.02",
  "lowest_date": "2026-10-18",
  "daily": [
    {
      "date": "2026-10-11",
      "balance": "15801.47"
    },
    {
      "date": "2026-10-12",
      "balance": "15801.47"
    },
    {
      "date": "2026-10-13",
      "balance": "15801.47"
    },
    {
      "date": "2026-10-14",
      "balance": "15801.47"
    },
    {
      "date": "2026-10-15",
      "balance": "15801.47"
    },
    {
      "date": "2026-10-16",
      "balance": "15801.47"
    },
    {
      "date": "2026-10-17",
      "balance": "15801.47"
    },
    {
      "date": "2026-10-18",
      "balance": "15727.02"
    },
    {
      "date": "2026-10-19",
      "balance": "15727.02"
    },
    {
      "date": "2026-10-20",
      "balance": "15727.02"
    },
    {
      "date": "2026-10-21",
      "balance": "15727.02"
    },
    {
      "date": "2026-10-22",
      "balance": "15727.02"
    },
    {
      "date": "2026-10-23",
      "balance": "15727.02"
    },
    {
      "date": "2026-10-24",
      "balance": "15727.02"
    },
    {
      "date": "2026-10-25",
      "balance": "19727.02"
    },
    {
      "date": "2026-10-26",
      "balance": "19227.02"
    },
    {
      "date": "2026-10-27",
      "balance": "19227.02"
    },
    {
      "date": "2026-10-28",
      "balance": "19227.02"
    },
    {
      "date": "2026-10-29",
      "balance": "19227.02"
    },
    {
      "date": "2026-10-30",
      "balance": "19227.02"
    },
    {
      "date": "2026-10-31",
      "balance": "19227.02"
    },
    {
      "date": "2026-11-01",
      "balance": "17727.02"
    },
    {
      "date": "2026-11-02",
      "balance": "17727.02"
    },
    {
      "date": "2026-11-03",
      "balance": "17727.02"
    },
    {
      "date": "2026-11-04",
      "balance": "17727.02"
    },
    {
      "date": "2026-11-05",
      "balance": "17727.02"
    },
    {
      "date": "2026-11-06",
      "balance": "17727.02"
    },
    {
      "date": "2026-11-07",
      "balance": "17727.02"
    },
    {
      "date": "2026-11-08",
      "balance": "17714.03"
    },
    {
      "date": "2026-11-09",
      "balance": "17714.03"
    },
    {
      "date": "2026-11-10",
      "balance": "17714.03"
    },
    {
      "date": "2026-11-11",
      "balance": "17714.03"
    },
    {
      "date": "2026-11-12",
      "balance": "17714.03"
    },
    {
      "date": "2026-11-13",
      "balance": "17714.03"
    },
    {
      "date": "2026-11-14",
      "balance": "17714.03"
    },
    {
      "date": "2026-11-15",
      "balance": "17714.03"
    },
    {
      "date": "2026-11-16",
      "balance": "17714.03"
    },
    {
      "date": "2026-11-17",
      "balance": "17714.03"
    },
    {
      "date": "2026-11-18",
      "balance": "17639.58"
    },
    {
      "date": "2026-11-19",
      "balance": "17639.58"
    },
    {
      "date": "2026-11-20",
      "balance": "17639.58"
    },
    {
      "date": "2026-11-21",
      "balance": "17639.58"
    },
    {
      "date": "2026-11-22",
      "balance": "17639.58"
    },
    {
      "date": "2026-11-23",
      "balance": "17639.58"
    },
    {
      "date": "2026-11-24",
      "balance": "17639.58"
    },
    {
      "date": "2026-11-25",
      "balance": "21639.58"
    },
    {
      "date": "2026-11-26",
      "balance": "21139.58"
    },
    {
      "date": "2026-11-27",
      "balance": "21139.58"
    },
    {
      "date": "2026-11-28",
      "balance": "21139.58"
    },
    {
      "date": "2026-11-29",
      "balance": "21139.58"
    },
    {
      "date": "2026-11-30",
      "balance": "21139.58"
    },
    {
      "date": "2026-12-01",
      "balance": "19639.58"
    },
    {
      "date": "2026-12-02",
      "balance": "19639.58"
    },
    {
      "date": "2026-12-03",
      "balance": "19639.58"
    },
    {
      "date": "2026-12-04",
      "balance": "19639.58"
    },
    {
      "date": "2026-12-05",
      "balance": "19639.58"
    },
    {
      "date": "2026-12-06",
      "balance": "19639.58"
    },
    {
      "date": "2026-12-07",
      "balance": "19639.58"
    },
    {
      "date": "2026-12-08",
      "balance": "19626.59"
    },
    {
      "date": "2026-12-09",
      "balance": "19626.59"
    },
    {
      "date": "2026-12-10",
      "balance": "19626.59"
    }
  ],
  "accounts": [
    {
      "account_id": "card",
      "name": "Credit card",
      "currency": "EUR",
      "today": "-691.68",
      "end": "92.82",
      "lowest": "-691.68",
      "lowest_date": "2026-10-11"
    },
    {
      "account_id": "chk",
      "name": "Checking",
      "currency": "EUR",
      "today": "6543.15",
      "end": "8983.77",
      "lowest": "6063.46",
      "lowest_date": "2026-10-15"
    },
    {
      "account_id": "sav",
      "name": "Savings",
      "currency": "EUR",
      "today": "7800.00",
      "end": "8400.00",
      "lowest": "7800.00",
      "lowest_date": "2026-10-11"
    },
    {
      "account_id": "usd",
      "name": "Dollar account",
      "currency": "USD",
      "today": "2500.00",
      "end": "2500.00",
      "lowest": "2500.00",
      "lowest_date": "2026-10-11"
    }
  ],
  "flows": [
    {
      "date": "2026-10-15",
      "account_id": "chk",
      "amount": "-479.69",
      "currency": "EUR",
      "description": "Thank",
      "source": "recurring"
    },
    {
      "date": "2026-10-15",
      "account_id": "card",
      "amount": "479.69",
      "currency": "EUR",
      "description": "Thank",
      "source": "recurring"
    },
    {
      "date": "2026-10-18",
      "account_id": "card",
      "amount": "-74.45",
      "currency": "EUR",
      "description": "Bistro Novo",
      "source": "recurring"
    },
    {
      "date": "2026-10-25",
      "account_id": "chk",
      "amount": "4000.00",
      "currency": "EUR",
      "description": "Acme Salary",
      "source": "recurring"
    },
    {
      "date": "2026-10-26",
      "account_id": "chk",
      "amount": "-500.00",
      "currency": "EUR",
      "description": "Brokerage",
      "source": "recurring"
    },
    {
      "date": "2026-10-26",
      "account_id": "chk",
      "amount": "-300.00",
      "currency": "EUR",
      "description": "Savings",
      "source": "recurring"
    },
    {
      "date": "2026-10-26",
      "account_id": "sav",
      "amount": "300.00",
      "currency": "EUR",
      "description": "Savings",
      "source": "recurring"
    },
    {
      "date": "2026-11-01",
      "account_id": "chk",
      "amount": "-1500.00",
      "currency": "EUR",
      "description": "City Lettings Rent",
      "source": "recurring"
    },
    {
      "date": "2026-11-08",
      "account_id": "card",
      "amount": "-12.99",
      "currency": "EUR",
      "description": "Streamflix",
      "source": "recurring"
    },
    {
      "date": "2026-11-15",
      "account_id": "chk",
      "amount": "-479.69",
      "currency": "EUR",
      "description": "Thank",
      "source": "recurring"
    },
    {
      "date": "2026-11-15",
      "account_id": "card",
      "amount": "479.69",
      "currency": "EUR",
      "description": "Thank",
      "source": "recurring"
    },
    {
      "date": "2026-11-18",
      "account_id": "card",
      "amount": "-74.45",
      "currency": "EUR",
      "description": "Bistro Novo",
      "source": "recurring"
    },
    {
      "date": "2026-11-25",
      "account_id": "chk",
      "amount": "4000.00",
      "currency": "EUR",
      "description": "Acme Salary",
      "source": "recurring"
    },
    {
      "date": "2026-11-26",
      "account_id": "chk",
      "amount": "-500.00",
      "currency": "EUR",
      "description": "Brokerage",
      "source": "recurring"
    },
    {
      "date": "2026-11-26",
      "account_id": "chk",
      "amount": "-300.00",
      "currency": "EUR",
      "description": "Savings",
      "source": "recurring"
    },
    {
      "date": "2026-11-26",
      "account_id": "sav",
      "amount": "300.00",
      "currency": "EUR",
      "description": "Savings",
      "source": "recurring"
    },
    {
      "date": "2026-12-01",
      "account_id": "chk",
      "amount": "-1500.00",
      "currency": "EUR",
      "description": "City Lettings Rent",
      "source": "recurring"
    },
    {
      "date": "2026-12-08",
      "account_id": "card",
      "amount": "-12.99",
      "currency": "EUR",
      "description": "Streamflix",
      "source": "recurring"
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

/**
 * Six full months and this one so far.
 */
export const CASH_FLOW: CashFlow = {
  "currency": "EUR",
  "months": [
    {
      "month": "2026-04",
      "income": "4000.00",
      "expenses": "2020.99",
      "net": "1979.01",
      "savings_rate": "0.4948",
      "complete": true,
      "observed": true
    },
    {
      "month": "2026-05",
      "income": "4000.00",
      "expenses": "2051.89",
      "net": "1948.11",
      "savings_rate": "0.4870",
      "complete": true,
      "observed": true
    },
    {
      "month": "2026-06",
      "income": "4000.00",
      "expenses": "2029.69",
      "net": "1970.31",
      "savings_rate": "0.4926",
      "complete": true,
      "observed": true
    },
    {
      "month": "2026-07",
      "income": "4000.00",
      "expenses": "2057.99",
      "net": "1942.01",
      "savings_rate": "0.4855",
      "complete": true,
      "observed": true
    },
    {
      "month": "2026-08",
      "income": "4000.00",
      "expenses": "2021.29",
      "net": "1978.71",
      "savings_rate": "0.4947",
      "complete": true,
      "observed": true
    },
    {
      "month": "2026-09",
      "income": "4000.00",
      "expenses": "2040.69",
      "net": "1959.31",
      "savings_rate": "0.4898",
      "complete": true,
      "observed": true
    },
    {
      "month": "2026-10",
      "income": "0.00",
      "expenses": "1750.99",
      "net": "-1750.99",
      "savings_rate": null,
      "complete": false,
      "observed": false
    }
  ],
  "average": {
    "months_observed": [
      "2026-04",
      "2026-05",
      "2026-06",
      "2026-07",
      "2026-08",
      "2026-09"
    ],
    "income": "4000.00",
    "expenses": "2037.09",
    "net": "1962.91",
    "savings_rate": "0.4907"
  }
};

/**
 * By category, August to October so far.
 */
export const SPENDING: Spending = {
  "currency": "EUR",
  "by": "category",
  "months": [
    "2026-08",
    "2026-09",
    "2026-10"
  ],
  "lines": [
    {
      "key": "Rent",
      "total": "4500.00",
      "share": "0.7741",
      "by_month": {
        "2026-08": "1500.00",
        "2026-09": "1500.00",
        "2026-10": "1500.00"
      }
    },
    {
      "key": "Groceries",
      "total": "988.00",
      "share": "0.1700",
      "by_month": {
        "2026-08": "400.00",
        "2026-09": "400.00",
        "2026-10": "188.00"
      }
    },
    {
      "key": "Loan interest",
      "total": "150.00",
      "share": "0.0258",
      "by_month": {
        "2026-08": "50.00",
        "2026-09": "50.00",
        "2026-10": "50.00"
      }
    },
    {
      "key": "Eating out",
      "total": "136.00",
      "share": "0.0234",
      "by_month": {
        "2026-08": "58.30",
        "2026-09": "77.70",
        "2026-10": "0.00"
      }
    },
    {
      "key": "Streaming",
      "total": "38.97",
      "share": "0.0067",
      "by_month": {
        "2026-08": "12.99",
        "2026-09": "12.99",
        "2026-10": "12.99"
      }
    }
  ]
};

/**
 * Pending and done.
 */
export const REMINDERS_ALL: ReminderList = {
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
      "id": "00002331-5a11-4000-8000-000000009009",
      "kind": "Pay the window cleaner",
      "due_date": "2026-10-02",
      "status": "done",
      "alert_type": null,
      "source_domain": null,
      "source_id": null,
      "severity": null,
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

export const ASSUMPTIONS: FiAssumptionsReport = {
  "applied": {
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
  "own": {
    "real_return": null,
    "nominal_return": null,
    "inflation": null,
    "volatility": null,
    "safe_withdrawal_rate": null,
    "surplus_invested": null
  },
  "placeholder_values": {
    "real_return": {
      "value": "0.04",
      "source": "Placeholder: a round 4% a year after inflation, not a forecast and not any country's figure. Set your own, with its source."
    },
    "safe_withdrawal_rate": {
      "value": "0.0314",
      "source": "Placeholder: the yearly withdrawal 90% of 1000 simulated return paths sustain over 30 years drawn down, on the placeholder pack's returns. Not a recommendation. Set your own rate, or your own returns, with a source."
    },
    "surplus_invested": {
      "value": "1",
      "source": "Placeholder: all of your monthly surplus is assumed invested at the real return; set what you actually invest."
    }
  },
  "scenario_spread": "0.02"
};

export const PROJECTIONS: FiProjections = {
  "currency": "EUR",
  "headline_status": "placeholder",
  "headline": "Rests on placeholders for the real return, the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
  "terms": "real",
  "points": [
    {
      "year": 0,
      "conservative": "24691.01",
      "base": "24691.01",
      "growth": "24691.01"
    },
    {
      "year": 1,
      "conservative": "53972.00",
      "base": "55055.67",
      "growth": "56158.96"
    },
    {
      "year": 2,
      "conservative": "80449.37",
      "base": "83047.11",
      "growth": "85736.80"
    },
    {
      "year": 3,
      "conservative": "107636.08",
      "base": "112256.40",
      "growth": "117117.01"
    },
    {
      "year": 4,
      "conservative": "135430.78",
      "base": "142675.94",
      "growth": "150412.97"
    },
    {
      "year": 5,
      "conservative": "163818.97",
      "base": "174341.35",
      "growth": "185742.67"
    },
    {
      "year": 6,
      "conservative": "192814.14",
      "base": "207303.73",
      "growth": "223230.67"
    },
    {
      "year": 7,
      "conservative": "222424.56",
      "base": "241615.10",
      "growth": "263012.48"
    },
    {
      "year": 8,
      "conservative": "252636.25",
      "base": "277325.11",
      "growth": "305245.71"
    },
    {
      "year": 9,
      "conservative": "283457.75",
      "base": "314490.00",
      "growth": "350083.80"
    },
    {
      "year": 10,
      "conservative": "314901.36",
      "base": "353169.04",
      "growth": "397687.40"
    },
    {
      "year": 11,
      "conservative": "346979.63",
      "base": "393423.93",
      "growth": "448227.09"
    },
    {
      "year": 12,
      "conservative": "379705.39",
      "base": "435318.86",
      "growth": "501883.95"
    },
    {
      "year": 13,
      "conservative": "413091.69",
      "base": "478920.65",
      "growth": "558850.25"
    },
    {
      "year": 14,
      "conservative": "447151.88",
      "base": "524298.86",
      "growth": "619330.11"
    },
    {
      "year": 15,
      "conservative": "481899.55",
      "base": "571525.84",
      "growth": "683540.23"
    },
    {
      "year": 16,
      "conservative": "517348.58",
      "base": "620676.91",
      "growth": "751710.70"
    },
    {
      "year": 17,
      "conservative": "553513.12",
      "base": "671830.48",
      "growth": "824085.77"
    },
    {
      "year": 18,
      "conservative": "590407.62",
      "base": "725068.13",
      "growth": "900924.77"
    },
    {
      "year": 19,
      "conservative": "628046.81",
      "base": "780474.76",
      "growth": "982503.04"
    },
    {
      "year": 20,
      "conservative": "666445.73",
      "base": "838138.74",
      "growth": "1069112.87"
    },
    {
      "year": 21,
      "conservative": "705619.70",
      "base": "898152.04",
      "growth": "1161064.61"
    },
    {
      "year": 22,
      "conservative": "745584.38",
      "base": "960610.37",
      "growth": "1258687.74"
    },
    {
      "year": 23,
      "conservative": "786355.71",
      "base": "1025613.36",
      "growth": "1362332.04"
    },
    {
      "year": 24,
      "conservative": "827949.99",
      "base": "1093264.66",
      "growth": "1472368.90"
    }
  ],
  "fi_number": "714042.04",
  "swr": "0.0314",
  "fi_by": {
    "conservative": {
      "months": 255,
      "month": "2048-01"
    },
    "base": {
      "months": 214,
      "month": "2044-08"
    },
    "growth": {
      "months": 186,
      "month": "2042-04"
    }
  },
  "as_of": "2026-10-11",
  "current_portfolio": "24691.01",
  "real_returns": {
    "conservative": "0.02",
    "base": "0.04",
    "growth": "0.06"
  },
  "inflation": null,
  "nominal_returns": null,
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
  }
};

/**
 * The score as Salli kept it on the household's date.
 */
export const SCORE_HISTORY: FiScoreHistory = {
  "currency": "EUR",
  "history": [
    {
      "score": 56.42,
      "net_worth": "335901.47",
      "created_at": "2026-10-11T10:00:00+00:00"
    }
  ]
};

/**
 * The answer to posting lunch from checking.
 */
export const POSTED: Ref = {
  "id": "0000239d-5a11-4000-8000-000000009117"
};

/**
 * Lunch, as posted.
 */
export const LUNCH: JournalEntry = {
  "id": "0000239d-5a11-4000-8000-000000009117",
  "entry_date": "2026-10-11",
  "description": "Lunch with a friend",
  "source": "manual",
  "external_ref": null,
  "reversed_by": null,
  "reverses": null,
  "corrects": null,
  "created_by": null,
  "created_via": null,
  "seq": null,
  "hash": null,
  "postings": [
    {
      "id": "0000239e-5a11-4000-8000-000000009118",
      "tags": {},
      "account_id": "out",
      "direction": 1,
      "amount": "12.50",
      "currency": "EUR",
      "fx_rate": "1"
    },
    {
      "id": "0000239f-5a11-4000-8000-000000009119",
      "tags": {},
      "account_id": "chk",
      "direction": -1,
      "amount": "12.50",
      "currency": "EUR",
      "fx_rate": "1"
    }
  ]
};

export const LUNCH_PROVENANCE: EntryProvenance = {
  "entry_id": "0000239d-5a11-4000-8000-000000009117",
  "entry_date": "2026-10-11",
  "description": "Lunch with a friend",
  "source": "manual",
  "external_ref": null,
  "corrects": null,
  "statement": null,
  "receipt": null,
  "possible_subscriptions": []
};

/**
 * Checking with lunch posted.
 */
export const CHECKING_POSTED: AccountOverview = {
  "account": {
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
  "base_currency": "EUR",
  "current_balance": "6530.65",
  "balance": "6530.65",
  "transactions": [
    {
      "entry_id": "e001",
      "entry_date": "2026-03-31",
      "description": "Opening balance",
      "source": "manual",
      "external_ref": null,
      "running_balance": "3200.00",
      "running_balance_native": "3200.00"
    },
    {
      "entry_id": "e008",
      "entry_date": "2026-04-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "1700.00",
      "running_balance_native": "1700.00"
    },
    {
      "entry_id": "e009",
      "entry_date": "2026-04-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "1350.00",
      "running_balance_native": "1350.00"
    },
    {
      "entry_id": "e014",
      "entry_date": "2026-04-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5350.00",
      "running_balance_native": "5350.00"
    },
    {
      "entry_id": "e015",
      "entry_date": "2026-04-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4850.00",
      "running_balance_native": "4850.00"
    },
    {
      "entry_id": "e016",
      "entry_date": "2026-04-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4550.00",
      "running_balance_native": "4550.00"
    },
    {
      "entry_id": "e017",
      "entry_date": "2026-05-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3050.00",
      "running_balance_native": "3050.00"
    },
    {
      "entry_id": "e018",
      "entry_date": "2026-05-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "2700.00",
      "running_balance_native": "2700.00"
    },
    {
      "entry_id": "e021",
      "entry_date": "2026-05-15",
      "description": "CARD PAYMENT THANK YOU",
      "source": "statement",
      "external_ref": null,
      "running_balance": "2229.01",
      "running_balance_native": "2229.01"
    },
    {
      "entry_id": "e024",
      "entry_date": "2026-05-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6229.01",
      "running_balance_native": "6229.01"
    },
    {
      "entry_id": "e071",
      "entry_date": "2026-05-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "10229.01",
      "running_balance_native": "10229.01"
    },
    {
      "entry_id": "e072",
      "entry_date": "2026-05-25",
      "description": "REVERSAL: ACME LTD SALARY",
      "source": "system",
      "external_ref": "e071",
      "running_balance": "6229.01",
      "running_balance_native": "6229.01"
    },
    {
      "entry_id": "e025",
      "entry_date": "2026-05-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5729.01",
      "running_balance_native": "5729.01"
    },
    {
      "entry_id": "e026",
      "entry_date": "2026-05-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5429.01",
      "running_balance_native": "5429.01"
    },
    {
      "entry_id": "e027",
      "entry_date": "2026-06-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3929.01",
      "running_balance_native": "3929.01"
    },
    {
      "entry_id": "e028",
      "entry_date": "2026-06-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3579.01",
      "running_balance_native": "3579.01"
    },
    {
      "entry_id": "e031",
      "entry_date": "2026-06-15",
      "description": "CARD PAYMENT THANK YOU",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3077.12",
      "running_balance_native": "3077.12"
    },
    {
      "entry_id": "e034",
      "entry_date": "2026-06-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "7077.12",
      "running_balance_native": "7077.12"
    },
    {
      "entry_id": "e035",
      "entry_date": "2026-06-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6577.12",
      "running_balance_native": "6577.12"
    },
    {
      "entry_id": "e036",
      "entry_date": "2026-06-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6277.12",
      "running_balance_native": "6277.12"
    },
    {
      "entry_id": "e037",
      "entry_date": "2026-07-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4777.12",
      "running_balance_native": "4777.12"
    },
    {
      "entry_id": "e038",
      "entry_date": "2026-07-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4427.12",
      "running_balance_native": "4427.12"
    },
    {
      "entry_id": "e041",
      "entry_date": "2026-07-15",
      "description": "CARD PAYMENT THANK YOU",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3947.43",
      "running_balance_native": "3947.43"
    },
    {
      "entry_id": "e075",
      "entry_date": "2026-07-15",
      "description": "TO DOLLAR ACCOUNT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3472.43",
      "running_balance_native": "3472.43"
    },
    {
      "entry_id": "e044",
      "entry_date": "2026-07-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "7472.43",
      "running_balance_native": "7472.43"
    },
    {
      "entry_id": "e045",
      "entry_date": "2026-07-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6972.43",
      "running_balance_native": "6972.43"
    },
    {
      "entry_id": "e046",
      "entry_date": "2026-07-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6672.43",
      "running_balance_native": "6672.43"
    },
    {
      "entry_id": "e047",
      "entry_date": "2026-08-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5172.43",
      "running_balance_native": "5172.43"
    },
    {
      "entry_id": "e048",
      "entry_date": "2026-08-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4822.43",
      "running_balance_native": "4822.43"
    },
    {
      "entry_id": "e051",
      "entry_date": "2026-08-15",
      "description": "CARD PAYMENT THANK YOU",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4314.44",
      "running_balance_native": "4314.44"
    },
    {
      "entry_id": "e054",
      "entry_date": "2026-08-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "8314.44",
      "running_balance_native": "8314.44"
    },
    {
      "entry_id": "e055",
      "entry_date": "2026-08-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "7814.44",
      "running_balance_native": "7814.44"
    },
    {
      "entry_id": "e056",
      "entry_date": "2026-08-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "7514.44",
      "running_balance_native": "7514.44"
    },
    {
      "entry_id": "e057",
      "entry_date": "2026-09-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6014.44",
      "running_balance_native": "6014.44"
    },
    {
      "entry_id": "e058",
      "entry_date": "2026-09-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5664.44",
      "running_balance_native": "5664.44"
    },
    {
      "entry_id": "e061",
      "entry_date": "2026-09-15",
      "description": "CARD PAYMENT THANK YOU",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5193.15",
      "running_balance_native": "5193.15"
    },
    {
      "entry_id": "e064",
      "entry_date": "2026-09-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "9193.15",
      "running_balance_native": "9193.15"
    },
    {
      "entry_id": "e065",
      "entry_date": "2026-09-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "8693.15",
      "running_balance_native": "8693.15"
    },
    {
      "entry_id": "e066",
      "entry_date": "2026-09-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "8393.15",
      "running_balance_native": "8393.15"
    },
    {
      "entry_id": "e067",
      "entry_date": "2026-10-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6893.15",
      "running_balance_native": "6893.15"
    },
    {
      "entry_id": "e068",
      "entry_date": "2026-10-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6543.15",
      "running_balance_native": "6543.15"
    },
    {
      "entry_id": "0000239d-5a11-4000-8000-000000009117",
      "entry_date": "2026-10-11",
      "description": "Lunch with a friend",
      "source": "manual",
      "external_ref": null,
      "running_balance": "6530.65",
      "running_balance_native": "6530.65"
    }
  ]
};

/**
 * With lunch posted.
 */
export const TRIAL_BALANCE_POSTED: TrialBalance = {
  "currency": "EUR",
  "balances": {
    "chk": "6530.65",
    "eq": "-334000.00",
    "sav": "7800.00",
    "brk": "13000.00",
    "pen": "25000.00",
    "flat": "300000.00",
    "usd": "2275.00",
    "loan": "-9900.00",
    "rent": "10500.00",
    "int": "350.00",
    "tv": "90.93",
    "card": "-691.68",
    "food": "2577.90",
    "out": "467.20",
    "sal": "-24000.00"
  },
  "net": "0.00"
};

/**
 * The answer to reversing lunch.
 */
export const REVERSED: Ref = {
  "id": "000023a5-5a11-4000-8000-000000009125"
};

/**
 * Lunch, reversed.
 */
export const LUNCH_REVERSED: JournalEntry = {
  "id": "0000239d-5a11-4000-8000-000000009117",
  "entry_date": "2026-10-11",
  "description": "Lunch with a friend",
  "source": "manual",
  "external_ref": null,
  "reversed_by": "000023a5-5a11-4000-8000-000000009125",
  "reverses": null,
  "corrects": null,
  "created_by": null,
  "created_via": null,
  "seq": null,
  "hash": null,
  "postings": [
    {
      "id": "0000239e-5a11-4000-8000-000000009118",
      "tags": {},
      "account_id": "out",
      "direction": 1,
      "amount": "12.50",
      "currency": "EUR",
      "fx_rate": "1"
    },
    {
      "id": "0000239f-5a11-4000-8000-000000009119",
      "tags": {},
      "account_id": "chk",
      "direction": -1,
      "amount": "12.50",
      "currency": "EUR",
      "fx_rate": "1"
    }
  ]
};

export const REVERSAL: JournalEntry = {
  "id": "000023a5-5a11-4000-8000-000000009125",
  "entry_date": "2026-10-11",
  "description": "Reversal of Lunch with a friend: Paid twice",
  "source": "reversal",
  "external_ref": null,
  "reversed_by": null,
  "reverses": "0000239d-5a11-4000-8000-000000009117",
  "corrects": null,
  "created_by": null,
  "created_via": null,
  "seq": null,
  "hash": null,
  "postings": [
    {
      "id": "000023a6-5a11-4000-8000-000000009126",
      "tags": {},
      "account_id": "out",
      "direction": -1,
      "amount": "12.50",
      "currency": "EUR",
      "fx_rate": "1"
    },
    {
      "id": "000023a7-5a11-4000-8000-000000009127",
      "tags": {},
      "account_id": "chk",
      "direction": 1,
      "amount": "12.50",
      "currency": "EUR",
      "fx_rate": "1"
    }
  ]
};

export const REVERSAL_PROVENANCE: EntryProvenance = {
  "entry_id": "000023a5-5a11-4000-8000-000000009125",
  "entry_date": "2026-10-11",
  "description": "Reversal of Lunch with a friend: Paid twice",
  "source": "reversal",
  "external_ref": null,
  "corrects": null,
  "statement": null,
  "receipt": null,
  "possible_subscriptions": []
};

/**
 * Checking with lunch and its reversal.
 */
export const CHECKING_REVERSED: AccountOverview = {
  "account": {
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
  "base_currency": "EUR",
  "current_balance": "6543.15",
  "balance": "6543.15",
  "transactions": [
    {
      "entry_id": "e001",
      "entry_date": "2026-03-31",
      "description": "Opening balance",
      "source": "manual",
      "external_ref": null,
      "running_balance": "3200.00",
      "running_balance_native": "3200.00"
    },
    {
      "entry_id": "e008",
      "entry_date": "2026-04-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "1700.00",
      "running_balance_native": "1700.00"
    },
    {
      "entry_id": "e009",
      "entry_date": "2026-04-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "1350.00",
      "running_balance_native": "1350.00"
    },
    {
      "entry_id": "e014",
      "entry_date": "2026-04-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5350.00",
      "running_balance_native": "5350.00"
    },
    {
      "entry_id": "e015",
      "entry_date": "2026-04-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4850.00",
      "running_balance_native": "4850.00"
    },
    {
      "entry_id": "e016",
      "entry_date": "2026-04-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4550.00",
      "running_balance_native": "4550.00"
    },
    {
      "entry_id": "e017",
      "entry_date": "2026-05-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3050.00",
      "running_balance_native": "3050.00"
    },
    {
      "entry_id": "e018",
      "entry_date": "2026-05-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "2700.00",
      "running_balance_native": "2700.00"
    },
    {
      "entry_id": "e021",
      "entry_date": "2026-05-15",
      "description": "CARD PAYMENT THANK YOU",
      "source": "statement",
      "external_ref": null,
      "running_balance": "2229.01",
      "running_balance_native": "2229.01"
    },
    {
      "entry_id": "e024",
      "entry_date": "2026-05-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6229.01",
      "running_balance_native": "6229.01"
    },
    {
      "entry_id": "e071",
      "entry_date": "2026-05-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "10229.01",
      "running_balance_native": "10229.01"
    },
    {
      "entry_id": "e072",
      "entry_date": "2026-05-25",
      "description": "REVERSAL: ACME LTD SALARY",
      "source": "system",
      "external_ref": "e071",
      "running_balance": "6229.01",
      "running_balance_native": "6229.01"
    },
    {
      "entry_id": "e025",
      "entry_date": "2026-05-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5729.01",
      "running_balance_native": "5729.01"
    },
    {
      "entry_id": "e026",
      "entry_date": "2026-05-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5429.01",
      "running_balance_native": "5429.01"
    },
    {
      "entry_id": "e027",
      "entry_date": "2026-06-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3929.01",
      "running_balance_native": "3929.01"
    },
    {
      "entry_id": "e028",
      "entry_date": "2026-06-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3579.01",
      "running_balance_native": "3579.01"
    },
    {
      "entry_id": "e031",
      "entry_date": "2026-06-15",
      "description": "CARD PAYMENT THANK YOU",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3077.12",
      "running_balance_native": "3077.12"
    },
    {
      "entry_id": "e034",
      "entry_date": "2026-06-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "7077.12",
      "running_balance_native": "7077.12"
    },
    {
      "entry_id": "e035",
      "entry_date": "2026-06-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6577.12",
      "running_balance_native": "6577.12"
    },
    {
      "entry_id": "e036",
      "entry_date": "2026-06-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6277.12",
      "running_balance_native": "6277.12"
    },
    {
      "entry_id": "e037",
      "entry_date": "2026-07-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4777.12",
      "running_balance_native": "4777.12"
    },
    {
      "entry_id": "e038",
      "entry_date": "2026-07-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4427.12",
      "running_balance_native": "4427.12"
    },
    {
      "entry_id": "e041",
      "entry_date": "2026-07-15",
      "description": "CARD PAYMENT THANK YOU",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3947.43",
      "running_balance_native": "3947.43"
    },
    {
      "entry_id": "e075",
      "entry_date": "2026-07-15",
      "description": "TO DOLLAR ACCOUNT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "3472.43",
      "running_balance_native": "3472.43"
    },
    {
      "entry_id": "e044",
      "entry_date": "2026-07-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "7472.43",
      "running_balance_native": "7472.43"
    },
    {
      "entry_id": "e045",
      "entry_date": "2026-07-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6972.43",
      "running_balance_native": "6972.43"
    },
    {
      "entry_id": "e046",
      "entry_date": "2026-07-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6672.43",
      "running_balance_native": "6672.43"
    },
    {
      "entry_id": "e047",
      "entry_date": "2026-08-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5172.43",
      "running_balance_native": "5172.43"
    },
    {
      "entry_id": "e048",
      "entry_date": "2026-08-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4822.43",
      "running_balance_native": "4822.43"
    },
    {
      "entry_id": "e051",
      "entry_date": "2026-08-15",
      "description": "CARD PAYMENT THANK YOU",
      "source": "statement",
      "external_ref": null,
      "running_balance": "4314.44",
      "running_balance_native": "4314.44"
    },
    {
      "entry_id": "e054",
      "entry_date": "2026-08-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "8314.44",
      "running_balance_native": "8314.44"
    },
    {
      "entry_id": "e055",
      "entry_date": "2026-08-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "7814.44",
      "running_balance_native": "7814.44"
    },
    {
      "entry_id": "e056",
      "entry_date": "2026-08-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "7514.44",
      "running_balance_native": "7514.44"
    },
    {
      "entry_id": "e057",
      "entry_date": "2026-09-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6014.44",
      "running_balance_native": "6014.44"
    },
    {
      "entry_id": "e058",
      "entry_date": "2026-09-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5664.44",
      "running_balance_native": "5664.44"
    },
    {
      "entry_id": "e061",
      "entry_date": "2026-09-15",
      "description": "CARD PAYMENT THANK YOU",
      "source": "statement",
      "external_ref": null,
      "running_balance": "5193.15",
      "running_balance_native": "5193.15"
    },
    {
      "entry_id": "e064",
      "entry_date": "2026-09-25",
      "description": "ACME LTD SALARY",
      "source": "statement",
      "external_ref": null,
      "running_balance": "9193.15",
      "running_balance_native": "9193.15"
    },
    {
      "entry_id": "e065",
      "entry_date": "2026-09-26",
      "description": "TO BROKERAGE",
      "source": "statement",
      "external_ref": null,
      "running_balance": "8693.15",
      "running_balance_native": "8693.15"
    },
    {
      "entry_id": "e066",
      "entry_date": "2026-09-26",
      "description": "TO SAVINGS",
      "source": "statement",
      "external_ref": null,
      "running_balance": "8393.15",
      "running_balance_native": "8393.15"
    },
    {
      "entry_id": "e067",
      "entry_date": "2026-10-01",
      "description": "CITY LETTINGS RENT",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6893.15",
      "running_balance_native": "6893.15"
    },
    {
      "entry_id": "e068",
      "entry_date": "2026-10-05",
      "description": "AUTOFIN CAR LOAN",
      "source": "statement",
      "external_ref": null,
      "running_balance": "6543.15",
      "running_balance_native": "6543.15"
    },
    {
      "entry_id": "0000239d-5a11-4000-8000-000000009117",
      "entry_date": "2026-10-11",
      "description": "Lunch with a friend",
      "source": "manual",
      "external_ref": null,
      "running_balance": "6530.65",
      "running_balance_native": "6530.65"
    },
    {
      "entry_id": "000023a5-5a11-4000-8000-000000009125",
      "entry_date": "2026-10-11",
      "description": "Reversal of Lunch with a friend: Paid twice",
      "source": "reversal",
      "external_ref": null,
      "running_balance": "6543.15",
      "running_balance_native": "6543.15"
    }
  ]
};

/**
 * With lunch and its reversal.
 */
export const TRIAL_BALANCE_REVERSED: TrialBalance = {
  "currency": "EUR",
  "balances": {
    "chk": "6543.15",
    "eq": "-334000.00",
    "sav": "7800.00",
    "brk": "13000.00",
    "pen": "25000.00",
    "flat": "300000.00",
    "usd": "2275.00",
    "loan": "-9900.00",
    "rent": "10500.00",
    "int": "350.00",
    "tv": "90.93",
    "card": "-691.68",
    "food": "2577.90",
    "out": "454.70",
    "sal": "-24000.00"
  },
  "net": "0.00"
};

/**
 * Reversing lunch a second time.
 */
export const REVERSE_REFUSED: ProblemDetails = {
  "type": "about:blank",
  "title": "Salli didn't do this",
  "status": 400,
  "detail": "That entry is already reversed. An entry can be reversed only once."
};

export const DOLLARS_POSTED: Ref = {
  "id": "000023af-5a11-4000-8000-000000009135"
};

/**
 * 100.00 USD from checking, at the published rate for the day.
 */
export const DOLLARS: JournalEntry = {
  "id": "000023af-5a11-4000-8000-000000009135",
  "entry_date": "2026-10-11",
  "description": "Dollars for the trip",
  "source": "manual",
  "external_ref": null,
  "reversed_by": null,
  "reverses": null,
  "corrects": null,
  "created_by": null,
  "created_via": null,
  "seq": null,
  "hash": null,
  "postings": [
    {
      "id": "000023b0-5a11-4000-8000-000000009136",
      "tags": {},
      "account_id": "usd",
      "direction": 1,
      "amount": "100.00",
      "currency": "USD",
      "fx_rate": "0.86"
    },
    {
      "id": "000023b1-5a11-4000-8000-000000009137",
      "tags": {},
      "account_id": "chk",
      "direction": -1,
      "amount": "100.00",
      "currency": "USD",
      "fx_rate": "0.86"
    }
  ]
};

/**
 * Pounds, with no rate given and none published for the day.
 */
export const NO_RATE: ProblemDetails = {
  "type": "/problems/fx-rate-unavailable",
  "title": "No exchange rate",
  "status": 422,
  "detail": "No GBP→EUR rate for 2026-10-11. Send the exchange rate (fx_rate) with the amount."
};

/**
 * The answer to setting the real return, with its source and a note.
 */
export const ASSUMPTION_SET: FiAssumptionsReport = {
  "applied": {
    "status": "placeholder",
    "placeholders": [
      "safe_withdrawal_rate",
      "surplus_invested",
      "drawdown_horizon"
    ],
    "headline_status": "placeholder",
    "headline": "Rests on placeholders for the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
    "message": "Using placeholder assumptions for the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: round figures, not forecasts. Set your own, with a source, to replace them. Figures are in today's money; set your inflation to see them in future money too.",
    "real_return": {
      "value": "0.035",
      "origin": "user",
      "source": "My own long-run view, after inflation",
      "note": "Halfway between the conservative and base scenarios."
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
      "conservative": "0.015",
      "base": "0.035",
      "growth": "0.055"
    },
    "nominal_returns": null,
    "cma": null
  },
  "own": {
    "real_return": {
      "value": "0.035",
      "source": "My own long-run view, after inflation",
      "note": "Halfway between the conservative and base scenarios.",
      "set_at": "2026-10-11T10:00:00+00:00"
    },
    "nominal_return": null,
    "inflation": null,
    "volatility": null,
    "safe_withdrawal_rate": null,
    "surplus_invested": null
  },
  "placeholder_values": {
    "real_return": {
      "value": "0.04",
      "source": "Placeholder: a round 4% a year after inflation, not a forecast and not any country's figure. Set your own, with its source."
    },
    "safe_withdrawal_rate": {
      "value": "0.0314",
      "source": "Placeholder: the yearly withdrawal 90% of 1000 simulated return paths sustain over 30 years drawn down, on the placeholder pack's returns. Not a recommendation. Set your own rate, or your own returns, with a source."
    },
    "surplus_invested": {
      "value": "1",
      "source": "Placeholder: all of your monthly surplus is assumed invested at the real return; set what you actually invest."
    }
  },
  "scenario_spread": "0.02"
};

/**
 * With the real return set.
 */
export const FI_SCORE_SET: FiScore = {
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
  "projected_fi_months": 223,
  "projected_fi_month": "2045-05",
  "as_of": "2026-10-11",
  "status": "ok",
  "months_observed": 6,
  "headline_status": "placeholder",
  "headline": "Rests on placeholders for the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
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
      "safe_withdrawal_rate",
      "surplus_invested",
      "drawdown_horizon"
    ],
    "headline_status": "placeholder",
    "headline": "Rests on placeholders for the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
    "message": "Using placeholder assumptions for the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: round figures, not forecasts. Set your own, with a source, to replace them. Figures are in today's money; set your inflation to see them in future money too.",
    "real_return": {
      "value": "0.035",
      "origin": "user",
      "source": "My own long-run view, after inflation",
      "note": "Halfway between the conservative and base scenarios."
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
      "conservative": "0.015",
      "base": "0.035",
      "growth": "0.055"
    },
    "nominal_returns": null
  },
  "inputs_hash": "dc71decaba353bb5e8cf0f82c55a65a63ded5fb7826bcbdc5ba37f587f7f2117"
};

/**
 * With the real return set.
 */
export const PROJECTIONS_SET: FiProjections = {
  "currency": "EUR",
  "headline_status": "placeholder",
  "headline": "Rests on placeholders for the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
  "terms": "real",
  "points": [
    {
      "year": 0,
      "conservative": "24691.01",
      "base": "24691.01",
      "growth": "24691.01"
    },
    {
      "year": 1,
      "conservative": "53704.11",
      "base": "54782.93",
      "growth": "55881.28"
    },
    {
      "year": 2,
      "conservative": "79813.93",
      "base": "82389.18",
      "growth": "85055.58"
    },
    {
      "year": 3,
      "conservative": "106517.09",
      "base": "111079.29",
      "growth": "115878.63"
    },
    {
      "year": 4,
      "conservative": "133692.41",
      "base": "140819.87",
      "growth": "148430.70"
    },
    {
      "year": 5,
      "conservative": "161317.07",
      "base": "171631.30",
      "growth": "182805.73"
    },
    {
      "year": 6,
      "conservative": "189399.65",
      "base": "203552.29",
      "growth": "219105.98"
    },
    {
      "year": 7,
      "conservative": "217942.28",
      "base": "236620.70",
      "growth": "257441.63"
    },
    {
      "year": 8,
      "conservative": "246920.31",
      "base": "270866.71",
      "growth": "297938.23"
    },
    {
      "year": 9,
      "conservative": "276336.02",
      "base": "306330.76",
      "growth": "340719.16"
    },
    {
      "year": 10,
      "conservative": "306196.01",
      "base": "343056.15",
      "growth": "385913.27"
    },
    {
      "year": 11,
      "conservative": "336506.98",
      "base": "381087.75",
      "growth": "433656.68"
    },
    {
      "year": 12,
      "conservative": "367275.77",
      "base": "420472.01",
      "growth": "484093.20"
    },
    {
      "year": 13,
      "conservative": "398509.27",
      "base": "461257.06",
      "growth": "537374.73"
    },
    {
      "year": 14,
      "conservative": "430214.50",
      "base": "503492.71",
      "growth": "593661.76"
    },
    {
      "year": 15,
      "conservative": "462398.60",
      "base": "547230.55",
      "growth": "653123.82"
    },
    {
      "year": 16,
      "conservative": "495068.80",
      "base": "592524.01",
      "growth": "715940.01"
    },
    {
      "year": 17,
      "conservative": "528232.43",
      "base": "639428.42",
      "growth": "782299.52"
    },
    {
      "year": 18,
      "conservative": "561896.95",
      "base": "688001.08",
      "growth": "852402.23"
    },
    {
      "year": 19,
      "conservative": "596069.92",
      "base": "738301.32",
      "growth": "926459.29"
    },
    {
      "year": 20,
      "conservative": "630759.02",
      "base": "790390.59",
      "growth": "1004693.75"
    },
    {
      "year": 21,
      "conservative": "665972.06",
      "base": "844332.51",
      "growth": "1087341.24"
    },
    {
      "year": 22,
      "conservative": "701716.94",
      "base": "900192.99",
      "growth": "1174650.71"
    },
    {
      "year": 23,
      "conservative": "738001.69",
      "base": "958040.25",
      "growth": "1266885.11"
    },
    {
      "year": 24,
      "conservative": "774834.47",
      "base": "1017944.96",
      "growth": "1364322.26"
    },
    {
      "year": 25,
      "conservative": "812223.55",
      "base": "1079980.29",
      "growth": "1467255.63"
    }
  ],
  "fi_number": "714042.04",
  "swr": "0.0314",
  "fi_by": {
    "conservative": {
      "months": 269,
      "month": "2049-03"
    },
    "base": {
      "months": 223,
      "month": "2045-05"
    },
    "growth": {
      "months": 192,
      "month": "2042-10"
    }
  },
  "as_of": "2026-10-11",
  "current_portfolio": "24691.01",
  "real_returns": {
    "conservative": "0.015",
    "base": "0.035",
    "growth": "0.055"
  },
  "inflation": null,
  "nominal_returns": null,
  "assumptions": {
    "status": "placeholder",
    "placeholders": [
      "safe_withdrawal_rate",
      "surplus_invested",
      "drawdown_horizon"
    ],
    "headline_status": "placeholder",
    "headline": "Rests on placeholders for the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: not a forecast.",
    "message": "Using placeholder assumptions for the safe withdrawal rate, the share of your monthly surplus invested and the years drawn down: round figures, not forecasts. Set your own, with a source, to replace them. Figures are in today's money; set your inflation to see them in future money too.",
    "real_return": {
      "value": "0.035",
      "origin": "user",
      "source": "My own long-run view, after inflation",
      "note": "Halfway between the conservative and base scenarios."
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
      "conservative": "0.015",
      "base": "0.035",
      "growth": "0.055"
    },
    "nominal_returns": null
  }
};

/**
 * A real return of 60% a year.
 */
export const ASSUMPTION_REFUSED: ProblemDetails = {
  "type": "/problems/invalid",
  "title": "Invalid request",
  "status": 422,
  "detail": "real_return must be a yearly fraction from -0.05 to 0.15 (0.03 for 3%), got 0.6"
};
