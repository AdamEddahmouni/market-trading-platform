"""Deterministic live canary identities (BUILD 29)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..live_execution_safety.identity import derive_account_fingerprint, derive_payload_hash
from ..live_execution_safety.types import LiveExecutionAuthorizationV1
from .types import (
    LIVE_CANARY_IMPLEMENTATION_VERSION,
    BrokerSubmissionReceiptV1,
    CanaryAuthorizationPreviewV1,
    HumanCanaryApprovalV1,
    LiveCanaryPolicyV1,
    LiveCanaryProgramPolicyV1,
    LiveCanaryProgramReportV1,
    LiveCanaryProgramRunV1,
    LiveCanaryQualificationReportV1,
    LiveCanaryRunV1,
    LiveCanarySessionReportV1,
    LiveExecutionIncidentV1,
    LiveFillReceiptV1,
    LiveIncidentResponsePolicyV1,
    LiveOperationalResumeApprovalV1,
    LiveOrderConfirmationV1,
    LivePortfolioSnapshotV1,
    LiveReconciliationCheckpointV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def derive_canary_policy_id(policy: LiveCanaryPolicyV1) -> str:
    payload = {
        "broker": policy.broker,
        "account_ref": policy.account_ref,
        "allowed_instruments": list(policy.allowed_instruments),
        "max_single_order_notional_minor": policy.max_single_order_notional_minor,
        "max_total_canary_notional_minor": policy.max_total_canary_notional_minor,
        "max_order_count": policy.max_order_count,
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("CANPOL", payload)


def derive_preview_id(preview: CanaryAuthorizationPreviewV1) -> str:
    payload = {
        "canary_policy_ref": preview.canary_policy_ref,
        "broker": preview.broker,
        "account_fingerprint": preview.account_fingerprint,
        "symbol_universe": list(preview.symbol_universe),
        "max_single_order_notional_minor": preview.max_single_order_notional_minor,
        "max_total_canary_notional_minor": preview.max_total_canary_notional_minor,
        "max_order_count": preview.max_order_count,
        "generated_at_ns": preview.generated_at_ns,
    }
    return _sha256_prefix("CANPREV", payload)


def derive_preview_hash(preview: CanaryAuthorizationPreviewV1) -> str:
    return derive_payload_hash(
        {
            "preview_id": preview.preview_id,
            "canary_policy_ref": preview.canary_policy_ref,
            "broker": preview.broker,
            "account_fingerprint": preview.account_fingerprint,
            "symbol_universe": list(preview.symbol_universe),
            "max_single_order_notional_minor": preview.max_single_order_notional_minor,
            "max_total_canary_notional_minor": preview.max_total_canary_notional_minor,
            "max_order_count": preview.max_order_count,
            "authorization_duration_ns": preview.authorization_duration_ns,
            "implementation_version": LIVE_CANARY_IMPLEMENTATION_VERSION,
        }
    )


def derive_human_approval_id(approval: HumanCanaryApprovalV1) -> str:
    payload = {
        "preview_id": approval.preview_id,
        "preview_hash": approval.preview_hash,
        "approved_at_ns": approval.approved_at_ns,
        "approved_by": approval.approved_by,
        "approval_source": approval.approval_source.value,
    }
    return _sha256_prefix("HUMANAP", payload)


def derive_canary_authorization_id(
    *,
    policy: LiveCanaryPolicyV1,
    preview_id: str,
    human_approval_id: str,
    effective_from_ns: int,
    effective_until_ns: int,
) -> str:
    payload = {
        "policy_id": policy.canary_policy_id,
        "preview_id": preview_id,
        "human_approval_id": human_approval_id,
        "broker": policy.broker,
        "account_ref": policy.account_ref,
        "effective_from_ns": effective_from_ns,
        "effective_until_ns": effective_until_ns,
        "implementation_version": LIVE_CANARY_IMPLEMENTATION_VERSION,
    }
    return _sha256_prefix("CANAUTH", payload)


def derive_order_confirmation_id(confirmation: LiveOrderConfirmationV1) -> str:
    payload = {
        "authorization_ref": confirmation.authorization_ref,
        "broker_order_intent_ref": confirmation.broker_order_intent_ref,
        "instrument_id": confirmation.instrument_id,
        "side": confirmation.side,
        "quantity": confirmation.quantity,
        "order_type": confirmation.order_type,
        "limit_price_minor": confirmation.limit_price_minor,
        "confirmation_time_ns": confirmation.confirmation_time_ns,
    }
    return _sha256_prefix("ORDCONF", payload)


def derive_portfolio_snapshot_id(snapshot: LivePortfolioSnapshotV1) -> str:
    payload = {
        "broker": snapshot.broker,
        "account_fingerprint": snapshot.account_fingerprint,
        "as_of_ns": snapshot.as_of_ns,
        "cash_minor": snapshot.cash_minor,
        "gross_exposure_minor": snapshot.gross_exposure_minor,
        "net_exposure_minor": snapshot.net_exposure_minor,
    }
    return _sha256_prefix("LIVEPF", payload)


def derive_submission_receipt_id(receipt: BrokerSubmissionReceiptV1) -> str:
    payload = {
        "order_intent_ref": receipt.order_intent_ref,
        "authorization_ref": receipt.authorization_ref,
        "confirmation_ref": receipt.confirmation_ref,
        "client_order_id": receipt.client_order_id,
        "submit_attempt_time_ns": receipt.submit_attempt_time_ns,
        "payload_hash": receipt.payload_hash,
    }
    return _sha256_prefix("SUBREC", payload)


def derive_fill_receipt_id(fill: LiveFillReceiptV1) -> str:
    payload = {
        "broker_order_id": fill.broker_order_id,
        "client_order_id": fill.client_order_id,
        "broker_fill_id": fill.broker_fill_id,
        "fill_time_ns": fill.fill_time_ns,
        "quantity": fill.quantity,
        "price_minor": fill.price_minor,
    }
    return _sha256_prefix("FILLREC", payload)


def derive_canary_run_id(run: LiveCanaryRunV1) -> str:
    payload = {
        "canary_policy_ref": run.canary_policy_ref,
        "broker": run.broker,
        "account_ref": run.account_ref,
        "start_time_ns": run.start_time_ns,
        "source_head": run.source_head,
    }
    return _sha256_prefix("CANRUN", payload)


def derive_canary_report_id(report: LiveCanaryQualificationReportV1) -> str:
    payload = {
        "canary_run_ref": report.canary_run_ref,
        "disposition": report.disposition.value,
        "submit_attempts": report.submit_attempts,
        "fills": report.fills,
    }
    return _sha256_prefix("CANREP", payload)


def derive_program_policy_id(policy: LiveCanaryProgramPolicyV1) -> str:
    payload = {
        "allowed_brokers": list(policy.allowed_brokers),
        "allowed_accounts": list(policy.allowed_accounts),
        "max_sessions": policy.max_sessions,
        "max_program_order_count": policy.max_program_order_count,
        "max_program_live_notional_minor": policy.max_program_live_notional_minor,
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("PROGPOL", payload)


def derive_program_run_id(run: LiveCanaryProgramRunV1) -> str:
    payload = {
        "program_policy_ref": run.program_policy_ref,
        "source_head": run.source_head,
        "program_start_ns": run.program_start_ns,
    }
    return _sha256_prefix("PROGRUN", payload)


def derive_checkpoint_id(checkpoint: LiveReconciliationCheckpointV1) -> str:
    payload = {
        "as_of_ns": checkpoint.as_of_ns,
        "broker": checkpoint.broker,
        "account_ref": checkpoint.account_ref,
        "known_local_orders": list(checkpoint.known_local_orders),
        "broker_open_orders": list(checkpoint.broker_open_orders),
        "health": checkpoint.health,
    }
    return _sha256_prefix("RECONCP", payload)


def derive_incident_id(incident: LiveExecutionIncidentV1) -> str:
    payload = {
        "incident_type": incident.incident_type.value,
        "severity": incident.severity.value,
        "detected_at_ns": incident.detected_at_ns,
        "session_ref": incident.session_ref,
        "program_run_ref": incident.program_run_ref,
    }
    return _sha256_prefix("INCID", payload)


def derive_response_policy_id(policy: LiveIncidentResponsePolicyV1) -> str:
    payload = {
        "critical_actions": list(policy.critical_actions),
        "implementation_version": policy.implementation_version,
    }
    return _sha256_prefix("INCRESP", payload)


def derive_resume_approval_id(approval: LiveOperationalResumeApprovalV1) -> str:
    payload = {
        "incident_refs": list(approval.incident_refs),
        "program_run_ref": approval.program_run_ref,
        "approved_at_ns": approval.approved_at_ns,
        "approved_by": approval.approved_by,
    }
    return _sha256_prefix("RESUME", payload)


def derive_session_report_id(report: LiveCanarySessionReportV1) -> str:
    payload = {
        "session_ref": report.session_ref,
        "program_run_ref": report.program_run_ref,
        "disposition": report.disposition.value,
    }
    return _sha256_prefix("SESREP", payload)


def derive_program_report_id(report: LiveCanaryProgramReportV1) -> str:
    payload = {
        "program_run_ref": report.program_run_ref,
        "disposition": report.disposition.value,
        "sessions_executed": report.sessions_executed,
    }
    return _sha256_prefix("PROGREP", payload)


def authorization_semantics_hash(auth: LiveExecutionAuthorizationV1) -> str:
    return derive_payload_hash(
        {
            "broker": auth.broker,
            "account_ref": auth.account_ref,
            "scope": auth.scope,
            "allowed_instruments": list(auth.allowed_instruments),
            "allowed_sides": list(auth.allowed_sides),
            "allowed_order_types": list(auth.allowed_order_types),
            "max_order_notional_minor": auth.max_order_notional_minor,
            "effective_from_ns": auth.effective_from_ns,
            "effective_until_ns": auth.effective_until_ns,
            "required_runtime_activation_ref": auth.required_runtime_activation_ref,
            "required_execution_policy_ref": auth.required_execution_policy_ref,
        }
    )


__all__ = [
    "authorization_semantics_hash",
    "derive_account_fingerprint",
    "derive_canary_authorization_id",
    "derive_canary_policy_id",
    "derive_canary_report_id",
    "derive_canary_run_id",
    "derive_checkpoint_id",
    "derive_fill_receipt_id",
    "derive_human_approval_id",
    "derive_incident_id",
    "derive_order_confirmation_id",
    "derive_portfolio_snapshot_id",
    "derive_preview_hash",
    "derive_preview_id",
    "derive_program_policy_id",
    "derive_program_report_id",
    "derive_program_run_id",
    "derive_response_policy_id",
    "derive_resume_approval_id",
    "derive_session_report_id",
    "derive_submission_receipt_id",
]
