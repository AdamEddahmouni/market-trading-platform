"""Edge-stats evidence pipeline: query → match → estimate → CI → artifact."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..wave1.statistics import DEFAULT_WAVE1_STATISTICAL_PLAN, Wave1StatisticalPlan, moving_block_bootstrap_ci
from .artifact import build_evidence_artifact
from .dataset import verify_and_load_biya_bars
from .matching import build_candidate_examples, extract_outcome_values
from .models import DEFAULT_EDGE_STATS_QUERY, EdgeStatsQueryV1


def _estimate_from_values(metric: str, values: tuple[float, ...]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    if metric == "positive_rate":
        return round(mean, 6)
    return round(mean, 3)


def _ci_payload(
    values: tuple[float, ...],
    metric: str,
    plan: Wave1StatisticalPlan,
) -> dict[str, Any]:
    if len(values) < plan.minimum_paired_sample:
        return {
            "status": "INSUFFICIENT_DATA",
            "sample_count": len(values),
            "ci_lower": None,
            "ci_upper": None,
            "mean": _estimate_from_values(metric, values) if values else None,
        }
    paired = moving_block_bootstrap_ci(values, plan)
    return {
        "status": "OK",
        "block_length": paired.block_length,
        "ci_lower": round(paired.ci_lower, 6) if paired.ci_lower is not None else None,
        "ci_upper": round(paired.ci_upper, 6) if paired.ci_upper is not None else None,
        "mean": round(paired.mean_delta, 6),
        "replicate_count": paired.replicate_count,
        "sample_count": paired.sample_count,
        "seed": paired.seed,
    }


def run_edge_stats_pipeline(
    query: EdgeStatsQueryV1 | None = None,
    *,
    bar_source: Path | None = None,
    generated_at: str | None = None,
    statistical_plan: Wave1StatisticalPlan | None = None,
) -> dict[str, Any]:
    query = query or DEFAULT_EDGE_STATS_QUERY
    plan = statistical_plan or DEFAULT_WAVE1_STATISTICAL_PLAN
    bars, dataset = verify_and_load_biya_bars(bar_source=bar_source)
    matched = build_candidate_examples(bars, query)
    values = extract_outcome_values(matched, query.outcome.metric)
    estimate = _estimate_from_values(query.outcome.metric, values)
    ci = _ci_payload(values, query.outcome.metric, plan)
    stamp = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return build_evidence_artifact(
        query=query,
        dataset=dataset,
        matched_examples=matched,
        estimate=estimate,
        ci=ci,
        generated_at=stamp,
        n=len(matched),
    )
