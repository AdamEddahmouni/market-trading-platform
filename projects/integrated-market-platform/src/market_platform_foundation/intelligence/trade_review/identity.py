"""Deterministic trade review identities."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..contracts.common import ContractReference, contract_reference_to_dict
from .contracts import TradeReviewMode


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def _refs_identity_payload(refs: tuple[ContractReference, ...]) -> list[dict[str, Any]]:
    return sorted(
        [contract_reference_to_dict(ref) for ref in refs],
        key=lambda item: (item["kind"], item["id"]),
    )


def derive_trade_review_id(
    *,
    review_mode: TradeReviewMode | str,
    opportunity_id: str | None,
    strategy_id: str | None,
    decision: str,
    decision_time_ns: int,
    ftep_campaign: str | None = None,
    ftep_session_id: str | None = None,
    evidence_snapshot_refs: tuple[ContractReference, ...] = (),
) -> str:
    payload: dict[str, Any] = {
        "review_mode": str(review_mode),
        "opportunity_id": opportunity_id,
        "strategy_id": strategy_id,
        "decision": decision,
        "decision_time_ns": decision_time_ns,
        "ftep_campaign": ftep_campaign,
        "ftep_session_id": ftep_session_id,
        "evidence_snapshot_refs": _refs_identity_payload(evidence_snapshot_refs),
    }
    return _sha256_prefix("TREV", payload)


__all__ = ["derive_trade_review_id"]
