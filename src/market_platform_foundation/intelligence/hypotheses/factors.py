"""Mechanism factor model for BUILD 13 composite hypotheses."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ShortSqueezeFactor(StrEnum):
    SHORT_PRESSURE = "SHORT_PRESSURE"
    POSITIVE_DEMAND_ACTIVATION = "POSITIVE_DEMAND_ACTIVATION"
    LIQUIDITY_CONSTRAINT = "LIQUIDITY_CONSTRAINT"
    DERIVATIVES_ACCELERATION = "DERIVATIVES_ACCELERATION"
    REGIME_SUPPORT = "REGIME_SUPPORT"
    SHORT_PRESSURE_EASING = "SHORT_PRESSURE_EASING"
    NEGATIVE_DEMAND_PRESSURE = "NEGATIVE_DEMAND_PRESSURE"
    LIQUIDITY_ABUNDANT = "LIQUIDITY_ABUNDANT"
    DERIVATIVES_OPPOSITION = "DERIVATIVES_OPPOSITION"


class FactorState(StrEnum):
    MISSING = "MISSING"
    SUPPORTED = "SUPPORTED"
    CONTESTED = "CONTESTED"
    OPPOSED = "OPPOSED"
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


REQUIRED_SHORT_SQUEEZE_FACTORS = (
    ShortSqueezeFactor.SHORT_PRESSURE,
    ShortSqueezeFactor.POSITIVE_DEMAND_ACTIVATION,
)

OPTIONAL_SHORT_SQUEEZE_FACTORS = (
    ShortSqueezeFactor.LIQUIDITY_CONSTRAINT,
    ShortSqueezeFactor.DERIVATIVES_ACCELERATION,
    ShortSqueezeFactor.REGIME_SUPPORT,
)

OPPOSING_SHORT_SQUEEZE_FACTORS = (
    ShortSqueezeFactor.SHORT_PRESSURE_EASING,
    ShortSqueezeFactor.NEGATIVE_DEMAND_PRESSURE,
    ShortSqueezeFactor.LIQUIDITY_ABUNDANT,
    ShortSqueezeFactor.DERIVATIVES_OPPOSITION,
)


@dataclass(frozen=True, slots=True)
class FactorEvaluation:
    factor: ShortSqueezeFactor
    state: FactorState
    support_refs: tuple[str, ...] = ()
    oppose_refs: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    provenance_groups: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FalsificationCriterion:
    criterion_code: str
    factor: str
    description: str
    observation_type: str


SHORT_SQUEEZE_FALSIFICATION_CRITERIA: tuple[FalsificationCriterion, ...] = (
    FalsificationCriterion(
        criterion_code="SHORT_PRESSURE_NORMALIZES",
        factor=ShortSqueezeFactor.SHORT_PRESSURE.value,
        description="Short-positioning pressure evidence no longer supports constrained short exposure.",
        observation_type="FACTOR_ABSENT_OR_OPPOSED",
    ),
    FalsificationCriterion(
        criterion_code="POSITIVE_DEMAND_ACTIVATION_REVERSES",
        factor=ShortSqueezeFactor.POSITIVE_DEMAND_ACTIVATION.value,
        description="Positive demand activation evidence reverses or is contradicted.",
        observation_type="FACTOR_OPPOSED",
    ),
    FalsificationCriterion(
        criterion_code="REQUIRED_FACTOR_DISAPPEARS",
        factor="CORE_MECHANISM",
        description="A required squeeze-setup factor becomes missing on a subsequent sealed blackboard.",
        observation_type="REQUIRED_FACTOR_MISSING",
    ),
    FalsificationCriterion(
        criterion_code="MECHANISM_OPPOSITION_DOMINATES",
        factor="CORE_MECHANISM",
        description="Opposing mechanism evidence dominates required squeeze-setup support.",
        observation_type="REQUIRED_FACTOR_OPPOSED",
    ),
)


def factor_receipt(evaluations: tuple[FactorEvaluation, ...]) -> dict[str, str]:
    receipt: dict[str, str] = {}
    for row in evaluations:
        if row.factor in REQUIRED_SHORT_SQUEEZE_FACTORS or row.factor in OPPOSING_SHORT_SQUEEZE_FACTORS:
            receipt[row.factor.value] = row.state.value
        elif row.factor in OPTIONAL_SHORT_SQUEEZE_FACTORS:
            if row.state in {FactorState.SUPPORTED, FactorState.CONTESTED, FactorState.PRESENT}:
                receipt[row.factor.value] = FactorState.PRESENT.value
            else:
                receipt[row.factor.value] = FactorState.ABSENT.value
    return receipt


def falsification_codes() -> tuple[str, ...]:
    return tuple(row.criterion_code for row in SHORT_SQUEEZE_FALSIFICATION_CRITERIA)


def falsification_receipt() -> list[dict[str, Any]]:
    return [
        {
            "criterion_code": row.criterion_code,
            "factor": row.factor,
            "description": row.description,
            "observation_type": row.observation_type,
        }
        for row in SHORT_SQUEEZE_FALSIFICATION_CRITERIA
    ]


__all__ = [
    "FactorEvaluation",
    "FactorState",
    "FalsificationCriterion",
    "OPPOSING_SHORT_SQUEEZE_FACTORS",
    "OPTIONAL_SHORT_SQUEEZE_FACTORS",
    "REQUIRED_SHORT_SQUEEZE_FACTORS",
    "SHORT_SQUEEZE_FALSIFICATION_CRITERIA",
    "ShortSqueezeFactor",
    "factor_receipt",
    "falsification_codes",
    "falsification_receipt",
]
