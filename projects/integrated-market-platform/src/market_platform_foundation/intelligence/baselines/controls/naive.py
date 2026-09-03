"""Naive baseline controls (BUILD 08)."""

from __future__ import annotations

from dataclasses import dataclass

from ...contracts.common import ForecastTarget
from ..features import BaselineFeatureSchema
from ..identity import derive_model_id, deterministic_probability
from ..types import (
    BaselineClassLabel,
    BaselineFeatureVector,
    BaselineModelDescriptor,
    BaselineModelOutput,
    BaselinePredictionContext,
    PredictionDiagnosticCode,
)


def _empty_schema_fingerprint() -> str:
    return BaselineFeatureSchema(selectors=()).fingerprint


def _base_descriptor(
    *,
    model_kind: str,
    implementation_version: str,
    target: ForecastTarget,
    hyperparameters: dict | None = None,
    seed: int | None = None,
) -> BaselineModelDescriptor:
    schema_fp = _empty_schema_fingerprint()
    model_id = derive_model_id(
        model_kind=model_kind,
        implementation_version=implementation_version,
        feature_schema_fingerprint_value=schema_fp,
        target=target,
        hyperparameters=hyperparameters,
        seed=seed,
    )
    return BaselineModelDescriptor(
        model_id=model_id,
        model_kind=model_kind,
        implementation_version=implementation_version,
        feature_schema_fingerprint=schema_fp,
        target=target,
        hyperparameters=hyperparameters or {},
        seed=seed,
    )


@dataclass
class AlwaysUpBaseline:
    model_kind: str = "always-up"
    implementation_version: str = "1"

    def __post_init__(self) -> None:
        self._target: ForecastTarget | None = None
        self._descriptor: BaselineModelDescriptor | None = None

    def bind_target(self, target: ForecastTarget) -> AlwaysUpBaseline:
        self._target = target
        self._descriptor = _base_descriptor(
            model_kind=self.model_kind,
            implementation_version=self.implementation_version,
            target=target,
        )
        return self

    @property
    def descriptor(self) -> BaselineModelDescriptor:
        if self._descriptor is None:
            raise RuntimeError("MODEL_NOT_BOUND_TO_TARGET")
        return self._descriptor

    def predict(
        self,
        features: BaselineFeatureVector,
        context: BaselinePredictionContext,
    ) -> BaselineModelOutput:
        _ = features
        _ = context
        return BaselineModelOutput(
            predicted_class=BaselineClassLabel.UP,
            raw_score=1.0,
            raw_probability_up=1.0,
        )


@dataclass
class AlwaysDownBaseline:
    model_kind: str = "always-down"
    implementation_version: str = "1"

    def __post_init__(self) -> None:
        self._descriptor: BaselineModelDescriptor | None = None

    def bind_target(self, target: ForecastTarget) -> AlwaysDownBaseline:
        self._descriptor = _base_descriptor(
            model_kind=self.model_kind,
            implementation_version=self.implementation_version,
            target=target,
        )
        return self

    @property
    def descriptor(self) -> BaselineModelDescriptor:
        if self._descriptor is None:
            raise RuntimeError("MODEL_NOT_BOUND_TO_TARGET")
        return self._descriptor

    def predict(
        self,
        features: BaselineFeatureVector,
        context: BaselinePredictionContext,
    ) -> BaselineModelOutput:
        _ = features
        _ = context
        return BaselineModelOutput(
            predicted_class=BaselineClassLabel.DOWN,
            raw_score=0.0,
            raw_probability_up=0.0,
        )


@dataclass
class FixedPriorBaseline:
    probability_up: float
    model_kind: str = "fixed-prior"
    implementation_version: str = "1"

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability_up <= 1.0:
            raise ValueError("PRIOR_OUT_OF_RANGE")
        self._descriptor: BaselineModelDescriptor | None = None

    def bind_target(self, target: ForecastTarget) -> FixedPriorBaseline:
        self._descriptor = _base_descriptor(
            model_kind=self.model_kind,
            implementation_version=self.implementation_version,
            target=target,
            hyperparameters={"probability_up": self.probability_up},
        )
        return self

    @property
    def descriptor(self) -> BaselineModelDescriptor:
        if self._descriptor is None:
            raise RuntimeError("MODEL_NOT_BOUND_TO_TARGET")
        return self._descriptor

    def predict(
        self,
        features: BaselineFeatureVector,
        context: BaselinePredictionContext,
    ) -> BaselineModelOutput:
        _ = features
        _ = context
        predicted = (
            BaselineClassLabel.UP if self.probability_up >= 0.5 else BaselineClassLabel.DOWN
        )
        return BaselineModelOutput(
            predicted_class=predicted,
            raw_score=self.probability_up,
            raw_probability_up=self.probability_up,
        )


@dataclass
class DeterministicRandomBaseline:
    seed: str
    model_kind: str = "deterministic-random"
    implementation_version: str = "1"

    def __post_init__(self) -> None:
        if not self.seed:
            raise ValueError("SEED_REQUIRED")
        self._descriptor: BaselineModelDescriptor | None = None

    def bind_target(self, target: ForecastTarget) -> DeterministicRandomBaseline:
        self._descriptor = _base_descriptor(
            model_kind=self.model_kind,
            implementation_version=self.implementation_version,
            target=target,
            hyperparameters={"seed": self.seed},
            seed=hash(self.seed) % (2**31),
        )
        return self

    @property
    def descriptor(self) -> BaselineModelDescriptor:
        if self._descriptor is None:
            raise RuntimeError("MODEL_NOT_BOUND_TO_TARGET")
        return self._descriptor

    def predict(
        self,
        features: BaselineFeatureVector,
        context: BaselinePredictionContext,
    ) -> BaselineModelOutput:
        _ = features
        p_up = deterministic_probability(
            seed=self.seed,
            snapshot_id=context.snapshot.snapshot_id,
            target=context.target,
            horizon=context.horizon,
        )
        predicted = BaselineClassLabel.UP if p_up >= 0.5 else BaselineClassLabel.DOWN
        return BaselineModelOutput(
            predicted_class=predicted,
            raw_score=p_up,
            raw_probability_up=p_up,
        )


__all__ = [
    "AlwaysDownBaseline",
    "AlwaysUpBaseline",
    "DeterministicRandomBaseline",
    "FixedPriorBaseline",
]
