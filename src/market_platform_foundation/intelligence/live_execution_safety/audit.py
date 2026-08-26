"""Live execution audit events (BUILD 28)."""

from __future__ import annotations

from .identity import _sha256_prefix
from .types import (
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    AccountEnvironment,
    LiveAuditEventKind,
    LiveExecutionAuditEventV1,
)


def build_audit_event(
    *,
    event_kind: LiveAuditEventKind,
    event_time_ns: int,
    broker: str,
    account_environment: AccountEnvironment,
    subject_ref: str | None = None,
    reason_codes: tuple[str, ...] = (),
    metadata: dict | None = None,
) -> LiveExecutionAuditEventV1:
    event_id = _sha256_prefix(
        "LESAUD",
        {
            "event_kind": event_kind.value,
            "event_time_ns": event_time_ns,
            "broker": broker,
            "subject_ref": subject_ref,
        },
    )
    return LiveExecutionAuditEventV1(
        event_id=event_id,
        schema_version=LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
        event_kind=event_kind,
        event_time_ns=event_time_ns,
        broker=broker,
        account_environment=account_environment,
        subject_ref=subject_ref,
        reason_codes=reason_codes,
        metadata=dict(metadata or {}),
    )
