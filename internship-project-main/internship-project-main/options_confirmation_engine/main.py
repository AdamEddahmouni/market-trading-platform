"""Main entrypoint for standalone options confirmation runs."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

from options_engine.runner import run_batch
from options_engine.utils import acquire_pid_lock, load_settings, release_pid_lock


def run_from_request(request_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute batch run from structured request payload."""
    settings = load_settings()
    runtime_cfg = settings.get("runtime", {})
    if not acquire_pid_lock(bool(runtime_cfg.get("single_instance_required", True))):
        return {"error": "instance_locked"}
    try:
        tickers = request_payload.get("tickers", [])
        as_of = request_payload.get("as_of")
        request_id = str(request_payload.get("request_id", datetime.now(timezone.utc).isoformat()))
        if not isinstance(tickers, list) or not tickers:
            return {"error": "tickers must be a non-empty list"}
        return run_batch(tickers=tickers, settings=settings, as_of=as_of, request_id=request_id)
    finally:
        release_pid_lock()


def main() -> None:
    """
    Run options engine with a basic stdin JSON request.

    Input example:
    {"request_id":"demo","as_of":"2026-06-07T12:00:00+00:00","tickers":["AAPL","TSLA"]}
    """
    raw = sys.stdin.read().strip()
    if not raw:
        payload: Dict[str, Any] = {"request_id": "default", "tickers": ["AAPL"]}
    else:
        payload = json.loads(raw)
    result = run_from_request(payload)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

