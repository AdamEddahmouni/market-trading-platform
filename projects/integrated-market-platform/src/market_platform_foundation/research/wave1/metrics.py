"""Primary and guardrail metrics for Wave 1 families."""

from __future__ import annotations

from typing import Any

from .config import Wave1FamilyConfig


def realized_outcome_bps(example: dict[str, Any]) -> float | None:
    outcome = example.get("outcome") or {}
    if "forward_return_bps" in outcome:
        return float(outcome["forward_return_bps"])
    if "survival" in outcome:
        return 100.0 if bool(outcome["survival"]) else -100.0
    return None


def signed_prediction_error_bps(score: float, outcome_bps: float) -> float:
    direction = 1.0 if score >= 0 else -1.0
    return direction * outcome_bps


def compute_primary_metric(
    config: Wave1FamilyConfig,
    *,
    candidate_scores: tuple[float, ...],
    baseline_scores: tuple[float, ...],
    outcomes_bps: tuple[float, ...],
) -> dict[str, float | int | None]:
    n = len(outcomes_bps)
    if n == 0:
        return {"sample_count": 0, "primary_value": None, "baseline_value": None, "delta": None}
    cand_losses: list[float] = []
    base_losses: list[float] = []
    for c_score, b_score, outcome in zip(candidate_scores, baseline_scores, outcomes_bps, strict=True):
        cand_losses.append(-signed_prediction_error_bps(c_score, outcome))
        base_losses.append(-signed_prediction_error_bps(b_score, outcome))
    cand_mean = sum(cand_losses) / n
    base_mean = sum(base_losses) / n
    delta = cand_mean - base_mean
    if config.primary_metric == "survival_rate_delta":
        cand_hits = sum(1 for loss in cand_losses if loss <= 0)
        base_hits = sum(1 for loss in base_losses if loss <= 0)
        primary = (cand_hits - base_hits) / n
        return {
            "sample_count": n,
            "primary_value": primary,
            "baseline_value": base_hits / n,
            "delta": primary,
        }
    if config.primary_metric == "calibration_brier_delta":
        # Lower loss is better; report delta as baseline_loss - candidate_loss (positive => candidate better).
        primary = base_mean - cand_mean
        return {
            "sample_count": n,
            "primary_value": primary,
            "baseline_value": base_mean,
            "delta": primary,
        }
    # Default: paired return delta in bps space (candidate minus baseline expected signed return).
    primary = -delta
    return {
        "sample_count": n,
        "primary_value": primary,
        "baseline_value": -base_mean,
        "delta": primary,
    }
