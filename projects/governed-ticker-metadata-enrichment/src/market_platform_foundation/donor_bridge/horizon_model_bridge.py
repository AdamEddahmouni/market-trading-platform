"""Build HorizonModelSnapshot for donor causal evaluator from fixture adjudicated rows."""

from __future__ import annotations

from typing import Any

from ..options.features.squeeze_context import augment_features_with_context, build_squeeze_context_for_options
from ..research.squeeze_models.harness import load_mechanism_dataset, run_squeeze_walk_forward_harness
from ..research.squeeze_models.magnitude import predict_squeeze_magnitude
from ..research.squeeze_models.rare_event_ensemble import predict_squeeze_ensemble


def _matching_mechanism_row(
    *,
    symbol: str,
    prediction_cutoff: int | None,
) -> dict[str, Any] | None:
    symbol_upper = symbol.strip().upper()
    for row in load_mechanism_dataset():
        if str(row.get("symbol", "")).upper() != symbol_upper:
            continue
        cutoff = row.get("prediction_cutoff")
        if prediction_cutoff is not None and isinstance(cutoff, int) and cutoff != prediction_cutoff:
            continue
        return row
    return None


def build_horizon_model_snapshot(
    *,
    symbol: str,
    row: dict[str, Any] | None = None,
    prediction_cutoff: int | None = None,
    squeeze_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build calibrated horizon model payload when walk-forward PIT harness passes."""
    harness = run_squeeze_walk_forward_harness()
    if harness.get("pit_status") != "PASS":
        return None

    mechanism_row = row if isinstance(row, dict) else None
    if mechanism_row is None:
        mechanism_row = _matching_mechanism_row(
            symbol=symbol,
            prediction_cutoff=prediction_cutoff,
        )
    if mechanism_row is None:
        return None

    features = mechanism_row.get("features", [])
    if not isinstance(features, list):
        return None

    physical_forecast = mechanism_row.get("physical_forecast")
    context = squeeze_context
    if context is None:
        context = mechanism_row.get("squeeze_context")
    if context is None and isinstance(row, dict):
        causal = row.get("causal_intelligence")
        if isinstance(causal, dict):
            context = build_squeeze_context_for_options(causal)

    augmented = augment_features_with_context(
        features,
        squeeze_context=context if isinstance(context, dict) else None,
        physical_forecast=physical_forecast if isinstance(physical_forecast, dict) else None,
    )
    ensemble = predict_squeeze_ensemble(augmented)
    magnitude = predict_squeeze_magnitude(
        features,
        squeeze_context=context if isinstance(context, dict) else None,
        physical_forecast=physical_forecast if isinstance(physical_forecast, dict) else None,
    )

    return {
        "model_version": ensemble["model_version"],
        "status": "CALIBRATED",
        "pit_verified": True,
        "occurrence_probability": ensemble["occurrence_probability"],
        "hazard_by_horizon": ensemble["hazard_by_horizon"],
        "magnitude": magnitude,
    }


__all__ = ["build_horizon_model_snapshot"]
