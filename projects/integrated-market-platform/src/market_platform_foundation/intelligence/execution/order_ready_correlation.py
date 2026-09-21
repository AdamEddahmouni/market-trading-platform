"""Read-only correlation helpers for OrderReadyV1 lineage.

Observability only: extracts already-persisted identifiers. Does not mint
authority, grant Live execution, or invent missing opportunity links.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..contracts.common import ContractKind
from .types import OrderReadyV1

_OPPORTUNITY_KIND = ContractKind.OPPORTUNITY.value


def opportunity_id_from_order_ready(order_ready: OrderReadyV1) -> str | None:
    """Return the opportunity id stamped on OrderReady lineage_refs, if any."""
    for ref in order_ready.lineage_refs:
        if str(getattr(ref, "kind", "")) == _OPPORTUNITY_KIND:
            value = str(getattr(ref, "id", "")).strip()
            if value:
                return value
    return None


def order_ready_correlation_snapshot(order_ready: OrderReadyV1) -> dict[str, str | None]:
    """Bounded id map from opportunity through risk to order_ready."""
    return {
        "opportunity_id": opportunity_id_from_order_ready(order_ready),
        "allocation_decision_id": order_ready.allocation_decision_id,
        "trade_proposal_id": order_ready.trade_proposal_id,
        "risk_decision_id": order_ready.risk_decision_id,
        "order_ready_id": order_ready.order_ready_id,
        "correlation_id": order_ready.correlation_id,
    }


def assert_order_ready_opportunity_correlation(
    order_ready: OrderReadyV1,
    *,
    opportunity_id: str,
    correlation_id: str,
) -> None:
    """Fail closed when durable OrderReady cannot explain its opportunity thread."""
    snapshot = order_ready_correlation_snapshot(order_ready)
    observed_opportunity_id = snapshot["opportunity_id"]
    if not observed_opportunity_id:
        raise ValueError("ORDER_READY_OPPORTUNITY_LINEAGE_MISSING")
    if observed_opportunity_id != str(opportunity_id):
        raise ValueError("ORDER_READY_OPPORTUNITY_LINEAGE_MISMATCH")
    if snapshot["correlation_id"] != str(correlation_id):
        raise ValueError("ORDER_READY_CORRELATION_MISMATCH")
    if not snapshot["risk_decision_id"] or not snapshot["trade_proposal_id"]:
        raise ValueError("ORDER_READY_EXECUTION_PREP_IDS_MISSING")


def correlation_snapshot_from_mapping(payload: Mapping[str, Any]) -> dict[str, str | None]:
    """Normalize a serialized OrderReady-shaped mapping for trace contract checks."""
    lineage = payload.get("lineage_refs") or ()
    opportunity_id = None
    for item in lineage:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("kind", "")) == _OPPORTUNITY_KIND:
            candidate = str(item.get("id", "")).strip()
            if candidate:
                opportunity_id = candidate
                break
    return {
        "opportunity_id": opportunity_id,
        "allocation_decision_id": (
            str(payload["allocation_decision_id"])
            if payload.get("allocation_decision_id") is not None
            else None
        ),
        "trade_proposal_id": (
            str(payload["trade_proposal_id"]) if payload.get("trade_proposal_id") is not None else None
        ),
        "risk_decision_id": (
            str(payload["risk_decision_id"]) if payload.get("risk_decision_id") is not None else None
        ),
        "order_ready_id": (
            str(payload["order_ready_id"]) if payload.get("order_ready_id") is not None else None
        ),
        "correlation_id": (
            str(payload["correlation_id"]) if payload.get("correlation_id") is not None else None
        ),
    }


__all__ = [
    "assert_order_ready_opportunity_correlation",
    "correlation_snapshot_from_mapping",
    "opportunity_id_from_order_ready",
    "order_ready_correlation_snapshot",
]
