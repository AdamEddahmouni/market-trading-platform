"""Machine-readable primary-source verification artifact (not trading authority)."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes

ARTIFACT_SCHEMA_VERSION = "1.0.0"
ENGINE_VERSION = "research.public_record_primary_source/1.0.0"
PUBLIC_RECORD_PRIMARY_SOURCE_ARTIFACT_TYPE = "PUBLIC_RECORD_PRIMARY_SOURCE_VERIFICATION_ARTIFACT"
AUTHORITY_CLASS = "EVIDENCE_NOT_PREDICTION"
REALTIME_CONGRESSIONAL_FEED_CLAIM = "NOT_CLAIMED"


def build_verification_artifact(
    *,
    domain: str,
    verification: dict[str, Any],
    generated_at: str,
    live_network: bool,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "artifact_type": PUBLIC_RECORD_PRIMARY_SOURCE_ARTIFACT_TYPE,
        "authority_class": AUTHORITY_CLASS,
        "domain": domain,
        "engine_version": ENGINE_VERSION,
        "generated_at": generated_at,
        "live_network_used": live_network,
        "realtime_congressional_feed_claim": REALTIME_CONGRESSIONAL_FEED_CLAIM,
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "verification": verification,
    }
    body["content_sha256"] = artifact_content_sha256(body)
    return body


def artifact_content_sha256(artifact: dict[str, Any]) -> str:
    payload = {key: value for key, value in artifact.items() if key != "content_sha256"}
    return sha256_bytes(canonical_bytes(payload))


__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "AUTHORITY_CLASS",
    "ENGINE_VERSION",
    "PUBLIC_RECORD_PRIMARY_SOURCE_ARTIFACT_TYPE",
    "REALTIME_CONGRESSIONAL_FEED_CLAIM",
    "artifact_content_sha256",
    "build_verification_artifact",
]
