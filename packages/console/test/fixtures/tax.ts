/**
 * What a real server answers the console's tax pages on the fictional rules
 * "XA 2031" (tests/golden/rules/xa2031.json, with a filing deadline) and the
 * taxed household (tests/golden/taxed.py, as of Jun 30, 2031, in New Zealand
 * dollars; XA is a user-assigned code, no country's). Version 1 is the
 * person's, active, with a computation; version 2 an agent's, proposed;
 * version 3 an agent's draft whose worked example fails. The writes at the
 * end (activating version 2, first from a sign-in six minutes old, then
 * just after the password; computing again; version 3 validated and its
 * proposal refused) come after every read.
 *
 * Written by tests/console_fixtures.py (`uv run python -m tests.console_fixtures`):
 * tests/contract/test_console_fixtures.py fails while it differs from what
 * the server answers. Don't edit it by hand.
 */
import type { LatestTaxComputation, ProblemDetails, TaxComputation, TaxLineExplanation, TaxRuleDiff, TaxRuleExport, TaxRuleSet, TaxRuleSetVersion, TaxYearStatus } from '@leafmonkeylabs/salli-sdk';

export const RULE_SETS: TaxRuleSet[] = [
  {
    "id": "0000232a-5a11-4000-8000-000000009002",
    "country": "XA",
    "region": null,
    "year_label": "2031",
    "name": "XA 2031",
    "active_version_id": "0000232b-5a11-4000-8000-000000009003",
    "created_at": "2031-02-01T09:00:00Z",
    "updated_at": "2031-06-25T11:00:00Z",
    "versions": [
      {
        "id": "0000232b-5a11-4000-8000-000000009003",
        "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
        "version": 1,
        "status": "active",
        "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
        "author_kind": "user",
        "author_name": null,
        "change_note": "From the Act",
        "created_at": "2031-02-01T09:00:00Z",
        "proposed_at": null,
        "activated_at": "2031-02-01T09:00:00Z",
        "superseded_at": null
      },
      {
        "id": "00002331-5a11-4000-8000-000000009009",
        "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
        "version": 2,
        "status": "proposed",
        "content_hash": "702c5a4ac8f7b3c76f63524af1cf0a6927598ee1c720fa51896de9fadabac2ce",
        "author_kind": "agent",
        "author_name": "Claude",
        "change_note": "The 2031 budget raises the relief to 12,500.",
        "created_at": "2031-06-20T14:00:00Z",
        "proposed_at": "2031-06-20T14:00:00Z",
        "activated_at": null,
        "superseded_at": null
      },
      {
        "id": "00002334-5a11-4000-8000-000000009012",
        "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
        "version": 3,
        "status": "draft",
        "content_hash": "f99790f5018b66d8ce451fcfea35f24e2e50b23688b1f0519adfee5f52aef13a",
        "author_kind": "agent",
        "author_name": "Claude",
        "change_note": "Rounding the examples.",
        "created_at": "2031-06-25T11:00:00Z",
        "proposed_at": null,
        "activated_at": null,
        "superseded_at": null
      }
    ]
  }
];

export const RULE_SET: TaxRuleSet = {
  "id": "0000232a-5a11-4000-8000-000000009002",
  "country": "XA",
  "region": null,
  "year_label": "2031",
  "name": "XA 2031",
  "active_version_id": "0000232b-5a11-4000-8000-000000009003",
  "created_at": "2031-02-01T09:00:00Z",
  "updated_at": "2031-06-25T11:00:00Z",
  "versions": [
    {
      "id": "0000232b-5a11-4000-8000-000000009003",
      "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
      "version": 1,
      "status": "active",
      "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
      "author_kind": "user",
      "author_name": null,
      "change_note": "From the Act",
      "created_at": "2031-02-01T09:00:00Z",
      "proposed_at": null,
      "activated_at": "2031-02-01T09:00:00Z",
      "superseded_at": null
    },
    {
      "id": "00002331-5a11-4000-8000-000000009009",
      "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
      "version": 2,
      "status": "proposed",
      "content_hash": "702c5a4ac8f7b3c76f63524af1cf0a6927598ee1c720fa51896de9fadabac2ce",
      "author_kind": "agent",
      "author_name": "Claude",
      "change_note": "The 2031 budget raises the relief to 12,500.",
      "created_at": "2031-06-20T14:00:00Z",
      "proposed_at": "2031-06-20T14:00:00Z",
      "activated_at": null,
      "superseded_at": null
    },
    {
      "id": "00002334-5a11-4000-8000-000000009012",
      "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
      "version": 3,
      "status": "draft",
      "content_hash": "f99790f5018b66d8ce451fcfea35f24e2e50b23688b1f0519adfee5f52aef13a",
      "author_kind": "agent",
      "author_name": "Claude",
      "change_note": "Rounding the examples.",
      "created_at": "2031-06-25T11:00:00Z",
      "proposed_at": null,
      "activated_at": null,
      "superseded_at": null
    }
  ]
};

/**
 * The person's, active.
 */
