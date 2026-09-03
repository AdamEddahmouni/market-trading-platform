"""Time-of-day decay curve for 0DTE entries.

Purpose
-------
Model late-session theta burn and raise the confidence bar after a configurable
ET cutoff for new 0DTE entries.

Features / API role
-------------------
``compute_tod_features`` → ``tod_confidence_multiplier``, ``tod_theta_remaining_frac``,
``tod_is_late``. ``theta_adjusted_breakeven_move_pct`` estimates required underlying
move after expected theta loss.

How ``news_momentum_agent`` consumes it
---------------------------------------
``features`` on scored items; ``odte_decision`` / paper trader may read TOD keys
for sizing and breakeven hints without importing this module directly.

Options-specific vs reusable
----------------------------
Options-specific 0DTE session curve. Reusable sqrt-time remaining fraction helper.

Theta burns nonlinearly into the close. After a configurable Eastern cutoff
(default 13:30 ET) we raise the confidence bar for new entries and estimate
remaining intraday theta cost as a fraction of premium.
"""

from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")


def _parse_hhmm(value: str, default: time) -> time:
    text = str(value or "").strip()
    try:
        parts = text.split(":")
        return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    except (TypeError, ValueError, IndexError):
        return default


def _as_of_et(as_of: Optional[str] = None) -> datetime:
    if as_of:
        try:
            dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(ET)
        except ValueError:
            pass
    return datetime.now(timezone.utc).astimezone(ET)


def estimate_remaining_theta_fraction(now_et: datetime, eod_flatten: time) -> float:
    """
    Crude remaining extrinsic fraction for 0DTE (1.0 at open → ~0 near flatten).

    Uses a square-root-of-time style burn so late day decays faster than linear.
    """
    open_t = time(9, 30)
    open_min = open_t.hour * 60 + open_t.minute
    eod_min = eod_flatten.hour * 60 + eod_flatten.minute
    now_min = now_et.hour * 60 + now_et.minute
    session = max(1, eod_min - open_min)
    elapsed = max(0, min(session, now_min - open_min))
    remaining_frac_time = max(0.0, 1.0 - (elapsed / session))
    # sqrt-time: remaining extrinsic ≈ sqrt(remaining time fraction)
    return remaining_frac_time ** 0.5


def compute_tod_features(settings: Dict[str, Any], as_of: Optional[str] = None) -> Dict[str, float]:
    """
    Keys:
      - tod_confidence_multiplier (>=1 after cutoff means require *higher* bar)
      - tod_theta_remaining_frac  (estimated remaining extrinsic, 0..1)
      - tod_is_late (1.0 after raise_bar_after_et)
      - tod_available
    """
    odte = settings.get("odte_signals", {}).get("time_of_day", {})
    if not bool(odte.get("enabled", True)):
        return {
            "tod_confidence_multiplier": 1.0,
            "tod_theta_remaining_frac": 1.0,
            "tod_is_late": 0.0,
            "tod_available": 0.0,
        }

    now_et = _as_of_et(as_of)
    cutoff = _parse_hhmm(str(odte.get("raise_bar_after_et", "13:30")), time(13, 30))
    late_mult = float(odte.get("late_confidence_mult", 1.25))
    eod = _parse_hhmm(
        str(
            odte.get("eod_flatten_et")
            or settings.get("trading", {}).get("options_exits", {}).get("eod_flatten_et", "15:45")
        ),
        time(15, 45),
    )

    is_late = (now_et.hour, now_et.minute) >= (cutoff.hour, cutoff.minute)
    # Weekend / outside RTH: still mark available but do not inflate late bar
    # beyond the configured multiplier when clearly after cutoff on a weekday.
    theta_left = estimate_remaining_theta_fraction(now_et, eod)
    mult = late_mult if is_late else 1.0

    return {
        "tod_confidence_multiplier": float(mult),
        "tod_theta_remaining_frac": float(theta_left),
        "tod_is_late": 1.0 if is_late else 0.0,
        "tod_available": 1.0,
    }


def theta_adjusted_breakeven_move_pct(
    premium: float,
    spot: float,
    theta_remaining_frac: float,
    *,
    delta_approx: float = 0.50,
) -> float:
    """
    Rough underlying % move needed to recover premium after expected theta burn.

    breakeven_move ≈ (premium * theta_burn) / (spot * |delta|)
    where theta_burn = 1 - remaining_frac (extrinsic we expect to lose).
    """
    if spot <= 0 or premium <= 0 or abs(delta_approx) < 1e-6:
        return 0.0
    burn = max(0.0, 1.0 - float(theta_remaining_frac))
    # Option premium is per-share; underlying move needed:
    needed = (premium * burn) / (spot * abs(delta_approx))
    return float(needed * 100.0)
