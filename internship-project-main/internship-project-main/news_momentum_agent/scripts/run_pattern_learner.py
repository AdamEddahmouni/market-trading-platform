#!/usr/bin/env python3
"""Run offline win/loss pattern learning on stored paper history.

CLI
---
``python scripts/run_pattern_learner.py [--backfill-calibration] [--min-group-n N]
[--dry-run-backfill]``

Usage examples::

  ./venv/bin/python scripts/run_pattern_learner.py
  ./venv/bin/python scripts/run_pattern_learner.py --backfill-calibration

When to run
-----------
Periodically after paper trading accumulates executions; offline analysis only.

Safe vs live agent
------------------
**Safe / offline:** Reads history, writes learning reports. Optional backfill
updates calibration log from closed trades — does not place orders or touch
``main.py`` scheduler.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.pattern_learner import (  # noqa: E402
    backfill_calibration_outcomes,
    format_pattern_report,
    run_pattern_learning,
)


def main() -> int:
    """CLI entry: optional calibration backfill, then offline pattern learning report."""
    parser = argparse.ArgumentParser(description="Learn win/loss patterns from paper history")
    parser.add_argument(
        "--backfill-calibration",
        action="store_true",
        help="Fill calibration_log outcomes from closed executions before learning",
    )
    parser.add_argument(
        "--min-group-n",
        type=int,
        default=3,
        help="Minimum samples for a categorical pattern (default 3)",
    )
    parser.add_argument(
        "--dry-run-backfill",
        action="store_true",
        help="Show calibration backfill counts without writing",
    )
    args = parser.parse_args()

    if args.backfill_calibration or args.dry_run_backfill:
        result = backfill_calibration_outcomes(dry_run=bool(args.dry_run_backfill))
        print(
            f"[calibration backfill] updated={result['updated']} "
            f"already={result['already_labeled']} unmatched={result['still_unmatched']} "
            f"total={result['total_rows']} dry_run={result['dry_run']}"
        )

    report = run_pattern_learning(min_group_n=max(1, int(args.min_group_n)), persist=True)
    print(format_pattern_report(report))
    print(f"\nWrote artifacts under {PROJECT_ROOT / 'state' / 'learning'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