export const VERSION_1: TaxRuleSetVersion = {
  "id": "0000232b-5a11-4000-8000-000000009003",
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "version": 1,
  "status": "active",
  "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
  "author_kind": "user",
  "author_name": null,
  "change_note": "From the Act",
  "created_at": "2031-02-01T09:00:00Z",
  "proposed_at": null,
  "activated_at": "2031-02-01T09:00:00Z",
  "superseded_at": null,
  "document": {
    "schema": "salli.tax/1",
    "jurisdiction": {
      "country": "XA",
      "region": null
    },
    "year": {
      "label": "2031",
      "start": "2031-01-01",
      "end": "2031-12-31"
    },
    "currency": "NZD",
    "sources": [
      {
        "id": "act",
        "url": "https://example.org/xa/income-tax-act",
        "title": "XA Income Tax Act (fictional)",
        "retrieved": "2031-01-15"
      }
    ],
    "roles": [
      {
        "key": "salary",
        "kind": "income",
        "label": "Salary"
      },
      {
        "key": "pension",
        "kind": "deduction",
        "label": "Pension contributions"
      },
      {
        "key": "tax_withheld",
        "kind": "withholding",
        "label": "Tax withheld"
      }
    ],
    "band_tables": {
      "main": {
        "label": "Rates on taxable income",
        "bands": [
          {
            "upto": "40000",
            "rate": "0.20"
          },
          {
            "upto": null,
            "rate": "0.40"
          }
        ],
        "source": "act"
      }
    },
    "blocks": [
      {
        "type": "relief",
        "key": "relief",
        "label": "Relief",
        "of": "line.taxable_income",
        "amount": "12000",
        "source": "act"
      },
      {
        "type": "schedule",
        "key": "income_tax",
        "label": "Income tax",
        "of": "line.relief.remaining",
        "table": "main"
      },
      {
        "type": "credit",
        "key": "withholding",
        "label": "Tax withheld",
        "of": "role.tax_withheld",
        "refundable": true
      }
    ],
    "lines": [
      {
        "key": "taxable_income",
        "label": "Salary less pension contributions",
        "expr": "max(0, role.salary - role.pension)"
      },
      {
        "key": "balance",
        "label": "Tax less withholding",
        "expr": "line.income_tax - line.withholding"
      }
    ],
    "result": {
      "net": "line.balance",
      "round": {
        "mode": "nearest",
        "unit": "0.01"
      }
    },
    "suggested_accounts": [
      {
        "code": "1450",
        "name": "Tax withheld",
        "type": "asset",
        "tax_role": "tax_withheld"
      }
    ],
    "examples": [
      {
        "name": "48,000",
        "source": "act",
        "inputs": {
          "salary": "48000"
        },
        "expected": {
          "payable": "7200"
        }
      },
      {
        "name": "54,000",
        "source": "act",
        "inputs": {
          "salary": "54000"
        },
        "expected": {
          "payable": "8800"
        }
      },
      {
        "name": "60,000",
        "source": "act",
        "inputs": {
          "salary": "60000"
        },
        "expected": {
          "payable": "11200"
        }
      },
      {
        "name": "A pension contribution",
        "source": "act",
        "inputs": {
          "salary": "54000",
          "pension": "6000"
        },
        "expected": {
          "payable": "7200"
        }
      }
    ],
    "deadlines": [
      {
        "key": "return",
        "label": "Return due",
        "date": "2032-04-30",
        "source": "act"
      }
    ]
  },
  "validation": {
    "ok": true,
    "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
    "validated_at": "2031-02-01T09:00:00Z",
    "errors": [],
    "warnings": [],
    "examples": [
      {
        "name": "48,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "54,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "60,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "A pension contribution",
        "passed": true,
        "error": null,
        "mismatches": []
      }
    ]
  }
};

/**
 * An agent's, proposed.
 */
export const VERSION_2: TaxRuleSetVersion = {
  "id": "00002331-5a11-4000-8000-000000009009",
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "version": 2,
  "status": "proposed",
  "content_hash": "702c5a4ac8f7b3c76f63524af1cf0a6927598ee1c720fa51896de9fadabac2ce",
  "author_kind": "agent",
  "author_name": "Claude",
  "change_note": "The 2031 budget raises the relief to 12,500.",
  "created_at": "2031-06-20T14:00:00Z",
  "proposed_at": "2031-06-20T14:00:00Z",
  "activated_at": null,
  "superseded_at": null,
  "document": {
    "schema": "salli.tax/1",
    "jurisdiction": {
      "country": "XA",
      "region": null
    },
    "year": {
      "label": "2031",
      "start": "2031-01-01",
      "end": "2031-12-31"
    },
    "currency": "NZD",
    "sources": [
      {
        "id": "act",
        "url": "https://example.org/xa/income-tax-act",
        "title": "XA Income Tax Act (fictional)",
        "retrieved": "2031-01-15"
      },
      {
        "id": "budget",
        "url": "https://example.org/xa/budget-2031",
        "title": "XA Budget 2031 (fictional)",
        "retrieved": "2031-06-01"
      }
    ],
    "roles": [
      {
        "key": "salary",
        "kind": "income",
        "label": "Salary"
      },
      {
        "key": "pension",
        "kind": "deduction",
        "label": "Pension contributions"
      },
      {
        "key": "tax_withheld",
        "kind": "withholding",
        "label": "Tax withheld"
      }
    ],
    "band_tables": {
      "main": {
        "label": "Rates on taxable income",
        "bands": [
          {
            "upto": "40000",
            "rate": "0.20"
          },
          {
            "upto": null,
            "rate": "0.40"
          }
        ],
        "source": "act"
      }
    },
    "blocks": [
      {
        "type": "relief",
        "key": "relief",
        "label": "Relief",
        "of": "line.taxable_income",
        "amount": "12500",
        "source": "budget"
      },
      {
        "type": "schedule",
        "key": "income_tax",
        "label": "Income tax",
        "of": "line.relief.remaining",
        "table": "main"
      },
      {
        "type": "credit",
        "key": "withholding",
        "label": "Tax withheld",
        "of": "role.tax_withheld",
        "refundable": true
      }
    ],
    "lines": [
      {
        "key": "taxable_income",
        "label": "Salary less pension contributions",
        "expr": "max(0, role.salary - role.pension)"
      },
      {
        "key": "balance",
        "label": "Tax less withholding",
        "expr": "line.income_tax - line.withholding"
      }
    ],
    "result": {
      "net": "line.balance",
      "round": {
        "mode": "nearest",
        "unit": "0.01"
      }
    },
    "suggested_accounts": [
      {
        "code": "1450",
        "name": "Tax withheld",
        "type": "asset",
        "tax_role": "tax_withheld"
      }
    ],
    "examples": [
      {
        "name": "48,000",
        "source": "budget",
        "inputs": {
          "salary": "48000"
        },
        "expected": {
          "payable": "7100"
        }
      },
      {
        "name": "54,000",
        "source": "budget",
        "inputs": {
          "salary": "54000"
        },
        "expected": {
          "payable": "8600"
        }
      },
      {
        "name": "60,000",
        "source": "budget",
        "inputs": {
          "salary": "60000"
        },
        "expected": {
          "payable": "11000"
        }
      },
      {
        "name": "A pension contribution",
        "source": "budget",
        "inputs": {
          "salary": "54000",
          "pension": "6000"
        },
        "expected": {
          "payable": "7100"
        }
      }
    ],
    "deadlines": [
      {
        "key": "return",
        "label": "Return due",
        "date": "2032-04-30",
        "source": "act"
      }
    ]
  },
  "validation": {
    "ok": true,
    "content_hash": "702c5a4ac8f7b3c76f63524af1cf0a6927598ee1c720fa51896de9fadabac2ce",
    "validated_at": "2031-06-20T14:00:00Z",
    "errors": [],
    "warnings": [],
    "examples": [
      {
        "name": "48,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "54,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "60,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "A pension contribution",
        "passed": true,
        "error": null,
        "mismatches": []
      }
    ]
  }
};

/**
 * An agent's draft: one worked example fails.
 */
