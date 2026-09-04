"""Deterministic operational reliability identities (BUILD 32)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import (
    AlertDeliveryReceiptV1,
    AlertPolicyV1,
    AlertV1,
    BackupManifestV1,
    DisasterRecoveryDrillReportV1,
    OperationalHealthMatrixV1,
    OperationalReliabilityQualificationReportV1,
    OperationalSLOAssessmentV1,
    OperationalSLOPolicyV1,
    PersistenceHealthSnapshotV1,
    RecoveryPlanV1,
    SoakQualificationReportV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def derive_slo_policy_id(policy: OperationalSLOPolicyV1) -> str:
    payload = {
        "scope": policy.scope,
        "measurement_window_ns": policy.measurement_window_ns,
        "evaluation_cadence_ns": policy.evaluation_cadence_ns,
        "minimum_sample": policy.minimum_sample,
        "missing_data_semantics": policy.missing_data_semantics,
        "objectives": [
            {
                "objective_id": obj.objective_id,
                "warning_threshold": obj.warning_threshold,
                "critical_threshold": obj.critical_threshold,
                "safety_critical": obj.safety_critical,
                "missing_data_semantics": obj.missing_data_semantics,
            }
            for obj in policy.objectives
        ],
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("SLOPOL", payload)


def derive_slo_assessment_id(assessment: OperationalSLOAssessmentV1) -> str:
    payload = {
        "policy_ref": assessment.policy_ref,
        "window_start_ns": assessment.window_start_ns,
        "window_end_ns": assessment.window_end_ns,
        "overall_status": assessment.overall_status,
    }
    return _sha256_prefix("SLOASM", payload)


def derive_alert_policy_id(policy: AlertPolicyV1) -> str:
    payload = {
        "source_assessment_types": list(policy.source_assessment_types),
        "dedup_window_ns": policy.dedup_window_ns,
        "cooldown_ns": policy.cooldown_ns,
        "delivery_channels": list(policy.delivery_channels),
        "critical_requires_delivery": policy.critical_requires_delivery,
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("ALTPOL", payload)


def derive_alert_id(alert: AlertV1) -> str:
    payload = {
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "scope": alert.scope,
        "raised_at_ns": alert.raised_at_ns,
        "dedup_key": alert.dedup_key,
    }
    return _sha256_prefix("ALERT", payload)


def derive_delivery_receipt_id(receipt: AlertDeliveryReceiptV1) -> str:
    payload = {
        "alert_ref": receipt.alert_ref,
        "channel": receipt.channel,
        "attempt_time_ns": receipt.attempt_time_ns,
        "result": receipt.result,
    }
    return _sha256_prefix("DLVREC", payload)


def derive_health_matrix_id(matrix: OperationalHealthMatrixV1) -> str:
    payload = {
        "as_of_ns": matrix.as_of_ns,
        "observability_state": matrix.observability_state,
        "component_count": len(matrix.entries),
    }
    return _sha256_prefix("HLTHMX", payload)


def derive_persistence_health_id(snapshot: PersistenceHealthSnapshotV1) -> str:
    payload = {
        "as_of_ns": snapshot.as_of_ns,
        "backend": snapshot.backend,
        "disposition": snapshot.disposition,
        "blocking_live": snapshot.blocking_live,
    }
    return _sha256_prefix("PERSHP", payload)


def derive_backup_manifest_id(manifest: BackupManifestV1) -> str:
    payload = {
        "created_at_ns": manifest.created_at_ns,
        "source_head": manifest.source_head,
        "included_stores": list(manifest.included_stores),
        "integrity_status": manifest.integrity_status,
    }
    return _sha256_prefix("BKPMAN", payload)


def derive_recovery_plan_id(plan: RecoveryPlanV1) -> str:
    payload = {
        "failure_scenario": plan.failure_scenario,
        "restore_order": list(plan.restore_order),
        "startup_mode": plan.startup_mode,
        "implementation_version": plan.implementation_version,
    }
    return _sha256_prefix("RCVPLN", payload)


def derive_drill_report_id(report: DisasterRecoveryDrillReportV1) -> str:
    payload = {
        "drill_spec_ref": report.drill_spec_ref,
        "result": report.result,
        "real_broker_submits": report.real_broker_submits,
    }
    return _sha256_prefix("DRDRPT", payload)


def derive_soak_report_id(report: SoakQualificationReportV1) -> str:
    payload = {
        "spec_ref": report.spec_ref,
        "actual_duration_ns": report.actual_duration_ns,
        "disposition": report.disposition,
    }
    return _sha256_prefix("SOAKRP", payload)


def derive_qualification_report_id(report: OperationalReliabilityQualificationReportV1) -> str:
    payload = {
        "build31_source_ref": report.build31_source_ref,
        "disposition": report.disposition,
    }
    return _sha256_prefix("OPRELQ", payload)
