"""Pre-trade risk controls and daily PnL circuit breaker for autonomous execution.

Pipeline role
-------------
``check_new_trade_allowed`` runs in ``portfolio.execute_options_decision``
*before* sizing and opening a new position. Also maintains:
  - daily entry caps and per-ticker cooldowns,
  - concurrent 0DTE / overnight position limits,
  - simple correlation-bucket exposure caps,
  - kill-switch and daily loss circuit breaker.

State files
-----------
  - ``state/daily_risk.json`` — today's realized PnL, halt flag, entry counts.
  - ``state/calibration_log.json`` — predicted confidence vs outcomes (research).

Sector / correlation map (``CORRELATION_BUCKETS``) is intentionally simple for
v1 — ticker → theme bucket so rules are explainable without clustering.

Merge notes for stocks/futures
------------------------------
  - **Highly reusable:** daily loss circuit, entry counting, correlation caps
    (extend buckets for sector futures / index products).
  - **Options-specific:** ``fixed_fractional_contracts`` (premium × 100 × stop),
    ``max_concurrent_0dte``, overnight hold cap keyed on option expiration.
  - **Futures fork:** swap contract sizing helper; keep ``check_new_trade_allowed``
    gate pattern and ``daily_risk.json`` lifecycle.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
CALIBRATION_PATH = STATE_DIR / "calibration_log.json"
DAILY_PNL_PATH = STATE_DIR / "daily_risk.json"

# Simple correlation buckets — names in the same bucket count as one "theme".
CORRELATION_BUCKETS: Dict[str, str] = {
    "SPY": "index",
    "QQQ": "index_tech",
    "IWM": "index_small",
    "DIA": "index",
    "AAPL": "mega_tech",
    "MSFT": "mega_tech",
    "GOOGL": "mega_tech",
    "GOOG": "mega_tech",
    "AMZN": "mega_tech",
    "META": "mega_tech",
    "NVDA": "semi",
    "AMD": "semi",
    "AVGO": "semi",
    "TSLA": "consumer_growth",
    "NFLX": "consumer_growth",
}


def correlation_bucket(ticker: str) -> str:
    """Return correlation bucket id for a ticker."""
    return CORRELATION_BUCKETS.get(ticker.upper().strip(), f"single:{ticker.upper().strip()}")


def _today_et_key() -> str:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_daily_risk() -> Dict[str, Any]:
    """Load today's risk counters from ``state/daily_risk.json`` (resets on ET date change)."""
    empty = {
        "date": _today_et_key(),
        "realized_pnl": 0.0,
        "halted": False,
        "entries_today": 0,
        "last_entry_by_ticker": {},
    }
    try:
        if not DAILY_PNL_PATH.exists():
            return dict(empty)
        data = json.loads(DAILY_PNL_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(empty)
        if data.get("date") != _today_et_key():
            return dict(empty)
        data.setdefault("entries_today", 0)
        data.setdefault("last_entry_by_ticker", {})
        return data
    except Exception:
        return dict(empty)


def record_new_entry(ticker: str, settings: Optional[Dict[str, Any]] = None) -> None:
    """Count a new 0DTE entry for daily / per-ticker caps."""
    _ = settings
    daily = load_daily_risk()
    daily["entries_today"] = int(daily.get("entries_today", 0)) + 1
    last = daily.setdefault("last_entry_by_ticker", {})
    if not isinstance(last, dict):
        last = {}
        daily["last_entry_by_ticker"] = last
    last[str(ticker).upper().strip()] = datetime.now(timezone.utc).isoformat()
    save_daily_risk(daily)


def save_daily_risk(payload: Dict[str, Any]) -> None:
    """Persist daily risk state to ``state/daily_risk.json``."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = DAILY_PNL_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(DAILY_PNL_PATH)


def record_realized_pnl(pnl: float, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Accumulate daily realized PnL and trip circuit breaker if needed."""
    cfg = (settings or {}).get("risk") or {}
    daily = load_daily_risk()
    daily["realized_pnl"] = float(daily.get("realized_pnl", 0.0)) + float(pnl)
    starting = float((settings or {}).get("trading", {}).get("starting_cash", 100000))
    limit_pct = float(cfg.get("daily_loss_circuit_pct", 0.03))
    if starting > 0 and daily["realized_pnl"] <= -abs(limit_pct) * starting:
        daily["halted"] = True
        daily["halt_reason"] = (
            f"daily_loss_circuit ({daily['realized_pnl']:.2f} <= {-abs(limit_pct)*starting:.2f})"
        )
    save_daily_risk(daily)
    return daily


def fixed_fractional_contracts(
    *,
    equity: float,
    premium: float,
    risk_fraction: float,
    stop_loss_pct: float,
    max_contracts: int = 20,
) -> int:
    """
    Size contracts so that a stop-out loses ~risk_fraction of equity.

    risk_dollars = equity * risk_fraction
    loss_per_contract ≈ premium * 100 * stop_loss_pct
    """
    if equity <= 0 or premium <= 0 or risk_fraction <= 0 or stop_loss_pct <= 0:
        return 0
    risk_dollars = equity * risk_fraction
    loss_per = premium * 100.0 * stop_loss_pct
    if loss_per <= 0:
        return 0
    qty = int(risk_dollars // loss_per)
    return max(0, min(int(max_contracts), qty))


def check_new_trade_allowed(
    *,
    ticker: str,
    decision: str,
    portfolio: Dict[str, Any],
    settings: Dict[str, Any],
    option_side: str | None = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Pre-trade risk gate. Returns (allowed, reason, details).

    Does not open the trade — caller still executes if allowed.
    """
    cfg = settings.get("risk") or {}
    trading = settings.get("trading") or {}
    details: Dict[str, Any] = {"ticker": ticker.upper().strip(), "decision": decision}

    if bool(cfg.get("force_review_all", False)) or bool(
        (settings.get("execution") or {}).get("force_review_all", False)
    ):
        return False, "kill_switch_force_review_all", details

    if not bool(cfg.get("enabled", True)):
        return True, "risk_disabled", details

    daily = load_daily_risk()
    details["daily_realized_pnl"] = daily.get("realized_pnl", 0.0)
    details["entries_today"] = int(daily.get("entries_today", 0))
    if daily.get("halted"):
        return False, str(daily.get("halt_reason") or "daily_loss_circuit"), details

    max_entries = int(cfg.get("max_new_0dte_entries_per_day", 5))
    if max_entries > 0 and int(daily.get("entries_today", 0)) >= max_entries:
        return False, f"max_new_0dte_entries_per_day ({daily.get('entries_today')}>={max_entries})", details

    min_gap = int(cfg.get("min_minutes_between_entries_same_ticker", 240))
    if min_gap > 0:
        last_map = daily.get("last_entry_by_ticker") or {}
        stamp = last_map.get(ticker.upper().strip()) if isinstance(last_map, dict) else None
        if stamp:
            try:
                last_dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                age_min = (datetime.now(timezone.utc) - last_dt).total_seconds() / 60.0
                if age_min < min_gap:
                    return (
                        False,
                        f"ticker_entry_cooldown ({ticker} {age_min:.0f}m<{min_gap}m)",
                        details,
                    )
            except ValueError:
                pass

    positions = portfolio.get("positions") or {}
    if not isinstance(positions, dict):
        positions = {}

    # Count 0DTE / options positions
    open_option_positions = []
    for sym, pos in positions.items():
        if not isinstance(pos, dict):
            continue
        if str(pos.get("instrument_type", "")).lower() == "option" or str(sym).count(" ") >= 1:
            open_option_positions.append(sym)
        elif str(pos.get("option_side", "")) in {"call", "put"}:
            open_option_positions.append(sym)

    max_concurrent = int(cfg.get("max_concurrent_0dte", trading.get("max_positions", 4)))
    details["open_0dte"] = len(open_option_positions)
    if len(open_option_positions) >= max_concurrent:
        return False, f"max_concurrent_0dte ({len(open_option_positions)}>={max_concurrent})", details

    # Overnight / multi-day hold cap (expiration after today ET).
    max_overnight = int(cfg.get("max_overnight_positions", 0) or 0)
    if max_overnight > 0:
        try:
            from agent.market_session import now_et

            today_iso = now_et().date().isoformat()
        except Exception:
            today_iso = datetime.now(timezone.utc).date().isoformat()
        overnight_count = 0
        for sym, pos in positions.items():
            if not isinstance(pos, dict):
                continue
            is_opt = (
                str(pos.get("instrument_type", "")).lower() == "option"
                or str(pos.get("option_side", "")) in {"call", "put"}
            )
            if not is_opt:
                continue
            exp = str(pos.get("expiration") or "").strip()
            if exp and exp > today_iso:
                overnight_count += 1
        details["overnight_open"] = overnight_count
        # Incoming trade becomes overnight if we will pick a non-today expiry;
        # gate when already at cap (new multi-day entries blocked).
        if overnight_count >= max_overnight:
            # Allow same-day (0DTE) entries still; callers pass option_side only.
            # Soft check: when overnight horizon is active and cap reached, refuse
            # new multi-day entries. Conservative: block when at overnight cap.
            from agent.market_session import (
                allows_overnight_holds,
                effective_options_max_dte,
            )

            if allows_overnight_holds(settings) and int(effective_options_max_dte(settings)) > 0:
                return (
                    False,
                    f"max_overnight_positions ({overnight_count}>={max_overnight})",
                    details,
                )

    # Correlation cap within same bucket + same directional side
    bucket = correlation_bucket(ticker)
    max_corr = int(cfg.get("max_correlated_group", 2))
    same_bucket = 0
    desired_side = "call" if str(decision).upper() == "BUY" else "put"
    if option_side in {"call", "put"}:
        desired_side = option_side
    for sym, pos in positions.items():
        if not isinstance(pos, dict):
            continue
        underlying = str(pos.get("underlying") or sym.split()[0] if sym else "").upper()
        if not underlying:
            underlying = str(sym).upper()
        if correlation_bucket(underlying) != bucket:
            continue
        side = str(pos.get("option_side") or pos.get("side") or "").lower()
        # Treat long call / short put-ish as bullish; we only open long premium.
        if side == desired_side or (desired_side == "call" and side in {"long", "call"}):
            same_bucket += 1
        elif desired_side == "put" and side in {"put"}:
            same_bucket += 1
    details["correlation_bucket"] = bucket
    details["same_bucket_count"] = same_bucket
    if same_bucket >= max_corr:
        return False, f"correlation_cap bucket={bucket} ({same_bucket}>={max_corr})", details

    return True, "ok", details


def append_calibration_record(record: Dict[str, Any]) -> None:
    """Append one predicted-confidence vs outcome row for internship analysis."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    try:
        if CALIBRATION_PATH.exists():
            data = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                rows = data
    except Exception:
        rows = []
    rows.append(record)
    temp = CALIBRATION_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    temp.replace(CALIBRATION_PATH)


def calibration_entry_from_trade(
    *,
    trade_entry: Dict[str, Any],
    outcome: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a calibration log row from a trade log entry (+ optional exit outcome)."""
    return {
        "timestamp": trade_entry.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "ticker": trade_entry.get("ticker"),
        "decision": trade_entry.get("decision"),
        "predicted_confidence_pct": trade_entry.get("confidence_pct"),
        "predicted_confidence_label": trade_entry.get("confidence")
        or trade_entry.get("confidence_label"),
        "agreement": (trade_entry.get("decision_meta") or {}).get("agreement"),
        "signal_source": trade_entry.get("signal_source"),
        "options_score": trade_entry.get("options_score"),
        "gex_regime": (trade_entry.get("decision_meta") or {}).get("gex_regime"),
        "outcome": outcome,
    }