export const VERSION_3: TaxRuleSetVersion = {
  "id": "00002334-5a11-4000-8000-000000009012",
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "version": 3,
  "status": "draft",
  "content_hash": "f99790f5018b66d8ce451fcfea35f24e2e50b23688b1f0519adfee5f52aef13a",
  "author_kind": "agent",
  "author_name": "Claude",
  "change_note": "Rounding the examples.",
  "created_at": "2031-06-25T11:00:00Z",
  "proposed_at": null,
  "activated_at": null,
  "superseded_at": null,
  "document": {
    "schema": "salli.tax/1",
    "jurisdiction": {
      "country": "XA",
      "region": null
    },
    "year": {
      "label": "2031",
      "start": "2031-01-01",
      "end": "2031-12-31"
    },
    "currency": "NZD",
    "sources": [
      {
        "id": "act",
        "url": "https://example.org/xa/income-tax-act",
        "title": "XA Income Tax Act (fictional)",
        "retrieved": "2031-01-15"
      },
      {
        "id": "budget",
        "url": "https://example.org/xa/budget-2031",
        "title": "XA Budget 2031 (fictional)",
        "retrieved": "2031-06-01"
      }
    ],
    "roles": [
      {
        "key": "salary",
        "kind": "income",
        "label": "Salary"
      },
      {
        "key": "pension",
        "kind": "deduction",
        "label": "Pension contributions"
      },
      {
        "key": "tax_withheld",
        "kind": "withholding",
        "label": "Tax withheld"
      }
    ],
    "band_tables": {
      "main": {
        "label": "Rates on taxable income",
        "bands": [
          {
            "upto": "40000",
            "rate": "0.20"
          },
          {
            "upto": null,
            "rate": "0.40"
          }
        ],
        "source": "act"
      }
    },
    "blocks": [
      {
        "type": "relief",
        "key": "relief",
        "label": "Relief",
        "of": "line.taxable_income",
        "amount": "12500",
        "source": "budget"
      },
      {
        "type": "schedule",
        "key": "income_tax",
        "label": "Income tax",
        "of": "line.relief.remaining",
        "table": "main"
      },
      {
        "type": "credit",
        "key": "withholding",
        "label": "Tax withheld",
        "of": "role.tax_withheld",
        "refundable": true
      }
    ],
    "lines": [
      {
        "key": "taxable_income",
        "label": "Salary less pension contributions",
        "expr": "max(0, role.salary - role.pension)"
      },
      {
        "key": "balance",
        "label": "Tax less withholding",
        "expr": "line.income_tax - line.withholding"
      }
    ],
    "result": {
      "net": "line.balance",
      "round": {
        "mode": "nearest",
        "unit": "0.01"
      }
    },
    "suggested_accounts": [
      {
        "code": "1450",
        "name": "Tax withheld",
        "type": "asset",
        "tax_role": "tax_withheld"
      }
    ],
    "examples": [
      {
        "name": "48,000",
        "source": "budget",
        "inputs": {
          "salary": "48000"
        },
        "expected": {
          "payable": "7100"
        }
      },
      {
        "name": "54,000",
        "source": "budget",
        "inputs": {
          "salary": "54000"
        },
        "expected": {
          "payable": "8800"
        }
      },
      {
        "name": "60,000",
        "source": "budget",
        "inputs": {
          "salary": "60000"
        },
        "expected": {
          "payable": "11000"
        }
      },
      {
        "name": "A pension contribution",
        "source": "budget",
        "inputs": {
          "salary": "54000",
          "pension": "6000"
        },
        "expected": {
          "payable": "7100"
        }
      }
    ],
    "deadlines": [
      {
        "key": "return",
        "label": "Return due",
        "date": "2032-04-30",
        "source": "act"
      }
    ]
  },
  "validation": {
    "ok": false,
    "content_hash": "f99790f5018b66d8ce451fcfea35f24e2e50b23688b1f0519adfee5f52aef13a",
    "validated_at": "2031-06-25T11:00:00Z",
    "errors": [],
    "warnings": [],
    "examples": [
      {
        "name": "48,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "54,000",
        "passed": false,
        "error": null,
        "mismatches": [
          {
            "key": "payable",
            "expected": "8800",
            "got": "8600",
            "expr": "line.balance",
            "message": "payable: expected 8800, got 8600 (from line.balance)"
          }
        ]
      },
      {
        "name": "60,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "A pension contribution",
        "passed": true,
        "error": null,
        "mismatches": []
      }
    ]
  }
};

/**
 * Version 2 against the active version.
 */
export const DIFF_2: TaxRuleDiff = {
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "from": {
    "id": "0000232b-5a11-4000-8000-000000009003",
    "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
    "version": 1,
    "status": "active",
    "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
    "author_kind": "user",
    "author_name": null,
    "change_note": "From the Act",
    "created_at": "2031-02-01T09:00:00Z",
    "proposed_at": null,
    "activated_at": "2031-02-01T09:00:00Z",
    "superseded_at": null
  },
  "to": {
    "id": "00002331-5a11-4000-8000-000000009009",
    "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
    "version": 2,
    "status": "proposed",
    "content_hash": "702c5a4ac8f7b3c76f63524af1cf0a6927598ee1c720fa51896de9fadabac2ce",
    "author_kind": "agent",
    "author_name": "Claude",
    "change_note": "The 2031 budget raises the relief to 12,500.",
    "created_at": "2031-06-20T14:00:00Z",
    "proposed_at": "2031-06-20T14:00:00Z",
    "activated_at": null,
    "superseded_at": null
  },
  "changes": [
    {
      "path": "sources[id=budget]",
      "kind": "added",
      "before": null,
      "after": {
        "id": "budget",
        "url": "https://example.org/xa/budget-2031",
        "title": "XA Budget 2031 (fictional)",
        "retrieved": "2031-06-01"
      },
      "figure": false,
      "source": null
    },
    {
      "path": "blocks[key=relief].amount",
      "kind": "changed",
      "before": "12000",
      "after": "12500",
      "figure": true,
      "source": "budget"
    },
    {
      "path": "blocks[key=relief].source",
      "kind": "changed",
      "before": "act",
      "after": "budget",
      "figure": false,
      "source": "budget"
    },
    {
      "path": "examples[name=\"48,000\"].source",
      "kind": "changed",
      "before": "act",
      "after": "budget",
      "figure": false,
      "source": "budget"
    },
    {
      "path": "examples[name=\"48,000\"].expected.payable",
      "kind": "changed",
      "before": "7200",
      "after": "7100",
      "figure": true,
      "source": "budget"
    },
    {
      "path": "examples[name=\"54,000\"].source",
      "kind": "changed",
      "before": "act",
      "after": "budget",
      "figure": false,
      "source": "budget"
    },
    {
      "path": "examples[name=\"54,000\"].expected.payable",
      "kind": "changed",
      "before": "8800",
      "after": "8600",
      "figure": true,
      "source": "budget"
    },
    {
      "path": "examples[name=\"60,000\"].source",
      "kind": "changed",
      "before": "act",
      "after": "budget",
      "figure": false,
      "source": "budget"
    },
    {
      "path": "examples[name=\"60,000\"].expected.payable",
      "kind": "changed",
      "before": "11200",
      "after": "11000",
      "figure": true,
      "source": "budget"
    },
    {
      "path": "examples[name=\"A pension contribution\"].source",
      "kind": "changed",
      "before": "act",
      "after": "budget",
      "figure": false,
      "source": "budget"
    },
    {
      "path": "examples[name=\"A pension contribution\"].expected.payable",
      "kind": "changed",
      "before": "7200",
      "after": "7100",
      "figure": true,
      "source": "budget"
    }
  ],
  "sources": {
    "budget": {
      "id": "budget",
      "url": "https://example.org/xa/budget-2031",
      "title": "XA Budget 2031 (fictional)",
      "retrieved": "2031-06-01"
    }
  },
  "examples": [
    {
      "name": "48,000",
      "passed": true,
      "error": null,
      "mismatches": []
    },
    {
      "name": "54,000",
      "passed": true,
      "error": null,
      "mismatches": []
    },
    {
      "name": "60,000",
      "passed": true,
      "error": null,
      "mismatches": []
    },
    {
      "name": "A pension contribution",
      "passed": true,
      "error": null,
      "mismatches": []
    }
  ],
  "validation_ok": true
};

