"""Explicit CANDIDATE→VERIFIED gate on operator review rows only.

Does not mutate ``OpportunityV1``. Promotion requires every fail-closed gate to
pass using fields already on the review row (freshness, family admission,
comparator-ranked economic sidecar). Any missing or negative signal keeps
``CANDIDATE``.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .family_lookup import STATUS_ADMITTED
from .freshness import FRESHNESS_FRESH
from .lifecycle import OperatorLifecycleState
from .read_model import (
    RANKING_BASIS_COMPARATOR,
    OpportunitySummary,
)

EVIDENCE_CLASS_CANDIDATE = "CANDIDATE"
EVIDENCE_CLASS_VERIFIED = "VERIFIED"

PROMOTION_VERIFIED = "EVIDENCE_PROMOTION_GATES_PASSED"
PROMOTION_STAY_CANDIDATE = "EVIDENCE_PROMOTION_STAY_CANDIDATE"

GATE_NOT_OPPORTUNITY_V1 = "NOT_OPPORTUNITY_V1"
GATE_INELIGIBLE = "LIFECYCLE_INELIGIBLE"
GATE_FRESHNESS_NOT_FRESH = "FRESHNESS_NOT_FRESH"
GATE_FAMILY_NOT_ADMITTED = "FAMILY_NOT_ADMITTED"
GATE_COMPARATOR_EVIDENCE_ABSENT = "COMPARATOR_EVIDENCE_ABSENT"


class EvidencePromotionError(ValueError):
    """Invalid evidence promotion inputs."""


def _freshness_status(row: OpportunitySummary) -> str:
    quality = row.data_quality if isinstance(row.data_quality, Mapping) else {}
    evaluation = quality.get("freshness_evaluation") or {}
    if isinstance(evaluation, Mapping):
        return str(evaluation.get("status") or "")
    return ""


def evaluate_evidence_promotion(row: OpportunitySummary) -> tuple[str | None, str]:
    """Return ``(evidence_class, promotion_reason_code)`` without mutating the row."""

    if row.evidence_class is None:
        return None, PROMOTION_STAY_CANDIDATE
    if row.identity_kind != "OPPORTUNITY_V1":
        return EVIDENCE_CLASS_CANDIDATE, GATE_NOT_OPPORTUNITY_V1
    lifecycle = str(row.lifecycle_state or "")
    if lifecycle == OperatorLifecycleState.INELIGIBLE.value or not row.accepted:
        return EVIDENCE_CLASS_CANDIDATE, GATE_INELIGIBLE
    if _freshness_status(row) != FRESHNESS_FRESH:
        return EVIDENCE_CLASS_CANDIDATE, GATE_FRESHNESS_NOT_FRESH
    metadata = row.metadata if isinstance(row.metadata, Mapping) else {}
    if metadata.get("family_admission_status") != STATUS_ADMITTED:
        return EVIDENCE_CLASS_CANDIDATE, GATE_FAMILY_NOT_ADMITTED
    vector = row.ranking_vector
    if vector is None or vector.basis != RANKING_BASIS_COMPARATOR:
        return EVIDENCE_CLASS_CANDIDATE, GATE_COMPARATOR_EVIDENCE_ABSENT
    return EVIDENCE_CLASS_VERIFIED, PROMOTION_VERIFIED


def apply_evidence_promotion(row: OpportunitySummary) -> OpportunitySummary:
    """Project promoted evidence class onto a review row."""

    evidence_class, reason = evaluate_evidence_promotion(row)
    if evidence_class == row.evidence_class and (row.metadata or {}).get("evidence_promotion_reason") == reason:
        return row
    metadata: dict[str, Any] = dict(row.metadata or {})
    metadata["evidence_promotion_reason"] = reason
    if evidence_class == EVIDENCE_CLASS_VERIFIED:
        metadata["evidence_promotion_from"] = EVIDENCE_CLASS_CANDIDATE
    return replace(row, evidence_class=evidence_class, metadata=metadata)


def apply_evidence_promotion_to_rows(
    rows: tuple[OpportunitySummary, ...],
) -> tuple[OpportunitySummary, ...]:
    return tuple(apply_evidence_promotion(row) for row in rows)
