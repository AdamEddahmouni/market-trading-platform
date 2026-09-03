"""Serialization for BUILD 18 training artifacts."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from .types import (
    CandidateArtifactV1,
    CandidateStatus,
    DistillationDatasetManifestV1,
    DistillationTargetKind,
    SupervisionKind,
    TrainerKind,
    TrainingDatasetManifestV1,
    TrainingDatasetMode,
    TrainingDiagnostics,
    TrainingExampleRef,
    TrainingRunManifestV1,
    TrainingRunStatus,
)


def _example_ref_to_dict(ref: TrainingExampleRef) -> dict[str, Any]:
    body: dict[str, Any] = {
        "snapshot_id": ref.snapshot_id,
        "decision_time_ns": ref.decision_time_ns,
    }
    if ref.outcome_id is not None:
        body["outcome_id"] = ref.outcome_id
    if ref.forecast_id is not None:
        body["forecast_id"] = ref.forecast_id
    if ref.teacher_output_ref is not None:
        body["teacher_output_ref"] = ref.teacher_output_ref
    return body


def _example_ref_from_dict(payload: dict[str, Any]) -> TrainingExampleRef:
    return TrainingExampleRef(
        snapshot_id=str(payload["snapshot_id"]),
        decision_time_ns=int(payload["decision_time_ns"]),
        outcome_id=payload.get("outcome_id"),
        forecast_id=payload.get("forecast_id"),
        teacher_output_ref=payload.get("teacher_output_ref"),
    )


def training_dataset_manifest_v1_to_dict(record: TrainingDatasetManifestV1) -> dict[str, Any]:
    return {
        "training_dataset_id": record.training_dataset_id,
        "schema_version": record.schema_version,
        "experiment_id": record.experiment_id,
        "development_start_ns": record.development_start_ns,
        "development_end_ns": record.development_end_ns,
        "training_cutoff_ns": record.training_cutoff_ns,
        "target_kind": record.target_kind,
        "horizon_ns": record.horizon_ns,
        "mode": record.mode,
        "feature_schema_fingerprint": record.feature_schema_fingerprint,
        "example_count": record.example_count,
        "example_refs": [_example_ref_to_dict(ref) for ref in record.example_refs],
        "dataset_fingerprint": record.dataset_fingerprint,
        "supervision_kind": record.supervision_kind.value,
        "dataset_mode": record.dataset_mode.value,
        "scenario_id": record.scenario_id,
        "quality_policy": list(record.quality_policy),
        "source_artifact_refs": list(record.source_artifact_refs),
        "builder_version": record.builder_version,
        "holdout_boundary_ns": record.holdout_boundary_ns,
        "teacher_identity": record.teacher_identity,
        "teacher_version": record.teacher_version,
        "metadata": dict(record.metadata),
    }


def training_dataset_manifest_v1_from_dict(payload: dict[str, Any]) -> TrainingDatasetManifestV1:
    return TrainingDatasetManifestV1(
        training_dataset_id=str(payload["training_dataset_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        experiment_id=str(payload["experiment_id"]),
        development_start_ns=int(payload["development_start_ns"]),
        development_end_ns=int(payload["development_end_ns"]),
        training_cutoff_ns=int(payload["training_cutoff_ns"]),
        target_kind=str(payload["target_kind"]),
        horizon_ns=int(payload["horizon_ns"]),
        mode=str(payload["mode"]),
        feature_schema_fingerprint=str(payload["feature_schema_fingerprint"]),
        example_count=int(payload["example_count"]),
        example_refs=tuple(
            _example_ref_from_dict(item) for item in (payload.get("example_refs") or [])
        ),
        dataset_fingerprint=str(payload["dataset_fingerprint"]),
        supervision_kind=SupervisionKind(payload["supervision_kind"]),
        dataset_mode=TrainingDatasetMode(payload.get("dataset_mode", "SUPERVISED")),
        scenario_id=payload.get("scenario_id"),
        quality_policy=tuple(payload.get("quality_policy") or ()),
        source_artifact_refs=tuple(payload.get("source_artifact_refs") or ()),
        builder_version=str(payload.get("builder_version", "training-distillation-factory-v1")),
        holdout_boundary_ns=payload.get("holdout_boundary_ns"),
        teacher_identity=payload.get("teacher_identity"),
        teacher_version=payload.get("teacher_version"),
        metadata=dict(payload.get("metadata") or {}),
    )


def _diagnostics_to_dict(diag: TrainingDiagnostics) -> dict[str, Any]:
    body: dict[str, Any] = {
        "example_count": diag.example_count,
        "up_count": diag.up_count,
        "down_count": diag.down_count,
    }
    if diag.training_loss is not None:
        body["training_loss"] = diag.training_loss
    if diag.teacher_target_loss is not None:
        body["teacher_target_loss"] = diag.teacher_target_loss
    if diag.convergence_status is not None:
        body["convergence_status"] = diag.convergence_status
    if diag.iterations is not None:
        body["iterations"] = diag.iterations
    if diag.parameter_norm is not None:
        body["parameter_norm"] = diag.parameter_norm
    if diag.extra:
        body["extra"] = dict(diag.extra)
    return body


def _diagnostics_from_dict(payload: dict[str, Any] | None) -> TrainingDiagnostics | None:
    if payload is None:
        return None
    return TrainingDiagnostics(
        example_count=int(payload["example_count"]),
        up_count=int(payload.get("up_count", 0)),
        down_count=int(payload.get("down_count", 0)),
        training_loss=payload.get("training_loss"),
        teacher_target_loss=payload.get("teacher_target_loss"),
        convergence_status=payload.get("convergence_status"),
        iterations=payload.get("iterations"),
        parameter_norm=payload.get("parameter_norm"),
        extra=dict(payload.get("extra") or {}),
    )


def training_run_manifest_v1_to_dict(record: TrainingRunManifestV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "training_run_id": record.training_run_id,
        "schema_version": record.schema_version,
        "experiment_id": record.experiment_id,
        "candidate_spec_id": record.candidate_spec_id,
        "training_dataset_id": record.training_dataset_id,
        "dataset_fingerprint": record.dataset_fingerprint,
        "trainer_kind": record.trainer_kind.value,
        "trainer_version": record.trainer_version,
        "hyperparameters": dict(record.hyperparameters),
        "seed": record.seed,
        "status": record.status.value,
        "metadata": dict(record.metadata),
        "software_lineage": dict(record.software_lineage),
    }
    if record.candidate_id is not None:
        body["candidate_id"] = record.candidate_id
    if record.diagnostics is not None:
        body["diagnostics"] = _diagnostics_to_dict(record.diagnostics)
    return body


def training_run_manifest_v1_from_dict(payload: dict[str, Any]) -> TrainingRunManifestV1:
    return TrainingRunManifestV1(
        training_run_id=str(payload["training_run_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        experiment_id=str(payload["experiment_id"]),
        candidate_spec_id=str(payload["candidate_spec_id"]),
        training_dataset_id=str(payload["training_dataset_id"]),
        dataset_fingerprint=str(payload["dataset_fingerprint"]),
        trainer_kind=TrainerKind(payload["trainer_kind"]),
        trainer_version=str(payload["trainer_version"]),
        hyperparameters=dict(payload.get("hyperparameters") or {}),
        seed=int(payload["seed"]),
        status=TrainingRunStatus(payload["status"]),
        candidate_id=payload.get("candidate_id"),
        diagnostics=_diagnostics_from_dict(payload.get("diagnostics")),
        software_lineage=dict(payload.get("software_lineage") or {}),
        metadata=dict(payload.get("metadata") or {}),
    )


def candidate_artifact_v1_to_dict(record: CandidateArtifactV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "candidate_id": record.candidate_id,
        "schema_version": record.schema_version,
        "experiment_id": record.experiment_id,
        "training_run_id": record.training_run_id,
        "candidate_spec_id": record.candidate_spec_id,
        "training_dataset_id": record.training_dataset_id,
        "dataset_fingerprint": record.dataset_fingerprint,
        "candidate_kind": record.candidate_kind.value,
        "model_family": record.model_family,
        "artifact_format": record.artifact_format,
        "artifact_hash": record.artifact_hash,
        "parameter_fingerprint": record.parameter_fingerprint,
        "trainer_version": record.trainer_version,
        "target_kind": record.target_kind,
        "horizon_ns": record.horizon_ns,
        "input_schema_fingerprint": record.input_schema_fingerprint,
        "seed": record.seed,
        "status": record.status.value,
        "supervision_kind": record.supervision_kind.value,
        "lineage": dict(record.lineage),
        "metadata": dict(record.metadata),
    }
    if record.artifact_ref is not None:
        body["artifact_ref"] = record.artifact_ref
    return body


def candidate_artifact_v1_from_dict(payload: dict[str, Any]) -> CandidateArtifactV1:
    return CandidateArtifactV1(
        candidate_id=str(payload["candidate_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        experiment_id=str(payload["experiment_id"]),
        training_run_id=str(payload["training_run_id"]),
        candidate_spec_id=str(payload["candidate_spec_id"]),
        training_dataset_id=str(payload["training_dataset_id"]),
        dataset_fingerprint=str(payload["dataset_fingerprint"]),
        candidate_kind=TrainerKind(payload["candidate_kind"]),
        model_family=str(payload["model_family"]),
        artifact_format=str(payload["artifact_format"]),
        artifact_hash=str(payload["artifact_hash"]),
        parameter_fingerprint=str(payload["parameter_fingerprint"]),
        trainer_version=str(payload["trainer_version"]),
        target_kind=str(payload["target_kind"]),
        horizon_ns=int(payload["horizon_ns"]),
        input_schema_fingerprint=str(payload["input_schema_fingerprint"]),
        seed=int(payload["seed"]),
        status=CandidateStatus(payload["status"]),
        supervision_kind=SupervisionKind(payload["supervision_kind"]),
        artifact_ref=payload.get("artifact_ref"),
        lineage=dict(payload.get("lineage") or {}),
        metadata=dict(payload.get("metadata") or {}),
    )


def distillation_dataset_manifest_v1_to_dict(record: DistillationDatasetManifestV1) -> dict[str, Any]:
    return {
        "distillation_dataset_id": record.distillation_dataset_id,
        "schema_version": record.schema_version,
        "experiment_id": record.experiment_id,
        "training_dataset_id": record.training_dataset_id,
        "teacher_id": record.teacher_id,
        "teacher_version": record.teacher_version,
        "target_kind": record.target_kind.value,
        "example_count": record.example_count,
        "dataset_fingerprint": record.dataset_fingerprint,
        "teacher_output_refs": list(record.teacher_output_refs),
        "metadata": dict(record.metadata),
    }


def distillation_dataset_manifest_v1_from_dict(payload: dict[str, Any]) -> DistillationDatasetManifestV1:
    return DistillationDatasetManifestV1(
        distillation_dataset_id=str(payload["distillation_dataset_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        experiment_id=str(payload["experiment_id"]),
        training_dataset_id=str(payload["training_dataset_id"]),
        teacher_id=str(payload["teacher_id"]),
        teacher_version=str(payload["teacher_version"]),
        target_kind=DistillationTargetKind(payload["target_kind"]),
        example_count=int(payload["example_count"]),
        dataset_fingerprint=str(payload["dataset_fingerprint"]),
        teacher_output_refs=tuple(payload.get("teacher_output_refs") or ()),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "candidate_artifact_v1_from_dict",
    "candidate_artifact_v1_to_dict",
    "distillation_dataset_manifest_v1_from_dict",
    "distillation_dataset_manifest_v1_to_dict",
    "training_dataset_manifest_v1_from_dict",
    "training_dataset_manifest_v1_to_dict",
    "training_run_manifest_v1_from_dict",
    "training_run_manifest_v1_to_dict",
]
