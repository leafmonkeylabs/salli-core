/**
 * What a real server answers the console's imports, review queue and
 * categorisation rules (docs/design/console.md, section 5) on the golden
 * household ledger (tests/golden/household.py, as of Oct 11, 2026, in
 * euros): the person's rule for FreshMart, then a checking statement for
 * October so far imported against it (no model is set up, so only the rule
 * sorts it). The writes at the end (an account chosen, two posted, two
 * discarded, rules tested, refused, made and edited) come after every read,
 * so the reads are what the console sees first.
 *
 * Written by tests/console_fixtures.py (`uv run python -m tests.console_fixtures`):
 * tests/contract/test_console_fixtures.py fails while it differs from what
 * the server answers. Don't edit it by hand.
 */
import type { BankConnections, BankStatementList, CategorizationRule, CategorizedTransactions, DiscardedStatementTransactions, PendingStatementTransactions, PostedStatementTransactions, ProblemDetails, Ref, RuleSuggestion, RuleTestResult, StatementUpload } from '@leafmonkeylabs/salli-sdk';

/**
 * The answer to importing checking-october.csv into Checking.
 */
export const UPLOADED: StatementUpload = {
  "statement_id": "0000232c-5a11-4000-8000-000000009004",
  "bank": "Example Bank",
  "period_start": "2026-10-01",
  "period_end": "2026-10-10",
  "total_rows": 5,
  "parsed": 5,
  "errors": [
    "4 transactions need an account: with no AI key set up, only your rules sorted this statement."
  ],
  "transactions": [
    {
      "id": "0000232d-5a11-4000-8000-000000009005",
      "date": "2026-10-01",
      "description": "CITY LETTINGS RENT",
      "amount": "1500.00",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "",
      "credit_account_id": "chk",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "fuzzy_match",
      "duplicate_of": "e067"
    },
    {
      "id": "0000232e-5a11-4000-8000-000000009006",
      "date": "2026-10-05",
      "description": "AUTOFIN CAR LOAN",
      "amount": "350.00",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "",
      "credit_account_id": "chk",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "pending",
      "duplicate_of": null
    },
    {
      "id": "0000232f-5a11-4000-8000-000000009007",
      "date": "2026-10-07",
      "description": "CORNER BAKERY",
      "amount": "8.40",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "",
      "credit_account_id": "chk",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "pending",
      "duplicate_of": null
    },
    {
      "id": "00002330-5a11-4000-8000-000000009008",
      "date": "2026-10-09",
      "description": "FRESHMART",
      "amount": "46.20",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "food",
      "credit_account_id": "chk",
      "category": "groceries",
      "need": "essential",
      "rule_id": "0000232a-5a11-4000-8000-000000009002",
      "description_override": null,
      "confidence": 1.0,
      "dedup_status": "pending",
      "duplicate_of": null
    },
    {
      "id": "00002331-5a11-4000-8000-000000009009",
      "date": "2026-10-10",
      "description": "HARDWARE STORE REFUND",
      "amount": "19.99",
      "credit_flag": true,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "chk",
      "credit_account_id": "",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "pending",
      "duplicate_of": null
    }
  ]
};

export const STATEMENTS: BankStatementList = {
  "statements": [
    {
      "id": "0000232c-5a11-4000-8000-000000009004",
      "bank": "Example Bank",
      "account_id": "chk",
      "period_start": "2026-10-01",
      "period_end": "2026-10-10",
      "status": "pending",
      "created_at": "2026-10-11T09:30:00+00:00"
    }
  ]
};

/**
 * The October statement's transactions waiting for review.
 */
