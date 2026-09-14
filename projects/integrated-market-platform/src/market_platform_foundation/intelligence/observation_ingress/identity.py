"""Stable observation ingress dispatch identities."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes

DISPATCH_IDENTITY_VERSION = "observation-ingress-dispatch-sha256-v1"


def derive_ingress_dispatch_id(
    *,
    event_id: str,
    router_policy_identity: str,
    consumer_ids: tuple[str, ...],
) -> str:
    payload: dict[str, Any] = {
        "consumer_ids": sorted(set(consumer_ids)),
        "event_id": event_id,
        "identity_version": DISPATCH_IDENTITY_VERSION,
        "router_policy_identity": router_policy_identity,
        "schema_version": "1",
    }
    return f"ING-{sha256_bytes(canonical_bytes(payload))}"


__all__ = ["DISPATCH_IDENTITY_VERSION", "derive_ingress_dispatch_id"]
