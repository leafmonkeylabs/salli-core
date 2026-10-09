"""Life-stage derivation — a small pure function alongside the risk engine."""

from __future__ import annotations

from typing import Literal

EmploymentStatus = Literal["employed", "self_employed", "unemployed", "student", "retired"]
LifeStage = Literal["student", "early_career", "family", "pre_retirement", "retired"]


def derive_life_stage(
    age: int | None,
    dependents_count: int,
    employment_status: EmploymentStatus | None,
) -> LifeStage:
    if employment_status == "retired":
        return "retired"
    if employment_status == "student":
        return "student"
    if age is None:
        return "early_career"
    if age < 24:
        return "student"
    if age >= 58:
        return "pre_retirement"
    if dependents_count > 0:
        return "family"
    return "early_career"
