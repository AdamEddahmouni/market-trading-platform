"""News momentum + options research dashboard (read-only toward the agent).

Run: ``streamlit run dashboard/app.py`` from ``news_momentum_agent/``.

Reads ``state/*.json`` and ``settings.json``. Does not run the agent, does not
approve trades, and does not write portfolio/pending state.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.components.header import render_header
from dashboard.data.loaders import clear_loader_cache, load_settings
from dashboard.tabs import (
    diagnostics,
    discovery,
    options,
    overview,
    portfolio,
    quadrant,
    research,
    screener,
    trade_log,
)
from dashboard.theme import inject_css


def _sidebar(settings: dict) -> int:
    st.sidebar.markdown("### Agent config (read-only)")
    trading = settings.get("trading") or {}
    execution = settings.get("execution") or {}
    oc = settings.get("options_confirmation") or {}
    screener_cfg = settings.get("screener") or {}
    alpaca = settings.get("alpaca") or {}

    st.sidebar.write(f"**instrument:** `{trading.get('instrument')}`")
    st.sidebar.write(f"**auto_execute:** `{trading.get('auto_execute')}`")
    st.sidebar.write(f"**horizon:** `{trading.get('options_expiry_horizon')}`")
    st.sidebar.write(f"**dte_range:** `{trading.get('options_dte_range')}`")
    st.sidebar.write(f"**options_confirmation:** `{oc.get('enabled')}`")
    st.sidebar.write(f"**offline_mode:** `{oc.get('offline_mode')}`")
    st.sidebar.write(f"**screener.provider:** `{screener_cfg.get('provider')}`")
    st.sidebar.write(f"**starting_cash:** `{trading.get('starting_cash')}`")
    st.sidebar.write(f"**alpaca.enabled:** `{alpaca.get('enabled')}`")
    st.sidebar.write(f"**path_b_auto_execute:** `{execution.get('path_b_auto_execute')}`")
    st.sidebar.write(f"**path_a2_auto_execute:** `{execution.get('path_a2_auto_execute')}`")
    st.sidebar.caption("These mirror settings.json — changing them here is not supported. Edit settings and restart the agent.")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Dashboard")
    if "dashboard_refresh" not in st.session_state:
        st.session_state["dashboard_refresh"] = 30
    refresh = st.sidebar.selectbox(
        "Auto-refresh (seconds)",
        options=[0, 15, 30, 60],
        index=[0, 15, 30, 60].index(st.session_state["dashboard_refresh"])
        if st.session_state["dashboard_refresh"] in {0, 15, 30, 60}
        else 2,
    )
    st.session_state["dashboard_refresh"] = refresh
    if st.sidebar.button("Refresh now"):
        clear_loader_cache()
        st.rerun()
    return int(refresh)


def _auto_refresh(seconds: int) -> None:
    if seconds > 0:
        components.html(
            f"<script>setTimeout(function(){{window.parent.location.reload();}}, {seconds * 1000});</script>",
            height=0,
        )


def main() -> None:
    st.set_page_config(
        page_title="Momentum + Options Monitor",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(inject_css(), unsafe_allow_html=True)

    settings = load_settings()
    refresh = _sidebar(settings)

    st.title("Momentum + Options Monitor")
    st.caption("Read-only research dashboard — watches agent `state/`; does not trade.")

    render_header(settings)

    tabs = st.tabs(
        [
            "Overview",
            "Portfolio",
            "Discovery",
            "Trade Log",
            "Diagnostics",
            "Research",
            "Options",
            "Near-Expiry",
            "Quadrant",
        ]
    )
    with tabs[0]:
        overview.render(settings)
    with tabs[1]:
        portfolio.render(settings)
    with tabs[2]:
        discovery.render(settings)
    with tabs[3]:
        trade_log.render(settings)
    with tabs[4]:
        diagnostics.render(settings)
    with tabs[5]:
        research.render(settings)
    with tabs[6]:
        options.render(settings)
    with tabs[7]:
        screener.render(settings)
    with tabs[8]:
        quadrant.render(settings)

    _auto_refresh(refresh)


if __name__ == "__main__":
    main()
