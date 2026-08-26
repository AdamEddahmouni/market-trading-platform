"""Serialization for BUILD 19 validation artifacts."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from .types import (
    ContaminationDisposition,
    ContaminationRecordV1,
    ContaminationType,
    FoldMetricResult,
    HoldoutCommitmentV1,
    HoldoutMetricResult,
    HoldoutSpec,
    HoldoutUnlockReceiptV1,
    KnowledgeAssessmentStatus,
    KnowledgeCutoffState,
    KnowledgeProfileV1,
    NetworkPolicy,
    PairedMetricDelta,
    StatisticalPlan,
    TemporalKnowledgePolicyV1,
    ToolPolicyClass,
    ValidationDisposition,
    ValidationPlanV1,
    ValidationReportV1,
    WalkForwardMode,
    WalkForwardSpec,
)


def _holdout_spec_to_dict(spec: HoldoutSpec) -> dict[str, Any]:
    return {
        "holdout_start_ns": spec.holdout_start_ns,
        "holdout_end_ns": spec.holdout_end_ns,
        "selector_ref": spec.selector_ref,
    }


def _holdout_spec_from_dict(payload: dict[str, Any]) -> HoldoutSpec:
    return HoldoutSpec(
        holdout_start_ns=int(payload["holdout_start_ns"]),
        holdout_end_ns=int(payload["holdout_end_ns"]),
        selector_ref=payload.get("selector_ref"),
    )


def _statistical_plan_to_dict(plan: StatisticalPlan) -> dict[str, Any]:
    return {
        "block_length": plan.block_length,
        "replicate_count": plan.replicate_count,
        "seed": plan.seed,
        "confidence_level": plan.confidence_level,
        "minimum_paired_sample": plan.minimum_paired_sample,
        "criterion_upper_ci_bound_lt_zero": plan.criterion_upper_ci_bound_lt_zero,
    }


def _statistical_plan_from_dict(payload: dict[str, Any]) -> StatisticalPlan:
    return StatisticalPlan(
        block_length=int(payload["block_length"]),
        replicate_count=int(payload["replicate_count"]),
        seed=int(payload["seed"]),
        confidence_level=float(payload["confidence_level"]),
        minimum_paired_sample=int(payload["minimum_paired_sample"]),
        criterion_upper_ci_bound_lt_zero=bool(
            payload.get("criterion_upper_ci_bound_lt_zero", False)
        ),
    )


def _walk_forward_to_dict(spec: WalkForwardSpec | None) -> dict[str, Any] | None:
    if spec is None:
        return None
    return {
        "mode": spec.mode.value,
        "fold_boundaries_ns": list(spec.fold_boundaries_ns),
        "fold_candidate_ids": list(spec.fold_candidate_ids),
    }


def _walk_forward_from_dict(payload: dict[str, Any] | None) -> WalkForwardSpec | None:
    if payload is None:
        return None
    return WalkForwardSpec(
        mode=WalkForwardMode(str(payload["mode"])),
        fold_boundaries_ns=tuple(int(v) for v in payload["fold_boundaries_ns"]),
        fold_candidate_ids=tuple(payload.get("fold_candidate_ids", ())),
    )


def _knowledge_policy_to_dict(policy: TemporalKnowledgePolicyV1) -> dict[str, Any]:
    return {
        "policy_id": policy.policy_id,
        "schema_version": policy.schema_version,
        "network_policy": policy.network_policy.value,
        "require_declared_model_cutoff": policy.require_declared_model_cutoff,
        "reject_prompt_only_time_travel": policy.reject_prompt_only_time_travel,
        "allow_synthetic_test_teachers": policy.allow_synthetic_test_teachers,
        "metadata": dict(policy.metadata),
    }


def _knowledge_policy_from_dict(payload: dict[str, Any]) -> TemporalKnowledgePolicyV1:
    return TemporalKnowledgePolicyV1(
        policy_id=str(payload["policy_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        network_policy=NetworkPolicy(str(payload.get("network_policy", NetworkPolicy.DENIED.value))),
        require_declared_model_cutoff=bool(payload.get("require_declared_model_cutoff", True)),
        reject_prompt_only_time_travel=bool(payload.get("reject_prompt_only_time_travel", True)),
        allow_synthetic_test_teachers=bool(payload.get("allow_synthetic_test_teachers", True)),
        metadata=dict(payload.get("metadata", {})),
    )


def validation_plan_v1_to_dict(plan: ValidationPlanV1) -> dict[str, Any]:
    return {
        "validation_plan_id": plan.validation_plan_id,
        "schema_version": plan.schema_version,
        "experiment_id": plan.experiment_id,
        "candidate_ids": list(plan.candidate_ids),
        "candidate_artifact_hashes": list(plan.candidate_artifact_hashes),
        "control_ref": plan.control_ref,
        "target_kind": plan.target_kind,
        "horizon_ns": plan.horizon_ns,
        "mode": plan.mode,
        "scenario_id": plan.scenario_id,
        "validation_method": plan.validation_method,
        "walk_forward_spec": _walk_forward_to_dict(plan.walk_forward_spec),
        "purge_ns": plan.purge_ns,
        "embargo_ns": plan.embargo_ns,
        "holdout_spec": _holdout_spec_to_dict(plan.holdout_spec),
        "primary_metric": plan.primary_metric,
        "guardrail_metrics": list(plan.guardrail_metrics),
        "statistical_plan": _statistical_plan_to_dict(plan.statistical_plan),
        "temporal_knowledge_policy": _knowledge_policy_to_dict(plan.temporal_knowledge_policy),
        "minimum_paired_sample": plan.minimum_paired_sample,
        "implementation_version": plan.implementation_version,
        "metadata": dict(plan.metadata),
    }


def validation_plan_v1_from_dict(payload: dict[str, Any]) -> ValidationPlanV1:
    return ValidationPlanV1(
        validation_plan_id=str(payload["validation_plan_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        experiment_id=str(payload["experiment_id"]),
        candidate_ids=tuple(str(v) for v in payload["candidate_ids"]),
        candidate_artifact_hashes=tuple(str(v) for v in payload["candidate_artifact_hashes"]),
        control_ref=str(payload["control_ref"]),
        target_kind=str(payload["target_kind"]),
        horizon_ns=int(payload["horizon_ns"]),
        mode=str(payload["mode"]),
        scenario_id=payload.get("scenario_id"),
        validation_method=str(payload["validation_method"]),
        walk_forward_spec=_walk_forward_from_dict(payload.get("walk_forward_spec")),
        purge_ns=int(payload.get("purge_ns", 0)),
        embargo_ns=int(payload.get("embargo_ns", 0)),
        holdout_spec=_holdout_spec_from_dict(payload["holdout_spec"]),
        primary_metric=str(payload["primary_metric"]),
        guardrail_metrics=tuple(str(v) for v in payload.get("guardrail_metrics", ())),
        statistical_plan=_statistical_plan_from_dict(payload["statistical_plan"]),
        temporal_knowledge_policy=_knowledge_policy_from_dict(payload["temporal_knowledge_policy"]),
        minimum_paired_sample=int(payload.get("minimum_paired_sample", 5)),
        implementation_version=str(payload.get("implementation_version", "independent-validation-temporal-firewall-v1")),
        metadata=dict(payload.get("metadata", {})),
    )


def holdout_commitment_v1_to_dict(commitment: HoldoutCommitmentV1) -> dict[str, Any]:
    return {
        "holdout_commitment_id": commitment.holdout_commitment_id,
        "schema_version": commitment.schema_version,
        "validation_plan_id": commitment.validation_plan_id,
        "experiment_id": commitment.experiment_id,
        "candidate_ids": list(commitment.candidate_ids),
        "candidate_artifact_hashes": list(commitment.candidate_artifact_hashes),
        "control_ref": commitment.control_ref,
        "holdout_spec": _holdout_spec_to_dict(commitment.holdout_spec),
        "primary_metric": commitment.primary_metric,
        "guardrail_metrics": list(commitment.guardrail_metrics),
        "statistical_plan": _statistical_plan_to_dict(commitment.statistical_plan),
        "temporal_knowledge_policy_id": commitment.temporal_knowledge_policy_id,
        "implementation_version": commitment.implementation_version,
        "metadata": dict(commitment.metadata),
    }


def holdout_commitment_v1_from_dict(payload: dict[str, Any]) -> HoldoutCommitmentV1:
    return HoldoutCommitmentV1(
        holdout_commitment_id=str(payload["holdout_commitment_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        validation_plan_id=str(payload["validation_plan_id"]),
        experiment_id=str(payload["experiment_id"]),
        candidate_ids=tuple(str(v) for v in payload["candidate_ids"]),
        candidate_artifact_hashes=tuple(str(v) for v in payload["candidate_artifact_hashes"]),
        control_ref=str(payload["control_ref"]),
        holdout_spec=_holdout_spec_from_dict(payload["holdout_spec"]),
        primary_metric=str(payload["primary_metric"]),
        guardrail_metrics=tuple(str(v) for v in payload.get("guardrail_metrics", ())),
        statistical_plan=_statistical_plan_from_dict(payload["statistical_plan"]),
        temporal_knowledge_policy_id=str(payload["temporal_knowledge_policy_id"]),
        implementation_version=str(payload.get("implementation_version", "independent-validation-temporal-firewall-v1")),
        metadata=dict(payload.get("metadata", {})),
    )


def holdout_unlock_receipt_v1_to_dict(receipt: HoldoutUnlockReceiptV1) -> dict[str, Any]:
    return {
        "receipt_id": receipt.receipt_id,
        "schema_version": receipt.schema_version,
        "holdout_commitment_id": receipt.holdout_commitment_id,
        "validation_plan_id": receipt.validation_plan_id,
        "candidate_ids": list(receipt.candidate_ids),
        "unlocked_at_ns": receipt.unlocked_at_ns,
        "context": receipt.context,
        "metadata": dict(receipt.metadata),
    }


def holdout_unlock_receipt_v1_from_dict(payload: dict[str, Any]) -> HoldoutUnlockReceiptV1:
    return HoldoutUnlockReceiptV1(
        receipt_id=str(payload["receipt_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        holdout_commitment_id=str(payload["holdout_commitment_id"]),
        validation_plan_id=str(payload["validation_plan_id"]),
        candidate_ids=tuple(str(v) for v in payload["candidate_ids"]),
        unlocked_at_ns=int(payload["unlocked_at_ns"]),
        context=str(payload["context"]),
        metadata=dict(payload.get("metadata", {})),
    )


def contamination_record_v1_to_dict(record: ContaminationRecordV1) -> dict[str, Any]:
    return {
        "contamination_record_id": record.contamination_record_id,
        "schema_version": record.schema_version,
        "experiment_id": record.experiment_id,
        "validation_plan_id": record.validation_plan_id,
        "holdout_commitment_id": record.holdout_commitment_id,
        "contamination_type": record.contamination_type.value,
        "disposition": record.disposition.value,
        "source_ref": record.source_ref,
        "affected_decision_start_ns": record.affected_decision_start_ns,
        "affected_decision_end_ns": record.affected_decision_end_ns,
        "affected_artifact_refs": list(record.affected_artifact_refs),
        "detected_context": record.detected_context,
        "severity": record.severity,
        "metadata": dict(record.metadata),
    }


def contamination_record_v1_from_dict(payload: dict[str, Any]) -> ContaminationRecordV1:
    return ContaminationRecordV1(
        contamination_record_id=str(payload["contamination_record_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        experiment_id=str(payload["experiment_id"]),
        validation_plan_id=str(payload["validation_plan_id"]),
        holdout_commitment_id=payload.get("holdout_commitment_id"),
        contamination_type=ContaminationType(str(payload["contamination_type"])),
        disposition=ContaminationDisposition(str(payload["disposition"])),
        source_ref=payload.get("source_ref"),
        affected_decision_start_ns=payload.get("affected_decision_start_ns"),
        affected_decision_end_ns=payload.get("affected_decision_end_ns"),
        affected_artifact_refs=tuple(str(v) for v in payload.get("affected_artifact_refs", ())),
        detected_context=str(payload.get("detected_context", "")),
        severity=str(payload.get("severity", "HIGH")),
        metadata=dict(payload.get("metadata", {})),
    )


def _paired_delta_to_dict(delta: PairedMetricDelta | None) -> dict[str, Any] | None:
    if delta is None:
        return None
    return {
        "metric_name": delta.metric_name,
        "mean_delta": delta.mean_delta,
        "sample_count": delta.sample_count,
        "ci_lower": delta.ci_lower,
        "ci_upper": delta.ci_upper,
        "block_length": delta.block_length,
        "replicate_count": delta.replicate_count,
        "seed": delta.seed,
    }


def _paired_delta_from_dict(payload: dict[str, Any] | None) -> PairedMetricDelta | None:
    if payload is None:
        return None
    return PairedMetricDelta(
        metric_name=str(payload["metric_name"]),
        mean_delta=float(payload["mean_delta"]),
        sample_count=int(payload["sample_count"]),
        ci_lower=payload.get("ci_lower"),
        ci_upper=payload.get("ci_upper"),
        block_length=payload.get("block_length"),
        replicate_count=payload.get("replicate_count"),
        seed=payload.get("seed"),
    )


def validation_report_v1_to_dict(report: ValidationReportV1) -> dict[str, Any]:
    return {
        "validation_report_id": report.validation_report_id,
        "schema_version": report.schema_version,
        "validation_plan_id": report.validation_plan_id,
        "experiment_id": report.experiment_id,
        "candidate_ids": list(report.candidate_ids),
        "candidate_artifact_hashes": list(report.candidate_artifact_hashes),
        "control_ref": report.control_ref,
        "holdout_commitment_id": report.holdout_commitment_id,
        "fold_results": [
            {
                "fold_id": fr.fold_id,
                "candidate_id": fr.candidate_id,
                "control_ref": fr.control_ref,
                "matched_count": fr.matched_count,
                "candidate_primary_metric": fr.candidate_primary_metric,
                "control_primary_metric": fr.control_primary_metric,
                "primary_delta": fr.primary_delta,
                "guardrail_results": dict(fr.guardrail_results),
                "knowledge_assessment_status": fr.knowledge_assessment_status.value,
                "contamination_disposition": fr.contamination_disposition.value,
                "disposition": fr.disposition.value,
            }
            for fr in report.fold_results
        ],
        "holdout_results": [
            {
                "candidate_id": hr.candidate_id,
                "control_ref": hr.control_ref,
                "matched_count": hr.matched_count,
                "candidate_metrics": dict(hr.candidate_metrics),
                "control_metrics": dict(hr.control_metrics),
                "primary_delta": hr.primary_delta,
                "paired_delta": _paired_delta_to_dict(hr.paired_delta),
                "guardrail_results": dict(hr.guardrail_results),
                "knowledge_assessment_status": hr.knowledge_assessment_status.value,
                "contamination_disposition": hr.contamination_disposition.value,
                "disposition": hr.disposition.value,
                "coverage_notes": list(hr.coverage_notes),
            }
            for hr in report.holdout_results
        ],
        "contamination_disposition": report.contamination_disposition.value,
        "contamination_record_ids": list(report.contamination_record_ids),
        "knowledge_assessment_status": report.knowledge_assessment_status.value,
        "candidate_family_size": report.candidate_family_size,
        "final_disposition": report.final_disposition.value,
        "limitations": list(report.limitations),
        "implementation_version": report.implementation_version,
        "metadata": dict(report.metadata),
    }


def validation_report_v1_from_dict(payload: dict[str, Any]) -> ValidationReportV1:
    fold_results = tuple(
        FoldMetricResult(
            fold_id=str(fr["fold_id"]),
            candidate_id=str(fr["candidate_id"]),
            control_ref=str(fr["control_ref"]),
            matched_count=int(fr["matched_count"]),
            candidate_primary_metric=fr.get("candidate_primary_metric"),
            control_primary_metric=fr.get("control_primary_metric"),
            primary_delta=fr.get("primary_delta"),
            guardrail_results=dict(fr.get("guardrail_results", {})),
            knowledge_assessment_status=KnowledgeAssessmentStatus(
                str(fr["knowledge_assessment_status"])
            ),
            contamination_disposition=ContaminationDisposition(
                str(fr["contamination_disposition"])
            ),
            disposition=ValidationDisposition(str(fr["disposition"])),
        )
        for fr in payload.get("fold_results", [])
    )
    holdout_results = tuple(
        HoldoutMetricResult(
            candidate_id=str(hr["candidate_id"]),
            control_ref=str(hr["control_ref"]),
            matched_count=int(hr["matched_count"]),
            candidate_metrics=dict(hr.get("candidate_metrics", {})),
            control_metrics=dict(hr.get("control_metrics", {})),
            primary_delta=hr.get("primary_delta"),
            paired_delta=_paired_delta_from_dict(hr.get("paired_delta")),
            guardrail_results=dict(hr.get("guardrail_results", {})),
            knowledge_assessment_status=KnowledgeAssessmentStatus(
                str(hr["knowledge_assessment_status"])
            ),
            contamination_disposition=ContaminationDisposition(
                str(hr["contamination_disposition"])
            ),
            disposition=ValidationDisposition(str(hr["disposition"])),
            coverage_notes=tuple(hr.get("coverage_notes", ())),
        )
        for hr in payload.get("holdout_results", [])
    )
    return ValidationReportV1(
        validation_report_id=str(payload["validation_report_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        validation_plan_id=str(payload["validation_plan_id"]),
        experiment_id=str(payload["experiment_id"]),
        candidate_ids=tuple(str(v) for v in payload["candidate_ids"]),
        candidate_artifact_hashes=tuple(str(v) for v in payload["candidate_artifact_hashes"]),
        control_ref=str(payload["control_ref"]),
        holdout_commitment_id=str(payload["holdout_commitment_id"]),
        fold_results=fold_results,
        holdout_results=holdout_results,
        contamination_disposition=ContaminationDisposition(
            str(payload["contamination_disposition"])
        ),
        contamination_record_ids=tuple(str(v) for v in payload.get("contamination_record_ids", ())),
        knowledge_assessment_status=KnowledgeAssessmentStatus(
            str(payload["knowledge_assessment_status"])
        ),
        candidate_family_size=int(payload["candidate_family_size"]),
        final_disposition=ValidationDisposition(str(payload["final_disposition"])),
        limitations=tuple(payload.get("limitations", ())),
        implementation_version=str(payload.get("implementation_version", "independent-validation-temporal-firewall-v1")),
        metadata=dict(payload.get("metadata", {})),
    )


__all__ = [
    "contamination_record_v1_from_dict",
    "contamination_record_v1_to_dict",
    "holdout_commitment_v1_from_dict",
    "holdout_commitment_v1_to_dict",
    "holdout_unlock_receipt_v1_from_dict",
    "holdout_unlock_receipt_v1_to_dict",
    "validation_plan_v1_from_dict",
    "validation_plan_v1_to_dict",
    "validation_report_v1_from_dict",
    "validation_report_v1_to_dict",
]
