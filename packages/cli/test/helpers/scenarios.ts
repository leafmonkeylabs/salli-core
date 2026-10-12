/**
 * What a real server answers for two scenarios on the golden household
 * ledger (tests/golden/household.py, as of Oct 11, 2026, in euros),
 * written by the scenario engine itself: a run, and a comparison of
 * paying cash against instalments.
 */
import type { ScenarioComparison, ScenarioRun } from '@leafmonkeylabs/salli-sdk';

export const SCENARIO_RUN: ScenarioRun = {
  "schema": "salli.scenario/1",
  "label": "Laptop",
  "as_of": "2026-10-11",
  "horizon_years": 20,
  "currency": "EUR",
  "hash": "sha256:6f2513783307730c6c0f34d2583fc5bd9fcb2bb0927da6e99a0d1cdd47d74560",
  "baseline_fingerprint": "sha256:c7e08824614b11110f1f6acc50864b04c84bf1e33de95e0810c6fe51133c6d01",
  "scenario": {
    "schema": "salli.scenario/1",
    "label": "Laptop",
    "as_of": "2026-10-11",
    "horizon_years": 20,
    "changes": [
      {
        "type": "one_off",
        "date": "2026-11-02",
        "amount": "-2400.00",
        "account": "chk",
        "label": "New laptop"
      },
      {
        "type": "loan",
        "principal": "18000.00",
        "annual_rate": "0.069",
        "term_months": 48,
        "start": "2026-12-01",
        "into": null,
        "label": "Car loan"
      },
      {
        "type": "stop_recurring",
        "key": "streamflix",
        "from": "2026-11-01",
        "label": null
      }
    ]
  },
  "changes": [
    {
      "index": 0,
      "type": "one_off",
      "label": "New laptop",
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
      "label": "Car loan",
      "debt_id": "scenario-loan-2",
      "payment": "430.20",
      "first_payment": "2027-01",
      "monthly": null,
      "for_good": null,
      "stopped": []
    },
    {
      "index": 2,
      "type": "stop_recurring",
      "label": "Stop Streamflix",
      "debt_id": null,
      "payment": null,
      "first_payment": null,
      "monthly": "12.99",
      "for_good": true,
      "stopped": [
        {
          "payee": "Streamflix",
          "cadence": "monthly",
          "amount": "-12.99",
          "currency": "EUR"
        }
      ]
    }
  ],
  "cash": {
    "start": "2026-10-11",
    "end": "2027-10-31",
    "lowest": {
      "baseline": "13998.91",
      "scenario": "11626.24",
      "delta": "-2372.67"
    },
    "lowest_date": {
      "baseline": "2027-02-24",
      "scenario": "2026-11-24",
      "delta_days": -92
    },
    "at_end": {
      "baseline": "15801.47",
      "scenario": "31401.47",
      "delta": "15600.00"
    },
    "safe_to_spend": {
      "baseline": "15727.02",
      "scenario": "15727.02",
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
        "scenario": "363010.64",
        "delta": "-3255.50"
      },
      "cash": {
        "baseline": "15801.47",
        "scenario": "31401.47",
        "delta": "15600.00"
      },
      "investments": {
        "baseline": "63546.81",
        "scenario": "59338.48",
        "delta": "-4208.34"
      },
      "debts": {
        "baseline": "13082.15",
        "scenario": "27729.31",
        "delta": "14647.16"
      }
    },
    {
      "years": 5,
      "month": "2031-10",
      "date": "2031-10-31",
      "net_worth": {
        "baseline": "485551.81",
        "scenario": "478903.79",
        "delta": "-6648.03"
      },
      "cash": {
        "baseline": "15801.47",
        "scenario": "31401.47",
        "delta": "15600.00"
      },
      "investments": {
        "baseline": "171707.25",
        "scenario": "149459.23",
        "delta": "-22248.03"
      },
      "debts": {
        "baseline": "1956.91",
        "scenario": "1956.91",
        "delta": "0.00"
      }
    },
    {
      "years": 10,
      "month": "2036-10",
      "date": "2036-10-31",
      "net_worth": {
        "baseline": "664379.50",
        "scenario": "653675.96",
        "delta": "-10703.54"
      },
      "cash": {
        "baseline": "15801.47",
        "scenario": "31401.47",
        "delta": "15600.00"
      },
      "investments": {
        "baseline": "348578.03",
        "scenario": "322274.49",
        "delta": "-26303.54"
      },
      "debts": {
        "baseline": "0.00",
        "scenario": "0.00",
        "delta": "0.00"
      }
    },
    {
      "years": 20,
      "month": "2046-10",
      "date": "2046-10-31",
      "net_worth": {
        "baseline": "1149349.20",
        "scenario": "1127647.79",
        "delta": "-21701.41"
      },
      "cash": {
        "baseline": "15801.47",
        "scenario": "31401.47",
        "delta": "15600.00"
      },
      "investments": {
        "baseline": "833547.73",
        "scenario": "796246.32",
        "delta": "-37301.41"
      },
      "debts": {
        "baseline": "0.00",
        "scenario": "0.00",
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
        "name": "Car loan",
        "source": "scenario",
        "paid_off": {
          "baseline": null,
          "scenario": "2030-12",
          "delta_months": null
        },
        "total_interest": {
          "baseline": "0.00",
          "scenario": "2649.46",
          "delta": "2649.46"
        }
      }
    ],
    "total_interest": {
      "baseline": "2009.25",
      "scenario": "4658.71",
      "delta": "2649.46"
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
      "scenario": "6.12",
      "delta": "-1.25"
    },
    "at_end": {
      "baseline": "8.32",
      "scenario": "16.54",
      "delta": "8.22"
    }
  },
  "fi": {
    "fi_number": {
      "baseline": "611127.00",
      "scenario": "607230.00",
      "delta": "-3897.00"
    },
    "monthly_spending": {
      "baseline": "2037.09",
      "scenario": "2024.10",
      "delta": "-12.99"
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
    "engine": "3",
    "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
    "fire_strategy": null,
    "rule_sets": []
  },
  "data_as_of": "2026-10-09",
  "is_stale": false,
  "notes": []
};

