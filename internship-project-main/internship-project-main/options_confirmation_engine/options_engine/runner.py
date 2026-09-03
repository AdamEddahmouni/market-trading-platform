"""Core orchestration for one-ticker and batch options scoring runs.

Purpose
-------
End-to-end pipeline: fetch snapshot → load local history → compute features →
score → optionally persist raw snapshot and batch state files.

Features / API role
-------------------
- ``run_ticker``: returns one scored dict (includes ``features``, ``provider``).
- ``run_batch``: loops tickers, writes ``state/signals.json``, appends
  ``state/trade_log.json``, updates ``state/health.json``.

How ``news_momentum_agent`` consumes it
---------------------------------------
``agent/options_client.score_ticker`` calls ``run_batch([ticker], ...)`` and
uses the first ``items[0]`` entry. The agent dashboard reads ``state/`` under
``engine_path`` when configured.

Options-specific vs reusable
----------------------------
Options-specific: ties ingest, feature cache on snapshots, and scoring together.
Reusable: batch JSON state pattern and ``request_id`` tracing for cross-service
correlation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from options_engine.data_ingestor import fetch_options_snapshot
from options_engine.features import compute_features
from options_engine.scoring import score_options
from options_engine.snapshot_store import load_snapshot_history, save_snapshot
from options_engine.utils import PROJECT_ROOT, load_json, save_json


STATE_DIR = PROJECT_ROOT / "state"
SIGNALS_PATH = STATE_DIR / "signals.json"
TRADE_LOG_PATH = STATE_DIR / "trade_log.json"
HEALTH_PATH = STATE_DIR / "health.json"


def _append_list_json(path: Path, item: Dict[str, Any], atomic: bool) -> None:
    """Append item to a list JSON file."""
    existing = load_json(path, [])
    rows = existing if isinstance(existing, list) else []
    rows.append(item)
    save_json(path, rows, atomic=atomic)


def run_ticker(ticker: str, settings: Dict[str, Any], as_of: str | None = None) -> Dict[str, Any]:
    """Run options confirmation for one ticker."""
    as_of_text = as_of or datetime.now(timezone.utc).isoformat()
    snapshot = fetch_options_snapshot(ticker=ticker, settings=settings, as_of=as_of_text)
    history = load_snapshot_history(snapshot.ticker, max_files=120)
    features = compute_features(snapshot=snapshot, history=history, settings=settings)
    provider = str(settings.get("chain", {}).get("provider", "yfinance")).lower()
    save_snapshots = bool(settings.get("logging", {}).get("save_raw_snapshot", True))
    if provider == "replay":
        save_snapshots = False
    if save_snapshots:
        snapshot_dict = snapshot.to_dict()
        snapshot_dict["feature_cache"] = {
            "atm_iv": features.get("atm_iv", 0.0),
            "total_volume": features.get("total_volume", 0.0),
        }
        save_snapshot(snapshot=snapshot, atomic=bool(settings.get("runtime", {}).get("state_write_atomic", True)))
    scored = score_options(snapshot.ticker, features, snapshot.data_quality_flags, settings)
    scored["as_of"] = as_of_text
    scored["spot_price"] = round(float(snapshot.spot_price), 4)
    scored["features"] = features
    scored["provider"] = str(snapshot.provider or "")
    return scored


def run_batch(tickers: List[str], settings: Dict[str, Any], as_of: str | None = None, request_id: str = "") -> Dict[str, Any]:
    """Run batch scoring and persist state outputs."""
    runtime_cfg = settings.get("runtime", {})
    atomic = bool(runtime_cfg.get("state_write_atomic", True))
    as_of_text = as_of or datetime.now(timezone.utc).isoformat()
    clean_tickers = [item.upper().strip() for item in tickers if item.strip()]
    results: List[Dict[str, Any]] = []
    for ticker in clean_tickers:
        scored = run_ticker(ticker=ticker, settings=settings, as_of=as_of_text)
        scored["request_id"] = request_id
        results.append(scored)

    signals_payload = {
        "meta": {"updated_at": as_of_text, "request_id": request_id, "count": len(results)},
        "items": results,
    }
    save_json(SIGNALS_PATH, signals_payload, atomic=atomic)

    for result in results:
        _append_list_json(TRADE_LOG_PATH, result, atomic=atomic)

    no_data_count = len([row for row in results if row.get("options_bias") == "no_data"])
    bias_counts: Dict[str, int] = {}
    for row in results:
        bias = str(row.get("options_bias", "unknown"))
        bias_counts[bias] = bias_counts.get(bias, 0) + 1
    health_payload = {
        "updated_at": as_of_text,
        "request_id": request_id,
        "tickers_evaluated": len(results),
        "no_data_count": no_data_count,
        "bias_counts": bias_counts,
        "score_distribution": {
            "gte_65": len([row for row in results if float(row.get("options_score", 0)) >= 65]),
            "between_35_65": len(
                [row for row in results if 35 < float(row.get("options_score", 0)) < 65]
            ),
            "lte_35": len([row for row in results if float(row.get("options_score", 0)) <= 35]),
        },
    }
    save_json(HEALTH_PATH, health_payload, atomic=atomic)
    return signals_payload

