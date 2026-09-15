"""Append-only operator overlays on immutable canonical trade reviews."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .contracts import TradeReviewV1


class TradeReviewEditKind(StrEnum):
    NOTES = "NOTES"
    TAGS = "TAGS"
    MISTAKES = "MISTAKES"
    REFLECTION = "REFLECTION"
    DERIVED_REFLECTION = "DERIVED_REFLECTION"


class TradeReviewEditSourceKind(StrEnum):
    OPERATOR = "OPERATOR"
    DERIVED_MODEL = "DERIVED_MODEL"


@dataclass(frozen=True, slots=True)
class TradeReviewOperatorEdit:
    review_id: str
    edit_kind: TradeReviewEditKind
    payload: dict[str, Any]
    created_at_ns: int
    source_kind: TradeReviewEditSourceKind = TradeReviewEditSourceKind.OPERATOR
    model_identity: str | None = None
    edit_id: int | None = None


def merge_operator_edits(
    canonical: TradeReviewV1,
    edits: tuple[TradeReviewOperatorEdit, ...],
) -> tuple[TradeReviewV1, tuple[dict[str, Any], ...]]:
    """Apply latest operator field edits; expose derived commentary separately."""

    notes = canonical.notes
    reflection = canonical.reflection
    tags = canonical.tags
    mistakes = canonical.mistakes
    derived: list[dict[str, Any]] = []
    latest: dict[TradeReviewEditKind, TradeReviewOperatorEdit] = {}
    for edit in edits:
        latest[edit.edit_kind] = edit
    for kind, edit in latest.items():
        if kind == TradeReviewEditKind.NOTES:
            notes = str(edit.payload.get("notes") or "")
        elif kind == TradeReviewEditKind.REFLECTION:
            reflection = str(edit.payload.get("reflection") or "")
        elif kind == TradeReviewEditKind.TAGS:
            tags = tuple(str(v) for v in edit.payload.get("tags") or ())
        elif kind == TradeReviewEditKind.MISTAKES:
            mistakes = tuple(str(v) for v in edit.payload.get("mistakes") or ())
        elif kind == TradeReviewEditKind.DERIVED_REFLECTION:
            derived.append(
                {
                    "reflection": str(edit.payload.get("reflection") or ""),
                    "source_kind": edit.source_kind.value,
                    "model_identity": edit.model_identity,
                    "generated_at_ns": int(
                        edit.payload.get("generated_at_ns") or edit.created_at_ns
                    ),
                }
            )
    merged = TradeReviewV1(
        review_id=canonical.review_id,
        schema_version=canonical.schema_version,
        review_mode=canonical.review_mode,
        decision=canonical.decision,
        decision_time_ns=canonical.decision_time_ns,
        created_at_ns=canonical.created_at_ns,
        opportunity_id=canonical.opportunity_id,
        strategy_id=canonical.strategy_id,
        ftep_campaign=canonical.ftep_campaign,
        ftep_session_id=canonical.ftep_session_id,
        evidence_snapshot_refs=canonical.evidence_snapshot_refs,
        contradictions=canonical.contradictions,
        risk_snapshot=canonical.risk_snapshot,
        preview_refs=canonical.preview_refs,
        execution_attribution=canonical.execution_attribution,
        execution_decision_trace_id=canonical.execution_decision_trace_id,
        tags=tags,
        mistakes=mistakes,
        notes=notes,
        reflection=reflection,
        implementation_version=canonical.implementation_version,
        metadata=dict(canonical.metadata),
    )
    return merged, tuple(derived)


def canonicalize_for_persist(review: TradeReviewV1) -> TradeReviewV1:
    """Strip mutable operator overlays before durable canonical insert."""

    return TradeReviewV1(
        review_id=review.review_id,
        schema_version=review.schema_version,
        review_mode=review.review_mode,
        decision=review.decision,
        decision_time_ns=review.decision_time_ns,
        created_at_ns=review.created_at_ns,
        opportunity_id=review.opportunity_id,
        strategy_id=review.strategy_id,
        ftep_campaign=review.ftep_campaign,
        ftep_session_id=review.ftep_session_id,
        evidence_snapshot_refs=review.evidence_snapshot_refs,
        contradictions=review.contradictions,
        risk_snapshot=review.risk_snapshot,
        preview_refs=review.preview_refs,
        execution_attribution=review.execution_attribution,
        execution_decision_trace_id=review.execution_decision_trace_id,
        tags=(),
        mistakes=(),
        notes="",
        reflection="",
        implementation_version=review.implementation_version,
        metadata=dict(review.metadata),
    )


__all__ = [
    "TradeReviewEditKind",
    "TradeReviewEditSourceKind",
    "TradeReviewOperatorEdit",
    "canonicalize_for_persist",
    "merge_operator_edits",
]
