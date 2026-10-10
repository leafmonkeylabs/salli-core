"""A computation as TaxService serves it, made by the real engine from the
minimal test rule set (tests/taxrules/documents.py), for tests of the layers
above it (tools, MCP, API, return workflow) that fake the service."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from salli.application.services.tax_rule_service import Applied
from salli.application.services.tax_service import ActiveRules, _record, _view
from salli.domain.taxrules.engine import compile_rule_set, evaluate
from salli.domain.taxrules.inputs import RoleTotals
from tests.taxrules.documents import minimal


def applied(income: str = "25000", withheld: str = "0", document: dict | None = None) -> Applied:
    doc = document or minimal()
    compiled = compile_rule_set(doc)
    totals = {"income": Decimal(income), "withheld": Decimal(withheld)}
    result = evaluate(compiled, totals)
    version = {"id": "version-2", "version": 2, "validation": {"ok": True}}
    return Applied(
        version=version,
        compiled=compiled,
        result=result,
        totals=RoleTotals(totals, {"income": 1, "withheld": 1 if withheld != "0" else 0}),
        answers={},
        base_currency=doc["currency"],
        rates=[],
        warnings=[],
    )


def active_rules(document: dict | None = None) -> ActiveRules:
    doc = compile_rule_set(document or minimal()).document
    return ActiveRules(
        rule_set={"id": "rule-set-1", "name": "XZ 2031"},
        version={"id": "version-2", "version": 2},
        document=doc,
    )


def computation_view(
    income: str = "25000", withheld: str = "0", **overrides: Any
) -> dict[str, Any]:
    record = _record(active_rules(), applied(income, withheld))
    return _view(
        {
            **record,
            "id": "computation-1",
            "created_at": datetime.datetime(2031, 6, 1, tzinfo=datetime.UTC),
            **overrides,
        }
    )
