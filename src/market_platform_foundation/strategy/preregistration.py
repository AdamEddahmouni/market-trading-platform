"""Preregistration binding before strategy interpretation."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

PREREGISTRATION_VERSION = "1.0.0"


def build_preregistration(
    strategy_spec: dict[str, Any],
    *,
    registered_at: str,
    principal_id: str = "PROJECT-PRINCIPAL-001",
) -> dict[str, Any]:
    identity = str(strategy_spec["strategy_identity_hash"])
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
    strategy_spec: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if preregistration.get("preregistration_version") != PREREGISTRATION_VERSION:
        reasons.append("PREREG_VERSION_MISMATCH")
    expected_identity = str(strategy_spec["strategy_identity_hash"])
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
