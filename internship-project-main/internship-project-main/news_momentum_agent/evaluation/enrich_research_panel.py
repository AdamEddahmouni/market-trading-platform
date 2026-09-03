"""Enrich research panel rows with macro calendar + VIX (research only).

Purpose
-------
Post-process SPY/QQQ panel rows with scheduled catalyst and VIX EOD features
before pattern mining.

Features / API role
-------------------
``enrich_panel_rows``, ``enrich_and_save_panel`` → writes enriched JSON panel.

How this uses ``options_confirmation_engine``
-----------------------------------------------
Independent; enriches rows that already contain ``options_score`` from replay.

Options-specific vs reusable
----------------------------
Reusable enrichment pipeline; VIX/macro features complement options bands in mining.

Research only.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from evaluation.macro_calendar import enrich_rows_with_calendar
from evaluation.vix_history import enrich_rows_with_vix, fetch_vix_history

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENRICHED_PANEL_PATH = PROJECT_ROOT / "state" / "learning" / "research_panel_spy_qqq_enriched.json"


def _date_span(rows: Sequence[Dict[str, Any]]) -> tuple[date, date]:
    days: List[date] = []
    for row in rows:
        text = str(row.get("session_date") or row.get("timestamp") or "")[:10]
        try:
            days.append(date.fromisoformat(text))
        except ValueError:
            continue
    if not days:
        today = date.today()
        return today, today
    return min(days), max(days)


def enrich_panel_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    fetch_vix: bool = True,
    force_vix_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """Apply macro calendar + optional VIX history enrichment to panel rows."""
    enriched = enrich_rows_with_calendar(rows)
    if fetch_vix:
        start, end = _date_span(enriched)
        try:
            vix = fetch_vix_history(start=start, end=end, force_refresh=force_vix_refresh)
            enriched = enrich_rows_with_vix(enriched, vix)
        except Exception as error:
            for row in enriched:
                row.setdefault("vix_level", None)
                row.setdefault("vix_change_intraday", None)
                row["vix_enrich_error"] = str(error)
    return enriched


def enrich_and_save_panel(
    panel: Dict[str, Any],
    *,
    out_path: Path = ENRICHED_PANEL_PATH,
    fetch_vix: bool = True,
) -> Dict[str, Any]:
    """Enrich panel rows and persist to ``out_path`` with enrichment metadata."""
    rows = enrich_panel_rows(panel.get("rows") or [], fetch_vix=fetch_vix)
    catalyst_n = sum(1 for r in rows if r.get("is_scheduled_catalyst_day") is True)
    vix_n = sum(1 for r in rows if r.get("vix_level") is not None)
    out = dict(panel)
    out["rows"] = rows
    out["n_rows"] = len(rows)
    out["enrichment"] = {
        "catalyst_days_rows": catalyst_n,
        "vix_rows": vix_n,
        "note": (
            "vix_change_intraday is EOD prior-close→close % proxy; "
            "macro calendar is a static major-event list (FOMC/CPI/NFP)."
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out
