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
  "hash": "sha256:c96461abfc8eb370d812bfc45e4e8021b27a6b59d7f87e0e9981376f5d8601f7",
  "baseline_fingerprint": "sha256:58d04aceaabd7cb4575ff0bdb45a12686dcb7ddf1941113eb202ad3c673f05c7",
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
      "baseline": "15740.01",
      "scenario": "15085.90",
      "delta": "-654.11"
    },
    "lowest_date": {
      "baseline": "2026-10-18",
      "scenario": "2026-11-24",
      "delta_days": 37
    },
    "at_end": {
      "baseline": "39200.21",
      "scenario": "50654.09",
      "delta": "11453.88"
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
        "baseline": "365755.54",
        "scenario": "362562.26",
        "delta": "-3193.28"
      },
      "cash": {
        "baseline": "39200.21",
        "scenario": "50654.09",
        "delta": "11453.88"
      },
      "investments": {
        "baseline": "39637.48",
        "scenario": "39637.48",
        "delta": "0.00"
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
        "baseline": "473816.13",
        "scenario": "469546.07",
        "delta": "-4270.06"
      },
      "cash": {
        "baseline": "129270.40",
        "scenario": "125000.34",
        "delta": "-4270.06"
      },
      "investments": {
        "baseline": "46502.64",
        "scenario": "46502.64",
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
        "baseline": "611922.24",
        "scenario": "608431.58",
        "delta": "-3490.66"
      },
      "cash": {
        "baseline": "255142.68",
        "scenario": "251652.02",
        "delta": "-3490.66"
      },
      "investments": {
        "baseline": "56779.56",
        "scenario": "56779.56",
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
        "baseline": "895582.31",
        "scenario": "893650.45",
        "delta": "-1931.86"
      },
      "cash": {
        "baseline": "510933.48",
        "scenario": "509001.62",
        "delta": "-1931.86"
      },
      "investments": {
        "baseline": "84648.83",
        "scenario": "84648.83",
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
      "baseline": "8.29",
      "scenario": "7.95",
      "delta": "-0.34"
    },
    "at_end": {
      "baseline": "20.65",
      "scenario": "26.68",
      "delta": "6.03"
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
      "baseline": "2047-05",
      "scenario": "2047-04",
      "delta_months": -1
    },
    "months_gained": 1
  },
  "break_evens": [],
  "assumptions": {
    "status": "placeholder",
    "placeholders": [
      "real_return",
      "safe_withdrawal_rate"
    ],
    "message": "Using placeholder assumptions for the real return and the safe withdrawal rate: round figures, not forecasts. Set your own, with a source, to replace them. Figures are in today's money; set your inflation to see them in future money too.",
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
    "inflation"
  ],
  "versions": {
    "schema": "salli.scenario/1",
    "engine": "1",
    "fi_assumptions": "sha256:007c166ccd9fa0fe1706a636937eb7266f94db89dba293a2bc5823a91dbf1846",
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
      "hash": "sha256:c25f7c53f603182c68a2d1450079cc71cdcab7d61eb72e88ac47d1cce01b773e",
      "baseline_fingerprint": "sha256:58d04aceaabd7cb4575ff0bdb45a12686dcb7ddf1941113eb202ad3c673f05c7",
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
          "baseline": "15740.01",
          "scenario": "15072.91",
          "delta": "-667.10"
        },
        "lowest_date": {
          "baseline": "2026-10-18",
          "scenario": "2026-11-24",
          "delta_days": 37
        },
        "at_end": {
          "baseline": "39200.21",
          "scenario": "36800.21",
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
            "baseline": "365755.54",
            "scenario": "363355.54",
            "delta": "-2400.00"
          },
          "cash": {
            "baseline": "39200.21",
            "scenario": "36800.21",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "39637.48",
            "scenario": "39637.48",
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
            "baseline": "473816.13",
            "scenario": "471416.13",
            "delta": "-2400.00"
          },
          "cash": {
            "baseline": "129270.40",
            "scenario": "126870.40",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "46502.64",
            "scenario": "46502.64",
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
            "baseline": "611922.24",
            "scenario": "609522.24",
            "delta": "-2400.00"
          },
          "cash": {
            "baseline": "255142.68",
            "scenario": "252742.68",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "56779.56",
            "scenario": "56779.56",
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
            "baseline": "895582.31",
            "scenario": "893182.31",
            "delta": "-2400.00"
          },
          "cash": {
            "baseline": "510933.48",
            "scenario": "508533.48",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "84648.83",
            "scenario": "84648.83",
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
          "baseline": "8.29",
          "scenario": "7.94",
          "delta": "-0.35"
        },
        "at_end": {
          "baseline": "20.65",
          "scenario": "19.39",
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
          "baseline": "2047-05",
          "scenario": "2047-06",
          "delta_months": 1
        },
        "months_gained": -1
      },
      "break_evens": [],
      "assumptions": {
        "status": "placeholder",
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate"
        ],
        "message": "Using placeholder assumptions for the real return and the safe withdrawal rate: round figures, not forecasts. Set your own, with a source, to replace them. Figures are in today's money; set your inflation to see them in future money too.",
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
        "inflation"
      ],
      "versions": {
        "schema": "salli.scenario/1",
        "engine": "1",
        "fi_assumptions": "sha256:007c166ccd9fa0fe1706a636937eb7266f94db89dba293a2bc5823a91dbf1846",
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
      "hash": "sha256:07dfbff27a34bcc4eba237969c8a4f2635f37d2f9f255d5beed5af14f59f90cf",
      "baseline_fingerprint": "sha256:58d04aceaabd7cb4575ff0bdb45a12686dcb7ddf1941113eb202ad3c673f05c7",
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
          "baseline": "15740.01",
          "scenario": "15740.01",
          "delta": "0.00"
        },
        "lowest_date": {
          "baseline": "2026-10-18",
          "scenario": "2026-10-18",
          "delta_days": 0
        },
        "at_end": {
          "baseline": "39200.21",
          "scenario": "36917.16",
          "delta": "-2283.05"
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
            "baseline": "365755.54",
            "scenario": "363266.05",
            "delta": "-2489.49"
          },
          "cash": {
            "baseline": "39200.21",
            "scenario": "36917.16",
            "delta": "-2283.05"
          },
          "investments": {
            "baseline": "39637.48",
            "scenario": "39637.48",
            "delta": "0.00"
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
            "baseline": "473816.13",
            "scenario": "471325.45",
            "delta": "-2490.68"
          },
          "cash": {
            "baseline": "129270.40",
            "scenario": "126779.72",
            "delta": "-2490.68"
          },
          "investments": {
            "baseline": "46502.64",
            "scenario": "46502.64",
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
            "baseline": "611922.24",
            "scenario": "609431.56",
            "delta": "-2490.68"
          },
          "cash": {
            "baseline": "255142.68",
            "scenario": "252652.00",
            "delta": "-2490.68"
          },
          "investments": {
            "baseline": "56779.56",
            "scenario": "56779.56",
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
            "baseline": "895582.31",
            "scenario": "893091.63",
            "delta": "-2490.68"
          },
          "cash": {
            "baseline": "510933.48",
            "scenario": "508442.80",
            "delta": "-2490.68"
          },
          "investments": {
            "baseline": "84648.83",
            "scenario": "84648.83",
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
          "baseline": "8.29",
          "scenario": "8.29",
          "delta": "0.00"
        },
        "at_end": {
          "baseline": "20.65",
          "scenario": "19.45",
          "delta": "-1.20"
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
          "baseline": "2047-05",
          "scenario": "2047-06",
          "delta_months": 1
        },
        "months_gained": -1
      },
      "break_evens": [],
      "assumptions": {
        "status": "placeholder",
        "placeholders": [
          "real_return",
          "safe_withdrawal_rate"
        ],
        "message": "Using placeholder assumptions for the real return and the safe withdrawal rate: round figures, not forecasts. Set your own, with a source, to replace them. Figures are in today's money; set your inflation to see them in future money too.",
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
        "inflation"
      ],
      "versions": {
        "schema": "salli.scenario/1",
        "engine": "1",
        "fi_assumptions": "sha256:007c166ccd9fa0fe1706a636937eb7266f94db89dba293a2bc5823a91dbf1846",
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
          "this": "363355.54",
          "other": "363266.05",
          "delta": "89.49"
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
          "this": "471416.13",
          "other": "471325.45",
          "delta": "90.68"
        },
        {
          "figure": "monthly.5y.cash",
          "unit": "amount",
          "this": "126870.40",
          "other": "126779.72",
          "delta": "90.68"
        },
        {
          "figure": "monthly.10y.net_worth",
          "unit": "amount",
          "this": "609522.24",
          "other": "609431.56",
          "delta": "90.68"
        },
        {
          "figure": "monthly.10y.cash",
          "unit": "amount",
          "this": "252742.68",
          "other": "252652.00",
          "delta": "90.68"
        },
        {
          "figure": "monthly.20y.net_worth",
          "unit": "amount",
          "this": "893182.31",
          "other": "893091.63",
          "delta": "90.68"
        },
        {
          "figure": "monthly.20y.cash",
          "unit": "amount",
          "this": "508533.48",
          "other": "508442.80",
          "delta": "90.68"
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
          "this": "15072.91",
          "other": "15740.01",
          "delta": "-667.10"
        },
        {
          "figure": "resilience.lowest",
          "unit": "months_of_spending",
          "this": "7.94",
          "other": "8.29",
          "delta": "-0.35"
        },
        {
          "figure": "monthly.1y.cash",
          "unit": "amount",
          "this": "36800.21",
          "other": "36917.16",
          "delta": "-116.95"
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
          "this": "15740.01",
          "other": "15072.91",
          "delta": "667.10"
        },
        {
          "figure": "resilience.lowest",
          "unit": "months_of_spending",
          "this": "8.29",
          "other": "7.94",
          "delta": "0.35"
        },
        {
          "figure": "monthly.1y.cash",
          "unit": "amount",
          "this": "36917.16",
          "other": "36800.21",
          "delta": "116.95"
        }
      ],
      "gives_up": [
        {
          "figure": "monthly.1y.net_worth",
          "unit": "amount",
          "this": "363266.05",
          "other": "363355.54",
          "delta": "-89.49"
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
          "this": "471325.45",
          "other": "471416.13",
          "delta": "-90.68"
        },
        {
          "figure": "monthly.5y.cash",
          "unit": "amount",
          "this": "126779.72",
          "other": "126870.40",
          "delta": "-90.68"
        },
        {
          "figure": "monthly.10y.net_worth",
          "unit": "amount",
          "this": "609431.56",
          "other": "609522.24",
          "delta": "-90.68"
        },
        {
          "figure": "monthly.10y.cash",
          "unit": "amount",
          "this": "252652.00",
          "other": "252742.68",
          "delta": "-90.68"
        },
        {
          "figure": "monthly.20y.net_worth",
          "unit": "amount",
          "this": "893091.63",
          "other": "893182.31",
          "delta": "-90.68"
        },
        {
          "figure": "monthly.20y.cash",
          "unit": "amount",
          "this": "508442.80",
          "other": "508533.48",
          "delta": "-90.68"
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
            "baseline": "867667.93",
            "scenario": "865267.93",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "56734.45",
            "scenario": "56734.45",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2048-06",
            "scenario": "2048-07",
            "delta_months": 1
          },
          "months_gained": -1
        },
        "base": {
          "net_worth": {
            "baseline": "895582.31",
            "scenario": "893182.31",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "84648.83",
            "scenario": "84648.83",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2047-05",
            "scenario": "2047-06",
            "delta_months": 1
          },
          "months_gained": -1
        },
        "growth": {
          "net_worth": {
            "baseline": "937147.31",
            "scenario": "934747.31",
            "delta": "-2400.00"
          },
          "investments": {
            "baseline": "126213.83",
            "scenario": "126213.83",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2046-01",
            "scenario": "2046-02",
            "delta_months": 1
          },
          "months_gained": -1
        }
      },
      {
        "option": "Instalments",
        "conservative": {
          "net_worth": {
            "baseline": "867667.93",
            "scenario": "865177.25",
            "delta": "-2490.68"
          },
          "investments": {
            "baseline": "56734.45",
            "scenario": "56734.45",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2048-06",
            "scenario": "2048-07",
            "delta_months": 1
          },
          "months_gained": -1
        },
        "base": {
          "net_worth": {
            "baseline": "895582.31",
            "scenario": "893091.63",
            "delta": "-2490.68"
          },
          "investments": {
            "baseline": "84648.83",
            "scenario": "84648.83",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2047-05",
            "scenario": "2047-06",
            "delta_months": 1
          },
          "months_gained": -1
        },
        "growth": {
          "net_worth": {
            "baseline": "937147.31",
            "scenario": "934656.63",
            "delta": "-2490.68"
          },
          "investments": {
            "baseline": "126213.83",
            "scenario": "126213.83",
            "delta": "0.00"
          },
          "fi_month": {
            "baseline": "2046-01",
            "scenario": "2046-02",
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
      "status": "found",
      "unit": "rate",
      "value": "0",
      "low": "0",
      "high": "1",
      "ahead": null,
      "says": "Only at a loan rate of 0% does Instalments end the horizon with at least Pay cash's net worth; at any higher rate, Pay cash costs less."
    }
  ]
};
