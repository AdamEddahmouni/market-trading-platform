"""Herd urgency and decision-quadrant coordinates for Path A and Path B.

Pipeline role
-------------
Turns raw social level, relative volume, DTE, and volume/OI spike into:
  - ``herd_stage`` labels (quiet → coiled → whispers → herd_forming → herd_here),
  - ``y_urgency`` (0–100) and ``x_bias`` (-1..+1) for quadrant plotting,
  - ``build_candidate`` rows consumed by ``decision_engine`` and dashboards.

Path A weights rel vol + social; Path B weights DTE + vol/OI spike; when both
signals exist, urgency takes the max of the two paths.

Merge notes for stocks/futures
------------------------------
  - **Fully reusable** — momentum/flow urgency framing applies to futures OI/volume
    spikes and equity social signals alike.
  - **Options-specific inputs:** ``dte``, ``volume_oi_spike`` (Path B expiry screener).
  - No state files; pure functions.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _norm(value: float, low: float, high: float) -> float:
    """Normalize value into 0..1 between low and high."""
    if high <= low:
        return 0.0
    return _clamp((value - low) / (high - low), 0.0, 1.0)


def social_score_from_level(social_signal_level: str, keyword_hits: int = 0) -> int:
    """Map social level to a numeric herd score."""
    level = str(social_signal_level or "IGNORE").upper().strip()
    if level == "HIGH_ALERT":
        return max(3, int(keyword_hits) or 3)
    if level == "WATCH":
        return max(1, min(2, int(keyword_hits) or 1))
    return 0


def classify_herd_stage(
    relative_volume: float | None,
    social_score: int,
    percent_change: float | None = None,
) -> str:
    """Label herd stage for dashboard and trade log."""
    rel = float(relative_volume) if relative_volume is not None else 0.0
    pct = abs(float(percent_change)) if percent_change is not None else 0.0
    if rel >= 5.0 and pct >= 5.0:
        return "herd_here"
    if social_score >= 3:
        return "herd_forming"
    if 1 <= social_score <= 2:
        return "whispers"
    if rel >= 1.5:
        return "coiled"
    return "quiet"


def compute_herd_urgency(
    relative_volume: float | None = None,
    social_score: int = 0,
    dte: int | None = None,
    volume_oi_spike: float | None = None,
) -> float:
    """
    Compute herd/positioning urgency on 0–100 scale.

    Path A uses rel vol + social; Path B uses DTE + volume/OI spike.
    When both present, take the max.
    """
    path_a = 0.0
    if relative_volume is not None or social_score > 0:
        rel_part = _norm(float(relative_volume or 0.0), 1.5, 10.0)
        social_part = _norm(float(social_score), 0.0, 5.0)
        path_a = 100.0 * (0.4 * rel_part + 0.6 * social_part)

    path_b = 0.0
    if dte is not None and dte >= 0:
        spike_part = _norm(float(volume_oi_spike or 0.0), 1.0, 5.0)
        if int(dte) == 0:
            # Same-day expiry: floor so Path B alone clears expiry_buy_min_urgency (45).
            dte_part = 1.0
            path_b = max(55.0, 100.0 * (0.55 * dte_part + 0.45 * spike_part))
        else:
            # Sooner expiry => higher urgency (DTE 1 ~ 1.0, DTE 14 ~ 0.0).
            dte_part = _norm(1.0 / float(dte), 1.0 / 14.0, 1.0)
            path_b = 100.0 * (0.5 * dte_part + 0.5 * spike_part)
    elif volume_oi_spike is not None:
        path_b = 100.0 * _norm(float(volume_oi_spike), 1.0, 5.0)

    return round(_clamp(max(path_a, path_b)), 2)


def compute_directional_bias(
    news_score: float | None = None,
    options_score: float | None = None,
) -> float:
    """
    Directional bias on -1..+1 scale.

    News score is already -1..+1. Options score 0–100 maps with 50 as neutral.
    """
    parts: list[float] = []
    weights: list[float] = []
    if news_score is not None:
        parts.append(_clamp(float(news_score), -1.0, 1.0))
        weights.append(0.4)
    if options_score is not None:
        parts.append(_clamp((float(options_score) - 50.0) / 50.0, -1.0, 1.0))
        weights.append(0.6)
    if not parts:
        return 0.0
    total_w = sum(weights)
    return round(sum(p * w for p, w in zip(parts, weights)) / total_w, 4)


def quadrant_label(x_bias: float, y_urgency: float, urgency_mid: float = 50.0) -> str:
    """Map bias/urgency to Q1–Q4 labels."""
    bullish = x_bias >= 0
    urgent = y_urgency >= urgency_mid
    if bullish and urgent:
        return "Q1"
    if not bullish and not urgent:
        return "Q2"
    if not bullish and urgent:
        return "Q3"
    return "Q4"


def decision_hint_from_quadrant(quadrant: str) -> str:
    """Suggested action label from quadrant."""
    return {
        "Q1": "BUY",
        "Q2": "WAIT",
        "Q3": "SELL",
        "Q4": "WAIT",
    }.get(quadrant, "WAIT")


def build_candidate(
    ticker: str,
    source: str = "news",
    relative_volume: float | None = None,
    social_signal_level: str = "IGNORE",
    social_score: int | None = None,
    percent_change: float | None = None,
    news_score: float | None = None,
    options_score: float | None = None,
    dte: int | None = None,
    volume_oi_spike: float | None = None,
    total_oi: float | None = None,
    decision: str | None = None,
) -> Dict[str, Any]:
    """Build one quadrant candidate row."""
    social = social_score if social_score is not None else social_score_from_level(social_signal_level)
    y_urgency = compute_herd_urgency(
        relative_volume=relative_volume,
        social_score=social,
        dte=dte,
        volume_oi_spike=volume_oi_spike,
    )
    x_bias = compute_directional_bias(news_score=news_score, options_score=options_score)
    quadrant = quadrant_label(x_bias, y_urgency)
    herd_stage = classify_herd_stage(relative_volume, social, percent_change)
    return {
        "ticker": ticker.upper().strip(),
        "source": source,
        "x_bias": x_bias,
        "y_urgency": y_urgency,
        "herd_stage": herd_stage,
        "quadrant": quadrant,
        "rel_volume": relative_volume,
        "social_score": social,
        "dte": dte,
        "total_oi": total_oi,
        "decision_hint": decision or decision_hint_from_quadrant(quadrant),
    }


def merge_sources(existing: Optional[str], new_source: str) -> str:
    """Merge path tags into news | expiry | both."""
    old = str(existing or "").lower().strip()
    new = str(new_source or "").lower().strip()
    if not old:
        return new or "news"
    if not new or old == new:
        return old
    if {old, new} == {"news", "expiry"} or "both" in {old, new}:
        return "both"
    return new
