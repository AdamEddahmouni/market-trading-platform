"""Distributional and option-return baselines (O10-S4) — research-only."""

from __future__ import annotations

import math
from typing import Any, Literal, Sequence

from ...research.distribution.forecast import physical_distribution_forecast
from ...research.model_spec import build_model_spec

DISTRIBUTIONAL_BASELINE_VERSION = "options_distributional_baseline_v1"
DistributionalBaselineMethod = Literal["quantile_regression_v1", "skewed_t_v1", "physical_p_anchor"]
GATE_MILESTONE_R_O5 = "R-O5"


def distributional_baseline_spec(
    method: DistributionalBaselineMethod,
) -> dict[str, Any]:
    return build_model_spec(
        model_family=DISTRIBUTIONAL_BASELINE_VERSION,
        interface_version="distributional_baseline_v1",
        hyperparameters={"method": method},
    )


def _qlike(realized: float, forecast: float) -> float | None:
    if realized <= 0 or forecast <= 0:
        return None
    ratio = realized / forecast
    return ratio - math.log(ratio) - 1.0


def _crps_gaussian(forecast_mean: float, forecast_std: float, realized: float) -> float:
    if forecast_std <= 0:
        return abs(realized - forecast_mean)
    z = (realized - forecast_mean) / forecast_std
    pdf = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return forecast_std * (z * (2.0 * cdf - 1.0) + 2.0 * pdf - 1.0 / math.sqrt(math.pi))


def forecast_distributional_baseline(
    closes: Sequence[float],
    *,
    symbol: str,
    as_of_time: str,
    method: DistributionalBaselineMethod = "physical_p_anchor",
) -> dict[str, Any]:
    """Baseline distributional forecast — Gaussian v1 fallback per SHARED P2."""
    if len(closes) < 5:
        return {
            "available": False,
            "reason": "INSUFFICIENT_CLOSES",
            "gate_milestone": GATE_MILESTONE_R_O5,
            "distributional_baseline_version": DISTRIBUTIONAL_BASELINE_VERSION,
        }

    forecast = physical_distribution_forecast(
        closes,
        symbol=symbol,
        as_of_time=as_of_time,
        model="ewma",
    )
    if forecast is None:
        return {
            "available": False,
            "reason": "PHYSICAL_P_FORECAST_FAILED",
            "gate_milestone": GATE_MILESTONE_R_O5,
            "distributional_baseline_version": DISTRIBUTIONAL_BASELINE_VERSION,
        }

    vol = forecast.vol_forecast_annualized
    return {
        "available": True,
        "gate_milestone": GATE_MILESTONE_R_O5,
        "distributional_baseline_version": DISTRIBUTIONAL_BASELINE_VERSION,
        "method": method,
        "model_spec": distributional_baseline_spec(method),
        "vol_forecast_annualized": round(vol, 6),
        "realized_vol_close_to_close": round(forecast.realized_vol_close_to_close, 6),
        "not_trade_signal": True,
        "research_only": True,
        "interpretation": (
            "Distributional baseline anchored on SHARED P2 physical P — "
            "quantile/skewed-t stubs use Gaussian v1 fallback"
        ),
    }


def evaluate_p_baseline_oos(
    predictions: list[float],
    realized: list[float],
    *,
    naive_predictions: list[float] | None = None,
) -> dict[str, Any]:
    """QLIKE / CRPS vs naive last-value for R-O5 gate machinery."""
    if not predictions or not realized or len(predictions) != len(realized):
        return {
            "available": False,
            "gate_milestone": GATE_MILESTONE_R_O5,
            "gate_status": "INSUFFICIENT_SAMPLE",
            "distributional_baseline_version": DISTRIBUTIONAL_BASELINE_VERSION,
        }

    qlike_scores = [
        score
        for pred, real in zip(predictions, realized)
        if (score := _qlike(float(real), float(pred))) is not None
    ]
    crps_scores = [
        _crps_gaussian(0.0, max(float(pred), 1e-8), float(real))
        for pred, real in zip(predictions, realized)
    ]
    naive_qlike_scores: list[float] = []
    if naive_predictions and len(naive_predictions) == len(realized):
        naive_qlike_scores = [
            score
            for pred, real in zip(naive_predictions, realized)
            if (score := _qlike(float(real), float(pred))) is not None
        ]

    mean_qlike = sum(qlike_scores) / len(qlike_scores) if qlike_scores else None
    mean_crps = sum(crps_scores) / len(crps_scores) if crps_scores else None
    naive_mean_qlike = (
        sum(naive_qlike_scores) / len(naive_qlike_scores) if naive_qlike_scores else None
    )

    gate_status = "INSUFFICIENT_SAMPLE"
    if mean_qlike is not None and naive_mean_qlike is not None:
        gate_status = "PASS" if mean_qlike < naive_mean_qlike else "FAIL"
    elif mean_qlike is not None:
        gate_status = "PASS"

    return {
        "available": True,
        "gate_milestone": GATE_MILESTONE_R_O5,
        "gate_status": gate_status,
        "distributional_baseline_version": DISTRIBUTIONAL_BASELINE_VERSION,
        "mean_qlike": round(mean_qlike, 6) if mean_qlike is not None else None,
        "mean_crps": round(mean_crps, 6) if mean_crps is not None else None,
        "naive_mean_qlike": (
            round(naive_mean_qlike, 6) if naive_mean_qlike is not None else None
        ),
        "sample_size": len(qlike_scores),
        "not_trade_signal": True,
        "research_only": True,
    }


def option_return_linear_factors(
    *,
    delta: float,
    vega: float,
    vol_exposure: float,
) -> dict[str, Any]:
    """Linear factor exposure model spec for T-OPT target — research only."""
    spec = build_model_spec(
        model_family="options_option_return_linear_v1",
        interface_version="option_return_factors_v1",
        hyperparameters={
            "delta_weight": 1.0,
            "vega_weight": 1.0,
            "vol_weight": 1.0,
        },
    )
    expected_return_proxy = delta * 0.01 + vega * 0.001 + vol_exposure * 0.005
    return {
        "available": True,
        "target_id": "T-OPT",
        "model_spec": spec,
        "delta_exposure": round(delta, 6),
        "vega_exposure": round(vega, 6),
        "vol_exposure": round(vol_exposure, 6),
        "expected_return_proxy": round(expected_return_proxy, 6),
        "not_trade_signal": True,
        "research_only": True,
        "interpretation": (
            "Linear option-return factor decomposition — research scaffold, no strategy ranking"
        ),
    }


__all__ = [
    "DISTRIBUTIONAL_BASELINE_VERSION",
    "DistributionalBaselineMethod",
    "GATE_MILESTONE_R_O5",
    "distributional_baseline_spec",
    "evaluate_p_baseline_oos",
    "forecast_distributional_baseline",
    "option_return_linear_factors",
]
