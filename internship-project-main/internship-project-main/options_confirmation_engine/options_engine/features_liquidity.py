"""Liquidity / spread floor checks for options contract selection.

Purpose
-------
Hard gate: reject names whose ATM band has no contract passing spread and OI
floors before the agent sizes a 0DTE or multi-day options thesis.

Features / API role
-------------------
``compute_liquidity_features`` → ``liquidity_ok``, ``liquidity_reject``,
``liquidity_reject_primary``, ``atm_median_spread_pct``, etc.
``format_liquidity_reject_detail`` for human-readable logs.

How ``news_momentum_agent`` consumes it
---------------------------------------
``agent/odte_decision`` imports ``format_liquidity_reject_detail`` when
``liquidity_reject`` is set on scored features. Does not change thresholds at
runtime — observation and block only.

Options-specific vs reusable
----------------------------
Options-specific (ATM band, contract spread/OI). Reusable pattern: primary +
sub-reason codes for structured reject telemetry.

Why this gate exists
--------------------
Path A often surfaces small/micro-cap news names with **no listed options chain**
or ATM spreads of **46–60%+**. A correct directional thesis still loses edge
paying those spreads. Liquidity is therefore a **hard reject** before sizing —
thresholds were deliberately *not* loosened when discovery widened; discovery
was steered toward optionable mid/large names instead.

Primary reject codes (``liquidity_reject_primary``):
  - ``no_listed_chain`` / ``empty_atm_band`` / ``no_spot``
  - ``spread_too_wide`` — median ATM (ask-bid)/mid above max
  - ``oi_below_min`` — open interest below floor
  - ``missing_or_invalid_quotes``

Sub-reason / detail fields are **observation-only** (logs, EOD, near-miss) —
they explain which check failed and by how much without changing pass/fail.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from options_engine.data_models import ContractRow, Snapshot


def _nearest_dte_from_contracts(contracts: List[ContractRow], as_of: str | None = None) -> Optional[float]:
    """Calendar DTE of the soonest expiry in the snapshot (ET date; None if unknown/empty)."""
    if not contracts:
        return None
    try:
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
    except Exception:
        et = timezone.utc
    try:
        if as_of:
            current = datetime.fromisoformat(str(as_of).replace("Z", "+00:00")).astimezone(et).date()
        else:
            current = datetime.now(timezone.utc).astimezone(et).date()
    except Exception:
        current = datetime.now(timezone.utc).astimezone(et).date()
    dtes: List[int] = []
    for row in contracts:
        exp = str(getattr(row, "expiration", "") or "").strip()
        if not exp:
            continue
        try:
            exp_date = datetime.strptime(exp[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        dtes.append((exp_date - current).days)
    if not dtes:
        return None
    return float(min(dtes))


def contract_spread_pct_of_mid(row: ContractRow) -> Optional[float]:
    """Return (ask-bid)/mid, or None if quotes are unusable."""
    bid = float(row.bid or 0.0)
    ask = float(row.ask or 0.0)
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return None
    return (ask - bid) / mid


def evaluate_contract_liquidity(
    row: ContractRow,
    *,
    max_spread_pct_of_mid: float,
    min_oi: float,
) -> Tuple[bool, str, float]:
    """
    Return (passes, reason, spread_pct).

    ``passes`` is False when the contract fails the hard liquidity floor.
    """
    oi = float(row.open_interest or 0.0)
    if oi < min_oi:
        return False, f"oi_below_min ({oi:.0f}<{min_oi:.0f})", 1.0
    spread = contract_spread_pct_of_mid(row)
    if spread is None:
        return False, "missing_or_invalid_quotes", 1.0
    if spread > max_spread_pct_of_mid:
        return False, f"spread_too_wide ({spread:.1%}>{max_spread_pct_of_mid:.1%})", float(spread)
    return True, "ok", float(spread)


def _primary_fail_code(reason: str) -> str:
    text = str(reason or "")
    if text.startswith("oi_below_min"):
        return "oi_below_min"
    if text.startswith("spread_too_wide"):
        return "spread_too_wide"
    if text == "missing_or_invalid_quotes":
        return "missing_or_invalid_quotes"
    if text == "ok":
        return "ok"
    return "other"


def format_liquidity_reject_detail(feats: Dict[str, Any]) -> str:
    """Human-readable one-liner for logs / EOD (observation only)."""
    if float(feats.get("liquidity_reject", 0.0) or 0.0) < 1.0:
        return ""
    primary = str(feats.get("liquidity_reject_primary") or "liquidity_reject")
    max_spread = float(feats.get("liquidity_max_spread_pct") or 0.0)
    min_oi = float(feats.get("liquidity_min_oi_required") or 0.0)
    median_spread = float(feats.get("atm_median_spread_pct") or 0.0)
    min_atm_oi = float(feats.get("atm_min_oi") or 0.0)
    max_atm_oi = float(feats.get("atm_max_oi") or 0.0)
    atm_n = int(float(feats.get("atm_contract_count") or 0.0))
    nearest_dte = feats.get("liquidity_nearest_dte")
    bits = [primary]
    if primary == "no_spot":
        bits.append("spot unavailable")
    elif primary in {"no_listed_chain", "empty_atm_band"}:
        bits.append(f"atm_contracts={atm_n}")
    else:
        bits.append(
            f"spread={median_spread:.1%} (max allowed {max_spread:.1%}), "
            f"OI min/max in ATM={min_atm_oi:.0f}/{max_atm_oi:.0f} (min required {min_oi:.0f}), "
            f"atm_n={atm_n}"
        )
    if nearest_dte is not None:
        try:
            bits.append(f"nearest_dte={float(nearest_dte):.0f}")
        except Exception:
            pass
    fail_counts = feats.get("liquidity_fail_counts") or {}
    if isinstance(fail_counts, dict) and fail_counts:
        counted = ", ".join(f"{k}={v}" for k, v in sorted(fail_counts.items()) if int(v or 0) > 0)
        if counted:
            bits.append(f"fails[{counted}]")
    return " | ".join(bits)


def compute_liquidity_features(snapshot: Snapshot, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aggregate ATM-band liquidity quality for the chain.

    ``liquidity_ok`` is True if *some* ATM-band contract passes the hard floor
    (not "average looks fine"). Small-cap chains often fail entirely via
    ``no_listed_chain`` or every ATM row failing spread/OI — that mismatch is
    why Path A mid/large widening and multi-day ``range`` horizon exist.

    Keys:
      - atm_median_spread_pct
      - atm_min_oi / atm_max_oi / atm_contract_count
      - liquidity_ok (1.0 / 0.0)
      - liquidity_available
      - liquidity_reject (1.0 when hard-fail for trading the name today)
      - liquidity_reject_primary / liquidity_reject_detail (observation only)
      - liquidity_fail_counts (per sub-check counts across ATM contracts)
      - threshold mirrors: liquidity_max_spread_pct, liquidity_min_oi_required
    """
    odte = settings.get("odte_signals", {}).get("liquidity", {})
    if not bool(odte.get("enabled", True)):
        return {
            "atm_median_spread_pct": 0.0,
            "atm_min_oi": 0.0,
            "atm_max_oi": 0.0,
            "atm_contract_count": 0.0,
            "liquidity_ok": 1.0,
            "liquidity_available": 0.0,
            "liquidity_reject": 0.0,
            "liquidity_reject_primary": "",
            "liquidity_reject_detail": "",
            "liquidity_fail_counts": {},
            "liquidity_max_spread_pct": float(odte.get("max_spread_pct_of_mid", 0.08)),
            "liquidity_min_oi_required": float(odte.get("min_oi", 100)),
            "liquidity_nearest_dte": None,
        }

    spot = float(snapshot.spot_price or 0.0)
    band = float(odte.get("atm_band_pct", settings.get("features", {}).get("atm_strike_band_pct", 0.03)))
    max_spread = float(odte.get("max_spread_pct_of_mid", 0.08))
    min_oi = float(odte.get("min_oi", 100))

    # Best-effort nearest DTE from the snapshot (helps distinguish 0DTE-absent days).
    nearest_dte = _nearest_dte_from_contracts(list(snapshot.contracts or []), snapshot.as_of)

    base_thresholds = {
        "liquidity_max_spread_pct": max_spread,
        "liquidity_min_oi_required": min_oi,
        "liquidity_nearest_dte": nearest_dte,
    }

    if spot <= 0:
        out = {
            "atm_median_spread_pct": 0.0,
            "atm_min_oi": 0.0,
            "atm_max_oi": 0.0,
            "atm_contract_count": 0.0,
            "liquidity_ok": 0.0,
            "liquidity_available": 0.0,
            "liquidity_reject": 1.0,
            "liquidity_reject_primary": "no_spot",
            "liquidity_fail_counts": {"no_spot": 1},
            **base_thresholds,
        }
        out["liquidity_reject_detail"] = format_liquidity_reject_detail(out)
        return out

    contracts = list(snapshot.contracts or [])
    if not contracts:
        out = {
            "atm_median_spread_pct": 1.0,
            "atm_min_oi": 0.0,
            "atm_max_oi": 0.0,
            "atm_contract_count": 0.0,
            "liquidity_ok": 0.0,
            "liquidity_available": 0.0,
            "liquidity_reject": 1.0,
            "liquidity_reject_primary": "no_listed_chain",
            "liquidity_fail_counts": {"no_listed_chain": 1},
            **base_thresholds,
        }
        out["liquidity_reject_detail"] = format_liquidity_reject_detail(out)
        return out

    lower = spot * (1.0 - band)
    upper = spot * (1.0 + band)
    atm = [r for r in contracts if lower <= float(r.strike) <= upper]
    used_full_chain_fallback = False
    if not atm:
        atm = list(contracts)
        used_full_chain_fallback = True

    spreads: List[float] = []
    oi_vals: List[float] = []
    vol_vals: List[float] = []
    fail_counts: Counter = Counter()
    any_pass = False
    for row in atm:
        oi_vals.append(float(row.open_interest or 0.0))
        vol_vals.append(float(getattr(row, "volume", 0.0) or 0.0))
        ok, reason, spread = evaluate_contract_liquidity(
            row, max_spread_pct_of_mid=max_spread, min_oi=min_oi
        )
        if spread < 1.0:
            spreads.append(spread)
        if ok:
            any_pass = True
            fail_counts["ok"] += 1
        else:
            fail_counts[_primary_fail_code(reason)] += 1

    spreads_sorted = sorted(spreads)
    if spreads_sorted:
        mid_idx = len(spreads_sorted) // 2
        median_spread = spreads_sorted[mid_idx]
    else:
        median_spread = 1.0

    min_atm_oi = min(oi_vals) if oi_vals else 0.0
    max_atm_oi = max(oi_vals) if oi_vals else 0.0
    # Observation only — volume is not part of the hard floor today.
    atm_max_volume = max(vol_vals) if vol_vals else 0.0

    reject = not any_pass
    if reject:
        ranked = [
            (code, n)
            for code, n in fail_counts.items()
            if code != "ok" and int(n or 0) > 0
        ]
        if ranked:
            primary = max(ranked, key=lambda kv: kv[1])[0]
        elif used_full_chain_fallback:
            primary = "empty_atm_band"
        else:
            primary = "liquidity_reject"
    else:
        primary = ""

    out: Dict[str, Any] = {
        "atm_median_spread_pct": float(median_spread),
        "atm_min_oi": float(min_atm_oi),
        "atm_max_oi": float(max_atm_oi),
        "atm_contract_count": float(len(atm)),
        "atm_max_volume": float(atm_max_volume),
        "liquidity_ok": 1.0 if any_pass else 0.0,
        "liquidity_available": 1.0 if atm else 0.0,
        "liquidity_reject": 1.0 if reject else 0.0,
        "liquidity_reject_primary": primary,
        "liquidity_fail_counts": dict(fail_counts),
        **base_thresholds,
    }
    out["liquidity_reject_detail"] = format_liquidity_reject_detail(out) if reject else ""
    return out
