"""Distillation dataset construction (BUILD 18)."""

from __future__ import annotations

from typing import Any

from ...baselines.features import BaselineFeatureSchema
from ...baselines.training import BaselineTrainingExample, build_training_dataset
from ...baselines.types import BaselineClassLabel, BaselineFeatureVector
from ...contracts.common import ForecastTarget
from ..identity import derive_distillation_dataset_id, derive_training_dataset_fingerprint, derive_training_dataset_id
from ..types import (
    DistillationDatasetManifestV1,
    DistillationTargetKind,
    PreparedTrainingDataset,
    SupervisionKind,
    TeacherOutputV1,
    TrainingDatasetManifestV1,
    TrainingDatasetMode,
    TrainingExampleRef,
    TRAINING_IMPLEMENTATION_VERSION,
)
from .teacher import TeacherProvider


def build_distillation_dataset(
    *,
    experiment_id: str,
    teacher: TeacherProvider,
    input_examples: list[tuple[str, int, BaselineFeatureVector, int]],
    feature_schema: BaselineFeatureSchema,
    target: ForecastTarget,
    training_cutoff_ns: int,
    development_start_ns: int,
    development_end_ns: int,
    mode: str,
    horizon_ns: int,
) -> tuple[PreparedTrainingDataset, DistillationDatasetManifestV1]:
    """Build distillation dataset with teacher soft targets (not market OutcomeV1)."""
    teacher_outputs: list[TeacherOutputV1] = []
    training_examples: list[BaselineTrainingExample] = []
    distillation_targets: dict[str, float] = {}
    fingerprint_rows: list[dict[str, Any]] = []
    refs: list[TrainingExampleRef] = []

    for snapshot_id, decision_time_ns, feature_vector, availability_time_ns in input_examples:
        if availability_time_ns > training_cutoff_ns:
            raise ValueError("FUTURE_TEACHER_OUTPUT_REJECTED")
        input_ref = f"{snapshot_id}:{decision_time_ns}"
        teacher_output = teacher.produce(
            input_ref=input_ref,
            features=feature_vector.values,
            availability_time_ns=availability_time_ns,
        )
        teacher_outputs.append(teacher_output)
        p_up = float(teacher_output.output["p_up"])
        label = BaselineClassLabel.UP if p_up >= 0.5 else BaselineClassLabel.DOWN
        training_examples.append(
            BaselineTrainingExample(
                snapshot_id=snapshot_id,
                decision_time_ns=decision_time_ns,
                feature_vector=feature_vector,
                label=label,
                label_available_time_ns=availability_time_ns,
                label_provenance="TEACHER_TARGET",
            )
        )
        distillation_targets[input_ref] = p_up
        refs.append(
            TrainingExampleRef(
                snapshot_id=snapshot_id,
                decision_time_ns=decision_time_ns,
                teacher_output_ref=str(teacher_output.output.get("output_ref")),
            )
        )
        fingerprint_rows.append(
            {
                "snapshot_id": snapshot_id,
                "decision_time_ns": decision_time_ns,
                "feature_values": list(feature_vector.values),
                "feature_keys": list(feature_vector.feature_keys),
                "label": label.value,
                "label_available_time_ns": availability_time_ns,
                "label_provenance": "TEACHER_TARGET",
                "teacher_output": teacher_output.output,
                "teacher_id": teacher.teacher_id,
                "teacher_version": teacher.teacher_version,
            }
        )

    baseline_dataset = build_training_dataset(
        raw_examples=training_examples,
        feature_schema=feature_schema,
        target=target,
        training_cutoff_ns=training_cutoff_ns,
    )
    dataset_fp = derive_training_dataset_fingerprint(
        feature_schema_fingerprint=feature_schema.fingerprint,
        target_kind=target.target_kind,
        horizon_ns=horizon_ns,
        mode=mode,
        training_cutoff_ns=training_cutoff_ns,
        development_start_ns=development_start_ns,
        development_end_ns=development_end_ns,
        supervision_kind=SupervisionKind.TEACHER_TARGET.value,
        examples=fingerprint_rows,
        teacher_identity=teacher.teacher_id,
        teacher_version=teacher.teacher_version,
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
        supervision_kind=SupervisionKind.TEACHER_TARGET,
        dataset_mode=TrainingDatasetMode.DISTILLATION,
        teacher_identity=teacher.teacher_id,
        teacher_version=teacher.teacher_version,
        builder_version=TRAINING_IMPLEMENTATION_VERSION,
    )
    distillation_id = derive_distillation_dataset_id(
        experiment_id=experiment_id,
        teacher_id=teacher.teacher_id,
        teacher_version=teacher.teacher_version,
        dataset_fingerprint=dataset_fp,
    )
    distillation_manifest = DistillationDatasetManifestV1(
        distillation_dataset_id=distillation_id,
        schema_version="1",
        experiment_id=experiment_id,
        training_dataset_id=dataset_id,
        teacher_id=teacher.teacher_id,
        teacher_version=teacher.teacher_version,
        target_kind=DistillationTargetKind.TEACHER_PROBABILITIES,
        example_count=len(baseline_dataset.examples),
        dataset_fingerprint=dataset_fp,
        teacher_output_refs=tuple(
            sorted(str(output.output.get("output_ref", "")) for output in teacher_outputs)
        ),
    )
    return (
        PreparedTrainingDataset(
            manifest=manifest,
            baseline_dataset=baseline_dataset,
            distillation_targets=distillation_targets,
        ),
        distillation_manifest,
    )


__all__ = ["build_distillation_dataset"]
