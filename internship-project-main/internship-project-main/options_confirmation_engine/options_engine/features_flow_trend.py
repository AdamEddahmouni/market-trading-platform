"""Put/call volume *trend* over recent snapshots (not just a point-in-time PCR).

Purpose
-------
Detect accelerating call vs put flow using slope of ``call_volume_share`` over
saved snapshot history.

Features / API role
-------------------
``compute_flow_trend_features`` → ``flow_trend_score``, ``call_share_slope_per_min``,
``flow_trend_available``.

How ``news_momentum_agent`` consumes it
---------------------------------------
Part of live ``features`` when snapshot history exists under ``engine_path/state``.
Sparse history → ``flow_trend_available=0``; scorer falls back to snapshot PCR weights.

Options-specific vs reusable
----------------------------
Options-specific (PCR share slope). Reusable time-series slope helper over JSON history.

0DTE flow that is accelerating in one direction is more informative than a
single snapshot ratio. We compute the slope of call_volume_share across the
local feature history (and the current snapshot).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _extract_share_points(
    history: Sequence[Dict[str, Any]],
    current_share: float,
    current_as_of: str,
    lookback_minutes: float,
) -> List[Tuple[float, float]]:
    """Return (minutes_ago_negative_x, call_volume_share) points newest-last."""
    now = _parse_ts(current_as_of) or datetime.now(timezone.utc)
    points: List[Tuple[float, float]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        cache = item.get("feature_cache") or {}
        if not isinstance(cache, dict):
            continue
        try:
            share = float(cache.get("call_volume_share"))
        except (TypeError, ValueError):
            continue
        ts = _parse_ts(item.get("as_of") or item.get("timestamp"))
        if ts is None:
            continue
        age_min = (now - ts).total_seconds() / 60.0
        if age_min < 0:
            age_min = 0.0
        if age_min > lookback_minutes:
            continue
        points.append((-age_min, share))  # x increases toward "now"
    points.append((0.0, float(current_share)))
    points.sort(key=lambda p: p[0])
    return points


def _linear_slope(points: Sequence[Tuple[float, float]]) -> Optional[float]:
    """Ordinary least-squares slope of y vs x; None if undefined."""
    n = len(points)
    if n < 2:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x <= 1e-12:
        return 0.0
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    return cov / var_x


def compute_flow_trend_features(
    *,
    call_volume_share: float,
    put_call_volume_ratio: float,
    as_of: str,
    history: List[Dict[str, Any]],
    settings: Dict[str, Any],
) -> Dict[str, float]:
    """
    Keys:
      - call_share_slope_per_min: change in call volume share per minute
      - flow_trend_score: bullish-normalized [0,1] from the slope
      - flow_trend_available
    """
    odte = settings.get("odte_signals", {}).get("flow_trend", {})
    if not bool(odte.get("enabled", True)):
        return {
            "call_share_slope_per_min": 0.0,
            "flow_trend_score": 0.5,
            "flow_trend_available": 0.0,
        }

    lookback = float(odte.get("lookback_minutes", 30))
    # Slope that maps to a full-strength signal (share points per minute).
    # 0.002 / min ≈ +6 pts of call share over 30 minutes.
    gain = float(odte.get("slope_gain", 200.0))

    points = _extract_share_points(history, call_volume_share, as_of, lookback)
    slope = _linear_slope(points)
    if slope is None:
        # Fall back: treat current PCR lean as a weak trend proxy.
        # Lower PCR → slightly bullish score, but mark unavailable for weighting
        # if we truly have no history (scorer can still use snapshot PCR).
        return {
            "call_share_slope_per_min": 0.0,
            "flow_trend_score": 0.5,
            "flow_trend_available": 0.0,
            "put_call_volume_ratio_snapshot": float(put_call_volume_ratio),
        }

    # Positive slope (rising call share) → bullish.
    score = max(0.0, min(1.0, 0.5 + slope * gain))
    return {
        "call_share_slope_per_min": float(slope),
        "flow_trend_score": float(score),
        "flow_trend_available": 1.0,
        "put_call_volume_ratio_snapshot": float(put_call_volume_ratio),
    }
