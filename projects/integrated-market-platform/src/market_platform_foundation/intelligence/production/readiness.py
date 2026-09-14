"""Item 7 Lane B — PRODUCTION contributor/calibration readiness and binding diagnostics.

Validates pre-existing ``ForecastV1`` contributor JSON and calibration artifacts.
Does not mint probabilities from quotes, does not weaken gates, and never
claims ``ITEM7_COMPLETE``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contracts.forecast import ForecastV1
from ..evaluation.types import forecast_role
from ..fusion.types import (
    CONTROL_FORECAST_STAGE,
    CalibrationMethod,
    CalibrationModelArtifact,
    ForecastContributorRole,
    PRODUCTION_FORECAST_STAGE,
)
from .identity import matches_path_a_identity
from .model_store import load_production_specialist_model

STATUS_ARTIFACT_READY = "PRODUCTION_FORECAST_ARTIFACT_READY"
STATUS_BLOCKED_PREFIX = "PRODUCTION_FORECAST_BLOCKED_"

BLOCKER_NO_CONTRIBUTOR_PATH = "NO_CONTRIBUTOR_PATH"
BLOCKER_NO_VALID_PRODUCTION_CONTRIBUTOR = "NO_VALID_PRODUCTION_CONTRIBUTOR"
BLOCKER_NO_CALIBRATION_PATH = "NO_CALIBRATION_PATH"
BLOCKER_NO_VALID_CALIBRATION_ARTIFACT = "NO_VALID_CALIBRATION_ARTIFACT"
BLOCKER_NO_GOVERNED_TRAINING_CORPUS = "NO_GOVERNED_PATH_A_TRAINING_CORPUS"
BLOCKER_SOFTWARE_READY_RTH_REQUIRED = "SOFTWARE_READY_RTH_REQUIRED"
BLOCKER_PRODUCTION_CONTRIBUTOR_NOT_PREREGISTERED = "PRODUCTION_CONTRIBUTOR_NOT_PREREGISTERED"

TRAINING_MANIFEST_KIND = "path_a_production_training_manifest_v1"


def production_contributor_refusal_reasons(
    forecast: ForecastV1,
    *,
    as_of_time_ns: int | None = None,
    expected_account_id: str | None = None,
    expected_mode: str | None = None,
) -> tuple[str, ...]:
    """Return refusal codes for a candidate contributor. Empty → lawful PRODUCTION_RAW."""

    reasons: list[str] = []
    role = forecast_role(forecast)
    if role == ForecastContributorRole.CONTROL.value:
        reasons.append("CONTROL_ROLE_REJECTED")
    elif role == ForecastContributorRole.RESEARCH.value:
        reasons.append("RESEARCH_ROLE_REJECTED")
    elif role != ForecastContributorRole.PRODUCTION.value:
        reasons.append("FORECAST_ROLE_NOT_ALLOWED")

    stage = str(forecast.metadata.get("forecast_stage") or "")
    if stage == CONTROL_FORECAST_STAGE:
        reasons.append("CONTROL_STAGE_REJECTED")
    elif stage != PRODUCTION_FORECAST_STAGE:
        reasons.append("FORECAST_STAGE_NOT_ALLOWED")

    calibration = str(forecast.metadata.get("calibration_status") or "").upper()
    if calibration and calibration != "UNCALIBRATED":
        reasons.append("CONTRIBUTOR_MUST_BE_UNCALIBRATED")
    if forecast.estimate.calibrated_probability is not None:
        reasons.append("CONTRIBUTOR_MUST_BE_UNCALIBRATED")

    identity_reasons = matches_path_a_identity(target=forecast.target, horizon=forecast.horizon)
    reasons.extend(identity_reasons)

    if as_of_time_ns is not None and forecast.decision_time_ns > as_of_time_ns:
        reasons.append("FORECAST_PIT_VIOLATION")

    if expected_account_id is not None:
        bound_account = str(forecast.metadata.get("account_id") or "").strip()
        if bound_account and bound_account != expected_account_id:
            reasons.append("ACCOUNT_MISMATCH")

    if expected_mode is not None:
        bound_mode = str(forecast.metadata.get("mode") or "").strip().lower()
        expected = str(expected_mode).strip().lower()
        if bound_mode and bound_mode != expected:
            reasons.append("MODE_MISMATCH")

    return tuple(dict.fromkeys(reasons))


def is_lawful_production_raw_contributor(
    forecast: ForecastV1,
    *,
    as_of_time_ns: int | None = None,
    expected_account_id: str | None = None,
    expected_mode: str | None = None,
) -> bool:
    return not production_contributor_refusal_reasons(
        forecast,
        as_of_time_ns=as_of_time_ns,
        expected_account_id=expected_account_id,
        expected_mode=expected_mode,
    )


def calibration_artifact_refusal_reasons(
    artifact: CalibrationModelArtifact | None,
    *,
    decision_time_ns: int,
) -> tuple[str, ...]:
    if artifact is None:
        return ("CALIBRATION_ARTIFACT_MISSING",)
    reasons: list[str] = []
    if artifact.method == CalibrationMethod.IDENTITY_CONTROL:
        reasons.append("IDENTITY_CONTROL_REJECTED")
    if artifact.method not in {CalibrationMethod.LOGISTIC_PROBABILITY, CalibrationMethod.ISOTONIC}:
        reasons.append("UNSUPPORTED_CALIBRATION_METHOD")
    identity_reasons = matches_path_a_identity(target=artifact.target, horizon=artifact.horizon)
    reasons.extend(identity_reasons)
    if artifact.available_time_ns > decision_time_ns:
        reasons.append("CALIBRATION_NOT_YET_AVAILABLE")
    return tuple(dict.fromkeys(reasons))


def forecast_binding_refusal_reasons(
    *,
    forecast_id: str,
    contributor_path: Path | None,
    repository_forecast_ids: Iterable[str] | None = None,
) -> tuple[str, ...]:
    """Binding must reference a pre-existing lawful PRODUCTION_RAW contributor."""

    from ...strategy.path_a_forecast_producer import load_paper_demo_contributors

    forecast_id = str(forecast_id or "").strip()
    if not forecast_id:
        return ("FORECAST_ID_REQUIRED",)

    loaded = load_paper_demo_contributors(contributor_path) if contributor_path is not None else ()
    by_id = {str(row.forecast_id): row for row in loaded}
    forecast = by_id.get(forecast_id)
    if forecast is None:
        repo_ids = {str(item) for item in (repository_forecast_ids or ())}
        if forecast_id not in repo_ids:
            return ("BINDING_FORECAST_NOT_FOUND",)
        return ("BINDING_FORECAST_NOT_IN_CONTRIBUTOR_STORE",)

    reasons = production_contributor_refusal_reasons(forecast)
    if reasons:
        return ("BINDING_FORECAST_NOT_LAWFUL", *reasons)
    return ()


@dataclass(frozen=True, slots=True)
class ContributorScanRow:
    forecast_id: str
    lawful: bool
    refusal_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProductionReadinessReport:
    disposition: str
    first_blocker: str
    valid_contributor_ids: tuple[str, ...] = ()
    contributor_scan: tuple[ContributorScanRow, ...] = ()
    calibration_lawful: bool = False
    calibration_refusal_reasons: tuple[str, ...] = ()
    model_artifact_present: bool = False
    training_manifest_present: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_kind": "item7_production_readiness_v1",
            "calibration_lawful": self.calibration_lawful,
            "calibration_refusal_reasons": list(self.calibration_refusal_reasons),
            "contributor_scan": [
                {
                    "forecast_id": row.forecast_id,
                    "lawful": row.lawful,
                    "refusal_reasons": list(row.refusal_reasons),
                }
                for row in self.contributor_scan
            ],
            "disposition": self.disposition,
            "first_blocker": self.first_blocker,
            "model_artifact_present": self.model_artifact_present,
            "notes": list(self.notes),
            "training_manifest_present": self.training_manifest_present,
            "valid_contributor_ids": list(self.valid_contributor_ids),
        }


def _blocked(code: str, **kwargs: Any) -> ProductionReadinessReport:
    return ProductionReadinessReport(
        disposition=f"{STATUS_BLOCKED_PREFIX}{code}",
        first_blocker=code,
        **kwargs,
    )


def scan_contributor_directory(
    contributor_path: Path | None,
    *,
    as_of_time_ns: int | None = None,
    expected_account_id: str | None = None,
    expected_mode: str | None = None,
) -> tuple[ContributorScanRow, ...]:
    from ...strategy.path_a_forecast_producer import load_paper_demo_contributors

    if contributor_path is None or not contributor_path.exists():
        return ()
    rows: list[ContributorScanRow] = []
    for forecast in load_paper_demo_contributors(contributor_path):
        reasons = production_contributor_refusal_reasons(
            forecast,
            as_of_time_ns=as_of_time_ns,
            expected_account_id=expected_account_id,
            expected_mode=expected_mode,
        )
        rows.append(
            ContributorScanRow(
                forecast_id=str(forecast.forecast_id),
                lawful=not reasons,
                refusal_reasons=reasons,
            )
        )
    return tuple(sorted(rows, key=lambda row: row.forecast_id))


def assess_production_readiness(
    *,
    contributor_path: Path | None = None,
    calibration_path: Path | None = None,
    model_path: Path | None = None,
    training_manifest_path: Path | None = None,
    decision_time_ns: int,
    as_of_time_ns: int | None = None,
    expected_account_id: str | None = None,
    expected_mode: str | None = None,
) -> ProductionReadinessReport:
    """Assess operator-side PRODUCTION artifact readiness (software, not empirical)."""

    from ...strategy.path_a_forecast_producer import load_paper_demo_calibration

    as_of = decision_time_ns if as_of_time_ns is None else as_of_time_ns
    manifest_present = training_manifest_path is not None and training_manifest_path.is_file()
    model_present = load_production_specialist_model(model_path) is not None

    scan = scan_contributor_directory(
        contributor_path,
        as_of_time_ns=as_of,
        expected_account_id=expected_account_id,
        expected_mode=expected_mode,
    )
    valid_ids = tuple(row.forecast_id for row in scan if row.lawful)

    calibration = load_paper_demo_calibration(calibration_path)
    cal_reasons = calibration_artifact_refusal_reasons(calibration, decision_time_ns=decision_time_ns)
    cal_ok = not cal_reasons

    notes = (
        "Historical training artifacts are software-ready only until a weekday hop consumes them.",
        "Item 7 remains PARTIAL until empirical acceptance.",
    )

    if valid_ids and cal_ok:
        return ProductionReadinessReport(
            disposition=STATUS_ARTIFACT_READY,
            first_blocker="none",
            valid_contributor_ids=valid_ids,
            contributor_scan=scan,
            calibration_lawful=True,
            calibration_refusal_reasons=(),
            model_artifact_present=model_present,
            training_manifest_present=manifest_present,
            notes=notes,
        )

    if contributor_path is None or not contributor_path.exists():
        if model_present and cal_ok:
            return _blocked(
                BLOCKER_SOFTWARE_READY_RTH_REQUIRED,
                contributor_scan=scan,
                calibration_lawful=cal_ok,
                calibration_refusal_reasons=cal_reasons,
                model_artifact_present=True,
                training_manifest_present=manifest_present,
                notes=notes,
            )
        if not manifest_present and not model_present:
            return _blocked(
                BLOCKER_NO_GOVERNED_TRAINING_CORPUS,
                contributor_scan=scan,
                calibration_lawful=cal_ok,
                calibration_refusal_reasons=cal_reasons,
                notes=notes,
            )
        return _blocked(
            BLOCKER_NO_CONTRIBUTOR_PATH,
            contributor_scan=scan,
            calibration_lawful=cal_ok,
            calibration_refusal_reasons=cal_reasons,
            model_artifact_present=model_present,
            training_manifest_present=manifest_present,
            notes=notes,
        )

    if not valid_ids:
        return _blocked(
            BLOCKER_NO_VALID_PRODUCTION_CONTRIBUTOR,
            contributor_scan=scan,
            calibration_lawful=cal_ok,
            calibration_refusal_reasons=cal_reasons,
            model_artifact_present=model_present,
            training_manifest_present=manifest_present,
            notes=notes,
        )

    if calibration_path is None or not calibration_path.exists():
        return _blocked(
            BLOCKER_NO_CALIBRATION_PATH,
            valid_contributor_ids=valid_ids,
            contributor_scan=scan,
            calibration_lawful=False,
            calibration_refusal_reasons=cal_reasons,
            model_artifact_present=model_present,
            training_manifest_present=manifest_present,
            notes=notes,
        )

    return _blocked(
        BLOCKER_NO_VALID_CALIBRATION_ARTIFACT,
        valid_contributor_ids=valid_ids,
        contributor_scan=scan,
        calibration_lawful=False,
        calibration_refusal_reasons=cal_reasons,
        model_artifact_present=model_present,
        training_manifest_present=manifest_present,
        notes=notes,
    )


def training_manifest_kind(payload: Mapping[str, Any]) -> str | None:
    kind = payload.get("artifact_kind")
    return str(kind) if kind is not None else None


__all__ = [
    "BLOCKER_NO_CALIBRATION_PATH",
    "BLOCKER_NO_CONTRIBUTOR_PATH",
    "BLOCKER_NO_GOVERNED_TRAINING_CORPUS",
    "BLOCKER_NO_VALID_CALIBRATION_ARTIFACT",
    "BLOCKER_NO_VALID_PRODUCTION_CONTRIBUTOR",
    "BLOCKER_PRODUCTION_CONTRIBUTOR_NOT_PREREGISTERED",
    "BLOCKER_SOFTWARE_READY_RTH_REQUIRED",
    "STATUS_ARTIFACT_READY",
    "STATUS_BLOCKED_PREFIX",
    "TRAINING_MANIFEST_KIND",
    "ContributorScanRow",
    "ProductionReadinessReport",
    "assess_production_readiness",
    "calibration_artifact_refusal_reasons",
    "forecast_binding_refusal_reasons",
    "is_lawful_production_raw_contributor",
    "production_contributor_refusal_reasons",
    "scan_contributor_directory",
    "training_manifest_kind",
]
