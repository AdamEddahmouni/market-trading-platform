"""Paper handoff builders for locked forward-test decisions."""

from __future__ import annotations

from typing import Any

from .types import ForwardTestDecision, ForwardTestMode


def forward_test_correlation_id(forward_test_id: str) -> str:
    return f"forward_test:{forward_test_id}"


def build_decision_source_snapshot(decision: ForwardTestDecision) -> dict[str, Any]:
    headline = (
        f"Forward test {decision.forward_test_id} — {decision.direction} {decision.symbol}"
    )
    snapshot: dict[str, Any] = {
        "source_type": "forward_test_decision",
        "source_id": decision.forward_test_id,
        "source_module": "paper_forward_bridge",
        "headline": headline[:240],
        "source_time": decision.source_time_ns,
        "reasons": [
            {
                "code": "FORWARD_TEST_LOCKED",
                "label": "Prospective forward-test decision locked at decision time",
            }
        ],
    }
    return snapshot


def build_paper_preview_body(
    decision: ForwardTestDecision,
    *,
    instrument_id: str | None = None,
) -> dict[str, Any]:
    if decision.test_mode != ForwardTestMode.EXECUTION:
        raise ValueError("FORWARD_TEST_EXECUTION_NOT_REQUESTED")
    if decision.quantity is None or decision.quantity <= 0:
        raise ValueError("FORWARD_TEST_QUANTITY_REQUIRED")
    direction = decision.direction.upper()
    if direction in {"POSITIVE_DIRECTIONAL_BIAS", "UP", "LONG"}:
        side = "BUY"
    elif direction in {"NEGATIVE_DIRECTIONAL_BIAS", "DOWN", "SHORT"}:
        side = "SELL"
    elif direction in {"BUY", "SELL"}:
        side = direction
    else:
        raise ValueError("FORWARD_TEST_DIRECTION_NOT_EXECUTABLE")
    correlation_id = forward_test_correlation_id(decision.forward_test_id)
    return {
        "side": side,
        "quantity": decision.quantity,
        "order_type": "MARKET",
        "instrument_id": instrument_id or decision.symbol,
        "correlation_id": correlation_id,
        "client_order_id": correlation_id,
        "idempotency_key": correlation_id,
        "decision_source_snapshot": build_decision_source_snapshot(decision),
    }
