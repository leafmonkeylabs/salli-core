/**
 * What a real server answers for decision templates on the golden household
 * ledger (tests/golden/household.py, as of Oct 11, 2026, in euros, with the
 * principle "Six months of essentials in cash"): the list, the afford-it,
 * emergency-fund and rent-or-buy templates, and a start of each
 * (rent-or-buy's against the household's rent, City Lettings, with two
 * mortgages). Account and debt ids are the mock server's own; the hashes
 * are the server's for the household's.
 *
 * Written by tests/cli_fixtures.py (`uv run python -m tests.cli_fixtures`):
 * tests/contract/test_cli_fixtures.py fails while it differs from what the
 * server answers. Don't edit it by hand.
 */
import type { DecisionStart, DecisionTemplate, DecisionTemplateList } from '@leafmonkeylabs/salli-sdk';

export const TEMPLATE_LIST: DecisionTemplateList = {
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
          "00000002-5a11-4000-8000-000000000002",
          "00000003-5a11-4000-8000-000000000003"
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
      "value": "00000002-5a11-4000-8000-000000000002",
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
            "account": "00000002-5a11-4000-8000-000000000002",
            "tax_role": null,
            "label": "Laptop"
          }
        ],
        "tax": null
      },
      "scenario_hash": "sha256:c51686f1c65c277fe38f7f721cc2fec8eb68813cb4f7831e26730541f9707f40"
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
            "account": "00000002-5a11-4000-8000-000000000002",
            "tax_role": null,
            "label": "Laptop"
          },
          {
            "type": "loan",
            "principal": "2400.00",
            "annual_rate": "0.069",
            "term_months": 12,
            "start": "2026-11-02",
            "into": "00000002-5a11-4000-8000-000000000002",
            "label": "Laptop, over 12 months"
          }
        ],
        "tax": null
      },
      "scenario_hash": "sha256:44c00c745130e3ff2ffa078f2f95e8c1b5dd2446ebe6b218ec24e05c76448366"
    }
  ],
  "comparison": {
    "as_of": "2026-10-11",
    "horizon_years": 5,
    "currency": "EUR",
    "labels": [
      "Pay cash",
      "Spread over 12 months"
    ],
    "options": [
      {
        "schema": "salli.scenario/1",
        "label": "Pay cash",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "currency": "EUR",
        "hash": "sha256:c51686f1c65c277fe38f7f721cc2fec8eb68813cb4f7831e26730541f9707f40",
        "baseline_fingerprint": "sha256:da45ad36b9e3ff9925e7f74d1c804b3074a9fb8e757e59c04854a3f7a23115b0",
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
              "account": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000003-5a11-4000-8000-000000000003",
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
              "debt_id": "0000019c-5a11-4000-8000-000000000412",
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
              "debt_id": "0000019b-5a11-4000-8000-000000000411",
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
            "baseline": "611127.00",
            "scenario": "611127.00",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2042-05",
            "scenario": "2042-06",
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
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
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
        "hash": "sha256:44c00c745130e3ff2ffa078f2f95e8c1b5dd2446ebe6b218ec24e05c76448366",
        "baseline_fingerprint": "sha256:da45ad36b9e3ff9925e7f74d1c804b3074a9fb8e757e59c04854a3f7a23115b0",
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
              "account": "00000002-5a11-4000-8000-000000000002",
              "tax_role": null,
              "label": "Laptop"
            },
            {
              "type": "loan",
              "principal": "2400.00",
              "annual_rate": "0.069",
              "term_months": 12,
              "start": "2026-11-02",
              "into": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000003-5a11-4000-8000-000000000003",
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
              "debt_id": "0000019c-5a11-4000-8000-000000000412",
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
              "debt_id": "0000019b-5a11-4000-8000-000000000411",
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
            "baseline": "611127.00",
            "scenario": "611127.00",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2042-05",
            "scenario": "2042-07",
            "delta_months": 2
          },
          "months_gained": -2
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
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
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
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2042-06",
            "other": "2042-07",
            "delta": -1
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
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2042-07",
            "other": "2042-06",
            "delta": 1
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
              "baseline": "2045-02",
              "scenario": "2045-02",
              "delta_months": 0
            },
            "months_gained": 0
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
              "baseline": "2042-05",
              "scenario": "2042-06",
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
              "baseline": "2040-07",
              "scenario": "2040-07",
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
              "baseline": "2045-02",
              "scenario": "2045-03",
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
              "baseline": "2042-05",
              "scenario": "2042-07",
              "delta_months": 2
            },
            "months_gained": -2
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
              "baseline": "2040-07",
              "scenario": "2040-08",
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
      }
    ]
  },
  "principles": {
    "principles": [
      {
        "id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
        "label": "Six months of essentials in cash",
        "check": "emergency_months >= 6",
        "account": null,
        "version": 1,
        "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
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
        "fi_number": "611127.00",
        "fi_months": 187,
        "fi_months_gained": 0,
        "tax_change_this_year": "0.00"
      },
      "unavailable": {},
      "results": [
        {
          "principle_id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
          "figures": {
            "emergency_months": "7.37"
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
          "fi_number": "611127.00",
          "fi_months": 188,
          "fi_months_gained": -1,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 6.11.",
            "figures": {
              "emergency_months": "6.11"
            }
          }
        ],
        "label": "Pay cash",
        "scenario_hash": "sha256:c51686f1c65c277fe38f7f721cc2fec8eb68813cb4f7831e26730541f9707f40"
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
          "fi_number": "611127.00",
          "fi_months": 189,
          "fi_months_gained": -2,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.28.",
            "figures": {
              "emergency_months": "7.28"
            }
          }
        ],
        "label": "Spread over 12 months",
        "scenario_hash": "sha256:44c00c745130e3ff2ffa078f2f95e8c1b5dd2446ebe6b218ec24e05c76448366"
      }
    ]
  },
  "cover": null,
  "level": null,
  "placeholders": [
    "real_return",
    "safe_withdrawal_rate",
    "surplus_invested",
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
            "account": "00000002-5a11-4000-8000-000000000002",
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
            "account": "00000002-5a11-4000-8000-000000000002",
            "tax_role": null,
            "label": "Laptop"
          },
          {
            "type": "loan",
            "principal": "2400.00",
            "annual_rate": "0.069",
            "term_months": 12,
            "start": "2026-11-02",
            "into": "00000002-5a11-4000-8000-000000000002",
            "label": "Laptop, over 12 months"
          }
        ],
        "tax": null
      }
    ],
    "labels": [
      "Pay cash",
      "Spread over 12 months"
    ],
    "earliest_review": "2026-10-31"
  },
  "says": "Salli computed every figure here and ranks none of the options: what matters most is the person's to weigh. To record what they choose, call record_decision (POST /v1/decisions) with `record.question` (theirs to change), `record.options`, the label they chose, their reasons in their own words and a review date, once they confirm."
};

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
      "scenario_hash": "sha256:450685f043fac8d5d3f7bcf9959a9321af3885949988618771f27b13200a30d1"
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
      "scenario_hash": "sha256:ff38f4b71a7615e3594770cb1f74f58bf0f1744fbc322bca429f4b553e8ddd28"
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
      "scenario_hash": "sha256:fedf7aa1a39687a837241699abe92b7d22c9c78daabd1882197a180e1eba8345"
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
        "hash": "sha256:450685f043fac8d5d3f7bcf9959a9321af3885949988618771f27b13200a30d1",
        "baseline_fingerprint": "sha256:da45ad36b9e3ff9925e7f74d1c804b3074a9fb8e757e59c04854a3f7a23115b0",
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
              "account_id": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000003-5a11-4000-8000-000000000003",
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
              "debt_id": "0000019c-5a11-4000-8000-000000000412",
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
              "debt_id": "0000019b-5a11-4000-8000-000000000411",
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
            "baseline": "611127.00",
            "scenario": "611127.00",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2042-05",
            "scenario": "2042-05",
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
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
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
        "hash": "sha256:ff38f4b71a7615e3594770cb1f74f58bf0f1744fbc322bca429f4b553e8ddd28",
        "baseline_fingerprint": "sha256:da45ad36b9e3ff9925e7f74d1c804b3074a9fb8e757e59c04854a3f7a23115b0",
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
              "account_id": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000003-5a11-4000-8000-000000000003",
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
              "debt_id": "0000019c-5a11-4000-8000-000000000412",
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
              "debt_id": "0000019b-5a11-4000-8000-000000000411",
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
            "baseline": "611127.00",
            "scenario": "611127.00",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2042-05",
            "scenario": "2042-09",
            "delta_months": 4
          },
          "months_gained": -4
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
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
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
        "hash": "sha256:fedf7aa1a39687a837241699abe92b7d22c9c78daabd1882197a180e1eba8345",
        "baseline_fingerprint": "sha256:da45ad36b9e3ff9925e7f74d1c804b3074a9fb8e757e59c04854a3f7a23115b0",
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
              "account_id": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000003-5a11-4000-8000-000000000003",
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
              "debt_id": "0000019c-5a11-4000-8000-000000000412",
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
              "debt_id": "0000019b-5a11-4000-8000-000000000411",
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
            "baseline": "611127.00",
            "scenario": "611127.00",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2042-05",
            "scenario": "2043-03",
            "delta_months": 10
          },
          "months_gained": -10
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
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
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
            "this": "2042-05",
            "other": "2042-09",
            "delta": -4
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
            "this": "2042-05",
            "other": "2043-03",
            "delta": -10
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
            "this": "2042-09",
            "other": "2042-05",
            "delta": 4
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
            "this": "2042-09",
            "other": "2043-03",
            "delta": -6
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
            "this": "2043-03",
            "other": "2042-05",
            "delta": 10
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
            "this": "2043-03",
            "other": "2042-09",
            "delta": 6
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
              "baseline": "2045-02",
              "scenario": "2045-02",
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
              "baseline": "2042-05",
              "scenario": "2042-05",
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
              "baseline": "2040-07",
              "scenario": "2040-07",
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
              "baseline": "2045-02",
              "scenario": "2045-05",
              "delta_months": 3
            },
            "months_gained": -3
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
              "baseline": "2042-05",
              "scenario": "2042-09",
              "delta_months": 4
            },
            "months_gained": -4
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
              "baseline": "2040-07",
              "scenario": "2040-10",
              "delta_months": 3
            },
            "months_gained": -3
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
              "baseline": "2045-02",
              "scenario": "2045-09",
              "delta_months": 7
            },
            "months_gained": -7
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
              "baseline": "2042-05",
              "scenario": "2043-03",
              "delta_months": 10
            },
            "months_gained": -10
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
              "baseline": "2040-07",
              "scenario": "2041-05",
              "delta_months": 10
            },
            "months_gained": -10
          }
        }
      ]
    },
    "break_evens": []
  },
  "principles": {
    "principles": [
      {
        "id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
        "label": "Six months of essentials in cash",
        "check": "emergency_months >= 6",
        "account": null,
        "version": 1,
        "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
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
        "fi_number": "611127.00",
        "fi_months": 187,
        "fi_months_gained": 0,
        "tax_change_this_year": "0.00"
      },
      "unavailable": {},
      "results": [
        {
          "principle_id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
          "figures": {
            "emergency_months": "7.37"
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
          "fi_number": "611127.00",
          "fi_months": 187,
          "fi_months_gained": 0,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
            "figures": {
              "emergency_months": "7.37"
            }
          }
        ],
        "label": "As things are",
        "scenario_hash": "sha256:450685f043fac8d5d3f7bcf9959a9321af3885949988618771f27b13200a30d1"
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
          "fi_number": "611127.00",
          "fi_months": 191,
          "fi_months_gained": -4,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.38.",
            "figures": {
              "emergency_months": "7.38"
            }
          }
        ],
        "label": "Set aside 200.00 a month",
        "scenario_hash": "sha256:ff38f4b71a7615e3594770cb1f74f58bf0f1744fbc322bca429f4b553e8ddd28"
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
          "fi_number": "611127.00",
          "fi_months": 197,
          "fi_months_gained": -10,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.38.",
            "figures": {
              "emergency_months": "7.38"
            }
          }
        ],
        "label": "Set aside 500.00 a month",
        "scenario_hash": "sha256:fedf7aa1a39687a837241699abe92b7d22c9c78daabd1882197a180e1eba8345"
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
  "placeholders": [
    "real_return",
    "safe_withdrawal_rate",
    "surplus_invested",
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
          "00000002-5a11-4000-8000-000000000002",
          "00000003-5a11-4000-8000-000000000003"
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
      "value": "00000002-5a11-4000-8000-000000000002",
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
            "account": "00000002-5a11-4000-8000-000000000002",
            "tax_role": null,
            "real_growth": null,
            "label": "Rent: City Lettings Rent"
          }
        ],
        "tax": null
      },
      "scenario_hash": "sha256:558be28e9c84140e2178e6df954ccd25dd88f7e198f45d671edf411224f3274a"
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
            "from": "00000002-5a11-4000-8000-000000000002",
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
            "into": "00000002-5a11-4000-8000-000000000002",
            "label": "Mortgage, 4.2% over 300 months"
          },
          {
            "type": "one_off",
            "date": "2026-11-01",
            "amount": "-9000.00",
            "account": "00000002-5a11-4000-8000-000000000002",
            "tax_role": null,
            "label": "Buying costs"
          },
          {
            "type": "recurring",
            "amount": "-250.00",
            "cadence": "monthly",
            "start": "2026-11-01",
            "end": null,
            "account": "00000002-5a11-4000-8000-000000000002",
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
      "scenario_hash": "sha256:6aa0e89707d58ed8e30133ff459ea2bc8f96ac26c001804199ee40b95cbce86d"
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
            "from": "00000002-5a11-4000-8000-000000000002",
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
            "into": "00000002-5a11-4000-8000-000000000002",
            "label": "Shorter"
          },
          {
            "type": "one_off",
            "date": "2026-11-01",
            "amount": "-9000.00",
            "account": "00000002-5a11-4000-8000-000000000002",
            "tax_role": null,
            "label": "Buying costs"
          },
          {
            "type": "recurring",
            "amount": "-250.00",
            "cadence": "monthly",
            "start": "2026-11-01",
            "end": null,
            "account": "00000002-5a11-4000-8000-000000000002",
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
      "scenario_hash": "sha256:a9ece0d189bc65a1be201f543b0577326018ac3f8cbd32a56502b4c8dd0a4250"
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
        "hash": "sha256:558be28e9c84140e2178e6df954ccd25dd88f7e198f45d671edf411224f3274a",
        "baseline_fingerprint": "sha256:da45ad36b9e3ff9925e7f74d1c804b3074a9fb8e757e59c04854a3f7a23115b0",
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
              "account": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000003-5a11-4000-8000-000000000003",
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
              "debt_id": "0000019c-5a11-4000-8000-000000000412",
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
              "debt_id": "0000019b-5a11-4000-8000-000000000411",
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
            "baseline": "611127.00",
            "scenario": "611127.00",
            "delta": "0.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "2037.09",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2042-05",
            "scenario": "2042-05",
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
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
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
        "hash": "sha256:6aa0e89707d58ed8e30133ff459ea2bc8f96ac26c001804199ee40b95cbce86d",
        "baseline_fingerprint": "sha256:da45ad36b9e3ff9925e7f74d1c804b3074a9fb8e757e59c04854a3f7a23115b0",
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
              "from": "00000002-5a11-4000-8000-000000000002",
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
              "into": "00000002-5a11-4000-8000-000000000002",
              "label": "Mortgage, 4.2% over 300 months"
            },
            {
              "type": "one_off",
              "date": "2026-11-01",
              "amount": "-9000.00",
              "account": "00000002-5a11-4000-8000-000000000002",
              "tax_role": null,
              "label": "Buying costs"
            },
            {
              "type": "recurring",
              "amount": "-250.00",
              "cadence": "monthly",
              "start": "2026-11-01",
              "end": null,
              "account": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000003-5a11-4000-8000-000000000003",
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
              "00000002-5a11-4000-8000-000000000002"
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
              "debt_id": "0000019c-5a11-4000-8000-000000000412",
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
              "debt_id": "0000019b-5a11-4000-8000-000000000411",
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
            "baseline": "611127.00",
            "scenario": "236127.00",
            "delta": "-375000.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "787.09",
            "delta": "-1250.00"
          },
          "fi_month": {
            "baseline": "2042-05",
            "scenario": "2040-09",
            "delta_months": -20
          },
          "months_gained": 20
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
          "inflation",
          "asset_growth"
        ],
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
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
        "hash": "sha256:a9ece0d189bc65a1be201f543b0577326018ac3f8cbd32a56502b4c8dd0a4250",
        "baseline_fingerprint": "sha256:da45ad36b9e3ff9925e7f74d1c804b3074a9fb8e757e59c04854a3f7a23115b0",
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
              "from": "00000002-5a11-4000-8000-000000000002",
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
              "into": "00000002-5a11-4000-8000-000000000002",
              "label": "Shorter"
            },
            {
              "type": "one_off",
              "date": "2026-11-01",
              "amount": "-9000.00",
              "account": "00000002-5a11-4000-8000-000000000002",
              "tax_role": null,
              "label": "Buying costs"
            },
            {
              "type": "recurring",
              "amount": "-250.00",
              "cadence": "monthly",
              "start": "2026-11-01",
              "end": null,
              "account": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000002-5a11-4000-8000-000000000002",
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
              "account_id": "00000003-5a11-4000-8000-000000000003",
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
              "00000002-5a11-4000-8000-000000000002"
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
              "debt_id": "0000019c-5a11-4000-8000-000000000412",
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
              "debt_id": "0000019b-5a11-4000-8000-000000000411",
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
            "baseline": "611127.00",
            "scenario": "236127.00",
            "delta": "-375000.00"
          },
          "monthly_spending": {
            "baseline": "2037.09",
            "scenario": "787.09",
            "delta": "-1250.00"
          },
          "fi_month": {
            "baseline": "2042-05",
            "scenario": "2040-07",
            "delta_months": -22
          },
          "months_gained": 22
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
          "inflation",
          "asset_growth"
        ],
        "versions": {
          "schema": "salli.scenario/1",
          "engine": "4",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
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
            "this": "611127.00",
            "other": "236127.00",
            "delta": "375000.00"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2042-05",
            "other": "2040-09",
            "delta": 20
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
            "this": "611127.00",
            "other": "236127.00",
            "delta": "375000.00"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2042-05",
            "other": "2040-07",
            "delta": 22
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
            "this": "236127.00",
            "other": "611127.00",
            "delta": "-375000.00"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2040-09",
            "other": "2042-05",
            "delta": -20
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
            "this": "2040-09",
            "other": "2040-07",
            "delta": 2
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
            "this": "236127.00",
            "other": "611127.00",
            "delta": "-375000.00"
          },
          {
            "figure": "fi.fi_month",
            "unit": "month",
            "this": "2040-07",
            "other": "2042-05",
            "delta": -22
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
            "this": "2040-07",
            "other": "2040-09",
            "delta": -2
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
              "baseline": "2045-02",
              "scenario": "2045-02",
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
              "baseline": "2042-05",
              "scenario": "2042-05",
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
              "baseline": "2040-07",
              "scenario": "2040-07",
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
              "baseline": "2045-02",
              "scenario": "2042-05",
              "delta_months": -33
            },
            "months_gained": 33
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
              "baseline": "2042-05",
              "scenario": "2040-09",
              "delta_months": -20
            },
            "months_gained": 20
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
              "baseline": "2040-07",
              "scenario": "2039-06",
              "delta_months": -13
            },
            "months_gained": 13
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
              "baseline": "2045-02",
              "scenario": "2041-11",
              "delta_months": -39
            },
            "months_gained": 39
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
              "baseline": "2042-05",
              "scenario": "2040-07",
              "delta_months": -22
            },
            "months_gained": 22
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
              "baseline": "2040-07",
              "scenario": "2039-04",
              "delta_months": -15
            },
            "months_gained": 15
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
        "id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
        "label": "Six months of essentials in cash",
        "check": "emergency_months >= 6",
        "account": null,
        "version": 1,
        "hash": "sha256:c87ea33767863b2df58519491b095fb15d6f50264d21d69358562e4c9a9df93a"
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
        "fi_number": "611127.00",
        "fi_months": 187,
        "fi_months_gained": 0,
        "tax_change_this_year": "0.00"
      },
      "unavailable": {},
      "results": [
        {
          "principle_id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
          "label": "Six months of essentials in cash",
          "status": "keeps",
          "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
          "figures": {
            "emergency_months": "7.37"
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
          "fi_number": "611127.00",
          "fi_months": 187,
          "fi_months_gained": 0,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
            "label": "Six months of essentials in cash",
            "status": "keeps",
            "reason": "emergency_months >= 6 holds: emergency_months is 7.37.",
            "figures": {
              "emergency_months": "7.37"
            }
          }
        ],
        "label": "Keep renting",
        "scenario_hash": "sha256:558be28e9c84140e2178e6df954ccd25dd88f7e198f45d671edf411224f3274a"
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
          "fi_number": "236127.00",
          "fi_months": 167,
          "fi_months_gained": 20,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
            "label": "Six months of essentials in cash",
            "status": "breaks",
            "reason": "emergency_months >= 6 doesn't hold: emergency_months is -34.26.",
            "figures": {
              "emergency_months": "-34.26"
            }
          }
        ],
        "label": "Buy, 4.2% over 300 months",
        "scenario_hash": "sha256:6aa0e89707d58ed8e30133ff459ea2bc8f96ac26c001804199ee40b95cbce86d"
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
          "fi_number": "236127.00",
          "fi_months": 165,
          "fi_months_gained": 22,
          "tax_change_this_year": "0.00"
        },
        "unavailable": {},
        "results": [
          {
            "principle_id": "3a20d884-aa5c-4254-819e-865c1085b3d6",
            "label": "Six months of essentials in cash",
            "status": "breaks",
            "reason": "emergency_months >= 6 doesn't hold: emergency_months is -34.34.",
            "figures": {
              "emergency_months": "-34.34"
            }
          }
        ],
        "label": "Buy, Shorter",
        "scenario_hash": "sha256:a9ece0d189bc65a1be201f543b0577326018ac3f8cbd32a56502b4c8dd0a4250"
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
  "placeholders": [
    "real_return",
    "safe_withdrawal_rate",
    "surplus_invested",
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
            "account": "00000002-5a11-4000-8000-000000000002",
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
            "from": "00000002-5a11-4000-8000-000000000002",
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
            "into": "00000002-5a11-4000-8000-000000000002",
            "label": "Mortgage, 4.2% over 300 months"
          },
          {
            "type": "one_off",
            "date": "2026-11-01",
            "amount": "-9000.00",
            "account": "00000002-5a11-4000-8000-000000000002",
            "tax_role": null,
            "label": "Buying costs"
          },
          {
            "type": "recurring",
            "amount": "-250.00",
            "cadence": "monthly",
            "start": "2026-11-01",
            "end": null,
            "account": "00000002-5a11-4000-8000-000000000002",
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
            "from": "00000002-5a11-4000-8000-000000000002",
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
            "into": "00000002-5a11-4000-8000-000000000002",
            "label": "Shorter"
          },
          {
            "type": "one_off",
            "date": "2026-11-01",
            "amount": "-9000.00",
            "account": "00000002-5a11-4000-8000-000000000002",
            "tax_role": null,
            "label": "Buying costs"
          },
          {
            "type": "recurring",
            "amount": "-250.00",
            "cadence": "monthly",
            "start": "2026-11-01",
            "end": null,
            "account": "00000002-5a11-4000-8000-000000000002",
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
