"""Options confirmation tab — engine signals (read-only)."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components.empty import empty_state, stale_banner
from dashboard.data.loaders import load_options_health, load_options_signals
from dashboard.theme import BIAS_COLORS, COLORS, plotly_layout

OPTIONS_FEATURE_HELP = {
    "call_volume_share": ("Call volume share", "Higher = more call buying"),
    "put_call_volume_ratio": ("Put/call volume", "Lower = more calls vs puts"),
    "put_call_oi_ratio": ("Put/call OI", "Lower = more call OI"),
    "net_delta_oi": ("Net delta OI", "Positive = bullish OI tilt"),
    "iv_skew": ("IV skew", "Negative = calls bid vs puts"),
}


def _bullish_score(name: str, value: float) -> float:
    if name == "call_volume_share":
        return max(0.0, min(1.0, value))
    if name == "put_call_volume_ratio":
        return max(0.0, min(1.0, 0.5 + (0.9 - value) * 0.6))
    if name == "put_call_oi_ratio":
        return max(0.0, min(1.0, 0.5 + (1.0 - value) * 0.5))
    if name == "net_delta_oi":
        return max(0.0, min(1.0, 0.5 + value * 1.5))
    if name == "iv_skew":
        return max(0.0, min(1.0, 0.5 - value / 0.08))
    return 0.5


def render(settings: Dict[str, Any]) -> None:
    sig = load_options_signals(settings)
    health = load_options_health(settings)
    stale_banner(sig.get("age_sec"), threshold_sec=300, label="options signals")

    hdata = health["data"] if health["ok"] and isinstance(health.get("data"), dict) else {}
    if hdata:
        st.caption(
            f"Engine health: ok={hdata.get('ok', hdata.get('healthy', '—'))} "
            f"updated={health.get('updated_at')}"
        )

    items: List[Dict[str, Any]] = list(sig.get("items") or [])
    if not items:
        empty_state("No options confirmation signals", "Check options_confirmation.engine_path and engine state/signals.json")
        return

    rows = []
    for r in items:
        rows.append(
            {
                "ticker": r.get("ticker"),
                "options_score": r.get("options_score"),
                "options_bias": r.get("options_bias"),
                "spot": r.get("spot_price"),
                "as_of": r.get("as_of"),
                "summary": str(r.get("reasoning_summary") or "")[:100],
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if "options_bias" in df.columns:
        counts = df["options_bias"].fillna("no_data").value_counts().reset_index()
        counts.columns = ["bias", "count"]
        fig = px.bar(counts, x="bias", y="count", color="bias", color_discrete_map=BIAS_COLORS)
        fig.update_layout(**plotly_layout(title="Options bias mix", height=280, showlegend=False))
        st.plotly_chart(fig, use_container_width=True)

    pick = st.selectbox("Feature breakdown", options=[r.get("ticker") for r in items if r.get("ticker")])
    chosen = next((r for r in items if r.get("ticker") == pick), None)
    if chosen and isinstance(chosen.get("feature_values"), dict):
        feats = chosen["feature_values"]
        brow = []
        for key in OPTIONS_FEATURE_HELP:
            if key not in feats:
                continue
            val = float(feats[key])
            bull = _bullish_score(key, val)
            label, _ = OPTIONS_FEATURE_HELP[key]
            brow.append({"Signal": label, "Value": round(val, 4), "Bullish %": int(bull * 100)})
        if brow:
            st.dataframe(pd.DataFrame(brow), use_container_width=True, hide_index=True)
            for row in brow:
                st.progress(row["Bullish %"] / 100.0, text=f"{row['Signal']}: {row['Bullish %']}%")
