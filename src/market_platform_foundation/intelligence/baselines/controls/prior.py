"""Prior baselines — empirical and regime-conditioned (BUILD 08)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ...contracts.common import ForecastTarget
from ..errors import BaselineTrainingError
from ..features import BaselineFeatureSchema
from ..identity import derive_model_id, parameter_fingerprint_from_payload
from ..training import BaselineTrainingDataset
from ..types import (
    BaselineClassLabel,
    BaselineFeatureVector,
    BaselineModelDescriptor,
    BaselineModelOutput,
    BaselinePredictionContext,
    FitSummary,
    PredictionDiagnosticCode,
)


class UnseenRegimePolicy(StrEnum):
    GLOBAL_FALLBACK = "GLOBAL_FALLBACK"
    ABSTAIN = "ABSTAIN"


@dataclass
class EmpiricalPriorBaseline:
    model_kind: str = "empirical-prior"
    implementation_version: str = "1"

    def __post_init__(self) -> None:
        self._schema = BaselineFeatureSchema(selectors=())
        self._descriptor: BaselineModelDescriptor | None = None
        self._p_up: float | None = None
        self._up_count: int = 0
        self._down_count: int = 0

    @property
    def descriptor(self) -> BaselineModelDescriptor:
        if self._descriptor is None:
            raise RuntimeError("MODEL_NOT_FITTED")
        return self._descriptor

    @property
    def is_fitted(self) -> bool:
        return self._descriptor is not None

    def fit(self, dataset: BaselineTrainingDataset) -> FitSummary:
        if not dataset.examples:
            raise BaselineTrainingError("TRAINING_DATASET_EMPTY")
        up_count = sum(1 for example in dataset.examples if example.label == BaselineClassLabel.UP)
        down_count = len(dataset.examples) - up_count
        total = up_count + down_count
        if total == 0:
            raise BaselineTrainingError("NO_TRAINING_EXAMPLES")
        self._up_count = up_count
        self._down_count = down_count
        self._p_up = up_count / total
        param_fp = parameter_fingerprint_from_payload(
            {"p_up": self._p_up, "up_count": up_count, "down_count": down_count}
        )
        self._descriptor = BaselineModelDescriptor(
            model_id=derive_model_id(
                model_kind=self.model_kind,
                implementation_version=self.implementation_version,
                feature_schema_fingerprint_value=self._schema.fingerprint,
                target=dataset.target,
                training_dataset_fingerprint=dataset.fingerprint,
                training_cutoff_ns=dataset.training_cutoff_ns,
            ),
            model_kind=self.model_kind,
            implementation_version=self.implementation_version,
            feature_schema_fingerprint=self._schema.fingerprint,
            target=dataset.target,
            training_dataset_fingerprint=dataset.fingerprint,
            training_cutoff_ns=dataset.training_cutoff_ns,
            parameter_fingerprint=param_fp,
            class_mapping={"UP": 1, "DOWN": 0},
        )
        return FitSummary(
            model_id=self._descriptor.model_id,
            dataset_fingerprint=dataset.fingerprint,
            example_count=total,
            up_count=up_count,
            down_count=down_count,
            feature_count=0,
            training_cutoff_ns=dataset.training_cutoff_ns,
            parameter_fingerprint=param_fp,
        )

    def predict(
        self,
        features: BaselineFeatureVector,
        context: BaselinePredictionContext,
    ) -> BaselineModelOutput:
        _ = features
        _ = context
        if self._p_up is None or self._descriptor is None:
            return BaselineModelOutput(
                abstain=True,
                abstain_reason=PredictionDiagnosticCode.MODEL_NOT_FITTED,
            )
        predicted = BaselineClassLabel.UP if self._p_up >= 0.5 else BaselineClassLabel.DOWN
        return BaselineModelOutput(
            predicted_class=predicted,
            raw_score=self._p_up,
            raw_probability_up=self._p_up,
        )


@dataclass
class RegimeConditionedPriorBaseline:
    unseen_regime_policy: UnseenRegimePolicy = UnseenRegimePolicy.GLOBAL_FALLBACK
    model_kind: str = "regime-prior"
    implementation_version: str = "1"
    _regime_priors: dict[str, float] = field(default_factory=dict, init=False)
    _regime_counts: dict[str, dict[str, int]] = field(default_factory=dict, init=False)
    _global_p_up: float | None = field(default=None, init=False)
    _descriptor: BaselineModelDescriptor | None = field(default=None, init=False)
    _schema: BaselineFeatureSchema = field(
        default_factory=lambda: BaselineFeatureSchema(selectors=()),
        init=False,
    )

    @property
    def descriptor(self) -> BaselineModelDescriptor:
        if self._descriptor is None:
            raise RuntimeError("MODEL_NOT_FITTED")
        return self._descriptor

    def fit(self, dataset: BaselineTrainingDataset) -> FitSummary:
        if not dataset.examples:
            raise BaselineTrainingError("TRAINING_DATASET_EMPTY")
        up_count = 0
        down_count = 0
        regime_counts: dict[str, dict[str, int]] = {}
        for example in dataset.examples:
            if example.label == BaselineClassLabel.UP:
                up_count += 1
            else:
                down_count += 1
            regime = example.regime_key or "__missing__"
            bucket = regime_counts.setdefault(regime, {"up": 0, "down": 0})
            if example.label == BaselineClassLabel.UP:
                bucket["up"] += 1
            else:
                bucket["down"] += 1
        total = up_count + down_count
        self._global_p_up = up_count / total
        regime_priors: dict[str, float] = {}
        for regime, counts in regime_counts.items():
            regime_total = counts["up"] + counts["down"]
            if regime_total > 0:
                regime_priors[regime] = counts["up"] / regime_total
        self._regime_counts = regime_counts
        self._regime_priors = regime_priors
        param_fp = parameter_fingerprint_from_payload(
            {
                "global_p_up": self._global_p_up,
                "regime_priors": {key: regime_priors[key] for key in sorted(regime_priors)},
                "unseen_regime_policy": self.unseen_regime_policy.value,
            }
        )
        self._descriptor = BaselineModelDescriptor(
            model_id=derive_model_id(
                model_kind=self.model_kind,
                implementation_version=self.implementation_version,
                feature_schema_fingerprint_value=self._schema.fingerprint,
                target=dataset.target,
                training_dataset_fingerprint=dataset.fingerprint,
                training_cutoff_ns=dataset.training_cutoff_ns,
                hyperparameters={"unseen_regime_policy": self.unseen_regime_policy.value},
            ),
            model_kind=self.model_kind,
            implementation_version=self.implementation_version,
            feature_schema_fingerprint=self._schema.fingerprint,
            target=dataset.target,
            training_dataset_fingerprint=dataset.fingerprint,
            training_cutoff_ns=dataset.training_cutoff_ns,
            hyperparameters={"unseen_regime_policy": self.unseen_regime_policy.value},
            parameter_fingerprint=param_fp,
        )
        return FitSummary(
            model_id=self._descriptor.model_id,
            dataset_fingerprint=dataset.fingerprint,
            example_count=total,
            up_count=up_count,
            down_count=down_count,
            feature_count=0,
            training_cutoff_ns=dataset.training_cutoff_ns,
            parameter_fingerprint=param_fp,
        )

    def predict(
        self,
        features: BaselineFeatureVector,
        context: BaselinePredictionContext,
    ) -> BaselineModelOutput:
        _ = features
        if self._descriptor is None or self._global_p_up is None:
            return BaselineModelOutput(
                abstain=True,
                abstain_reason=PredictionDiagnosticCode.MODEL_NOT_FITTED,
            )
        regime_key = context.regime_key
        if regime_key is None:
            return BaselineModelOutput(
                abstain=True,
                abstain_reason=PredictionDiagnosticCode.UNKNOWN_REGIME,
            )
        if regime_key in self._regime_priors:
            p_up = self._regime_priors[regime_key]
        elif self.unseen_regime_policy == UnseenRegimePolicy.GLOBAL_FALLBACK:
            p_up = self._global_p_up
        else:
            return BaselineModelOutput(
                abstain=True,
                abstain_reason=PredictionDiagnosticCode.UNKNOWN_REGIME,
            )
        predicted = BaselineClassLabel.UP if p_up >= 0.5 else BaselineClassLabel.DOWN
        return BaselineModelOutput(
            predicted_class=predicted,
            raw_score=p_up,
            raw_probability_up=p_up,
        )


__all__ = [
    "EmpiricalPriorBaseline",
    "RegimeConditionedPriorBaseline",
    "UnseenRegimePolicy",
]