/**
 * Version 3 against the active version.
 */
export const DIFF_3: TaxRuleDiff = {
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "from": {
    "id": "0000232b-5a11-4000-8000-000000009003",
    "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
    "version": 1,
    "status": "active",
    "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
    "author_kind": "user",
    "author_name": null,
    "change_note": "From the Act",
    "created_at": "2031-02-01T09:00:00Z",
    "proposed_at": null,
    "activated_at": "2031-02-01T09:00:00Z",
    "superseded_at": null
  },
  "to": {
    "id": "00002334-5a11-4000-8000-000000009012",
    "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
    "version": 3,
    "status": "draft",
    "content_hash": "f99790f5018b66d8ce451fcfea35f24e2e50b23688b1f0519adfee5f52aef13a",
    "author_kind": "agent",
    "author_name": "Claude",
    "change_note": "Rounding the examples.",
    "created_at": "2031-06-25T11:00:00Z",
    "proposed_at": null,
    "activated_at": null,
    "superseded_at": null
  },
  "changes": [
    {
      "path": "sources[id=budget]",
      "kind": "added",
      "before": null,
      "after": {
        "id": "budget",
        "url": "https://example.org/xa/budget-2031",
        "title": "XA Budget 2031 (fictional)",
        "retrieved": "2031-06-01"
      },
      "figure": false,
      "source": null
    },
    {
      "path": "blocks[key=relief].amount",
      "kind": "changed",
      "before": "12000",
      "after": "12500",
      "figure": true,
      "source": "budget"
    },
    {
      "path": "blocks[key=relief].source",
      "kind": "changed",
      "before": "act",
      "after": "budget",
      "figure": false,
      "source": "budget"
    },
    {
      "path": "examples[name=\"48,000\"].source",
      "kind": "changed",
      "before": "act",
      "after": "budget",
      "figure": false,
      "source": "budget"
    },
    {
      "path": "examples[name=\"48,000\"].expected.payable",
      "kind": "changed",
      "before": "7200",
      "after": "7100",
      "figure": true,
      "source": "budget"
    },
    {
      "path": "examples[name=\"54,000\"].source",
      "kind": "changed",
      "before": "act",
      "after": "budget",
      "figure": false,
      "source": "budget"
    },
    {
      "path": "examples[name=\"60,000\"].source",
      "kind": "changed",
      "before": "act",
      "after": "budget",
      "figure": false,
      "source": "budget"
    },
    {
      "path": "examples[name=\"60,000\"].expected.payable",
      "kind": "changed",
      "before": "11200",
      "after": "11000",
      "figure": true,
      "source": "budget"
    },
    {
      "path": "examples[name=\"A pension contribution\"].source",
      "kind": "changed",
      "before": "act",
      "after": "budget",
      "figure": false,
      "source": "budget"
    },
    {
      "path": "examples[name=\"A pension contribution\"].expected.payable",
      "kind": "changed",
      "before": "7200",
      "after": "7100",
      "figure": true,
      "source": "budget"
    }
  ],
  "sources": {
    "budget": {
      "id": "budget",
      "url": "https://example.org/xa/budget-2031",
      "title": "XA Budget 2031 (fictional)",
      "retrieved": "2031-06-01"
    }
  },
  "examples": [
    {
      "name": "48,000",
      "passed": true,
      "error": null,
      "mismatches": []
    },
    {
      "name": "54,000",
      "passed": false,
      "error": null,
      "mismatches": [
        {
          "key": "payable",
          "expected": "8800",
          "got": "8600",
          "expr": "line.balance",
          "message": "payable: expected 8800, got 8600 (from line.balance)"
        }
      ]
    },
    {
      "name": "60,000",
      "passed": true,
      "error": null,
      "mismatches": []
    },
    {
      "name": "A pension contribution",
      "passed": true,
      "error": null,
      "mismatches": []
    }
  ],
  "validation_ok": false
};

/**
 * Version 1, the first: nothing before it.
 */
export const DIFF_1: TaxRuleDiff = {
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "from": {
    "id": "0000232b-5a11-4000-8000-000000009003",
    "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
    "version": 1,
    "status": "active",
    "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
    "author_kind": "user",
    "author_name": null,
    "change_note": "From the Act",
    "created_at": "2031-02-01T09:00:00Z",
    "proposed_at": null,
    "activated_at": "2031-02-01T09:00:00Z",
    "superseded_at": null
  },
  "to": {
    "id": "0000232b-5a11-4000-8000-000000009003",
    "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
    "version": 1,
    "status": "active",
    "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
    "author_kind": "user",
    "author_name": null,
    "change_note": "From the Act",
    "created_at": "2031-02-01T09:00:00Z",
    "proposed_at": null,
    "activated_at": "2031-02-01T09:00:00Z",
    "superseded_at": null
  },
  "changes": [],
  "sources": {},
  "examples": [
    {
      "name": "48,000",
      "passed": true,
      "error": null,
      "mismatches": []
    },
    {
      "name": "54,000",
      "passed": true,
      "error": null,
      "mismatches": []
    },
    {
      "name": "60,000",
      "passed": true,
      "error": null,
      "mismatches": []
    },
    {
      "name": "A pension contribution",
      "passed": true,
      "error": null,
      "mismatches": []
    }
  ],
  "validation_ok": true
};