export const PENDING: PendingStatementTransactions = {
  "statement_id": "0000232c-5a11-4000-8000-000000009004",
  "transactions": [
    {
      "id": "0000232d-5a11-4000-8000-000000009005",
      "date": "2026-10-01",
      "description": "CITY LETTINGS RENT",
      "amount": "1500.00",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "",
      "credit_account_id": "chk",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "fuzzy_match",
      "duplicate_of": "e067"
    },
    {
      "id": "0000232e-5a11-4000-8000-000000009006",
      "date": "2026-10-05",
      "description": "AUTOFIN CAR LOAN",
      "amount": "350.00",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "",
      "credit_account_id": "chk",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "pending",
      "duplicate_of": null
    },
    {
      "id": "0000232f-5a11-4000-8000-000000009007",
      "date": "2026-10-07",
      "description": "CORNER BAKERY",
      "amount": "8.40",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "",
      "credit_account_id": "chk",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "pending",
      "duplicate_of": null
    },
    {
      "id": "00002330-5a11-4000-8000-000000009008",
      "date": "2026-10-09",
      "description": "FRESHMART",
      "amount": "46.20",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "food",
      "credit_account_id": "chk",
      "category": "groceries",
      "need": "essential",
      "rule_id": "0000232a-5a11-4000-8000-000000009002",
      "description_override": null,
      "confidence": 1.0,
      "dedup_status": "pending",
      "duplicate_of": null
    },
    {
      "id": "00002331-5a11-4000-8000-000000009009",
      "date": "2026-10-10",
      "description": "HARDWARE STORE REFUND",
      "amount": "19.99",
      "credit_flag": true,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "chk",
      "credit_account_id": "",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "pending",
      "duplicate_of": null
    }
  ]
};

export const RULES: CategorizationRule[] = [
  {
    "name": "FreshMart is groceries",
    "conditions": [
      {
        "field": "description",
        "operator": "contains",
        "value": "FRESHMART",
        "value2": null
      }
    ],
    "actions": {
      "account_id": "food",
      "category": "groceries",
      "need": "essential",
      "description": null
    },
    "priority": 100,
    "match_all": true,
    "enabled": true,
    "id": "0000232a-5a11-4000-8000-000000009002",
    "hits": 1,
    "last_hit_at": "2026-10-11T09:30:00Z",
    "created_at": "2026-10-01T09:00:00Z",
    "updated_at": "2026-10-01T09:00:00Z"
  }
];

/**
 * The rules the household's own bookkeeping implies.
 */
