"""Always-on header: verdict, summary strip, horizon, gate chips."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from dashboard.components.empty import stale_banner
from dashboard.data import paths as P
from dashboard.data.loaders import (
    freshness_text,
    gate_flags,
    horizon_explainer,
    load_agent_pid,
    load_items_file,
    load_json,
    load_latest_eod,
)


def _metric_card(label: str, value: str, sub: str = "") -> str:
    sub_html = f"<div class='sub'>{sub}</div>" if sub else ""
    return (
        f"<div class='dash-card'><div class='label'>{label}</div>"
        f"<div class='value'>{value}</div>{sub_html}</div>"
    )


def render_header(settings: Dict[str, Any]) -> None:
    """Tier 0–2 chrome above tabs."""
    health_env = load_json(P.HEALTH_PATH, {})
    health = health_env["data"] if isinstance(health_env.get("data"), dict) else {}
    eod_env = load_latest_eod()
    eod = eod_env["data"] if isinstance(eod_env.get("data"), dict) else {}
    pid_env = load_agent_pid()
    pid_data = pid_env.get("data") or {}
    running = bool(pid_data.get("running"))
    watch = load_items_file(P.WATCHLIST_PATH)
    trade = load_items_file(P.TRADE_LOG_PATH)
    portfolio_env = load_json(P.PORTFOLIO_PATH, {})
    portfolio = portfolio_env["data"] if isinstance(portfolio_env.get("data"), dict) else {}

    # --- Tier 0: verdict / critical alerts ---
    if P.DEMO_LOCK_PATH.exists() or health.get("demo_mode"):
        st.info("**Demo mode** — frozen replay state (`demo.lock`). Agent may not overwrite live files.")

    if eod_env["ok"] and eod:
        clean = bool(eod.get("clean"))
        headline = str(eod.get("headline") or "EOD summary available")
        cls = "verdict-clean" if clean else "verdict-dirty"
        day = eod.get("session_date") or ""
        st.markdown(
            f"<div class='verdict-bar {cls}'>EOD {day}: {headline}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<div class='verdict-bar verdict-missing'>No EOD summary for a completed session yet "
            "(file appears after the agent writes eod_summary_*.json).</div>",
            unsafe_allow_html=True,
        )

    if not running:
        st.error(
            f"Agent process not detected (pid file: {pid_data.get('pid') or 'missing'}). "
            "Dashboard is read-only — start `main.py` separately if needed."
        )

    stale_banner(health_env.get("age_sec"), threshold_sec=180, label="health.json")

    # --- Tier 1: summary strip ---
    horizon = horizon_explainer(settings)
    st.markdown(
        f"<div class='horizon-box'><div class='mode'>{horizon['mode'].upper()}</div>"
        f"<div style='color:#8B9BB0;margin-top:0.25rem'>{horizon['detail']}</div></div>",
        unsafe_allow_html=True,
    )

    positions = portfolio.get("positions") or {}
    n_pos = len(positions) if isinstance(positions, dict) else 0
    realized = portfolio.get("realized_pnl")
    try:
        realized_s = f"${float(realized):,.0f}"
    except Exception:
        realized_s = "—"

    opens = eod.get("opens") if eod_env["ok"] else "—"
    closes = eod.get("closes") if eod_env["ok"] else "—"

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.markdown(
            _metric_card(
                "Agent",
                "RUNNING" if running else "STOPPED",
                f"pid {pid_data.get('pid') or '—'}",
            ),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            _metric_card("State age", freshness_text(health_env.get("age_sec")), "health.json"),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            _metric_card("Horizon", horizon["mode"], horizon["raw"]),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            _metric_card("Open positions", str(n_pos), f"realized {realized_s}"),
            unsafe_allow_html=True,
        )
    with c5:
        st.markdown(
            _metric_card("EOD opens/closes", f"{opens} / {closes}", str(eod.get("session_date") or "—")),
            unsafe_allow_html=True,
        )
    with c6:
        st.markdown(
            _metric_card(
                "Watchlist",
                str(len(watch.get("items") or [])),
                f"log rows {len(trade.get('items') or [])}",
            ),
            unsafe_allow_html=True,
        )

    # --- Tier 2: gate chips ---
    chips: List[str] = []
    for g in gate_flags(settings):
        if g["key"] in {"instrument", "auto_execute"}:
            val = g.get("value", "")
            chips.append(f"<span class='gate-chip gate-on'>{g['key']}={val}</span>")
        else:
            cls = "gate-on" if g["on"] else "gate-off"
            chips.append(f"<span class='gate-chip {cls}'>{g['key']}={'on' if g['on'] else 'off'}</span>")
    st.markdown("".join(chips), unsafe_allow_html=True)

    # Watchlist empty soft alert
    zero_reason = str(health.get("zero_reason") or "")
    if len(watch.get("items") or []) == 0 and zero_reason:
        st.warning(f"Watchlist empty: {zero_reason}")
