"""Deterministic EVIDENCE-01 identities."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import (
    FORWARD_EVIDENCE_QUALIFICATION_IMPLEMENTATION_VERSION,
    ForwardEvidenceQualificationAssessmentV1,
    ForwardEvidenceQualificationPolicyV1,
    ForwardEvidenceQualificationReportV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def policy_identity_payload(policy: ForwardEvidenceQualificationPolicyV1) -> dict[str, Any]:
    return {
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
    }


def derive_forward_evidence_policy_id(policy: ForwardEvidenceQualificationPolicyV1) -> str:
    return _sha256_prefix("FEPOL", policy_identity_payload(policy))


def derive_source_evidence_fingerprint(
    *,
    receipt_ids: tuple[str, ...],
    observation_cutoff_ns: int,
    settlement_cutoff_ns: int,
) -> str:
    payload = {
        "receipt_ids": list(receipt_ids),
        "observation_cutoff_ns": observation_cutoff_ns,
        "settlement_cutoff_ns": settlement_cutoff_ns,
    }
    return _sha256_prefix("FESRC", payload)


def derive_forward_evidence_assessment_id(
    *,
    policy_id: str,
    source_evidence_fingerprint: str,
    observation_cutoff_ns: int,
    settlement_cutoff_ns: int,
    implementation_version: str,
) -> str:
    payload = {
        "policy_id": policy_id,
        "source_evidence_fingerprint": source_evidence_fingerprint,
        "observation_cutoff_ns": observation_cutoff_ns,
        "settlement_cutoff_ns": settlement_cutoff_ns,
        "implementation_version": implementation_version,
    }
    return _sha256_prefix("FEASM", payload)


def derive_forward_evidence_report_id(
    *,
    policy_id: str,
    assessment_id: str,
    build26_historical_report_ref: str,
    implementation_version: str,
) -> str:
    payload = {
        "policy_id": policy_id,
        "assessment_id": assessment_id,
        "build26_historical_report_ref": build26_historical_report_ref,
        "implementation_version": implementation_version,
    }
    return _sha256_prefix("FEREP", payload)


def assessment_identity_payload(assessment: ForwardEvidenceQualificationAssessmentV1) -> dict[str, Any]:
    return {
        "policy_ref": assessment.policy_ref,
        "observation_cutoff_ns": assessment.observation_cutoff_ns,
        "settlement_cutoff_ns": assessment.settlement_cutoff_ns,
        "source_evidence_fingerprint": assessment.source_evidence_fingerprint,
        "qualification_disposition": assessment.qualification_disposition.value,
        "disposition_reason_codes": list(assessment.disposition_reason_codes),
        "implementation_version": assessment.implementation_version,
    }


def report_identity_payload(report: ForwardEvidenceQualificationReportV1) -> dict[str, Any]:
    return {
        "policy_ref": report.policy_ref,
        "assessment_ref": report.assessment_ref,
        "build26_historical_disposition": report.build26_historical_disposition,
        "build26_historical_report_ref": report.build26_historical_report_ref,
        "evidence01_disposition": report.evidence01_disposition.value,
        "limitation_status": report.limitation_status,
        "implementation_version": report.implementation_version,
    }
