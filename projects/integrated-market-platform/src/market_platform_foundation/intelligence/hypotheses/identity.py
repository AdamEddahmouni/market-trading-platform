"""Deterministic hypothesis identity for BUILD 13."""

from __future__ import annotations

from ...canonical import canonical_bytes, sha256_bytes

HYPOTHESIS_IDENTITY_VERSION = "composite-hypothesis-sha256-v1"


def derive_hypothesis_id(
    *,
    hypothesis_type: str,
    blackboard_id: str,
    snapshot_id: str,
    engine_id: str,
    engine_version: str,
    policy_identity: str,
    scope_key: str,
) -> str:
    payload = {
        "identity_version": HYPOTHESIS_IDENTITY_VERSION,
        "hypothesis_type": hypothesis_type,
        "blackboard_id": blackboard_id,
        "snapshot_id": snapshot_id,
        "engine_id": engine_id,
        "engine_version": engine_version,
        "policy_identity": policy_identity,
        "scope_key": scope_key,
    }
    return f"HYP-{sha256_bytes(canonical_bytes(payload))}"


def scope_key_from_instrument_ids(instrument_ids: tuple[str, ...]) -> str:
    return ",".join(sorted(instrument_ids))


__all__ = [
    "HYPOTHESIS_IDENTITY_VERSION",
    "derive_hypothesis_id",
    "scope_key_from_instrument_ids",
]
