"""Deterministic supervised production pilot identities (BUILD 33)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import (
    BrokerRedundancyAssessmentV1,
    LiveSupervisedPilotPolicyV1,
    LiveSupervisedPilotRunV1,
    OperationalPilotCheckpointV1,
    PilotOperationalReviewV1,
    ProviderDivergenceAssessmentV1,
    ProviderRedundancyPolicyV1,
    ProviderSelectionDecisionV1,
    RunbookExerciseReportV1,
    RunbookExerciseSpecV1,
    ScheduledReliabilityReviewV1,
    SustainedPilotQualificationReportV1,
    SustainedPilotQualificationSpecV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def derive_pilot_policy_id(policy: LiveSupervisedPilotPolicyV1) -> str:
    payload = {
        "source_build32_ref": policy.source_build32_ref,
        "pilot_start_ns": policy.pilot_start_ns,
        "pilot_end_ns": policy.pilot_end_ns,
        "allowed_market_sessions": list(policy.allowed_market_sessions),
        "allowed_data_providers": list(policy.allowed_data_providers),
        "primary_provider_policy": dict(policy.primary_provider_policy),
        "allowed_live_broker": policy.allowed_live_broker,
        "allowed_live_account_ref": policy.allowed_live_account_ref,
        "max_pilot_sessions": policy.max_pilot_sessions,
        "max_pilot_orders": policy.max_pilot_orders,
        "max_pilot_fills": policy.max_pilot_fills,
        "max_pilot_single_order_notional_minor": policy.max_pilot_single_order_notional_minor,
        "max_pilot_total_notional_minor": policy.max_pilot_total_notional_minor,
        "max_pilot_live_exposure_minor": policy.max_pilot_live_exposure_minor,
        "provider_redundancy_policy_ref": policy.provider_redundancy_policy_ref,
        "required_slo_policy_ref": policy.required_slo_policy_ref,
        "required_alert_policy_ref": policy.required_alert_policy_ref,
        "required_reconciliation_interval_ns": policy.required_reconciliation_interval_ns,
        "required_operational_checkpoint_interval_ns": policy.required_operational_checkpoint_interval_ns,
        "required_backup_freshness_ns": policy.required_backup_freshness_ns,
        "required_restore_drill_age_ns": policy.required_restore_drill_age_ns,
        "human_session_authorization_required": policy.human_session_authorization_required,
        "human_order_confirmation_required": policy.human_order_confirmation_required,
        "manual_resume_required": policy.manual_resume_required,
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("PILPOL", payload)


def derive_pilot_run_id(run: LiveSupervisedPilotRunV1) -> str:
    payload = {
        "pilot_policy_ref": run.pilot_policy_ref,
        "build33_source_ref": run.build33_source_ref,
        "start_ns": run.start_ns,
        "broker_certification_ref": run.broker_certification_ref,
        "live_account_ref": run.live_account_ref,
    }
    return _sha256_prefix("PILRUN", payload)


def derive_provider_redundancy_policy_id(policy: ProviderRedundancyPolicyV1) -> str:
    payload = {
        "scope": policy.scope,
        "capability": policy.capability,
        "instrument_class": policy.instrument_class,
        "primary_provider": policy.primary_provider,
        "fallback_providers": list(policy.fallback_providers),
        "minimum_failure_duration_ns": policy.minimum_failure_duration_ns,
        "minimum_recovery_duration_ns": policy.minimum_recovery_duration_ns,
        "switch_cooldown_ns": policy.switch_cooldown_ns,
        "divergence_warning_bps": policy.divergence_warning_bps,
        "divergence_critical_bps": policy.divergence_critical_bps,
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("PRPOL", payload)


def derive_provider_selection_decision_id(decision: ProviderSelectionDecisionV1) -> str:
    payload = {
        "decision_time_ns": decision.decision_time_ns,
        "scope": decision.scope,
        "capability": decision.capability,
        "selected_provider": decision.selected_provider,
        "decision_reason": decision.decision_reason,
        "policy_ref": decision.policy_ref,
    }
    return _sha256_prefix("PRVSEL", payload)


def derive_provider_divergence_id(assessment: ProviderDivergenceAssessmentV1) -> str:
    payload = {
        "as_of_ns": assessment.as_of_ns,
        "instrument": assessment.instrument,
        "capability": assessment.capability,
        "provider_a": assessment.provider_a,
        "provider_b": assessment.provider_b,
        "status": assessment.status,
        "policy_ref": assessment.policy_ref,
    }
    return _sha256_prefix("PRVDIV", payload)


def derive_broker_redundancy_assessment_id(assessment: BrokerRedundancyAssessmentV1) -> str:
    payload = {
        "brokers_assessed": list(assessment.brokers_assessed),
        "auto_failover_authorization": assessment.auto_failover_authorization,
        "implementation_version": assessment.implementation_version,
    }
    return _sha256_prefix("BRKRED", payload)


def derive_pilot_checkpoint_id(checkpoint: OperationalPilotCheckpointV1) -> str:
    payload = {
        "pilot_run_ref": checkpoint.pilot_run_ref,
        "as_of_ns": checkpoint.as_of_ns,
        "pilot_state": checkpoint.pilot_state,
    }
    return _sha256_prefix("PILCHK", payload)


def derive_pilot_review_id(review: PilotOperationalReviewV1) -> str:
    payload = {
        "pilot_run_ref": review.pilot_run_ref,
        "review_window_start_ns": review.review_window_start_ns,
        "review_window_end_ns": review.review_window_end_ns,
        "operator_review_disposition": review.operator_review_disposition,
    }
    return _sha256_prefix("PILREV", payload)


def derive_runbook_exercise_spec_id(spec: RunbookExerciseSpecV1) -> str:
    payload = {
        "runbook_id": spec.runbook_id,
        "runbook_version": spec.runbook_version,
        "trigger": spec.trigger,
        "implementation_version": spec.implementation_version,
    }
    return _sha256_prefix("RBEXSP", payload)


def derive_runbook_exercise_report_id(report: RunbookExerciseReportV1) -> str:
    payload = {
        "exercise_spec_ref": report.exercise_spec_ref,
        "result": report.result,
        "real_broker_submits": report.real_broker_submits,
    }
    return _sha256_prefix("RBEXPR", payload)


def derive_reliability_review_id(review: ScheduledReliabilityReviewV1) -> str:
    payload = {
        "review_window_start_ns": review.review_window_start_ns,
        "review_window_end_ns": review.review_window_end_ns,
        "recommendation": review.recommendation,
    }
    return _sha256_prefix("RELREV", payload)


def derive_pilot_qualification_spec_id(spec: SustainedPilotQualificationSpecV1) -> str:
    payload = {
        "pilot_policy_ref": spec.pilot_policy_ref,
        "minimum_observation_duration_ns": spec.minimum_observation_duration_ns,
        "required_market_sessions": spec.required_market_sessions,
        "implementation_version": spec.implementation_version,
    }
    return _sha256_prefix("PILQSP", payload)


def derive_pilot_qualification_report_id(report: SustainedPilotQualificationReportV1) -> str:
    payload = {
        "qualification_spec_ref": report.qualification_spec_ref,
        "pilot_run_ref": report.pilot_run_ref,
        "disposition": report.disposition,
    }
    return _sha256_prefix("PILQRP", payload)
