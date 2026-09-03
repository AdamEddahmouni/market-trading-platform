"""Strategy evaluation integrated with Phase 5R walk-forward."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..research.evaluation import run_walk_forward_evaluation
from ..research.forecast import verify_forecast_interface
from .interpretation import interpret_strategy
from .preregistration import build_preregistration
from .strategy_spec import build_strategy_spec

DEFAULT_REGISTERED_AT = "2026-08-16T00:00:00.000000000Z"


def default_forecast_momentum_spec() -> dict[str, Any]:
    return build_strategy_spec(
        alignment_type="FORECAST_MOMENTUM",
        hypothesis="Naive forecast score direction implies tactical alignment",
        evidence_requirements=["bar_derived_features", "naive_forecast"],
    )


def default_whale_aligned_spec() -> dict[str, Any]:
    return build_strategy_spec(
        alignment_type="WHALE_ALIGNED",
        hypothesis="Align with institutional flow when entitled evidence supports direction",
        evidence_requirements=["bar_derived_features", "naive_forecast", "institutional_flow"],
    )


def run_strategy_evaluation(
    events: list[dict[str, Any]],
    *,
    strategy_spec: dict[str, Any] | None = None,
    preregistration: dict[str, Any] | None = None,
    registered_at: str = DEFAULT_REGISTERED_AT,
) -> dict[str, object]:
    spec = strategy_spec or default_forecast_momentum_spec()
    prereg = preregistration or build_preregistration(spec, registered_at=registered_at)
    evaluation = run_walk_forward_evaluation(events)
    interpretations: list[dict[str, object]] = []
    signal_count = 0
    abstention_count = 0

    for row in evaluation.get("predictions", []):
        if not isinstance(row, dict):
            continue
        forecast = row.get("forecast", {})
        if not isinstance(forecast, dict):
            continue
        fcast_status, _ = verify_forecast_interface(forecast)
        cutoff = int(forecast.get("prediction_cutoff", 0))
        obs_time = int(row.get("observation_time", cutoff))
        result = interpret_strategy(
            strategy_spec=spec,
            preregistration=prereg,
            forecast=forecast,
            forecast_status=fcast_status,
            prediction_cutoff=cutoff,
            observation_time=obs_time,
        )
        interpretations.append(result)
        if result["outcome"] == "signal":
            signal_count += 1
        else:
            abstention_count += 1

    prereg_status = "PASS"
    if prereg is None:
        prereg_status = "FAIL"
    else:
        from .preregistration import verify_preregistration

        prereg_status, _ = verify_preregistration(prereg, spec)

    return {
        "abstention_count": abstention_count,
        "dataset_manifest": evaluation["dataset_manifest"],
        "interpretations": interpretations,
        "preregistration": prereg,
        "preregistration_status": prereg_status,
        "signal_count": signal_count,
        "strategy_spec": spec,
        "walk_forward_fold_count": evaluation["fold_count"],
    }


def strategy_evaluation_root_hash(result: dict[str, object]) -> str:
    body = {
        "abstention_count": result["abstention_count"],
        "interpretation_hashes": [
            sha256_bytes(canonical_bytes(row))
            for row in result.get("interpretations", [])
            if isinstance(row, dict)
        ],
        "signal_count": result["signal_count"],
        "strategy_identity_hash": result["strategy_spec"]["strategy_identity_hash"],
    }
    return sha256_bytes(canonical_bytes(body))
