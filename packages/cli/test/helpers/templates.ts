/**
 * What a real server answers for decision templates on the golden household
 * ledger (tests/golden/household.py, as of Oct 11, 2026, in euros, with the
 * principle "Six months of essentials in cash"), written by the services
 * themselves: the list, the afford-it and emergency-fund templates, and a
 * start of each. Account and debt ids are the mock server's own.
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
            "label": "Laptop"
          }
        ]
      },
      "scenario_hash": "sha256:eeb0c4c72d62bbbdafafe119b65f38da75dcd164fb91993e93ccc39062d958ca"
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
        ]
      },
      "scenario_hash": "sha256:604bc90236a3e83c511af3ec0c55db732220ed59b9cae912c83384af84629117"
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
        "hash": "sha256:eeb0c4c72d62bbbdafafe119b65f38da75dcd164fb91993e93ccc39062d958ca",
        "baseline_fingerprint": "sha256:fe55137cc10e6e8ba8755f3dd88b73cc841a15c22299f66902518cb3de71d4ab",
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
              "label": "Laptop"
            }
          ]
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
            "stopped": []
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
            "baseline": "15727.02",
            "scenario": "15727.02",
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
          "engine": "2",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
          "fire_strategy": null,
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": []
      },
      {
        "schema": "salli.scenario/1",
        "label": "Spread over 12 months",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "currency": "EUR",
        "hash": "sha256:604bc90236a3e83c511af3ec0c55db732220ed59b9cae912c83384af84629117",
        "baseline_fingerprint": "sha256:fe55137cc10e6e8ba8755f3dd88b73cc841a15c22299f66902518cb3de71d4ab",
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
          ]
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
            "stopped": []
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
            "stopped": []
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
            "baseline": "15727.02",
            "scenario": "15727.02",
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
          "engine": "2",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
          "fire_strategy": null,
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": []
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
        "scenario_hash": "sha256:eeb0c4c72d62bbbdafafe119b65f38da75dcd164fb91993e93ccc39062d958ca"
      },
      {
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
        "scenario_hash": "sha256:604bc90236a3e83c511af3ec0c55db732220ed59b9cae912c83384af84629117"
      }
    ]
  },
  "cover": null,
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
            "label": "Laptop"
          }
        ]
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
        ]
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
        "changes": []
      },
      "scenario_hash": "sha256:0cf0e2ae9b1728eb7d126d5c6546bc7f116d21f6f0d6becc76962a351ed99efd"
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
        ]
      },
      "scenario_hash": "sha256:4784a3445f70385456c330429e10539f9a9a00b19050fcc66d54f28b83ba37f0"
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
        ]
      },
      "scenario_hash": "sha256:224f5e0125e85e80f02fc044510f5d939b363f24b392b8d26154405672a95f8f"
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
        "hash": "sha256:0cf0e2ae9b1728eb7d126d5c6546bc7f116d21f6f0d6becc76962a351ed99efd",
        "baseline_fingerprint": "sha256:fe55137cc10e6e8ba8755f3dd88b73cc841a15c22299f66902518cb3de71d4ab",
        "scenario": {
          "schema": "salli.scenario/1",
          "label": "As things are",
          "as_of": "2026-10-11",
          "horizon_years": 5,
          "changes": []
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
            "baseline": "15727.02",
            "scenario": "15727.02",
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
          "engine": "2",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
          "fire_strategy": null,
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": []
      },
      {
        "schema": "salli.scenario/1",
        "label": "Set aside 200.00 a month",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "currency": "EUR",
        "hash": "sha256:4784a3445f70385456c330429e10539f9a9a00b19050fcc66d54f28b83ba37f0",
        "baseline_fingerprint": "sha256:fe55137cc10e6e8ba8755f3dd88b73cc841a15c22299f66902518cb3de71d4ab",
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
          ]
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
            "stopped": []
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
            "baseline": "15727.02",
            "scenario": "15727.02",
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
          "engine": "2",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
          "fire_strategy": null,
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": []
      },
      {
        "schema": "salli.scenario/1",
        "label": "Set aside 500.00 a month",
        "as_of": "2026-10-11",
        "horizon_years": 5,
        "currency": "EUR",
        "hash": "sha256:224f5e0125e85e80f02fc044510f5d939b363f24b392b8d26154405672a95f8f",
        "baseline_fingerprint": "sha256:fe55137cc10e6e8ba8755f3dd88b73cc841a15c22299f66902518cb3de71d4ab",
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
          ]
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
            "stopped": []
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
            "baseline": "15727.02",
            "scenario": "15727.02",
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
          "engine": "2",
          "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
          "fire_strategy": null,
          "rule_sets": []
        },
        "data_as_of": "2026-10-09",
        "is_stale": false,
        "notes": []
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
        "scenario_hash": "sha256:0cf0e2ae9b1728eb7d126d5c6546bc7f116d21f6f0d6becc76962a351ed99efd"
      },
      {
        "figures": {
          "lowest_cash": "14013.25",
          "cash_in_12_months": "18201.47",
          "safe_to_spend": "15727.02",
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
          "fi_months_gained": -4
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
        "scenario_hash": "sha256:4784a3445f70385456c330429e10539f9a9a00b19050fcc66d54f28b83ba37f0"
      },
      {
        "figures": {
          "lowest_cash": "14013.25",
          "cash_in_12_months": "21801.47",
          "safe_to_spend": "15727.02",
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
          "fi_months_gained": -10
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
        "scenario_hash": "sha256:224f5e0125e85e80f02fc044510f5d939b363f24b392b8d26154405672a95f8f"
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
        "changes": []
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
        ]
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
        ]
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
