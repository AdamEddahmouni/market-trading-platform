"""XA-05 state query and comparison helpers."""

from __future__ import annotations

from .contracts import CrossAssetStrategicState, DimensionClassification, state_to_dict
from .enums import StateDimensionId


def get_dimension(
    state: CrossAssetStrategicState,
    dimension_id: StateDimensionId,
) -> DimensionClassification | None:
    for item in state.dimensions:
        if item.dimension_id is dimension_id:
            return item
    return None


def compare_states(
    earlier: CrossAssetStrategicState,
    later: CrossAssetStrategicState,
) -> dict[str, object]:
    earlier_map = {item.dimension_id: item for item in earlier.dimensions}
    later_map = {item.dimension_id: item for item in later.dimensions}
    changed_dimensions: list[dict[str, object]] = []
    for dimension_id in StateDimensionId:
        before = earlier_map.get(dimension_id)
        after = later_map.get(dimension_id)
        if before is None or after is None:
            continue
        if (
            before.classification != after.classification
            or before.evidence_status != after.evidence_status
            or before.numeric_features != after.numeric_features
        ):
            changed_dimensions.append(
                {
                    "dimension_id": dimension_id.value,
                    "before": {
                        "classification": before.classification,
                        "evidence_status": before.evidence_status.value,
                        "numeric_features": dict(before.numeric_features),
                    },
                    "after": {
                        "classification": after.classification,
                        "evidence_status": after.evidence_status.value,
                        "numeric_features": dict(after.numeric_features),
                    },
                }
            )
    added_evidence = sorted(
        set(ref.observation_id for ref in later.evidence_references)
        - set(ref.observation_id for ref in earlier.evidence_references)
    )
    removed_evidence = sorted(
        set(ref.observation_id for ref in earlier.evidence_references)
        - set(ref.observation_id for ref in later.evidence_references)
    )
    return {
        "earlier_state_id": earlier.state_id,
        "later_state_id": later.state_id,
        "earlier_decision_time": earlier.decision_time,
        "later_decision_time": later.decision_time,
        "semantic_fingerprint_changed": (
            earlier.provenance.semantic_fingerprint != later.provenance.semantic_fingerprint
        ),
        "changed_dimensions": changed_dimensions,
        "added_evidence_observation_ids": added_evidence,
        "removed_evidence_observation_ids": removed_evidence,
        "earlier": state_to_dict(earlier),
        "later": state_to_dict(later),
    }
