"""Forward qualification serialization (BUILD 26)."""

from __future__ import annotations

from typing import Any

from .types import (
    EvidenceClass,
    ForwardIntegrityStatus,
    ForwardPredictionReceiptV1,
    ForwardQualificationReportV1,
    ForwardQualificationRunV1,
    ForwardQualificationSpecV1,
    ProviderCapabilityEntryV1,
)


def provider_capability_entry_v1_to_dict(entry: ProviderCapabilityEntryV1) -> dict[str, Any]:
    return entry.to_dict()


def forward_qualification_spec_v1_to_dict(spec: ForwardQualificationSpecV1) -> dict[str, Any]:
    return {
        "qualification_spec_id": spec.qualification_spec_id,
        "schema_version": spec.schema_version,
        "release_candidate_ref": spec.release_candidate_ref,
        "source_head": spec.source_head,
        "contract_inventory_hash": spec.contract_inventory_hash,
        "qualification_kind": spec.qualification_kind.value,
        "allowed_providers": list(spec.allowed_providers),
        "instrument_universe": list(spec.instrument_universe),
        "target_kind": spec.target_kind,
        "horizon_ns": spec.horizon_ns,
        "champion_scope": spec.champion_scope,
        "qualification_start_ns": spec.qualification_start_ns,
        "qualification_end_ns": spec.qualification_end_ns,
        "minimum_prediction_count": spec.minimum_prediction_count,
        "minimum_labelable_count": spec.minimum_labelable_count,
        "minimum_duration_ns": spec.minimum_duration_ns,
        "required_quality_states": list(spec.required_quality_states),
        "control_set": list(spec.control_set),
        "execution_mode_requirement": spec.execution_mode_requirement,
        "execution_authority_requirement": spec.execution_authority_requirement,
        "implementation_version": spec.implementation_version,
        "metadata": dict(spec.metadata),
    }


def forward_qualification_run_v1_to_dict(run: ForwardQualificationRunV1) -> dict[str, Any]:
    return {
        "qualification_run_id": run.qualification_run_id,
        "schema_version": run.schema_version,
        "qualification_spec_ref": run.qualification_spec_ref,
        "release_candidate_ref": run.release_candidate_ref,
        "source_head": run.source_head,
        "runtime_activation_ref": run.runtime_activation_ref,
        "champion_assignment_ref": run.champion_assignment_ref,
        "provider_capability_snapshot": [
            provider_capability_entry_v1_to_dict(entry) for entry in run.provider_capability_snapshot
        ],
        "instrument_universe": list(run.instrument_universe),
        "run_start_ns": run.run_start_ns,
        "run_end_ns": run.run_end_ns,
        "data_mode": run.data_mode,
        "execution_mode": run.execution_mode,
        "execution_authority": run.execution_authority,
        "policy_stack_refs": list(run.policy_stack_refs),
        "implementation_version": run.implementation_version,
        "lineage": dict(run.lineage),
        "metadata": dict(run.metadata),
    }


def forward_prediction_receipt_v1_to_dict(receipt: ForwardPredictionReceiptV1) -> dict[str, Any]:
    return {
        "receipt_id": receipt.receipt_id,
        "schema_version": receipt.schema_version,
        "forecast_id": receipt.forecast_id,
        "ledger_entry_id": receipt.ledger_entry_id,
        "decision_time_ns": receipt.decision_time_ns,
        "target_time_ns": receipt.target_time_ns,
        "registered_at_ns": receipt.registered_at_ns,
        "recorded_at_ns": receipt.recorded_at_ns,
        "qualification_run_ref": receipt.qualification_run_ref,
        "evidence_class": receipt.evidence_class.value,
        "content_hash": receipt.content_hash,
        "forward_integrity_status": receipt.forward_integrity_status.value,
        "integrity_failure_codes": list(receipt.integrity_failure_codes),
        "metadata": dict(receipt.metadata),
    }


def forward_qualification_report_v1_to_dict(report: ForwardQualificationReportV1) -> dict[str, Any]:
    return {
        "qualification_report_id": report.qualification_report_id,
        "schema_version": report.schema_version,
        "qualification_spec_ref": report.qualification_spec_ref,
        "qualification_run_ref": report.qualification_run_ref,
        "release_candidate_ref": report.release_candidate_ref,
        "evaluation_as_of_ns": report.evaluation_as_of_ns,
        "provider_capability_summary": dict(report.provider_capability_summary),
        "provider_health_summary": dict(report.provider_health_summary),
        "data_quality_summary": dict(report.data_quality_summary),
        "prediction_counts": dict(report.prediction_counts),
        "settlement_counts": dict(report.settlement_counts),
        "labelability_counts": dict(report.labelability_counts),
        "primary_forward_metrics": dict(report.primary_forward_metrics),
        "control_comparison": dict(report.control_comparison),
        "calibration_diagnostics": dict(report.calibration_diagnostics),
        "ood_diagnostics": dict(report.ood_diagnostics),
        "operational_errors": list(report.operational_errors),
        "runtime_incidents": list(report.runtime_incidents),
        "forward_integrity_status": report.forward_integrity_status.value,
        "forward_integrity_failures": list(report.forward_integrity_failures),
        "qualification_disposition": report.qualification_disposition.value,
        "disposition_reason_codes": list(report.disposition_reason_codes),
        "limitations": list(report.limitations),
        "lineage": dict(report.lineage),
        "implementation_version": report.implementation_version,
        "metadata": dict(report.metadata),
    }