export const EXPORT_2: TaxRuleExport = {
  "filename": "xa-2031-v2.salli-tax.json",
  "content_hash": "702c5a4ac8f7b3c76f63524af1cf0a6927598ee1c720fa51896de9fadabac2ce",
  "canonical": true,
  "text": "{\"band_tables\":{\"main\":{\"bands\":[{\"rate\":\"0.2\",\"upto\":\"40000\"},{\"rate\":\"0.4\",\"upto\":null}],\"label\":\"Rates on taxable income\",\"round\":null,\"source\":\"act\"}},\"blocks\":[{\"amount\":\"12500\",\"key\":\"relief\",\"label\":\"Relief\",\"of\":\"line.taxable_income\",\"source\":\"budget\",\"type\":\"relief\"},{\"key\":\"income_tax\",\"label\":\"Income tax\",\"of\":\"line.relief.remaining\",\"source\":null,\"table\":\"main\",\"type\":\"schedule\"},{\"cap\":null,\"key\":\"withholding\",\"label\":\"Tax withheld\",\"of\":\"role.tax_withheld\",\"refundable\":true,\"source\":null,\"type\":\"credit\"}],\"currency\":\"NZD\",\"deadlines\":[{\"date\":\"2032-04-30\",\"key\":\"return\",\"label\":\"Return due\",\"source\":\"act\"}],\"examples\":[{\"expected\":{\"lines\":null,\"payable\":\"7100\",\"refund\":null},\"inputs\":{\"salary\":\"48000\"},\"name\":\"48,000\",\"source\":\"budget\"},{\"expected\":{\"lines\":null,\"payable\":\"8600\",\"refund\":null},\"inputs\":{\"salary\":\"54000\"},\"name\":\"54,000\",\"source\":\"budget\"},{\"expected\":{\"lines\":null,\"payable\":\"11000\",\"refund\":null},\"inputs\":{\"salary\":\"60000\"},\"name\":\"60,000\",\"source\":\"budget\"},{\"expected\":{\"lines\":null,\"payable\":\"7100\",\"refund\":null},\"inputs\":{\"pension\":\"6000\",\"salary\":\"54000\"},\"name\":\"A pension contribution\",\"source\":\"budget\"}],\"forms\":[],\"jurisdiction\":{\"country\":\"XA\",\"region\":null},\"lines\":[{\"expr\":\"max(0, role.salary - role.pension)\",\"key\":\"taxable_income\",\"label\":\"Salary less pension contributions\",\"source\":null},{\"expr\":\"line.income_tax - line.withholding\",\"key\":\"balance\",\"label\":\"Tax less withholding\",\"source\":null}],\"questions\":[],\"result\":{\"net\":\"line.balance\",\"round\":{\"mode\":\"nearest\",\"unit\":\"0.01\"}},\"roles\":[{\"description\":null,\"key\":\"salary\",\"kind\":\"income\",\"label\":\"Salary\"},{\"description\":null,\"key\":\"pension\",\"kind\":\"deduction\",\"label\":\"Pension contributions\"},{\"description\":null,\"key\":\"tax_withheld\",\"kind\":\"withholding\",\"label\":\"Tax withheld\"}],\"schema\":\"salli.tax/1\",\"sources\":[{\"id\":\"act\",\"retrieved\":\"2031-01-15\",\"title\":\"XA Income Tax Act (fictional)\",\"url\":\"https://example.org/xa/income-tax-act\"},{\"id\":\"budget\",\"retrieved\":\"2031-06-01\",\"title\":\"XA Budget 2031 (fictional)\",\"url\":\"https://example.org/xa/budget-2031\"}],\"suggested_accounts\":[{\"code\":\"1450\",\"name\":\"Tax withheld\",\"tax_role\":\"tax_withheld\",\"type\":\"asset\"}],\"year\":{\"end\":\"2031-12-31\",\"label\":\"2031\",\"start\":\"2031-01-01\"}}"
};

export const YEAR: TaxYearStatus = {
  "country": "XA",
  "country_source": "tax_residency",
  "year": "2031",
  "region": null,
  "start": "2031-01-01",
  "end": "2031-12-31",
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "rule_set_version_id": "0000232b-5a11-4000-8000-000000009003",
  "version": 1,
  "latest_year": "2031",
  "latest_rule_set_version_id": "0000232b-5a11-4000-8000-000000009003"
};

export const LATEST: LatestTaxComputation = {
  "result": {
    "id": "0000232f-5a11-4000-8000-000000009007",
    "created_at": "2031-05-31T18:00:00Z",
    "country": "XA",
    "region": null,
    "year": "2031",
    "period_start": "2031-01-01",
    "period_end": "2031-12-31",
    "currency": "NZD",
    "base_currency": "NZD",
    "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
    "rule_set_version_id": "0000232b-5a11-4000-8000-000000009003",
    "version": 1,
    "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
    "roles": [
      {
        "key": "salary",
        "kind": "income",
        "label": "Salary",
        "total": "24000",
        "postings": 6
      },
      {
        "key": "pension",
        "kind": "deduction",
        "label": "Pension contributions",
        "total": "0",
        "postings": 0
      },
      {
        "key": "tax_withheld",
        "kind": "withholding",
        "label": "Tax withheld",
        "total": "0",
        "postings": 0
      }
    ],
    "answers": {},
    "rates": [],
    "lines": [
      {
        "key": "taxable_income",
        "label": "Salary less pension contributions",
        "amount": "24000",
        "expr": "max(0, role.salary - role.pension)",
        "source": null,
        "refundable": null
      },
      {
        "key": "relief",
        "label": "Relief",
        "amount": "12000",
        "expr": "min(12000, max(0, line.taxable_income))",
        "source": "act",
        "refundable": null
      },
      {
        "key": "relief.remaining",
        "label": "Relief: remaining",
        "amount": "12000",
        "expr": "max(0, line.taxable_income - line.relief)",
        "source": "act",
        "refundable": null
      },
      {
        "key": "income_tax.band_1.amount",
        "label": "Income tax: band 1 amount",
        "amount": "12000",
        "expr": "band_amount(line.relief.remaining, \"main\", 1)",
        "source": null,
        "refundable": null
      },
      {
        "key": "income_tax.band_1.tax",
        "label": "Income tax: band 1 tax",
        "amount": "2400",
        "expr": "line.income_tax.band_1.amount * 0.20",
        "source": null,
        "refundable": null
      },
      {
        "key": "income_tax.band_2.amount",
        "label": "Income tax: band 2 amount",
        "amount": "0",
        "expr": "band_amount(line.relief.remaining, \"main\", 2)",
        "source": null,
        "refundable": null
      },
      {
        "key": "income_tax.band_2.tax",
        "label": "Income tax: band 2 tax",
        "amount": "0",
        "expr": "line.income_tax.band_2.amount * 0.40",
        "source": null,
        "refundable": null
      },
      {
        "key": "income_tax",
        "label": "Income tax",
        "amount": "2400",
        "expr": "line.income_tax.band_1.tax + line.income_tax.band_2.tax",
        "source": null,
        "refundable": null
      },
      {
        "key": "withholding",
        "label": "Tax withheld",
        "amount": "0",
        "expr": "role.tax_withheld",
        "source": null,
        "refundable": true
      },
      {
        "key": "balance",
        "label": "Tax less withholding",
        "amount": "2400",
        "expr": "line.income_tax - line.withholding",
        "source": null,
        "refundable": null
      }
    ],
    "net": "2400.00",
    "tax_payable": "2400.00",
    "refund_due": "0.00",
    "warnings": [],
    "provenance": "Computed by Salli's engine from rules you or your agent entered. Salli doesn't vouch for the law: check the rules' sources."
  }
};

