"""Momentum baseline control (BUILD 08)."""

from __future__ import annotations

from dataclasses import dataclass

from ...contracts.common import ForecastTarget
from ..features import BaselineFeatureSchema, MOMENTUM_5M_SELECTOR
from ..identity import derive_model_id
from ..types import (
    BaselineClassLabel,
    BaselineFeatureVector,
    BaselineModelDescriptor,
    BaselineModelOutput,
    BaselinePredictionContext,
    PredictionDiagnosticCode,
)


@dataclass
class MomentumBaseline:
    model_kind: str = "momentum"
    implementation_version: str = "1"

    def __post_init__(self) -> None:
        self._schema = BaselineFeatureSchema(selectors=(MOMENTUM_5M_SELECTOR,))
        self._descriptor: BaselineModelDescriptor | None = None

    def bind_target(self, target: ForecastTarget) -> MomentumBaseline:
        self._descriptor = BaselineModelDescriptor(
            model_id=derive_model_id(
                model_kind=self.model_kind,
                implementation_version=self.implementation_version,
                feature_schema_fingerprint_value=self._schema.fingerprint,
                target=target,
            ),
            model_kind=self.model_kind,
            implementation_version=self.implementation_version,
            feature_schema_fingerprint=self._schema.fingerprint,
            target=target,
        )
        return self

    @property
    def descriptor(self) -> BaselineModelDescriptor:
        if self._descriptor is None:
            raise RuntimeError("MODEL_NOT_BOUND_TO_TARGET")
        return self._descriptor

    @property
    def feature_schema(self) -> BaselineFeatureSchema:
        return self._schema

    def predict(
        self,
        features: BaselineFeatureVector,
        context: BaselinePredictionContext,
    ) -> BaselineModelOutput:
        _ = context
        momentum = features.values[0]
        if momentum > 0:
            return BaselineModelOutput(
                predicted_class=BaselineClassLabel.UP,
                raw_score=momentum,
                raw_probability_up=0.5 + 0.5 * min(max(momentum, -1.0), 1.0),
            )
        if momentum < 0:
            return BaselineModelOutput(
                predicted_class=BaselineClassLabel.DOWN,
                raw_score=momentum,
                raw_probability_up=0.5 + 0.5 * min(max(momentum, -1.0), 1.0),
            )
        return BaselineModelOutput(
            abstain=True,
            abstain_reason=PredictionDiagnosticCode.NEUTRAL_FEATURE_VALUE,
        )


__all__ = ["MomentumBaseline"]
