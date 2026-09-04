"""Deterministic operator control plane identities (BUILD 31)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import (
    AuditReviewReportV1,
    IncidentDrillReportV1,
    IncidentDrillSpecV1,
    OperatorActionReceiptV1,
    OperatorAuditTimelineV1,
    OperatorControlPlaneQualificationReportV1,
    OperatorControlSnapshotV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def derive_snapshot_id(snapshot: OperatorControlSnapshotV1) -> str:
    payload = {
        "as_of_ns": snapshot.as_of_ns,
        "program_run_ref": snapshot.program_run_ref,
        "session_ref": snapshot.session_ref,
        "live_blocked": snapshot.live_blocked,
        "block_reasons": list(snapshot.block_reasons),
        "authorization_status": snapshot.authorization_status,
        "kill_switch_global": snapshot.kill_switch_global,
    }
    return _sha256_prefix("OPSNA", payload)


def derive_action_receipt_id(receipt: OperatorActionReceiptV1) -> str:
    payload = {
        "action_type": receipt.action_type,
        "request_id": receipt.request_id,
        "operator_action_time_ns": receipt.operator_action_time_ns,
        "precondition_snapshot_ref": receipt.precondition_snapshot_ref,
        "success": receipt.success,
    }
    return _sha256_prefix("OPREC", payload)


def derive_timeline_id(timeline: OperatorAuditTimelineV1) -> str:
    payload = {
        "as_of_ns": timeline.as_of_ns,
        "program_run_ref": timeline.program_run_ref,
        "session_ref": timeline.session_ref,
        "event_count": len(timeline.events),
    }
    return _sha256_prefix("OPTLN", payload)


def derive_timeline_event_id(
    *,
    event_family: str,
    event_type: str,
    event_time_ns: int,
    source_ref: str,
) -> str:
    payload = {
        "event_family": event_family,
        "event_type": event_type,
        "event_time_ns": event_time_ns,
        "source_ref": source_ref,
    }
    return _sha256_prefix("OPEVT", payload)


def derive_review_report_id(report: AuditReviewReportV1) -> str:
    payload = {
        "program_run_ref": report.program_run_ref,
        "session_ref": report.session_ref,
        "disposition": report.disposition.value,
        "window_start_ns": report.window_start_ns,
        "window_end_ns": report.window_end_ns,
    }
    return _sha256_prefix("OPREV", payload)


def derive_drill_report_id(report: IncidentDrillReportV1) -> str:
    payload = {
        "drill_spec_ref": report.drill_spec_ref,
        "result": report.result.value,
        "real_broker_submits": report.real_broker_submits,
    }
    return _sha256_prefix("DRILL", payload)


def derive_qualification_report_id(report: OperatorControlPlaneQualificationReportV1) -> str:
    payload = {
        "build31_source_ref": report.build31_source_ref,
        "disposition": report.disposition.value,
    }
    return _sha256_prefix("OPQUAL", payload)
