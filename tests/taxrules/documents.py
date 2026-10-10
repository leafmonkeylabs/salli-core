"""A small, valid rule set for tests to break one piece at a time."""

from __future__ import annotations

import copy
from typing import Any

_MINIMAL: dict[str, Any] = {
    "schema": "salli.tax/1",
    "jurisdiction": {"country": "XZ"},
    "year": {"label": "2031", "start": "2031-01-01", "end": "2031-12-31"},
    "currency": "EUR",
    "sources": [{"id": "law", "url": "https://example.org/law", "title": "A fictional law"}],
    "roles": [
        {"key": "income", "kind": "income", "label": "Income"},
        {"key": "withheld", "kind": "withholding", "label": "Tax withheld"},
    ],
    "band_tables": {
        "main": {
            "bands": [{"upto": "10000", "rate": "0.1"}, {"upto": None, "rate": "0.2"}],
            "source": "law",
        }
    },
    "blocks": [
        {
            "type": "relief",
            "key": "allowance",
            "of": "role.income",
            "amount": "5000",
            "source": "law",
        },
        {"type": "schedule", "key": "tax", "of": "line.allowance.remaining", "table": "main"},
        {"type": "credit", "key": "withholding", "of": "role.withheld", "refundable": True},
    ],
    "lines": [
        {"key": "balance", "label": "Tax less withholding", "expr": "line.tax - line.withholding"}
    ],
    "result": {"net": "line.balance"},
    # 25,000 − 5,000 = 20,000: 10,000 × 10% + 10,000 × 20% = 3,000
    "examples": [
        {
            "name": "Basic",
            "source": "law",
            "inputs": {"income": "25000"},
            "expected": {"payable": "3000"},
        }
    ],
}


def minimal() -> dict[str, Any]:
    """A fresh copy of the minimal document, safe to mutate."""
    return copy.deepcopy(_MINIMAL)
