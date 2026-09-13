"""Fail-closed persist for Path A PRODUCTION contributor + calibrator JSON.

Serializes an already-emitted PRODUCTION_RAW ForecastV1 and a temporally
legal CalibrationModelArtifact. Persist is allowed only on Paper/Demo after
identity, PIT, and method gates pass. Tests may write tempdirs. This module
does not mint probabilities, does not treat tempfile JSON as empirical, and
does not activate Live.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..intelligence.contracts.forecast import ForecastV1
from ..intelligence.fusion.types import (
    CalibrationMethod,
    CalibrationModelArtifact,
    ForecastContributorRole,
    PRODUCTION_FORECAST_STAGE,
)
from ..intelligence.production.identity import matches_path_a_identity
from .path_a_forecast_producer import (
    persist_paper_demo_calibration,
    persist_paper_demo_forecast,
)
from .path_a_scan_caller import ALLOWED_SCAN_MODES, FORBIDDEN_LIVE_MODES

STATUS_PERSISTED = "PERSISTED"
STATUS_FORECAST_UNAVAILABLE = "FORECAST_UNAVAILABLE"
STATUS_CALIBRATION_UNAVAILABLE = "CALIBRATION_UNAVAILABLE"
STATUS_LIVE_FORBIDDEN = "LIVE_FORBIDDEN"


def _normalize_mode(value: str) -> str:
    return str(value).strip().lower()


@dataclass(frozen=True, slots=True)
class PathAProductionPersistResult:
    status: str
    reason_codes: tuple[str, ...]
    payload: dict[str, Any] | None = None
    forecast: ForecastV1 | None = None
    artifact: CalibrationModelArtifact | None = None

    @property
    def persisted(self) -> bool:
        return self.status == STATUS_PERSISTED and self.payload is not None


def _unavailable(status: str, *reason_codes: str) -> PathAProductionPersistResult:
    codes = tuple(dict.fromkeys((status, *reason_codes)))
    return PathAProductionPersistResult(status=status, reason_codes=codes)


def persist_path_a_production_contributor(
    forecast: ForecastV1,
    *,
    destination: str | Path,
    mode: str,
) -> PathAProductionPersistResult:
    """Persist PRODUCTION_RAW only. Unlawful forecasts write nothing."""

    mode_n = _normalize_mode(mode)
    if mode_n in FORBIDDEN_LIVE_MODES:
        return PathAProductionPersistResult(
            status=STATUS_LIVE_FORBIDDEN,
            reason_codes=("LIVE_SCAN_CALLER_FORBIDDEN",),
        )
    if mode_n not in ALLOWED_SCAN_MODES:
        return _unavailable(STATUS_FORECAST_UNAVAILABLE, "MODE_NOT_PAPER_OR_DEMO")
    if not isinstance(forecast, ForecastV1):
        return _unavailable(STATUS_FORECAST_UNAVAILABLE, "FORECAST_V1_REQUIRED")
    metadata = forecast.metadata
    if str(metadata.get("contributor_role") or "") != ForecastContributorRole.PRODUCTION.value:
        return _unavailable(STATUS_FORECAST_UNAVAILABLE, "FORECAST_ROLE_NOT_ALLOWED")
    if str(metadata.get("forecast_stage") or "") != PRODUCTION_FORECAST_STAGE:
        return _unavailable(STATUS_FORECAST_UNAVAILABLE, "FORECAST_STAGE_NOT_ALLOWED")
    if str(metadata.get("calibration_status") or "").upper() != "UNCALIBRATED":
        return _unavailable(STATUS_FORECAST_UNAVAILABLE, "CONTRIBUTOR_MUST_BE_UNCALIBRATED")
    if forecast.estimate.calibrated_probability is not None:
        return _unavailable(STATUS_FORECAST_UNAVAILABLE, "CONTRIBUTOR_MUST_BE_UNCALIBRATED")
    identity_reasons = matches_path_a_identity(target=forecast.target, horizon=forecast.horizon)
    if identity_reasons:
        return _unavailable(STATUS_FORECAST_UNAVAILABLE, *identity_reasons)
    payload = persist_paper_demo_forecast(forecast, destination=destination)
    return PathAProductionPersistResult(
        status=STATUS_PERSISTED,
        reason_codes=(STATUS_PERSISTED,),
        payload=payload,
        forecast=forecast,
    )


def persist_path_a_production_calibration(
    artifact: CalibrationModelArtifact,
    *,
    destination: str | Path,
    mode: str,
    decision_time_ns: int,
) -> PathAProductionPersistResult:
    """Persist LOGISTIC/ISOTONIC only when available at decision time."""

    mode_n = _normalize_mode(mode)
    if mode_n in FORBIDDEN_LIVE_MODES:
        return PathAProductionPersistResult(
            status=STATUS_LIVE_FORBIDDEN,
            reason_codes=("LIVE_SCAN_CALLER_FORBIDDEN",),
        )
    if mode_n not in ALLOWED_SCAN_MODES:
        return _unavailable(STATUS_CALIBRATION_UNAVAILABLE, "MODE_NOT_PAPER_OR_DEMO")
    if not isinstance(artifact, CalibrationModelArtifact):
        return _unavailable(STATUS_CALIBRATION_UNAVAILABLE, "CALIBRATION_ARTIFACT_REQUIRED")
    if artifact.method == CalibrationMethod.IDENTITY_CONTROL:
        return _unavailable(STATUS_CALIBRATION_UNAVAILABLE, "IDENTITY_CONTROL_REJECTED")
    if artifact.method not in {CalibrationMethod.LOGISTIC_PROBABILITY, CalibrationMethod.ISOTONIC}:
        return _unavailable(STATUS_CALIBRATION_UNAVAILABLE, "UNSUPPORTED_CALIBRATION_METHOD")
    identity_reasons = matches_path_a_identity(target=artifact.target, horizon=artifact.horizon)
    if identity_reasons:
        return _unavailable(STATUS_CALIBRATION_UNAVAILABLE, *identity_reasons)
    if artifact.available_time_ns > decision_time_ns:
        return _unavailable(STATUS_CALIBRATION_UNAVAILABLE, "CALIBRATION_NOT_YET_AVAILABLE")
    payload = persist_paper_demo_calibration(artifact, destination=destination)
    return PathAProductionPersistResult(
        status=STATUS_PERSISTED,
        reason_codes=(STATUS_PERSISTED,),
        payload=payload,
        artifact=artifact,
    )


__all__ = [
    "PathAProductionPersistResult",
    "STATUS_CALIBRATION_UNAVAILABLE",
    "STATUS_FORECAST_UNAVAILABLE",
    "STATUS_LIVE_FORBIDDEN",
    "STATUS_PERSISTED",
    "emit_production_forecast",
    "persist_path_a_production_calibration",
    "persist_path_a_production_contributor",
]
