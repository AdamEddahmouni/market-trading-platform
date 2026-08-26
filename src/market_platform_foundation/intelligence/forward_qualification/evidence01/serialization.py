"""EVIDENCE-01 serialization."""

from __future__ import annotations

from typing import Any

from .types import (
    ForwardEvidenceQualificationAssessmentV1,
    ForwardEvidenceQualificationPolicyV1,
    ForwardEvidenceQualificationReportV1,
    ForwardObservationSummaryV1,
)


def forward_observation_summary_v1_to_dict(summary: ForwardObservationSummaryV1) -> dict[str, Any]:
    return {
        "observation_cutoff_ns": summary.observation_cutoff_ns,
        "settlement_cutoff_ns": summary.settlement_cutoff_ns,
        "first_eligible_decision_ns": summary.first_eligible_decision_ns,
        "last_eligible_decision_ns": summary.last_eligible_decision_ns,
        "elapsed_qualifying_duration_ns": summary.elapsed_qualifying_duration_ns,
        "distinct_trading_days": summary.distinct_trading_days,
        "distinct_sessions": summary.distinct_sessions,
        "raw_observations": summary.raw_observations,
        "eligible_predictions": summary.eligible_predictions,
        "settled_predictions": summary.settled_predictions,
        "unsettled_predictions": summary.unsettled_predictions,
        "abstentions": summary.abstentions,
        "excluded_observations": summary.excluded_observations,
        "exclusions_by_reason": dict(summary.exclusions_by_reason),
        "up_support": summary.up_support,
        "down_support": summary.down_support,
        "settlement_rate": summary.settlement_rate,
        "settlement_rate_state": summary.settlement_rate_state.value,
        "maximum_observation_gap_ns": summary.maximum_observation_gap_ns,
        "provider_disconnected_exclusions": summary.provider_disconnected_exclusions,
    }


def forward_evidence_policy_v1_to_dict(policy: ForwardEvidenceQualificationPolicyV1) -> dict[str, Any]:
    return {
        "policy_id": policy.policy_id,
        "schema_version": policy.schema_version,
        "build26_spec_ref": policy.build26_spec_ref,
        "horizon_ns": policy.horizon_ns,
        "minimum_eligible_predictions": policy.minimum_eligible_predictions,
        "minimum_settled_predictions": policy.minimum_settled_predictions,
        "minimum_settlement_rate": policy.minimum_settlement_rate,
        "minimum_duration_ns": policy.minimum_duration_ns,
        "minimum_distinct_trading_days": policy.minimum_distinct_trading_days,
        "minimum_distinct_sessions": policy.minimum_distinct_sessions,
        "minimum_class_support": policy.minimum_class_support,
        "maximum_admissible_gap_ns": policy.maximum_admissible_gap_ns,
        "required_quality_states": list(policy.required_quality_states),
        "implementation_version": policy.implementation_version,
        "metadata": dict(policy.metadata),
    }


def forward_evidence_assessment_v1_to_dict(
    assessment: ForwardEvidenceQualificationAssessmentV1,
) -> dict[str, Any]:
    return {
        "assessment_id": assessment.assessment_id,
        "schema_version": assessment.schema_version,
        "policy_ref": assessment.policy_ref,
        "observation_cutoff_ns": assessment.observation_cutoff_ns,
        "settlement_cutoff_ns": assessment.settlement_cutoff_ns,
        "source_evidence_fingerprint": assessment.source_evidence_fingerprint,
        "observation_summary": forward_observation_summary_v1_to_dict(assessment.observation_summary),
        "evidence_sufficiency_passed": assessment.evidence_sufficiency_passed,
        "performance_evaluated": assessment.performance_evaluated,
        "qualification_disposition": assessment.qualification_disposition.value,
        "disposition_reason_codes": list(assessment.disposition_reason_codes),
        "limitations": list(assessment.limitations),
        "remaining_requirements": list(assessment.remaining_requirements),
        "implementation_version": assessment.implementation_version,
        "metadata": dict(assessment.metadata),
    }


def forward_evidence_report_v1_to_dict(report: ForwardEvidenceQualificationReportV1) -> dict[str, Any]:
    return {
        "report_id": report.report_id,
        "schema_version": report.schema_version,
        "policy_ref": report.policy_ref,
        "assessment_ref": report.assessment_ref,
        "build26_historical_disposition": report.build26_historical_disposition,
        "build26_historical_report_ref": report.build26_historical_report_ref,
        "evidence01_disposition": report.evidence01_disposition.value,
        "limitation_status": report.limitation_status,
        "observation_summary": forward_observation_summary_v1_to_dict(report.observation_summary),
        "remaining_requirements": list(report.remaining_requirements),
        "implementation_version": report.implementation_version,
        "metadata": dict(report.metadata),
    }
