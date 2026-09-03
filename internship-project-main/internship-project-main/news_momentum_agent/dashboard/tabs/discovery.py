"""Discovery tab — watchlist + HIGH_ALERT with alert_reason chips."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from dashboard.components.badges import alert_reason_badges, render_html
from dashboard.components.empty import empty_state, stale_banner
from dashboard.data import paths as P
from dashboard.data.loaders import load_items_file, load_json


def render(settings: Dict[str, Any]) -> None:
    del settings
    watch = load_items_file(P.WATCHLIST_PATH)
    high = load_items_file(P.HIGH_ALERT_PATH)
    path_a = load_json(P.PATH_A_HEALTH_PATH, {})

    stale_banner(watch.get("age_sec"), threshold_sec=300, label="watchlist")
    by_path = {}
    if isinstance(high.get("meta"), dict):
        by_path = high["meta"].get("herd_alert_by_path") or {}
    if not by_path and path_a["ok"]:
        by_path = ((path_a["data"] or {}).get("last_screener") or {}).get("herd_alert_by_path") or {}

    if by_path:
        cols = st.columns(len(by_path))
        for col, (name, count) in zip(cols, by_path.items()):
            col.metric(str(name), int(count))
        st.caption("HIGH_ALERT promotion paths — current cycle")

    mode = st.radio("Show", ["All watchlist", "HIGH_ALERT only", "WATCH only"], horizontal=True)
    items: List[Dict[str, Any]] = list(watch.get("items") or [])
    if mode == "HIGH_ALERT only":
        # Prefer high_alert.json items when present
        ha_items = list(high.get("items") or [])
        items = ha_items if ha_items else [
            r for r in items if str(r.get("social_signal_level") or "").upper() == "HIGH_ALERT"
        ]
    elif mode == "WATCH only":
        items = [r for r in items if str(r.get("social_signal_level") or "").upper() == "WATCH"]

    if not items:
        empty_state("No names in this view")
        return

    # Card strip for HIGH_ALERT
    if mode != "WATCH only":
        alerts = [
            r for r in items if str(r.get("social_signal_level") or "").upper() == "HIGH_ALERT"
        ][:12]
        for r in alerts:
            reasons = r.get("alert_reason") or []
            render_html(
                f"<strong>{r.get('ticker')}</strong> "
                f"{alert_reason_badges(reasons)} "
                f"<span style='color:#8B9BB0'>{r.get('company_name') or ''}</span>"
            )
            st.caption(
                f"px={r.get('current_price')} Δ%={r.get('percent_change')} "
                f"tier={r.get('universe_tier')} rvol_pct={r.get('herd_rvol_percentile')}"
            )

    table = []
    for r in items:
        table.append(
            {
                "ticker": r.get("ticker"),
                "company": r.get("company_name"),
                "level": r.get("social_signal_level"),
                "alert_reason": ",".join(r.get("alert_reason") or [])
                if isinstance(r.get("alert_reason"), list)
                else r.get("alert_reason"),
                "pct_change": r.get("percent_change"),
                "price": r.get("current_price"),
                "rvol": r.get("relative_volume"),
                "universe_tier": r.get("universe_tier"),
                "market_cap_b": r.get("market_cap_billion"),
            }
        )
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True, height=400)
