"""Conservative bar-level execution simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..numeric import apply_participation_cap, decimal_to_minor_units

SIMULATOR_VERSION = "phase7.bar-conservative/1.0.0"
SOURCE_CAPABILITY = "BAR_OHLCV_1M"


@dataclass(frozen=True)
class SimulatorDescriptor:
    registry_id: str = "simulation.noop"
    routing_capability: bool = False


class BarConservativeSimulator:
    """Conservative bar-only fill model for admitted equity intraday bars."""

    registry_id = "simulation.bar_conservative"

    def __init__(self, *, policy: dict[str, Any]) -> None:
        self.policy = policy
        self._bar_allocations: dict[int, int] = {}

    def reset_allocations(self) -> None:
        self._bar_allocations = {}

    def simulate(
        self,
        *,
        intent: dict[str, Any],
        risk_decision: dict[str, Any],
        bars: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        order_body = {
            "allocation_model": SIMULATOR_VERSION,
            "created_time": intent["created_time"],
            "direction": intent["direction"],
            "instrument_id": intent["instrument_id"],
            "intent_id": intent["intent_id"],
            "quantity": risk_decision["approved_quantity"],
            "risk_decision": risk_decision["decision"],
            "source_capability": SOURCE_CAPABILITY,
        }
        order_id = sha256_bytes(canonical_bytes(order_body))
        order: dict[str, Any] = {
            **order_body,
            "activation_time": None,
            "order_id": order_id,
            "state": "CREATED",
        }

        if risk_decision["decision"] not in {"APPROVE", "RESIZE"}:
            order["state"] = "REJECTED"
            order["reason_codes"] = ["SIM_RISK_NOT_APPROVED"]
            return order, None

        approved_qty = int(risk_decision["approved_quantity"])
        if approved_qty <= 0:
            order["state"] = "REJECTED"
            order["reason_codes"] = ["SIM_ZERO_APPROVED_QUANTITY"]
            return order, None

        activation_bar = self._next_bar_after(intent["created_time"], bars)
        if activation_bar is None:
            order["state"] = "REJECTED"
            order["reason_codes"] = ["SIM_NO_POST_SIGNAL_BAR"]
            return order, None

        activation_time = int(activation_bar["available_time"])
        order["activation_time"] = activation_time
        order["state"] = "ACTIVATED"

        fill_bar = self._next_bar_at_or_after(activation_time, bars)
        if fill_bar is None:
            order["state"] = "REJECTED"
            order["reason_codes"] = ["SIM_NO_FILL_BAR"]
            return order, None

        fill_time = int(fill_bar["available_time"])
        if fill_time < activation_time:
            order["state"] = "REJECTED"
            order["reason_codes"] = ["SIM_FILL_BEFORE_ACTIVATION"]
            return order, None

        payload = fill_bar.get("bar_payload", {})
        if not isinstance(payload, dict):
            order["state"] = "REJECTED"
            order["reason_codes"] = ["SIM_INVALID_BAR_PAYLOAD"]
            return order, None

        direction = str(intent["direction"])
        price_key = "high" if direction == "long" else "low"
        price_str = str(payload.get(price_key, ""))
        try:
            fill_price_minor = decimal_to_minor_units(
                price_str,
                scale=int(self.policy["price_scale"]),
            )
        except ValueError:
            order["state"] = "REJECTED"
            order["reason_codes"] = ["SIM_INVALID_FILL_PRICE"]
            return order, None

        bar_volume = int(payload.get("volume", 0))
        eligible = apply_participation_cap(
            bar_volume,
            numerator=int(self.policy["participation_cap_numerator"]),
            denominator=int(self.policy["participation_cap_denominator"]),
        )
        prior = self._bar_allocations.get(fill_time, 0)
        remaining = max(eligible - prior, 0)
        fill_qty = min(approved_qty, remaining)
        if fill_qty <= 0:
            order["state"] = "REJECTED"
            order["reason_codes"] = ["SIM_NO_ELIGIBLE_VOLUME"]
            return order, None

        self._bar_allocations[fill_time] = prior + fill_qty
        fill_body = {
            "activation_time": activation_time,
            "direction": direction,
            "fill_price_minor": fill_price_minor,
            "fill_quantity": fill_qty,
            "fill_time": fill_time,
            "instrument_id": intent["instrument_id"],
            "normalized_event_id": fill_bar.get("normalized_event_id"),
            "order_id": order_id,
        }
        fill = {
            **fill_body,
            "fill_id": sha256_bytes(canonical_bytes(fill_body)),
        }
        order["state"] = "FILLED" if fill_qty == approved_qty else "PARTIALLY_FILLED"
        order["filled_quantity"] = fill_qty
        return order, fill

    @staticmethod
    def _next_bar_after(created_time: int, bars: list[dict[str, Any]]) -> dict[str, Any] | None:
        for bar in bars:
            if int(bar["available_time"]) > created_time:
                return bar
        return None

    @staticmethod
    def _next_bar_at_or_after(activation_time: int, bars: list[dict[str, Any]]) -> dict[str, Any] | None:
        for bar in bars:
            if int(bar["available_time"]) >= activation_time:
                return bar
        return None


def simulate_futures_roll(
    *,
    from_contract_id: str,
    to_contract_id: str,
    quantity: int,
    roll_gap: float,
) -> dict[str, Any]:
    """F2 roll execution stub — records roll intent with explicit gap semantics."""
    if quantity <= 0 or from_contract_id == to_contract_id:
        return {
            "available": False,
            "reason": "ROLL_INVALID_PARAMETERS",
        }
    body = {
        "from_contract_id": from_contract_id,
        "gap_multiplier": roll_gap,
        "quantity": quantity,
        "simulator_version": SIMULATOR_VERSION,
        "to_contract_id": to_contract_id,
    }
    return {
        "available": True,
        "roll_event": body,
        "roll_id": sha256_bytes(canonical_bytes(body)),
    }


__all__ = ["BarConservativeSimulator", "SIMULATOR_VERSION", "simulate_futures_roll"]
