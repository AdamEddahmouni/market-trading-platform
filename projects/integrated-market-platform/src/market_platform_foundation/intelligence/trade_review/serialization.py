"""Serialization for trade review artifacts."""

from __future__ import annotations

from typing import Any

from ..contracts.common import contract_reference_from_dict, contract_reference_to_dict
from .contracts import (
    TRADE_REVIEW_IMPLEMENTATION_VERSION,
    TRADE_REVIEW_SCHEMA_VERSION,
    TradeExecutionAttribution,
    TradeReviewMode,
    TradeReviewV1,
)


def trade_execution_attribution_to_dict(attribution: TradeExecutionAttribution) -> dict[str, Any]:
    return {
        "order_refs": [contract_reference_to_dict(ref) for ref in attribution.order_refs],
        "fill_refs": [contract_reference_to_dict(ref) for ref in attribution.fill_refs],
        "entry_price_minor": attribution.entry_price_minor,
        "exit_price_minor": attribution.exit_price_minor,
        "realized_pnl_minor": attribution.realized_pnl_minor,
        "mae_bps": attribution.mae_bps,
        "mfe_bps": attribution.mfe_bps,
        "slippage_bps": attribution.slippage_bps,
        "decision_to_submit_latency_ns": attribution.decision_to_submit_latency_ns,
        "exit_reason": attribution.exit_reason,
    }


def trade_execution_attribution_from_dict(payload: dict[str, Any]) -> TradeExecutionAttribution:
    return TradeExecutionAttribution(
        order_refs=tuple(
            contract_reference_from_dict(item) for item in payload.get("order_refs", ())
        ),
        fill_refs=tuple(
            contract_reference_from_dict(item) for item in payload.get("fill_refs", ())
        ),
        entry_price_minor=payload.get("entry_price_minor"),
        exit_price_minor=payload.get("exit_price_minor"),
        realized_pnl_minor=payload.get("realized_pnl_minor"),
        mae_bps=payload.get("mae_bps"),
        mfe_bps=payload.get("mfe_bps"),
        slippage_bps=payload.get("slippage_bps"),
        decision_to_submit_latency_ns=payload.get("decision_to_submit_latency_ns"),
        exit_reason=payload.get("exit_reason"),
    )


def trade_review_v1_to_dict(review: TradeReviewV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": review.schema_version,
        "review_id": review.review_id,
        "review_mode": review.review_mode.value,
        "decision": review.decision,
        "decision_time_ns": review.decision_time_ns,
        "created_at_ns": review.created_at_ns,
        "opportunity_id": review.opportunity_id,
        "strategy_id": review.strategy_id,
        "ftep_campaign": review.ftep_campaign,
        "ftep_session_id": review.ftep_session_id,
        "evidence_snapshot_refs": [
            contract_reference_to_dict(ref) for ref in review.evidence_snapshot_refs
        ],
        "contradictions": list(review.contradictions),
        "risk_snapshot": dict(review.risk_snapshot) if review.risk_snapshot is not None else None,
        "preview_refs": [contract_reference_to_dict(ref) for ref in review.preview_refs],
        "execution_attribution": (
            trade_execution_attribution_to_dict(review.execution_attribution)
            if review.execution_attribution is not None
            else None
        ),
        "execution_decision_trace_id": review.execution_decision_trace_id,
        "tags": list(review.tags),
        "mistakes": list(review.mistakes),
        "notes": review.notes,
        "reflection": review.reflection,
        "implementation_version": review.implementation_version,
        "metadata": dict(review.metadata),
    }
    return body


def trade_review_v1_from_dict(payload: dict[str, Any]) -> TradeReviewV1:
    attribution_payload = payload.get("execution_attribution")
    return TradeReviewV1(
        review_id=str(payload["review_id"]),
        schema_version=str(payload.get("schema_version", TRADE_REVIEW_SCHEMA_VERSION)),
        review_mode=TradeReviewMode(str(payload["review_mode"])),
        decision=str(payload["decision"]),
        decision_time_ns=int(payload["decision_time_ns"]),
        created_at_ns=int(payload["created_at_ns"]),
        opportunity_id=payload.get("opportunity_id"),
        strategy_id=payload.get("strategy_id"),
        ftep_campaign=payload.get("ftep_campaign"),
        ftep_session_id=payload.get("ftep_session_id"),
        evidence_snapshot_refs=tuple(
            contract_reference_from_dict(item)
            for item in payload.get("evidence_snapshot_refs", ())
        ),
        contradictions=tuple(str(v) for v in payload.get("contradictions", ())),
        risk_snapshot=dict(payload["risk_snapshot"]) if payload.get("risk_snapshot") is not None else None,
        preview_refs=tuple(
            contract_reference_from_dict(item) for item in payload.get("preview_refs", ())
        ),
        execution_attribution=(
            trade_execution_attribution_from_dict(attribution_payload)
            if attribution_payload is not None
            else None
        ),
        execution_decision_trace_id=payload.get("execution_decision_trace_id"),
        tags=tuple(str(v) for v in payload.get("tags", ())),
        mistakes=tuple(str(v) for v in payload.get("mistakes", ())),
        notes=str(payload.get("notes", "")),
        reflection=str(payload.get("reflection", "")),
        implementation_version=str(
            payload.get("implementation_version", TRADE_REVIEW_IMPLEMENTATION_VERSION)
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "trade_execution_attribution_from_dict",
    "trade_execution_attribution_to_dict",
    "trade_review_v1_from_dict",
    "trade_review_v1_to_dict",
]
