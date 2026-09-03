"""Attribution records for risk, simulation, and accounting outcomes."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes


def build_attribution_record(
    *,
    intent: dict[str, Any],
    risk_decision: dict[str, Any],
    order: dict[str, Any],
    fill: dict[str, Any] | None,
    ledger_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    body = {
        "fill_id": fill.get("fill_id") if fill else None,
        "intent_id": intent["intent_id"],
        "order_id": order["order_id"],
        "order_state": order["state"],
        "realized_pnl_delta_minor": (
            ledger_entry.get("realized_pnl_delta_minor") if ledger_entry else 0
        ),
        "risk_decision": risk_decision["decision"],
        "risk_reason_codes": risk_decision.get("reason_codes", []),
        "simulation_reason_codes": order.get("reason_codes", []),
        "strategy_identity_hash": intent.get("strategy_identity_hash"),
    }
    return {
        **body,
        "attribution_id": sha256_bytes(canonical_bytes(body)),
    }
