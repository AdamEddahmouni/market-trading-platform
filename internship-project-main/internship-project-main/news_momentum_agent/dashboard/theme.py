"""Design tokens and Streamlit CSS for the research monitoring dashboard."""

from __future__ import annotations

from typing import Any, Dict

# Semantic + chrome tokens (keep charts/CSS in sync)
COLORS: Dict[str, str] = {
    "bg": "#0B0F14",
    "surface": "#121820",
    "surface2": "#182230",
    "border": "#243041",
    "text": "#E8EEF6",
    "muted": "#8B9BB0",
    "bull": "#22C55E",
    "bear": "#EF4444",
    "warn": "#F59E0B",
    "info": "#2DD4BF",
    "path_a": "#2DD4BF",
    "path_a2": "#A78BFA",
    "path_b": "#F59E0B",
    "log": "#94A3B8",
    "review": "#F59E0B",
}

DECISION_COLORS = {
    "BUY": COLORS["bull"],
    "SELL": COLORS["bear"],
    "REVIEW": COLORS["review"],
    "LOG": COLORS["log"],
}

BIAS_COLORS = {
    "bullish": COLORS["bull"],
    "bearish": COLORS["bear"],
    "neutral": COLORS["warn"],
    "no_data": COLORS["log"],
}


def plotly_layout(**extra: Any) -> Dict[str, Any]:
    """Shared Plotly layout defaults matching the dashboard theme."""
    base: Dict[str, Any] = {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": COLORS["text"], "family": "DM Sans, sans-serif"},
        "margin": {"l": 40, "r": 20, "t": 40, "b": 40},
        "xaxis": {"gridcolor": COLORS["border"], "zerolinecolor": COLORS["border"]},
        "yaxis": {"gridcolor": COLORS["border"], "zerolinecolor": COLORS["border"]},
        "legend": {"bgcolor": "rgba(0,0,0,0)"},
    }
    base.update(extra)
    return base


def inject_css() -> str:
    """Return custom CSS string (caller passes to st.markdown unsafe_allow_html)."""
    c = COLORS
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
  font-family: "DM Sans", system-ui, sans-serif;
}}
.stApp {{
  background: {c["bg"]};
  color: {c["text"]};
}}
h1, h2, h3 {{
  letter-spacing: -0.02em;
}}
code, .mono {{
  font-family: "JetBrains Mono", ui-monospace, monospace !important;
}}
div[data-testid="stSidebar"] {{
  background: {c["surface"]};
  border-right: 1px solid {c["border"]};
}}
.dash-card {{
  background: linear-gradient(180deg, {c["surface2"]} 0%, {c["surface"]} 100%);
  border: 1px solid {c["border"]};
  border-radius: 8px;
  padding: 0.85rem 1rem;
  margin-bottom: 0.5rem;
}}
.dash-card .label {{
  color: {c["muted"]};
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.25rem;
}}
.dash-card .value {{
  font-family: "JetBrains Mono", monospace;
  font-size: 1.35rem;
  font-weight: 600;
  color: {c["text"]};
}}
.dash-card .sub {{
  color: {c["muted"]};
  font-size: 0.8rem;
  margin-top: 0.2rem;
}}
.verdict-bar {{
  border-radius: 8px;
  padding: 0.9rem 1.1rem;
  margin-bottom: 0.75rem;
  border: 1px solid {c["border"]};
  font-weight: 600;
}}
.verdict-clean {{
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.35);
  color: {c["bull"]};
}}
.verdict-dirty {{
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.4);
  color: {c["bear"]};
}}
.verdict-missing {{
  background: rgba(245, 158, 11, 0.1);
  border-color: rgba(245, 158, 11, 0.35);
  color: {c["warn"]};
}}
.gate-chip {{
  display: inline-block;
  border: 1px solid {c["border"]};
  border-radius: 6px;
  padding: 0.2rem 0.55rem;
  margin: 0.15rem 0.25rem 0.15rem 0;
  font-size: 0.78rem;
  font-family: "JetBrains Mono", monospace;
  background: {c["surface"]};
}}
.gate-on {{ color: {c["bull"]}; border-color: rgba(34,197,94,0.4); }}
.gate-off {{ color: {c["muted"]}; }}
.badge {{
  display: inline-block;
  border-radius: 6px;
  padding: 0.12rem 0.45rem;
  font-size: 0.72rem;
  font-weight: 600;
  font-family: "JetBrains Mono", monospace;
  margin-right: 0.25rem;
}}
.badge-path-a {{ background: rgba(45,212,191,0.15); color: {c["path_a"]}; }}
.badge-path-a2 {{ background: rgba(167,139,250,0.18); color: {c["path_a2"]}; }}
.badge-path-b {{ background: rgba(245,158,11,0.15); color: {c["path_b"]}; }}
.badge-buy {{ background: rgba(34,197,94,0.15); color: {c["bull"]}; }}
.badge-sell {{ background: rgba(239,68,68,0.15); color: {c["bear"]}; }}
.badge-review {{ background: rgba(245,158,11,0.15); color: {c["warn"]}; }}
.badge-log {{ background: rgba(148,163,184,0.15); color: {c["log"]}; }}
.badge-warn {{ background: rgba(245,158,11,0.18); color: {c["warn"]}; }}
.badge-gap {{ background: rgba(245,158,11,0.12); color: {c["warn"]}; border: 1px dashed rgba(245,158,11,0.5); }}
.stale-banner {{
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.4);
  border-radius: 8px;
  padding: 0.65rem 0.9rem;
  color: {c["warn"]};
  margin-bottom: 0.75rem;
}}
.empty-box {{
  border: 1px dashed {c["border"]};
  border-radius: 8px;
  padding: 1.25rem;
  color: {c["muted"]};
  text-align: center;
  background: {c["surface"]};
}}
.horizon-box {{
  background: {c["surface"]};
  border: 1px solid {c["info"]};
  border-radius: 8px;
  padding: 0.75rem 1rem;
  margin-bottom: 0.5rem;
}}
.horizon-box .mode {{
  font-family: "JetBrains Mono", monospace;
  color: {c["info"]};
  font-weight: 600;
  font-size: 1.05rem;
}}
.research-banner {{
  background: rgba(167, 139, 250, 0.1);
  border: 1px solid rgba(167, 139, 250, 0.35);
  border-radius: 8px;
  padding: 0.65rem 0.9rem;
  color: {c["path_a2"]};
  margin-bottom: 0.75rem;
}}
</style>
"""
