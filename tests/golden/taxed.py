"""
A small household for tax-aware scenarios, on the fictional rule set
"XA 2031" (tests/golden/rules/xa2031.json): a relief of 12,000 on salary
(less pension contributions), then 20% to 40,000 and 40% above; the year
2031-01-01 to 2031-12-31; in New Zealand dollars, the household's base
currency. Every figure is made up; XA is a user-assigned code, no country's.

The books open on 2031-01-01: a salary of 4,000.00 on the 25th of each month
and rent of 1,500.00 on the 1st, January to June. As of 2031-06-30, the
salary so far is 24,000.00 and its monthly average over the five full months
before June (January to May) 4,000.00. No inflation is set.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from typing import Any

from salli.domain.taxrules.engine import content_hash
from tests.baseline_ledger import USER, Ledger

AS_OF = dt.date(2031, 6, 30)
RULES: dict[str, Any] = json.loads((Path(__file__).parent / "rules" / "xa2031.json").read_text())


def rules_row(
    doc: dict[str, Any] | None = None, *, rule_set_id: str = "rs-xa-2031", status: str = "active"
) -> dict[str, Any]:
    """A rule set with its active version, as the repository returns it."""
    content = copy.deepcopy(doc or RULES)
    return {
        "id": rule_set_id,
        "country": content["jurisdiction"]["country"],
        "region": content["jurisdiction"]["region"],
        "year_label": content["year"]["label"],
        "name": f"XA {content['year']['label']}",
        "active_version_id": f"{rule_set_id}-v1",
        "version": {
            "id": f"{rule_set_id}-v1",
            "rule_set_id": rule_set_id,
            "version": 1,
            "status": status,
            "content_hash": content_hash(content),
            "content": content,
        },
    }


def ledger(
    *, residency: str | None = "XA", active: bool = True, months: int = 6, salary: str = "4000"
) -> Ledger:
    """The household's books: XA's rules active unless `active` is False
    (then a draft only), its residency XA unless said otherwise."""
    books = Ledger("NZD")
    books.account("chk", "asset")
    books.account("sal", "income", tax_role="salary")
    books.account("pen", "expense", tax_role="pension")
    books.account("rent", "expense")
    books.account("eq", "equity")
    books.book("2030-12-31", "chk", "eq", "10000")
    for month in range(1, months + 1):
        books.book(f"2031-{month:02d}-01", "rent", "chk", "1500", description="RENT")
        books.book(f"2031-{month:02d}-25", "chk", "sal", salary, description="ACME SALARY")
    if residency:
        books.uow.user_profiles.rows.setdefault(USER, {})["tax_residency"] = residency
    row = rules_row()
    if active:
        books.uow.tax_rule_sets.active.append(row)
    else:
        draft = {**row, "active_version_id": None}
        books.uow.tax_rule_sets.sets = [{k: v for k, v in draft.items() if k != "version"}]
    return books
