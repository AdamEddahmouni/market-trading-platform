"""Fail-closed Paper/Demo Path A PRODUCTION ForecastV1 producer.

The real persist path is BUILD 14 ``ForecastFusionService``: a fused forecast
is emitted only when production policy permits, then serialized through
``persist_paper_demo_forecast``. This module does not mint a probability from
a quote print, does not inject a fixture probability, does not call CONTROL
baseline construction, and does not wrap a research score dict as empirical.

Software producer wiring is not FTEP ``EMPIRICAL_ACTIVE``. Absent PRODUCTION
contributors, missing/illegal calibration, CONTROL/RESEARCH/uncalibrated
output, or identity/PIT/champion/horizon/account/mode mismatch fail closed
(``FORECAST_UNAVAILABLE``) and persist nothing.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from ..canonical import load_json_strict, write_canonical_json
from ..intelligence.contracts.common import (
    forecast_target_from_dict,
    forecast_target_to_dict,
    time_horizon_from_dict,
    time_horizon_to_dict,
)
from ..intelligence.contracts.forecast import ForecastV1
from ..intelligence.evaluation.types import forecast_role
from ..intelligence.fusion import (
    DEFAULT_PRODUCTION_FINAL_POLICY,
    DEFAULT_PRODUCTION_FUSION_POLICY,
    CalibrationError,
    CalibrationMethod,
    CalibrationStatus,
    FINAL_FORECAST_STAGE,
    ForecastContributorRole,
    ForecastDecisionStatus,
    ForecastFusionManifest,
    ForecastFusionService,
    FusionContributorRef,
    FusionError,
    build_contributor_ref,
    resolve_contributor_role,
)
from ..intelligence.fusion.types import CalibrationModelArtifact
from ..intelligence.opportunity.types import OpportunityPolicyV1
from ..intelligence.persistence import InMemoryIntelligenceRepository
from ..intelligence.persistence.repository import IntelligenceRepository
from ..intelligence.promotion.types import ChampionAssignmentV1
from .path_a_forecast_store import (
    forecast_matches_path_a_hop_policy,
    load_paper_demo_forecasts,
    persist_paper_demo_forecast,
)
from .path_a_scan_caller import ALLOWED_SCAN_MODES, FORBIDDEN_LIVE_MODES

STATUS_EMITTED_CALIBRATED = ForecastDecisionStatus.EMITTED_CALIBRATED.value
STATUS_FORECAST_UNAVAILABLE = "FORECAST_UNAVAILABLE"
STATUS_LIVE_FORBIDDEN = "LIVE_FORBIDDEN"


def _normalize_mode(value: str) -> str:
    return str(value).strip().lower()


@dataclass(frozen=True, slots=True)
class PathAForecastProduceResult:
    """Honest outcome of one Paper/Demo fusion persist attempt."""

    status: str
    reason_codes: tuple[str, ...]
    forecast: ForecastV1 | None = None
    payload: dict[str, Any] | None = None
    fusion_status: str | None = None

    @property
    def persisted(self) -> bool:
        return self.status == STATUS_EMITTED_CALIBRATED and self.forecast is not None and self.payload is not None


def _unavailable(
    *reason_codes: str,
    fusion_status: str | None = None,
) -> PathAForecastProduceResult:
    codes = tuple(dict.fromkeys(("FORECAST_UNAVAILABLE", *reason_codes)))
    return PathAForecastProduceResult(
        status=STATUS_FORECAST_UNAVAILABLE,
        reason_codes=codes,
        fusion_status=fusion_status,
    )


def _canonical_contributor(item: object) -> FusionContributorRef | None:
    """Accept only ForecastV1 / FusionContributorRef. Never promote CONTROL/RESEARCH."""

    family_key = None
    weight = 1.0
    if isinstance(item, FusionContributorRef):
        forecast = item.forecast
        weight = item.contributor_weight
        family_key = item.forecast_family_key
    elif isinstance(item, ForecastV1):
        forecast = item
    else:
        return None
    innate = resolve_contributor_role(forecast)
    return build_contributor_ref(
        forecast,
        role=innate,
        contributor_weight=weight,
        forecast_family_key=family_key,
    )


def _bind_path_a_identity(
    forecast: ForecastV1,
    *,
    champion: ChampionAssignmentV1,
    account_id: str,
    mode: str,
) -> ForecastV1:
    metadata = dict(forecast.metadata)
    metadata["contributor_role"] = ForecastContributorRole.PRODUCTION.value
    metadata["champion_candidate_id"] = champion.candidate_id
    metadata["candidate_artifact_hash"] = champion.candidate_artifact_hash
    metadata["account_id"] = account_id
    metadata["mode"] = mode
    return replace(forecast, metadata=metadata)


def _contributor_identity(forecast: ForecastV1) -> tuple[object, ...]:
    return (
        forecast.snapshot_id,
        forecast.decision_time_ns,
        forecast.scope,
        forecast.target,
        forecast.horizon,
    )


def calibration_artifact_to_dict(artifact: CalibrationModelArtifact) -> dict[str, Any]:
    body: dict[str, Any] = {
        "available_time_ns": artifact.available_time_ns,
        "calibration_model_id": artifact.calibration_model_id,
        "class_counts": dict(artifact.class_counts),
        "dataset_fingerprint": artifact.dataset_fingerprint,
        "fusion_policy_identity": artifact.fusion_policy_identity,
        "horizon": time_horizon_to_dict(artifact.horizon),
        "max_training_raw_probability": artifact.max_training_raw_probability,
        "method": artifact.method.value,
        "method_version": artifact.method_version,
        "min_training_raw_probability": artifact.min_training_raw_probability,
        "parameter_fingerprint": artifact.parameter_fingerprint,
        "parameters": dict(artifact.parameters),
        "sample_count": artifact.sample_count,
        "target": forecast_target_to_dict(artifact.target),
        "training_cutoff_ns": artifact.training_cutoff_ns,
    }
    if artifact.regime_key is not None:
        body["regime_key"] = artifact.regime_key
    return body


def calibration_artifact_from_dict(payload: Mapping[str, Any]) -> CalibrationModelArtifact | None:
    try:
        method = CalibrationMethod(str(payload["method"]))
        return CalibrationModelArtifact(
            calibration_model_id=str(payload["calibration_model_id"]),
            method=method,
            method_version=str(payload["method_version"]),
            target=forecast_target_from_dict(dict(payload["target"])),
            horizon=time_horizon_from_dict(dict(payload["horizon"])),
            fusion_policy_identity=str(payload["fusion_policy_identity"]),
            dataset_fingerprint=str(payload["dataset_fingerprint"]),
            training_cutoff_ns=int(payload["training_cutoff_ns"]),
            available_time_ns=int(payload["available_time_ns"]),
            parameters=dict(payload.get("parameters") or {}),
            parameter_fingerprint=str(payload["parameter_fingerprint"]),
            min_training_raw_probability=float(payload["min_training_raw_probability"]),
            max_training_raw_probability=float(payload["max_training_raw_probability"]),
            sample_count=int(payload["sample_count"]),
            class_counts={str(k): int(v) for k, v in dict(payload.get("class_counts") or {}).items()},
            regime_key=payload.get("regime_key"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def persist_paper_demo_calibration(
    artifact: CalibrationModelArtifact,
    *,
    destination: str | Path,
) -> dict[str, Any]:
    """Serialize an already-constructed calibrator. Not a trainer."""

    dest = Path(destination)
    payload = calibration_artifact_to_dict(artifact)
    if dest.suffix.lower() == ".json":
        target = dest
    else:
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / f"{artifact.calibration_model_id}.json"
    write_canonical_json(target, payload)
    return payload


def load_paper_demo_calibration(source: str | Path | None) -> CalibrationModelArtifact | None:
    """Load one previously persisted calibrator. Missing/corrupt → None."""

    if source is None:
        return None
    path = Path(source)
    if not path.exists():
        return None
    targets = sorted(path.glob("*.json")) if path.is_dir() else (path,)
    for child in targets:
        try:
            payload = load_json_strict(child)
        except (OSError, TypeError, ValueError):
            continue
        if not isinstance(payload, Mapping):
            continue
        artifact = calibration_artifact_from_dict(payload)
        if artifact is not None:
            return artifact
    return None


def load_paper_demo_contributors(source: str | Path | None) -> tuple[ForecastV1, ...]:
    """Load PRODUCTION-eligible contributor ForecastV1 rows. Missing → empty."""

    if source is None:
        return ()
    return load_paper_demo_forecasts(source)


def produce_paper_demo_forecast(
    *,
    contributors: Iterable[object],
    calibration_artifact: CalibrationModelArtifact | None,
    champion: ChampionAssignmentV1,
    policy: OpportunityPolicyV1,
    destination: str | Path,
    account_id: str,
    mode: str,
    repository: IntelligenceRepository | None = None,
    as_of_time_ns: int | None = None,
) -> PathAForecastProduceResult:
    """Fuse PRODUCTION contributors and persist only a calibrated hop artifact.

    Does not accept a quote print, a raw probability, or a research score.
    CONTROL, RESEARCH, IDENTITY_CONTROL, uncalibrated, and fusion abstention
    persist nothing.
    """

    mode_n = _normalize_mode(mode)
    if mode_n in FORBIDDEN_LIVE_MODES:
        return PathAForecastProduceResult(
            status=STATUS_LIVE_FORBIDDEN,
            reason_codes=("LIVE_SCAN_CALLER_FORBIDDEN",),
        )
    if mode_n not in ALLOWED_SCAN_MODES:
        return _unavailable("MODE_NOT_PAPER_OR_DEMO")
    account = str(account_id or "").strip()
    if not account:
        return _unavailable("ACCOUNT_ID_REQUIRED")
    champion_mode = str(champion.champion_scope.mode or "").strip().lower()
    if champion_mode and champion_mode != mode_n:
        return _unavailable("MODE_MISMATCH")

    refs: list[FusionContributorRef] = []
    rejected_non_forecast = False
    for item in contributors:
        canonical = _canonical_contributor(item)
        if canonical is None:
            rejected_non_forecast = True
            continue
        refs.append(canonical)
    if not refs:
        reason = "RESEARCH_REJECTED" if rejected_non_forecast else "NO_PRODUCTION_CONTRIBUTORS"
        return _unavailable(reason)

    production_refs = [ref for ref in refs if ref.role == ForecastContributorRole.PRODUCTION]
    if not production_refs:
        return _unavailable("ABSTAINED_CONTROL_ONLY", fusion_status=ForecastDecisionStatus.ABSTAINED_CONTROL_ONLY.value)

    identity = _contributor_identity(production_refs[0].forecast)
    if any(_contributor_identity(ref.forecast) != identity for ref in production_refs):
        return _unavailable("CONTRIBUTOR_IDENTITY_MISMATCH")

    seed = production_refs[0].forecast
    if seed.target.target_kind != champion.champion_scope.target_kind:
        return _unavailable("TARGET_MISMATCH")
    if seed.horizon.duration_ns != champion.champion_scope.horizon_ns:
        return _unavailable("HORIZON_MISMATCH")
    if seed.decision_time_ns < champion.effective_from_ns:
        return _unavailable("CHAMPION_NOT_EFFECTIVE")
    if as_of_time_ns is not None and seed.decision_time_ns > as_of_time_ns:
        return _unavailable("FORECAST_PIT_VIOLATION")

    if calibration_artifact is None:
        return _unavailable(
            "ABSTAINED_CALIBRATION_UNAVAILABLE",
            fusion_status=ForecastDecisionStatus.ABSTAINED_CALIBRATION_UNAVAILABLE.value,
        )
    if calibration_artifact.method == CalibrationMethod.IDENTITY_CONTROL:
        return _unavailable("IDENTITY_CONTROL_REJECTED")

    fusion_policy = DEFAULT_PRODUCTION_FUSION_POLICY
    final_policy = DEFAULT_PRODUCTION_FINAL_POLICY
    if final_policy.research_mode or final_policy.allow_raw_research_output:
        return _unavailable("RESEARCH_POLICY_REJECTED")
    if not final_policy.require_calibration:
        return _unavailable("UNCALIBRATED_POLICY_REJECTED")

    repo = repository if repository is not None else InMemoryIntelligenceRepository()
    for ref in refs:
        repo.put_forecast(ref.forecast)

    try:
        manifest = ForecastFusionManifest.create(
            snapshot_id=seed.snapshot_id,
            target=seed.target,
            horizon=seed.horizon,
            decision_time_ns=seed.decision_time_ns,
            scope=seed.scope,
            contributors=refs,
            fusion_policy=fusion_policy,
        )
        service = ForecastFusionService(
            repo,
            fusion_policy=fusion_policy,
            final_policy=final_policy,
        )
        result = service.evaluate(
            manifest,
            calibration_artifact=calibration_artifact,
            persist=False,
            final_policy=final_policy,
        )
    except (FusionError, CalibrationError, ValueError, TypeError):
        return _unavailable("FUSION_FAILED")

    fusion_status = result.status.value
    if result.status != ForecastDecisionStatus.EMITTED_CALIBRATED or result.forecast is None:
        reason = fusion_status if fusion_status else "FUSION_ABSTAINED"
        return _unavailable(reason, fusion_status=fusion_status)

    fused = result.forecast
    stage = str(fused.metadata.get("forecast_stage") or "")
    calibration = str(fused.metadata.get("calibration_status") or "").upper()
    if stage != FINAL_FORECAST_STAGE:
        return _unavailable("FORECAST_STAGE_NOT_ALLOWED", fusion_status=fusion_status)
    if calibration != CalibrationStatus.CALIBRATED.value:
        if calibration == CalibrationStatus.IDENTITY_CONTROL.value:
            return _unavailable("IDENTITY_CONTROL_REJECTED", fusion_status=fusion_status)
        return _unavailable("UNCALIBRATED_REJECTED", fusion_status=fusion_status)
    calibrated = fused.estimate.calibrated_probability
    if calibrated is None or not math.isfinite(float(calibrated)):
        return _unavailable("CALIBRATED_PROBABILITY_REQUIRED", fusion_status=fusion_status)
    if forecast_role(fused) in {
        ForecastContributorRole.CONTROL.value,
        ForecastContributorRole.RESEARCH.value,
    }:
        return _unavailable("FORECAST_ROLE_NOT_ALLOWED", fusion_status=fusion_status)

    bound = _bind_path_a_identity(
        fused,
        champion=champion,
        account_id=account,
        mode=mode_n,
    )
    if not forecast_matches_path_a_hop_policy(bound, champion=champion, policy=policy):
        return _unavailable("HOP_POLICY_REJECTED", fusion_status=fusion_status)

    payload = persist_paper_demo_forecast(bound, destination=destination)
    repo.put_forecast(bound)
    return PathAForecastProduceResult(
        status=STATUS_EMITTED_CALIBRATED,
        reason_codes=("EMITTED_CALIBRATED",),
        forecast=bound,
        payload=payload,
        fusion_status=fusion_status,
    )


__all__ = [
    "PathAForecastProduceResult",
    "STATUS_EMITTED_CALIBRATED",
    "STATUS_FORECAST_UNAVAILABLE",
    "STATUS_LIVE_FORBIDDEN",
    "calibration_artifact_from_dict",
    "calibration_artifact_to_dict",
    "load_paper_demo_calibration",
    "load_paper_demo_contributors",
    "persist_paper_demo_calibration",
    "produce_paper_demo_forecast",
]
