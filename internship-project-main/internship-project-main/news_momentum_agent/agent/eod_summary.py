"""End-of-day cleanliness summary for paper options trading.

Pipeline role
-------------
Runs once per ET session (via ``maybe_run_eod_summary`` from the scheduler)
after the close. Aggregates:
  - option opens/closes from ``state/executions.json``,
  - LOG rejection codes from ``state/trade_log.json``,
  - near-miss shadow stats, Path A funnel line, quote-sanity pauses.

Delivers a Telegram digest (``format_telegram_summary``) and writes
``state/eod_summary_{date}.json``. Idempotency via ``state/eod_summary_sent.json``.

Merge notes for stocks/futures
------------------------------
  - **Reusable:** daily audit pattern, hold-time stats, rejection breakdown.
  - **Options-specific:** filters option fills, liquidity sub-reasons, flip-exit
    percentages — generalize instrument filter for futures/stock ledgers.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
EXECUTIONS_PATH = STATE_DIR / "executions.json"
TRADE_LOG_PATH = STATE_DIR / "trade_log.json"
SENT_MARKER_PATH = STATE_DIR / "eod_summary_sent.json"


def _now_et() -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now(timezone.utc)


def _session_date(now: Optional[datetime] = None) -> str:
    current = now or _now_et()
    return current.date().isoformat()


def _load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt
    except Exception:
        return None


def _to_et(dt: datetime) -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return dt.astimezone(ZoneInfo("America/New_York"))
    except Exception:
        return dt


def _is_outside_rth(et: datetime) -> bool:
    minutes = et.hour * 60 + et.minute
    return minutes < (9 * 60 + 30) or minutes >= (16 * 60)


def build_eod_summary(
    *,
    session_date: Optional[str] = None,
    executions: Optional[List[Dict[str, Any]]] = None,
    trade_log: Optional[List[Dict[str, Any]]] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute cleanliness metrics for one ET session date."""
    day = session_date or _session_date()
    fills = executions if executions is not None else _load_json(EXECUTIONS_PATH, [])
    if not isinstance(fills, list):
        fills = []
    logs = trade_log if trade_log is not None else _load_json(TRADE_LOG_PATH, [])
    if not isinstance(logs, list):
        logs = []

    day_fills: List[Dict[str, Any]] = []
    for row in fills:
        ts = _parse_ts(str(row.get("timestamp", "")))
        if not ts:
            continue
        if _to_et(ts).date().isoformat() != day:
            continue
        if str(row.get("instrument_type", "")).lower() == "option" or row.get("contract_symbol"):
            day_fills.append(row)

    opens = [r for r in day_fills if str(r.get("action")).lower() == "open"]
    closes = [r for r in day_fills if str(r.get("action")).lower() == "close"]

    # Hold times: FIFO match by ticker+contract
    queues: Dict[Tuple[str, str], List[datetime]] = {}
    hold_secs: List[float] = []
    for row in sorted(day_fills, key=lambda r: str(r.get("timestamp", ""))):
        ts = _parse_ts(str(row.get("timestamp", "")))
        if not ts:
            continue
        key = (str(row.get("ticker", "")), str(row.get("contract_symbol", "")))
        action = str(row.get("action")).lower()
        if action == "open":
            queues.setdefault(key, []).append(ts)
        elif action == "close":
            q = queues.get(key) or []
            if q:
                opened = q.pop(0)
                hold_secs.append(max(0.0, (ts - opened).total_seconds()))

    exit_reasons = Counter(str(r.get("reason") or "other") for r in closes)
    by_ticker = Counter(str(r.get("ticker") or "?") for r in opens)
    out_of_hours_opens = 0
    for row in opens:
        ts = _parse_ts(str(row.get("timestamp", "")))
        if ts and _is_outside_rth(_to_et(ts)):
            out_of_hours_opens += 1

    close_n = len(closes) or 1
    flip_n = int(exit_reasons.get("signal_flip", 0))
    flip_pct = round(100.0 * flip_n / close_n, 1) if closes else 0.0

    buckets = {
        "lt_1m": sum(1 for s in hold_secs if s < 60),
        "1_to_5m": sum(1 for s in hold_secs if 60 <= s < 300),
        "gte_5m": sum(1 for s in hold_secs if s >= 300),
    }
    held_gt_5_pct = round(100.0 * buckets["gte_5m"] / len(hold_secs), 1) if hold_secs else 0.0

    # Rejection codes from LOG rows
    reject_counts: Counter = Counter()
    liquidity_subreasons: Counter = Counter()
    liquidity_examples: List[Dict[str, Any]] = []
    for row in logs:
        ts = _parse_ts(str(row.get("timestamp", "")))
        if not ts or _to_et(ts).date().isoformat() != day:
            continue
        if str(row.get("decision", "")).upper() != "LOG":
            continue
        code = str(row.get("decision_reason_code") or row.get("review_reason_code") or "log_other")
        reject_counts[code] += 1
        if code != "liquidity_reject":
            continue
        meta = row.get("decision_meta") if isinstance(row.get("decision_meta"), dict) else {}
        snap = meta.get("factor_snapshot") if isinstance(meta.get("factor_snapshot"), dict) else {}
        primary = str(
            meta.get("liquidity_reject_primary")
            or snap.get("liquidity_reject_primary")
            or ""
        ).strip()
        detail = str(
            meta.get("liquidity_reject_detail")
            or snap.get("liquidity_reject_detail")
            or ""
        ).strip()
        if not primary:
            # Infer from legacy snapshots that only stored median spread.
            spread = snap.get("atm_median_spread_pct")
            min_oi = snap.get("atm_min_oi")
            if spread is None and min_oi is None:
                primary = "unspecified"
            elif spread is not None and float(spread) >= 0.99:
                primary = "no_listed_chain_or_unusable_quotes"
            else:
                primary = "spread_or_oi"
        liquidity_subreasons[primary] += 1
        if len(liquidity_examples) < 8:
            liquidity_examples.append(
                {
                    "ticker": row.get("ticker"),
                    "timestamp": row.get("timestamp"),
                    "primary": primary,
                    "detail": detail,
                    "atm_median_spread_pct": snap.get("atm_median_spread_pct"),
                    "atm_min_oi": snap.get("atm_min_oi"),
                    "atm_max_oi": snap.get("atm_max_oi"),
                    "liquidity_max_spread_pct": snap.get("liquidity_max_spread_pct"),
                    "liquidity_min_oi_required": snap.get("liquidity_min_oi_required"),
                    "liquidity_nearest_dte": snap.get("liquidity_nearest_dte"),
                }
            )

    try:
        from agent.quote_sanity import paused_tickers

        paused = paused_tickers()
    except Exception:
        paused = []

    flags = {
        "signal_flip_high": flip_pct > 20.0,
        "out_of_hours_opens": out_of_hours_opens > 0,
        "identical_quote_pauses": len(paused) > 0,
    }
    hold_stats = {
        "count": len(hold_secs),
        "min_sec": round(min(hold_secs), 1) if hold_secs else None,
        "median_sec": round(statistics.median(hold_secs), 1) if hold_secs else None,
        "max_sec": round(max(hold_secs), 1) if hold_secs else None,
        "buckets": buckets,
        "pct_held_gt_5m": held_gt_5_pct,
    }
    exit_breakdown = {
        reason: {"count": count, "pct": round(100.0 * count / close_n, 1) if closes else 0.0}
        for reason, count in exit_reasons.most_common()
    }

    clean = not any(flags.values()) and flip_pct <= 20.0 and out_of_hours_opens == 0
    headline = (
        f"{len(opens)} opens / {len(closes)} closes, "
        f"{held_gt_5_pct}% held >5min, "
        f"{out_of_hours_opens} out-of-hours opens, "
        f"{flip_pct}% signal_flip exits"
        + (" — CLEAN" if clean else " — NEEDS REVIEW")
    )

    near_miss: Dict[str, Any] = {}
    try:
        from agent.near_miss_tracker import build_near_miss_eod_section

        near_miss = build_near_miss_eod_section(session_date=day, settings=settings)
    except Exception:
        near_miss = {}

    path_a_funnel: Dict[str, Any] = {}
    try:
        from agent.path_a_pipeline_health import format_funnel_line, load_health

        path_a_health = load_health()
        path_a_funnel = {
            "funnel_line": path_a_health.get("funnel_line") or format_funnel_line(path_a_health),
            "consecutive_zero": path_a_health.get("consecutive_zero") or {},
            "alert_threshold": path_a_health.get("alert_threshold"),
            "updated_at": path_a_health.get("updated_at"),
        }
    except Exception:
        path_a_funnel = {}

    return {
        "session_date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "headline": headline,
        "clean": clean,
        "opens": len(opens),
        "closes": len(closes),
        "hold_time": hold_stats,
        "exit_reasons": exit_breakdown,
        "trades_by_ticker": dict(by_ticker.most_common()),
        "out_of_hours_opens": out_of_hours_opens,
        "signal_flip_pct": flip_pct,
        "rejection_codes": dict(reject_counts.most_common(20)),
        "liquidity_reject_subreasons": dict(liquidity_subreasons.most_common()),
        "liquidity_reject_examples": liquidity_examples,
        "paused_quote_tickers": paused,
        "flags": flags,
        "near_miss": near_miss,
        "path_a_funnel": path_a_funnel,
    }


