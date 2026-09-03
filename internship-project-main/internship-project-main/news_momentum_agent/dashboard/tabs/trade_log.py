"""Trade Log tab — includes LOG/blocked rows with reason filters."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from dashboard.components.badges import decision_badge, headline_display, path_badges_inline, render_html
from dashboard.components.empty import empty_state
from dashboard.data import paths as P
from dashboard.data.loaders import load_items_file, path_label


def _ts_day(ts: Any) -> str:
    text = str(ts or "")
    if "T" in text:
        return text.split("T", 1)[0]
    return text[:10]


def render(settings: Dict[str, Any]) -> None:
    trade = load_items_file(P.TRADE_LOG_PATH)
    items: List[Dict[str, Any]] = list(trade.get("items") or [])
    if not items:
        empty_state("trade_log.json empty")
        return

    today = P.session_date_et()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        scope = st.selectbox("Scope", ["Today", "All"], index=0)
    with c2:
        show_logs = st.checkbox("Include LOG / blocked", value=False)
    with c3:
        decisions = sorted({str(r.get("decision") or "").upper() for r in items})
        dec_filter = st.multiselect(
            "Decisions",
            options=decisions,
            default=[d for d in ["BUY", "SELL", "REVIEW"] if d in decisions] or decisions[:3],
        )
    with c4:
        codes = sorted(
            {
                str(r.get("decision_reason_code") or r.get("review_reason_code") or "")
                for r in items
                if r.get("decision_reason_code") or r.get("review_reason_code")
            }
        )
        code_filter = st.multiselect("Reason codes", options=codes, default=[])

    sources = sorted({str(r.get("signal_source") or "news") for r in items})
    src_filter = st.multiselect("signal_source", options=sources, default=[])
    q = st.text_input("Search ticker / text", "")

    rows = items
    if scope == "Today":
        rows = [r for r in rows if _ts_day(r.get("timestamp")) == today]
        if not rows:
            st.caption(f"No rows for {today} — showing all.")
            rows = items

    filtered: List[Dict[str, Any]] = []
    for r in rows:
        dec = str(r.get("decision") or "").upper()
        if not show_logs and dec == "LOG":
            continue
        if dec_filter and dec not in dec_filter:
            continue
        code = str(r.get("decision_reason_code") or r.get("review_reason_code") or "")
        if code_filter and code not in code_filter:
            continue
        src = str(r.get("signal_source") or "news")
        if src_filter and src not in src_filter:
            continue
        if q:
            blob = " ".join(
                str(r.get(k) or "")
                for k in ("ticker", "news_headline", "reasoning", "why", "decision_reason_code")
            ).lower()
            if q.lower() not in blob:
                continue
        filtered.append(r)

    st.caption(f"Showing {len(filtered)} / {len(items)} rows")
    if not filtered:
        empty_state("No rows match filters")
        return

    # Card preview for latest few actionable
    preview = [r for r in filtered if str(r.get("decision") or "").upper() != "LOG"][:6]
    if preview:
        st.markdown("**Recent actionable**")
        for r in preview:
            render_html(
                decision_badge(r.get("decision"))
                + " "
                + path_badges_inline(r.get("signal_source"), settings)
                + f" <strong>{r.get('ticker')}</strong> "
                + headline_display(r)
            )
            st.caption(
                f"{r.get('timestamp')} · lean={r.get('lean')} {r.get('lean_pct')}% · "
                f"conf={r.get('confidence_pct') or r.get('agreement_confidence')} · "
                f"reason={r.get('decision_reason_code') or r.get('review_reason_code') or '—'}"
            )

    table_rows = []
    for r in filtered:
        meta = r.get("decision_meta") if isinstance(r.get("decision_meta"), dict) else {}
        table_rows.append(
            {
                "timestamp": r.get("timestamp"),
                "ticker": r.get("ticker"),
                "decision": str(r.get("decision") or "").upper(),
                "path": path_label(r.get("signal_source")),
                "signal_source": r.get("signal_source"),
                "decision_reason_code": r.get("decision_reason_code") or r.get("review_reason_code"),
                "liquidity_primary": meta.get("liquidity_reject_primary"),
                "liquidity_detail": (meta.get("liquidity_reject_detail") or "")[:120],
                "lean": r.get("lean"),
                "lean_pct": r.get("lean_pct"),
                "confidence_pct": r.get("confidence_pct") or r.get("agreement_confidence"),
                "executed": r.get("executed"),
                "headline": str(r.get("news_headline") or ""),
                "reasoning": str(r.get("reasoning") or "")[:120],
            }
        )
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True, height=420)
