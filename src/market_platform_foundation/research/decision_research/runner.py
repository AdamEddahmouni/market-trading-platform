"""Decision research runner."""

from __future__ import annotations

from typing import Any

from .experiments import SHORT_SQUEEZE_EXPERIMENTS, evaluate_experiment
from .pit_gate import chronological_split


def run_short_squeeze_family(examples: list[dict[str, Any]]) -> dict[str, Any]:
    splits = chronological_split(examples)
    results = []
    for hypothesis in SHORT_SQUEEZE_EXPERIMENTS.values():
        results.append(evaluate_experiment(hypothesis, splits.get("train") or examples))
    return {
        "family": "SHORT_SQUEEZE",
        "experiments": results,
        "splits": {key: len(rows) for key, rows in splits.items()},
        "execution_authority": "NONE",
        "auto_strategy_promotion": False,
    }
