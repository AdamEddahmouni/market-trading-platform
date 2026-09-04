"""Operational event persistence for EVIDENCE-01B."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import HealthSeverity, OperationalEventType, OperationalEventV1


def derive_event_id(
    *,
    campaign_id: str,
    event_type: OperationalEventType,
    recorded_at_ns: int,
    session_id: str | None,
) -> str:
    payload = f"{campaign_id}|{event_type.value}|{recorded_at_ns}|{session_id or ''}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"OPEV-{digest}"


def operational_event_to_dict(event: OperationalEventV1) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "campaign_id": event.campaign_id,
        "session_id": event.session_id,
        "recorded_at_ns": event.recorded_at_ns,
        "severity": event.severity.value,
        "message": event.message,
        "metadata": dict(event.metadata),
    }


def operational_event_from_dict(payload: dict[str, Any]) -> OperationalEventV1:
    return OperationalEventV1(
        event_id=str(payload["event_id"]),
        event_type=OperationalEventType(str(payload["event_type"])),
        campaign_id=str(payload["campaign_id"]),
        session_id=payload.get("session_id"),
        recorded_at_ns=int(payload["recorded_at_ns"]),
        severity=HealthSeverity(str(payload["severity"])),
        message=str(payload["message"]),
        metadata=dict(payload.get("metadata") or {}),
    )


def append_event_jsonl(path, event: OperationalEventV1) -> None:
    import os

    line = json.dumps(operational_event_to_dict(event), sort_keys=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())
