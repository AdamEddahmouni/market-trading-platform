"""Calibration dataset construction for BUILD 14."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.common import ForecastTarget, TimeHorizonNs, forecast_target_to_dict, time_horizon_to_dict
from .errors import CalibrationTrainingError
from .identity import derive_calibration_dataset_id
from .types import CalibrationDataset, CalibrationExample

MINIMUM_CALIBRATION_SAMPLES = 20
MINIMUM_CLASS_COUNT = 5


@dataclass(frozen=True, slots=True)
class CalibrationDatasetBuilder:
    def build(
        self,
        examples: list[CalibrationExample],
        *,
        target: ForecastTarget,
        horizon: TimeHorizonNs,
        fusion_policy_identity: str,
        calibration_cutoff_ns: int,
        regime_key: str | None = None,
    ) -> CalibrationDataset:
        normalized = _normalize_examples(examples, calibration_cutoff_ns=calibration_cutoff_ns, horizon=horizon)
        dataset_id = derive_calibration_dataset_id(
            examples=normalized,
            target=target,
            horizon=horizon,
            fusion_policy_identity=fusion_policy_identity,
            calibration_cutoff_ns=calibration_cutoff_ns,
            regime_key=regime_key,
        )
        return CalibrationDataset(
            dataset_id=dataset_id,
            examples=normalized,
            target=target,
            horizon=horizon,
            fusion_policy_identity=fusion_policy_identity,
            calibration_cutoff_ns=calibration_cutoff_ns,
            regime_key=regime_key,
        )


def _normalize_examples(
    examples: list[CalibrationExample],
    *,
    calibration_cutoff_ns: int,
    horizon: TimeHorizonNs,
) -> tuple[CalibrationExample, ...]:
    by_id: dict[str, CalibrationExample] = {}
    for example in examples:
        if example.label_available_time_ns <= example.forecast_decision_time_ns:
            raise CalibrationTrainingError("LABEL_AVAILABLE_BEFORE_FORECAST")
        if example.label_available_time_ns < example.forecast_decision_time_ns + horizon.duration_ns:
            raise CalibrationTrainingError("LABEL_AVAILABLE_BEFORE_HORIZON_COMPLETION")
        if example.label_available_time_ns > calibration_cutoff_ns:
            raise CalibrationTrainingError("FUTURE_LABEL_PAST_CUTOFF")
        if example.label not in (0, 1):
            raise CalibrationTrainingError("INVALID_LABEL")
        existing = by_id.get(example.raw_fusion_id)
        if existing is not None:
            if (
                existing.label != example.label
                or existing.raw_probability != example.raw_probability
                or existing.label_available_time_ns != example.label_available_time_ns
            ):
                raise CalibrationTrainingError(f"DUPLICATE_CONFLICT:{example.raw_fusion_id}")
            continue
        by_id[example.raw_fusion_id] = example
    return tuple(sorted(by_id.values(), key=lambda row: row.raw_fusion_id))


def dataset_support_summary(dataset: CalibrationDataset) -> dict[str, int]:
    class_counts = {"0": 0, "1": 0}
    for example in dataset.examples:
        class_counts[str(example.label)] += 1
    return {
        "sample_count": len(dataset.examples),
        "class_0": class_counts["0"],
        "class_1": class_counts["1"],
    }


def targets_equal(left: ForecastTarget, right: ForecastTarget) -> bool:
    return forecast_target_to_dict(left) == forecast_target_to_dict(right)


def horizons_equal(left: TimeHorizonNs, right: TimeHorizonNs) -> bool:
    return time_horizon_to_dict(left) == time_horizon_to_dict(right)


__all__ = [
    "MINIMUM_CALIBRATION_SAMPLES",
    "MINIMUM_CLASS_COUNT",
    "CalibrationDatasetBuilder",
    "dataset_support_summary",
    "horizons_equal",
    "targets_equal",
]
