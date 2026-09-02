"""Preregistration binding before strategy interpretation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from .strategy_spec import StrategyDefinition, coerce_strategy_spec

PREREGISTRATION_VERSION = "1.0.0"


def build_preregistration(
    strategy_spec: StrategyDefinition | Mapping[str, Any],
    *,
    registered_at: str,
    principal_id: str = "PROJECT-PRINCIPAL-001",
) -> dict[str, Any]:
    spec = coerce_strategy_spec(strategy_spec)
    identity = str(spec["strategy_identity_hash"])
    body = {
        "principal_id": principal_id,
        "preregistration_version": PREREGISTRATION_VERSION,
        "registered_at": registered_at,
        "strategy_identity_hash": identity,
    }
    record_hash = sha256_bytes(canonical_bytes(body))
    return {**body, "preregistration_record_hash": record_hash}


def verify_preregistration(
    preregistration: dict[str, Any],
    strategy_spec: StrategyDefinition | Mapping[str, Any],
) -> tuple[str, list[str]]:
    spec = coerce_strategy_spec(strategy_spec)
    reasons: list[str] = []
    if preregistration.get("preregistration_version") != PREREGISTRATION_VERSION:
        reasons.append("PREREG_VERSION_MISMATCH")
    expected_identity = str(spec["strategy_identity_hash"])
    if preregistration.get("strategy_identity_hash") != expected_identity:
        reasons.append("PREREG_IDENTITY_MISMATCH")
    body = {
        "principal_id": preregistration.get("principal_id"),
        "preregistration_version": preregistration.get("preregistration_version"),
        "registered_at": preregistration.get("registered_at"),
        "strategy_identity_hash": preregistration.get("strategy_identity_hash"),
    }
    expected_hash = sha256_bytes(canonical_bytes(body))
    if preregistration.get("preregistration_record_hash") != expected_hash:
        reasons.append("PREREG_RECORD_HASH_MISMATCH")
    status = "PASS" if not reasons else "FAIL"
    return status, reasons
