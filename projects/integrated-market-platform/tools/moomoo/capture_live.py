"""Bounded real observational capture through the live runtime ingest path."""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "moomoo"))

from market_platform_foundation.market_data.live_config import default_capture_root, moomoo_host, moomoo_port
from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime, reset_live_runtime
from market_platform_foundation.market_data.recorder import ObservationalRecorder
from market_platform_foundation.market_data.subscription_manager import SubscriptionPriority


def _git_head() -> str | None:
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        text = (completed.stdout or "").strip()
        return text or None
    except OSError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Bounded live observational capture")
    parser.add_argument("--symbols", default="AAPL,NVDA")
    parser.add_argument("--seconds", type=float, default=12.0)
    parser.add_argument("--max-records", type=int, default=400)
    args = parser.parse_args()
    os.environ.setdefault("IMP_LIVE_OBSERVATIONAL", "1")
    os.environ.setdefault("IMP_MOOMOO_LIVE", "1")
    reset_live_runtime()
    runtime = LiveObservationalRuntime()
    capture_id = f"p21-{uuid.uuid4().hex[:10]}"
    runtime.recorder = ObservationalRecorder(
        capture_id=capture_id,
        root=default_capture_root(),
        max_records=max(20, args.max_records // 4) if args.max_records >= 40 else args.max_records,
        max_bytes=2 * 1024 * 1024,
        rotate_on_bound=True,
    )
    runtime.configure()
    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    for symbol in symbols:
        runtime.subscribe(
            instrument_id=symbol,
            capabilities=["BASIC_QUOTE", "TRADES", "ORDER_BOOK"],
            consumer_id="capture",
            priority=SubscriptionPriority.ACTIVE_WORKSPACE,
        )
    time.sleep(max(2.0, args.seconds))
    for symbol in symbols:
        runtime.unsubscribe(
            instrument_id=symbol,
            capabilities=["BASIC_QUOTE", "TRADES", "ORDER_BOOK"],
            consumer_id="capture",
        )
    runtime.stop()
    extra = {
        "host": moomoo_host(),
        "port": moomoo_port(),
        "provider_generation": runtime.lifecycle.provider_generation_id,
        "sdk_version": runtime.lifecycle.sdk_version,
        "opend_version": runtime.lifecycle.opend_version,
        "python_version": sys.version.split()[0],
        "feed_metrics": runtime.feed_metrics,
        "state_metrics": runtime.state.metrics_report(),
        "imp_head": _git_head(),
        "capabilities_requested": ["BASIC_QUOTE", "TRADES", "ORDER_BOOK"],
        "trade_api_counters": (runtime.feed_metrics or {}).get("trade_api_counters"),
    }
    manifest = runtime.recorder.finalize(instruments=symbols, extra=extra)
    print(manifest["events_path"])
    print(manifest["capture_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
