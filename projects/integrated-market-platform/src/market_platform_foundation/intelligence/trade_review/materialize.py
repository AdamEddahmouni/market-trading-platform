"""Automatic trade review materialization from operator lifecycle events."""

from __future__ import annotations

from typing import Any

from ..contracts.common import ContractReference
from ..opportunity.lifecycle import OperatorLifecycleState
from .construct import build_rejected_opportunity_review, build_watched_opportunity_review
from .contracts import TradeReviewV1
from .operator_edits import canonicalize_for_persist
from .store import open_trade_review_repository


def _refs_from_lineage(lineage_refs: tuple[Any, ...]) -> tuple[ContractReference, ...]:
    refs: list[ContractReference] = []
    for item in lineage_refs:
        if isinstance(item, ContractReference):
            refs.append(item)
        elif isinstance(item, dict) and item.get("kind") and item.get("id"):
            refs.append(ContractReference(kind=str(item["kind"]), id=str(item["id"])))
    return tuple(refs)


def materialize_trade_review_for_operator_ack(
    *,
    action: str,
    opportunity_id: str | None,
    strategy_id: str | None,
    decision_time_ns: int,
    created_at_ns: int,
    evidence_snapshot_refs: tuple[ContractReference, ...] = (),
    risk_snapshot: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> TradeReviewV1 | None:
    ack_action = OperatorLifecycleState(str(action))
    if ack_action == OperatorLifecycleState.DISMISSED:
        if not opportunity_id:
            return None
        review = build_rejected_opportunity_review(
            opportunity_id=str(opportunity_id),
            strategy_id=strategy_id,
            decision_time_ns=decision_time_ns,
            created_at_ns=created_at_ns,
            evidence_snapshot_refs=evidence_snapshot_refs,
            risk_snapshot=risk_snapshot,
            metadata=metadata,
        )
    elif ack_action == OperatorLifecycleState.WATCHED:
        if not opportunity_id:
            return None
        review = build_watched_opportunity_review(
            opportunity_id=str(opportunity_id),
            strategy_id=strategy_id,
            decision_time_ns=decision_time_ns,
            created_at_ns=created_at_ns,
            evidence_snapshot_refs=evidence_snapshot_refs,
            risk_snapshot=risk_snapshot,
            metadata=metadata,
        )
    else:
        return None
    repo = open_trade_review_repository()
    repo.put_trade_review(canonicalize_for_persist(review))
    return repo.get_trade_review(review.review_id)


__all__ = ["materialize_trade_review_for_operator_ack", "_refs_from_lineage"]
