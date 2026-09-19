"""Component research metrics for historical development runs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _percentile(values: Sequence[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * pct))
    return ordered[index]


def compute_component_research_metrics(
    *,
    predictions: Sequence[dict[str, Any]],
    labels: Sequence[dict[str, Any]],
    simulator_summary: Mapping[str, Any],
) -> dict[str, Any]:
    paired: list[tuple[int, float, float]] = []
    for pred in predictions:
        decision_time = int(pred["decision_time_ns"])
        label = next((row for row in labels if int(row["decision_time_ns"]) == decision_time), None)
        if label is None:
            continue
        direction = int(pred.get("predicted_direction", 0))
        if direction == 0:
            continue
        forward_return = float(label["forward_return"])
        paired.append((direction, forward_return, 1.0 if direction == int(label["direction"]) else 0.0))
    sample_count = len(paired)
    abstentions = sum(1 for pred in predictions if int(pred.get("predicted_direction", 0)) == 0)
    hit_rate = (sum(hit for _, _, hit in paired) / sample_count) if sample_count else None
    forward_returns = [ret for _, ret, _ in paired]
    directional_accuracy = hit_rate
    positives = [hit for _, _, hit in paired]
    precision = (sum(positives) / len(positives)) if positives else None
    recall = precision
    return {
        "sample_count": sample_count,
        "abstention_rate": abstentions / len(predictions) if predictions else None,
        "hit_rate": hit_rate,
        "precision": precision,
        "recall": recall,
        "directional_accuracy": directional_accuracy,
        "avg_forward_return": (sum(forward_returns) / len(forward_returns)) if forward_returns else None,
        "median_forward_return": _percentile(forward_returns, 0.5),
        "tail_summary": {
            "p10_forward_return": _percentile(forward_returns, 0.1),
            "p90_forward_return": _percentile(forward_returns, 0.9),
        },
        "simulated_fills": simulator_summary.get("fill_count"),
        "gross_realized_pnl": simulator_summary.get("gross_realized_pnl"),
        "gross_unrealized_pnl": simulator_summary.get("gross_unrealized_pnl"),
        "gross_pnl": simulator_summary.get("gross_pnl"),
        "net_pnl": simulator_summary.get("net_pnl"),
        "transaction_costs": simulator_summary.get("transaction_costs"),
        "estimated_costs": simulator_summary.get("estimated_costs"),
        "traded_notional": simulator_summary.get("traded_notional"),
        "turnover": simulator_summary.get("turnover"),
        "position_count": simulator_summary.get("position_count"),
        "winning_closed_trades": simulator_summary.get("winning_closed_trades"),
        "losing_closed_trades": simulator_summary.get("losing_closed_trades"),
        "accounting_version": simulator_summary.get("accounting_version"),
        "cost_model_version": simulator_summary.get("cost_model_version"),
        "drawdown": simulator_summary.get("max_drawdown"),
        "exposure": simulator_summary.get("exposure"),
        "coverage": simulator_summary.get("coverage"),
    }


__all__ = ["compute_component_research_metrics"]
