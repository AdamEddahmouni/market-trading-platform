"""Experiment authorization for training (BUILD 18)."""

from __future__ import annotations

from ..research_experiments.types import ExperimentManifestV1
from .errors import TrainingFactoryError
from .types import TrainerKind


_FORBIDDEN_MUTATION_PARAMS = frozenset(
    {
        "settlement_semantics",
        "evaluation_metric_formula",
        "holdout_window",
        "target_definition",
    }
)


def validate_experiment_for_training(
    manifest: ExperimentManifestV1,
    *,
    trainer_kind: TrainerKind,
    target_kind: str,
    horizon_ns: int,
    mode: str,
    scenario_id: str | None = None,
    hyperparameter_keys: frozenset[str] | None = None,
) -> None:
    if not manifest.experiment_id:
        raise TrainingFactoryError("EXPERIMENT_NOT_FOUND")
    if manifest.data_spec.target_kind != target_kind:
        raise TrainingFactoryError(
            "TARGET_MISMATCH",
            details={"expected": manifest.data_spec.target_kind, "actual": target_kind},
        )
    if manifest.data_spec.horizon_ns != horizon_ns:
        raise TrainingFactoryError("HORIZON_MISMATCH")
    if manifest.data_spec.mode != mode:
        raise TrainingFactoryError("MODE_MISMATCH")
    if (
        manifest.data_spec.scenario_id is not None
        and scenario_id is not None
        and manifest.data_spec.scenario_id != scenario_id
    ):
        raise TrainingFactoryError("SCENARIO_MISMATCH")

    _validate_mutation_authorization(manifest, hyperparameter_keys)
    _validate_trainer_kind(manifest, trainer_kind)
    _validate_search_space(manifest)
    _validate_seed_policy(manifest)
    _validate_resource_budget(manifest)


def _validate_mutation_authorization(
    manifest: ExperimentManifestV1,
    hyperparameter_keys: frozenset[str] | None,
) -> None:
    forbidden = set(manifest.forbidden_changes)
    treatment_component = manifest.treatment.component
    if treatment_component in forbidden:
        raise TrainingFactoryError(
            "TRAINING_AUTHORIZATION_ERROR",
            details={"forbidden": treatment_component},
        )
    for item in _FORBIDDEN_MUTATION_PARAMS:
        if item in forbidden and hyperparameter_keys and item in hyperparameter_keys:
            raise TrainingFactoryError(
                "TRAINING_AUTHORIZATION_ERROR",
                details={"forbidden": item},
            )
    if hyperparameter_keys:
        allowed = set(manifest.allowed_changes)
        treatment_component = manifest.treatment.component
        if allowed and treatment_component not in allowed:
            for key in hyperparameter_keys:
                if key not in allowed:
                    raise TrainingFactoryError(
                        "TRAINING_AUTHORIZATION_ERROR",
                        details={"component": treatment_component, "parameter": key},
                    )


def _validate_trainer_kind(manifest: ExperimentManifestV1, trainer_kind: TrainerKind) -> None:
    if trainer_kind == TrainerKind.LORA_ADAPTER:
        raise TrainingFactoryError("TRAINER_UNAVAILABLE", details={"trainer_kind": trainer_kind.value})
    treatment = manifest.treatment
    if treatment.component == "baseline_model" and trainer_kind not in (
        TrainerKind.LOGISTIC_REGRESSION,
        TrainerKind.GRADIENT_BOOSTING,
        TrainerKind.DISTILLATION_LOGISTIC,
    ):
        if trainer_kind == TrainerKind.LORA_ADAPTER:
            raise TrainingFactoryError("TRAINER_UNAVAILABLE")


def _validate_search_space(manifest: ExperimentManifestV1) -> None:
    if manifest.search_space is None:
        return
    if not manifest.search_space.parameters:
        raise TrainingFactoryError("EMPTY_SEARCH_SPACE")
    for key, values in manifest.search_space.parameters.items():
        if not values:
            raise TrainingFactoryError("EMPTY_SEARCH_SPACE", details={"parameter": key})


def _validate_seed_policy(manifest: ExperimentManifestV1) -> None:
    if manifest.search_space is not None and manifest.seed_policy is None:
        raise TrainingFactoryError("SEED_POLICY_REQUIRED")


def _validate_resource_budget(manifest: ExperimentManifestV1) -> None:
    if manifest.resource_budget is None:
        return
    if manifest.resource_budget.max_training_runs is not None and manifest.resource_budget.max_training_runs < 1:
        raise TrainingFactoryError("RESOURCE_BUDGET_INVALID")


def holdout_boundary_ns(manifest: ExperimentManifestV1) -> int | None:
    """Return holdout start boundary when declared; BUILD 18 must not query holdout data."""
    if not manifest.validation_requirements.requires_locked_holdout:
        return None
    holdout_start = manifest.metadata.get("holdout_start_ns")
    if holdout_start is not None:
        return int(holdout_start)
    return manifest.data_spec.decision_end_ns


def is_frontier_historical_teacher_blocked(manifest: ExperimentManifestV1) -> bool:
    return bool(manifest.metadata.get("requires_frontier_teacher_replay"))


__all__ = [
    "holdout_boundary_ns",
    "is_frontier_historical_teacher_blocked",
    "validate_experiment_for_training",
]
