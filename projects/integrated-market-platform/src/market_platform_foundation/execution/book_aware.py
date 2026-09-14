"""Book-aware L2 execution simulator tier — Order Flow OF9 (OF-D09)."""

from __future__ import annotations

from typing import Any

from .fill_model import assert_simulation_execution_allowed, stamp_fill_model_provenance
from .simulator import BarConservativeSimulator

BOOK_AWARE_SIMULATOR_VERSION = "phase9.book-aware-l2/1.0.0"
BOOK_MODEL_VERSION = "displayed_depth_l2_v1"
QUEUE_MODEL_VERSION = "none"


def _touch_depth_cap(book_snapshot: dict[str, Any], direction: str) -> int | None:
    if not isinstance(book_snapshot, dict):
        return None
    if direction == "long":
        raw = book_snapshot.get("ask_size")
    else:
        raw = book_snapshot.get("bid_size")
    if raw is None:
        bids = book_snapshot.get("bids")
        asks = book_snapshot.get("asks")
        if isinstance(bids, list) and bids and isinstance(asks, list) and asks:
            if direction == "long":
                raw = asks[0].get("size") if isinstance(asks[0], dict) else None
            else:
                raw = bids[0].get("size") if isinstance(bids[0], dict) else None
    if raw is None:
        return None
    try:
        depth = int(float(raw))
    except (TypeError, ValueError):
        return None
    return max(depth, 0)


class BookAwareL2Simulator(BarConservativeSimulator):
    """Conservative bar fills capped by displayed L2 touch depth when book snapshot provided."""

    registry_id = "simulation.book_aware_l2_v1"

    def _restamp(
        self,
        order: dict[str, Any],
        fill: dict[str, Any] | None,
        *,
        intent: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        mode = assert_simulation_execution_allowed(
            intent.get("execution_mode") or self.policy.get("execution_mode")
        )
        return stamp_fill_model_provenance(
            order=order,
            fill=fill,
            simulator_version=BOOK_AWARE_SIMULATOR_VERSION,
            source_capability=str(order.get("source_capability") or "BAR_OHLCV_1M"),
            registry_id=self.registry_id,
            execution_mode=mode,
            git_sha=str(order.get("git_sha") or "") or None,
        )

    def simulate(
        self,
        *,
        intent: dict[str, Any],
        risk_decision: dict[str, Any],
        bars: list[dict[str, Any]],
        squeeze_context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        order, fill = super().simulate(
            intent=intent,
            risk_decision=risk_decision,
            bars=bars,
            squeeze_context=squeeze_context,
        )
        if fill is None:
            return self._restamp(order, None, intent=intent)

        book_snapshot = intent.get("book_snapshot")
        approved_qty = int(risk_decision.get("approved_quantity", 0))
        if not isinstance(book_snapshot, dict):
            fill["execution_model_version"] = BOOK_AWARE_SIMULATOR_VERSION
            fill["book_model_version"] = BOOK_MODEL_VERSION
            fill["queue_model_version"] = QUEUE_MODEL_VERSION
            fill["fill_reason_codes"] = list(fill.get("fill_reason_codes", [])) + ["NO_BOOK_SNAPSHOT"]
            fill["unfilled_quantity"] = max(approved_qty - int(fill.get("fill_quantity", 0)), 0)
            return self._restamp(order, fill, intent=intent)

        direction = str(intent.get("direction", ""))
        touch_cap = _touch_depth_cap(book_snapshot, direction)
        if touch_cap is None:
            fill["execution_model_version"] = BOOK_AWARE_SIMULATOR_VERSION
            fill["book_model_version"] = BOOK_MODEL_VERSION
            fill["queue_model_version"] = QUEUE_MODEL_VERSION
            fill["fill_reason_codes"] = list(fill.get("fill_reason_codes", [])) + ["BOOK_DEPTH_UNKNOWN"]
            fill["unfilled_quantity"] = max(approved_qty - int(fill.get("fill_quantity", 0)), 0)
            return self._restamp(order, fill, intent=intent)

        bar_filled_qty = int(fill.get("fill_quantity", 0))
        book_capped_qty = min(bar_filled_qty, touch_cap)
        reason_codes: list[str] = list(fill.get("fill_reason_codes", []))

        if book_capped_qty < bar_filled_qty:
            reason_codes.append("BOOK_DEPTH_PARTIAL")

        order["filled_quantity"] = book_capped_qty
        fill["fill_quantity"] = book_capped_qty
        fill["unfilled_quantity"] = max(approved_qty - book_capped_qty, 0)
        if fill["unfilled_quantity"] > 0:
            order["state"] = "PARTIALLY_FILLED"
        else:
            order["state"] = "FILLED"

        fill["execution_model_version"] = BOOK_AWARE_SIMULATOR_VERSION
        fill["book_model_version"] = BOOK_MODEL_VERSION
        fill["queue_model_version"] = QUEUE_MODEL_VERSION
        fill["fill_reason_codes"] = reason_codes
        fill["touch_depth_cap"] = touch_cap
        return self._restamp(order, fill, intent=intent)


__all__ = [
    "BOOK_AWARE_SIMULATOR_VERSION",
    "BOOK_MODEL_VERSION",
    "BookAwareL2Simulator",
    "QUEUE_MODEL_VERSION",
]