export const SUGGESTIONS: RuleSuggestion[] = [
  {
    "name": "Acme",
    "conditions": [
      {
        "field": "description",
        "operator": "contains",
        "value": "acme",
        "value2": null
      },
      {
        "field": "direction",
        "operator": "equals",
        "value": "in",
        "value2": null
      }
    ],
    "actions": {
      "account_id": "sal",
      "category": null,
      "need": null,
      "description": null
    },
    "priority": 100,
    "match_all": true,
    "enabled": true,
    "support": 7,
    "agreement": 7,
    "examples": [
      "ACME LTD SALARY"
    ]
  },
  {
    "name": "City",
    "conditions": [
      {
        "field": "description",
        "operator": "contains",
        "value": "city",
        "value2": null
      },
      {
        "field": "direction",
        "operator": "equals",
        "value": "out",
        "value2": null
      }
    ],
    "actions": {
      "account_id": "rent",
      "category": null,
      "need": null,
      "description": null
    },
    "priority": 100,
    "match_all": true,
    "enabled": true,
    "support": 7,
    "agreement": 7,
    "examples": [
      "CITY LETTINGS RENT"
    ]
  },
  {
    "name": "Streamflix",
    "conditions": [
      {
        "field": "description",
        "operator": "contains",
        "value": "streamflix",
        "value2": null
      },
      {
        "field": "direction",
        "operator": "equals",
        "value": "out",
        "value2": null
      }
    ],
    "actions": {
      "account_id": "tv",
      "category": null,
      "need": null,
      "description": null
    },
    "priority": 100,
    "match_all": true,
    "enabled": true,
    "support": 7,
    "agreement": 7,
    "examples": [
      "STREAMFLIX"
    ]
  },
  {
    "name": "Bistro",
    "conditions": [
      {
        "field": "description",
        "operator": "contains",
        "value": "bistro",
        "value2": null
      },
      {
        "field": "direction",
        "operator": "equals",
        "value": "out",
        "value2": null
      }
    ],
    "actions": {
      "account_id": "out",
      "category": null,
      "need": null,
      "description": null
    },
    "priority": 100,
    "match_all": true,
    "enabled": true,
    "support": 6,
    "agreement": 6,
    "examples": [
      "BISTRO NOVO"
    ]
  },
  {
    "name": "Brokerage",
    "conditions": [
      {
        "field": "description",
        "operator": "contains",
        "value": "brokerage",
        "value2": null
      },
      {
        "field": "direction",
        "operator": "equals",
        "value": "out",
        "value2": null
      }
    ],
    "actions": {
      "account_id": "brk",
      "category": null,
      "need": null,
      "description": null
    },
    "priority": 100,
    "match_all": true,
    "enabled": true,
    "support": 6,
    "agreement": 6,
    "examples": [
      "TO BROKERAGE"
    ]
  },
  {
    "name": "Opening",
    "conditions": [
      {
        "field": "description",
        "operator": "contains",
        "value": "opening",
        "value2": null
      },
      {
        "field": "direction",
        "operator": "equals",
        "value": "in",
        "value2": null
      }
    ],
    "actions": {
      "account_id": "eq",
      "category": null,
      "need": null,
      "description": null
    },
    "priority": 100,
    "match_all": true,
    "enabled": true,
    "support": 6,
    "agreement": 6,
    "examples": [
      "Opening balance"
    ]
  },
  {
    "name": "Savings",
    "conditions": [
      {
        "field": "description",
        "operator": "contains",
        "value": "savings",
        "value2": null
      },
      {
        "field": "direction",
        "operator": "equals",
        "value": "out",
        "value2": null
      }
    ],
    "actions": {
      "account_id": "sav",
      "category": null,
      "need": null,
      "description": null
    },
    "priority": 100,
    "match_all": true,
    "enabled": true,
    "support": 6,
    "agreement": 6,
    "examples": [
      "TO SAVINGS"
    ]
  },
  {
    "name": "Thank",
    "conditions": [
      {
        "field": "description",
        "operator": "contains",
        "value": "thank",
        "value2": null
      },
      {
        "field": "direction",
        "operator": "equals",
        "value": "out",
        "value2": null
      }
    ],
    "actions": {
      "account_id": "card",
      "category": null,
      "need": null,
      "description": null
    },
    "priority": 100,
    "match_all": true,
    "enabled": true,
    "support": 5,
    "agreement": 5,
    "examples": [
      "CARD PAYMENT THANK YOU"
    ]
  }
];

export const BANKS: BankConnections = {
  "available": false,
  "providers": [],
  "connections": [
    {
      "id": "bank-1",
      "provider": "simplefin",
      "name": "Example Bank",
      "status": "ok",
      "last_error": null,
      "warnings": [],
      "last_synced_at": "2026-10-11T06:00:00Z",
      "created_at": "2026-09-01T09:00:00Z",
      "accounts": [
        {
          "remote_id": "ACT-1",
          "name": "Everyday checking",
          "institution": "Example Bank",
          "currency": "EUR",
          "balance": "2104.33",
          "balance_date": "2026-10-11T06:00:00Z",
          "account_id": "chk",
          "last_imported_at": "2026-10-11T06:00:00Z",
          "notes": null
        }
      ]
    }
  ]
};

/**
 * The bakery is eating out.
 */
export const CATEGORIZED: CategorizedTransactions = {
  "updated": [
    "0000232f-5a11-4000-8000-000000009007"
  ]
};

