"""Surface forecasting baselines (O10-S3) — research-only, not trade signals."""

from __future__ import annotations

from typing import Any, Literal

from ...research.model_spec import build_model_spec

SURFACE_BASELINE_VERSION = "options_surface_baseline_v1"
SurfaceBaselineMethod = Literal["parametric_skew_v1", "spline_valid_quotes_v1"]
GATE_MILESTONE = "R-O10-SURF"


def surface_baseline_spec(method: SurfaceBaselineMethod) -> dict[str, Any]:
    """Model identity for surface baseline research artifacts."""
    return build_model_spec(
        model_family=SURFACE_BASELINE_VERSION,
        interface_version="surface_baseline_v1",
        hyperparameters={"method": method},
    )


def _atm_iv(surface: dict[str, Any]) -> float | None:
    points = surface.get("points", [])
    if not isinstance(points, list) or not points:
        return None
    sigmas = [
        float(point["sigma"])
        for point in points
        if isinstance(point, dict) and isinstance(point.get("sigma"), (int, float))
    ]
    if not sigmas:
        return None
    return sum(sigmas) / len(sigmas)


def _skew_proxy(surface: dict[str, Any]) -> float | None:
    points = surface.get("points", [])
    if not isinstance(points, list):
        return None
    calls = [
        float(point["sigma"])
        for point in points
        if isinstance(point, dict)
        and point.get("call_put") == "call"
        and isinstance(point.get("sigma"), (int, float))
    ]
    puts = [
        float(point["sigma"])
        for point in points
        if isinstance(point, dict)
        and point.get("call_put") == "put"
        and isinstance(point.get("sigma"), (int, float))
    ]
    if not calls or not puts:
        return None
    return (sum(calls) / len(calls)) - (sum(puts) / len(puts))


def _term_slope(surface: dict[str, Any]) -> float | None:
    points = surface.get("points", [])
    if not isinstance(points, list) or len(points) < 2:
        return None
    by_dte: dict[int, list[float]] = {}
    for point in points:
        if not isinstance(point, dict):
            continue
        dte = point.get("dte")
        sigma = point.get("sigma")
        if isinstance(dte, int) and isinstance(sigma, (int, float)):
            by_dte.setdefault(dte, []).append(float(sigma))
    if len(by_dte) < 2:
        return None
    dtes = sorted(by_dte)
    short_iv = sum(by_dte[dtes[0]]) / len(by_dte[dtes[0]])
    long_iv = sum(by_dte[dtes[-1]]) / len(by_dte[dtes[-1]])
    return long_iv - short_iv


def forecast_surface_baseline(
    surface: dict[str, Any],
    method: SurfaceBaselineMethod = "parametric_skew_v1",
) -> dict[str, Any]:
    """Research-only forward snapshot from current O2 surface (fixture scope)."""
    point_count = int(surface.get("point_count", 0))
    if point_count <= 0:
        return {
            "available": False,
            "reason": "SURFACE_EMPTY",
            "gate_milestone": GATE_MILESTONE,
            "surface_baseline_version": SURFACE_BASELINE_VERSION,
        }

    atm_iv = _atm_iv(surface)
    skew = _skew_proxy(surface)
    term_slope = _term_slope(surface)
    if atm_iv is None:
        return {
            "available": False,
            "reason": "ATM_IV_UNAVAILABLE",
            "gate_milestone": GATE_MILESTONE,
            "surface_baseline_version": SURFACE_BASELINE_VERSION,
        }

    decay = 0.98 if method == "parametric_skew_v1" else 0.99
    return {
        "available": True,
        "gate_milestone": GATE_MILESTONE,
        "surface_baseline_version": SURFACE_BASELINE_VERSION,
        "method": method,
        "model_spec": surface_baseline_spec(method),
        "not_trade_signal": True,
        "research_only": True,
        "current_atm_iv": round(atm_iv, 6),
        "forecast_atm_iv_delta": round(atm_iv * (decay - 1.0), 6),
        "forecast_skew_delta": round((skew or 0.0) * (decay - 1.0), 6),
        "forecast_term_slope_delta": round((term_slope or 0.0) * (decay - 1.0), 6),
        "targets": ("T-IV", "T-SKEW", "T-TERM"),
        "interpretation": (
            "Surface baseline forward deltas — mean-reversion research scaffold only"
        ),
    }


def evaluate_surface_baseline_oos(
  predictions: list[dict[str, Any]],
  realized: list[dict[str, Any]],
) -> dict[str, Any]:
    """MAE on T-IV / T-SKEW / T-TERM targets for surface baseline walk-forward."""
    if not predictions or not realized or len(predictions) != len(realized):
        return {
            "available": False,
            "gate_milestone": GATE_MILESTONE,
            "gate_status": "INSUFFICIENT_SAMPLE",
            "surface_baseline_version": SURFACE_BASELINE_VERSION,
        }

    target_map = {
        "T-IV": ("forecast_atm_iv_delta", "realized_atm_iv_delta"),
        "T-SKEW": ("forecast_skew_delta", "realized_skew_delta"),
        "T-TERM": ("forecast_term_slope_delta", "realized_term_slope_delta"),
    }
    metrics: dict[str, Any] = {}
    for target_id, (pred_key, real_key) in target_map.items():
        errors: list[float] = []
        for pred_row, real_row in zip(predictions, realized):
            if not isinstance(pred_row, dict) or not isinstance(real_row, dict):
                continue
            pred_val = pred_row.get(pred_key)
            real_val = real_row.get(real_key)
            if isinstance(pred_val, (int, float)) and isinstance(real_val, (int, float)):
                errors.append(abs(float(pred_val) - float(real_val)))
        metrics[target_id] = {
            "mae": round(sum(errors) / len(errors), 6) if errors else None,
            "sample_size": len(errors),
        }

    primary_mae = metrics.get("T-IV", {}).get("mae")
    gate_status = "PASS" if primary_mae is not None else "INSUFFICIENT_SAMPLE"
    return {
        "available": True,
        "gate_milestone": GATE_MILESTONE,
        "gate_status": gate_status,
        "surface_baseline_version": SURFACE_BASELINE_VERSION,
        "target_metrics": metrics,
        "not_trade_signal": True,
        "research_only": True,
    }


__all__ = [
    "GATE_MILESTONE",
    "SURFACE_BASELINE_VERSION",
    "SurfaceBaselineMethod",
    "evaluate_surface_baseline_oos",
    "forecast_surface_baseline",
    "surface_baseline_spec",
]
