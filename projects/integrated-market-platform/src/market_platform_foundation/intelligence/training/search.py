"""Bounded search-space expansion (BUILD 18)."""

from __future__ import annotations

from itertools import product
from typing import Any

from ..research_experiments.types import ExperimentManifestV1, ResourceBudget, SearchSpaceSpec, SeedPolicy
from .errors import TrainingFactoryError
from .identity import derive_candidate_spec_id
from .types import CandidateTrainingSpec, TrainerKind


def expand_candidate_specs(
    manifest: ExperimentManifestV1,
    *,
    training_dataset_id: str,
    dataset_fingerprint: str,
    trainer_kind: TrainerKind,
    trainer_version: str,
    target_kind: str,
    horizon_ns: int,
    mode: str,
    base_hyperparameters: dict[str, Any],
    authorized_mutation_surface: tuple[str, ...],
) -> tuple[CandidateTrainingSpec, ...]:
    search_space = manifest.search_space
    seeds = _resolve_seeds(manifest.seed_policy, manifest.search_space)
    if search_space is None or not search_space.parameters:
        specs = []
        for seed in seeds:
            specs.append(
                _build_spec(
                    manifest=manifest,
                    training_dataset_id=training_dataset_id,
                    dataset_fingerprint=dataset_fingerprint,
                    trainer_kind=trainer_kind,
                    trainer_version=trainer_version,
                    target_kind=target_kind,
                    horizon_ns=horizon_ns,
                    mode=mode,
                    hyperparameters=dict(base_hyperparameters),
                    seed=seed,
                    authorized_mutation_surface=authorized_mutation_surface,
                )
            )
        _enforce_budget(manifest.resource_budget, len(specs))
        return tuple(specs)

    param_names = sorted(search_space.parameters.keys())
    value_lists = [search_space.parameters[name] for name in param_names]
    grid_size = 1
    for values in value_lists:
        grid_size *= len(values)
    total = grid_size * len(seeds)
    _enforce_budget(manifest.resource_budget, total)

    specs: list[CandidateTrainingSpec] = []
    for combo in product(*value_lists):
        hyperparams = dict(base_hyperparameters)
        for name, value in zip(param_names, combo, strict=True):
            hyperparams[name] = value
        for seed in seeds:
            specs.append(
                _build_spec(
                    manifest=manifest,
                    training_dataset_id=training_dataset_id,
                    dataset_fingerprint=dataset_fingerprint,
                    trainer_kind=trainer_kind,
                    trainer_version=trainer_version,
                    target_kind=target_kind,
                    horizon_ns=horizon_ns,
                    mode=mode,
                    hyperparameters=hyperparams,
                    seed=seed,
                    authorized_mutation_surface=authorized_mutation_surface,
                )
            )
    return tuple(specs)


def _resolve_seeds(seed_policy: SeedPolicy | None, search_space: SearchSpaceSpec | None) -> tuple[int, ...]:
    if seed_policy is None:
        return (42,)
    if seed_policy.fixed_seeds:
        return tuple(sorted(seed_policy.fixed_seeds))
    if seed_policy.derivation_algorithm:
        raise TrainingFactoryError("UNSUPPORTED_SEED_DERIVATION")
    return (42,)


def _enforce_budget(budget: ResourceBudget | None, planned_runs: int) -> None:
    if budget is None:
        return
    if budget.max_candidates is not None and planned_runs > budget.max_candidates:
        raise TrainingFactoryError(
            "MAX_CANDIDATES_EXCEEDED",
            details={"planned": planned_runs, "max": budget.max_candidates},
        )
    if budget.max_training_runs is not None and planned_runs > budget.max_training_runs:
        raise TrainingFactoryError(
            "MAX_TRAINING_RUNS_EXCEEDED",
            details={"planned": planned_runs, "max": budget.max_training_runs},
        )


def _build_spec(
    *,
    manifest: ExperimentManifestV1,
    training_dataset_id: str,
    dataset_fingerprint: str,
    trainer_kind: TrainerKind,
    trainer_version: str,
    target_kind: str,
    horizon_ns: int,
    mode: str,
    hyperparameters: dict[str, Any],
    seed: int,
    authorized_mutation_surface: tuple[str, ...],
) -> CandidateTrainingSpec:
    hyperparameters = dict(hyperparameters)
    hyperparameters["random_state"] = seed
    spec_id = derive_candidate_spec_id(
        experiment_id=manifest.experiment_id,
        dataset_fingerprint=dataset_fingerprint,
        trainer_kind=trainer_kind.value,
        trainer_version=trainer_version,
        hyperparameters=hyperparameters,
        seed=seed,
        authorized_mutation_surface=authorized_mutation_surface,
    )
    return CandidateTrainingSpec(
        candidate_spec_id=spec_id,
        experiment_id=manifest.experiment_id,
        training_dataset_id=training_dataset_id,
        dataset_fingerprint=dataset_fingerprint,
        trainer_kind=trainer_kind,
        hyperparameters=hyperparameters,
        seed=seed,
        authorized_mutation_surface=authorized_mutation_surface,
        trainer_version=trainer_version,
        target_kind=target_kind,
        horizon_ns=horizon_ns,
        mode=mode,
    )


__all__ = ["expand_candidate_specs"]
