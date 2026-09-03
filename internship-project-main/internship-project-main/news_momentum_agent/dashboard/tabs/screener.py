"""Near-expiry screener tab (odte_watchlist.json) — horizon-aware labeling."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from dashboard.components.empty import empty_state, stale_banner
from dashboard.data import paths as P
from dashboard.data.loaders import horizon_explainer, load_items_file


def render(settings: Dict[str, Any]) -> None:
    horizon = horizon_explainer(settings)
    st.markdown(
        f"<div class='horizon-box'><div class='mode'>Near-expiry screener</div>"
        f"<div style='color:#8B9BB0;margin-top:0.25rem'>Agent horizon: <strong>{horizon['mode']}</strong> — "
        f"{horizon['detail']}</div></div>",
        unsafe_allow_html=True,
    )
    st.caption("Data from `odte_watchlist.json` (setup-quality prefilter). Name kept for compatibility; not 0DTE-only when horizon is range/deadline.")

    env = load_items_file(P.ODTE_WATCHLIST_PATH)
    stale_banner(env.get("age_sec"), threshold_sec=600, label="odte_watchlist")
    items: List[Dict[str, Any]] = list(env.get("items") or [])
    if not items:
        empty_state("Near-expiry watchlist empty")
        return

    st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True, height=420)
