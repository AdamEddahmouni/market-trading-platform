"""Narrow BUILD 08/14 registration helpers (BUILD 15)."""

from __future__ import annotations

from ..contracts.forecast import ForecastV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..fusion.types import ForecastContributorRole
from ..persistence.repository import IntelligenceRepository
from .service import PredictionLedgerService
from .types import SettlementMode, SettlementResult


def register_control_forecast_for_settlement(
    forecast: ForecastV1,
    repository: IntelligenceRepository,
    *,
    now_ns: int,
) -> PredictionLedgerEntryV1 | SettlementResult:
    """Register a BUILD 08 control forecast while preserving CONTROL role metadata."""
    if forecast.metadata.get("contributor_role") != ForecastContributorRole.CONTROL.value:
        raise ValueError("FORECAST_NOT_CONTROL")
    service = PredictionLedgerService(repository)
    return service.register_forecast(
        forecast,
        now_ns=now_ns,
        mode=SettlementMode.ACTUAL_LIVE,
    )


def register_final_forecast_for_settlement(
    forecast: ForecastV1,
    repository: IntelligenceRepository,
    *,
    now_ns: int,
) -> PredictionLedgerEntryV1 | SettlementResult:
    """Register a BUILD 14 final fused forecast without mutating forecast content."""
    stage = forecast.metadata.get("forecast_stage")
    if stage not in {"FINAL_FUSED_CALIBRATED", "PRODUCTION_RAW"}:
        raise ValueError("FORECAST_NOT_FINAL")
    service = PredictionLedgerService(repository)
    return service.register_forecast(
        forecast,
        now_ns=now_ns,
        mode=SettlementMode.ACTUAL_LIVE,
    )


__all__ = [
    "register_control_forecast_for_settlement",
    "register_final_forecast_for_settlement",
]
