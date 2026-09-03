"""Diagnostics tab — health/debugging panels (read-only state)."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components.empty import empty_state, missing_file, stale_banner
from dashboard.data import paths as P
from dashboard.data.loaders import (
    load_items_file,
    load_json,
    load_latest_eod,
    load_near_miss_eod,
    solicitation_stats,
)
from dashboard.theme import COLORS, plotly_layout


def render(settings: Dict[str, Any]) -> None:
    del settings  # gates live in header; this tab is state diagnostics
    st.caption("Live-agent health & debugging — not research/backtest.")

    path_b = load_json(P.PATH_B_HEALTH_PATH, {})
    quote = load_json(P.QUOTE_SANITY_PATH, {})
    flip_cd = load_json(P.FLIP_COOLDOWN_PATH, {})
    flip_audit = load_json(P.FLIP_AUDIT_PATH, [])
    trade = load_items_file(P.TRADE_LOG_PATH)
    eod_env = load_latest_eod()
    eod = eod_env["data"] if eod_env["ok"] and isinstance(eod_env.get("data"), dict) else {}
    nm = load_near_miss_eod()
    sol = solicitation_stats()
    ha = load_items_file(P.HIGH_ALERT_PATH)
    path_a = load_json(P.PATH_A_HEALTH_PATH, {})

    # --- Path B ---
    st.subheader("Path B universe health")
    if not path_b["ok"]:
        missing_file("path_b_universe_health.json")
    else:
        stale_banner(path_b.get("age_sec"), threshold_sec=600, label="Path B health")
        data = path_b["data"] if isinstance(path_b.get("data"), dict) else {}
        stats = data.get("last_stats") or {}
        consec = int(data.get("consecutive_zero_finviz") or 0)
        thr = int(data.get("alert_threshold") or 3)
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Finviz raw", stats.get("finviz_raw", "—"))
        m2.metric("After filters", stats.get("after_filters", "—"))
        m3.metric("Seed", stats.get("seed_count", "—"))
        m4.metric("Kept near-exp", stats.get("kept_0dte", "—"))
        m5.metric("Dropped", stats.get("dropped_non_0dte", "—"))
        if consec >= thr or data.get("alert"):
            st.warning(f"Consecutive bad/empty cycles: **{consec}** (threshold {thr})")
        else:
            st.caption(f"Consecutive zero Finviz cycles: {consec} / {thr}")
        if stats.get("scrape_error"):
            st.error(f"Scrape error: {stats.get('scrape_error')}")

    # --- HIGH_ALERT by path (current cycle) ---
    st.subheader("HIGH_ALERT by promotion path")
    by_path = {}
    if isinstance(ha.get("meta"), dict):
        by_path = ha["meta"].get("herd_alert_by_path") or {}
    if not by_path and path_a["ok"]:
        by_path = ((path_a["data"] or {}).get("last_screener") or {}).get("herd_alert_by_path") or {}
    if by_path:
        bdf = pd.DataFrame([{"path": k, "count": int(v)} for k, v in by_path.items()])
        fig = px.bar(bdf, x="path", y="count", color="path", color_discrete_sequence=[COLORS["info"], COLORS["path_a2"], COLORS["path_b"]])
        fig.update_layout(**plotly_layout(title="Current cycle only (no multi-cycle history in state)", height=280, showlegend=False))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Multi-cycle history is not persisted by the agent yet — this is the latest cycle snapshot.")
    else:
        empty_state("No herd_alert_by_path on current high_alert / path_a health")

    # --- Quote sanity ---
    st.subheader("Quote sanity pauses")
    if not quote["ok"]:
        missing_file("quote_sanity.json")
    else:
        tickers = (quote["data"] or {}).get("tickers") if isinstance(quote.get("data"), dict) else {}
        paused_rows = []
        if isinstance(tickers, dict):
            for t, meta in tickers.items():
                if not isinstance(meta, dict):
                    continue
                if meta.get("paused_until_change"):
                    paused_rows.append(
                        {
                            "ticker": t,
                            "contract": meta.get("contract_symbol"),
                            "updated_at": meta.get("updated_at"),
                            "recent_n": len(meta.get("recent_premiums") or []),
                        }
                    )
        if paused_rows:
            st.dataframe(pd.DataFrame(paused_rows), use_container_width=True, hide_index=True)
        else:
            empty_state("No tickers currently paused for identical/stale quotes")

    # --- Flip audit ---
    st.subheader("Flip / churn")
    if flip_cd["ok"] and isinstance(flip_cd.get("data"), dict):
        entries = (flip_cd["data"].get("entries") or {})
        st.caption(f"Cooldownoldown entries: {len(entries) if isinstance(entries, dict) else 0}")
    audit_data = flip_audit.get("data")
    rows: List[Dict[str, Any]] = []
    if isinstance(audit_data, list):
        rows = [r for r in audit_data if isinstance(r, dict)]
    elif isinstance(audit_data, dict) and isinstance(audit_data.get("items"), list):
        rows = [r for r in audit_data["items"] if isinstance(r, dict)]
    if not flip_audit["ok"] and not rows:
        missing_file("flip_audit.json", "No flip audit yet — empty is normal if no flips fired.")
    elif rows:
        recent = sorted(rows, key=lambda r: str(r.get("timestamp") or ""), reverse=True)[:40]
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "timestamp": r.get("timestamp"),
                        "ticker": r.get("ticker"),
                        "flip_decision": r.get("flip_decision"),
                        "reason": r.get("reason"),
                        "option_side": r.get("option_side"),
                        "decision": r.get("decision"),
                    }
                    for r in recent
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    else:
        empty_state("Flip audit file present but empty")

    # --- Rejection breakdown ---
    st.subheader("Rejection breakdown (session trade_log)")
    items = trade.get("items") or []
    today = P.session_date_et()
    session_rows = [
        r
        for r in items
        if str(r.get("timestamp") or "").startswith(today)
        or str(r.get("timestamp") or "").startswith(today.replace("-", ""))
    ]
    # also accept UTC dates near session
    if not session_rows:
        session_rows = items  # fall back to all with caption
        st.caption("No rows matched today's date prefix — showing full trade_log aggregates.")
    codes = Counter(
        str(r.get("decision_reason_code") or r.get("review_reason_code") or "none")
        for r in session_rows
        if str(r.get("decision") or "").upper() == "LOG"
    )
    if codes:
        cdf = pd.DataFrame([{"decision_reason_code": k, "count": v} for k, v in codes.most_common()])
        st.dataframe(cdf, use_container_width=True, hide_index=True)
    else:
        empty_state("No LOG reason codes in scope")

    liq_primary = Counter()
    liq_examples: List[Dict[str, Any]] = []
    for r in session_rows:
        meta = r.get("decision_meta") if isinstance(r.get("decision_meta"), dict) else {}
        primary = meta.get("liquidity_reject_primary") or ""
        if primary:
            liq_primary[str(primary)] += 1
            if len(liq_examples) < 12:
                liq_examples.append(
                    {
                        "ticker": r.get("ticker"),
                        "primary": primary,
                        "detail": (meta.get("liquidity_reject_detail") or "")[:160],
                        "spread": meta.get("atm_median_spread_pct")
                        or (meta.get("factor_snapshot") or {}).get("atm_median_spread_pct"),
                        "oi_min": meta.get("atm_min_oi"),
                    }
                )
    # reinforce with EOD
    eod_liq = eod.get("liquidity_reject_subreasons") or {}
    if eod_liq:
        st.markdown("**EOD liquidity sub-reasons**")
        st.dataframe(
            pd.DataFrame([{"primary": k, "count": int(v)} for k, v in eod_liq.items()]),
            use_container_width=True,
            hide_index=True,
        )
    if liq_primary:
        st.markdown("**Trade-log liquidity_reject_primary**")
        st.dataframe(
            pd.DataFrame([{"primary": k, "count": v} for k, v in liq_primary.most_common()]),
            use_container_width=True,
            hide_index=True,
        )
    if liq_examples:
        st.markdown("**Sample liquidity rejects (with values)**")
        st.dataframe(pd.DataFrame(liq_examples), use_container_width=True, hide_index=True)

    # --- Near-miss ---
    st.subheader("Near-miss shadow outcomes")
    if not nm["ok"]:
        missing_file("near_miss_eod_*.json")
    else:
        data = nm["data"] if isinstance(nm.get("data"), dict) else {}
        st.markdown(
            f"**{data.get('headline') or 'Near-miss EOD'}** — total N={data.get('total', 0)}, "
            f"with entry quote N={data.get('with_entry_quote', 0)}"
        )
        if data.get("headline_detail"):
            st.caption(str(data.get("headline_detail")))
        outcomes = data.get("low_confidence_outcomes") or {}
        if outcomes:
            odf = pd.DataFrame(
                [{"outcome": k, "count": int(v), "N": int(v)} for k, v in outcomes.items()]
            )
            fig = px.bar(odf, x="outcome", y="count", color_discrete_sequence=[COLORS["warn"]])
            fig.update_layout(**plotly_layout(title="Shadow outcomes (counts = N)", height=280))
            st.plotly_chart(fig, use_container_width=True)
        bands = data.get("confidence_bands") or {}
        if isinstance(bands, dict) and bands:
            brow = []
            for band, meta in bands.items():
                if not isinstance(meta, dict):
                    continue
                n = int(meta.get("count") or 0)
                won = int(meta.get("would_have_won") or meta.get("TP") or 0)
                lost = int(meta.get("would_have_lost") or 0)
                brow.append(
                    {
                        "band": band,
                        "N": n,
                        "would_have_won": won,
                        "would_have_lost": lost,
                        "win_rate": f"{(100 * won / n):.0f}% (N={n})" if n else "—",
                    }
                )
            st.dataframe(pd.DataFrame(brow), use_container_width=True, hide_index=True)
            st.caption("Rates always shown with sample size N — never a bare percentage.")

    # --- Solicitation ---
    st.subheader("Solicitation filter (from agent log)")
    if not sol.get("ok"):
        empty_state("Solicitation activity not available", sol.get("error") or "log missing")
    else:
        st.metric("Skipped solicitation lines (today's log window)", sol.get("count", 0))
        samples = sol.get("samples") or []
        if samples:
            with st.expander("Sample log lines"):
                for s in samples:
                    st.code(s, language=None)
        st.caption("Counted from logs (no dedicated state counter yet).")
