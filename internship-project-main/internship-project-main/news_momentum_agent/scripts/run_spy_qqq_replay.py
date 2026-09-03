#!/usr/bin/env python3
"""Run SPY/QQQ Path B replay + optional sanity check vs live trade_log.

CLI
---
``python scripts/run_spy_qqq_replay.py [--cache-dir DIR] [--sanity-date YYYY-MM-DD]
[--skip-sanity] [--out PATH]``

Replays historical Path B decisions from IVolatility cache; optional compare to
live ``trade_log`` on a sanity date.

When to run
-----------
After ``scripts/run_ivolatility_ingest.py`` populated ``evaluation/`` cache.
Use for research/backtest, not during live trading hours.

Safe vs live agent
------------------
**Safe / offline:** Read-only vs live agent except writing replay JSON under
``state/learning/``. Does not start ``main.py`` or execute paper trades.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.ivolatility_client import DATA_ROOT  # noqa: E402
from evaluation.spy_qqq_replay import (  # noqa: E402
    PATH_A_EXCLUSION_NOTE,
    replay_range,
    sanity_check_against_live,
    save_replay_records,
)


def _latest_cache_dir() -> Path:
    if not DATA_ROOT.exists():
        raise FileNotFoundError(f"No cache under {DATA_ROOT}. Run ingest first.")
    dirs = sorted([p for p in DATA_ROOT.iterdir() if p.is_dir()], key=lambda p: p.name)
    if not dirs:
        raise FileNotFoundError(f"No cache dirs under {DATA_ROOT}")
    return dirs[-1]


def main() -> int:
    """CLI entry: replay Path B from IVolatility cache and optional live sanity check."""
    parser = argparse.ArgumentParser(description="SPY/QQQ historical Path B replay")
    parser.add_argument("--cache-dir", default="", help="IVolatility cache directory")
    parser.add_argument("--sanity-date", default="2026-07-22")
    parser.add_argument("--skip-sanity", action="store_true")
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "state" / "learning" / "spy_qqq_replay_records.json"),
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir) if args.cache_dir else _latest_cache_dir()
    print(f"[replay] cache={cache_dir}")
    print(f"[replay] {PATH_A_EXCLUSION_NOTE}")
    rows = replay_range(cache_dir)
    out = save_replay_records(rows, Path(args.out))
    print(f"[replay] wrote {len(rows)} records → {out}")

    if not args.skip_sanity:
        report = sanity_check_against_live(rows, sanity_date=args.sanity_date)
        print("[replay] sanity:", json.dumps(report, indent=2, default=str))
        sanity_path = Path(args.out).with_name("spy_qqq_replay_sanity.json")
        sanity_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        if not report.get("ok"):
            print("[replay] SANITY CHECK FAILED")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
