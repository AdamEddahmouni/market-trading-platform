"""Load and validate calibration experiment definitions."""

from __future__ import annotations

import json
from pathlib import Path

from squeeze_core.research.serialization import deserialize_research_dataset

from .models import CalibrationExperiment, CalibrationExperimentType


class CalibrationExperimentError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


def load_experiment(path: Path) -> CalibrationExperiment:
    document = json.loads(path.read_text(encoding="utf-8"))
    experiment = CalibrationExperiment.model_validate(document)
    _validate_experiment(experiment)
    return experiment


def load_source_dataset(experiment: CalibrationExperiment, experiment_path: Path):
    dataset_path = (experiment_path.parent / experiment.source_dataset_path).resolve()
    if not dataset_path.exists():
        dataset_path = Path(experiment.source_dataset_path).resolve()
    if not dataset_path.exists():
        raise CalibrationExperimentError(
            "CALIBRATION_DATASET_NOT_FOUND",
            experiment.source_dataset_path,
        )
    return deserialize_research_dataset(dataset_path.read_bytes())


def _validate_experiment(experiment: CalibrationExperiment) -> None:
    variant_ids = {variant.variant_id for variant in experiment.variants}
    if len(variant_ids) != len(experiment.variants):
        raise CalibrationExperimentError("CALIBRATION_DUPLICATE_VARIANT_ID")
    if experiment.baseline_variant_id not in variant_ids:
        raise CalibrationExperimentError(
            "CALIBRATION_BASELINE_MISSING",
            experiment.baseline_variant_id,
        )
    for variant in experiment.variants:
        if experiment.experiment_type is CalibrationExperimentType.DETECTION_ABLATION:
            if variant.detection_policy is None:
                raise CalibrationExperimentError(
                    "CALIBRATION_VARIANT_MISSING_DETECTION_POLICY",
                    variant.variant_id,
                )
        if experiment.experiment_type is CalibrationExperimentType.OUTCOME_SENSITIVITY:
            if variant.outcome_policy is None:
                raise CalibrationExperimentError(
                    "CALIBRATION_VARIANT_MISSING_OUTCOME_POLICY",
                    variant.variant_id,
                )


__all__ = ["CalibrationExperimentError", "load_experiment", "load_source_dataset"]