export const PENDING_CHOSEN: PendingStatementTransactions = {
  "statement_id": "0000232c-5a11-4000-8000-000000009004",
  "transactions": [
    {
      "id": "0000232d-5a11-4000-8000-000000009005",
      "date": "2026-10-01",
      "description": "CITY LETTINGS RENT",
      "amount": "1500.00",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "",
      "credit_account_id": "chk",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "fuzzy_match",
      "duplicate_of": "e067"
    },
    {
      "id": "0000232e-5a11-4000-8000-000000009006",
      "date": "2026-10-05",
      "description": "AUTOFIN CAR LOAN",
      "amount": "350.00",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "",
      "credit_account_id": "chk",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "pending",
      "duplicate_of": null
    },
    {
      "id": "0000232f-5a11-4000-8000-000000009007",
      "date": "2026-10-07",
      "description": "CORNER BAKERY",
      "amount": "8.40",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "out",
      "credit_account_id": "chk",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 1.0,
      "dedup_status": "pending",
      "duplicate_of": null
    },
    {
      "id": "00002330-5a11-4000-8000-000000009008",
      "date": "2026-10-09",
      "description": "FRESHMART",
      "amount": "46.20",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "food",
      "credit_account_id": "chk",
      "category": "groceries",
      "need": "essential",
      "rule_id": "0000232a-5a11-4000-8000-000000009002",
      "description_override": null,
      "confidence": 1.0,
      "dedup_status": "pending",
      "duplicate_of": null
    },
    {
      "id": "00002331-5a11-4000-8000-000000009009",
      "date": "2026-10-10",
      "description": "HARDWARE STORE REFUND",
      "amount": "19.99",
      "credit_flag": true,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "chk",
      "credit_account_id": "",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "pending",
      "duplicate_of": null
    }
  ]
};

/**
 * FreshMart and the bakery.
 */
export const POSTED: PostedStatementTransactions = {
  "posted": 2,
  "entry_ids": [
    "0000233a-5a11-4000-8000-000000009018",
    "0000233d-5a11-4000-8000-000000009021"
  ]
};

export const PENDING_POSTED: PendingStatementTransactions = {
  "statement_id": "0000232c-5a11-4000-8000-000000009004",
  "transactions": [
    {
      "id": "0000232d-5a11-4000-8000-000000009005",
      "date": "2026-10-01",
      "description": "CITY LETTINGS RENT",
      "amount": "1500.00",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "",
      "credit_account_id": "chk",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "fuzzy_match",
      "duplicate_of": "e067"
    },
    {
      "id": "0000232e-5a11-4000-8000-000000009006",
      "date": "2026-10-05",
      "description": "AUTOFIN CAR LOAN",
      "amount": "350.00",
      "credit_flag": false,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "",
      "credit_account_id": "chk",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "pending",
      "duplicate_of": null
    },
    {
      "id": "00002331-5a11-4000-8000-000000009009",
      "date": "2026-10-10",
      "description": "HARDWARE STORE REFUND",
      "amount": "19.99",
      "credit_flag": true,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "chk",
      "credit_account_id": "",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "pending",
      "duplicate_of": null
    }
  ]
};

/**
 * The rent and the car loan: already booked.
 */
export const DISCARDED: DiscardedStatementTransactions = {
  "discarded": 2
};

export const PENDING_DISCARDED: PendingStatementTransactions = {
  "statement_id": "0000232c-5a11-4000-8000-000000009004",
  "transactions": [
    {
      "id": "00002331-5a11-4000-8000-000000009009",
      "date": "2026-10-10",
      "description": "HARDWARE STORE REFUND",
      "amount": "19.99",
      "credit_flag": true,
      "bank_ref": "",
      "currency": "EUR",
      "account_id": "chk",
      "debit_account_id": "chk",
      "credit_account_id": "",
      "category": "",
      "need": null,
      "rule_id": null,
      "description_override": null,
      "confidence": 0.0,
      "dedup_status": "pending",
      "duplicate_of": null
    }
  ]
};

/**
 * After the console's writes.
 */
export const STATEMENTS_REVIEWED: BankStatementList = {
  "statements": [
    {
      "id": "0000232c-5a11-4000-8000-000000009004",
      "bank": "Example Bank",
      "account_id": "chk",
      "period_start": "2026-10-01",
      "period_end": "2026-10-10",
      "status": "pending",
      "created_at": "2026-10-11T09:30:00+00:00"
    }
  ]
};

