"""Serialization for BUILD 20 promotion artifacts."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..research_experiments.types import ComplexityBudget, EvidenceTier
from ..validation.types import ContaminationDisposition, KnowledgeAssessmentStatus, ValidationDisposition
from .types import (
    ChampionAssignmentReason,
    ChampionAssignmentStatus,
    ChampionAssignmentV1,
    ChampionScopeV1,
    ChallengerLifecycleEventV1,
    ChallengerLifecycleState,
    ChallengerRegistrationV1,
    ComplexityGateResult,
    ComplexityPolicy,
    ComplexityPolicyKind,
    EligibilityDisposition,
    GuardrailGateResult,
    GuardrailRule,
    MetricDirection,
    MetricGateResult,
    PromotionDecisionKind,
    PromotionDecisionV1,
    PromotionEligibilityAssessmentV1,
    PromotionPolicyV1,
    PromotionReasonCode,
    ShadowEvidenceManifestV1,
    ShadowMatchedObservation,
    StatisticalGateResult,
    StatisticalRequirementKind,
)


def _scope_to_dict(scope: ChampionScopeV1) -> dict[str, Any]:
    return {
        "component": scope.component,
        "target_kind": scope.target_kind,
        "horizon_ns": scope.horizon_ns,
        "mode": scope.mode,
        "scenario_id": scope.scenario_id,
    }


def _scope_from_dict(payload: dict[str, Any]) -> ChampionScopeV1:
    return ChampionScopeV1(
        component=str(payload["component"]),
        target_kind=str(payload["target_kind"]),
        horizon_ns=int(payload["horizon_ns"]),
        mode=str(payload["mode"]),
        scenario_id=payload.get("scenario_id"),
    )


def _guardrail_to_dict(rule: GuardrailRule) -> dict[str, Any]:
    return {
        "metric_name": rule.metric_name,
        "direction": rule.direction.value,
        "max_regression": rule.max_regression,
        "max_absolute": rule.max_absolute,
    }


def _guardrail_from_dict(payload: dict[str, Any]) -> GuardrailRule:
    return GuardrailRule(
        metric_name=str(payload["metric_name"]),
        direction=MetricDirection(str(payload["direction"])),
        max_regression=payload.get("max_regression"),
        max_absolute=payload.get("max_absolute"),
    )


def promotion_policy_v1_to_dict(policy: PromotionPolicyV1) -> dict[str, Any]:
    return {
        "schema_version": policy.schema_version,
        "promotion_policy_id": policy.promotion_policy_id,
        "champion_scope": _scope_to_dict(policy.champion_scope),
        "required_validation_dispositions": [d.value for d in policy.required_validation_dispositions],
        "require_clean_contamination": policy.require_clean_contamination,
        "require_temporal_knowledge_pass": policy.require_temporal_knowledge_pass,
        "require_artifact_integrity": policy.require_artifact_integrity,
        "primary_metric": policy.primary_metric,
        "primary_metric_direction": policy.primary_metric_direction.value,
        "required_improvement": policy.required_improvement,
        "secondary_metrics": list(policy.secondary_metrics),
        "guardrails": [_guardrail_to_dict(g) for g in policy.guardrails],
        "minimum_walk_forward_folds": policy.minimum_walk_forward_folds,
        "minimum_holdout_samples": policy.minimum_holdout_samples,
        "minimum_shadow_samples": policy.minimum_shadow_samples,
        "minimum_shadow_duration_ns": policy.minimum_shadow_duration_ns,
        "require_locked_holdout": policy.require_locked_holdout,
        "require_shadow_evidence": policy.require_shadow_evidence,
        "require_forward_shadow_evidence": policy.require_forward_shadow_evidence,
        "allowed_shadow_evidence_tiers": [t.value for t in policy.allowed_shadow_evidence_tiers],
        "statistical_requirement": policy.statistical_requirement.value,
        "complexity_policy": {
            "kind": policy.complexity_policy.kind.value,
            "base_required_improvement": policy.complexity_policy.base_required_improvement,
            "minor_complexity_additional_margin": policy.complexity_policy.minor_complexity_additional_margin,
            "major_complexity_additional_margin": policy.complexity_policy.major_complexity_additional_margin,
        },
        "allowed_validation_modes": list(policy.allowed_validation_modes),
        "implementation_version": policy.implementation_version,
        "metadata": dict(policy.metadata),
    }


def promotion_policy_v1_from_dict(payload: dict[str, Any]) -> PromotionPolicyV1:
    complexity = payload["complexity_policy"]
    return PromotionPolicyV1(
        promotion_policy_id=str(payload["promotion_policy_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        required_validation_dispositions=tuple(
            ValidationDisposition(v) for v in payload["required_validation_dispositions"]
        ),
        require_clean_contamination=bool(payload["require_clean_contamination"]),
        require_temporal_knowledge_pass=bool(payload["require_temporal_knowledge_pass"]),
        require_artifact_integrity=bool(payload["require_artifact_integrity"]),
        primary_metric=str(payload["primary_metric"]),
        primary_metric_direction=MetricDirection(str(payload["primary_metric_direction"])),
        required_improvement=float(payload["required_improvement"]),
        secondary_metrics=tuple(str(v) for v in payload.get("secondary_metrics", [])),
        guardrails=tuple(_guardrail_from_dict(g) for g in payload.get("guardrails", [])),
        minimum_walk_forward_folds=int(payload["minimum_walk_forward_folds"]),
        minimum_holdout_samples=int(payload["minimum_holdout_samples"]),
        minimum_shadow_samples=int(payload["minimum_shadow_samples"]),
        minimum_shadow_duration_ns=int(payload["minimum_shadow_duration_ns"]),
        require_locked_holdout=bool(payload["require_locked_holdout"]),
        require_shadow_evidence=bool(payload["require_shadow_evidence"]),
        require_forward_shadow_evidence=bool(payload["require_forward_shadow_evidence"]),
        allowed_shadow_evidence_tiers=tuple(
            EvidenceTier(v) for v in payload["allowed_shadow_evidence_tiers"]
        ),
        statistical_requirement=StatisticalRequirementKind(str(payload["statistical_requirement"])),
        complexity_policy=ComplexityPolicy(
            kind=ComplexityPolicyKind(str(complexity["kind"])),
            base_required_improvement=float(complexity["base_required_improvement"]),
            minor_complexity_additional_margin=float(complexity.get("minor_complexity_additional_margin", 0.0)),
            major_complexity_additional_margin=float(complexity.get("major_complexity_additional_margin", 0.0)),
        ),
        allowed_validation_modes=tuple(str(v) for v in payload.get("allowed_validation_modes", [])),
        implementation_version=str(payload.get("implementation_version", "")),
        metadata=dict(payload.get("metadata", {})),
    )


def promotion_eligibility_assessment_v1_to_dict(assessment: PromotionEligibilityAssessmentV1) -> dict[str, Any]:
    return {
        "schema_version": assessment.schema_version,
        "assessment_id": assessment.assessment_id,
        "promotion_policy_id": assessment.promotion_policy_id,
        "champion_scope": _scope_to_dict(assessment.champion_scope),
        "candidate_id": assessment.candidate_id,
        "candidate_artifact_hash": assessment.candidate_artifact_hash,
        "validation_report_id": assessment.validation_report_id,
        "experiment_id": assessment.experiment_id,
        "disposition": assessment.disposition.value,
        "reason_codes": [code.value for code in assessment.reason_codes],
        "validation_disposition": assessment.validation_disposition.value if assessment.validation_disposition else None,
        "contamination_disposition": assessment.contamination_disposition.value if assessment.contamination_disposition else None,
        "knowledge_assessment_status": assessment.knowledge_assessment_status.value if assessment.knowledge_assessment_status else None,
        "artifact_integrity_ok": assessment.artifact_integrity_ok,
        "implementation_version": assessment.implementation_version,
        "metadata": dict(assessment.metadata),
    }


def promotion_eligibility_assessment_v1_from_dict(payload: dict[str, Any]) -> PromotionEligibilityAssessmentV1:
    return PromotionEligibilityAssessmentV1(
        assessment_id=str(payload["assessment_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        promotion_policy_id=str(payload["promotion_policy_id"]),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        candidate_id=str(payload["candidate_id"]),
        candidate_artifact_hash=str(payload["candidate_artifact_hash"]),
        validation_report_id=str(payload["validation_report_id"]),
        experiment_id=str(payload["experiment_id"]),
        disposition=EligibilityDisposition(str(payload["disposition"])),
        reason_codes=tuple(PromotionReasonCode(v) for v in payload.get("reason_codes", [])),
        validation_disposition=ValidationDisposition(payload["validation_disposition"]) if payload.get("validation_disposition") else None,
        contamination_disposition=ContaminationDisposition(payload["contamination_disposition"]) if payload.get("contamination_disposition") else None,
        knowledge_assessment_status=KnowledgeAssessmentStatus(payload["knowledge_assessment_status"]) if payload.get("knowledge_assessment_status") else None,
        artifact_integrity_ok=bool(payload.get("artifact_integrity_ok", False)),
        implementation_version=str(payload.get("implementation_version", "")),
        metadata=dict(payload.get("metadata", {})),
    )


def challenger_registration_v1_to_dict(registration: ChallengerRegistrationV1) -> dict[str, Any]:
    return {
        "schema_version": registration.schema_version,
        "challenger_registration_id": registration.challenger_registration_id,
        "candidate_id": registration.candidate_id,
        "candidate_artifact_hash": registration.candidate_artifact_hash,
        "champion_scope": _scope_to_dict(registration.champion_scope),
        "current_champion_assignment_id": registration.current_champion_assignment_id,
        "validation_report_id": registration.validation_report_id,
        "promotion_policy_id": registration.promotion_policy_id,
        "eligibility_assessment_id": registration.eligibility_assessment_id,
        "registered_at_ns": registration.registered_at_ns,
        "minimum_shadow_samples": registration.minimum_shadow_samples,
        "minimum_shadow_duration_ns": registration.minimum_shadow_duration_ns,
        "shadow_window_start_ns": registration.shadow_window_start_ns,
        "shadow_window_end_ns": registration.shadow_window_end_ns,
        "lifecycle_state": registration.lifecycle_state.value,
        "metadata": dict(registration.metadata),
    }


def challenger_registration_v1_from_dict(payload: dict[str, Any]) -> ChallengerRegistrationV1:
    return ChallengerRegistrationV1(
        challenger_registration_id=str(payload["challenger_registration_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        candidate_id=str(payload["candidate_id"]),
        candidate_artifact_hash=str(payload["candidate_artifact_hash"]),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        current_champion_assignment_id=str(payload["current_champion_assignment_id"]),
        validation_report_id=str(payload["validation_report_id"]),
        promotion_policy_id=str(payload["promotion_policy_id"]),
        eligibility_assessment_id=str(payload["eligibility_assessment_id"]),
        registered_at_ns=int(payload["registered_at_ns"]),
        minimum_shadow_samples=int(payload["minimum_shadow_samples"]),
        minimum_shadow_duration_ns=int(payload["minimum_shadow_duration_ns"]),
        shadow_window_start_ns=payload.get("shadow_window_start_ns"),
        shadow_window_end_ns=payload.get("shadow_window_end_ns"),
        lifecycle_state=ChallengerLifecycleState(str(payload.get("lifecycle_state", ChallengerLifecycleState.REGISTERED.value))),
        metadata=dict(payload.get("metadata", {})),
    )


def _shadow_obs_to_dict(obs: ShadowMatchedObservation) -> dict[str, Any]:
    return {
        "opportunity_key": obs.opportunity_key,
        "decision_time_ns": obs.decision_time_ns,
        "champion_forecast_id": obs.champion_forecast_id,
        "challenger_forecast_id": obs.challenger_forecast_id,
        "outcome_id": obs.outcome_id,
        "settled": obs.settled,
        "champion_probability": obs.champion_probability,
        "challenger_probability": obs.challenger_probability,
        "binary_label": obs.binary_label,
    }


def _shadow_obs_from_dict(payload: dict[str, Any]) -> ShadowMatchedObservation:
    return ShadowMatchedObservation(
        opportunity_key=str(payload["opportunity_key"]),
        decision_time_ns=int(payload["decision_time_ns"]),
        champion_forecast_id=str(payload["champion_forecast_id"]),
        challenger_forecast_id=str(payload["challenger_forecast_id"]),
        outcome_id=payload.get("outcome_id"),
        settled=bool(payload["settled"]),
        champion_probability=float(payload["champion_probability"]),
        challenger_probability=float(payload["challenger_probability"]),
        binary_label=payload.get("binary_label"),
    )


def shadow_evidence_manifest_v1_to_dict(manifest: ShadowEvidenceManifestV1) -> dict[str, Any]:
    return {
        "schema_version": manifest.schema_version,
        "shadow_evidence_id": manifest.shadow_evidence_id,
        "challenger_registration_id": manifest.challenger_registration_id,
        "champion_assignment_id": manifest.champion_assignment_id,
        "promotion_policy_id": manifest.promotion_policy_id,
        "evidence_tier": manifest.evidence_tier.value,
        "decision_start_ns": manifest.decision_start_ns,
        "decision_end_ns": manifest.decision_end_ns,
        "matched_observations": [_shadow_obs_to_dict(o) for o in manifest.matched_observations],
        "unmatched_champion_count": manifest.unmatched_champion_count,
        "unmatched_challenger_count": manifest.unmatched_challenger_count,
        "sample_count": manifest.sample_count,
        "duration_ns": manifest.duration_ns,
        "settlement_complete": manifest.settlement_complete,
        "evaluation_report_ids": list(manifest.evaluation_report_ids),
        "implementation_version": manifest.implementation_version,
        "metadata": dict(manifest.metadata),
    }


def shadow_evidence_manifest_v1_from_dict(payload: dict[str, Any]) -> ShadowEvidenceManifestV1:
    return ShadowEvidenceManifestV1(
        shadow_evidence_id=str(payload["shadow_evidence_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        challenger_registration_id=str(payload["challenger_registration_id"]),
        champion_assignment_id=str(payload["champion_assignment_id"]),
        promotion_policy_id=str(payload["promotion_policy_id"]),
        evidence_tier=EvidenceTier(str(payload["evidence_tier"])),
        decision_start_ns=int(payload["decision_start_ns"]),
        decision_end_ns=int(payload["decision_end_ns"]),
        matched_observations=tuple(_shadow_obs_from_dict(o) for o in payload["matched_observations"]),
        unmatched_champion_count=int(payload.get("unmatched_champion_count", 0)),
        unmatched_challenger_count=int(payload.get("unmatched_challenger_count", 0)),
        sample_count=int(payload["sample_count"]),
        duration_ns=int(payload["duration_ns"]),
        settlement_complete=bool(payload["settlement_complete"]),
        evaluation_report_ids=tuple(str(v) for v in payload.get("evaluation_report_ids", [])),
        implementation_version=str(payload.get("implementation_version", "")),
        metadata=dict(payload.get("metadata", {})),
    )


def _metric_gate_to_dict(result: MetricGateResult) -> dict[str, Any]:
    return {
        "metric_name": result.metric_name,
        "direction": result.direction.value,
        "champion_value": result.champion_value,
        "challenger_value": result.challenger_value,
        "delta": result.delta,
        "required_improvement": result.required_improvement,
        "passed": result.passed,
    }


def _metric_gate_from_dict(payload: dict[str, Any]) -> MetricGateResult:
    return MetricGateResult(
        metric_name=str(payload["metric_name"]),
        direction=MetricDirection(str(payload["direction"])),
        champion_value=payload.get("champion_value"),
        challenger_value=payload.get("challenger_value"),
        delta=payload.get("delta"),
        required_improvement=float(payload["required_improvement"]),
        passed=bool(payload["passed"]),
    )


def promotion_decision_v1_to_dict(decision: PromotionDecisionV1) -> dict[str, Any]:
    return {
        "schema_version": decision.schema_version,
        "promotion_decision_id": decision.promotion_decision_id,
        "promotion_policy_id": decision.promotion_policy_id,
        "champion_scope": _scope_to_dict(decision.champion_scope),
        "current_champion_assignment_id": decision.current_champion_assignment_id,
        "challenger_registration_id": decision.challenger_registration_id,
        "candidate_id": decision.candidate_id,
        "candidate_artifact_hash": decision.candidate_artifact_hash,
        "validation_report_ids": list(decision.validation_report_ids),
        "shadow_evidence_id": decision.shadow_evidence_id,
        "artifact_integrity_status": decision.artifact_integrity_status,
        "contamination_status": decision.contamination_status.value,
        "knowledge_status": decision.knowledge_status.value,
        "primary_metric_result": _metric_gate_to_dict(decision.primary_metric_result) if decision.primary_metric_result else None,
        "guardrail_results": [
            {
                "rule": _guardrail_to_dict(g.rule),
                "champion_value": g.champion_value,
                "challenger_value": g.challenger_value,
                "passed": g.passed,
            }
            for g in decision.guardrail_results
        ],
        "statistical_result": {
            "requirement": decision.statistical_result.requirement.value,
            "sample_count": decision.statistical_result.sample_count,
            "mean_delta": decision.statistical_result.mean_delta,
            "ci_lower": decision.statistical_result.ci_lower,
            "ci_upper": decision.statistical_result.ci_upper,
            "passed": decision.statistical_result.passed,
        }
        if decision.statistical_result
        else None,
        "complexity_result": {
            "champion_complexity": decision.complexity_result.champion_complexity.value,
            "challenger_complexity": decision.complexity_result.challenger_complexity.value,
            "required_improvement": decision.complexity_result.required_improvement,
            "actual_improvement": decision.complexity_result.actual_improvement,
            "passed": decision.complexity_result.passed,
        }
        if decision.complexity_result
        else None,
        "decision": decision.decision.value,
        "reason_codes": [code.value for code in decision.reason_codes],
        "implementation_version": decision.implementation_version,
        "metadata": dict(decision.metadata),
    }


def promotion_decision_v1_from_dict(payload: dict[str, Any]) -> PromotionDecisionV1:
    statistical = payload.get("statistical_result")
    complexity = payload.get("complexity_result")
    return PromotionDecisionV1(
        promotion_decision_id=str(payload["promotion_decision_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        promotion_policy_id=str(payload["promotion_policy_id"]),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        current_champion_assignment_id=str(payload["current_champion_assignment_id"]),
        challenger_registration_id=str(payload["challenger_registration_id"]),
        candidate_id=str(payload["candidate_id"]),
        candidate_artifact_hash=str(payload["candidate_artifact_hash"]),
        validation_report_ids=tuple(str(v) for v in payload["validation_report_ids"]),
        shadow_evidence_id=payload.get("shadow_evidence_id"),
        artifact_integrity_status=bool(payload.get("artifact_integrity_status", False)),
        contamination_status=ContaminationDisposition(str(payload["contamination_status"])),
        knowledge_status=KnowledgeAssessmentStatus(str(payload["knowledge_status"])),
        primary_metric_result=_metric_gate_from_dict(payload["primary_metric_result"]) if payload.get("primary_metric_result") else None,
        guardrail_results=tuple(
            GuardrailGateResult(
                rule=_guardrail_from_dict(g["rule"]),
                champion_value=g.get("champion_value"),
                challenger_value=g.get("challenger_value"),
                passed=g.get("passed"),
            )
            for g in payload.get("guardrail_results", [])
        ),
        statistical_result=StatisticalGateResult(
            requirement=StatisticalRequirementKind(str(statistical["requirement"])),
            sample_count=int(statistical["sample_count"]),
            mean_delta=statistical.get("mean_delta"),
            ci_lower=statistical.get("ci_lower"),
            ci_upper=statistical.get("ci_upper"),
            passed=statistical.get("passed"),
        )
        if statistical
        else None,
        complexity_result=ComplexityGateResult(
            champion_complexity=ComplexityBudget(str(complexity["champion_complexity"])),
            challenger_complexity=ComplexityBudget(str(complexity["challenger_complexity"])),
            required_improvement=float(complexity["required_improvement"]),
            actual_improvement=complexity.get("actual_improvement"),
            passed=complexity.get("passed"),
        )
        if complexity
        else None,
        decision=PromotionDecisionKind(str(payload["decision"])),
        reason_codes=tuple(PromotionReasonCode(v) for v in payload.get("reason_codes", [])),
        implementation_version=str(payload.get("implementation_version", "")),
        metadata=dict(payload.get("metadata", {})),
    )


def champion_assignment_v1_to_dict(assignment: ChampionAssignmentV1) -> dict[str, Any]:
    return {
        "schema_version": assignment.schema_version,
        "assignment_id": assignment.assignment_id,
        "champion_scope": _scope_to_dict(assignment.champion_scope),
        "candidate_id": assignment.candidate_id,
        "candidate_artifact_hash": assignment.candidate_artifact_hash,
        "promotion_decision_id": assignment.promotion_decision_id,
        "previous_assignment_id": assignment.previous_assignment_id,
        "effective_from_ns": assignment.effective_from_ns,
        "assignment_reason": assignment.assignment_reason.value,
        "status": assignment.status.value,
        "metadata": dict(assignment.metadata),
    }


def champion_assignment_v1_from_dict(payload: dict[str, Any]) -> ChampionAssignmentV1:
    return ChampionAssignmentV1(
        assignment_id=str(payload["assignment_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        champion_scope=_scope_from_dict(payload["champion_scope"]),
        candidate_id=str(payload["candidate_id"]),
        candidate_artifact_hash=str(payload["candidate_artifact_hash"]),
        promotion_decision_id=payload.get("promotion_decision_id"),
        previous_assignment_id=payload.get("previous_assignment_id"),
        effective_from_ns=int(payload["effective_from_ns"]),
        assignment_reason=ChampionAssignmentReason(str(payload["assignment_reason"])),
        status=ChampionAssignmentStatus(str(payload.get("status", ChampionAssignmentStatus.ACTIVE.value))),
        metadata=dict(payload.get("metadata", {})),
    )


def challenger_lifecycle_event_v1_to_dict(event: ChallengerLifecycleEventV1) -> dict[str, Any]:
    return {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "challenger_registration_id": event.challenger_registration_id,
        "from_state": event.from_state.value if event.from_state else None,
        "to_state": event.to_state.value,
        "effective_at_ns": event.effective_at_ns,
        "reason_code": event.reason_code.value if event.reason_code else None,
        "metadata": dict(event.metadata),
    }


def challenger_lifecycle_event_v1_from_dict(payload: dict[str, Any]) -> ChallengerLifecycleEventV1:
    return ChallengerLifecycleEventV1(
        event_id=str(payload["event_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        challenger_registration_id=str(payload["challenger_registration_id"]),
        from_state=ChallengerLifecycleState(payload["from_state"]) if payload.get("from_state") else None,
        to_state=ChallengerLifecycleState(str(payload["to_state"])),
        effective_at_ns=int(payload["effective_at_ns"]),
        reason_code=PromotionReasonCode(payload["reason_code"]) if payload.get("reason_code") else None,
        metadata=dict(payload.get("metadata", {})),
    )


__all__ = [
    "challenger_lifecycle_event_v1_from_dict",
    "challenger_lifecycle_event_v1_to_dict",
    "challenger_registration_v1_from_dict",
    "challenger_registration_v1_to_dict",
    "champion_assignment_v1_from_dict",
    "champion_assignment_v1_to_dict",
    "promotion_decision_v1_from_dict",
    "promotion_decision_v1_to_dict",
    "promotion_eligibility_assessment_v1_from_dict",
    "promotion_eligibility_assessment_v1_to_dict",
    "promotion_policy_v1_from_dict",
    "promotion_policy_v1_to_dict",
    "shadow_evidence_manifest_v1_from_dict",
    "shadow_evidence_manifest_v1_to_dict",
]
