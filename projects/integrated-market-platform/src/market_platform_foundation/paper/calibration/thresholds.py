"""Preregisterable calibration threshold schema — no universal numeric defaults."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

THRESHOLD_SCHEMA_VERSION = "paper/calibration_thresholds/1.0.0"
THRESHOLD_UNSET_BLOCKING = "UNSET/BLOCKING"

_REQUIRED_KEYS = (
    "fill_no_fill_disagreement_rate_max",
    "fill_price_slippage_error_max",
    "timing_error_max_ns",
    "position_pnl_reconciliation_tolerance",
    "unexplained_divergence_rate_max",
)


class ThresholdStatus(StrEnum):
    SET = "SET"
    UNSET_BLOCKING = "UNSET/BLOCKING"


class CalibrationThresholdError(ValueError):
    """Invalid or blocking threshold configuration."""


@dataclass(frozen=True, slots=True)
class CalibrationThresholdField:
    status: ThresholdStatus
    value: float | None = None
    unit: str | None = None
    justification_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"status": self.status.value}
        if self.value is not None:
            payload["value"] = self.value
        if self.unit:
            payload["unit"] = self.unit
        if self.justification_ref:
            payload["justification_ref"] = self.justification_ref
        return payload

    @property
    def is_blocking(self) -> bool:
        return self.status == ThresholdStatus.UNSET_BLOCKING


@dataclass(frozen=True, slots=True)
class CalibrationThresholdConfig:
    schema_version: str
    thresholds: dict[str, CalibrationThresholdField]
    campaign_slug: str | None = None
    preregistered_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "campaign_slug": self.campaign_slug,
            "preregistered_at": self.preregistered_at,
            "thresholds": {key: field.to_dict() for key, field in self.thresholds.items()},
        }

    @property
    def execution_claims_blocked(self) -> bool:
        return any(field.is_blocking for field in self.thresholds.values())


def _parse_threshold_field(raw: Any, *, key: str) -> CalibrationThresholdField:
    if not isinstance(raw, Mapping):
        raise CalibrationThresholdError(f"CALIBRATION_THRESHOLD_INVALID:{key}")
    status_raw = str(raw.get("status") or "").strip()
    if status_raw == ThresholdStatus.SET.value:
        value = raw.get("value")
        if value is None or not isinstance(value, (int, float)):
            raise CalibrationThresholdError(f"CALIBRATION_THRESHOLD_VALUE_REQUIRED:{key}")
        return CalibrationThresholdField(
            status=ThresholdStatus.SET,
            value=float(value),
            unit=str(raw.get("unit") or "") or None,
            justification_ref=str(raw.get("justification_ref") or "") or None,
        )
    if status_raw == ThresholdStatus.UNSET_BLOCKING.value:
        if raw.get("value") is not None:
            raise CalibrationThresholdError(f"CALIBRATION_THRESHOLD_UNSET_MUST_NOT_HAVE_VALUE:{key}")
        return CalibrationThresholdField(status=ThresholdStatus.UNSET_BLOCKING)
    raise CalibrationThresholdError(f"CALIBRATION_THRESHOLD_STATUS_INVALID:{key}")


def default_unset_threshold_config(
    *,
    campaign_slug: str | None = None,
    preregistered_at: str | None = None,
) -> CalibrationThresholdConfig:
    """Template with every material gate UNSET/BLOCKING until owner/campaign freeze."""
    thresholds = {
        key: CalibrationThresholdField(status=ThresholdStatus.UNSET_BLOCKING) for key in _REQUIRED_KEYS
    }
    return CalibrationThresholdConfig(
        schema_version=THRESHOLD_SCHEMA_VERSION,
        thresholds=thresholds,
        campaign_slug=campaign_slug,
        preregistered_at=preregistered_at,
    )


def validate_threshold_config(payload: Mapping[str, Any]) -> CalibrationThresholdConfig:
    schema_version = str(payload.get("schema_version") or "")
    if schema_version != THRESHOLD_SCHEMA_VERSION:
        raise CalibrationThresholdError("CALIBRATION_THRESHOLD_SCHEMA_VERSION_INVALID")
    raw_thresholds = payload.get("thresholds")
    if not isinstance(raw_thresholds, Mapping):
        raise CalibrationThresholdError("CALIBRATION_THRESHOLD_MAP_REQUIRED")
    missing = [key for key in _REQUIRED_KEYS if key not in raw_thresholds]
    if missing:
        raise CalibrationThresholdError(f"CALIBRATION_THRESHOLD_MISSING:{','.join(missing)}")
    thresholds = {
        key: _parse_threshold_field(raw_thresholds[key], key=key) for key in _REQUIRED_KEYS
    }
    return CalibrationThresholdConfig(
        schema_version=schema_version,
        thresholds=thresholds,
        campaign_slug=str(payload.get("campaign_slug") or "") or None,
        preregistered_at=str(payload.get("preregistered_at") or "") or None,
    )


def load_threshold_config(payload: Mapping[str, Any]) -> CalibrationThresholdConfig:
    return validate_threshold_config(payload)


__all__ = [
    "THRESHOLD_SCHEMA_VERSION",
    "THRESHOLD_UNSET_BLOCKING",
    "CalibrationThresholdConfig",
    "CalibrationThresholdError",
    "CalibrationThresholdField",
    "ThresholdStatus",
    "default_unset_threshold_config",
    "load_threshold_config",
    "validate_threshold_config",
]
