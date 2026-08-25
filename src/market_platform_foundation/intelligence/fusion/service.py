"""Forecast fusion service orchestration for BUILD 14."""

from __future__ import annotations

from dataclasses import dataclass

from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from .calibration import CalibrationApplicator
from .decision import FinalForecastBuilder
from .fusion import FusionEngine
from .manifest import ForecastFusionManifest
from .policy import FinalForecastPolicy, FusionPolicy
from .provenance import ForecastProvenanceResolver
from .types import ForecastDecisionResult, ForecastDecisionStatus
from .uncertainty import UncertaintyAssessor


@dataclass
class ForecastFusionService:
    repository: IntelligenceRepository
    fusion_policy: FusionPolicy | None = None
    final_policy: FinalForecastPolicy | None = None

    def __post_init__(self) -> None:
        if self.fusion_policy is None:
            from .policy import DEFAULT_PRODUCTION_FUSION_POLICY

            self.fusion_policy = DEFAULT_PRODUCTION_FUSION_POLICY
        if self.final_policy is None:
            from .policy import DEFAULT_PRODUCTION_FINAL_POLICY

            self.final_policy = DEFAULT_PRODUCTION_FINAL_POLICY

    def evaluate(
        self,
        manifest: ForecastFusionManifest,
        *,
        calibration_artifact=None,
        persist: bool = False,
        final_policy: FinalForecastPolicy | None = None,
    ) -> ForecastDecisionResult:
        resolver = ForecastProvenanceResolver(self.repository)
        engine = FusionEngine(resolver)
        raw_fusion = engine.fuse(manifest)
        policy = final_policy or self.final_policy
        assert policy is not None

        contributor_families = tuple(
            sorted(
                {
                    ref.forecast_family_key
                    for ref in manifest.contributors
                    if ref.forecast.forecast_id in raw_fusion.eligible_contributor_ids and ref.forecast_family_key
                }
            )
        )
        calibration_applicator = CalibrationApplicator()
        calibration_result = calibration_applicator.apply(
            artifact=calibration_artifact,
            raw_probability=raw_fusion.raw_probability,
            target=manifest.target,
            horizon=manifest.horizon,
            fusion_policy_identity=manifest.fusion_policy.policy_identity,
            decision_time_ns=manifest.decision_time_ns,
            regime_key=manifest.regime_key,
        )
        uncertainty = UncertaintyAssessor().assess(
            raw_fusion=raw_fusion,
            calibrated_probability=calibration_result.calibrated_probability,
            calibration_status=calibration_result.status,
            final_policy_identity=policy.policy_identity,
            calibration_model_id=calibration_artifact.calibration_model_id if calibration_artifact is not None else None,
            required_families=policy.required_contributor_families,
            contributor_families=contributor_families,
            ood_reasons=calibration_result.ood_reasons,
        )
        builder = FinalForecastBuilder(calibration_applicator)
        result = builder.build(
            manifest=manifest,
            raw_fusion=raw_fusion,
            calibration_artifact=calibration_artifact,
            final_policy=policy,
            uncertainty=uncertainty,
        )
        if persist and result.forecast is not None and result.status == ForecastDecisionStatus.EMITTED_CALIBRATED:
            self.repository.put_forecast(result.forecast)
        return result

    def persist_result(self, result: ForecastDecisionResult) -> RepositoryPutResult | None:
        if result.forecast is None:
            return None
        if result.status != ForecastDecisionStatus.EMITTED_CALIBRATED:
            return None
        return self.repository.put_forecast(result.forecast)


__all__ = ["ForecastFusionService"]
