"""Promotion eligibility gate (BUILD 20)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..training.types import CandidateArtifactV1
from ..validation.artifacts import verify_candidate_artifact_hash
from ..validation.types import (
    ContaminationDisposition,
    KnowledgeAssessmentStatus,
    ValidationDisposition,
    ValidationReportV1,
)
from .identity import derive_eligibility_assessment_id
from .types import (
    ChampionScopeV1,
    EligibilityDisposition,
    PromotionEligibilityAssessmentV1,
    PromotionPolicyV1,
    PromotionReasonCode,
)

_KNOWLEDGE_PASS_STATUSES = {
    KnowledgeAssessmentStatus.PASS,
    KnowledgeAssessmentStatus.NOT_APPLICABLE,
}


def assess_promotion_eligibility(
    *,
    policy: PromotionPolicyV1,
    candidate: CandidateArtifactV1,
    validation_report: ValidationReportV1,
    candidate_artifact_bytes: bytes | None = None,
    champion_scope: ChampionScopeV1 | None = None,
) -> PromotionEligibilityAssessmentV1:
    scope = champion_scope or policy.champion_scope
    reason_codes: list[PromotionReasonCode] = []
    disposition = EligibilityDisposition.ELIGIBLE
    artifact_integrity_ok = True

    if candidate.candidate_id not in validation_report.candidate_ids:
        disposition = EligibilityDisposition.INELIGIBLE
        reason_codes.append(PromotionReasonCode.VALIDATION_NOT_ELIGIBLE)
    if candidate.candidate_id in validation_report.candidate_ids:
        idx = validation_report.candidate_ids.index(candidate.candidate_id)
        expected_hash = validation_report.candidate_artifact_hashes[idx]
        if candidate.artifact_hash != expected_hash:
            disposition = EligibilityDisposition.INELIGIBLE
            reason_codes.append(PromotionReasonCode.ARTIFACT_INTEGRITY_FAILED)
            artifact_integrity_ok = False
    if policy.require_artifact_integrity and candidate_artifact_bytes is not None:
        try:
            verify_candidate_artifact_hash(candidate, candidate_artifact_bytes)
        except Exception:
            disposition = EligibilityDisposition.INELIGIBLE
            reason_codes.append(PromotionReasonCode.ARTIFACT_INTEGRITY_FAILED)
            artifact_integrity_ok = False

    if validation_report.final_disposition not in policy.required_validation_dispositions:
        disposition = EligibilityDisposition.INELIGIBLE
        if PromotionReasonCode.VALIDATION_NOT_ELIGIBLE not in reason_codes:
            reason_codes.append(PromotionReasonCode.VALIDATION_NOT_ELIGIBLE)
    if validation_report.final_disposition == ValidationDisposition.INVALID_PLAN_DEVIATION:
        disposition = EligibilityDisposition.INELIGIBLE
        reason_codes.append(PromotionReasonCode.PLAN_DEVIATION)

    if policy.require_clean_contamination:
        if validation_report.contamination_disposition == ContaminationDisposition.CONTAMINATED:
            disposition = EligibilityDisposition.INELIGIBLE
            reason_codes.append(PromotionReasonCode.CONTAMINATION_NOT_CLEAN)
        elif validation_report.contamination_disposition == ContaminationDisposition.UNKNOWN:
            disposition = EligibilityDisposition.INELIGIBLE
            reason_codes.append(PromotionReasonCode.CONTAMINATION_NOT_CLEAN)

    if policy.require_temporal_knowledge_pass:
        if validation_report.knowledge_assessment_status not in _KNOWLEDGE_PASS_STATUSES:
            disposition = EligibilityDisposition.INELIGIBLE
            reason_codes.append(PromotionReasonCode.TEMPORAL_KNOWLEDGE_NOT_CLEAN)

    holdout_sample = 0
    for result in validation_report.holdout_results:
        if result.candidate_id == candidate.candidate_id:
            holdout_sample = result.matched_count
            break
    if policy.minimum_holdout_samples > 0 and holdout_sample < policy.minimum_holdout_samples:
        disposition = EligibilityDisposition.INELIGIBLE
        reason_codes.append(PromotionReasonCode.INSUFFICIENT_HOLDOUT_SAMPLE)

    if policy.minimum_walk_forward_folds > 0:
        fold_count = sum(
            1
            for fold in validation_report.fold_results
            if fold.candidate_id == candidate.candidate_id
            and fold.disposition == ValidationDisposition.MEETS_PRE_REGISTERED_CRITERIA
        )
        if fold_count < policy.minimum_walk_forward_folds:
            disposition = EligibilityDisposition.INELIGIBLE
            reason_codes.append(PromotionReasonCode.VALIDATION_NOT_ELIGIBLE)

    if candidate.target_kind != scope.target_kind or candidate.horizon_ns != scope.horizon_ns:
        disposition = EligibilityDisposition.INELIGIBLE
        reason_codes.append(PromotionReasonCode.SCOPE_INCOMPATIBLE)

    assessment_id = derive_eligibility_assessment_id(
        promotion_policy_id=policy.promotion_policy_id,
        candidate_id=candidate.candidate_id,
        candidate_artifact_hash=candidate.artifact_hash,
        validation_report_id=validation_report.validation_report_id,
    )
    return PromotionEligibilityAssessmentV1(
        assessment_id=assessment_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        promotion_policy_id=policy.promotion_policy_id,
        champion_scope=scope,
        candidate_id=candidate.candidate_id,
        candidate_artifact_hash=candidate.artifact_hash,
        validation_report_id=validation_report.validation_report_id,
        experiment_id=validation_report.experiment_id,
        disposition=disposition,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        validation_disposition=validation_report.final_disposition,
        contamination_disposition=validation_report.contamination_disposition,
        knowledge_assessment_status=validation_report.knowledge_assessment_status,
        artifact_integrity_ok=artifact_integrity_ok,
    )


__all__ = ["assess_promotion_eligibility"]
