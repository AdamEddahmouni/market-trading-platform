"""Evaluation metrics for baseline vs options-confirmed runs."""

from __future__ import annotations

from typing import Any, Dict, List


def evaluate_tracks(rows: List[Dict[str, Any]], confirmation_threshold: float = 65.0) -> Dict[str, Any]:
    """
    Evaluate baseline vs options-confirmed tracks.

    Expects optional `realized_return` values in rows for richer metrics.
    """
    baseline = rows
    confirmed = [row for row in rows if float(row.get("options_score", 0.0)) >= confirmation_threshold]

    def _win_rate(items: List[Dict[str, Any]]) -> float:
        returns = [float(row.get("realized_return", 0.0)) for row in items if "realized_return" in row]
        if not returns:
            return 0.0
        wins = len([value for value in returns if value > 0])
        return wins / len(returns)

    def _avg_return(items: List[Dict[str, Any]]) -> float:
        returns = [float(row.get("realized_return", 0.0)) for row in items if "realized_return" in row]
        if not returns:
            return 0.0
        return sum(returns) / len(returns)

    return {
        "baseline_count": len(baseline),
        "confirmed_count": len(confirmed),
        "coverage": (len(confirmed) / len(baseline)) if baseline else 0.0,
        "baseline_win_rate": _win_rate(baseline),
        "confirmed_win_rate": _win_rate(confirmed),
        "baseline_avg_return": _avg_return(baseline),
        "confirmed_avg_return": _avg_return(confirmed),
        "false_positive_reduction_potential": max(0.0, 1.0 - ((len(confirmed) / len(baseline)) if baseline else 1.0)),
    }

