#!/usr/bin/env python3
"""Seed realistic demo state for professor meetings outside market hours.

CLI
---
``python scripts/seed_demo_state.py`` — writes synthetic ``state/*.json`` and
creates ``state/demo.lock`` so live ``main.py`` skips overwriting demo data.

When to run
-----------
After market close or when Finviz returns empty; before dashboard demos when no
live agent cycle is available.

Safe vs live agent
------------------
**Safe / offline:** Does not call brokers or schedulers. Creates ``demo.lock`` —
remove that file before resuming live ``main.py`` or live state will stay frozen.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

STATE_DIR = PROJECT_ROOT / "state"
DEMO_LOCK_PATH = STATE_DIR / "demo.lock"
SETTINGS_PATH = PROJECT_ROOT / "settings.json"

# Demo position sizing (matches auto-execute equal-weight logic at ~$100k / 10 slots)
BOXL_ENTRY, BOXL_MARK = 3.58, 3.90
BJRI_ENTRY, BJRI_MARK = 54.72, 54.15
BOXL_QTY = 2773
BJRI_QTY = -182


def now_iso() -> str:
    """Current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def ago_iso(minutes: int) -> str:
    """UTC ISO-8601 timestamp ``minutes`` before now."""
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def save_json(path: Path, payload: Any) -> None:
    """Atomically write JSON payload to ``path`` via a temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(path)


def load_settings() -> Dict[str, Any]:
    """Load ``settings.json`` from the project root."""
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


def options_state_dir(settings: Dict[str, Any]) -> Path:
    """Resolve options confirmation engine ``state/`` directory from settings."""
    engine_path = str(settings.get("options_confirmation", {}).get("engine_path", "")).strip()
    if engine_path:
        return Path(engine_path).expanduser() / "state"
    return PROJECT_ROOT.parent / "options_confirmation_engine" / "state"


def social_post(body: str, keywords: List[str], post_id: int, minutes_ago: int) -> Dict[str, Any]:
    """Build a fake StockTwits-like post for demo watchlist rows."""
    return {
        "id": post_id,
        "created_at": ago_iso(minutes_ago).replace("+00:00", "Z"),
        "body": body,
        "keywords_found": keywords,
        "post_score": len(keywords),
    }


def watchlist_item(
    ticker: str,
    company: str,
    price: float,
    pct: float,
    volume: int,
    level: str,
    score: int,
    posts: List[Dict[str, Any]],
    reason: str,
    relative_volume: float = 2.0,
) -> Dict[str, Any]:
    """Build one demo ``watchlist.json`` row with social metadata."""
    avg_volume = int(volume / relative_volume) if relative_volume > 0 else volume
    return {
        "ticker": ticker,
        "company_name": company,
        "current_price": price,
        "percent_change": pct,
        "volume": volume,
        "average_volume": avg_volume,
        "relative_volume": relative_volume,
        "source": "news",
        "added_at": now_iso(),
        "social_signal_level": level,
        "social_total_score": score,
        "social_triggered_posts": posts,
        "social_posts_fetched": 30,
        "social_recent_posts_scanned": max(1, len(posts) * 3),
        "social_posts_matched": len(posts),
        "social_reason_code": reason,
    }


def options_signal(
    ticker: str,
    score: float,
    bias: str,
    spot: float,
    features: Dict[str, float],
    summary: str,
) -> Dict[str, Any]:
    """Build one demo options-engine signal row for the dashboard Options tab."""
    return {
        "ticker": ticker,
        "options_score": score,
        "options_bias": bias,
        "feature_values": features,
        "data_quality": {"quality_score": 1.0, "flags": []},
        "reasoning_summary": summary,
        "as_of": now_iso(),
        "spot_price": spot,
        "request_id": f"demo-{ticker}-{now_iso()}",
    }


def bullish_features() -> Dict[str, float]:
    """Static bullish feature dict used by demo options signals."""
    return {
        "put_call_volume_ratio": 0.62,
        "call_volume_share": 0.68,
        "put_call_oi_ratio": 0.71,
        "net_delta_oi": 0.18,
        "iv_skew": -0.012,
        "greeks_available": 1.0,
        "iv_skew_available": 1.0,
        "volume_available": 1.0,
        "oi_available": 1.0,
        "atm_iv": 0.42,
        "atm_iv_change": 0.03,
        "iv_rank": 0.55,
        "oi_near_spot_concentration": 0.72,
        "volume_to_oi_spike": 2.4,
        "nearest_dte": 5.0,
        "max_oi_strike": 4.0,
        "max_oi_strike_pct_from_spot": 11.7,
        "total_oi": 12000.0,
        "volume_oi_spike": 2.4,
    }


def bearish_features() -> Dict[str, float]:
    """Static bearish feature dict used by demo options signals."""
    return {
        "put_call_volume_ratio": 1.35,
        "call_volume_share": 0.38,
        "put_call_oi_ratio": 1.28,
        "net_delta_oi": -0.14,
        "iv_skew": 0.045,
        "greeks_available": 1.0,
        "iv_skew_available": 1.0,
        "volume_available": 1.0,
        "oi_available": 1.0,
        "atm_iv": 0.51,
        "atm_iv_change": 0.05,
        "iv_rank": 0.62,
        "oi_near_spot_concentration": 0.58,
        "volume_to_oi_spike": 3.1,
        "nearest_dte": 3.0,
        "max_oi_strike": 50.0,
        "max_oi_strike_pct_from_spot": -8.6,
        "total_oi": 18000.0,
        "volume_oi_spike": 3.1,
    }


def trade_entry(
    ticker: str,
    decision: str,
    score: float,
    headline: str,
    source: str,
    social_level: str,
    options_score: float,
    options_bias: str,
    options_reason: str,
    executed: bool,
    fills: List[Dict[str, Any]],
    minutes_ago: int,
    action_probs: Dict[str, float] | None = None,
    lean: str = "WAIT",
    lean_pct: int = 40,
    instrument_hint: str = "stock",
    signal_source: str = "news",
    herd_stage: str = "herd_forming",
    quadrant: str = "Q1",
    next_action: str = "",
) -> Dict[str, Any]:
    """Build one demo ``trade_log.json`` decision row (optionally with fills)."""
    probs = action_probs or {"BUY": 0.4, "SELL": 0.2, "WAIT": 0.3, "AVOID": 0.1}
    return {
        "ticker": ticker,
        "timestamp": ago_iso(minutes_ago),
        "decision": decision,
        "score": score,
        "label": "bullish" if score > 0 else "bearish" if score < 0 else "neutral",
        "confidence": "high" if abs(score) >= 0.7 else "medium",
        "reasoning": headline[:120],
        "catalyst_type": "earnings" if "earnings" in headline.lower() else "other",
        "news_headline": headline,
        "news_source": source,
        "social_signal_level": social_level,
        "social_signal_posts": [],
        "price_at_signal": BOXL_ENTRY if ticker == "BOXL" else 1.99 if ticker == "CNTB" else BJRI_ENTRY,
        "paper_trade": True,
        "options_score": options_score,
        "options_bias": options_bias,
        "options_reasoning": options_reason,
        "executed": executed,
        "execution_fills": fills,
        "instrument": instrument_hint,
        "instrument_hint": instrument_hint,
        "action_probs": probs,
        "lean": lean,
        "lean_pct": lean_pct,
        "signal_source": signal_source,
        "herd_stage": herd_stage,
        "quadrant": quadrant,
        "relative_volume": 2.4,
        "next_action": next_action,
    }


def build_demo_portfolio(starting_cash: float, ts: str) -> Dict[str, Any]:
    """Build portfolio state using the same cash/position math as agent/portfolio.py."""
    from agent.portfolio import compute_equity, compute_unrealized, portfolio_summary

    cash = starting_cash - BJRI_QTY * BJRI_ENTRY - BOXL_QTY * BOXL_ENTRY
    positions = {
        "BOXL": {
            "qty": BOXL_QTY,
            "entry_price": BOXL_ENTRY,
            "mark_price": BOXL_MARK,
            "side": "long",
            "opened_at": ago_iso(14),
        },
        "BJRI": {
            "qty": BJRI_QTY,
            "entry_price": BJRI_ENTRY,
            "mark_price": BJRI_MARK,
            "side": "short",
            "opened_at": ago_iso(35),
        },
    }
    prices = {"BOXL": BOXL_MARK, "BJRI": BJRI_MARK}
    portfolio = {
        "starting_cash": starting_cash,
        "cash": round(cash, 2),
        "realized_pnl": 512.50,
        "positions": positions,
        "equity_history": [],
        "updated_at": ts,
    }
    summary_start = portfolio_summary(portfolio, prices)
    summary_mid = portfolio_summary(
        {**portfolio, "positions": {"BJRI": positions["BJRI"]}, "cash": round(starting_cash - BJRI_QTY * BJRI_ENTRY, 2)},
        {"BJRI": BJRI_MARK},
    )
    portfolio["equity_history"] = [
        {
            "timestamp": ago_iso(120),
            "equity": starting_cash,
            "return_pct": 0.0,
            "cash": starting_cash,
            "open_positions": 0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "note": "session_open",
        },
        {
            "timestamp": ago_iso(35),
            "equity": round(float(summary_mid["equity"]), 2),
            "return_pct": float(summary_mid["return_pct"]),
            "cash": round(starting_cash - BJRI_QTY * BJRI_ENTRY, 2),
            "open_positions": 1,
            "realized_pnl": 0.0,
            "unrealized_pnl": round(compute_unrealized(portfolio, {"BJRI": BJRI_MARK}), 2),
            "note": "execute_sell_bjri",
        },
        {
            "timestamp": ago_iso(14),
            "equity": round(float(summary_start["equity"]) - 150, 2),
            "return_pct": round((float(summary_start["equity"]) - 150 - starting_cash) / starting_cash * 100, 2),
            "cash": round(cash, 2),
            "open_positions": 2,
            "realized_pnl": 512.50,
            "unrealized_pnl": round(compute_unrealized(portfolio, prices) - 150, 2),
            "note": "execute_buy_boxl",
        },
        {
            "timestamp": ts,
            "equity": round(float(summary_start["equity"]), 2),
            "return_pct": float(summary_start["return_pct"]),
            "cash": round(cash, 2),
            "open_positions": 2,
            "realized_pnl": 512.50,
            "unrealized_pnl": round(compute_unrealized(portfolio, prices), 2),
            "note": "mark_to_market",
        },
    ]
    return portfolio, summary_start


def seed_demo_state() -> None:
    """Write frozen demo ``state/*.json`` for Streamlit demos (sets ``demo.lock``)."""
    ts = now_iso()
    settings = load_settings()
    starting_cash = float(settings.get("trading", {}).get("starting_cash", 100000))

    boxl_posts = [
        social_post(
            "$BOXL heavy premarket volume — watching for breakout above $3.60",
            ["premarket", "breakout"],
            900001,
            18,
        ),
        social_post(
            "Reverse split name $BOXL getting attention ahead of open",
            ["reverse split"],
            900002,
            25,
        ),
    ]
    cntb_posts = [
        social_post(
            "$CNTB up 4% pre market again — someone loading before the bell",
            ["premarket", "pre market"],
            900003,
            12,
        ),
    ]
    bjri_posts = [
        social_post(
            "$BJRI unusual options activity ahead of restaurant sector read-through",
            ["unusual options"],
            900004,
            40,
        ),
    ]

    watchlist_items = [
        watchlist_item("BOXL", "Boxlight Corp", 3.58, -0.05, 572672, "HIGH_ALERT", 5, boxl_posts, "ok"),
        watchlist_item("CNTB", "Connect Biopharma Holdings Ltd", 1.99, -0.5, 1247008, "HIGH_ALERT", 4, cntb_posts, "ok"),
        watchlist_item("BJRI", "BJ's Restaurant Inc", 54.72, 0.31, 1234753, "WATCH", 2, bjri_posts, "ok"),
        watchlist_item("ALRS", "Alerus Financial Corp", 29.76, 0.27, 269484, "IGNORE", 0, [], "no_recent_posts"),
        watchlist_item("APC", "ARKO Petroleum Corp", 18.48, 0.49, 359480, "IGNORE", 0, [], "no_recent_posts"),
        watchlist_item("CCRN", "Cross Country Healthcares Inc", 13.17, 0.0, 1245270, "IGNORE", 0, [], "no_recent_posts"),
        watchlist_item("MPTI", "M-tron Industries Inc", 95.46, -0.5, 218058, "IGNORE", 0, [], "no_keywords_matched"),
        watchlist_item("SBET", "Sharplink Inc", 5.31, 0.38, 12512397, "IGNORE", 0, [], "no_keywords_matched"),
    ]
    high_alert_items = []
    for item in watchlist_items:
        if item["social_signal_level"] == "HIGH_ALERT":
            alert = dict(item)
            alert["first_alert_at"] = ago_iso(20)
            high_alert_items.append(alert)

    save_json(
        STATE_DIR / "watchlist.json",
        {"meta": {"cycle_id": 42, "updated_at": ts, "source_pid": 0, "demo": True}, "items": watchlist_items},
    )
    save_json(
        STATE_DIR / "high_alert.json",
        {
            "meta": {"cycle_id": 42, "updated_at": ts, "source_pid": 0, "ttl_seconds": 600, "demo": True},
            "items": high_alert_items,
        },
    )

    trade_log = [
        trade_entry(
            "BOXL",
            "BUY",
            0.82,
            "Boxlight announces strategic partnership driving premarket momentum",
            "Reuters",
            "HIGH_ALERT",
            74.2,
            "bullish",
            "Options confirmed BUY: call volume share elevated, net delta OI positive",
            True,
            [
                {
                    "timestamp": ago_iso(14),
                    "ticker": "BOXL",
                    "action": "open",
                    "side": "long",
                    "qty": BOXL_QTY,
                    "price": BOXL_ENTRY,
                    "realized_pnl": 0.0,
                    "reason": "BUY signal: Boxlight announces strategic partnership",
                }
            ],
            14,
            action_probs={"BUY": 0.62, "SELL": 0.08, "WAIT": 0.22, "AVOID": 0.08},
            lean="BUY",
            lean_pct=62,
            instrument_hint="call",
            signal_source="both",
            herd_stage="herd_forming",
            quadrant="Q1",
            next_action="If price holds above $3.50 into Friday expiry, bias remains bullish on calls.",
        ),
        trade_entry(
            "CNTB",
            "REVIEW",
            0.78,
            "Connect Biopharma reports positive trial update",
            "GlobeNewswire",
            "HIGH_ALERT",
            32.5,
            "bearish",
            "News BUY blocked: options bearish (put/call volume ratio elevated) | Lean BUY 48% (BUY 48% / SELL 22% / WAIT 22% / AVOID 8%)",
            False,
            [],
            22,
            action_probs={"BUY": 0.48, "SELL": 0.22, "WAIT": 0.22, "AVOID": 0.08},
            lean="BUY",
            lean_pct=48,
            instrument_hint="stock",
            signal_source="news",
            herd_stage="herd_forming",
            quadrant="Q1",
            next_action="Herd is bullish but options disagree — wait for options bias to flip or skip.",
        ),
        trade_entry(
            "BJRI",
            "SELL",
            -0.71,
            "BJ's Restaurant guidance cut after soft traffic data",
            "Bloomberg",
            "WATCH",
            28.4,
            "bearish",
            "Options confirmed SELL: bearish put skew and rising put OI",
            True,
            [
                {
                    "timestamp": ago_iso(35),
                    "ticker": "BJRI",
                    "action": "open",
                    "side": "short",
                    "qty": abs(BJRI_QTY),
                    "price": BJRI_ENTRY,
                    "realized_pnl": 0.0,
                    "reason": "SELL signal: guidance cut after soft traffic data",
                }
            ],
            35,
            action_probs={"BUY": 0.10, "SELL": 0.58, "WAIT": 0.24, "AVOID": 0.08},
            lean="SELL",
            lean_pct=58,
            instrument_hint="put",
            signal_source="news",
            herd_stage="whispers",
            quadrant="Q3",
            next_action="If price fails to reclaim $55 into Thursday expiry, put bias remains.",
        ),
        trade_entry(
            "SPY",
            "BUY",
            0.0,
            "Path B 0DTE options scan",
            "expiry_screener",
            "IGNORE",
            78.0,
            "bullish",
            "Path B override: expiry bullish+urgent (score=78.0, urgency=72) | 0DTE ATM call",
            True,
            [
                {
                    "timestamp": ago_iso(45),
                    "ticker": "SPY",
                    "instrument_type": "option",
                    "contract_symbol": "SPY0DTECALL",
                    "action": "open",
                    "side": "call",
                    "contracts": 2,
                    "price": 1.25,
                    "realized_pnl": 0.0,
                    "reason": "options_buy 0DTE",
                },
                {
                    "timestamp": ago_iso(10),
                    "ticker": "SPY",
                    "instrument_type": "option",
                    "contract_symbol": "SPY0DTECALL",
                    "action": "close",
                    "side": "call",
                    "contracts": 2,
                    "price": 1.75,
                    "realized_pnl": 100.0,
                    "reason": "take_profit",
                },
            ],
            10,
            action_probs={"BUY": 0.58, "SELL": 0.08, "WAIT": 0.24, "AVOID": 0.10},
            lean="BUY",
            lean_pct=58,
            instrument_hint="call",
            signal_source="expiry",
            herd_stage="coiled",
            quadrant="Q1",
            next_action="0DTE call hit +40% take-profit — flat before EOD.",
        ),
    ]
    save_json(STATE_DIR / "trade_log.json", trade_log)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    save_json(
        STATE_DIR / "expiry_watchlist.json",
        {
            "updated_at": ts,
            "count": 2,
            "items": [
                {
                    "ticker": "SPY",
                    "source": "expiry",
                    "current_price": 560.0,
                    "relative_volume": 2.1,
                    "volume": 45000000,
                    "nearest_dte": 0,
                    "max_oi_strike": 560.0,
                    "max_oi_strike_pct_from_spot": 0.0,
                    "total_oi": 520000,
                    "volume_oi_spike": 2.8,
                    "scanned_at": ts,
                    "expiration": today,
                },
                {
                    "ticker": "QQQ",
                    "source": "expiry",
                    "current_price": 480.0,
                    "relative_volume": 1.8,
                    "volume": 32000000,
                    "nearest_dte": 0,
                    "max_oi_strike": 480.0,
                    "max_oi_strike_pct_from_spot": 0.0,
                    "total_oi": 410000,
                    "volume_oi_spike": 2.1,
                    "scanned_at": ts,
                    "expiration": today,
                },
            ],
        },
    )
    save_json(
        STATE_DIR / "quadrant_candidates.json",
        {
            "updated_at": ts,
            "items": [
                {
                    "ticker": "BOXL",
                    "source": "both",
                    "x_bias": 0.72,
                    "y_urgency": 78,
                    "herd_stage": "herd_forming",
                    "quadrant": "Q1",
                    "rel_volume": 2.8,
                    "social_score": 5,
                    "dte": 5,
                    "total_oi": 12000,
                    "decision_hint": "BUY",
                },
                {
                    "ticker": "CNTB",
                    "source": "news",
                    "x_bias": 0.25,
                    "y_urgency": 70,
                    "herd_stage": "herd_forming",
                    "quadrant": "Q1",
                    "rel_volume": 3.1,
                    "social_score": 4,
                    "dte": None,
                    "total_oi": 4000,
                    "decision_hint": "REVIEW",
                },
                {
                    "ticker": "BJRI",
                    "source": "news",
                    "x_bias": -0.55,
                    "y_urgency": 42,
                    "herd_stage": "whispers",
                    "quadrant": "Q2",
                    "rel_volume": 1.7,
                    "social_score": 2,
                    "dte": 3,
                    "total_oi": 18000,
                    "decision_hint": "SELL",
                },
                {
                    "ticker": "SPY",
                    "source": "expiry",
                    "x_bias": 0.56,
                    "y_urgency": 72,
                    "herd_stage": "coiled",
                    "quadrant": "Q1",
                    "rel_volume": 2.1,
                    "social_score": 0,
                    "dte": 0,
                    "total_oi": 520000,
                    "decision_hint": "BUY",
                },
            ],
        },
    )
    save_json(STATE_DIR / "pending_reviews.json", [])

    portfolio, portfolio_summary_data = build_demo_portfolio(starting_cash, ts)
    save_json(STATE_DIR / "portfolio.json", portfolio)

    executions = [
        {
            "timestamp": ago_iso(45),
            "ticker": "SPY",
            "instrument_type": "option",
            "contract_symbol": "SPY0DTECALL",
            "action": "open",
            "side": "call",
            "contracts": 2,
            "price": 1.25,
            "realized_pnl": 0.0,
            "reason": "options_buy 0DTE",
        },
        {
            "timestamp": ago_iso(35),
            "ticker": "BJRI",
            "action": "open",
            "side": "short",
            "qty": abs(BJRI_QTY),
            "price": BJRI_ENTRY,
            "realized_pnl": 0.0,
            "reason": "SELL signal: guidance cut after soft traffic data",
        },
        {
            "timestamp": ago_iso(14),
            "ticker": "BOXL",
            "action": "open",
            "side": "long",
            "qty": BOXL_QTY,
            "price": BOXL_ENTRY,
            "realized_pnl": 0.0,
            "reason": "BUY signal: Boxlight announces strategic partnership",
        },
        {
            "timestamp": ago_iso(10),
            "ticker": "SPY",
            "instrument_type": "option",
            "contract_symbol": "SPY0DTECALL",
            "action": "close",
            "side": "call",
            "contracts": 2,
            "price": 1.75,
            "realized_pnl": 100.0,
            "reason": "take_profit",
        },
    ]
    save_json(STATE_DIR / "executions.json", executions)

    save_json(
        STATE_DIR / "health.json",
        {
            "cycle_id": 42,
            "updated_at": ts,
            "source_pid": 0,
            "watchlist_count": len(watchlist_items),
            "high_alert_count": len(high_alert_items),
            "social_reason_counts": {"ok": 3, "no_recent_posts": 3, "no_keywords_matched": 2},
            "social_posts_fetched_total": 240,
            "social_posts_recent_total": 48,
            "social_posts_matched_total": 4,
            "cooldown_skips": 0,
            "scan_skipped_due_to_overlap": False,
            "state_write_status": "ok",
            "zero_reason": "",
            "demo_mode": True,
            "timing": {
                "cycle_total_seconds": 1.85,
                "finviz_seconds": 0.28,
                "social_seconds": 1.42,
            },
            "finviz_provider": "scraper",
            "finviz_ok": True,
            "portfolio": portfolio_summary_data,
        },
    )

    options_state = options_state_dir(settings)
    options_signals = [
        options_signal(
            "BOXL",
            74.2,
            "bullish",
            3.58,
            bullish_features(),
            "BOXL: score=74.2, bias=bullish — elevated call volume, positive net delta OI",
        ),
        options_signal(
            "CNTB",
            32.5,
            "bearish",
            1.99,
            bearish_features(),
            "CNTB: score=32.5, bias=bearish — put/call volume ratio elevated, negative net delta OI",
        ),
        options_signal(
            "BJRI",
            28.4,
            "bearish",
            54.72,
            bearish_features(),
            "BJRI: score=28.4, bias=bearish — put skew and rising put OI confirm sell bias",
        ),
    ]
    save_json(
        options_state / "signals.json",
        {"meta": {"updated_at": ts, "count": len(options_signals), "demo": True}, "items": options_signals},
    )
    save_json(
        options_state / "health.json",
        {
            "updated_at": ts,
            "status": "ok",
            "demo": True,
            "tickers_scored": len(options_signals),
            "last_error": "",
        },
    )

    DEMO_LOCK_PATH.write_text(
        f"demo_mode=true\nseeded_at={ts}\nRemove this file (or run scripts/exit_demo.sh) to resume live agent.\n",
        encoding="utf-8",
    )

    return_pct = float(portfolio_summary_data.get("return_pct", 0))
    print("Demo state seeded successfully.")
    print(f"  Watchlist: {len(watchlist_items)} tickers ({len(high_alert_items)} high alert)")
    print(f"  Trade log: {len(trade_log)} signals (BUY executed, REVIEW blocked, SELL executed)")
    print(f"  Portfolio: 2 open positions, {return_pct:+.2f}% return")
    print("")
    print("DEMO MODE ON - do NOT run main.py (it is blocked while demo.lock exists).")
    print("")
    print("Open the dashboard:")
    print("  ./venv/bin/python -m streamlit run dashboard/app.py")
    print("")
    print("Meeting walkthrough (3 min):")
    print("  1. Overview -> pipeline metrics")
    print("  2. High Alert -> BOXL/CNTB social buzz")
    print("  3. Live Signals -> BUY confirmed, REVIEW with lean %, SELL confirmed")
    print("  4. Decision Quadrant -> bias vs herd urgency (Path A + Path B)")
    print("  5. Options Confirmation -> feature breakdown bars")
    print("  6. Paper Portfolio -> auto-executed positions + equity curve")
    print("  7. 0DTE -> SPY same-day call open -> take-profit close (+$100)")
    print("")
    print("After meeting: ./scripts/exit_demo.sh to resume live mode")
    print("")
    print("For a clean 0DTE-only win demo: python scripts/seed_demo_state.py --0dte")


def seed_0dte_win_demo() -> None:
    """Seed a completed same-day 0DTE call round-trip (professor weekend fallback)."""
    from agent.portfolio import OPTION_MULTIPLIER, default_portfolio, portfolio_summary

    ts = now_iso()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    settings = load_settings()
    starting_cash = float(settings.get("trading", {}).get("starting_cash", 100000))

    entry_premium = 1.25
    exit_premium = round(entry_premium * 1.40, 4)  # +40% take-profit
    contracts = 3
    cost = contracts * entry_premium * OPTION_MULTIPLIER
    proceeds = contracts * exit_premium * OPTION_MULTIPLIER
    realized = proceeds - cost  # 3 * 0.50 * 100 = 150

    DEMO_LOCK_PATH.write_text(
        f"demo_mode=true\nseeded_at={ts}\nmode=0dte_win\nRemove this file to resume live agent.\n",
        encoding="utf-8",
    )

    save_json(STATE_DIR / "watchlist.json", {"updated_at": ts, "items": []})
    save_json(STATE_DIR / "high_alert.json", {"updated_at": ts, "items": []})
    save_json(
        STATE_DIR / "expiry_watchlist.json",
        {
            "updated_at": ts,
            "count": 1,
            "items": [
                {
                    "ticker": "SPY",
                    "source": "expiry",
                    "current_price": 560.0,
                    "relative_volume": 2.4,
                    "nearest_dte": 0,
                    "total_oi": 520000,
                    "volume_oi_spike": 3.0,
                    "expiration": today,
                    "scanned_at": ts,
                }
            ],
        },
    )
    save_json(
        STATE_DIR / "quadrant_candidates.json",
        {
            "updated_at": ts,
            "items": [
                {
                    "ticker": "SPY",
                    "source": "expiry",
                    "x_bias": 0.6,
                    "y_urgency": 72,
                    "herd_stage": "coiled",
                    "quadrant": "Q1",
                    "dte": 0,
                    "decision_hint": "BUY",
                }
            ],
        },
    )

    trade_log = [
        trade_entry(
            "SPY",
            "BUY",
            0.0,
            "Path B 0DTE bullish flow",
            "expiry_screener",
            "IGNORE",
            80.0,
            "bullish",
            "Path B override: expiry bullish+urgent | opened 0DTE ATM call",
            True,
            [
                {
                    "timestamp": ago_iso(40),
                    "ticker": "SPY",
                    "instrument_type": "option",
                    "contract_symbol": f"SPY{today.replace('-', '')}C00560000",
                    "action": "open",
                    "side": "call",
                    "contracts": contracts,
                    "price": entry_premium,
                    "realized_pnl": 0.0,
                    "reason": "options_buy",
                },
                {
                    "timestamp": ago_iso(5),
                    "ticker": "SPY",
                    "instrument_type": "option",
                    "contract_symbol": f"SPY{today.replace('-', '')}C00560000",
                    "action": "close",
                    "side": "call",
                    "contracts": contracts,
                    "price": exit_premium,
                    "realized_pnl": realized,
                    "reason": "take_profit",
                },
            ],
            5,
            action_probs={"BUY": 0.62, "SELL": 0.08, "WAIT": 0.20, "AVOID": 0.10},
            lean="BUY",
            lean_pct=62,
            instrument_hint="call",
            signal_source="expiry",
            herd_stage="coiled",
            quadrant="Q1",
            next_action="Take-profit hit (+40% premium). Flat before EOD flatten.",
        )
    ]
    save_json(STATE_DIR / "trade_log.json", trade_log)
    save_json(STATE_DIR / "pending_reviews.json", [])

    portfolio = default_portfolio(starting_cash)
    portfolio["cash"] = starting_cash + realized
    portfolio["realized_pnl"] = realized
    portfolio["positions"] = {}
    portfolio["equity_history"] = [
        {
            "timestamp": ago_iso(60),
            "equity": starting_cash,
            "cash": starting_cash,
            "open_positions": 0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "return_pct": 0.0,
            "note": "session_open",
        },
        {
            "timestamp": ago_iso(40),
            "equity": starting_cash,
            "cash": starting_cash - cost,
            "open_positions": 1,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "return_pct": 0.0,
            "note": "execute_option_buy_SPY",
        },
        {
            "timestamp": ago_iso(5),
            "equity": starting_cash + realized,
            "cash": starting_cash + realized,
            "open_positions": 0,
            "realized_pnl": realized,
            "unrealized_pnl": 0.0,
            "return_pct": round(realized / starting_cash * 100, 3),
            "note": "option_exit_take_profit",
        },
    ]
    portfolio["updated_at"] = ts
    save_json(STATE_DIR / "portfolio.json", portfolio)

    contract = f"SPY{today.replace('-', '')}C00560000"
    save_json(
        STATE_DIR / "executions.json",
        [
            {
                "timestamp": ago_iso(40),
                "ticker": "SPY",
                "instrument_type": "option",
                "contract_symbol": contract,
                "action": "open",
                "side": "call",
                "contracts": contracts,
                "price": entry_premium,
                "realized_pnl": 0.0,
                "reason": "options_buy",
            },
            {
                "timestamp": ago_iso(5),
                "ticker": "SPY",
                "instrument_type": "option",
                "contract_symbol": contract,
                "action": "close",
                "side": "call",
                "contracts": contracts,
                "price": exit_premium,
                "realized_pnl": realized,
                "reason": "take_profit",
            },
        ],
    )

    summary = portfolio_summary(portfolio, {})
    save_json(
        STATE_DIR / "health.json",
        {
            "cycle_id": 1,
            "updated_at": ts,
            "demo_mode": True,
            "demo_0dte": True,
            "state_write_status": "ok",
            "portfolio": summary,
        },
    )

    print("0DTE win demo seeded successfully.")
    print(f"  SPY 0DTE call: open @ ${entry_premium:.2f} -> take_profit @ ${exit_premium:.2f}")
    print(f"  Realized P&L: ${realized:+.2f} (flat before EOD)")
    print(f"  Expiration: {today} (nearest_dte=0)")
    print("")
    print("Open the dashboard:")
    print("  ./venv/bin/python -m streamlit run dashboard/app.py")


if __name__ == "__main__":
    if "--0dte" in sys.argv:
        seed_0dte_win_demo()
    else:
        seed_demo_state()