def save_eod_summary(summary: Dict[str, Any]) -> Path:
    """Write summary dict to ``state/eod_summary_{session_date}.json``. Returns path."""
    day = str(summary.get("session_date") or _session_date())
    path = STATE_DIR / f"eod_summary_{day}.json"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    temp.replace(path)
    return path


def format_telegram_summary(summary: Dict[str, Any]) -> str:
    """Format an EOD summary dict as a multi-line Telegram message body."""
    holds = summary.get("hold_time") or {}
    exits = summary.get("exit_reasons") or {}
    exit_bits = ", ".join(f"{k}={v.get('count')}" for k, v in list(exits.items())[:6])
    rejects = summary.get("rejection_codes") or {}
    reject_bits = ", ".join(f"{k}={v}" for k, v in list(rejects.items())[:6]) or "none"
    liq_subs = summary.get("liquidity_reject_subreasons") or {}
    liq_bits = ", ".join(f"{k}={v}" for k, v in list(liq_subs.items())[:6])
    lines = [
        f"EOD SUMMARY {summary.get('session_date')}",
        f"{summary.get('headline')}",
        f"Hold sec min/med/max: {holds.get('min_sec')}/{holds.get('median_sec')}/{holds.get('max_sec')}",
        f"Exits: {exit_bits or 'none'}",
        f"By ticker: {summary.get('trades_by_ticker')}",
        f"LOG rejects: {reject_bits}",
    ]
    if liq_bits:
        lines.append(f"Liquidity sub-reasons: {liq_bits}")
    near_miss = summary.get("near_miss") or {}
    if near_miss.get("alpaca_error_alert") or int(near_miss.get("alpaca_error_count") or 0) > 0:
        lines.append(
            f"ALERT: alpaca_error={near_miss.get('alpaca_error_count', 0)} "
            f"(kinds={near_miss.get('by_alpaca_error_kind') or {}}) — not confirmed empty near-expiry chain."
        )
    if near_miss.get("yahoo_expiry_gap_caveat") or (
        "yfinance often omits" in str(near_miss.get("no_0dte_note") or "")
    ):
        lines.append(
            "CAVEAT: Yahoo may have omitted ETF same-day expiries today — "
            "near-miss chain labels for SPY/QQQ are not ground truth without Alpaca confirm."
        )
    if near_miss:
        try:
            from agent.near_miss_tracker import format_near_miss_telegram

            lines.append(format_near_miss_telegram(near_miss))
        except Exception:
            pass
    path_a = summary.get("path_a_funnel") or {}
    funnel_line = str(path_a.get("funnel_line") or "").strip()
    if funnel_line:
        lines.append(f"Path A: {funnel_line}")
    return "\n".join(lines)


