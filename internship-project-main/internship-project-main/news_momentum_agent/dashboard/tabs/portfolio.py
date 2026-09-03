"""Paper Portfolio tab — positions, executions with hold time, equity curve."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components.empty import empty_state, missing_file, stale_banner
from dashboard.data import paths as P
from dashboard.data.loaders import load_json
from dashboard.theme import COLORS, plotly_layout


def _parse(ts: Any) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _hold_pairs(executions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Match open→close by ticker/contract for hold seconds."""
    opens: Dict[str, Dict[str, Any]] = {}
    out: List[Dict[str, Any]] = []
    for ex in sorted(executions, key=lambda r: str(r.get("timestamp") or "")):
        if not isinstance(ex, dict):
            continue
        key = str(ex.get("contract_symbol") or ex.get("ticker") or "")
        action = str(ex.get("action") or "").lower()
        if action == "open":
            opens[key] = ex
        elif action == "close":
            op = opens.pop(key, None)
            hold = None
            if op:
                t0, t1 = _parse(op.get("timestamp")), _parse(ex.get("timestamp"))
                if t0 and t1:
                    hold = (t1 - t0).total_seconds()
            out.append(
                {
                    "ticker": ex.get("ticker"),
                    "contract": ex.get("contract_symbol"),
                    "opened_at": (op or {}).get("timestamp"),
                    "closed_at": ex.get("timestamp"),
                    "hold_sec": round(hold, 1) if hold is not None else None,
                    "entry": (op or {}).get("price"),
                    "exit": ex.get("price"),
                    "reason": ex.get("reason"),
                    "realized_pnl": ex.get("realized_pnl"),
                    "contracts": ex.get("contracts"),
                }
            )
    return out


def render(settings: Dict[str, Any]) -> None:
    try:
        from agent.portfolio import (
            build_open_positions_table,
            load_executions,
            load_portfolio,
            portfolio_summary,
        )
    except Exception as exc:
        st.error(f"Could not import portfolio helpers: {exc}")
        return

    port_env = load_json(P.PORTFOLIO_PATH, {})
    if not port_env["ok"]:
        missing_file("portfolio.json")
        return
    stale_banner(port_env.get("age_sec"), threshold_sec=300, label="portfolio.json")

    portfolio = load_portfolio(settings)
    executions = load_executions()
    prices: Dict[str, float] = {}
    # Prefer mark_price on option positions for summary
    positions = portfolio.get("positions") or {}
    if isinstance(positions, dict):
        for sym, pos in positions.items():
            if not isinstance(pos, dict):
                continue
            und = str(pos.get("underlying") or "")
            mark = pos.get("mark_price")
            if und and mark is not None:
                prices[und] = float(mark)

    summary = portfolio_summary(portfolio, prices)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cash", f"${float(summary.get('cash') or portfolio.get('cash') or 0):,.2f}")
    c2.metric("Realized P&L", f"${float(portfolio.get('realized_pnl') or 0):,.2f}")
    c3.metric("Unrealized", f"${float(summary.get('unrealized_pnl') or 0):,.2f}")
    c4.metric("Equity", f"${float(summary.get('equity') or 0):,.2f}")

    st.subheader("Open positions")
    table = build_open_positions_table(portfolio, prices)
    if not table:
        # Fallback raw
        rows = []
        if isinstance(positions, dict):
            for sym, pos in positions.items():
                if not isinstance(pos, dict):
                    continue
                entry = float(pos.get("entry_price") or 0)
                mark = float(pos.get("mark_price") or entry)
                n = int(pos.get("contracts") or 0)
                mult = 100 if str(pos.get("instrument_type")) == "option" else 1
                rows.append(
                    {
                        "contract": sym,
                        "underlying": pos.get("underlying"),
                        "side": pos.get("side"),
                        "contracts": n,
                        "entry": entry,
                        "mark": mark,
                        "uPnL": round((mark - entry) * n * mult, 2),
                        "strike": pos.get("strike"),
                        "expiration": pos.get("expiration"),
                        "opened_at": pos.get("opened_at"),
                    }
                )
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            empty_state("No open positions")
    else:
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

    # Sanity callout for known session names
    unds = set()
    if isinstance(positions, dict):
        unds = {str(p.get("underlying") or "").upper() for p in positions.values() if isinstance(p, dict)}
    st.caption(f"Open underlyings: {', '.join(sorted(unds)) or 'none'} (expect TGB/NWL open; COIN closed).")

    st.subheader("Executions & hold times")
    if not executions:
        empty_state("No executions")
    else:
        st.dataframe(pd.DataFrame(executions), use_container_width=True, hide_index=True, height=260)
        holds = _hold_pairs([e for e in executions if isinstance(e, dict)])
        if holds:
            st.markdown("**Closed trades — hold time**")
            st.dataframe(pd.DataFrame(holds), use_container_width=True, hide_index=True)
            coin = [h for h in holds if str(h.get("ticker") or "").upper() == "COIN"]
            if coin:
                st.info(
                    f"COIN close: reason={coin[0].get('reason')}, hold_sec={coin[0].get('hold_sec')} "
                    f"(≈48s stop_loss session diagnostic)."
                )

    hist = portfolio.get("equity_history") or []
    if isinstance(hist, list) and hist:
        hdf = pd.DataFrame(hist)
        if "equity" in hdf.columns:
            xcol = "timestamp" if "timestamp" in hdf.columns else hdf.columns[0]
            fig = px.line(hdf, x=xcol, y="equity", color_discrete_sequence=[COLORS["info"]])
            fig.update_layout(**plotly_layout(title="Equity history", height=300))
            st.plotly_chart(fig, use_container_width=True)
