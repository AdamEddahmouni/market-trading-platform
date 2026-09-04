"""Structured uncertainty assessment for BUILD 14."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..contracts.common import QualityState
from .identity import derive_uncertainty_assessment_id
from .types import (
    CalibrationStatus,
    EpistemicState,
    OodReason,
    RawFusionResult,
    UncertaintyAssessment,
)


def predictive_entropy(probability: float | None) -> float | None:
    if probability is None:
        return None
    if probability <= 0.0 or probability >= 1.0:
        return 0.0
    return -(probability * math.log(probability) + (1.0 - probability) * math.log(1.0 - probability)) / math.log(2)


def inter_group_dispersion(group_probabilities: tuple[float, ...]) -> float | None:
    if len(group_probabilities) < 2:
        return None
    mean = sum(group_probabilities) / len(group_probabilities)
    variance = sum((value - mean) ** 2 for value in group_probabilities) / len(group_probabilities)
    return math.sqrt(variance)


@dataclass(frozen=True, slots=True)
class UncertaintyAssessor:
    def assess(
        self,
        *,
        raw_fusion: RawFusionResult,
        calibrated_probability: float | None,
        calibration_status: CalibrationStatus,
        final_policy_identity: str,
        calibration_model_id: str | None,
        required_families: frozenset[str],
        contributor_families: tuple[str, ...],
        ood_reasons: tuple[OodReason, ...] = (),
    ) -> UncertaintyAssessment:
        group_probabilities = tuple(
            group.group_probability
            for group in raw_fusion.dependence_groups
            if group.group_probability is not None
        )
        independent_group_count = len(raw_fusion.dependence_groups)
        dispersion = inter_group_dispersion(group_probabilities)
        epistemic_state = EpistemicState.KNOWN if independent_group_count >= 2 else EpistemicState.UNKNOWN
        coverage = {
            "candidate_count": len(raw_fusion.eligible_contributor_ids) + len(raw_fusion.excluded_contributor_ids),
            "eligible_contributor_count": len(raw_fusion.eligible_contributor_ids),
            "excluded_contributor_count": len(raw_fusion.excluded_contributor_ids),
            "independent_group_count": independent_group_count,
            "required_contributor_families": sorted(required_families),
            "present_contributor_families": sorted(set(contributor_families)),
        }
        assessment_id = derive_uncertainty_assessment_id(
            raw_fusion_id=raw_fusion.fusion_id,
            calibration_model_id=calibration_model_id,
            final_policy_identity=final_policy_identity,
        )
        return UncertaintyAssessment(
            assessment_id=assessment_id,
            raw_probability=raw_fusion.raw_probability,
            calibrated_probability=calibrated_probability,
            predictive_entropy=predictive_entropy(calibrated_probability if calibrated_probability is not None else raw_fusion.raw_probability),
            independent_group_count=independent_group_count,
            inter_group_probability_dispersion=dispersion,
            epistemic_state=epistemic_state,
            coverage=coverage,
            calibration_status=calibration_status,
            ood_reasons=ood_reasons,
            quality_state=raw_fusion.quality,
        )


__all__ = ["UncertaintyAssessor", "inter_group_dispersion", "predictive_entropy"]
