"""Component research metrics for historical development runs."""

from __future__ import annotations

from collections.abc import Sequence
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
        "gross_pnl": simulator_summary.get("gross_pnl"),
        "net_pnl": simulator_summary.get("net_pnl"),
        "estimated_costs": simulator_summary.get("estimated_costs"),
        "turnover": simulator_summary.get("turnover"),
        "drawdown": simulator_summary.get("max_drawdown"),
        "exposure": simulator_summary.get("exposure"),
        "coverage": simulator_summary.get("coverage"),
    }


__all__ = ["compute_component_research_metrics"]
