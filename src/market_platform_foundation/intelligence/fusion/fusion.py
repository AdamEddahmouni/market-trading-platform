"""Raw forecast fusion for BUILD 14."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.common import (
    ForecastTarget,
    QualityState,
    QualitySummary,
    TimeHorizonNs,
    forecast_target_to_dict,
    time_horizon_to_dict,
)
from .dependence import DependenceGrouper
from .errors import FusionCompatibilityError, FusionInputError
from .identity import derive_raw_fusion_id
from .manifest import ForecastFusionManifest
from .pooling import across_group_probability, within_group_probability
from .provenance import ForecastProvenanceResolver
from .types import (
    DependenceState,
    ForecastContributorRole,
    ForecastDependenceGroup,
    FusionDiagnostic,
    FusionDiagnosticCode,
    RawFusionResult,
)


@dataclass(frozen=True, slots=True)
class FusionEngine:
    resolver: ForecastProvenanceResolver

    def fuse(self, manifest: ForecastFusionManifest) -> RawFusionResult:
        diagnostics: list[FusionDiagnostic] = []
        eligible: list = []
        excluded: list[str] = []
        policy = manifest.fusion_policy

        for ref in manifest.contributors:
            forecast = ref.forecast
            if not _compatible(manifest, ref, diagnostics):
                excluded.append(forecast.forecast_id)
                continue
            if ref.role not in policy.allowed_roles:
                diagnostics.append(
                    FusionDiagnostic(
                        FusionDiagnosticCode.CONTROL_EXCLUDED,
                        f"role excluded: {ref.role.value}",
                        {"forecast_id": forecast.forecast_id},
                    )
                )
                excluded.append(forecast.forecast_id)
                continue
            if forecast.quality.state == QualityState.INVALID:
                diagnostics.append(
                    FusionDiagnostic(
                        FusionDiagnosticCode.INVALID_PROBABILITY,
                        "invalid contributor quality",
                        {"forecast_id": forecast.forecast_id},
                    )
                )
                excluded.append(forecast.forecast_id)
                continue
            if forecast.quality.state == QualityState.DEGRADED and not policy.allow_degraded:
                diagnostics.append(
                    FusionDiagnostic(
                        FusionDiagnosticCode.DEGRADED_EXCLUDED,
                        "degraded contributor excluded",
                        {"forecast_id": forecast.forecast_id},
                    )
                )
                excluded.append(forecast.forecast_id)
                continue
            eligible.append(ref)

        if not eligible:
            status = _empty_status(manifest.contributors, diagnostics)
            return RawFusionResult(
                fusion_id=derive_raw_fusion_id(
                    manifest_id=manifest.fusion_input_id,
                    fusion_policy_identity=policy.policy_identity,
                    pooling_method=policy.pooling_method,
                ),
                manifest_id=manifest.fusion_input_id,
                raw_probability=None,
                eligible_contributor_ids=(),
                excluded_contributor_ids=tuple(sorted(excluded)),
                dependence_groups=(),
                quality=QualityState.INVALID,
                diagnostics=tuple(diagnostics),
            )

        grouper = DependenceGrouper(self.resolver)
        grouping = grouper.group(manifest, tuple(eligible))
        if grouping.dependence_state == DependenceState.UNKNOWN and not policy.allow_unknown_dependence:
            diagnostics.append(
                FusionDiagnostic(
                    FusionDiagnosticCode.DEPENDENCE_UNKNOWN,
                    "unknown dependence not allowed",
                )
            )
            return RawFusionResult(
                fusion_id=derive_raw_fusion_id(
                    manifest_id=manifest.fusion_input_id,
                    fusion_policy_identity=policy.policy_identity,
                    pooling_method=policy.pooling_method,
                ),
                manifest_id=manifest.fusion_input_id,
                raw_probability=None,
                eligible_contributor_ids=tuple(ref.forecast.forecast_id for ref in eligible),
                excluded_contributor_ids=tuple(sorted(excluded)),
                dependence_groups=grouping.groups,
                quality=_aggregate_quality(eligible),
                diagnostics=tuple(diagnostics),
                dependence_state=DependenceState.UNKNOWN,
            )

        contributors_by_id = {ref.forecast.forecast_id: ref for ref in eligible}
        group_probabilities: dict[str, float] = {}
        finalized_groups: list[ForecastDependenceGroup] = []
        for group in grouping.groups:
            group_contributors = tuple(contributors_by_id[forecast_id] for forecast_id in group.forecast_ids)
            group_probability = within_group_probability(
                group_contributors,
                contributor_weights=policy.contributor_weights,
            )
            group_probabilities[group.group_id] = group_probability
            finalized_groups.append(
                ForecastDependenceGroup(
                    group_id=group.group_id,
                    forecast_ids=group.forecast_ids,
                    group_probability=group_probability,
                    group_weight=1.0,
                )
            )

        raw_probability = across_group_probability(
            tuple(finalized_groups),
            group_probabilities,
            group_weights=policy.group_weights,
        )

        return RawFusionResult(
            fusion_id=derive_raw_fusion_id(
                manifest_id=manifest.fusion_input_id,
                fusion_policy_identity=policy.policy_identity,
                pooling_method=policy.pooling_method,
            ),
            manifest_id=manifest.fusion_input_id,
            raw_probability=raw_probability,
            eligible_contributor_ids=tuple(ref.forecast.forecast_id for ref in eligible),
            excluded_contributor_ids=tuple(sorted(excluded)),
            dependence_groups=tuple(finalized_groups),
            quality=_aggregate_quality(eligible),
            diagnostics=tuple(diagnostics),
            dependence_state=grouping.dependence_state,
        )


def _compatible(manifest: ForecastFusionManifest, ref, diagnostics: list[FusionDiagnostic]) -> bool:
    forecast = ref.forecast
    if forecast.snapshot_id != manifest.snapshot_id:
        diagnostics.append(
            FusionDiagnostic(
                FusionDiagnosticCode.SNAPSHOT_MISMATCH,
                "snapshot mismatch",
                {"forecast_id": forecast.forecast_id},
            )
        )
        return False
    if forecast.decision_time_ns != manifest.decision_time_ns:
        diagnostics.append(
            FusionDiagnostic(
                FusionDiagnosticCode.DECISION_TIME_MISMATCH,
                "decision time mismatch",
                {"forecast_id": forecast.forecast_id},
            )
        )
        return False
    if not _targets_equal(forecast.target, manifest.target):
        diagnostics.append(
            FusionDiagnostic(
                FusionDiagnosticCode.TARGET_MISMATCH,
                "target mismatch",
                {"forecast_id": forecast.forecast_id},
            )
        )
        return False
    if not _horizons_equal(forecast.horizon, manifest.horizon):
        diagnostics.append(
            FusionDiagnostic(
                FusionDiagnosticCode.HORIZON_MISMATCH,
                "horizon mismatch",
                {"forecast_id": forecast.forecast_id},
            )
        )
        return False
    if forecast.scope.instrument_ids != manifest.scope.instrument_ids:
        diagnostics.append(
            FusionDiagnostic(
                FusionDiagnosticCode.SCOPE_MISMATCH,
                "scope mismatch",
                {"forecast_id": forecast.forecast_id},
            )
        )
        return False
    return True


def _targets_equal(left: ForecastTarget, right: ForecastTarget) -> bool:
    return forecast_target_to_dict(left) == forecast_target_to_dict(right)


def _horizons_equal(left: TimeHorizonNs, right: TimeHorizonNs) -> bool:
    return time_horizon_to_dict(left) == time_horizon_to_dict(right)


def _aggregate_quality(contributors) -> QualityState:
    states = [ref.forecast.quality.state for ref in contributors]
    if QualityState.INVALID in states:
        return QualityState.INVALID
    if QualityState.DEGRADED in states:
        return QualityState.DEGRADED
    return QualityState.GOOD


def _empty_status(contributors, diagnostics: list[FusionDiagnostic]) -> QualityState:
    if not contributors:
        diagnostics.append(FusionDiagnostic(FusionDiagnosticCode.NO_ELIGIBLE_CONTRIBUTOR, "no contributors"))
    elif all(ref.role != ForecastContributorRole.PRODUCTION for ref in contributors):
        diagnostics.append(FusionDiagnostic(FusionDiagnosticCode.CONTROL_EXCLUDED, "control-only manifest"))
    return QualityState.INVALID


__all__ = ["FusionEngine"]
