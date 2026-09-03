"""Development dataset materialization (BUILD 18)."""

from __future__ import annotations

import math
from typing import Any

from ..baselines.features import BaselineFeatureSchema, DEFAULT_STATISTICAL_FEATURE_SCHEMA, FeatureVectorBuilder
from ..baselines.training import BaselineTrainingDataset, BaselineTrainingExample, build_training_dataset
from ..baselines.types import BaselineClassLabel
from ..contracts.common import Direction, ForecastTarget, OutcomeResolutionStatus, TimeHorizonNs
from ..evaluation.cohort import materialize_cohort
from ..evaluation.provenance import binary_label_from_outcome, label_available_time_ns
from ..evaluation.types import EvaluationSpec, ProbabilityView
from ..persistence.repository import IntelligenceRepository
from ..research_experiments.types import ExperimentManifestV1
from .authorization import holdout_boundary_ns
from .errors import TrainingFactoryError
from .identity import derive_training_dataset_fingerprint, derive_training_dataset_id
from .types import (
    PreparedTrainingDataset,
    SupervisionKind,
    TrainingDatasetManifestV1,
    TrainingDatasetMode,
    TrainingExampleRef,
    TRAINING_IMPLEMENTATION_VERSION,
)


def materialize_development_dataset(
    repository: IntelligenceRepository,
    manifest: ExperimentManifestV1,
    *,
    feature_schema: BaselineFeatureSchema | None = None,
    training_cutoff_ns: int | None = None,
    target: ForecastTarget | None = None,
) -> PreparedTrainingDataset:
    schema = feature_schema or DEFAULT_STATISTICAL_FEATURE_SCHEMA
    data_spec = manifest.data_spec
    cutoff = training_cutoff_ns if training_cutoff_ns is not None else data_spec.decision_end_ns
    holdout_start = holdout_boundary_ns(manifest)

    eval_spec = EvaluationSpec(
        evaluation_as_of_ns=cutoff,
        decision_start_ns=data_spec.decision_start_ns,
        decision_end_ns=data_spec.decision_end_ns,
        target_kind=data_spec.target_kind,
        horizon_ns=data_spec.horizon_ns,
        mode=data_spec.mode,
        probability_view=ProbabilityView.RAW,
        scenario_id=data_spec.scenario_id,
    )
    cohort_rows = materialize_cohort(repository, eval_spec)

    raw_examples: list[BaselineTrainingExample] = []
    example_refs: list[TrainingExampleRef] = []
    fingerprint_rows: list[dict[str, Any]] = []

    for row in cohort_rows:
        forecast = row.forecast
        if forecast.decision_time_ns < data_spec.decision_start_ns:
            continue
        if forecast.decision_time_ns > data_spec.decision_end_ns:
            continue
        if holdout_start is not None and forecast.decision_time_ns >= holdout_start:
            continue
        if row.outcome is None:
            continue
        if row.outcome.resolution_status != OutcomeResolutionStatus.SETTLED:
            continue
        label_time = row.label_available_time_ns
        if label_time is None:
            continue
        if label_time > cutoff:
            raise TrainingFactoryError(
                "FUTURE_LABEL_REJECTED",
                details={
                    "forecast_id": forecast.forecast_id,
                    "label_available_time_ns": label_time,
                    "training_cutoff_ns": cutoff,
                },
            )
        binary = binary_label_from_outcome(row.outcome)
        if binary is None:
            continue
        label = BaselineClassLabel.UP if binary == Direction.UP else BaselineClassLabel.DOWN

        snapshot = repository.get_snapshot(forecast.snapshot_id)
        if snapshot is None:
            continue
        instrument_id = (
            snapshot.scope.instrument_ids[0] if snapshot.scope.instrument_ids else None
        )
        signals = repository.query_signals_as_of(
            snapshot.decision_time_ns,
            instrument_id=instrument_id,
        )
        vector, diagnostics = FeatureVectorBuilder(schema).extract(snapshot, signals)
        if vector is None:
            codes = ", ".join(item.code.value for item in diagnostics)
            raise TrainingFactoryError(
                "MISSING_FEATURE",
                details={"snapshot_id": snapshot.snapshot_id, "codes": codes},
            )
        for value in vector.values:
            if not math.isfinite(value):
                raise TrainingFactoryError(
                    "NONFINITE_FEATURE",
                    details={"snapshot_id": snapshot.snapshot_id},
                )

        example = BaselineTrainingExample(
            snapshot_id=snapshot.snapshot_id,
            decision_time_ns=snapshot.decision_time_ns,
            feature_vector=vector,
            label=label,
            label_available_time_ns=label_time,
            source_signal_refs=tuple(signal.signal_id for signal in vector.source_signals),
            label_provenance="OUTCOME_LABEL",
        )
        raw_examples.append(example)
        example_refs.append(
            TrainingExampleRef(
                snapshot_id=snapshot.snapshot_id,
                decision_time_ns=snapshot.decision_time_ns,
                outcome_id=row.outcome.outcome_id,
                forecast_id=forecast.forecast_id,
            )
        )
        fingerprint_rows.append(
            {
                "snapshot_id": snapshot.snapshot_id,
                "decision_time_ns": snapshot.decision_time_ns,
                "feature_values": list(vector.values),
                "feature_keys": list(vector.feature_keys),
                "label": label.value,
                "label_available_time_ns": label_time,
                "label_provenance": "OUTCOME_LABEL",
            }
        )

    if not raw_examples:
        raise TrainingFactoryError("TRAINING_DATASET_EMPTY")

    forecast_target = target or ForecastTarget(
        target_kind=data_spec.target_kind,
        instrument_id=data_spec.instrument_ids[0] if data_spec.instrument_ids else "unknown",
    )

    baseline_dataset = build_training_dataset(
        raw_examples=raw_examples,
        feature_schema=schema,
        target=forecast_target,
        training_cutoff_ns=cutoff,
    )

    dataset_fp = derive_training_dataset_fingerprint(
        feature_schema_fingerprint=schema.fingerprint,
        target_kind=data_spec.target_kind,
        horizon_ns=data_spec.horizon_ns,
        mode=data_spec.mode,
        training_cutoff_ns=cutoff,
        development_start_ns=data_spec.decision_start_ns,
        development_end_ns=data_spec.decision_end_ns,
        supervision_kind=SupervisionKind.OUTCOME_LABEL.value,
        examples=fingerprint_rows,
        quality_policy=tuple(data_spec.quality_requirements),
    )
    dataset_id = derive_training_dataset_id(manifest.experiment_id, dataset_fp)

    dataset_manifest = TrainingDatasetManifestV1(
        training_dataset_id=dataset_id,
        schema_version="1",
        experiment_id=manifest.experiment_id,
        development_start_ns=data_spec.decision_start_ns,
        development_end_ns=data_spec.decision_end_ns,
        training_cutoff_ns=cutoff,
        target_kind=data_spec.target_kind,
        horizon_ns=data_spec.horizon_ns,
        mode=data_spec.mode,
        feature_schema_fingerprint=schema.fingerprint,
        example_count=len(baseline_dataset.examples),
        example_refs=tuple(
            sorted(example_refs, key=lambda ref: (ref.decision_time_ns, ref.snapshot_id))
        ),
        dataset_fingerprint=dataset_fp,
        supervision_kind=SupervisionKind.OUTCOME_LABEL,
        dataset_mode=TrainingDatasetMode.SUPERVISED,
        scenario_id=data_spec.scenario_id,
        quality_policy=tuple(data_spec.quality_requirements),
        holdout_boundary_ns=holdout_start,
        builder_version=TRAINING_IMPLEMENTATION_VERSION,
    )
    return PreparedTrainingDataset(manifest=dataset_manifest, baseline_dataset=baseline_dataset)


