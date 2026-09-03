"""Exponential time-decay for Claude news sentiment by headline age.

Pipeline role
-------------
Applied inside ``decision_engine`` before lean/probability math. A headline
scored 90 minutes ago should weigh less than one from 5 minutes ago when
deciding intraday (especially 0DTE) entries.

``apply_news_decay`` reads ``settings.news_decay`` (enabled, half_life_minutes)
and returns raw vs decayed score plus metadata for logging.

Merge notes for stocks/futures
------------------------------
  - **Fully reusable** — any news-driven system with time-sensitive alpha.
  - No state files; pure function of ``published_at`` and configured half-life.
  - For slower horizons (swing/futures overnight), increase half-life or disable.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
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


def age_minutes(published_at: Any, now: Optional[datetime] = None) -> float:
    """Minutes since ``published_at`` (0 if unknown / future)."""
    ts = _parse_ts(published_at)
    if ts is None:
        return 0.0
    now_dt = now or datetime.now(timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    mins = (now_dt - ts).total_seconds() / 60.0
    return float(max(0.0, mins))


def decay_multiplier(
    age_min: float,
    *,
    half_life_minutes: float = 45.0,
) -> float:
    """
    Return multiplier in (0, 1] using exponential half-life decay.

    score_effective = raw_score * decay_multiplier(age)
    """
    hl = max(1e-6, float(half_life_minutes))
    # m = 0.5 ** (age / half_life)
    return float(0.5 ** (float(age_min) / hl))


def apply_news_decay(
    raw_score: float,
    published_at: Any = None,
    settings: Optional[Dict[str, Any]] = None,
    *,
    now: Optional[datetime] = None,
) -> Dict[str, float]:
    """
    Apply configured news decay.

    Returns dict with raw_score, decayed_score, age_minutes, decay_multiplier.
    """
    cfg = (settings or {}).get("news_decay", {})
    enabled = bool(cfg.get("enabled", True))
    half_life = float(cfg.get("half_life_minutes", 45.0))
    age = age_minutes(published_at, now=now)
    if not enabled:
        return {
            "raw_score": float(raw_score),
            "decayed_score": float(raw_score),
            "age_minutes": float(age),
            "decay_multiplier": 1.0,
        }
    mult = decay_multiplier(age, half_life_minutes=half_life)
    return {
        "raw_score": float(raw_score),
        "decayed_score": float(raw_score) * mult,
        "age_minutes": float(age),
        "decay_multiplier": float(mult),
    }
