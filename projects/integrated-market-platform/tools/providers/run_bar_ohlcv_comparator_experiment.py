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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bounded IMP bar simulator dry-run for Item 9 comparator timing.",
    )
    parser.add_argument("--signal-time-ns", type=int, required=True)
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
    observation_ns = (
        args.observation_time_ns if args.observation_time_ns is not None else monotonic_wall_ns()
    )
    collection_root = args.collection_root if args.collection_root is not None else default_collection_root()
    result = run_bounded_bar_ohlcv_experiment(
        signal_time_ns=args.signal_time_ns,
        observation_time_ns=observation_ns,
        instrument_id=str(args.instrument_id),
        source=args.source,
        collection_root=collection_root,
        env=dict(os.environ),
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