def build_dataset_from_examples(
    *,
    experiment_id: str,
    examples: list[BaselineTrainingExample],
    feature_schema: BaselineFeatureSchema,
    target: ForecastTarget,
    training_cutoff_ns: int,
    development_start_ns: int,
    development_end_ns: int,
    mode: str = "ACTUAL_LIVE",
    horizon_ns: int,
    supervision_kind: SupervisionKind = SupervisionKind.OUTCOME_LABEL,
) -> PreparedTrainingDataset:
    """Deterministic dataset builder for tests and synthetic vertical slices."""
    baseline_dataset = build_training_dataset(
        raw_examples=examples,
        feature_schema=feature_schema,
        target=target,
        training_cutoff_ns=training_cutoff_ns,
    )
    fingerprint_rows = []
    refs = []
    for example in baseline_dataset.examples:
        fingerprint_rows.append(
            {
                "snapshot_id": example.snapshot_id,
                "decision_time_ns": example.decision_time_ns,
                "feature_values": list(example.feature_vector.values),
                "feature_keys": list(example.feature_vector.feature_keys),
                "label": example.label.value,
                "label_available_time_ns": example.label_available_time_ns,
                "label_provenance": example.label_provenance or supervision_kind.value,
            }
        )
        refs.append(
            TrainingExampleRef(
                snapshot_id=example.snapshot_id,
                decision_time_ns=example.decision_time_ns,
            )
        )
    dataset_fp = derive_training_dataset_fingerprint(
        feature_schema_fingerprint=feature_schema.fingerprint,
        target_kind=target.target_kind,
        horizon_ns=horizon_ns,
        mode=mode,
        training_cutoff_ns=training_cutoff_ns,
        development_start_ns=development_start_ns,
        development_end_ns=development_end_ns,
        supervision_kind=supervision_kind.value,
        examples=fingerprint_rows,
    )
    dataset_id = derive_training_dataset_id(experiment_id, dataset_fp)
    manifest = TrainingDatasetManifestV1(
        training_dataset_id=dataset_id,
        schema_version="1",
        experiment_id=experiment_id,
        development_start_ns=development_start_ns,
        development_end_ns=development_end_ns,
        training_cutoff_ns=training_cutoff_ns,
        target_kind=target.target_kind,
        horizon_ns=horizon_ns,
        mode=mode,
        feature_schema_fingerprint=feature_schema.fingerprint,
        example_count=len(baseline_dataset.examples),
        example_refs=tuple(sorted(refs, key=lambda ref: (ref.decision_time_ns, ref.snapshot_id))),
        dataset_fingerprint=dataset_fp,
        supervision_kind=supervision_kind,
    )
    return PreparedTrainingDataset(manifest=manifest, baseline_dataset=baseline_dataset)


__all__ = [
    "build_dataset_from_examples",
    "materialize_development_dataset",
]
