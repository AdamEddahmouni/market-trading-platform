"""Typed forecast interface per ADR-FCAST-001."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MODEL_INTERFACE_VERSION = "1.0.0"


@dataclass(frozen=True)
class ForecastResult:
    fallback_reason_code: str | None
    horizon_ns: int
    interface_version: str
    prediction_cutoff: int
    probability: None
    score: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fallback_reason_code": self.fallback_reason_code,
            "horizon_ns": self.horizon_ns,
            "interface_version": self.interface_version,
            "prediction_cutoff": self.prediction_cutoff,
            "probability": self.probability,
            "score": self.score,
            "status": self.status,
        }


def build_forecast(
    *,
    score: str,
    prediction_cutoff: int,
    horizon_ns: int,
    status: str = "ok",
    fallback_reason_code: str | None = None,
) -> dict[str, Any]:
    result = ForecastResult(
        fallback_reason_code=fallback_reason_code,
        horizon_ns=horizon_ns,
        interface_version=MODEL_INTERFACE_VERSION,
        prediction_cutoff=prediction_cutoff,
        probability=None,
        score=score,
        status=status,
    )
    return result.to_dict()


def verify_forecast_interface(forecast: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if forecast.get("interface_version") != MODEL_INTERFACE_VERSION:
        reasons.append("FCAST_INTERFACE_VERSION_MISMATCH")
    if forecast.get("probability") is not None:
        reasons.append("FCAST_UNCALIBRATED_PROBABILITY_CLAIM")
    if "score" not in forecast:
        reasons.append("FCAST_MISSING_SCORE")
    if "horizon_ns" not in forecast:
        reasons.append("FCAST_MISSING_HORIZON")
    status = "PASS" if not reasons else "FAIL"
    return status, reasons
