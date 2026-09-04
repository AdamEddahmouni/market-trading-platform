"""Baseline prediction engine (BUILD 08)."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.common import ForecastTarget, TimeHorizonNs
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from .errors import BaselinePredictionError
from .features import BaselineFeatureSchema, FeatureVectorBuilder
from .forecast import build_forecast_v1
from .types import (
    BaselineModel,
    BaselinePredictionContext,
    BaselinePredictionRequest,
    BaselinePredictionResult,
    PredictionDiagnostic,
    PredictionDiagnosticCode,
    PredictionStatus,
)


SUPPORTED_TARGET_KIND = "direction_up_down"


def direction_up_down_target(instrument_id: str) -> ForecastTarget:
    return ForecastTarget(
        target_kind=SUPPORTED_TARGET_KIND,
        instrument_id=instrument_id,
        parameters={"positive_direction": "UP", "negative_direction": "DOWN"},
    )


def _model_feature_schema(model: BaselineModel) -> BaselineFeatureSchema:
    schema = getattr(model, "feature_schema", None)
    if schema is not None:
        return schema
    internal = getattr(model, "_schema", None)
    if internal is not None:
        return internal
    return BaselineFeatureSchema(selectors=())


def _ensure_target_bound(model: BaselineModel, target: ForecastTarget) -> None:
    bind = getattr(model, "bind_target", None)
    if bind is None:
        return
    descriptor = getattr(model, "_descriptor", None)
    if descriptor is None:
        bind(target)


def _validate_request(request: BaselinePredictionRequest) -> PredictionDiagnostic | None:
    if request.target.target_kind != SUPPORTED_TARGET_KIND:
        return PredictionDiagnostic(
            code=PredictionDiagnosticCode.UNSUPPORTED_TARGET,
            message=f"Unsupported target kind: {request.target.target_kind}",
        )
    if request.horizon.duration_ns <= 0:
        return PredictionDiagnostic(
            code=PredictionDiagnosticCode.UNSUPPORTED_TARGET,
            message="Horizon must be positive",
        )
    if request.target.instrument_id not in request.snapshot.scope.instrument_ids:
        return PredictionDiagnostic(
            code=PredictionDiagnosticCode.UNSUPPORTED_TARGET,
            message="Target instrument not in snapshot scope",
        )
    return None


@dataclass
class BaselinePredictionEngine:
    """Orchestrates feature extraction, model invocation, and ForecastV1 construction."""

    def predict(
        self,
        request: BaselinePredictionRequest,
        model: BaselineModel,
    ) -> BaselinePredictionResult:
        validation = _validate_request(request)
        if validation is not None:
            return BaselinePredictionResult(
                status=PredictionStatus.ABSTAINED,
                diagnostics=(validation,),
            )

        _ensure_target_bound(model, request.target)
        schema = _model_feature_schema(model)
        builder = FeatureVectorBuilder(schema)
        feature_vector, diagnostics = builder.extract(
            request.snapshot,
            request.signals,
            allow_degraded=request.allow_degraded_features,
        )
        if feature_vector is None:
            return BaselinePredictionResult(
                status=PredictionStatus.ABSTAINED,
                diagnostics=diagnostics,
                model_descriptor=getattr(model, "descriptor", None),
            )

        context = BaselinePredictionContext(
            snapshot=request.snapshot,
            target=request.target,
            horizon=request.horizon,
            allow_degraded_features=request.allow_degraded_features,
            regime_key=request.regime_key,
        )
        model_output = model.predict(feature_vector, context)
        descriptor = model.descriptor

        if model_output.abstain:
            abstain_diag = PredictionDiagnostic(
                code=model_output.abstain_reason or PredictionDiagnosticCode.MODEL_OUTPUT_INVALID,
                message="Model abstained from prediction",
            )
            return BaselinePredictionResult(
                status=PredictionStatus.ABSTAINED,
                diagnostics=(abstain_diag,),
                model_descriptor=descriptor,
                feature_vector=feature_vector,
            )

        try:
            forecast = build_forecast_v1(
                snapshot=request.snapshot,
                source_signals=feature_vector.source_signals,
                target=request.target,
                horizon=request.horizon,
                model_output=model_output,
                descriptor=descriptor,
            )
        except BaselinePredictionError as error:
            return BaselinePredictionResult(
                status=PredictionStatus.ABSTAINED,
                diagnostics=(
                    PredictionDiagnostic(
                        code=PredictionDiagnosticCode.MODEL_OUTPUT_INVALID,
                        message=str(error),
                    ),
                ),
                model_descriptor=descriptor,
                feature_vector=feature_vector,
            )

        return BaselinePredictionResult(
            status=PredictionStatus.PREDICTED,
            forecast=forecast,
            model_descriptor=descriptor,
            feature_vector=feature_vector,
        )


def persist_forecast(
    repository: IntelligenceRepository,
    forecast,
) -> RepositoryPutResult:
    return repository.put_forecast(forecast)


__all__ = [
    "BaselinePredictionEngine",
    "SUPPORTED_TARGET_KIND",
    "direction_up_down_target",
    "persist_forecast",
]