/**
 * Where the income tax line came from.
 */
export const EXPLAINED: TaxLineExplanation = {
  "country": "XA",
  "region": null,
  "year": "2031",
  "currency": "NZD",
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "rule_set_version_id": "0000232b-5a11-4000-8000-000000009003",
  "version": 1,
  "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
  "line": {
    "key": "income_tax",
    "label": "Income tax",
    "amount": "2400",
    "expr": "line.income_tax.band_1.tax + line.income_tax.band_2.tax",
    "path": "blocks[1]",
    "block": "schedule",
    "refundable": null,
    "source": null
  },
  "inputs": [],
  "answers": [],
  "lines": [
    {
      "key": "income_tax.band_1.tax",
      "label": "Income tax: band 1 tax",
      "amount": "2400",
      "expr": "line.income_tax.band_1.amount * 0.20"
    },
    {
      "key": "income_tax.band_2.tax",
      "label": "Income tax: band 2 tax",
      "amount": "0",
      "expr": "line.income_tax.band_2.amount * 0.40"
    }
  ],
  "tables": [],
  "used_by": [
    "balance"
  ],
  "provenance": "Computed by Salli's engine from rules you or your agent entered. Salli doesn't vouch for the law: check the rules' sources."
};

/**
 * Activating version 2 from the console, six minutes after the password.
 */
export const STEP_UP: ProblemDetails = {
  "type": "/problems/step-up-required",
  "title": "Sign in again",
  "status": 403,
  "detail": "tax:activate needs your password, entered in the last 5 minutes. Sign in again on Salli's sign-in page, then try again.",
  "max_age": 300
};

/**
 * Version 2, activated just after the password.
 */
export const ACTIVATED: TaxRuleSetVersion = {
  "id": "00002331-5a11-4000-8000-000000009009",
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "version": 2,
  "status": "active",
  "content_hash": "702c5a4ac8f7b3c76f63524af1cf0a6927598ee1c720fa51896de9fadabac2ce",
  "author_kind": "agent",
  "author_name": "Claude",
  "change_note": "The 2031 budget raises the relief to 12,500.",
  "created_at": "2031-06-20T14:00:00Z",
  "proposed_at": "2031-06-20T14:00:00Z",
  "activated_at": "2031-06-30T09:06:00Z",
  "superseded_at": null,
  "document": {
    "schema": "salli.tax/1",
    "jurisdiction": {
      "country": "XA",
      "region": null
    },
    "year": {
      "label": "2031",
      "start": "2031-01-01",
      "end": "2031-12-31"
    },
    "currency": "NZD",
    "sources": [
      {
        "id": "act",
        "url": "https://example.org/xa/income-tax-act",
        "title": "XA Income Tax Act (fictional)",
        "retrieved": "2031-01-15"
      },
      {
        "id": "budget",
        "url": "https://example.org/xa/budget-2031",
        "title": "XA Budget 2031 (fictional)",
        "retrieved": "2031-06-01"
      }
    ],
    "roles": [
      {
        "key": "salary",
        "kind": "income",
        "label": "Salary"
      },
      {
        "key": "pension",
        "kind": "deduction",
        "label": "Pension contributions"
      },
      {
        "key": "tax_withheld",
        "kind": "withholding",
        "label": "Tax withheld"
      }
    ],
    "band_tables": {
      "main": {
        "label": "Rates on taxable income",
        "bands": [
          {
            "upto": "40000",
            "rate": "0.20"
          },
          {
            "upto": null,
            "rate": "0.40"
          }
        ],
        "source": "act"
      }
    },
    "blocks": [
      {
        "type": "relief",
        "key": "relief",
        "label": "Relief",
        "of": "line.taxable_income",
        "amount": "12500",
        "source": "budget"
      },
      {
        "type": "schedule",
        "key": "income_tax",
        "label": "Income tax",
        "of": "line.relief.remaining",
        "table": "main"
      },
      {
        "type": "credit",
        "key": "withholding",
        "label": "Tax withheld",
        "of": "role.tax_withheld",
        "refundable": true
      }
    ],
    "lines": [
      {
        "key": "taxable_income",
        "label": "Salary less pension contributions",
        "expr": "max(0, role.salary - role.pension)"
      },
      {
        "key": "balance",
        "label": "Tax less withholding",
        "expr": "line.income_tax - line.withholding"
      }
    ],
    "result": {
      "net": "line.balance",
      "round": {
        "mode": "nearest",
        "unit": "0.01"
      }
    },
    "suggested_accounts": [
      {
        "code": "1450",
        "name": "Tax withheld",
        "type": "asset",
        "tax_role": "tax_withheld"
      }
    ],
    "examples": [
      {
        "name": "48,000",
        "source": "budget",
        "inputs": {
          "salary": "48000"
        },
        "expected": {
          "payable": "7100"
        }
      },
      {
        "name": "54,000",
        "source": "budget",
        "inputs": {
          "salary": "54000"
        },
        "expected": {
          "payable": "8600"
        }
      },
      {
        "name": "60,000",
        "source": "budget",
        "inputs": {
          "salary": "60000"
        },
        "expected": {
          "payable": "11000"
        }
      },
      {
        "name": "A pension contribution",
        "source": "budget",
        "inputs": {
          "salary": "54000",
          "pension": "6000"
        },
        "expected": {
          "payable": "7100"
        }
      }
    ],
    "deadlines": [
      {
        "key": "return",
        "label": "Return due",
        "date": "2032-04-30",
        "source": "act"
      }
    ]
  },
  "validation": {
    "ok": true,
    "content_hash": "702c5a4ac8f7b3c76f63524af1cf0a6927598ee1c720fa51896de9fadabac2ce",
    "validated_at": "2031-06-30T09:06:00Z",
    "errors": [],
    "warnings": [],
    "examples": [
      {
        "name": "48,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "54,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "60,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "A pension contribution",
        "passed": true,
        "error": null,
        "mismatches": []
      }
    ]
  }
};

