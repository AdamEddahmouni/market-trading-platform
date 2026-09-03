"""Read-only diagnostics dashboard for options confirmation engine.

Purpose
-------
Streamlit UI over engine ``state/`` — signals, health, trade log, and local
paper portfolio. No scoring or broker actions.

Features / API role
-------------------
Displays ``signals.json``, ``health.json``, ``trade_log.json``, ``portfolio.json``,
and ``executions.json`` written by ``runner`` / ``paper_trader``.

How ``news_momentum_agent`` consumes it
---------------------------------------
Not imported by the agent. Operators may run ``streamlit run dashboard/app.py``
from ``options_confirmation_engine`` while the agent uses ``options_client`` separately.
Agent dashboard has its own options panels under ``news_momentum_agent/dashboard/``.

Options-specific vs reusable
----------------------------
Options-engine-specific metrics (bias counts, options_score table). Reusable
Streamlit state-file viewer pattern.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from options_engine.paper_trader import compute_equity
from options_engine.utils import load_json
STATE_DIR = PROJECT_ROOT / "state"
SIGNALS_PATH = STATE_DIR / "signals.json"
HEALTH_PATH = STATE_DIR / "health.json"
TRADE_LOG_PATH = STATE_DIR / "trade_log.json"
PORTFOLIO_PATH = STATE_DIR / "portfolio.json"
EXECUTIONS_PATH = STATE_DIR / "executions.json"


def _load_signals() -> List[Dict[str, Any]]:
    payload = load_json(SIGNALS_PATH, {"items": []})
    if isinstance(payload, dict):
        items = payload.get("items", [])
        return items if isinstance(items, list) else []
    return []


def _freshness_text(updated_at: str) -> str:
    """Human-readable age of the latest update."""
    try:
        ts = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        if age < 90:
            return f"{int(age)}s ago"
        if age < 5400:
            return f"{int(age / 60)}m ago"
        return f"{age / 3600:.1f}h ago"
    except Exception:
        return "unknown"


def _signal_prices(signals: List[Dict[str, Any]]) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    for item in signals:
        ticker = str(item.get("ticker", "")).upper()
        price = float(item.get("spot_price", 0.0) or 0.0)
        if ticker and price > 0:
            prices[ticker] = price
    return prices


def _render_portfolio(signals: List[Dict[str, Any]]) -> None:
    portfolio = load_json(PORTFOLIO_PATH, {})
    executions = load_json(EXECUTIONS_PATH, [])
    if not isinstance(portfolio, dict) or not portfolio:
        st.info("No paper portfolio yet. Run: python scheduler.py --once --offline")
        return

    prices = _signal_prices(signals)
    equity = compute_equity(portfolio, prices)
    starting = float(portfolio.get("starting_cash", 100000))
    cash = float(portfolio.get("cash", 0.0))
    realized = float(portfolio.get("realized_pnl", 0.0))
    positions = portfolio.get("positions", {}) if isinstance(portfolio.get("positions"), dict) else {}
    return_pct = (equity / starting - 1.0) * 100.0 if starting else 0.0

    unrealized = 0.0
    position_rows: List[Dict[str, Any]] = []
    for ticker, pos in positions.items():
        if not isinstance(pos, dict):
            continue
        qty = float(pos.get("qty", 0.0))
        entry = float(pos.get("entry_price", 0.0))
        mark = prices.get(ticker, entry)
        upnl = qty * (mark - entry)
        unrealized += upnl
        position_rows.append(
            {
                "ticker": ticker,
                "side": pos.get("side", "long" if qty > 0 else "short"),
                "qty": abs(qty),
                "entry": round(entry, 2),
                "mark": round(mark, 2),
                "unrealized_pnl": round(upnl, 2),
            }
        )

    st.subheader("Paper Portfolio (Simulated)")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Equity", f"${equity:,.0f}")
    c2.metric("Return", f"{return_pct:+.2f}%")
    c3.metric("Cash", f"${cash:,.0f}")
    c4.metric("Open positions", len(position_rows))
    c5.metric("Realized / Unrealized", f"${realized:,.0f} / ${unrealized:,.0f}")

    if position_rows:
        st.markdown("**Open Positions**")
        st.dataframe(pd.DataFrame(position_rows), width="stretch")
    else:
        st.caption("No open positions.")

    history = portfolio.get("equity_history", [])
    if isinstance(history, list) and history:
        hist_df = pd.DataFrame(history)
        if "equity" in hist_df.columns and "timestamp" in hist_df.columns:
            st.markdown("**Equity Curve**")
            chart_df = hist_df[["timestamp", "equity"]].copy()
            chart_df = chart_df.set_index("timestamp")
            st.line_chart(chart_df)

    if isinstance(executions, list) and executions:
        st.markdown("**Recent Executions**")
        exec_df = pd.DataFrame(executions[-20:])
        preferred = ["timestamp", "ticker", "action", "side", "qty", "price", "realized_pnl", "reason"]
        cols = [c for c in preferred if c in exec_df.columns] + [c for c in exec_df.columns if c not in preferred]
        st.dataframe(exec_df[cols], width="stretch")


def main() -> None:
    """Render the Streamlit dashboard (signals, health, paper portfolio)."""
    st.set_page_config(page_title="Options Confirmation Engine", layout="wide")
    st.title("Options Confirmation Engine Dashboard")

    refresh_seconds = st.sidebar.selectbox(
        "Auto-refresh", options=[0, 15, 30, 60, 300], index=2,
        format_func=lambda s: "Off" if s == 0 else f"Every {s}s",
    )
    if refresh_seconds:
        components.html(
            f"<script>setTimeout(function(){{window.parent.location.reload();}}, {refresh_seconds * 1000});</script>",
            height=0,
        )

    signals = _load_signals()
    health = load_json(HEALTH_PATH, {})
    trade_log = load_json(TRADE_LOG_PATH, [])

    signals_meta = load_json(SIGNALS_PATH, {})
    updated_at = signals_meta.get("meta", {}).get("updated_at", "") if isinstance(signals_meta, dict) else ""
    col1, col2, col3 = st.columns(3)
    col1.metric("Tickers", len(signals))
    col2.metric("Last update", _freshness_text(updated_at) if updated_at else "never")
    if isinstance(health, dict) and health.get("bias_counts"):
        col3.metric("Bullish / Bearish", f"{health['bias_counts'].get('bullish', 0)} / {health['bias_counts'].get('bearish', 0)}")

    _render_portfolio(signals)

    if isinstance(health, dict) and health:
        with st.expander("Health detail"):
            st.write(health)

    st.subheader("Latest Signals")
    if signals:
        table = pd.DataFrame(signals)
        preferred = ["ticker", "options_score", "options_bias", "spot_price", "reasoning_summary"]
        cols = [c for c in preferred if c in table.columns] + [c for c in table.columns if c not in preferred]
        table = table[cols].sort_values("options_score", ascending=False) if "options_score" in table.columns else table
        st.dataframe(table, width="stretch")
    else:
        st.info("No signals yet. Start the scheduler: python scheduler.py --once --offline")

    st.subheader("Signal History (Trade Log)")
    if isinstance(trade_log, list) and trade_log:
        st.dataframe(pd.DataFrame(trade_log).tail(50), width="stretch")
    else:
        st.info("No trade log entries yet.")


if __name__ == "__main__":
    main()
