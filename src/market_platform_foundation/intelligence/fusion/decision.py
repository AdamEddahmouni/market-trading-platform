"""Final forecast builder and abstention gate for BUILD 14."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts import ForecastV1
from ..contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ComponentLineage,
    ContractKind,
    ContractReference,
    ForecastEstimate,
    QualityState,
    QualitySummary,
)
from .calibration import CalibrationApplicator
from .manifest import ForecastFusionManifest
from .policy import FinalForecastPolicy
from .types import (
    CalibrationStatus,
    FINAL_FORECAST_STAGE,
    ForecastDecisionResult,
    ForecastDecisionStatus,
    FusionDiagnostic,
    FusionDiagnosticCode,
    OodReason,
    RawFusionResult,
    UncertaintyAssessment,
)
from .identity import derive_final_forecast_id


@dataclass(frozen=True, slots=True)
class FinalForecastBuilder:
    calibration_applicator: CalibrationApplicator

    def build(
        self,
        *,
        manifest: ForecastFusionManifest,
        raw_fusion: RawFusionResult,
        calibration_artifact,
        final_policy: FinalForecastPolicy,
        uncertainty: UncertaintyAssessment,
    ) -> ForecastDecisionResult:
        diagnostics = list(raw_fusion.diagnostics)
        if raw_fusion.raw_probability is None or not raw_fusion.eligible_contributor_ids:
            status = _no_contributor_status(manifest, diagnostics)
            return ForecastDecisionResult(status=status, raw_fusion=raw_fusion, uncertainty=uncertainty, diagnostics=tuple(diagnostics))

        calibration_result = self.calibration_applicator.apply(
            artifact=calibration_artifact,
            raw_probability=raw_fusion.raw_probability,
            target=manifest.target,
            horizon=manifest.horizon,
            fusion_policy_identity=manifest.fusion_policy.policy_identity,
            decision_time_ns=manifest.decision_time_ns,
            regime_key=manifest.regime_key,
        )

        if final_policy.required_contributor_families:
            present = set(uncertainty.coverage.get("present_contributor_families", []))
            if not final_policy.required_contributor_families.issubset(present):
                diagnostics.append(
                    FusionDiagnostic(
                        FusionDiagnosticCode.INSUFFICIENT_COVERAGE,
                        "required contributor families missing",
                    )
                )
                return ForecastDecisionResult(
                    status=ForecastDecisionStatus.ABSTAINED_INSUFFICIENT_COVERAGE,
                    raw_fusion=raw_fusion,
                    uncertainty=uncertainty,
                    diagnostics=tuple(diagnostics),
                )

        if uncertainty.independent_group_count < final_policy.minimum_independent_groups:
            return ForecastDecisionResult(
                status=ForecastDecisionStatus.ABSTAINED_INSUFFICIENT_INDEPENDENCE,
                raw_fusion=raw_fusion,
                uncertainty=uncertainty,
                diagnostics=tuple(diagnostics),
            )

        if (
            final_policy.maximum_inter_group_dispersion is not None
            and uncertainty.inter_group_probability_dispersion is not None
            and uncertainty.inter_group_probability_dispersion > final_policy.maximum_inter_group_dispersion
        ):
            return ForecastDecisionResult(
                status=ForecastDecisionStatus.ABSTAINED_DISAGREEMENT,
                raw_fusion=raw_fusion,
                uncertainty=uncertainty,
                diagnostics=tuple(diagnostics),
            )

        if raw_fusion.quality == QualityState.INVALID or (
            raw_fusion.quality == QualityState.DEGRADED and not final_policy.allow_degraded
        ):
            return ForecastDecisionResult(
                status=ForecastDecisionStatus.ABSTAINED_QUALITY,
                raw_fusion=raw_fusion,
                uncertainty=uncertainty,
                diagnostics=tuple(diagnostics),
            )

        if calibration_result.status == CalibrationStatus.CALIBRATION_MISMATCH:
            return ForecastDecisionResult(
                status=ForecastDecisionStatus.ABSTAINED_CALIBRATION_MISMATCH,
                raw_fusion=raw_fusion,
                uncertainty=uncertainty,
                diagnostics=tuple(diagnostics),
            )

        if calibration_result.status == CalibrationStatus.CALIBRATION_UNAVAILABLE:
            if final_policy.research_mode and final_policy.allow_raw_research_output:
                return ForecastDecisionResult(
                    status=ForecastDecisionStatus.RAW_ONLY_RESEARCH,
                    raw_fusion=raw_fusion,
                    uncertainty=uncertainty,
                    diagnostics=tuple(diagnostics),
                )
            if final_policy.require_calibration:
                return ForecastDecisionResult(
                    status=ForecastDecisionStatus.ABSTAINED_CALIBRATION_UNAVAILABLE,
                    raw_fusion=raw_fusion,
                    uncertainty=uncertainty,
                    diagnostics=tuple(diagnostics),
                )

        if OodReason.CALIBRATION_RANGE_OOD in calibration_result.ood_reasons and final_policy.fail_on_calibration_ood:
            return ForecastDecisionResult(
                status=ForecastDecisionStatus.ABSTAINED_OOD,
                raw_fusion=raw_fusion,
                uncertainty=uncertainty,
                diagnostics=tuple(diagnostics),
            )

        if final_policy.require_calibration and calibration_result.status not in {
            CalibrationStatus.CALIBRATED,
            CalibrationStatus.IDENTITY_CONTROL,
        }:
            return ForecastDecisionResult(
                status=ForecastDecisionStatus.ABSTAINED_CALIBRATION_UNAVAILABLE,
                raw_fusion=raw_fusion,
                uncertainty=uncertainty,
                diagnostics=tuple(diagnostics),
            )

        if final_policy.research_mode and final_policy.allow_raw_research_output and calibration_result.calibrated_probability is None:
            return ForecastDecisionResult(
                status=ForecastDecisionStatus.RAW_ONLY_RESEARCH,
                raw_fusion=raw_fusion,
                uncertainty=uncertainty,
                diagnostics=tuple(diagnostics),
            )

        forecast = _build_forecast(
            manifest=manifest,
            raw_fusion=raw_fusion,
            raw_probability=raw_fusion.raw_probability,
            calibrated_probability=calibration_result.calibrated_probability,
            calibration_status=calibration_result.status,
            calibration_artifact=calibration_artifact,
            final_policy=final_policy,
            uncertainty=uncertainty,
        )
        return ForecastDecisionResult(
            status=ForecastDecisionStatus.EMITTED_CALIBRATED,
            forecast=forecast,
            raw_fusion=raw_fusion,
            uncertainty=uncertainty,
            diagnostics=tuple(diagnostics),
        )


def _no_contributor_status(manifest: ForecastFusionManifest, diagnostics: list[FusionDiagnostic]) -> ForecastDecisionStatus:
    if any(code.code == FusionDiagnosticCode.CONTROL_EXCLUDED for code in diagnostics):
        return ForecastDecisionStatus.ABSTAINED_CONTROL_ONLY
    return ForecastDecisionStatus.ABSTAINED_NO_CONTRIBUTORS


def _build_forecast(
    *,
    manifest: ForecastFusionManifest,
    raw_fusion: RawFusionResult,
    raw_probability: float,
    calibrated_probability: float | None,
    calibration_status: CalibrationStatus,
    calibration_artifact,
    final_policy: FinalForecastPolicy,
    uncertainty: UncertaintyAssessment,
) -> ForecastV1:
    hypothesis_ids = tuple(ref.id for ref in manifest.hypothesis_context_refs)
    forecast_id = derive_final_forecast_id(
        raw_fusion_id=raw_fusion.fusion_id,
        calibration_model_id=calibration_artifact.calibration_model_id if calibration_artifact is not None else None,
        final_policy_identity=final_policy.policy_identity,
        target=manifest.target,
        horizon=manifest.horizon,
        snapshot_id=manifest.snapshot_id,
        decision_time_ns=manifest.decision_time_ns,
        hypothesis_context_ids=hypothesis_ids,
    )
    contributor_refs = tuple(
        ContractReference(kind=ContractKind.FORECAST.value, id=forecast_id)
        for forecast_id in raw_fusion.eligible_contributor_ids
    )
    metadata = {
        "forecast_stage": FINAL_FORECAST_STAGE,
        "calibration_status": calibration_status.value,
        "fusion_manifest_id": manifest.fusion_input_id,
        "fusion_policy_id": manifest.fusion_policy.policy_identity,
        "raw_fusion_id": raw_fusion.fusion_id,
        "final_policy_id": final_policy.policy_identity,
        "fusion_receipt": {
            "manifest_id": manifest.fusion_input_id,
            "fusion_policy_id": manifest.fusion_policy.policy_identity,
            "eligible_contributor_ids": list(raw_fusion.eligible_contributor_ids),
            "dependence_group_ids": [group.group_id for group in raw_fusion.dependence_groups],
            "independent_group_count": len(raw_fusion.dependence_groups),
        },
        "uncertainty_receipt": {
            "assessment_id": uncertainty.assessment_id,
            "predictive_entropy": uncertainty.predictive_entropy,
            "inter_group_probability_dispersion": uncertainty.inter_group_probability_dispersion,
            "independent_group_count": uncertainty.independent_group_count,
            "ood_reasons": [reason.value for reason in uncertainty.ood_reasons],
        },
    }
    if calibration_artifact is not None:
        metadata["calibration_receipt"] = {
            "calibration_model_id": calibration_artifact.calibration_model_id,
            "method": calibration_artifact.method.value,
            "method_version": calibration_artifact.method_version,
            "dataset_fingerprint": calibration_artifact.dataset_fingerprint,
            "training_cutoff_ns": calibration_artifact.training_cutoff_ns,
            "available_time_ns": calibration_artifact.available_time_ns,
            "parameter_fingerprint": calibration_artifact.parameter_fingerprint,
            "training_probability_range": [
                calibration_artifact.min_training_raw_probability,
                calibration_artifact.max_training_raw_probability,
            ],
        }
    return ForecastV1(
        forecast_id=forecast_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        scope=manifest.scope,
        decision_time_ns=manifest.decision_time_ns,
        snapshot_id=manifest.snapshot_id,
        target=manifest.target,
        horizon=manifest.horizon,
        estimate=ForecastEstimate(
            estimate_kind="classification_probability",
            probability=raw_probability,
            raw_score=raw_probability,
            calibrated_probability=calibrated_probability,
        ),
        quality=QualitySummary(state=raw_fusion.quality, flags=()),
        source_hypothesis_refs=manifest.hypothesis_context_refs,
        resolve_time_ns=manifest.decision_time_ns + manifest.horizon.duration_ns,
        uncertainty={
            "predictive_entropy": uncertainty.predictive_entropy,
            "inter_group_probability_dispersion": uncertainty.inter_group_probability_dispersion,
            "independent_group_count": uncertainty.independent_group_count,
            "epistemic_state": uncertainty.epistemic_state.value,
            "ood_reasons": [reason.value for reason in uncertainty.ood_reasons],
        },
        component_lineage=ComponentLineage(
            component_id="STATIC_FUSION_POLICY",
            component_version="1",
            model_id=manifest.fusion_policy.policy_identity,
            model_version="1",
        ),
        lineage_refs=contributor_refs,
        metadata=metadata,
    )


__all__ = ["FinalForecastBuilder"]
