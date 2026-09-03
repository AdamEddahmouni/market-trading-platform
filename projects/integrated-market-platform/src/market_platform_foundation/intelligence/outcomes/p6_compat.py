"""P6-compatible settlement semantics promoted for BUILD 15 reuse."""

from __future__ import annotations

from typing import Any

from ...shadow.predictor import eligible_trades, reference_price


def tape_row_from_mapping(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_time_ns": int(row["event_time_ns"]),
        "available_time_ns": int(row["available_time_ns"]),
        "price": float(row["price"]),
        "trade_id": row.get("trade_id") or row.get("event_id"),
    }


def p6_reference_price(tape: list[dict[str, Any]], *, decision_time_ns: int) -> dict[str, Any] | None:
    """Reuse frozen P6 P0 selection over eligible trade tape rows."""
    eligible = eligible_trades(tape, decision_time_ns=decision_time_ns)
    return reference_price(eligible, decision_time_ns=decision_time_ns)


def p6_terminal_candidate(
    ticks: list[tuple[int, float, int]],
    *,
    target_ns: int,
    tolerance_ns: int,
) -> tuple[int, float, int] | None:
    """First P6-compatible terminal observation in [target, target + tolerance]."""
    candidates = [row for row in ticks if target_ns <= row[0] <= target_ns + tolerance_ns]
    if not candidates:
        return None
    return candidates[0]


def p6_realized_return(*, p0: float, p_target: float) -> float:
    return p_target / p0 - 1.0


def p6_classify_return(realized_return: float) -> str:
    if realized_return > 0.0:
        return "UP"
    if realized_return < 0.0:
        return "DOWN"
    return "ZERO_RETURN"


__all__ = [
    "p6_classify_return",
    "p6_realized_return",
    "p6_reference_price",
    "p6_terminal_candidate",
    "tape_row_from_mapping",
]
