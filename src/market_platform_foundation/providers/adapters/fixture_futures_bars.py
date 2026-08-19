"""Fixture-first ES settlement bars adapter (F5)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult

DEFAULT_BARS_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "futures"
    / "es_settlement_bars_slice.json"
)


class FixtureFuturesBarsProvider:
    """Offline settlement bar adapter returning PIT-filtered bars with history sidecars."""

    provider_id = "bars.fixture.futures_settlement"
    capability = "futures_bars"
    entitlement = "BARS_ES_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None) -> None:
        path = fixture_path or DEFAULT_BARS_FIXTURE
        self._fixture = json.loads(path.read_text(encoding="utf-8"))

    def fetch_bars(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        symbol_upper = symbol.upper()
        fixture_symbol = str(self._fixture.get("symbol", "")).upper()
        if fixture_symbol != symbol_upper:
            return ProviderResult(
                status="unavailable",
                reason_code="BARS_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        bars = self._fixture.get("bars", [])
        if not isinstance(bars, list) or not bars:
            return ProviderResult(
                status="unavailable",
                reason_code="BARS_NO_DATA",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        meta_event: dict[str, Any] = {
            "_meta": True,
            "instrument_family": str(self._fixture.get("instrument_family", symbol_upper)),
            "carry_history": self._fixture.get("carry_history", []),
            "curve_slope_history": self._fixture.get("curve_slope_history", []),
        }

        eligible: list[dict[str, Any]] = [meta_event]
        for bar in bars:
            if not isinstance(bar, dict):
                continue
            event_time = str(bar.get("event_time") or bar.get("date", ""))
            if as_of_time_ns is not None and event_time:
                if iso_to_epoch_ns(event_time) > as_of_time_ns:
                    continue
            eligible.append(dict(bar))

        if len(eligible) < 2:
            return ProviderResult(
                status="unavailable",
                reason_code="BARS_NOT_PIT_ELIGIBLE",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        return ProviderResult(
            status="available",
            events=tuple(eligible),
            provider_id=self.provider_id,
            capability=self.capability,
        )


__all__ = ["DEFAULT_BARS_FIXTURE", "FixtureFuturesBarsProvider"]
