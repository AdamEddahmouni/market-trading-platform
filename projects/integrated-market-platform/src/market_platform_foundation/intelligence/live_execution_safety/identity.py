"""Deterministic live execution safety identities (BUILD 28)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .types import (
    LIVE_EXECUTION_SAFETY_IMPLEMENTATION_VERSION,
    BrokerCapabilityCertificationV1,
    BrokerOrderIntentV1,
    BrokerReconciliationSnapshotV1,
    LiveExecutionAuthorizationV1,
    LiveExecutionGateDecisionV1,
    LiveExecutionKillSwitchV1,
    LiveExecutionSafetyReportV1,
    LiveExecutionSafetySpecV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def derive_client_order_id(
    *,
    risk_decision_id: str,
    trade_proposal_id: str,
    broker: str,
    account_environment: str,
    max_length: int = 32,
) -> str:
    """Deterministic idempotency identity derived from approved intent context."""
    raw = _sha256_prefix(
        "CLORD",
        {
            "risk_decision_id": risk_decision_id,
            "trade_proposal_id": trade_proposal_id,
            "broker": broker,
            "account_environment": account_environment,
            "implementation_version": LIVE_EXECUTION_SAFETY_IMPLEMENTATION_VERSION,
        },
    )
    # Provider-safe alphanumeric mapping preserving collision resistance.
    token = raw.split("-", 1)[1][: max_length - 2]
    return f"IMP{token}"[:max_length]


def derive_broker_order_intent_id(intent_payload: dict[str, Any]) -> str:
    return _sha256_prefix("BOINT", intent_payload)


def derive_gate_decision_id(payload: dict[str, Any]) -> str:
    return _sha256_prefix("LEGATE", payload)


def derive_certification_id(cert: BrokerCapabilityCertificationV1) -> str:
    payload = {
        "broker": cert.broker,
        "adapter_version": cert.adapter_version,
        "asset_classes": list(cert.asset_classes),
        "account_environment": cert.account_environment.value,
        "certification_mode": cert.certification_mode.value,
        "implementation_version": cert.implementation_version,
    }
    return _sha256_prefix("BROKCERT", payload)


def derive_authorization_id(auth: LiveExecutionAuthorizationV1) -> str:
    payload = {
        "broker": auth.broker,
        "account_ref": auth.account_ref,
        "scope": auth.scope,
        "authorization_state": auth.authorization_state.value,
        "effective_from_ns": auth.effective_from_ns,
        "effective_until_ns": auth.effective_until_ns,
        "implementation_version": LIVE_EXECUTION_SAFETY_IMPLEMENTATION_VERSION,
    }
    return _sha256_prefix("LIVEAUTH", payload)


def derive_kill_switch_id(kill_switch: LiveExecutionKillSwitchV1) -> str:
    payload = {
        "scope": kill_switch.scope,
        "state": kill_switch.state.value,
        "effective_from_ns": kill_switch.effective_from_ns,
        "source": kill_switch.source,
    }
    return _sha256_prefix("KILLSW", payload)


def derive_payload_hash(payload: dict[str, Any]) -> str:
    return _sha256_prefix("PAYLOAD", payload)


def derive_reconciliation_snapshot_id(snapshot: BrokerReconciliationSnapshotV1) -> str:
    payload = {
        "broker": snapshot.broker,
        "account_environment": snapshot.account_environment.value,
        "as_of_ns": snapshot.as_of_ns,
        "local_open_intents": list(snapshot.local_open_intents),
        "broker_open_orders": list(snapshot.broker_open_orders),
        "health_state": snapshot.health_state.value,
    }
    return _sha256_prefix("BREC", payload)


def derive_safety_spec_id(spec: LiveExecutionSafetySpecV1) -> str:
    payload = {
        "source_build27_ref": spec.source_build27_ref,
        "source_build26_ref": spec.source_build26_ref,
        "certification_mode": spec.certification_mode.value,
        "required_brokers": list(spec.required_brokers),
        "implementation_version": spec.implementation_version,
    }
    return _sha256_prefix("LESSPEC", payload)


def derive_safety_report_id(
    *,
    spec_id: str,
    broker_certification_ids: tuple[str, ...],
    evaluation_as_of_ns: int,
) -> str:
    payload = {
        "spec_id": spec_id,
        "broker_certification_ids": list(broker_certification_ids),
        "evaluation_as_of_ns": evaluation_as_of_ns,
        "implementation_version": LIVE_EXECUTION_SAFETY_IMPLEMENTATION_VERSION,
    }
    return _sha256_prefix("LESREP", payload)


def derive_account_fingerprint(account_ref: str) -> str:
    """Privacy-safe account reference — never persist full account numbers."""
    return _sha256_prefix("ACCTFP", {"account_ref": account_ref})[:24]


def redact_secrets(text: str) -> str:
    """Redact common secret patterns from audit text."""
    patterns = [
        (r"(?i)(password|token|secret|api[_-]?key)\s*[:=]\s*\S+", r"\1=***REDACTED***"),
        (r"\b\d{8,}\b", "***ACCOUNT***"),
    ]
    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)
    return result
