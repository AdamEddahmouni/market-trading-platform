"""Python reference logic for PineTS parity fixtures (not Pine execution)."""

from __future__ import annotations

import math
from typing import Any, Mapping

from .pinets_fixtures import (
    FIXTURE_RSI_THRESHOLD,
    FIXTURE_SIMPLE_BREAKOUT,
    FIXTURE_SMA_CROSSOVER,
)


def bars_from_dataset_events(events: tuple[Mapping[str, Any], ...]) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for event in events:
        payload = event.get("bar_payload") if isinstance(event, dict) else None
        if not isinstance(payload, dict):
            continue
        time_key = event.get("event_time", event.get("available_time", 0))
        try:
            rows.append(
                {
                    "time": int(time_key),
                    "open": float(payload.get("open", payload.get("close", 0))),
                    "high": float(payload.get("high", payload.get("close", 0))),
                    "low": float(payload.get("low", payload.get("close", 0))),
                    "close": float(payload.get("close", 0)),
                    "volume": float(payload.get("volume", 0)),
                }
            )
        except (TypeError, ValueError):
            continue
    return rows


def _sma(values: list[float], length: int) -> list[float | None]:
    out: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < length:
            out.append(None)
            continue
        window = values[index + 1 - length : index + 1]
        out.append(sum(window) / float(length))
    return out


def _rsi(closes: list[float], length: int) -> list[float | None]:
    out: list[float | None] = []
    if length <= 0:
        return [None] * len(closes)
    gains: list[float] = []
    losses: list[float] = []
    for index in range(len(closes)):
        if index == 0:
            gains.append(0.0)
            losses.append(0.0)
            out.append(None)
            continue
        delta = closes[index] - closes[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
        if index < length:
            out.append(None)
            continue
        avg_gain = sum(gains[index - length + 1 : index + 1]) / float(length)
        avg_loss = sum(losses[index - length + 1 : index + 1]) / float(length)
        if avg_loss == 0:
            out.append(100.0 if avg_gain > 0 else 0.0)
            continue
        rs = avg_gain / avg_loss
        out.append(100.0 - (100.0 / (1.0 + rs)))
    return out


def run_reference_fixture(
    script_id: str,
    bars: list[dict[str, float | int]],
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    closes = [float(row["close"]) for row in bars]
    highs = [float(row["high"]) for row in bars]
    times = [int(row["time"]) for row in bars]
    indicators: dict[str, list[float | None]] = {}
    signals: list[dict[str, Any]] = []
    warmup_bars = 0

    if script_id == FIXTURE_SMA_CROSSOVER:
        fast_len = int(parameters.get("fast_length", 3))
        slow_len = int(parameters.get("slow_length", 5))
        warmup_bars = max(fast_len, slow_len)
        fast = _sma(closes, fast_len)
        slow = _sma(closes, slow_len)
        indicators = {"fast_sma": fast, "slow_sma": slow}
        for index in range(1, len(closes)):
            if fast[index] is None or slow[index] is None:
                continue
            if fast[index - 1] is None or slow[index - 1] is None:
                continue
            if fast[index - 1] <= slow[index - 1] and fast[index] > slow[index]:
                signals.append(
                    {
                        "time": times[index],
                        "side": "long",
                        "kind": "sma_cross_up",
                        "fast_sma": fast[index],
                        "slow_sma": slow[index],
                    }
                )
    elif script_id == FIXTURE_RSI_THRESHOLD:
        rsi_len = int(parameters.get("rsi_length", 3))
        oversold = float(parameters.get("oversold", 30.0))
        warmup_bars = rsi_len + 1
        rsi = _rsi(closes, rsi_len)
        indicators = {"rsi": rsi}
        for index in range(1, len(closes)):
            if rsi[index] is None or rsi[index - 1] is None:
                continue
            if rsi[index - 1] >= oversold and rsi[index] < oversold:
                signals.append(
                    {
                        "time": times[index],
                        "side": "long",
                        "kind": "rsi_cross_below_oversold",
                        "rsi": rsi[index],
                    }
                )
    elif script_id == FIXTURE_SIMPLE_BREAKOUT:
        lookback = int(parameters.get("lookback", 4))
        warmup_bars = lookback
        highest: list[float | None] = []
        for index in range(len(highs)):
            if index + 1 < lookback:
                highest.append(None)
                continue
            highest.append(max(highs[index + 1 - lookback : index]))
        indicators = {"highest_high": highest}
        for index in range(len(closes)):
            if highest[index] is None:
                continue
            if closes[index] > highest[index]:
                signals.append(
                    {
                        "time": times[index],
                        "side": "long",
                        "kind": "breakout_close_above_range",
                        "close": closes[index],
                        "range_high": highest[index],
                    }
                )
    else:
        raise ValueError(f"UNSUPPORTED_REFERENCE_FIXTURE:{script_id}")

    return {
        "indicators": indicators,
        "signals": signals,
        "warmup_bars": warmup_bars,
        "bar_count": len(bars),
    }


def reference_statistics(payload: dict[str, Any]) -> dict[str, float | int]:
    signals = payload.get("signals") or []
    return {
        "bar_count": int(payload.get("bar_count", 0)),
        "signal_count": len(signals),
        "warmup_bars": int(payload.get("warmup_bars", 0)),
    }
