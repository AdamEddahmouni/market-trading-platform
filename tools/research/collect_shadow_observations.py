"""Bounded forward shadow observation collection for P6 Shadow Run 1.

Subscribes to preregistered instrument(s), admits trades through the live
observational runtime with shadow recording armed, and writes captures under
the experiment store root for later labeling.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "moomoo"))

from market_platform_foundation.market_data.live_runtime import (  # noqa: E402
    LiveObservationalRuntime,
    reset_live_runtime,
)
from market_platform_foundation.market_data.recorder import ObservationalRecorder  # noqa: E402
from market_platform_foundation.market_data.subscription_manager import SubscriptionPriority  # noqa: E402
from market_platform_foundation.shadow.experiment import ShadowExperimentStore  # noqa: E402

import run_shadow_run as shadow_cli  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect forward shadow observations")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--store-root", default=str(shadow_cli.store_root_default()))
    parser.add_argument("--symbols", default="BIYA")
    parser.add_argument("--seconds", type=float, default=90.0)
    parser.add_argument("--max-records", type=int, default=2000)
    args = parser.parse_args(argv)

    store_root = Path(args.store_root)
    capture_root = store_root / "captures"
    capture_root.mkdir(parents=True, exist_ok=True)

    exp = ShadowExperimentStore(store_root / "experiment.sqlite3")
    try:
        contract = exp.manifest(args.run_id)
        if contract is None:
            print(json.dumps({"error": "RUN_NOT_FOUND", "run_id": args.run_id}))
            return 3
        if exp.run_state(args.run_id) != "OPEN":
            print(json.dumps({"error": "RUN_NOT_OPEN", "state": exp.run_state(args.run_id)}))
            return 4
    finally:
        exp.close()

    os.environ["IMP_LIVE_OBSERVATIONAL"] = "1"
    os.environ["IMP_MOOMOO_LIVE"] = "1"
    os.environ["IMP_SHADOW_RECORDING"] = "1"
    os.environ["IMP_SHADOW_RUN_ID"] = args.run_id
    os.environ["IMP_LIVE_CAPTURE_ROOT"] = str(capture_root)

    reset_live_runtime()
    runtime = LiveObservationalRuntime()
    capture_id = str((contract["manifest"].get("config") or {}).get("capture_id") or f"shadow-{uuid.uuid4().hex[:10]}")
    runtime.recorder = ObservationalRecorder(
        capture_id=capture_id,
        root=capture_root,
        max_records=max(50, args.max_records),
        max_bytes=8 * 1024 * 1024,
        rotate_on_bound=True,
    )
    runtime.configure()

    if runtime.shadow_recorder is None:
        print(json.dumps({"error": "SHADOW_RECORDER_NOT_ARMED", "run_id": args.run_id}))
        return 5

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    for symbol in symbols:
        runtime.subscribe(
            instrument_id=symbol,
            capabilities=["BASIC_QUOTE", "TRADES", "ORDER_BOOK"],
            consumer_id="shadow-run-1",
            priority=SubscriptionPriority.ACTIVE_WORKSPACE,
        )

    deadline = time.time() + max(5.0, args.seconds)
    while time.time() < deadline:
        time.sleep(0.5)

    stats = runtime.shadow_recorder.stats() if runtime.shadow_recorder else None
    for symbol in symbols:
        runtime.unsubscribe(
            instrument_id=symbol,
            capabilities=["BASIC_QUOTE", "TRADES", "ORDER_BOOK"],
            consumer_id="shadow-run-1",
        )
    runtime.stop()
    manifest = runtime.recorder.finalize(instruments=symbols, extra={"shadow_run_id": args.run_id})

    rc, status = shadow_cli.cmd_status(
        argparse.Namespace(run_id=args.run_id, store_root=str(store_root))
    )
    summary = {
        "capture_id": manifest.get("capture_id"),
        "capture_path": manifest.get("events_path"),
        "run_id": args.run_id,
        "symbols": symbols,
        "seconds": args.seconds,
        "recorder_stats": stats.__dict__ if stats else {},
        "status": status,
        "status_rc": rc,
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
