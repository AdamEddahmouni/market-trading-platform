"""Deterministic multi-source candidate scoring and conflict retention."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .observations import Observation


@dataclass(frozen=True, slots=True)
class QualityScore:
    completeness: float
    freshness: float
    timestamp_validity: float
    entitlement: float
    consistency: float
    source_reliability: float

    def total(self) -> float:
        values = (
            self.completeness,
            self.freshness,
            self.timestamp_validity,
            self.entitlement,
            self.consistency,
            self.source_reliability,
        )
        if any(not 0.0 <= value <= 1.0 for value in values):
            raise ValueError("QUALITY_SCORE_INVALID")
        return sum(values) / len(values)

    @classmethod
    def from_observation(
        cls,
        observation: Observation,
        *,
        now_time_ns: int | None = None,
        stale_after_ns: int | None = None,
    ) -> "QualityScore":
        complete = observation.value is not None and observation.value not in ({}, "")
        future = (
            now_time_ns is not None
            and observation.clocks.available_time_ns > now_time_ns
        )
        stale = (
            now_time_ns is not None
            and stale_after_ns is not None
            and now_time_ns - observation.clocks.available_time_ns > stale_after_ns
        )
        timestamp_valid = (
            observation.clocks.available_time_ns >= observation.clocks.event_time_ns
            and not future
        )
        return cls(
            1.0 if complete else 0.0,
            0.0 if future or stale else 1.0,
            1.0 if timestamp_valid else 0.0,
            0.0 if observation.license_class.strip().upper() == "UNKNOWN" else 1.0,
            1.0,
            observation.confidence,
        )


@dataclass(frozen=True, slots=True)
class ReconciliationPolicy:
    now_time_ns: int | None = None
    as_of_time_ns: int | None = None
    stale_after_ns: int | None = None
    numeric_tolerance: float = 0.0
    allow_stale: bool = False
    require_timestamp_validity: bool = True
    minimum_confidence: float = 0.0

    def __post_init__(self) -> None:
        for value in (self.now_time_ns, self.as_of_time_ns, self.stale_after_ns):
            if value is not None and value < 0:
                raise ValueError("RECONCILIATION_TIME_INVALID")
        if self.numeric_tolerance < 0 or not 0.0 <= self.minimum_confidence <= 1.0:
            raise ValueError("RECONCILIATION_POLICY_INVALID")


@dataclass(frozen=True, slots=True)
class CandidateObservation:
    observation: Observation
    quality_score: QualityScore | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationConflict:
    code: str
    observation_ids: tuple[str, ...]
    details: str


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    selected: Observation
    candidates: tuple[CandidateObservation, ...]
    conflicts: tuple[ReconciliationConflict, ...]
    selection_reason: str
    quality_summary: dict[str, float]


def reconcile_candidates(
    candidates: tuple[CandidateObservation, ...],
    *,
    value_type: str,
    numeric_tolerance: float = 0.0,
    policy: ReconciliationPolicy | None = None,
) -> ReconciliationResult:
    if not candidates:
        raise ValueError("RECONCILIATION_CANDIDATES_REQUIRED")
    if value_type not in {"numeric", "string", "enum", "object"}:
        raise ValueError("RECONCILIATION_VALUE_TYPE_INVALID")
    active_policy = policy or ReconciliationPolicy(numeric_tolerance=numeric_tolerance)
    tolerance = active_policy.numeric_tolerance

    def score(item: CandidateObservation) -> float:
        quality = item.quality_score or QualityScore.from_observation(
            item.observation,
            now_time_ns=active_policy.now_time_ns,
            stale_after_ns=active_policy.stale_after_ns,
        )
        return quality.total()

    ordered = tuple(
        sorted(
            candidates,
            key=lambda item: (-score(item), item.observation.provider_id, item.observation.observation_id),
        )
    )
    selected = ordered[0].observation
    conflicts: list[ReconciliationConflict] = []
    eligible: list[CandidateObservation] = []
    for candidate in ordered:
        observation = candidate.observation
        clocks = observation.clocks
        timestamp_valid = (
            clocks.available_time_ns >= clocks.event_time_ns
            and clocks.validity_start_ns <= clocks.available_time_ns
            and (
                active_policy.now_time_ns is None
                or clocks.available_time_ns <= active_policy.now_time_ns
            )
            and (
                clocks.validity_end_ns is None
                or clocks.validity_end_ns >= clocks.validity_start_ns
            )
        )
        if not timestamp_valid:
            conflicts.append(
                ReconciliationConflict("TIMESTAMP_INVALID", (observation.observation_id,), "clock ordering is invalid")
            )
        stale = (
            active_policy.now_time_ns is not None
            and active_policy.stale_after_ns is not None
            and active_policy.now_time_ns - clocks.available_time_ns > active_policy.stale_after_ns
        )
        if stale:
            conflicts.append(
                ReconciliationConflict("STALE_CANDIDATE", (observation.observation_id,), "available time exceeds freshness policy")
            )
        if observation.confidence < active_policy.minimum_confidence:
            conflicts.append(
                ReconciliationConflict("LOW_CONFIDENCE", (observation.observation_id,), "confidence is below policy minimum")
            )
        as_of_valid = (
            active_policy.as_of_time_ns is None
            or clocks.available_time_ns <= active_policy.as_of_time_ns
        )
        if (
            (not active_policy.require_timestamp_validity or timestamp_valid)
            and (active_policy.allow_stale or not stale)
            and observation.confidence >= active_policy.minimum_confidence
            and as_of_valid
        ):
            eligible.append(candidate)
    if eligible:
        selected = eligible[0].observation
    values = [item.observation.value for item in ordered]
    if value_type == "numeric":
        numbers = [_numeric_value(value) for value in values]
        if max(numbers) - min(numbers) > tolerance:
            conflicts.append(
                ReconciliationConflict(
                    "VALUE_OUTLIER",
                    tuple(item.observation.observation_id for item in ordered),
                    f"numeric spread {max(numbers) - min(numbers):.12g} exceeds tolerance {tolerance:.12g}",
                )
            )
    elif value_type in {"string", "enum", "object"} and any(value != values[0] for value in values[1:]):
        conflicts.append(
            ReconciliationConflict(
                "VALUE_CONFLICT",
                tuple(item.observation.observation_id for item in ordered),
                "candidate values disagree",
            )
        )
    return ReconciliationResult(
        selected=selected,
        candidates=ordered,
        conflicts=tuple(conflicts),
        selection_reason=f"highest_quality:{selected.provider_id}",
        quality_summary={
            item.observation.observation_id: round(score(item), 6)
            for item in ordered
        },
    )


def _numeric_value(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("NUMERIC_VALUE_INVALID")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict) and isinstance(value.get("price"), (int, float)):
        return float(value["price"])
    raise ValueError("NUMERIC_VALUE_INVALID")


__all__ = [
    "CandidateObservation",
    "QualityScore",
    "ReconciliationConflict",
    "ReconciliationPolicy",
    "ReconciliationResult",
    "reconcile_candidates",
]
