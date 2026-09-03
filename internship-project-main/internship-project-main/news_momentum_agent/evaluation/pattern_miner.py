"""Disciplined pattern miner: hard N floor + chronological out-of-sample validation.

Purpose
-------
Mine categorical buckets on the SPY/QQQ research panel; require minimum N and
chronological OOS validation before surfacing patterns to proposals.

Features / API role
-------------------
``run_pattern_pipeline`` → discovery patterns, survivors, failed replications.
``annotate_buckets`` adds banded features for mining.

How this uses ``options_confirmation_engine``
-----------------------------------------------
Reads ``options_score``, ``options_bias``, and liquidity bands from panel rows
produced by replay (which imports ``compute_features`` / ``score_options``).

Options-specific vs reusable
----------------------------
Options bands are domain features; Wilson CI + chronological split are reusable
research utilities. **Never rewrites live thresholds.**

Research only — never rewrites live thresholds.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from evaluation.spy_qqq_replay import PATH_A_EXCLUSION_NOTE

DEFAULT_MIN_N = 30
DISCOVERY_FRAC = 0.70

CATEGORICAL_FEATURES = (
    "would_be_side",
    "options_bias",
    "lean",
    "decision",
    "confidence_band",
    "options_band",
    "lean_band",
    "tod_bucket",
    "n_dir_band",
    # Part 2 — scheduled catalysts / VIX regime (research panel enrichment)
    "is_scheduled_catalyst_day",
    "hours_until_catalyst_band",
    "hours_since_catalyst_band",
    "vix_level_band",
    "vix_change_band",
)
# Excluded from mining: signal_source / source_kind (nearly constant in this panel → tautologies).

MIN_ABS_LIFT = 0.08  # |lift-1| must clear this in discovery
MAX_BUCKET_FRAC = 0.90  # skip buckets that cover almost the whole sample
# Default paper TP/SL used when pnl_pct missing (matches settings take_profit/stop_loss).
DEFAULT_TP_PCT = 0.40
DEFAULT_SL_PCT = 0.30



def _f(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _session_date(row: Dict[str, Any]) -> str:
    for key in ("session_date", "timestamp", "rejected_at"):
        text = str(row.get(key) or "")
        if len(text) >= 10 and text[4] == "-":
            return text[:10]
    return ""


def annotate_buckets(row: Dict[str, Any]) -> Dict[str, Any]:
    """Add categorical bands (confidence, options, lean, TOD, VIX) for mining."""
    copy = dict(row)
    conf = _f(copy.get("confidence_pct"))
    if conf is None:
        copy["confidence_band"] = "unknown"
    elif conf >= 70:
        copy["confidence_band"] = "70+"
    elif conf >= 60:
        copy["confidence_band"] = "60-69"
    elif conf >= 45:
        copy["confidence_band"] = "45-59"
    else:
        copy["confidence_band"] = "0-44"

    score = _f(copy.get("options_score"))
    if score is None:
        copy["options_band"] = "unknown"
    elif score >= 70:
        copy["options_band"] = "70+"
    elif score >= 55:
        copy["options_band"] = "55-69"
    elif score <= 30:
        copy["options_band"] = "0-30"
    elif score <= 45:
        copy["options_band"] = "31-45"
    else:
        copy["options_band"] = "46-54"

    lean = _f(copy.get("lean_pct"))
    if lean is None:
        copy["lean_band"] = "unknown"
    elif lean >= 70:
        copy["lean_band"] = "70+"
    elif lean >= 60:
        copy["lean_band"] = "60-69"
    else:
        copy["lean_band"] = "0-59"

    n_dir = _f(copy.get("n_dir"))
    if n_dir is None:
        copy["n_dir_band"] = "unknown"
    elif n_dir >= 3:
        copy["n_dir_band"] = "3+"
    elif n_dir >= 2:
        copy["n_dir_band"] = "2"
    else:
        copy["n_dir_band"] = "0-1"

    # EOD snapshot pipelines usually lack intraday TOD — still record hour if present.
    ts = str(copy.get("timestamp") or "")
    tod = "eod_or_unknown"
    try:
        if "T" in ts:
            hour = int(ts.split("T", 1)[1][:2])
            # Rough ET if already offset; otherwise label utc buckets explicitly.
            if hour < 14:
                tod = "morning"
            elif hour < 18:
                tod = "midday"
            else:
                tod = "afternoon_eod"
    except Exception:
        tod = "eod_or_unknown"
    copy["tod_bucket"] = tod
    copy["session_date"] = _session_date(copy)

    # Catalyst / VIX bands (populated by evaluation.macro_calendar + vix_history enrichment).
    cat = copy.get("is_scheduled_catalyst_day")
    if isinstance(cat, bool):
        copy["is_scheduled_catalyst_day"] = "yes" if cat else "no"
    elif str(cat).lower() in {"1", "true", "yes"}:
        copy["is_scheduled_catalyst_day"] = "yes"
    elif str(cat).lower() in {"0", "false", "no"}:
        copy["is_scheduled_catalyst_day"] = "no"
    else:
        copy["is_scheduled_catalyst_day"] = "unknown"

    hu = _f(copy.get("hours_until_next_catalyst"))
    if hu is None:
        copy["hours_until_catalyst_band"] = "unknown"
    elif hu <= 24:
        copy["hours_until_catalyst_band"] = "0-24h"
    elif hu <= 72:
        copy["hours_until_catalyst_band"] = "24-72h"
    else:
        copy["hours_until_catalyst_band"] = "72h+"

    hs = _f(copy.get("hours_since_last_catalyst"))
    if hs is None:
        copy["hours_since_catalyst_band"] = "unknown"
    elif hs <= 24:
        copy["hours_since_catalyst_band"] = "0-24h"
    elif hs <= 72:
        copy["hours_since_catalyst_band"] = "24-72h"
    else:
        copy["hours_since_catalyst_band"] = "72h+"

    vix = _f(copy.get("vix_level"))
    if vix is None:
        copy["vix_level_band"] = "unknown"
    elif vix < 15:
        copy["vix_level_band"] = "lt15"
    elif vix < 20:
        copy["vix_level_band"] = "15-20"
    elif vix < 25:
        copy["vix_level_band"] = "20-25"
    else:
        copy["vix_level_band"] = "25+"

    vix_chg = _f(copy.get("vix_change_intraday"))
    if vix_chg is None:
        copy["vix_change_band"] = "unknown"
    elif vix_chg <= -5:
        copy["vix_change_band"] = "down_ge5"
    elif vix_chg < 5:
        copy["vix_change_band"] = "flat_pm5"
    else:
        copy["vix_change_band"] = "up_ge5"

    return copy


def row_r_multiple(
    row: Dict[str, Any],
    *,
    sl_pct: float = DEFAULT_SL_PCT,
    tp_pct: float = DEFAULT_TP_PCT,
) -> Optional[float]:
    """R-multiple vs stop distance. Prefer realized pnl_pct; else win/loss stubs."""
    risk = float(sl_pct) if sl_pct else 0.0
    if risk <= 0:
        return None
    pnl = _f(row.get("pnl_pct"))
    if pnl is not None:
        return pnl / risk
    outcome = str(row.get("outcome") or "").lower()
    if outcome == "win":
        return float(tp_pct) / risk
    if outcome == "loss":
        return -1.0
    return None


def wilson_ci(wins: int, n: int, z: float = 1.96) -> Tuple[Optional[float], Optional[float]]:
    """Wilson score interval for binomial win rate."""
    if n <= 0:
        return None, None
    p = wins / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, center - half), min(1.0, center + half)


def _win_loss_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        outcome = str(row.get("outcome") or "").lower()
        if outcome in {"win", "loss"}:
            out.append(row)
    return out


def mine_buckets(
    rows: Sequence[Dict[str, Any]],
    *,
    min_n: int = DEFAULT_MIN_N,
    require_lift: bool = True,
) -> List[Dict[str, Any]]:
    """Find categorical buckets with win-rate lift vs base (N floor enforced)."""
    annotated = [annotate_buckets(r) for r in _win_loss_rows(rows)]
    base_n = len(annotated)
    if base_n == 0:
        return []
    base_wins = sum(1 for r in annotated if r["outcome"] == "win")
    base_rate = base_wins / base_n
    patterns: List[Dict[str, Any]] = []

    for feature in CATEGORICAL_FEATURES:
        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in annotated:
            buckets[str(row.get(feature) if row.get(feature) not in (None, "") else "unknown")].append(row)
        for value, group in buckets.items():
            n = len(group)
            if n < min_n:
                continue  # hard exclude — not shown with caveat
            if n >= MAX_BUCKET_FRAC * base_n:
                continue  # tautology: bucket ≈ entire sample
            wins = sum(1 for r in group if r["outcome"] == "win")
            losses = n - wins
            rate = wins / n
            lo, hi = wilson_ci(wins, n)
            se = math.sqrt(rate * (1 - rate) / n) if n else None
            lift = (rate / base_rate) if base_rate > 0 else None
            if require_lift and (lift is None or abs(lift - 1.0) < MIN_ABS_LIFT):
                continue  # no meaningful edge vs base rate
            r_vals = [row_r_multiple(r) for r in group]
            r_vals = [x for x in r_vals if x is not None]
            avg_r = (sum(r_vals) / len(r_vals)) if r_vals else None
            expectancy_pnl = None
            pnls = [_f(r.get("pnl_pct")) for r in group]
            pnls = [p for p in pnls if p is not None]
            if pnls:
                expectancy_pnl = sum(pnls) / len(pnls)
            elif avg_r is not None:
                expectancy_pnl = avg_r * DEFAULT_SL_PCT
            patterns.append(
                {
                    "feature": feature,
                    "value": value,
                    "n": n,
                    "wins": wins,
                    "losses": losses,
                    "win_rate": round(rate, 4),
                    "win_rate_se": round(se, 4) if se is not None else None,
                    "wilson_lo": round(lo, 4) if lo is not None else None,
                    "wilson_hi": round(hi, 4) if hi is not None else None,
                    "base_win_rate": round(base_rate, 4),
                    "base_n": base_n,
                    "lift": round(lift, 4) if lift is not None else None,
                    "avg_r_multiple": round(avg_r, 4) if avg_r is not None else None,
                    "expectancy_pnl_pct": round(expectancy_pnl, 4) if expectancy_pnl is not None else None,
                    "kind": "favorable" if rate >= base_rate else "protective",
                    "summary": (
                        f"when {feature}={value}: win_rate={rate:.1%} (N={n}, "
                        f"CI=[{lo:.1%},{hi:.1%}] vs base {base_rate:.1%} N={base_n}; "
                        f"avg_R={avg_r:.2f}, E[pnl]={expectancy_pnl:.1%})"
                        if avg_r is not None and expectancy_pnl is not None
                        else (
                            f"when {feature}={value}: win_rate={rate:.1%} (N={n}, "
                            f"CI=[{lo:.1%},{hi:.1%}] vs base {base_rate:.1%} N={base_n})"
                        )
                    ),
                }
            )
    patterns.sort(key=lambda p: (abs(float(p.get("lift") or 1) - 1), p["n"]), reverse=True)
    return patterns


def chronological_split(
    rows: Sequence[Dict[str, Any]],
    *,
    discovery_frac: float = DISCOVERY_FRAC,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str], List[str]]:
    """Split panel rows by session date into discovery vs validation sets."""
    annotated = [annotate_buckets(r) for r in rows]
    days = sorted({r["session_date"] for r in annotated if r.get("session_date")})
    if not days:
        return [], [], [], []
    cut = max(1, int(len(days) * discovery_frac))
    if cut >= len(days) and len(days) > 1:
        cut = len(days) - 1
    discovery_days = set(days[:cut])
    validation_days = set(days[cut:])
    discovery = [r for r in annotated if r.get("session_date") in discovery_days]
    validation = [r for r in annotated if r.get("session_date") in validation_days]
    return discovery, validation, sorted(discovery_days), sorted(validation_days)


def validate_patterns(
    discovery_patterns: Sequence[Dict[str, Any]],
    validation_rows: Sequence[Dict[str, Any]],
    *,
    min_n: int = DEFAULT_MIN_N,
    min_lift_persist: float = 0.10,
) -> Dict[str, Any]:
    """Keep patterns whose direction/magnitude roughly hold OOS with N floor.

    Discovery uses ``min_n`` (default 30). Validation uses ``max(15, min_n // 2)``
    because a chronological 30% holdout is often thinner than discovery buckets.
    """
    val_min_n = max(15, int(min_n) // 2)
    # Do not apply discovery lift filter here — OOS lookup needs the bucket even if flat.
    val_patterns = {
        (p["feature"], p["value"]): p
        for p in mine_buckets(validation_rows, min_n=val_min_n, require_lift=False)
    }
    survivors: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    for disc in discovery_patterns:
        key = (disc["feature"], disc["value"])
        val = val_patterns.get(key)
        if val is None:
            failed.append(
                {
                    **disc,
                    "status": "found_but_did_not_replicate",
                    "fail_reason": f"validation N<{val_min_n} or bucket absent",
                }
            )
            continue
        disc_lift = float(disc.get("lift") or 1.0)
        val_lift = float(val.get("lift") or 1.0)
        disc_dir = 1 if disc_lift >= 1 else -1
        val_dir = 1 if val_lift >= 1 else -1
        if disc_dir != val_dir:
            failed.append(
                {
                    **disc,
                    "validation": val,
                    "status": "found_but_did_not_replicate",
                    "fail_reason": "direction_reversed_in_validation",
                }
            )
            continue
        if abs(val_lift - 1.0) < min_lift_persist and abs(disc_lift - 1.0) >= min_lift_persist:
            failed.append(
                {
                    **disc,
                    "validation": val,
                    "status": "found_but_did_not_replicate",
                    "fail_reason": "effect_weakened_below_persistence_floor",
                }
            )
            continue
        survivors.append(
            {
                **disc,
                "validation": val,
                "status": "survived_oos",
                "validation_min_n": val_min_n,
            }
        )

    return {
        "survivors": survivors,
        "found_but_did_not_replicate": failed,
        "path_a_note": PATH_A_EXCLUSION_NOTE,
        "validation_min_n": val_min_n,
    }


def run_pattern_pipeline(
    panel_rows: Sequence[Dict[str, Any]],
    *,
    min_n: int = DEFAULT_MIN_N,
    discovery_frac: float = DISCOVERY_FRAC,
) -> Dict[str, Any]:
    """Run discovery mining + OOS validation; return survivors and failures."""
    discovery, validation, disc_days, val_days = chronological_split(
        panel_rows, discovery_frac=discovery_frac
    )
    discovery_patterns = mine_buckets(discovery, min_n=min_n)
    oos = validate_patterns(discovery_patterns, validation, min_n=min_n)
    return {
        "min_n": min_n,
        "discovery_frac": discovery_frac,
        "discovery_days": disc_days,
        "validation_days": val_days,
        "discovery_n_win_loss": len(_win_loss_rows(discovery)),
        "validation_n_win_loss": len(_win_loss_rows(validation)),
        "discovery_patterns_passing_n": discovery_patterns,
        "survivors": oos["survivors"],
        "found_but_did_not_replicate": oos["found_but_did_not_replicate"],
        "path_a_note": PATH_A_EXCLUSION_NOTE,
        "tod_limitation_note": (
            "If historical cache is EOD-only, tod_bucket findings are limited by snapshot "
            "frequency and should be treated cautiously."
        ),
    }
