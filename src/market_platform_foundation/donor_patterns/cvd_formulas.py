"""Lee-Ready aggressor and BVC estimators — reimplemented from CVD Bubble concepts."""

from __future__ import annotations

import math
from typing import Sequence


def classify_aggressor(
    price: float,
    size: float,
    bid: float | None,
    ask: float | None,
    prev_price: float | None,
    prev_dir: float = 0.0,
    *,
    use_midpoint: bool = False,
) -> float:
    """Return signed delta: +size buy, -size sell, 0 indeterminate."""
    if bid is not None and ask is not None and bid < ask:
        if use_midpoint:
            mid = (bid + ask) / 2.0
            if price > mid:
                return size
            if price < mid:
                return -size
        else:
            if price >= ask:
                return size
            if price <= bid:
                return -size
    if prev_price is not None:
        if price > prev_price:
            return size
        if price < prev_price:
            return -size
        if prev_dir:
            return prev_dir * size
    return 0.0


def next_tick_dir(price: float, prev_price: float | None, prev_dir: float) -> float:
    if prev_price is None or price == prev_price:
        return prev_dir
    return 1.0 if price > prev_price else -1.0


def cumulative_delta(deltas: Sequence[float]) -> list[float]:
    total = 0.0
    out: list[float] = []
    for delta in deltas:
        total += delta
        out.append(total)
    return out


def bvc_buy_sell_volume(
    closes: Sequence[float],
    volumes: Sequence[float],
    *,
    sigma_window: int = 50,
    sigma_min_periods: int = 10,
) -> tuple[list[float], list[float]]:
    """Bulk Volume Classification using stdlib math.erf for normal CDF."""
    if not closes or len(closes) != len(volumes):
        return [], []
    deltas: list[float] = []
    for index in range(len(closes)):
        if index == 0:
            deltas.append(0.0)
        else:
            deltas.append(closes[index] - closes[index - 1])
    buy_volumes: list[float] = []
    sell_volumes: list[float] = []
    for index, volume in enumerate(volumes):
        if index == 0 or volume <= 0:
            buy_volumes.append(0.0)
            sell_volumes.append(0.0)
            continue
        start = max(0, index - sigma_window)
        window = deltas[start:index]
        if len(window) < sigma_min_periods:
            buy_volumes.append(volume / 2.0)
            sell_volumes.append(volume / 2.0)
            continue
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        sigma = math.sqrt(variance) if variance > 0 else 0.0
        if sigma == 0.0:
            buy_volumes.append(volume / 2.0)
            sell_volumes.append(volume / 2.0)
            continue
        z = deltas[index] / sigma
        buy_frac = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        buy = volume * buy_frac
        buy_volumes.append(buy)
        sell_volumes.append(volume - buy)
    return buy_volumes, sell_volumes


def ofi_events(
    bids: Sequence[float],
    asks: Sequence[float],
    bid_sizes: Sequence[float],
    ask_sizes: Sequence[float],
) -> list[float]:
    """Cont-Kukanov-Stoikov OFI event contributions (first element 0)."""
    n = len(bids)
    if n == 0 or n != len(asks) or n != len(bid_sizes) or n != len(ask_sizes):
        return []
    events = [0.0]
    for index in range(1, n):
        pb0, pb1 = bids[index - 1], bids[index]
        pa0, pa1 = asks[index - 1], asks[index]
        qb0, qb1 = bid_sizes[index - 1], bid_sizes[index]
        qa0, qa1 = ask_sizes[index - 1], ask_sizes[index]
        values = (pb0, pb1, pa0, pa1, qb0, qb1, qa0, qa1)
        if any(math.isnan(v) for v in values):
            events.append(0.0)
            continue
        d_w = qb1 * (1.0 if pb1 >= pb0 else 0.0) - qb0 * (1.0 if pb1 <= pb0 else 0.0)
        d_v = qa1 * (1.0 if pa1 <= pa0 else 0.0) - qa0 * (1.0 if pa1 >= pa0 else 0.0)
        events.append(d_w - d_v)
    return events