export const RULE_SET_ACTIVATED: TaxRuleSet = {
  "id": "0000232a-5a11-4000-8000-000000009002",
  "country": "XA",
  "region": null,
  "year_label": "2031",
  "name": "XA 2031",
  "active_version_id": "00002331-5a11-4000-8000-000000009009",
  "created_at": "2031-02-01T09:00:00Z",
  "updated_at": "2031-06-30T09:06:00Z",
  "versions": [
    {
      "id": "0000232b-5a11-4000-8000-000000009003",
      "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
      "version": 1,
      "status": "superseded",
      "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
      "author_kind": "user",
      "author_name": null,
      "change_note": "From the Act",
      "created_at": "2031-02-01T09:00:00Z",
      "proposed_at": null,
      "activated_at": "2031-02-01T09:00:00Z",
      "superseded_at": "2031-06-30T09:06:00Z"
    },
    {
      "id": "00002331-5a11-4000-8000-000000009009",
      "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
      "version": 2,
      "status": "active",
      "content_hash": "702c5a4ac8f7b3c76f63524af1cf0a6927598ee1c720fa51896de9fadabac2ce",
      "author_kind": "agent",
      "author_name": "Claude",
      "change_note": "The 2031 budget raises the relief to 12,500.",
      "created_at": "2031-06-20T14:00:00Z",
      "proposed_at": "2031-06-20T14:00:00Z",
      "activated_at": "2031-06-30T09:06:00Z",
      "superseded_at": null
    },
    {
      "id": "00002334-5a11-4000-8000-000000009012",
      "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
      "version": 3,
      "status": "draft",
      "content_hash": "f99790f5018b66d8ce451fcfea35f24e2e50b23688b1f0519adfee5f52aef13a",
      "author_kind": "agent",
      "author_name": "Claude",
      "change_note": "Rounding the examples.",
      "created_at": "2031-06-25T11:00:00Z",
      "proposed_at": null,
      "activated_at": null,
      "superseded_at": null
    }
  ]
};

export const VERSION_1_SUPERSEDED: TaxRuleSetVersion = {
  "id": "0000232b-5a11-4000-8000-000000009003",
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "version": 1,
  "status": "superseded",
  "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
  "author_kind": "user",
  "author_name": null,
  "change_note": "From the Act",
  "created_at": "2031-02-01T09:00:00Z",
  "proposed_at": null,
  "activated_at": "2031-02-01T09:00:00Z",
  "superseded_at": "2031-06-30T09:06:00Z",
  "document": {
    "schema": "salli.tax/1",
    "jurisdiction": {
      "country": "XA",
      "region": null
    },
    "year": {
      "label": "2031",
      "start": "2031-01-01",
      "end": "2031-12-31"
    },
    "currency": "NZD",
    "sources": [
      {
        "id": "act",
        "url": "https://example.org/xa/income-tax-act",
        "title": "XA Income Tax Act (fictional)",
        "retrieved": "2031-01-15"
      }
    ],
    "roles": [
      {
        "key": "salary",
        "kind": "income",
        "label": "Salary"
      },
      {
        "key": "pension",
        "kind": "deduction",
        "label": "Pension contributions"
      },
      {
        "key": "tax_withheld",
        "kind": "withholding",
        "label": "Tax withheld"
      }
    ],
    "band_tables": {
      "main": {
        "label": "Rates on taxable income",
        "bands": [
          {
            "upto": "40000",
            "rate": "0.20"
          },
          {
            "upto": null,
            "rate": "0.40"
          }
        ],
        "source": "act"
      }
    },
    "blocks": [
      {
        "type": "relief",
        "key": "relief",
        "label": "Relief",
        "of": "line.taxable_income",
        "amount": "12000",
        "source": "act"
      },
      {
        "type": "schedule",
        "key": "income_tax",
        "label": "Income tax",
        "of": "line.relief.remaining",
        "table": "main"
      },
      {
        "type": "credit",
        "key": "withholding",
        "label": "Tax withheld",
        "of": "role.tax_withheld",
        "refundable": true
      }
    ],
    "lines": [
      {
        "key": "taxable_income",
        "label": "Salary less pension contributions",
        "expr": "max(0, role.salary - role.pension)"
      },
      {
        "key": "balance",
        "label": "Tax less withholding",
        "expr": "line.income_tax - line.withholding"
      }
    ],
    "result": {
      "net": "line.balance",
      "round": {
        "mode": "nearest",
        "unit": "0.01"
      }
    },
    "suggested_accounts": [
      {
        "code": "1450",
        "name": "Tax withheld",
        "type": "asset",
        "tax_role": "tax_withheld"
      }
    ],
    "examples": [
      {
        "name": "48,000",
        "source": "act",
        "inputs": {
          "salary": "48000"
        },
        "expected": {
          "payable": "7200"
        }
      },
      {
        "name": "54,000",
        "source": "act",
        "inputs": {
          "salary": "54000"
        },
        "expected": {
          "payable": "8800"
        }
      },
      {
        "name": "60,000",
        "source": "act",
        "inputs": {
          "salary": "60000"
        },
        "expected": {
          "payable": "11200"
        }
      },
      {
        "name": "A pension contribution",
        "source": "act",
        "inputs": {
          "salary": "54000",
          "pension": "6000"
        },
        "expected": {
          "payable": "7200"
        }
      }
    ],
    "deadlines": [
      {
        "key": "return",
        "label": "Return due",
        "date": "2032-04-30",
        "source": "act"
      }
    ]
  },
  "validation": {
    "ok": true,
    "content_hash": "53e89ccd4283fa14d5574a9d954a4d71f7ec16fd2cde544dfb16dbac893a6561",
    "validated_at": "2031-02-01T09:00:00Z",
    "errors": [],
    "warnings": [],
    "examples": [
      {
        "name": "48,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "54,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "60,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "A pension contribution",
        "passed": true,
        "error": null,
        "mismatches": []
      }
    ]
  }
};

/**
 * Computed again, with version 2.
 */
