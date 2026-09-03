"""Persistence helpers for options snapshots.

Purpose
-------
Save and load per-ticker daily JSON under ``state/raw_snapshots/`` for IV rank,
flow-trend history, and offline replay.

Features / API role
-------------------
``save_snapshot``, ``load_snapshot_history``, ``snapshot_filename``.

How ``news_momentum_agent`` consumes it
---------------------------------------
Indirectly via ``runner.run_ticker`` (history for features). Evaluation harnesses
read the same directory when replaying stored chains. Agent ``seed_demo_state`` may
point at ``engine_path/state``.

Options-specific vs reusable
----------------------------
Reusable dated JSON blob store; filenames are ticker-prefixed for options runs.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from options_engine.data_models import Snapshot
from options_engine.utils import PROJECT_ROOT, load_json, save_json


RAW_SNAPSHOT_DIR = PROJECT_ROOT / "state" / "raw_snapshots"


def snapshot_filename(ticker: str, as_of: str) -> Path:
    """Build deterministic snapshot file path."""
    safe_ticker = ticker.upper().strip()
    try:
        date_part = datetime.fromisoformat(as_of.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        date_part = as_of[:10]
    RAW_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return RAW_SNAPSHOT_DIR / f"{safe_ticker}_{date_part}.json"


def save_snapshot(snapshot: Snapshot, atomic: bool = True) -> Path:
    """Persist one snapshot."""
    path = snapshot_filename(snapshot.ticker, snapshot.as_of)
    save_json(path, snapshot.to_dict(), atomic=atomic)
    return path


def load_snapshot_history(ticker: str, max_files: int = 120) -> List[Dict[str, Any]]:
    """Load historical snapshot files for one ticker."""
    RAW_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"{ticker.upper().strip()}_"
    files = sorted([item for item in RAW_SNAPSHOT_DIR.glob(f"{prefix}*.json")], reverse=True)[:max_files]
    return [load_json(path, {}) for path in files]

