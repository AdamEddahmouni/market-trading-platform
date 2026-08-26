"""Label availability and probability extraction (BUILD 16)."""

from __future__ import annotations

from ..contracts.common import Direction, OutcomeResolutionStatus, validate_probability
from ..contracts.forecast import ForecastV1
from ..contracts.outcome import OutcomeV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..fusion.types import FINAL_FORECAST_STAGE
from .errors import EvaluationError
from .types import ProbabilityView


def label_available_time_ns(
    outcome: OutcomeV1 | None,
    ledger_entry: PredictionLedgerEntryV1,
) -> int | None:
    if outcome is None:
        return None
    end_obs = outcome.end_observation
    stored = end_obs.get("label_available_time_ns")
    if stored is not None:
        return int(stored)
    return ledger_entry.availability_cutoff_ns


def binary_label_from_outcome(outcome: OutcomeV1) -> int | None:
    if outcome.resolution_status != OutcomeResolutionStatus.SETTLED:
        return None
    direction = outcome.realized_direction
    if direction is None:
        return None
    if direction == Direction.LONG:
        return 1
    if direction == Direction.SHORT:
        return 0
    return None


def predicted_direction_from_forecast(forecast: ForecastV1, probability: float) -> Direction:
    stored = forecast.metadata.get("predicted_direction")
    if stored is not None:
        text = str(stored)
        if text in {"UP", "LONG"}:
            return Direction.LONG
        if text in {"DOWN", "SHORT"}:
            return Direction.SHORT
    if probability > 0.5:
        return Direction.LONG
    if probability < 0.5:
        return Direction.SHORT
    return Direction.NEUTRAL


def extract_probabilities(forecast: ForecastV1) -> tuple[float | None, float | None, float | None]:
    estimate = forecast.estimate
    raw = estimate.probability
    calibrated = estimate.calibrated_probability
    operational = _operational_probability(forecast, raw=raw, calibrated=calibrated)
    return raw, calibrated, operational


def probability_for_view(
    forecast: ForecastV1,
    view: ProbabilityView,
) -> float | None:
    raw, calibrated, operational = extract_probabilities(forecast)
    if view == ProbabilityView.RAW:
        return raw
    if view == ProbabilityView.CALIBRATED:
        return calibrated
    return operational


def validate_evaluated_probability(value: float) -> float:
    try:
        validate_probability(value)
    except ValueError as exc:
        raise EvaluationError("MALFORMED_PROBABILITY", details={"reason": str(exc)}) from exc
    return float(value)


def _operational_probability(
    forecast: ForecastV1,
    *,
    raw: float | None,
    calibrated: float | None,
) -> float | None:
    stage = forecast.metadata.get("forecast_stage")
    if stage == FINAL_FORECAST_STAGE and calibrated is not None:
        return calibrated
    if calibrated is not None:
        return calibrated
    return raw


__all__ = [
    "binary_label_from_outcome",
    "extract_probabilities",
    "label_available_time_ns",
    "predicted_direction_from_forecast",
    "probability_for_view",
    "validate_evaluated_probability",
]
