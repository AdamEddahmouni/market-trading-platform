"""Sealed fusion input manifest for BUILD 14."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.common import ContractReference, ForecastTarget, IntelligenceScope, TimeHorizonNs
from .errors import FusionInputError
from .identity import contributor_entry_for_identity, derive_fusion_manifest_id
from .policy import FusionPolicy
from .roles import resolve_contributor_role, resolve_forecast_family_key
from .types import ForecastContributorRole, FusionContributorRef, FusionDiagnostic, FusionDiagnosticCode


@dataclass(frozen=True, slots=True)
class ForecastFusionManifest:
    fusion_input_id: str
    snapshot_id: str
    target: ForecastTarget
    horizon: TimeHorizonNs
    decision_time_ns: int
    scope: IntelligenceScope
    contributors: tuple[FusionContributorRef, ...]
    fusion_policy: FusionPolicy
    hypothesis_context_refs: tuple[ContractReference, ...] = ()
    regime_key: str | None = None

    @classmethod
    def create(
        cls,
        *,
        snapshot_id: str,
        target: ForecastTarget,
        horizon: TimeHorizonNs,
        decision_time_ns: int,
        scope: IntelligenceScope,
        contributors: list[FusionContributorRef],
        fusion_policy: FusionPolicy,
        hypothesis_context_refs: tuple[ContractReference, ...] = (),
        regime_key: str | None = None,
    ) -> ForecastFusionManifest:
        normalized = _normalize_contributors(contributors)
        entries = [contributor_entry_for_identity(ref) for ref in normalized]
        entries.sort(key=lambda row: row["forecast_id"])
        fusion_input_id = derive_fusion_manifest_id(
            snapshot_id=snapshot_id,
            target=target,
            horizon=horizon,
            decision_time_ns=decision_time_ns,
            contributor_entries=entries,
            fusion_policy_identity=fusion_policy.policy_identity,
            hypothesis_context_ids=tuple(ref.id for ref in hypothesis_context_refs),
            regime_key=regime_key,
        )
        return cls(
            fusion_input_id=fusion_input_id,
            snapshot_id=snapshot_id,
            target=target,
            horizon=horizon,
            decision_time_ns=decision_time_ns,
            scope=scope,
            contributors=tuple(normalized),
            fusion_policy=fusion_policy,
            hypothesis_context_refs=hypothesis_context_refs,
            regime_key=regime_key,
        )


def _normalize_contributors(contributors: list[FusionContributorRef]) -> list[FusionContributorRef]:
    by_id: dict[str, FusionContributorRef] = {}
    for ref in contributors:
        forecast_id = ref.forecast.forecast_id
        if forecast_id in by_id:
            existing = by_id[forecast_id]
            if existing != ref:
                raise FusionInputError(f"DUPLICATE_FORECAST_CONFLICT:{forecast_id}")
            continue
        role = ref.role if ref.role is not None else resolve_contributor_role(ref.forecast)
        family_key = resolve_forecast_family_key(ref.forecast, ref.forecast_family_key)
        by_id[forecast_id] = FusionContributorRef(
            forecast=ref.forecast,
            role=role,
            contributor_weight=ref.contributor_weight,
            forecast_family_key=family_key,
        )
    return sorted(by_id.values(), key=lambda row: row.forecast.forecast_id)


def build_contributor_ref(
    forecast,
    *,
    role: ForecastContributorRole | None = None,
    contributor_weight: float = 1.0,
    forecast_family_key: str | None = None,
) -> FusionContributorRef:
    resolved_role = role if role is not None else resolve_contributor_role(forecast)
    return FusionContributorRef(
        forecast=forecast,
        role=resolved_role,
        contributor_weight=contributor_weight,
        forecast_family_key=resolve_forecast_family_key(forecast, forecast_family_key),
    )


def control_only_diagnostics(contributors: tuple[FusionContributorRef, ...]) -> tuple[FusionDiagnostic, ...]:
  if not contributors:
      return (FusionDiagnostic(FusionDiagnosticCode.NO_ELIGIBLE_CONTRIBUTOR, "no contributors"),)
  if all(ref.role != ForecastContributorRole.PRODUCTION for ref in contributors):
      return (FusionDiagnostic(FusionDiagnosticCode.CONTROL_EXCLUDED, "control-only manifest"),)
  return ()


__all__ = [
    "ForecastFusionManifest",
    "build_contributor_ref",
    "control_only_diagnostics",
]
