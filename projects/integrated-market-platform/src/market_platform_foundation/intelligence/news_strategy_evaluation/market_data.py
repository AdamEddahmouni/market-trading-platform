"""Canonical fixture market data for evaluation — no external fetchers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from market_platform_foundation.news.timestamps import epoch_ns_from_iso, parse_utc_iso, to_utc_iso

from .errors import EvaluationError, EvaluationErrorCode


@dataclass(frozen=True, slots=True)
class MarketBar:
    event_time: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_time": self.event_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass(frozen=True, slots=True)
class MarketBarSeries:
    instrument_id: str
    bars: tuple[MarketBar, ...]
    series_ref: str
    interval: str = "1m"

    def bar_at_or_before(self, as_of: str) -> MarketBar | None:
        as_of_ns = epoch_ns_from_iso(as_of)
        if as_of_ns is None:
            return None
        candidate: MarketBar | None = None
        candidate_ns = -1
        for bar in self.bars:
            bar_ns = epoch_ns_from_iso(bar.event_time)
            if bar_ns is None or bar_ns > as_of_ns:
                continue
            if bar_ns >= candidate_ns:
                candidate = bar
                candidate_ns = bar_ns
        return candidate

    def bars_in_window(self, start: str, end: str) -> tuple[MarketBar, ...]:
        start_ns = epoch_ns_from_iso(start)
        end_ns = epoch_ns_from_iso(end)
        if start_ns is None or end_ns is None:
            return ()
        selected: list[MarketBar] = []
        for bar in self.bars:
            bar_ns = epoch_ns_from_iso(bar.event_time)
            if bar_ns is None:
                continue
            if start_ns < bar_ns <= end_ns:
                selected.append(bar)
        return tuple(selected)

    def assert_observable_at(self, as_of: str) -> None:
        bar = self.bar_at_or_before(as_of)
        if bar is None:
            raise EvaluationError(
                EvaluationErrorCode.MARKET_DATA_MISSING,
                f"no bar at or before {as_of} for {self.instrument_id}",
            )
        bar_ns = epoch_ns_from_iso(bar.event_time)
        as_of_ns = epoch_ns_from_iso(as_of)
        if bar_ns is None or as_of_ns is None or bar_ns > as_of_ns:
            raise EvaluationError(
                EvaluationErrorCode.FUTURE_MARKET_LEAK,
                f"market bar after as_of for {self.instrument_id}",
            )


class FixtureMarketDataProvider:
    """Loads deterministic synthetic bars from evaluation fixture packs."""

    def __init__(self, *, bars_by_instrument: dict[str, MarketBarSeries] | None = None) -> None:
        self._series = bars_by_instrument or {}

    @classmethod
    def from_fixture_payload(cls, payload: dict[str, Any]) -> FixtureMarketDataProvider:
        market = payload.get("market_bars", {})
        if not isinstance(market, dict):
            return cls()
        series_map: dict[str, MarketBarSeries] = {}
        for instrument_id, rows in market.items():
            if not isinstance(rows, list):
                continue
            bars: list[MarketBar] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                bars.append(
                    MarketBar(
                        event_time=str(row["event_time"]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]) if row.get("volume") is not None else None,
                    )
                )
            bars.sort(key=lambda b: epoch_ns_from_iso(b.event_time) or 0)
            series_map[str(instrument_id)] = MarketBarSeries(
                instrument_id=str(instrument_id),
                bars=tuple(bars),
                series_ref=str(payload.get("market_data_ref", "fixture/evaluation")),
                interval=str(payload.get("bar_interval", "1m")),
            )
        return cls(bars_by_instrument=series_map)

    @classmethod
    def from_fixture_path(cls, path: Path) -> FixtureMarketDataProvider:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("EVALUATION_FIXTURE_INVALID")
        return cls.from_fixture_payload(payload)

    def get_series(self, instrument_id: str) -> MarketBarSeries | None:
        return self._series.get(instrument_id)

    def price_at_as_of(self, instrument_id: str, as_of: str) -> tuple[float | None, str]:
        series = self.get_series(instrument_id)
        if series is None:
            return None, ""
        bar = series.bar_at_or_before(as_of)
        if bar is None:
            return None, ""
        return bar.close, bar.event_time

    def window_end_iso(self, as_of: str, duration_seconds: int) -> str:
        parsed = parse_utc_iso(as_of)
        if parsed is None:
            raise EvaluationError(EvaluationErrorCode.CONFIG_INVALID, f"invalid as_of: {as_of}")
        from datetime import timedelta

        end = parsed + timedelta(seconds=duration_seconds)
        return to_utc_iso(end)


__all__ = [
    "FixtureMarketDataProvider",
    "MarketBar",
    "MarketBarSeries",
]
