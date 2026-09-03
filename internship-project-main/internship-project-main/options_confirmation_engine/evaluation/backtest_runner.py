"""Simple evaluation harness for options confirmation outputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from evaluation.metrics import evaluate_tracks
from options_engine.utils import PROJECT_ROOT, load_json, save_json


STATE_SIGNALS_PATH = PROJECT_ROOT / "state" / "signals.json"
REPORTS_DIR = PROJECT_ROOT / "evaluation" / "reports"


def load_rows() -> List[Dict[str, Any]]:
    payload = load_json(STATE_SIGNALS_PATH, {"items": []})
    if isinstance(payload, dict):
        items = payload.get("items", [])
        return items if isinstance(items, list) else []
    return []


def run_evaluation(confirmation_threshold: float = 65.0) -> Dict[str, Any]:
    rows = load_rows()
    metrics = evaluate_tracks(rows=rows, confirmation_threshold=confirmation_threshold)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "confirmation_threshold": confirmation_threshold,
        "metrics": metrics,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    filename = REPORTS_DIR / f"report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    save_json(filename, report, atomic=True)
    return report


def main() -> None:
    report = run_evaluation()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

