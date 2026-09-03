"""Fixture-first physical distribution forecast adapter (SHARED P2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...contracts.physical_distribution import physical_distribution_to_dict
from ...research.distribution import physical_distribution_forecast
from ..contracts import ProviderResult

DEFAULT_DISTRIBUTION_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "distribution"
    / "nvda_bars_slice.json"
)

ORDER_FLOW_BARS_FALLBACK = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "order_flow"
    / "nvda_order_flow_slice.json"
)


class FixtureDistributionForecastProvider:
    """Offline distribution forecast from admitted bar OHLCV fixtures."""

    provider_id = "distribution.fixture.forecast"
    capability = "distribution_forecast"

    def __init__(self, *, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_DISTRIBUTION_FIXTURE
        self._fixture = self._load_fixture()

    def _load_fixture(self) -> dict[str, Any]:
        path = self.fixture_path
        if not path.exists():
            path = ORDER_FLOW_BARS_FALLBACK
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("DISTRIBUTION_FIXTURE_INVALID")
        return payload

    def fetch_distribution_forecast(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        del as_of_time_ns
        fixture_symbol = str(self._fixture.get("symbol", "")).upper()
        if symbol.upper() != fixture_symbol:
            return ProviderResult(
                status="unavailable",
                reason_code="DISTRIBUTION_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        bars = self._fixture.get("bars", [])
        if not isinstance(bars, list) or len(bars) < 5:
            return ProviderResult(
                status="unavailable",
                reason_code="DISTRIBUTION_INSUFFICIENT_BARS",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        closes = [
            float(bar["close"])
            for bar in bars
            if isinstance(bar, dict) and bar.get("close") is not None
        ]
        if len(closes) < 5:
            return ProviderResult(
                status="unavailable",
                reason_code="DISTRIBUTION_NO_CLOSES",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        as_of_time = str(bars[-1].get("date", "")) if isinstance(bars[-1], dict) else ""
        catalyst_times = [
            str(row.get("event_time", ""))
            for row in self._fixture.get("catalyst_events", [])
            if isinstance(row, dict) and row.get("event_time")
        ]
        model = str(self._fixture.get("vol_model", "ewma"))
        if model not in {"ewma", "garch", "har_rv"}:
            model = "ewma"
        forecast = physical_distribution_forecast(
            closes,
            symbol=fixture_symbol,
            as_of_time=as_of_time,
            model=model,
            catalyst_event_times=catalyst_times,
            provenance_ref=str(self._fixture.get("fixture_id", "FIXTURE-DISTRIBUTION")),
        )
        if forecast is None:
            return ProviderResult(
                status="unavailable",
                reason_code="DISTRIBUTION_FORECAST_FAILED",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        payload = physical_distribution_to_dict(forecast)
        return ProviderResult(
            status="available",
            events=(payload,),
            provider_id=self.provider_id,
            capability=self.capability,
        )


def fetch_fixture_bar_closes(symbol: str) -> list[float] | None:
    """Extract close prices from admitted distribution fixture for a symbol."""
    provider = FixtureDistributionForecastProvider()
    fixture_symbol = str(provider._fixture.get("symbol", "")).upper()
    if symbol.upper() != fixture_symbol:
        return None
    bars = provider._fixture.get("bars", [])
    if not isinstance(bars, list):
        return None
    closes = [
        float(bar["close"])
        for bar in bars
        if isinstance(bar, dict) and bar.get("close") is not None
    ]
    return closes if len(closes) >= 2 else None


__all__ = [
    "DEFAULT_DISTRIBUTION_FIXTURE",
    "FixtureDistributionForecastProvider",
    "fetch_fixture_bar_closes",
]
