"""Core baseline prediction types (BUILD 08)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from .training import BaselineTrainingDataset

from ..contracts.forecast import ForecastV1
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from ..contracts.common import ForecastTarget, TimeHorizonNs


class BaselineClassLabel(StrEnum):
    UP = "UP"
    DOWN = "DOWN"


class PredictionStatus(StrEnum):
    PREDICTED = "PREDICTED"
    ABSTAINED = "ABSTAINED"


class PredictionDiagnosticCode(StrEnum):
    MISSING_FEATURE = "MISSING_FEATURE"
    DUPLICATE_FEATURE = "DUPLICATE_FEATURE"
    INVALID_FEATURE = "INVALID_FEATURE"
    DEGRADED_FEATURE_REJECTED = "DEGRADED_FEATURE_REJECTED"
    MODEL_NOT_FITTED = "MODEL_NOT_FITTED"
    UNSUPPORTED_TARGET = "UNSUPPORTED_TARGET"
    UNKNOWN_REGIME = "UNKNOWN_REGIME"
    MODEL_OUTPUT_INVALID = "MODEL_OUTPUT_INVALID"
    SIGNAL_SNAPSHOT_MISMATCH = "SIGNAL_SNAPSHOT_MISMATCH"
    SIGNAL_TIME_VIOLATION = "SIGNAL_TIME_VIOLATION"
    NEUTRAL_FEATURE_VALUE = "NEUTRAL_FEATURE_VALUE"


@dataclass(frozen=True, slots=True)
class PredictionDiagnostic:
    code: PredictionDiagnosticCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BaselineModelOutput:
    predicted_class: BaselineClassLabel | None = None
    raw_score: float | None = None
    raw_probability_up: float | None = None
    abstain: bool = False
    abstain_reason: PredictionDiagnosticCode | None = None


@dataclass(frozen=True, slots=True)
class BaselineFeatureVector:
    values: tuple[float, ...]
    source_signals: tuple[SignalV1, ...]
    feature_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BaselinePredictionContext:
    snapshot: SnapshotV1
    target: ForecastTarget
    horizon: TimeHorizonNs
    allow_degraded_features: bool = False
    regime_key: str | None = None


@dataclass(frozen=True, slots=True)
class BaselineModelDescriptor:
    model_id: str
    model_kind: str
    implementation_version: str
    feature_schema_fingerprint: str
    target: ForecastTarget
    training_dataset_fingerprint: str | None = None
    training_cutoff_ns: int | None = None
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    parameter_fingerprint: str | None = None
    calibration_status: str = "UNCALIBRATED"
    seed: int | None = None
    class_mapping: dict[str, int] = field(default_factory=dict)
    allow_degraded_features: bool = False
    allow_degraded_training_examples: bool = False


@dataclass(frozen=True, slots=True)
class BaselinePredictionRequest:
    snapshot: SnapshotV1
    signals: tuple[SignalV1, ...]
    target: ForecastTarget
    horizon: TimeHorizonNs
    allow_degraded_features: bool = False
    regime_key: str | None = None


@dataclass(frozen=True, slots=True)
class BaselinePredictionResult:
    status: PredictionStatus
    forecast: ForecastV1 | None = None
    diagnostics: tuple[PredictionDiagnostic, ...] = ()
    model_descriptor: BaselineModelDescriptor | None = None
    feature_vector: BaselineFeatureVector | None = None


@dataclass(frozen=True, slots=True)
class FitSummary:
    model_id: str
    dataset_fingerprint: str
    example_count: int
    up_count: int
    down_count: int
    feature_count: int
    training_cutoff_ns: int
    parameter_fingerprint: str | None = None


class BaselineModel(Protocol):
    model_kind: str
    implementation_version: str

    @property
    def descriptor(self) -> BaselineModelDescriptor: ...

    def predict(
        self,
        features: BaselineFeatureVector,
        context: BaselinePredictionContext,
    ) -> BaselineModelOutput: ...


class FittableBaselineModel(BaselineModel, Protocol):
    def fit(self, dataset: BaselineTrainingDataset) -> FitSummary: ...


__all__ = [
    "BaselineClassLabel",
    "BaselineFeatureVector",
    "BaselineModel",
    "BaselineModelDescriptor",
    "BaselineModelOutput",
    "BaselinePredictionContext",
    "BaselinePredictionRequest",
    "BaselinePredictionResult",
    "BaselineTrainingDataset",
    "FitSummary",
    "FittableBaselineModel",
    "PredictionDiagnostic",
    "PredictionDiagnosticCode",
    "PredictionStatus",
]
