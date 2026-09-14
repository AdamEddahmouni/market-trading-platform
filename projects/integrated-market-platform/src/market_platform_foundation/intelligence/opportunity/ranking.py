"""Explainable operator ranking. Does not change GlobalOpportunityComparator order."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .comparison import (
    ComparisonVectorV1,
    OpportunityComparisonError,
    comparison_vector_from_sidecar,
)
from .dedup import dedup_review_rows, keep_ranked_thesis_winners
from .lifecycle import OperatorLifecycleState
from .read_model import (
    COMPARATOR_DIMENSION_NAMES,
    RANKING_BASIS_ATTENTION,
    RANKING_BASIS_COMPARATOR,
    RANKING_BASIS_STUB,
    OpportunitySummary,
    RankingDimensionV1,
    RankingVectorV1,
    provisional_rank_score,
)


def _sidecar_id(opportunity: Any) -> str | None:
    metadata = getattr(opportunity, "metadata", None) or {}
    raw = metadata.get("economic_assessment_ref") if isinstance(metadata, dict) else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict) and raw.get("id"):
        return str(raw["id"])
    for ref in getattr(opportunity, "lineage_refs", ()) or ():
        kind = getattr(ref.kind, "value", ref.kind)
        if str(kind) == "universal_economic_assessment":
            return str(ref.id)
    return None


def comparison_vectors_from_repository(repository: Any) -> dict[str, ComparisonVectorV1]:
    """Load comparator vectors from persisted sidecars. Missing sidecar → omit (stub later)."""

    if repository is None:
        return {}
    from .ingest import _opportunities_from_repository

    getter = getattr(repository, "get_economic_assessment", None)
    vectors: dict[str, ComparisonVectorV1] = {}
    if not callable(getter):
        return vectors
    for opportunity in _opportunities_from_repository(repository):
        sidecar_id = _sidecar_id(opportunity)
        if not sidecar_id:
            continue
        sidecar = getter(sidecar_id)
        if sidecar is None:
            continue
        try:
            vectors[opportunity.opportunity_id] = comparison_vector_from_sidecar(opportunity, sidecar)
        except (OpportunityComparisonError, TypeError, ValueError):
            continue
    return vectors


def unavailable_comparator_dimensions() -> tuple[RankingDimensionV1, ...]:
    return tuple(
        RankingDimensionV1(name=name, status="UNAVAILABLE", reason_code="SIDECAR_ABSENT")
        for name in COMPARATOR_DIMENSION_NAMES
    )


def ranking_vector_from_comparison(
    vector: ComparisonVectorV1,
    *,
    rank_order: int | None = None,
) -> RankingVectorV1:
    from .comparison import explain_lexicographic_key

    explained = explain_lexicographic_key(vector)
    dimensions = tuple(
        RankingDimensionV1(
            name=str(item["name"]),
            status=str(item["status"]),
            value=item.get("value"),
            unit=item.get("unit"),
            reason_code=item.get("reason_code"),
        )
        for item in explained
    )
    return RankingVectorV1(
        basis=RANKING_BASIS_COMPARATOR,
        dimensions=dimensions,
        rank_order=rank_order,
    )


def rank_review_rows(
    rows: tuple[OpportunitySummary, ...],
    *,
    comparison_vectors: dict[str, ComparisonVectorV1] | None = None,
    dismissed_ids: set[str] | None = None,
) -> tuple[OpportunitySummary, ...]:
    dismissed = dismissed_ids or set()
    visible = [
        row
        for row in dedup_review_rows(rows)
        if row.lifecycle_state != OperatorLifecycleState.INELIGIBLE.value
        and row.summary_id not in dismissed
        and (row.opportunity_id or "") not in dismissed
    ]
    vectors = comparison_vectors or {}

    def sort_key(row: OpportunitySummary) -> tuple[Any, ...]:
        vector = None
        if row.opportunity_id:
            vector = vectors.get(row.opportunity_id)
        if vector is not None:
            return (0, vector.lexicographic_key(cluster_id="review", opportunity_id=row.opportunity_id or row.summary_id))
        if row.identity_kind == "OPPORTUNITY_V1":
            return (1, -provisional_rank_score(row), row.summary_id)
        return (2, row.summary_id)

    ordered = keep_ranked_thesis_winners(tuple(sorted(visible, key=sort_key)))
    ranked: list[OpportunitySummary] = []
    for index, row in enumerate(ordered, start=1):
        vector = vectors.get(row.opportunity_id or "") if row.opportunity_id else None
        if vector is not None:
            ranking_vector = ranking_vector_from_comparison(vector, rank_order=index)
        elif row.identity_kind == "OPPORTUNITY_V1":
            ranking_vector = RankingVectorV1(
                basis=RANKING_BASIS_STUB,
                dimensions=unavailable_comparator_dimensions(),
                rank_order=index,
            )
        else:
            ranking_vector = RankingVectorV1(
                basis=RANKING_BASIS_ATTENTION,
                dimensions=unavailable_comparator_dimensions(),
                rank_order=index,
            )
        lifecycle = row.lifecycle_state or OperatorLifecycleState.RANKED.value
        if row.lifecycle_state in {None, OperatorLifecycleState.ELIGIBLE.value, OperatorLifecycleState.NORMALIZED.value}:
            lifecycle = OperatorLifecycleState.RANKED.value
        ranked.append(
            replace(
                row,
                rank_order=index,
                ranking_vector=ranking_vector,
                lifecycle_state=lifecycle,
            )
        )
    return tuple(ranked)
