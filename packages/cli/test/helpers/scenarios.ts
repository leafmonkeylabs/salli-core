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
  "hash": "sha256:01756a0b53033b31a1597dcb5d8dfbcea9a89cf8ffa186304cc5b2dc81941b57",
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
      "hash": "sha256:c67789751bb9861552d93e1440317e8fbbb40fca19d147a1c2213e8ecaec7fe6",
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
      "label": "Instalments",
      "as_of": "2026-10-11",
      "horizon_years": 20,
      "currency": "EUR",
      "hash": "sha256:2ad20594087b83c8e2731062613844d25b4c1af17e4e8270eff1deeb381b35cb",
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
      "says": "Pay cash ends the horizon with more net worth at every loan rate from 0% to 100%."
    }
  ]
};
