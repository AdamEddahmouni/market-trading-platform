"""Conservative bar-level execution simulator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..numeric import apply_participation_cap, decimal_to_minor_units

SIMULATOR_VERSION = "phase7.bar-conservative/1.1.0"
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
        squeeze_context: dict[str, Any] | None = None,
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
        if squeeze_context and squeeze_context.get("available"):
            order_body["squeeze_context"] = {
                "squeeze_state": squeeze_context.get("squeeze_state"),
                "exhaustion_risk": squeeze_context.get("exhaustion_risk"),
                "remaining_fuel": squeeze_context.get("remaining_fuel"),
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
        cap_num, cap_den = self._effective_participation_policy(squeeze_context)
        eligible = apply_participation_cap(
            bar_volume,
            numerator=cap_num,
            denominator=cap_den,
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
        if squeeze_context and squeeze_context.get("available"):
            fill_body["squeeze_context"] = order_body.get("squeeze_context")
        fill = {
            **fill_body,
            "fill_id": sha256_bytes(canonical_bytes(fill_body)),
        }
        order["state"] = "FILLED" if fill_qty == approved_qty else "PARTIALLY_FILLED"
        order["filled_quantity"] = fill_qty
        return order, fill

    def _effective_participation_policy(
        self,
        squeeze_context: dict[str, Any] | None,
    ) -> tuple[int, int]:
        numerator = int(self.policy["participation_cap_numerator"])
        denominator = int(self.policy["participation_cap_denominator"])
        if not squeeze_context or not squeeze_context.get("available"):
            return numerator, denominator
        state = str(squeeze_context.get("squeeze_state", "")).upper()
        if state == "ACTIVE_SQUEEZE":
            return max(numerator // 2, 1), denominator
        if state == "EXHAUSTION":
            return max(numerator // 4, 1), denominator
        return numerator, denominator

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
    previous_price: float | None = None,
    current_price: float | None = None,
    contract_multiplier: float = 50.0,
) -> dict[str, Any]:
    """F2/F10 roll execution — records roll intent with optional variation margin."""
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
    vm_payload = None
    if previous_price is not None and current_price is not None:
        vm_payload = simulate_variation_margin_change(
            previous_price=previous_price,
            current_price=current_price,
            quantity=quantity,
            contract_multiplier=contract_multiplier,
        )
        body["variation_margin"] = vm_payload
    return {
        "available": True,
        "roll_event": body,
        "roll_id": sha256_bytes(canonical_bytes(body)),
        "variation_margin": vm_payload,
    }


def simulate_variation_margin_change(
    *,
    previous_price: float,
    current_price: float,
    quantity: int,
    contract_multiplier: float = 50.0,
) -> dict[str, Any]:
    """F10 variation margin delta for one contract leg."""
    if quantity <= 0:
        return {"available": False, "reason": "VM_INVALID_QUANTITY"}
    vm_change = (current_price - previous_price) * quantity * contract_multiplier
    return {
        "available": True,
        "previous_price": previous_price,
        "current_price": current_price,
        "quantity": quantity,
        "contract_multiplier": contract_multiplier,
        "variation_margin_change": round(vm_change, 6),
        "simulator_version": SIMULATOR_VERSION,
    }


def simulate_calendar_spread_pnl(
    *,
    front_price: float,
    back_price: float,
    quantity: int,
    hedge_ratio: float = 1.0,
    contract_multiplier: float = 50.0,
    entry_spread: float | None = None,
) -> dict[str, Any]:
    """F10 spread-leg PnL for calendar relative-value templates."""
    if quantity <= 0:
        return {"available": False, "reason": "SPREAD_INVALID_QUANTITY"}
    spread = back_price - front_price
    pnl = spread * quantity * contract_multiplier * hedge_ratio
    body = {
        "front_price": front_price,
        "back_price": back_price,
        "spread_value": spread,
        "quantity": quantity,
        "hedge_ratio": hedge_ratio,
        "contract_multiplier": contract_multiplier,
        "spread_pnl": round(pnl, 6),
        "simulator_version": SIMULATOR_VERSION,
    }
    if entry_spread is not None:
        body["entry_spread"] = entry_spread
        body["spread_pnl_vs_entry"] = round(
            (spread - entry_spread) * quantity * contract_multiplier * hedge_ratio,
            6,
        )
    return {
        "available": True,
        "spread_event": body,
        "spread_id": sha256_bytes(canonical_bytes(body)),
    }


__all__ = [
    "BarConservativeSimulator",
    "SIMULATOR_VERSION",
    "simulate_calendar_spread_pnl",
    "simulate_futures_roll",
    "simulate_variation_margin_change",
]
