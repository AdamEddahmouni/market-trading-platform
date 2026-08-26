"""Trainer protocol and registry (BUILD 18)."""

from __future__ import annotations

from typing import Protocol

from ..types import CandidateTrainingResult, CandidateTrainingSpec, PreparedTrainingDataset, TrainerKind


class CandidateTrainer(Protocol):
    trainer_kind: TrainerKind
    trainer_version: str

    def train(
        self,
        spec: CandidateTrainingSpec,
        dataset: PreparedTrainingDataset,
    ) -> CandidateTrainingResult: ...


_TRAINER_REGISTRY: dict[TrainerKind, type] = {}


def register_trainer(kind: TrainerKind, cls: type) -> None:
    _TRAINER_REGISTRY[kind] = cls


def get_trainer(kind: TrainerKind) -> CandidateTrainer:
    if kind not in _TRAINER_REGISTRY:
        raise KeyError(f"TRAINER_NOT_REGISTERED:{kind.value}")
    return _TRAINER_REGISTRY[kind]()  # type: ignore[return-value]


def supported_trainer_kinds() -> tuple[TrainerKind, ...]:
    return tuple(sorted(_TRAINER_REGISTRY.keys(), key=lambda item: item.value))


__all__ = [
    "CandidateTrainer",
    "get_trainer",
    "register_trainer",
    "supported_trainer_kinds",
]
