"""Unified SPY/QQQ research panel: replay + live near-miss + live executed.

Purpose
-------
Merge backtest replay rows with live near-miss and executed trades into one
chronological panel for pattern mining.

Features / API role
-------------------
``build_spy_qqq_research_panel``, ``save_research_panel`` →
``state/learning/research_panel_spy_qqq.json``.

How this uses ``options_confirmation_engine``
-----------------------------------------------
Replay rows include ``options_score`` / ``options_bias`` from
``spy_qqq_replay`` (production ``score_options``). Live rows carry the same
fields from ``options_client`` at decision time.

Options-specific vs reusable
----------------------------
SPY/QQQ Path B scope; panel merge pattern is reusable across signal sources.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.pattern_learner import (  # noqa: E402
    load_execution_rows,
    load_near_miss_rows,
)
from evaluation.spy_qqq_replay import PATH_A_EXCLUSION_NOTE  # noqa: E402

ALLOWED_TICKERS = frozenset({"SPY", "QQQ"})
PANEL_PATH = PROJECT_ROOT / "state" / "learning" / "research_panel_spy_qqq.json"


def _norm_outcome(raw: Any) -> Optional[str]:
    text = str(raw or "").strip().lower()
    if text in {"win", "would_have_won"}:
        return "win"
    if text in {"loss", "would_have_lost"}:
        return "loss"
    if text in {"flat", "would_have_flattened_flat"}:
        return "flat"
    return None


def _filter_spy_qqq(rows: Sequence[Dict[str, Any]], source_kind: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker not in ALLOWED_TICKERS:
            continue
        copy = dict(row)
        copy["ticker"] = ticker
        copy["source_kind"] = source_kind
        outcome = _norm_outcome(copy.get("outcome") or copy.get("shadow_outcome"))
        if outcome:
            copy["outcome"] = outcome
        out.append(copy)
    return out


def build_spy_qqq_research_panel(
    *,
    replay_rows: Optional[Sequence[Dict[str, Any]]] = None,
    state_dir: Optional[Path] = None,
    replay_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build unified panel from replay CSV/rows plus live near-miss and executions."""
    state_dir = state_dir or (PROJECT_ROOT / "state")
    if replay_rows is None and replay_path and replay_path.exists():
        replay_rows = json.loads(replay_path.read_text(encoding="utf-8"))
    replay_rows = list(replay_rows or [])

    near = _filter_spy_qqq(load_near_miss_rows(state_dir), "live_near_miss")
    # pattern_learner tags near_miss_shadow — force live_near_miss
    for row in near:
        row["source_kind"] = "live_near_miss"

    executed = _filter_spy_qqq(load_execution_rows(state_dir=state_dir), "live_executed")
    for row in executed:
        row["source_kind"] = "live_executed"

    replay = _filter_spy_qqq(replay_rows, "backtest_replay")
    for row in replay:
        row["source_kind"] = "backtest_replay"

    panel = replay + near + executed
    panel.sort(key=lambda r: str(r.get("timestamp") or r.get("session_date") or ""))

    by_source: Dict[str, int] = {}
    for row in panel:
        sk = str(row.get("source_kind") or "unknown")
        by_source[sk] = by_source.get(sk, 0) + 1

    return {
        "generated_note": PATH_A_EXCLUSION_NOTE,
        "tickers": sorted(ALLOWED_TICKERS),
        "n_rows": len(panel),
        "by_source": by_source,
        "rows": panel,
        "confidence_note": (
            "source_kind must stay visible in all analysis. "
            "backtest_replay is not equal-confidence to live_executed."
        ),
    }


def save_research_panel(payload: Dict[str, Any], path: Path = PANEL_PATH) -> Path:
    """Write research panel JSON to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path
