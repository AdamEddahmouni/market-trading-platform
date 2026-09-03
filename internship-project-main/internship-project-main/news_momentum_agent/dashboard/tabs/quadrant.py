"""Decision quadrant — view-only (no execute / approve buttons)."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components.badges import decision_badge, headline_display, path_badges_inline, render_html
from dashboard.components.empty import empty_state, stale_banner
from dashboard.data import paths as P
from dashboard.data.loaders import load_items_file, load_json
from dashboard.theme import DECISION_COLORS, plotly_layout


def render(settings: Dict[str, Any]) -> None:
    st.info(
        "View-only — Telegram remains the approval path. "
        "This dashboard does not execute paper trades or mutate pending reviews."
    )
    quad = load_items_file(P.QUADRANT_PATH)
    pending = load_json(P.PENDING_REVIEWS_PATH, {})
    trade = load_items_file(P.TRADE_LOG_PATH)
    stale_banner(quad.get("age_sec"), threshold_sec=300, label="quadrant_candidates")

    # Pending reviews (read-only list)
    st.subheader("Pending reviews")
    pdata = pending.get("data")
    pending_items: List[Dict[str, Any]] = []
    if isinstance(pdata, dict):
        raw = pdata.get("items")
        if isinstance(raw, list):
            pending_items = [x for x in raw if isinstance(x, dict)]
        else:
            pending_items = [v for v in pdata.values() if isinstance(v, dict) and v.get("ticker")]
    elif isinstance(pdata, list):
        pending_items = [x for x in pdata if isinstance(x, dict)]

    open_pending = [
        p
        for p in pending_items
        if str(p.get("status") or "").lower() in {"", "pending", "open", "waiting"}
        or p.get("status") is None
    ]
    # also show recently resolved for context
    if not open_pending:
        empty_state("No open pending reviews", "Approvals happen in Telegram.")
    else:
        for p in open_pending[:20]:
            render_html(
                decision_badge(p.get("decision"))
                + " "
                + path_badges_inline(p.get("signal_source"), settings)
                + f" <strong>{p.get('ticker')}</strong> status={p.get('status')}"
            )
            st.caption(str(p.get("reasoning") or p.get("why") or "")[:200])

    # Scatter from quadrant candidates or trade log REVIEW leans
    items: List[Dict[str, Any]] = list(quad.get("items") or [])
    if not items:
        items = [
            r
            for r in (trade.get("items") or [])
            if str(r.get("decision") or "").upper() in {"BUY", "SELL", "REVIEW"}
        ][-80:]

    if not items:
        empty_state("No quadrant / actionable points to plot")
        return

    rows = []
    for r in items:
        rows.append(
            {
                "ticker": r.get("ticker"),
                "decision": str(r.get("decision") or "REVIEW").upper(),
                "herd_urgency": float(r.get("herd_urgency") or r.get("urgency") or 0),
                "options_score": float(r.get("options_score") or 50),
                "lean_pct": r.get("lean_pct"),
                "signal_source": r.get("signal_source"),
            }
        )
    df = pd.DataFrame(rows)
    fig = px.scatter(
        df,
        x="options_score",
        y="herd_urgency",
        color="decision",
        hover_data=["ticker", "lean_pct", "signal_source"],
        color_discrete_map=DECISION_COLORS,
    )
    fig.update_layout(**plotly_layout(title="Options score vs herd urgency", height=420))
    st.plotly_chart(fig, use_container_width=True)
