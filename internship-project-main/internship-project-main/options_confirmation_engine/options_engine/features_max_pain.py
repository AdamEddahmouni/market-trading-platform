"""Max-pain and open-interest concentration features for 0DTE.

Purpose
-------
Locate max-pain strike and nearest OI wall relative to spot for pin/magnet context.

Features / API role
-------------------
``compute_max_pain_features``, ``compute_max_pain_strike`` (public for tests).

How ``news_momentum_agent`` consumes it
---------------------------------------
Included in ``features`` dict on live scores; optional weight via
``settings.odte_signals.max_pain`` in engine settings.

Options-specific vs reusable
----------------------------
Options-specific (pain minimization over OI). Reusable OI-by-strike aggregation
pattern for research dashboards.

Max pain is the underlying expiry price that minimizes the aggregate dollar
value of outstanding calls and puts (maximizing "pain" for option holders).
On 0DTE, price often gravitates toward large OI walls into the close.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

from options_engine.data_models import ContractRow, Snapshot


def _unique_strikes(contracts: Sequence[ContractRow]) -> List[float]:
    return sorted({float(row.strike) for row in contracts})


def compute_max_pain_strike(contracts: Sequence[ContractRow]) -> Tuple[float, float]:
    """
    Return (max_pain_strike, total_pain_at_that_strike).

    Pain at candidate expiry price S:
        sum_calls OI * max(S - K, 0) + sum_puts OI * max(K - S, 0)
    """
    strikes = _unique_strikes(contracts)
    if not strikes:
        return 0.0, 0.0

    calls = [(float(r.strike), float(r.open_interest)) for r in contracts if r.side == "call"]
    puts = [(float(r.strike), float(r.open_interest)) for r in contracts if r.side == "put"]

    best_strike = strikes[0]
    best_pain = float("inf")
    for s in strikes:
        pain = 0.0
        for k, oi in calls:
            if s > k:
                pain += oi * (s - k)
        for k, oi in puts:
            if k > s:
                pain += oi * (k - s)
        if pain < best_pain:
            best_pain = pain
            best_strike = s
    return float(best_strike), float(best_pain if best_pain < float("inf") else 0.0)


def _oi_wall_near_spot(
    contracts: Sequence[ContractRow],
    spot: float,
    band_pct: float,
) -> Tuple[float, float, float]:
    """Return (wall_strike, wall_oi, distance_pct_from_spot) for the densest OI in band."""
    if spot <= 0:
        return 0.0, 0.0, 0.0
    lower = spot * (1.0 - band_pct)
    upper = spot * (1.0 + band_pct)
    by_strike: Dict[float, float] = {}
    for row in contracts:
        k = float(row.strike)
        if lower <= k <= upper:
            by_strike[k] = by_strike.get(k, 0.0) + float(row.open_interest)
    if not by_strike:
        # Fall back to global max OI strike.
        for row in contracts:
            k = float(row.strike)
            by_strike[k] = by_strike.get(k, 0.0) + float(row.open_interest)
    if not by_strike:
        return 0.0, 0.0, 0.0
    wall_strike, wall_oi = max(by_strike.items(), key=lambda item: item[1])
    dist_pct = ((wall_strike - spot) / spot) * 100.0
    return float(wall_strike), float(wall_oi), float(dist_pct)


def compute_max_pain_features(snapshot: Snapshot, settings: Dict[str, Any]) -> Dict[str, float]:
    """
    Compute max-pain location and OI wall metrics.

    Keys:
      - max_pain_strike
      - max_pain_distance_pct  (positive => pain above spot)
      - oi_wall_strike
      - oi_wall_distance_pct
      - oi_wall_oi
      - max_pain_available
    """
    odte = settings.get("odte_signals", {}).get("max_pain", {})
    if not bool(odte.get("enabled", True)):
        return {
            "max_pain_strike": 0.0,
            "max_pain_distance_pct": 0.0,
            "oi_wall_strike": 0.0,
            "oi_wall_distance_pct": 0.0,
            "oi_wall_oi": 0.0,
            "max_pain_available": 0.0,
        }

    contracts: List[ContractRow] = list(snapshot.contracts)
    spot = float(snapshot.spot_price or 0.0)
    total_oi = sum(float(r.open_interest) for r in contracts)
    if spot <= 0 or total_oi <= 0:
        return {
            "max_pain_strike": 0.0,
            "max_pain_distance_pct": 0.0,
            "oi_wall_strike": 0.0,
            "oi_wall_distance_pct": 0.0,
            "oi_wall_oi": 0.0,
            "max_pain_available": 0.0,
        }

    band = float(odte.get("near_spot_band_pct", settings.get("features", {}).get("atm_strike_band_pct", 0.05)))
    max_pain, _pain = compute_max_pain_strike(contracts)
    wall_strike, wall_oi, wall_dist = _oi_wall_near_spot(contracts, spot, band)
    dist_pct = ((max_pain - spot) / spot) * 100.0 if spot > 0 else 0.0

    return {
        "max_pain_strike": float(max_pain),
        "max_pain_distance_pct": float(dist_pct),
        "oi_wall_strike": float(wall_strike),
        "oi_wall_distance_pct": float(wall_dist),
        "oi_wall_oi": float(wall_oi),
        "max_pain_available": 1.0,
    }
