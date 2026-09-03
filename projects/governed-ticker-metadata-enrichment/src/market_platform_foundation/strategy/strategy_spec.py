"""Strategy specification and identity per Revision 3 Section 11."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

ALIGNMENT_TYPES = ("FORECAST_MOMENTUM", "WHALE_ALIGNED", "WHALE_CONTRARIAN")
SPEC_VERSION = "1.0.0"


def build_strategy_spec(
    *,
    alignment_type: str,
    hypothesis: str,
    evidence_requirements: list[str],
    instrument_id: str = "EQ-1",
) -> dict[str, Any]:
    if alignment_type not in ALIGNMENT_TYPES:
        raise ValueError(f"unsupported alignment type: {alignment_type}")
    body = {
        "alignment_type": alignment_type,
        "evidence_requirements": sorted(evidence_requirements),
        "hypothesis": hypothesis,
        "instrument_id": instrument_id,
        "spec_version": SPEC_VERSION,
    }
    identity_hash = strategy_identity_hash(body)
    return {**body, "strategy_identity_hash": identity_hash}


def strategy_identity_hash(spec_body: dict[str, Any]) -> str:
    without_hash = {k: v for k, v in spec_body.items() if k != "strategy_identity_hash"}
    return sha256_bytes(canonical_bytes(without_hash))