def already_sent_today(session_date: Optional[str] = None) -> bool:
    """True if EOD summary Telegram was already sent for this ET session date."""
    day = session_date or _session_date()
    data = _load_json(SENT_MARKER_PATH, {})
    return isinstance(data, dict) and str(data.get("date")) == day and bool(data.get("sent"))


def mark_sent(session_date: Optional[str] = None) -> None:
    """Record that today's EOD summary was sent in ``state/eod_summary_sent.json``."""
    day = session_date or _session_date()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"date": day, "sent": True, "at": datetime.now(timezone.utc).isoformat()}
    temp = SENT_MARKER_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(SENT_MARKER_PATH)


def maybe_run_eod_summary(settings: Dict[str, Any], *, force: bool = False) -> Optional[Dict[str, Any]]:
    """
    Build, save, and Telegram-send the EOD summary once per ET day after 16:05.

    Returns the summary dict, or None if skipped (weekend, too early, already sent).
    ``force=True`` bypasses time and sent checks (useful for manual reruns).
    """
    now = _now_et()
    if not force:
        if now.weekday() >= 5:
            return None
        if (now.hour, now.minute) < (16, 5):
            return None
        if already_sent_today(now.date().isoformat()):
            return None

    summary = build_eod_summary(session_date=now.date().isoformat(), settings=settings)
    path = save_eod_summary(summary)
    print(f"[eod_summary] wrote {path}: {summary.get('headline')}")
    try:
        from agent.near_miss_tracker import save_near_miss_eod_section

        near_miss = summary.get("near_miss") or {}
        if near_miss:
            nm_path = save_near_miss_eod_section(near_miss)
            print(f"[eod_summary] wrote near-miss report {nm_path}")
    except Exception as error:
        print(f"[eod_summary] near-miss report failed: {error}")
    try:
        from agent.telegram_notifier import send_text

        send_text(format_telegram_summary(summary), settings)
    except Exception as error:
        print(f"[eod_summary] Telegram failed: {error}")
    if not force:
        mark_sent(now.date().isoformat())
    return summary


def load_latest_eod_summary() -> Dict[str, Any]:
    """Load today's EOD summary JSON, or the most recent ``eod_summary_*.json`` on disk."""
    day = _session_date()
    path = STATE_DIR / f"eod_summary_{day}.json"
    data = _load_json(path, {})
    if isinstance(data, dict) and data:
        return data
    # Fall back to newest eod_summary_*.json
    files = sorted(STATE_DIR.glob("eod_summary_*.json"), reverse=True)
    for f in files:
        data = _load_json(f, {})
        if isinstance(data, dict) and data.get("headline"):
            return data
    return {}
