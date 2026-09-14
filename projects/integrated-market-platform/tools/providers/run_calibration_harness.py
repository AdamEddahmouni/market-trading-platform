#!/usr/bin/env python3
"""Classify IMP vs Tradier sandbox or Alpaca Paper calibration without fabricating fills.

Default: print harness status (COMPARATOR_NOT_CONFIGURED / WAITING_FOR_MARKET /
HARNESS_READY / LIVE_FORBIDDEN). Never places Live orders. Does not declare
CALIBRATED or FTEP EMPIRICAL_ACTIVE. Equity Paper does not validate ES futures fills.
Missing Alpaca Paper keys stay COMPARATOR_NOT_CONFIGURED.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.clock import monotonic_wall_ns  # noqa: E402
from market_platform_foundation.paper.calibration.runner import (  # noqa: E402
    run_calibration_campaign,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed Paper calibration harness classifier.")
    parser.add_argument(
        "--place-sandbox-orders",
        action="store_true",
        help="ignored: this classifier never places orders; sandbox submit stays on probe_tradier_sandbox.py --submit",
    )
    args = parser.parse_args(argv)
    del args
    result = run_calibration_campaign(env=dict(os.environ), now_ns=monotonic_wall_ns())
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
