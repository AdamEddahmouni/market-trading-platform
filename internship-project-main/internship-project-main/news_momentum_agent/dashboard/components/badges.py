"""Badge helpers for path / decision / alert_reason chips."""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

import streamlit as st

from dashboard.data.loaders import path_label


def decision_badge(decision: Any) -> str:
    d = str(decision or "").upper()
    cls = {
        "BUY": "badge-buy",
        "SELL": "badge-sell",
        "REVIEW": "badge-review",
        "LOG": "badge-log",
    }.get(d, "badge-log")
    return f"<span class='badge {cls}'>{d or '—'}</span>"


def path_badge(signal_source: Any, *, research_only: bool = False) -> str:
    label = path_label(signal_source)
    cls = {"A": "badge-path-a", "A.2": "badge-path-a2", "B": "badge-path-b"}.get(label, "badge-path-a")
    suffix = " · research-only" if (label == "A.2" or research_only) else ""
    return f"<span class='badge {cls}'>Path {label}{suffix}</span>"


def alert_reason_badges(reasons: Any) -> str:
    if not reasons:
        return ""
    if isinstance(reasons, str):
        reasons = [reasons]
    if not isinstance(reasons, (list, tuple)):
        return ""
    bits: List[str] = []
    for r in reasons:
        bits.append(f"<span class='badge badge-warn'>{r}</span>")
    return " ".join(bits)


def headline_display(row: dict) -> str:
    """Headline with amber gap badge when scrape path left news_headline empty."""
    headline = str(row.get("news_headline") or "").strip()
    if headline and headline.lower() not in {"no headline", "unknown", "none"}:
        return headline
    fallback = str(row.get("reasoning") or row.get("why") or "").strip()
    gap = "<span class='badge badge-gap'>display gap</span> "
    if fallback:
        short = fallback if len(fallback) <= 140 else fallback[:137] + "…"
        return f"{gap}<em>{short}</em>"
    return f"{gap}<em>No headline</em>"


def render_html(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def path_badges_inline(signal_source: Any, settings: Optional[dict] = None) -> str:
    research = False
    if settings:
        research = not bool((settings.get("execution") or {}).get("path_a2_auto_execute", False))
    src = str(signal_source or "").lower()
    return path_badge(signal_source, research_only=(src in {"news_catalyst", "path_a2"} and research))
