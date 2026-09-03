"""Conservative NBBO options execution simulator (O9)."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..options.execution import (
    EXECUTION_VERSION,
    build_options_order_intent,
    legs_from_candidate,
    run_options_lifecycle,
    simulate_multi_leg_entry,
)
from ..portfolio.options_ledger import apply_option_fill, build_options_ledger_state

SOURCE_CAPABILITY = "OPTION_CHAIN_NBBO"


class OptionsConservativeSimulator:
    """Conservative multi-leg options fill model using NBBO spread crossing."""

    registry_id = "simulation.options_conservative"

    def __init__(self, *, policy: dict[str, Any] | None = None) -> None:
        self.policy = policy or {}

    def simulate(
        self,
        *,
        intent: dict[str, Any],
        risk_decision: dict[str, Any],
        chain_rows: list[dict[str, Any]],
        scenario: dict[str, Any] | None = None,
        squeeze_context: dict[str, Any] | None = None,
        initial_cash: float = 100_000.0,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        symbol = str(intent.get("symbol", ""))
        template = intent.get("template")
        order_body: dict[str, Any] = {
            "allocation_model": EXECUTION_VERSION,
            "created_time": intent.get("created_time"),
            "instrument_type": intent.get("instrument_type", "OPTION_MULTI_LEG"),
            "intent_id": intent.get("intent_id"),
            "legs": intent.get("legs", []),
            "quantity_legs": len(intent.get("legs", [])),
            "risk_decision": risk_decision.get("decision"),
            "source_capability": SOURCE_CAPABILITY,
            "symbol": symbol,
            "template": template,
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
            "order_id": order_id,
            "state": "CREATED",
        }

        if risk_decision.get("decision") not in {"APPROVE", "RESIZE"}:
            order["state"] = "REJECTED"
            order["reason_codes"] = ["SIM_RISK_NOT_APPROVED"]
            return order, []

        legs = [
            leg
            for leg in (
                legs_from_candidate({"legs": intent.get("legs", [])})
                if intent.get("legs")
                else []
            )
        ]
        if not legs:
            order["state"] = "REJECTED"
            order["reason_codes"] = ["SIM_NO_OPTION_LEGS"]
            return order, []

        entry_result = simulate_multi_leg_entry(legs, chain_rows)
        if not entry_result.get("available"):
            order["state"] = "REJECTED"
            order["reason_codes"] = [str(entry_result.get("reason", "SIM_ENTRY_FAILED"))]
            return order, []

        entry_fills = entry_result["entry_fills"]
        ledger = build_options_ledger_state(initial_cash=initial_cash)
        fills: list[dict[str, Any]] = []
        for fill in entry_fills:
            ledger = apply_option_fill(ledger, fill=fill)
            fill_record = {
                **fill,
                "activation_time": intent.get("created_time"),
                "fill_time": intent.get("created_time"),
                "instrument_id": f"{symbol}:{fill['call_put']}:{fill['strike']}:{fill['expiry']}",
                "order_id": order_id,
            }
            fills.append(fill_record)

        order["state"] = "FILLED"
        order["filled_leg_count"] = len(fills)
        order["entry_fills"] = entry_fills

        if scenario:
            lifecycle = run_options_lifecycle({"ledger": ledger}, scenario)
            if lifecycle.get("available"):
                order["lifecycle_events"] = lifecycle.get("lifecycle_events", [])
                order["realized_pnl"] = lifecycle.get("realized_pnl")

        return order, fills


def simulate_from_candidate(
    candidate: dict[str, Any],
    *,
    symbol: str,
    as_of_time: str,
    chain_rows: list[dict[str, Any]],
    scenario: dict[str, Any] | None = None,
    squeeze_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Convenience wrapper for strategy best_candidate execution."""
    intent = build_options_order_intent(candidate, as_of_time, symbol=symbol)
    if intent is None:
        return {"state": "REJECTED", "reason_codes": ["SIM_INTENT_BUILD_FAILED"]}, []
    simulator = OptionsConservativeSimulator()
    risk_decision = {"decision": "APPROVE", "approved_quantity": 1}
    return simulator.simulate(
        intent=intent,
        risk_decision=risk_decision,
        chain_rows=chain_rows,
        scenario=scenario,
        squeeze_context=squeeze_context,
    )


__all__ = [
    "OptionsConservativeSimulator",
    "simulate_from_candidate",
]
