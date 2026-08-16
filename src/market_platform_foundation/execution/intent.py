"""Order intent construction from strategy signals."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes


def build_order_intent(
    *,
    interpretation: dict[str, Any],
    instrument_id: str,
    observation_time: int,
    desired_quantity: int,
    action: str = "OPEN",
) -> dict[str, Any] | None:
    if interpretation.get("outcome") != "signal":
        return None
    direction = interpretation.get("direction")
    if direction not in {"long", "short"}:
        return None
    body = {
        "action": action,
        "created_time": observation_time,
        "desired_quantity": desired_quantity,
        "direction": direction,
        "instrument_id": instrument_id,
        "signal_prediction_cutoff": interpretation.get("prediction_cutoff"),
        "strategy_identity_hash": interpretation.get("strategy_identity_hash"),
    }
    return {
        **body,
        "intent_id": sha256_bytes(canonical_bytes(body)),
    }
