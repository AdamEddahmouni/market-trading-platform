"""Shared empty / stale UI components."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from dashboard.data.loaders import freshness_text


def empty_state(message: str, detail: str = "") -> None:
    """Show a dashed empty placeholder."""
    extra = f"<div style='margin-top:0.35rem;font-size:0.85rem'>{detail}</div>" if detail else ""
    st.markdown(
        f"<div class='empty-box'>{message}{extra}</div>",
        unsafe_allow_html=True,
    )


def stale_banner(age_sec: Optional[float], *, threshold_sec: float = 180.0, label: str = "State") -> None:
    """Warn when state looks stale."""
    if age_sec is None:
        return
    if age_sec < threshold_sec:
        return
    st.markdown(
        f"<div class='stale-banner'><strong>{label} may be stale</strong> — "
        f"last update {freshness_text(age_sec)}. "
        "If the agent should be running, check Overview runtime / PID.</div>",
        unsafe_allow_html=True,
    )


def missing_file(name: str, hint: str = "") -> None:
    empty_state(
        f"{name} not available yet",
        hint or "File missing or not written for this session — panels stay empty until the agent produces it.",
    )