export const COMPUTED: TaxComputation = {
  "id": "00002346-5a11-4000-8000-000000009030",
  "created_at": "2031-06-30T09:06:00Z",
  "country": "XA",
  "region": null,
  "year": "2031",
  "period_start": "2031-01-01",
  "period_end": "2031-12-31",
  "currency": "NZD",
  "base_currency": "NZD",
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "rule_set_version_id": "00002331-5a11-4000-8000-000000009009",
  "version": 2,
  "content_hash": "702c5a4ac8f7b3c76f63524af1cf0a6927598ee1c720fa51896de9fadabac2ce",
  "roles": [
    {
      "key": "salary",
      "kind": "income",
      "label": "Salary",
      "total": "24000",
      "postings": 6
    },
    {
      "key": "pension",
      "kind": "deduction",
      "label": "Pension contributions",
      "total": "0",
      "postings": 0
    },
    {
      "key": "tax_withheld",
      "kind": "withholding",
      "label": "Tax withheld",
      "total": "0",
      "postings": 0
    }
  ],
  "answers": {},
  "rates": [],
  "lines": [
    {
      "key": "taxable_income",
      "label": "Salary less pension contributions",
      "amount": "24000",
      "expr": "max(0, role.salary - role.pension)",
      "source": null,
      "refundable": null
    },
    {
      "key": "relief",
      "label": "Relief",
      "amount": "12500",
      "expr": "min(12500, max(0, line.taxable_income))",
      "source": "budget",
      "refundable": null
    },
    {
      "key": "relief.remaining",
      "label": "Relief: remaining",
      "amount": "11500",
      "expr": "max(0, line.taxable_income - line.relief)",
      "source": "budget",
      "refundable": null
    },
    {
      "key": "income_tax.band_1.amount",
      "label": "Income tax: band 1 amount",
      "amount": "11500",
      "expr": "band_amount(line.relief.remaining, \"main\", 1)",
      "source": null,
      "refundable": null
    },
    {
      "key": "income_tax.band_1.tax",
      "label": "Income tax: band 1 tax",
      "amount": "2300",
      "expr": "line.income_tax.band_1.amount * 0.20",
      "source": null,
      "refundable": null
    },
    {
      "key": "income_tax.band_2.amount",
      "label": "Income tax: band 2 amount",
      "amount": "0",
      "expr": "band_amount(line.relief.remaining, \"main\", 2)",
      "source": null,
      "refundable": null
    },
    {
      "key": "income_tax.band_2.tax",
      "label": "Income tax: band 2 tax",
      "amount": "0",
      "expr": "line.income_tax.band_2.amount * 0.40",
      "source": null,
      "refundable": null
    },
    {
      "key": "income_tax",
      "label": "Income tax",
      "amount": "2300",
      "expr": "line.income_tax.band_1.tax + line.income_tax.band_2.tax",
      "source": null,
      "refundable": null
    },
    {
      "key": "withholding",
      "label": "Tax withheld",
      "amount": "0",
      "expr": "role.tax_withheld",
      "source": null,
      "refundable": true
    },
    {
      "key": "balance",
      "label": "Tax less withholding",
      "amount": "2300",
      "expr": "line.income_tax - line.withholding",
      "source": null,
      "refundable": null
    }
  ],
  "net": "2300.00",
  "tax_payable": "2300.00",
  "refund_due": "0.00",
  "warnings": [],
  "provenance": "Computed by Salli's engine from rules you or your agent entered. Salli doesn't vouch for the law: check the rules' sources."
};

/**
 * Version 3 validated again: still a draft.
 */
export const VALIDATED_3: TaxRuleSetVersion = {
  "id": "00002334-5a11-4000-8000-000000009012",
  "rule_set_id": "0000232a-5a11-4000-8000-000000009002",
  "version": 3,
  "status": "draft",
  "content_hash": "f99790f5018b66d8ce451fcfea35f24e2e50b23688b1f0519adfee5f52aef13a",
  "author_kind": "agent",
  "author_name": "Claude",
  "change_note": "Rounding the examples.",
  "created_at": "2031-06-25T11:00:00Z",
  "proposed_at": null,
  "activated_at": null,
  "superseded_at": null,
  "document": {
    "schema": "salli.tax/1",
    "jurisdiction": {
      "country": "XA",
      "region": null
    },
    "year": {
      "label": "2031",
      "start": "2031-01-01",
      "end": "2031-12-31"
    },
    "currency": "NZD",
    "sources": [
      {
        "id": "act",
        "url": "https://example.org/xa/income-tax-act",
        "title": "XA Income Tax Act (fictional)",
        "retrieved": "2031-01-15"
      },
      {
        "id": "budget",
        "url": "https://example.org/xa/budget-2031",
        "title": "XA Budget 2031 (fictional)",
        "retrieved": "2031-06-01"
      }
    ],
    "roles": [
      {
        "key": "salary",
        "kind": "income",
        "label": "Salary"
      },
      {
        "key": "pension",
        "kind": "deduction",
        "label": "Pension contributions"
      },
      {
        "key": "tax_withheld",
        "kind": "withholding",
        "label": "Tax withheld"
      }
    ],
    "band_tables": {
      "main": {
        "label": "Rates on taxable income",
        "bands": [
          {
            "upto": "40000",
            "rate": "0.20"
          },
          {
            "upto": null,
            "rate": "0.40"
          }
        ],
        "source": "act"
      }
    },
    "blocks": [
      {
        "type": "relief",
        "key": "relief",
        "label": "Relief",
        "of": "line.taxable_income",
        "amount": "12500",
        "source": "budget"
      },
      {
        "type": "schedule",
        "key": "income_tax",
        "label": "Income tax",
        "of": "line.relief.remaining",
        "table": "main"
      },
      {
        "type": "credit",
        "key": "withholding",
        "label": "Tax withheld",
        "of": "role.tax_withheld",
        "refundable": true
      }
    ],
    "lines": [
      {
        "key": "taxable_income",
        "label": "Salary less pension contributions",
        "expr": "max(0, role.salary - role.pension)"
      },
      {
        "key": "balance",
        "label": "Tax less withholding",
        "expr": "line.income_tax - line.withholding"
      }
    ],
    "result": {
      "net": "line.balance",
      "round": {
        "mode": "nearest",
        "unit": "0.01"
      }
    },
    "suggested_accounts": [
      {
        "code": "1450",
        "name": "Tax withheld",
        "type": "asset",
        "tax_role": "tax_withheld"
      }
    ],
    "examples": [
      {
        "name": "48,000",
        "source": "budget",
        "inputs": {
          "salary": "48000"
        },
        "expected": {
          "payable": "7100"
        }
      },
      {
        "name": "54,000",
        "source": "budget",
        "inputs": {
          "salary": "54000"
        },
        "expected": {
          "payable": "8800"
        }
      },
      {
        "name": "60,000",
        "source": "budget",
        "inputs": {
          "salary": "60000"
        },
        "expected": {
          "payable": "11000"
        }
      },
      {
        "name": "A pension contribution",
        "source": "budget",
        "inputs": {
          "salary": "54000",
          "pension": "6000"
        },
        "expected": {
          "payable": "7100"
        }
      }
    ],
    "deadlines": [
      {
        "key": "return",
        "label": "Return due",
        "date": "2032-04-30",
        "source": "act"
      }
    ]
  },
  "validation": {
    "ok": false,
    "content_hash": "f99790f5018b66d8ce451fcfea35f24e2e50b23688b1f0519adfee5f52aef13a",
    "validated_at": "2031-06-30T09:06:00Z",
    "errors": [],
    "warnings": [],
    "examples": [
      {
        "name": "48,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "54,000",
        "passed": false,
        "error": null,
        "mismatches": [
          {
            "key": "payable",
            "expected": "8800",
            "got": "8600",
            "expr": "line.balance",
            "message": "payable: expected 8800, got 8600 (from line.balance)"
          }
        ]
      },
      {
        "name": "60,000",
        "passed": true,
        "error": null,
        "mismatches": []
      },
      {
        "name": "A pension contribution",
        "passed": true,
        "error": null,
        "mismatches": []
      }
    ]
  }
};

/**
 * Proposing version 3, whose example fails.
 */
export const PROPOSE_REFUSED: ProblemDetails = {
  "type": "/problems/rule-set-state",
  "title": "Not possible in this state",
  "status": 409,
  "detail": "Version 3 can't be proposed: worked examples don't match: 54,000"
};
