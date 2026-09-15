#!/usr/bin/env python3
"""Dry-run Item 9 BAR_OHLCV_1M comparator experiment (no orders, not CALIBRATED)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.clock import monotonic_wall_ns  # noqa: E402
from market_platform_foundation.paper.calibration.bar_ohlcv_experiment import (  # noqa: E402
    default_collection_root,
    run_bounded_bar_ohlcv_experiment,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_comparator_bridge import (  # noqa: E402
    load_prospective_receipt,
    validate_prospective_receipt_for_comparator,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bounded IMP bar simulator dry-run for Item 9 comparator timing.",
    )
    parser.add_argument(
        "--from-receipt",
        type=Path,
        default=None,
        help="Replay dry-run using signal/observation times from a prospective receipt (no override).",
    )
    parser.add_argument("--signal-time-ns", type=int, default=None)
    parser.add_argument("--observation-time-ns", type=int, default=None)
    parser.add_argument("--instrument-id", default="BIYA")
    parser.add_argument(
        "--source",
        choices=("admitted-fixture", "moomoo-opend"),
        default="admitted-fixture",
        help="admitted-fixture=ADMITTED-SHORTSQ-BIYA-BARS-001; moomoo-opend=loopback OpenD 1m kline",
    )
    parser.add_argument(
        "--collection-root",
        type=Path,
        default=None,
        help="Monorepo projects/ root (defaults to parent of IMP)",
    )
    args = parser.parse_args(argv)
    collection_root = args.collection_root if args.collection_root is not None else default_collection_root()
    instrument_id = str(args.instrument_id)
    source = args.source

    if args.from_receipt is not None:
        receipt = load_prospective_receipt(args.from_receipt)
        gate = validate_prospective_receipt_for_comparator(receipt)
        if not gate["ok"]:
            print(json.dumps({"ok": False, **gate}, indent=2, sort_keys=True))
            return 2
        signal_ns = int(receipt["signal_time_ns"])
        observation_ns = int(receipt["observation_time_ns"])
        instrument_id = str(receipt["instrument_id"])
        source = "moomoo-opend"
    else:
        if args.signal_time_ns is None:
            parser.error("--signal-time-ns is required unless --from-receipt is set")
        signal_ns = int(args.signal_time_ns)
        observation_ns = (
            args.observation_time_ns if args.observation_time_ns is not None else monotonic_wall_ns()
        )

    result = run_bounded_bar_ohlcv_experiment(
        signal_time_ns=signal_ns,
        observation_time_ns=observation_ns,
        instrument_id=instrument_id,
        source=source,
        collection_root=collection_root,
        env=dict(os.environ),
    )
    payload = result.to_dict()
    if args.from_receipt is not None:
        payload["from_receipt"] = str(args.from_receipt)
        payload["experiment_id"] = receipt.get("experiment_id")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
