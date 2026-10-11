"""
The decision lab's scenarios: what-ifs on the baseline (docs/scenarios.md).

Pure: no I/O, no model, Decimal throughout, and nothing is ever written.

- `schema`: the `salli.scenario/1` document an agent or a person writes, and
  its JSON Schema.
- `engine.run(baseline, scenario)`: every figure (cash over the next twelve
  months, the monthly timeline, debts, resilience, FI) under the baseline and
  under the scenario, with the delta; reproducible, with a content hash of
  its inputs.
- `comparison.compare(baseline, scenarios)`: two to five options side by side,
  the trade between each two, sensitivity to the real return, and
  break-evens. Never a ranking.
- `views`: results as JSON-ready data.
"""

from salli.domain.scenarios.comparison import Comparison, compare
from salli.domain.scenarios.engine import ScenarioError, ScenarioResult, run
from salli.domain.scenarios.schema import SCHEMA_ID, Scenario, json_schema, load

__all__ = [
    "SCHEMA_ID",
    "Comparison",
    "Scenario",
    "ScenarioError",
    "ScenarioResult",
    "compare",
    "json_schema",
    "load",
    "run",
]
