"""AUTO_SR_V1 — deterministic market-structure support/resistance zones.

Inputs are *completed* OHLCV bars of one timeframe and session scope, ordered
by end time. The method:

1. Reference volatility ("ATR" below) is the mean true range of the input's
   regular-session bars when at least ``ATR_PERIOD`` exist, otherwise Wilder
   ATR(14) over all bars. Thin pre-/after-hours bars would otherwise collapse
   the tolerance to a few ticks. Tolerance is ``max(0.25 * ATR, 2 ticks)``.
2. A bar ``i`` is a swing high when its high is strictly above the highs of the
   ``PIVOT_SPAN`` (3) bars before it and at or above the highs of the
   ``PIVOT_SPAN`` bars after it (mirror rule for swing lows). The pivot is
   *confirmed* at the end of bar ``i + PIVOT_SPAN``; a pivot whose confirming
   bars are not in the input does not exist. The input contains only completed
   bars, so no pivot can use a bar that was not yet available (no lookahead).
   A pivot is significant only when its rejection (the move away from it inside
   the confirmation window) is at least ``MIN_REJECTION_ATR`` (0.5) ATR.
3. Significant pivots (highs and lows together; role reversal is allowed) are sorted by
   price and greedily clustered: a pivot joins the open cluster while it is
   within one tolerance of the previous member and within ``2 * tolerance`` of
   the cluster's lowest member.
4. A zone spans its members' prices, widened symmetrically to at least one
   tolerance so a single pivot is shown as a band, not false precision. The
   widening is clipped at the midpoint to a neighbouring cluster, so zones
   never overlap.
5. Zone strength (0-100) is structural evidence, not a probability:
   touches ``min(n, 4) / 4 * 40`` + recency ``30 * 0.5 ** (age / 48 bars)`` +
   rejection ``20 * min(mean rejection / ATR, 2) / 2`` + volume
   ``10 * min(mean pivot volume / median volume, 2) / 2`` (0 when volume is
   unavailable). Rejection is the move away from the pivot inside its
   confirmation window. Age counts bars since the zone's latest member.
6. Relative to the current price, zones wholly below are support, wholly above
   are resistance, and a zone containing the price is being tested. Nearest
   support/resistance are the closest zones with strength >= ``MIN_STRENGTH``.
   Distances are to the nearest zone edge as a percent of current price.

Zone construction is independent of the current price, so zones are cached per
input dataset and only classification is repeated when price moves.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

METHOD = "AUTO_SR_V1"
ATR_PERIOD = 14
PIVOT_SPAN = 3
MIN_REJECTION_ATR = 0.5
MIN_BARS = 20
TOLERANCE_ATR = 0.25
CLUSTER_WIDTH_TOLERANCES = 2.0
RECENCY_HALF_LIFE_BARS = 48.0
MIN_STRENGTH = 20
MAX_ZONES = 12


class BarLike(Protocol):
    end_ns: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    session: str


@dataclass(frozen=True, slots=True)
class Pivot:
    index: int
    kind: str  # HIGH | LOW
    price: float
    confirmed_end_ns: int
    rejection: float
    volume: float | None


@dataclass(frozen=True, slots=True)
class Zone:
    lower: float
    upper: float
    center: float
    touches: int
    strength: int
    last_touch_end_ns: int
    kinds: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"lower": self.lower, "upper": self.upper, "center": self.center, "touches": self.touches,
                "strength": self.strength, "last_touch_end_ns": self.last_touch_end_ns, "kinds": list(self.kinds)}


@dataclass(frozen=True, slots=True)
class Structure:
    """Price-independent result of AUTO_SR_V1 over one bar dataset."""

    reason: str | None
    bar_count: int
    latest_bar_end_ns: int | None
    atr: float | None
    tolerance: float | None
    pivots: tuple[Pivot, ...]
    zones: tuple[Zone, ...]
    volatility_basis: str | None = None


def tick_size(price: float) -> float:
    return 0.01 if price >= 1 else 0.0001


def _valid(bar: BarLike) -> bool:
    values = (bar.open, bar.high, bar.low, bar.close)
    return (all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in values)
            and bar.low <= min(bar.open, bar.close) and bar.high >= max(bar.open, bar.close))


def wilder_atr(bars: Sequence[BarLike], period: int = ATR_PERIOD) -> float | None:
    if len(bars) < period + 1:
        return None
    ranges = [max(bar.high - bar.low, abs(bar.high - prev.close), abs(bar.low - prev.close))
              for prev, bar in zip(bars, bars[1:])]
    atr = sum(ranges[:period]) / period
    for value in ranges[period:]:
        atr = (atr * (period - 1) + value) / period
    return atr


def reference_volatility(bars: Sequence[BarLike]) -> tuple[float | None, str]:
    """Regular-session mean true range when available, else Wilder ATR(14)."""

    regular = [max(bar.high - bar.low, abs(bar.high - prev.close), abs(bar.low - prev.close))
               for prev, bar in zip(bars, bars[1:]) if getattr(bar, "session", None) == "REGULAR"]
    if len(regular) >= ATR_PERIOD:
        return sum(regular) / len(regular), "REGULAR_MEAN_TRUE_RANGE"
    return wilder_atr(bars), "WILDER_ATR_14"


def confirmed_pivots(bars: Sequence[BarLike], span: int = PIVOT_SPAN) -> list[Pivot]:
    """Swing pivots whose confirming ``span`` bars are all present in ``bars``."""

    pivots: list[Pivot] = []
    for index in range(span, len(bars) - span):
        bar = bars[index]
        left, right = bars[index - span:index], bars[index + 1:index + span + 1]
        confirmed = bars[index + span].end_ns
        if all(bar.high > other.high for other in left) and all(bar.high >= other.high for other in right):
            pivots.append(Pivot(index, "HIGH", bar.high, confirmed,
                                max(0.0, bar.high - min(other.low for other in right)), bar.volume))
        if all(bar.low < other.low for other in left) and all(bar.low <= other.low for other in right):
            pivots.append(Pivot(index, "LOW", bar.low, confirmed,
                                max(0.0, max(other.high for other in right) - bar.low), bar.volume))
    return pivots


def build_structure(bars: Sequence[BarLike]) -> Structure:
    ordered = list(bars)
    if any(not _valid(bar) for bar in ordered) or any(b.end_ns <= a.end_ns for a, b in zip(ordered, ordered[1:])):
        return Structure("MALFORMED_BARS", len(ordered), None, None, None, (), ())
    latest = ordered[-1].end_ns if ordered else None
    if len(ordered) < MIN_BARS:
        return Structure("INSUFFICIENT_BARS", len(ordered), latest, None, None, (), ())
    atr, basis = reference_volatility(ordered)
    if atr is None or atr <= 0:
        return Structure("INSUFFICIENT_BARS", len(ordered), latest, atr, None, (), (), basis)
    tolerance = max(TOLERANCE_ATR * atr, 2 * tick_size(ordered[-1].close))
    pivots = [pivot for pivot in confirmed_pivots(ordered) if pivot.rejection >= MIN_REJECTION_ATR * atr]
    volumes = [bar.volume for bar in ordered if bar.volume is not None and bar.volume > 0]
    median_volume = statistics.median(volumes) if volumes else None
    clusters: list[list[Pivot]] = []
    for pivot in sorted(pivots, key=lambda item: (item.price, item.index, item.kind)):
        if (clusters and pivot.price - clusters[-1][-1].price <= tolerance
                and pivot.price - clusters[-1][0].price <= CLUSTER_WIDTH_TOLERANCES * tolerance):
            clusters[-1].append(pivot)
        else:
            clusters.append([pivot])
    # Symmetric padding to one tolerance, clipped at the midpoint to a neighbour
    # so zones never overlap.
    bounds: list[list[float]] = []
    for members in clusters:
        low, high = members[0].price, members[-1].price
        pad = max(0.0, (tolerance - (high - low)) / 2)
        bounds.append([low - pad, high + pad])
    for index in range(1, len(clusters)):
        if bounds[index - 1][1] > bounds[index][0]:
            middle = (clusters[index - 1][-1].price + clusters[index][0].price) / 2
            bounds[index - 1][1] = bounds[index][0] = middle
    last_index = len(ordered) - 1
    zones: list[Zone] = []
    for members, (lower, upper) in zip(clusters, bounds):
        low, high = members[0].price, members[-1].price
        newest = max(members, key=lambda p: p.index)
        touches = len(members)
        age = last_index - newest.index
        rejection = sum(p.rejection for p in members) / touches / atr
        pivot_volumes = [p.volume for p in members if p.volume is not None]
        volume_score = (10 * min(sum(pivot_volumes) / len(pivot_volumes) / median_volume, 2) / 2
                        if pivot_volumes and median_volume else 0.0)
        strength = (min(touches, 4) / 4 * 40 + 30 * 0.5 ** (age / RECENCY_HALF_LIFE_BARS)
                    + 20 * min(rejection, 2) / 2 + volume_score)
        zones.append(Zone(round(lower, 6), round(upper, 6), round((low + high) / 2, 6), touches,
                          int(round(min(100.0, strength))), ordered[newest.index].end_ns,
                          tuple(sorted({p.kind for p in members}))))
    strongest = sorted(zones, key=lambda z: (-z.strength, -z.last_touch_end_ns, z.center))[:MAX_ZONES]
    return Structure(None, len(ordered), latest, atr, tolerance, tuple(pivots),
                     tuple(sorted(strongest, key=lambda z: z.center)), basis)


def classify(structure: Structure, price: float | None) -> dict[str, Any]:
    """Nearest meaningful support/resistance relative to ``price`` (pure, cheap)."""

    if structure.reason is not None:
        return {"state": "UNAVAILABLE", "reason": structure.reason, "support": None, "resistance": None,
                "testing": None, "reasons": [structure.reason]}
    if price is None or not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
        return {"state": "UNAVAILABLE", "reason": "INVALID_PRICE", "support": None, "resistance": None,
                "testing": None, "reasons": ["INVALID_PRICE"]}
    meaningful = [z for z in structure.zones if z.strength >= MIN_STRENGTH]
    below = [z for z in meaningful if z.upper < price]
    above = [z for z in meaningful if z.lower > price]
    testing = [z for z in meaningful if z.lower <= price <= z.upper]
    support = max(below, key=lambda z: (z.upper, z.strength), default=None)
    resistance = min(above, key=lambda z: (z.lower, -z.strength), default=None)
    reasons = ([] if support else ["NO_SUPPORT_ZONE"]) + ([] if resistance else ["NO_RESISTANCE_ZONE"])

    def side(zone: Zone | None, distance: float | None) -> dict[str, Any] | None:
        return None if zone is None else {**zone.to_dict(), "distance_pct": round(distance or 0.0, 4)}

    return {
        "state": "AVAILABLE" if support or resistance or testing else "NO_ZONES",
        "reason": None,
        "support": side(support, (price - support.upper) / price * 100 if support else None),
        "resistance": side(resistance, (resistance.lower - price) / price * 100 if resistance else None),
        "testing": side(max(testing, key=lambda z: z.strength), 0.0) if testing else None,
        "reasons": reasons,
    }


__all__ = [
    "ATR_PERIOD", "METHOD", "MIN_BARS", "MIN_REJECTION_ATR", "MIN_STRENGTH", "PIVOT_SPAN", "Pivot", "Structure", "Zone",
    "build_structure", "classify", "confirmed_pivots", "reference_volatility", "tick_size", "wilder_atr",
]