/**
 * A file with no transactions in it.
 */
export const UPLOAD_REFUSED: ProblemDetails = {
  "type": "about:blank",
  "title": "Salli couldn't use what was sent",
  "status": 422,
  "detail": [
    "Couldn't tell which columns hold the date and the amount in this CSV file",
    "No transactions found in the file. Check the format is supported."
  ]
};

/**
 * Bistro Novo, tested against what is booked.
 */
export const RULE_TEST: RuleTestResult = {
  "total": 6,
  "agreeing": 6,
  "matches": [
    {
      "entry_id": "e063",
      "entry_date": "2026-09-18",
      "description": "BISTRO NOVO",
      "amount": "77.70",
      "currency": "EUR",
      "direction": "out",
      "account_id": "out"
    },
    {
      "entry_id": "e053",
      "entry_date": "2026-08-18",
      "description": "BISTRO NOVO",
      "amount": "58.30",
      "currency": "EUR",
      "direction": "out",
      "account_id": "out"
    },
    {
      "entry_id": "e043",
      "entry_date": "2026-07-18",
      "description": "BISTRO NOVO",
      "amount": "95.00",
      "currency": "EUR",
      "direction": "out",
      "account_id": "out"
    },
    {
      "entry_id": "e033",
      "entry_date": "2026-06-18",
      "description": "BISTRO NOVO",
      "amount": "71.20",
      "currency": "EUR",
      "direction": "out",
      "account_id": "out"
    },
    {
      "entry_id": "e023",
      "entry_date": "2026-05-18",
      "description": "BISTRO NOVO",
      "amount": "88.50",
      "currency": "EUR",
      "direction": "out",
      "account_id": "out"
    },
    {
      "entry_id": "e013",
      "entry_date": "2026-04-18",
      "description": "BISTRO NOVO",
      "amount": "64.00",
      "currency": "EUR",
      "direction": "out",
      "account_id": "out"
    }
  ]
};

/**
 * A pattern that doesn't compile.
 */
export const RULE_REFUSED: ProblemDetails = {
  "type": "about:blank",
  "title": "Salli couldn't use what was sent",
  "status": 422,
  "detail": "Not a valid pattern: missing ), unterminated subpattern at position 0"
};

/**
 * The first suggestion, made a rule.
 */
export const RULE_MADE: Ref = {
  "id": "00002348-5a11-4000-8000-000000009032"
};

export const RULE_EDITED: Ref = {
  "id": "0000232a-5a11-4000-8000-000000009002"
};

export const RULES_EDITED: CategorizationRule[] = [
  {
    "name": "FreshMart: groceries",
    "conditions": [
      {
        "field": "description",
        "operator": "contains",
        "value": "FRESHMART",
        "value2": null
      }
    ],
    "actions": {
      "account_id": "food",
      "category": "groceries",
      "need": "essential",
      "description": null
    },
    "priority": 10,
    "match_all": true,
    "enabled": true,
    "id": "0000232a-5a11-4000-8000-000000009002",
    "hits": 1,
    "last_hit_at": "2026-10-11T09:30:00Z",
    "created_at": "2026-10-01T09:00:00Z",
    "updated_at": "2026-10-11T10:00:00Z"
  },
  {
    "name": "Acme",
    "conditions": [
      {
        "field": "description",
        "operator": "contains",
        "value": "acme",
        "value2": null
      },
      {
        "field": "direction",
        "operator": "equals",
        "value": "in",
        "value2": null
      }
    ],
    "actions": {
      "account_id": "sal",
      "category": null,
      "need": null,
      "description": null
    },
    "priority": 100,
    "match_all": true,
    "enabled": true,
    "id": "00002348-5a11-4000-8000-000000009032",
    "hits": 0,
    "last_hit_at": null,
    "created_at": "2026-10-11T10:00:00Z",
    "updated_at": "2026-10-11T10:00:00Z"
  }
];
