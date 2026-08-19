"""SHARED P4 opportunity fusion adapter — publishes cross-lane evidence from fused snapshots."""

from __future__ import annotations

from typing import Any

from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
    validate_evidence_dag,
)
from ..cross_lane.fusion import build_opportunity_snapshot
from .cross_lane_adapter import (
    build_cross_lane_snapshot_from_options,
    build_cross_lane_snapshot_from_order_flow,
    build_cross_lane_snapshot_from_squeeze,
    merge_cross_lane_evidence,
    merge_cross_lane_snapshots,
)


def opportunity_evidence_from_snapshot(
    opportunity_snapshot: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Publish SHARED P4 evidence from an opportunity fusion snapshot."""
    if not opportunity_snapshot or not opportunity_snapshot.get("available"):
        return []

    outcome = opportunity_snapshot.get("outcome")
    fused_net_ev = opportunity_snapshot.get("fused_net_ev")
    fusion = opportunity_snapshot.get("fusion")
    template = fusion.get("template") if isinstance(fusion, dict) else None

    if outcome == "RANKED" and isinstance(fused_net_ev, (int, float)) and float(fused_net_ev) > 0:
        return [
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.OPTIONS,
                    signal=EvidenceSignal.CROSS_LANE_OPPORTUNITY_FUSED,
                    strength="MODERATE" if float(fused_net_ev) < 500 else "HIGH",
                    available=True,
                    source_ref="platform:opportunity_fusion",
                    detail=(
                        f"Fused net EV {float(fused_net_ev):.2f} "
                        f"template={template}; not a trade recommendation"
                    ),
                    provenance_class=EvidenceProvenanceClass.CROSS_LANE_MODEL_OUTPUT,
                )
            )
        ]

    if outcome == "NO_ACTIONABLE_EDGE":
        reason = opportunity_snapshot.get("reason", "NO_ACTIONABLE_EDGE")
        return [
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.OPTIONS,
                    signal=EvidenceSignal.OPPORTUNITY_NO_ACTIONABLE_EDGE,
                    strength="LOW",
                    available=True,
                    source_ref="platform:opportunity_fusion",
                    detail=f"No actionable fused opportunity: {reason}; valid research outcome",
                    provenance_class=EvidenceProvenanceClass.CROSS_LANE_MODEL_OUTPUT,
                )
            )
        ]

    return []


def build_opportunity_fusion_bundle(
    symbol: str,
    as_of_time: str,
    *,
    strategy_snapshot: dict[str, Any] | None = None,
    execution_snapshot: dict[str, Any] | None = None,
    physical_forecast: dict[str, Any] | None = None,
    squeeze_context: dict[str, Any] | None = None,
    squeeze_detail: dict[str, Any] | None = None,
    order_flow_payload: dict[str, Any] | None = None,
    options_payload: dict[str, Any] | None = None,
    execution_friction: dict[str, Any] | None = None,
    existing_evidence: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Merge lane snapshots, fuse opportunity, and append SHARED P4 evidence."""
    squeeze_snapshot, squeeze_evidence = build_cross_lane_snapshot_from_squeeze(squeeze_detail)
    options_snapshot, options_evidence = build_cross_lane_snapshot_from_options(
        options_payload or {},
    )
    order_flow_snapshot, order_flow_evidence = build_cross_lane_snapshot_from_order_flow(
        order_flow_payload,
    )

    cross_lane_snapshot = merge_cross_lane_snapshots(
        squeeze_snapshot,
        options_snapshot,
        order_flow_snapshot,
    )
    lane_evidence = merge_cross_lane_evidence(
        squeeze_evidence,
        options_evidence,
        order_flow_evidence,
        existing_evidence or [],
    )

    opportunity_snapshot = build_opportunity_snapshot(
        symbol,
        as_of_time,
        strategy_snapshot=strategy_snapshot,
        execution_snapshot=execution_snapshot,
        physical_forecast=physical_forecast,
        squeeze_context=squeeze_context,
        cross_lane_snapshot=cross_lane_snapshot,
        order_flow_payload=order_flow_payload,
        execution_friction=execution_friction,
    )

    opportunity_evidence = opportunity_evidence_from_snapshot(opportunity_snapshot)
    all_evidence = merge_cross_lane_evidence(lane_evidence, opportunity_evidence)

    normalized_items: list[NormalizedLaneEvidence] = []
    for row in all_evidence:
        if not isinstance(row, dict):
            continue
        try:
            lane = LaneId(str(row.get("lane", LaneId.OPTIONS.value)))
            signal = EvidenceSignal(str(row.get("signal")))
            provenance = EvidenceProvenanceClass(
                str(row.get("provenance_class", EvidenceProvenanceClass.DERIVED.value))
            )
        except ValueError:
            continue
        normalized_items.append(
            NormalizedLaneEvidence(
                lane=lane,
                signal=signal,
                strength=str(row.get("strength", "LOW")),
                available=bool(row.get("available", True)),
                source_ref=str(row.get("source_ref", "")),
                detail=str(row.get("detail", "")),
                observed_at=row.get("observed_at"),
                quality_flags=tuple(row.get("quality_flags", [])),
                provenance_class=provenance,
            )
        )

    dag_violations = validate_evidence_dag(normalized_items)
    if dag_violations:
        opportunity_snapshot = {
            **opportunity_snapshot,
            "dag_violations": dag_violations,
        }

    bundle = {
        "opportunity_snapshot": opportunity_snapshot,
        "cross_lane_snapshot": cross_lane_snapshot,
        "evidence_count": len(all_evidence),
    }
    return bundle, all_evidence


__all__ = [
    "build_opportunity_fusion_bundle",
    "opportunity_evidence_from_snapshot",
]
