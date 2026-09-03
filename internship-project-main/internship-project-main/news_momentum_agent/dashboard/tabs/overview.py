"""Overview tab — EOD verdict details, funnels, decision mix."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components.empty import empty_state, missing_file, stale_banner
from dashboard.data import paths as P
from dashboard.data.loaders import load_items_file, load_json, load_latest_eod, path_label
from dashboard.theme import COLORS, DECISION_COLORS, plotly_layout


def render(settings: Dict[str, Any]) -> None:
    eod_env = load_latest_eod()
    eod = eod_env["data"] if isinstance(eod_env.get("data"), dict) else {}
    path_b = load_json(P.PATH_B_HEALTH_PATH, {})
    path_a = load_json(P.PATH_A_HEALTH_PATH, {})
    trade = load_items_file(P.TRADE_LOG_PATH)
    items: List[Dict[str, Any]] = trade.get("items") or []

    stale_banner(eod_env.get("age_sec"), threshold_sec=86_400, label="Latest EOD summary")

    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Session cleanliness")
        if not eod_env["ok"]:
            missing_file("eod_summary_*.json")
        else:
            flags = eod.get("flags") if isinstance(eod.get("flags"), dict) else {}
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Opens", eod.get("opens", 0))
            c2.metric("Closes", eod.get("closes", 0))
            ht = eod.get("hold_time") or {}
            c3.metric("Median hold (s)", round(float(ht.get("median_sec") or 0), 1))
            c4.metric("Clean", "yes" if eod.get("clean") else "no")
            buckets = (ht.get("buckets") or {}) if isinstance(ht, dict) else {}
            if buckets:
                bdf = pd.DataFrame(
                    [{"bucket": k, "count": int(v)} for k, v in buckets.items()]
                )
                fig = px.bar(bdf, x="bucket", y="count", color_discrete_sequence=[COLORS["info"]])
                fig.update_layout(**plotly_layout(title="Hold-time buckets", height=280))
                st.plotly_chart(fig, use_container_width=True)
            exits = eod.get("exit_reasons") or {}
            if exits:
                rows = []
                for k, v in exits.items():
                    if isinstance(v, dict):
                        rows.append({"reason": k, "count": int(v.get("count") or 0), "pct": v.get("pct")})
                    else:
                        rows.append({"reason": k, "count": int(v), "pct": None})
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            if flags:
                st.caption("Flags: " + ", ".join(f"{k}={v}" for k, v in flags.items()))

            rej = eod.get("rejection_codes") or {}
            liq = eod.get("liquidity_reject_subreasons") or {}
            if rej:
                st.markdown("**Rejection codes (EOD)**")
                st.dataframe(
                    pd.DataFrame([{"code": k, "count": int(v)} for k, v in rej.items()]),
                    use_container_width=True,
                    hide_index=True,
                )
            if liq:
                st.markdown("**Liquidity sub-reasons (EOD)**")
                st.dataframe(
                    pd.DataFrame([{"primary": k, "count": int(v)} for k, v in liq.items()]),
                    use_container_width=True,
                    hide_index=True,
                )

    with right:
        st.subheader("Path health")
        pb = path_b["data"] if path_b["ok"] and isinstance(path_b.get("data"), dict) else {}
        pa = path_a["data"] if path_a["ok"] and isinstance(path_a.get("data"), dict) else {}
        if not path_b["ok"]:
            missing_file("path_b_universe_health.json")
        else:
            stats = pb.get("last_stats") or {}
            st.markdown(
                f"**Path B** — consecutive zero Finviz: `{pb.get('consecutive_zero_finviz', 0)}` "
                f"(alert={'ON' if pb.get('alert') else 'off'}, threshold={pb.get('alert_threshold')})"
            )
            if pb.get("alert") or int(pb.get("consecutive_zero_finviz") or 0) >= int(pb.get("alert_threshold") or 3):
                st.warning("Path B universe health warning — consecutive empty/bad cycles climbing.")
            if stats:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"metric": "finviz_raw", "value": stats.get("finviz_raw")},
                            {"metric": "after_filters", "value": stats.get("after_filters")},
                            {"metric": "seed_count", "value": stats.get("seed_count")},
                            {"metric": "kept_0dte", "value": stats.get("kept_0dte")},
                            {"metric": "dropped_non_0dte", "value": stats.get("dropped_non_0dte")},
                        ]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )
        if not path_a["ok"]:
            missing_file("path_a_pipeline_health.json")
        else:
            last = pa.get("last_screener") or {}
            by_path = last.get("herd_alert_by_path") or {}
            st.markdown("**Path A — HIGH_ALERT by path (current cycle)**")
            if by_path:
                st.dataframe(
                    pd.DataFrame([{"path": k, "count": int(v)} for k, v in by_path.items()]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                empty_state("No herd_alert_by_path on last screener cycle")
            funnel = (pa.get("last_pipeline") or {})
            if funnel:
                st.caption(f"Last pipeline tag={funnel.get('tag')} tickers_in={funnel.get('tickers_in')}")

    st.subheader("Decision mix (trade log)")
    if not items:
        empty_state("No trade_log rows yet")
        return
    counts = Counter(str(r.get("decision") or "LOG").upper() for r in items)
    cdf = pd.DataFrame({"decision": list(counts.keys()), "count": list(counts.values())})
    fig = px.bar(
        cdf,
        x="decision",
        y="count",
        color="decision",
        color_discrete_map=DECISION_COLORS,
    )
    fig.update_layout(**plotly_layout(title="All-time decisions in trade_log", height=300, showlegend=False))
    st.plotly_chart(fig, use_container_width=True)

    path_counts = Counter(path_label(r.get("signal_source")) for r in items)
    st.caption(
        "By path: "
        + ", ".join(f"Path {k}={v}" for k, v in sorted(path_counts.items()))
    )

    # Quick execution rates folded from former Performance tab
    actionable = [r for r in items if str(r.get("decision") or "").upper() in {"BUY", "SELL", "REVIEW"}]
    executed = [r for r in actionable if r.get("executed")]
    st.metric(
        "Actionable executed rate",
        f"{(100 * len(executed) / len(actionable)):.0f}%" if actionable else "—",
        help=f"n={len(executed)}/{len(actionable)}",
    )