export const SCENARIO_COMPARISON: ScenarioComparison = {
  "as_of": "2026-10-11",
  "horizon_years": 20,
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
      "horizon_years": 20,
      "currency": "EUR",
      "hash": "sha256:b203a631d5c5ed9a54d6da8f092a874d10a8f504fe0c3330962aa022ebd97558",
      "baseline_fingerprint": "sha256:c7e08824614b11110f1f6acc50864b04c84bf1e33de95e0810c6fe51133c6d01",
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
            "account": null,
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
        },
        {
          "years": 10,
          "month": "2036-10",
          "date": "2036-10-31",
          "net_worth": {
            "baseline": "664379.50",
            "scenario": "661979.50",
            "delta": "-2400.00"
          },
          "cash": {
            "baseline": "15801.47",
            "scenario": "13401.47",
            "delta": "-2400.00"
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
          }
        },
        {
          "years": 20,
          "month": "2046-10",
          "date": "2046-10-31",
          "net_worth": {
            "baseline": "1149349.20",
            "scenario": "1146949.20",
            "delta": "-2400.00"
          },
          "cash": {
            "baseline": "15801.47",
            "scenario": "13401.47",
            "delta": "-2400.00"
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
        "engine": "3",
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
      "label": "Instalments",
      "as_of": "2026-10-11",
      "horizon_years": 20,
      "currency": "EUR",
      "hash": "sha256:00ce8b55a091b848b4f30a8885e073f5a38819c22491ec02f304f28501b29dfb",
      "baseline_fingerprint": "sha256:c7e08824614b11110f1f6acc50864b04c84bf1e33de95e0810c6fe51133c6d01",
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
            "account": null,
            "label": "Laptop"
          },
          {
            "type": "loan",
            "principal": "2400.00",
            "annual_rate": "0.069",
            "term_months": 12,
            "start": "2026-11-02",
            "into": null,
            "label": "Laptop instalments"
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
          "label": "Laptop instalments",
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
        },
        {
          "years": 10,
          "month": "2036-10",
          "date": "2036-10-31",
          "net_worth": {
            "baseline": "664379.50",
            "scenario": "660757.60",
            "delta": "-3621.90"
          },
          "cash": {
            "baseline": "15801.47",
            "scenario": "15801.47",
            "delta": "0.00"
          },
          "investments": {
            "baseline": "348578.03",
            "scenario": "344956.13",
            "delta": "-3621.90"
          },
          "debts": {
            "baseline": "0.00",
            "scenario": "0.00",
            "delta": "0.00"
          }
        },
        {
          "years": 20,
          "month": "2046-10",
          "date": "2046-10-31",
          "net_worth": {
            "baseline": "1149349.20",
            "scenario": "1143949.56",
            "delta": "-5399.64"
          },
          "cash": {
            "baseline": "15801.47",
            "scenario": "15801.47",
            "delta": "0.00"
          },
          "investments": {
            "baseline": "833547.73",
            "scenario": "828148.09",
            "delta": "-5399.64"
          },
          "debts": {
            "baseline": "0.00",
            "scenario": "0.00",
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
        "engine": "3",
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
          "figure": "monthly.10y.net_worth",
          "unit": "amount",
          "this": "661979.50",
          "other": "660757.60",
          "delta": "1221.90"
        },
        {
          "figure": "monthly.10y.investments",
          "unit": "amount",
          "this": "348578.03",
          "other": "344956.13",
          "delta": "3621.90"
        },
        {
          "figure": "monthly.20y.net_worth",
          "unit": "amount",
          "this": "1146949.20",
          "other": "1143949.56",
          "delta": "2999.64"
        },
        {
          "figure": "monthly.20y.investments",
          "unit": "amount",
          "this": "833547.73",
          "other": "828148.09",
          "delta": "5399.64"
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
        },
        {
          "figure": "monthly.10y.cash",
          "unit": "amount",
          "this": "13401.47",
          "other": "15801.47",
          "delta": "-2400.00"
        },
        {
          "figure": "monthly.20y.cash",
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
        },
        {
          "figure": "monthly.10y.cash",
          "unit": "amount",
          "this": "15801.47",
          "other": "13401.47",
          "delta": "2400.00"
        },
        {
          "figure": "monthly.20y.cash",
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
          "figure": "monthly.10y.net_worth",
          "unit": "amount",
          "this": "660757.60",
          "other": "661979.50",
          "delta": "-1221.90"
        },
        {
          "figure": "monthly.10y.investments",
          "unit": "amount",
          "this": "344956.13",
          "other": "348578.03",
          "delta": "-3621.90"
        },
        {
          "figure": "monthly.20y.net_worth",
          "unit": "amount",
          "this": "1143949.56",
          "other": "1146949.20",
          "delta": "-2999.64"
        },
        {
          "figure": "monthly.20y.investments",
          "unit": "amount",
          "this": "828148.09",
          "other": "833547.73",
          "delta": "-5399.64"
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
            "baseline": "977656.19",
            "scenario": "975256.19",
            "delta": "-2400.00"
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
            "scenario": "1146949.20",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "833547.73",
            "scenario": "833547.73",
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
            "baseline": "1380323.33",
            "scenario": "1377923.33",
            "delta": "-2400.00"
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
        "option": "Instalments",
        "conservative": {
          "net_worth": {
            "baseline": "977656.19",
            "scenario": "973987.81",
            "delta": "-3668.38"
          },
          "investments": {
            "baseline": "661854.72",
            "scenario": "658186.34",
            "delta": "-3668.38"
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
            "baseline": "1149349.20",
            "scenario": "1143949.56",
            "delta": "-5399.64"
          },
          "investments": {
            "baseline": "833547.73",
            "scenario": "828148.09",
            "delta": "-5399.64"
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
            "baseline": "1380323.33",
            "scenario": "1372380.21",
            "delta": "-7943.12"
          },
          "investments": {
            "baseline": "1064521.86",
            "scenario": "1056578.74",
            "delta": "-7943.12"
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

/**
 * A raise of 1,000.00 a month before tax, tagged with the salary role, on
 * the fictional XA 2031 household (tests/golden/taxed.py, as of
 * 2031-06-30, in New Zealand dollars), written by the scenario engine.
 */
export const TAXED_RUN: ScenarioRun = {
  "schema": "salli.scenario/1",
  "label": "Raise",
  "as_of": "2031-06-30",
  "horizon_years": 20,
  "currency": "NZD",
  "hash": "sha256:6e67412437b404b701a7c7edfb4ded7fa31242e0094f67c305d58ce97492e522",
  "baseline_fingerprint": "sha256:a578b5182f732beb18927582d6f4df47c1df7480735ca96dec7dadb9fe276335",
  "scenario": {
    "schema": "salli.scenario/1",
    "label": "Raise",
    "as_of": "2031-06-30",
    "horizon_years": 20,
    "changes": [
      {
        "type": "income_change",
        "monthly": "1000.00",
        "from": "2031-07-01",
        "to": null,
        "tax_role": "salary",
        "label": "Raise"
      }
    ],
    "tax": null
  },
  "changes": [
    {
      "index": 0,
      "type": "income_change",
      "label": "Raise",
      "debt_id": null,
      "payment": null,
      "first_payment": null,
      "monthly": "1000.00",
      "for_good": true,
      "stopped": []
    }
  ],
  "cash": {
    "start": "2031-06-30",
    "end": "2032-06-30",
    "lowest": {
      "baseline": "23500.00",
      "scenario": "24500.00",
      "delta": "1000.00"
    },
    "lowest_date": {
      "baseline": "2031-07-01",
      "scenario": "2031-07-01",
      "delta_days": 0
    },
    "at_end": {
      "baseline": "25000.00",
      "scenario": "25000.00",
      "delta": "0.00"
    },
    "safe_to_spend": {
      "baseline": "23500.00",
      "scenario": "24500.00",
      "delta": "1000.00"
    },
    "safe_until": "2031-07-25",
    "accounts": [
      {
        "account_id": "chk",
        "name": "Chk",
        "currency": "NZD",
        "lowest": {
          "baseline": "23500.00",
          "scenario": "23500.00",
          "delta": "0.00"
        },
        "lowest_date": {
          "baseline": "2031-07-01",
          "scenario": "2031-07-01",
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
      "month": "2032-06",
      "date": "2032-06-30",
      "net_worth": {
        "baseline": "55556.16",
        "scenario": "64115.97",
        "delta": "8559.81"
      },
      "cash": {
        "baseline": "25000.00",
        "scenario": "25000.00",
        "delta": "0.00"
      },
      "investments": {
        "baseline": "30556.16",
        "scenario": "39115.97",
        "delta": "8559.81"
      },
      "debts": {
        "baseline": "0.00",
        "scenario": "0.00",
        "delta": "0.00"
      }
    },
    {
      "years": 5,
      "month": "2036-06",
      "date": "2036-06-30",
      "net_worth": {
        "baseline": "190747.45",
        "scenario": "235429.54",
        "delta": "44682.09"
      },
      "cash": {
        "baseline": "25000.00",
        "scenario": "25000.00",
        "delta": "0.00"
      },
      "investments": {
        "baseline": "165747.45",
        "scenario": "210429.54",
        "delta": "44682.09"
      },
      "debts": {
        "baseline": "0.00",
        "scenario": "0.00",
        "delta": "0.00"
      }
    },
    {
      "years": 10,
      "month": "2041-06",
      "date": "2041-06-30",
      "net_worth": {
        "baseline": "393124.51",
        "scenario": "491880.51",
        "delta": "98756.00"
      },
      "cash": {
        "baseline": "25000.00",
        "scenario": "25000.00",
        "delta": "0.00"
      },
      "investments": {
        "baseline": "368124.51",
        "scenario": "466880.51",
        "delta": "98756.00"
      },
      "debts": {
        "baseline": "0.00",
        "scenario": "0.00",
        "delta": "0.00"
      }
    },
    {
      "years": 20,
      "month": "2051-06",
      "date": "2051-06-30",
      "net_worth": {
        "baseline": "941936.57",
        "scenario": "1187331.78",
        "delta": "245395.21"
      },
      "cash": {
        "baseline": "25000.00",
        "scenario": "25000.00",
        "delta": "0.00"
      },
      "investments": {
        "baseline": "916936.57",
        "scenario": "1162331.78",
        "delta": "245395.21"
      },
      "debts": {
        "baseline": "0.00",
        "scenario": "0.00",
        "delta": "0.00"
      }
    }
  ],
  "debts": {
    "items": [],
    "total_interest": {
      "baseline": "0.00",
      "scenario": "0.00",
      "delta": "0.00"
    },
    "debt_free": {
      "baseline": null,
      "scenario": null,
      "delta_months": null
    }
  },
  "resilience": {
    "basis": "all",
    "monthly_spending": "1500.00",
    "lowest": {
      "baseline": "15.67",
      "scenario": "16.33",
      "delta": "0.67"
    },
    "at_end": {
      "baseline": "16.67",
      "scenario": "16.67",
      "delta": "0.00"
    }
  },
  "fi": {
    "fi_number": {
      "baseline": "450000.00",
      "scenario": "450000.00",
      "delta": "0.00"
    },
    "monthly_spending": {
      "baseline": "1500.00",
      "scenario": "1500.00",
      "delta": "0.00"
    },
    "fi_month": {
      "baseline": "2042-09",
      "scenario": "2040-09",
      "delta_months": -24
    },
    "months_gained": 24
  },
  "break_evens": [],
  "tax": {
    "status": "computed",
    "reason": null,
    "years": [
      {
        "year": "2031",
        "start": "2031-01-01",
        "end": "2031-12-31",
        "status": "computed",
        "reason": null,
        "rules": {
          "country": "XA",
          "region": null,
          "year": "2031",
          "rule_set_id": "rs-xa-2031",
          "version": 1,
          "content_hash": "b07796bbae5e53327ecf9776e34161f5b5ee9c66437c78b2f58ab2dcd3033760",
          "carried_forward": false
        },
        "currency": "NZD",
        "roles": [
          {
            "key": "salary",
            "kind": "income",
            "label": "Salary",
            "actual": "24000.00",
            "projected": "48000.00",
            "scenario": "54000.00"
          }
        ],
        "net": {
          "baseline": "7200.00",
          "scenario": "8800.00",
          "delta": "1600.00"
        },
        "change": "1600.00",
        "monthly": [
          {
            "month": "2031-07",
            "amount": "266.67"
          },
          {
            "month": "2031-08",
            "amount": "266.67"
          },
          {
            "month": "2031-09",
            "amount": "266.67"
          },
          {
            "month": "2031-10",
            "amount": "266.67"
          },
          {
            "month": "2031-11",
            "amount": "266.67"
          },
          {
            "month": "2031-12",
            "amount": "266.65"
          }
        ]
      },
      {
        "year": "2032",
        "start": "2032-01-01",
        "end": "2032-12-31",
        "status": "computed",
        "reason": null,
        "rules": {
          "country": "XA",
          "region": null,
          "year": "2031",
          "rule_set_id": "rs-xa-2031",
          "version": 1,
          "content_hash": "b07796bbae5e53327ecf9776e34161f5b5ee9c66437c78b2f58ab2dcd3033760",
          "carried_forward": true
        },
        "currency": "NZD",
        "roles": [
          {
            "key": "salary",
            "kind": "income",
            "label": "Salary",
            "actual": "0.00",
            "projected": "48000.00",
            "scenario": "60000.00"
          }
        ],
        "net": {
          "baseline": "7200.00",
          "scenario": "11200.00",
          "delta": "4000.00"
        },
        "change": "4000.00",
        "monthly": [
          {
            "month": "2032-01",
            "amount": "333.33"
          },
          {
            "month": "2032-02",
            "amount": "333.33"
          },
          {
            "month": "2032-03",
            "amount": "333.33"
          },
          {
            "month": "2032-04",
            "amount": "333.33"
          },
          {
            "month": "2032-05",
            "amount": "333.33"
          },
          {
            "month": "2032-06",
            "amount": "333.33"
          },
          {
            "month": "2032-07",
            "amount": "333.33"
          },
          {
            "month": "2032-08",
            "amount": "333.33"
          },
          {
            "month": "2032-09",
            "amount": "333.33"
          },
          {
            "month": "2032-10",
            "amount": "333.33"
          },
          {
            "month": "2032-11",
            "amount": "333.33"
          },
          {
            "month": "2032-12",
            "amount": "333.37"
          }
        ]
      },
      {
        "year": "2036",
        "start": "2036-01-01",
        "end": "2036-12-31",
        "status": "computed",
        "reason": null,
        "rules": {
          "country": "XA",
          "region": null,
          "year": "2031",
          "rule_set_id": "rs-xa-2031",
          "version": 1,
          "content_hash": "b07796bbae5e53327ecf9776e34161f5b5ee9c66437c78b2f58ab2dcd3033760",
          "carried_forward": true
        },
        "currency": "NZD",
        "roles": [
          {
            "key": "salary",
            "kind": "income",
            "label": "Salary",
            "actual": "0.00",
            "projected": "48000.00",
            "scenario": "60000.00"
          }
        ],
        "net": {
          "baseline": "7200.00",
          "scenario": "11200.00",
          "delta": "4000.00"
        },
        "change": "4000.00",
        "monthly": [
          {
            "month": "2036-01",
            "amount": "333.33"
          },
          {
            "month": "2036-02",
            "amount": "333.33"
          },
          {
            "month": "2036-03",
            "amount": "333.33"
          },
          {
            "month": "2036-04",
            "amount": "333.33"
          },
          {
            "month": "2036-05",
            "amount": "333.33"
          },
          {
            "month": "2036-06",
            "amount": "333.33"
          },
          {
            "month": "2036-07",
            "amount": "333.33"
          },
          {
            "month": "2036-08",
            "amount": "333.33"
          },
          {
            "month": "2036-09",
            "amount": "333.33"
          },
          {
            "month": "2036-10",
            "amount": "333.33"
          },
          {
            "month": "2036-11",
            "amount": "333.33"
          },
          {
            "month": "2036-12",
            "amount": "333.37"
          }
        ]
      },
      {
        "year": "2041",
        "start": "2041-01-01",
        "end": "2041-12-31",
        "status": "computed",
        "reason": null,
        "rules": {
          "country": "XA",
          "region": null,
          "year": "2031",
          "rule_set_id": "rs-xa-2031",
          "version": 1,
          "content_hash": "b07796bbae5e53327ecf9776e34161f5b5ee9c66437c78b2f58ab2dcd3033760",
          "carried_forward": true
        },
        "currency": "NZD",
        "roles": [
          {
            "key": "salary",
            "kind": "income",
            "label": "Salary",
            "actual": "0.00",
            "projected": "48000.00",
            "scenario": "60000.00"
          }
        ],
        "net": {
          "baseline": "7200.00",
          "scenario": "11200.00",
          "delta": "4000.00"
        },
        "change": "4000.00",
        "monthly": [
          {
            "month": "2041-01",
            "amount": "333.33"
          },
          {
            "month": "2041-02",
            "amount": "333.33"
          },
          {
            "month": "2041-03",
            "amount": "333.33"
          },
          {
            "month": "2041-04",
            "amount": "333.33"
          },
          {
            "month": "2041-05",
            "amount": "333.33"
          },
          {
            "month": "2041-06",
            "amount": "333.33"
          },
          {
            "month": "2041-07",
            "amount": "333.33"
          },
          {
            "month": "2041-08",
            "amount": "333.33"
          },
          {
            "month": "2041-09",
            "amount": "333.33"
          },
          {
            "month": "2041-10",
            "amount": "333.33"
          },
          {
            "month": "2041-11",
            "amount": "333.33"
          },
          {
            "month": "2041-12",
            "amount": "333.37"
          }
        ]
      },
      {
        "year": "2051",
        "start": "2051-01-01",
        "end": "2051-12-31",
        "status": "computed",
        "reason": null,
        "rules": {
          "country": "XA",
          "region": null,
          "year": "2031",
          "rule_set_id": "rs-xa-2031",
          "version": 1,
          "content_hash": "b07796bbae5e53327ecf9776e34161f5b5ee9c66437c78b2f58ab2dcd3033760",
          "carried_forward": true
        },
        "currency": "NZD",
        "roles": [
          {
            "key": "salary",
            "kind": "income",
            "label": "Salary",
            "actual": "0.00",
            "projected": "48000.00",
            "scenario": "60000.00"
          }
        ],
        "net": {
          "baseline": "7200.00",
          "scenario": "11200.00",
          "delta": "4000.00"
        },
        "change": "4000.00",
        "monthly": [
          {
            "month": "2051-01",
            "amount": "333.33"
          },
          {
            "month": "2051-02",
            "amount": "333.33"
          },
          {
            "month": "2051-03",
            "amount": "333.33"
          },
          {
            "month": "2051-04",
            "amount": "333.33"
          },
          {
            "month": "2051-05",
            "amount": "333.33"
          },
          {
            "month": "2051-06",
            "amount": "333.33"
          },
          {
            "month": "2051-07",
            "amount": "333.33"
          },
          {
            "month": "2051-08",
            "amount": "333.33"
          },
          {
            "month": "2051-09",
            "amount": "333.33"
          },
          {
            "month": "2051-10",
            "amount": "333.33"
          },
          {
            "month": "2051-11",
            "amount": "333.33"
          },
          {
            "month": "2051-12",
            "amount": "333.37"
          }
        ]
      }
    ],
    "this_year": {
      "year": "2031",
      "start": "2031-01-01",
      "end": "2031-12-31",
      "status": "computed",
      "reason": null,
      "rules": {
        "country": "XA",
        "region": null,
        "year": "2031",
        "rule_set_id": "rs-xa-2031",
        "version": 1,
        "content_hash": "b07796bbae5e53327ecf9776e34161f5b5ee9c66437c78b2f58ab2dcd3033760",
        "carried_forward": false
      },
      "currency": "NZD",
      "roles": [
        {
          "key": "salary",
          "kind": "income",
          "label": "Salary",
          "actual": "24000.00",
          "projected": "48000.00",
          "scenario": "54000.00"
        }
      ],
      "net": {
        "baseline": "7200.00",
        "scenario": "8800.00",
        "delta": "1600.00"
      },
      "change": "1600.00",
      "monthly": [
        {
          "month": "2031-07",
          "amount": "266.67"
        },
        {
          "month": "2031-08",
          "amount": "266.67"
        },
        {
          "month": "2031-09",
          "amount": "266.67"
        },
        {
          "month": "2031-10",
          "amount": "266.67"
        },
        {
          "month": "2031-11",
          "amount": "266.67"
        },
        {
          "month": "2031-12",
          "amount": "266.65"
        }
      ]
    },
    "change_this_year": "1600.00",
    "total_change": "79599.98",
    "carried_forward": true
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
    "tax_rules_carried_forward"
  ],
  "versions": {
    "schema": "salli.scenario/1",
    "engine": "3",
    "fi_assumptions": "sha256:536c575a8620d3689284c70b65a7b89320dea5a1cd66bc71ea5a291d02c64f0e",
    "fire_strategy": null,
    "rule_sets": [
      {
        "country": "XA",
        "region": null,
        "year": "2031",
        "rule_set_id": "rs-xa-2031",
        "version": 1,
        "content_hash": "b07796bbae5e53327ecf9776e34161f5b5ee9c66437c78b2f58ab2dcd3033760"
      }
    ]
  },
  "data_as_of": "2031-06-25",
  "is_stale": false,
  "notes": []
};
