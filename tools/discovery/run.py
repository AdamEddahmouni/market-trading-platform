"""CLI discovery runner."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.discovery import DiscoveryEngine, list_screens


def main() -> int:
    parser = argparse.ArgumentParser(description="Run governed Finviz discovery screen")
    parser.add_argument("--screen", default="SHORT_SQUEEZE_DISCOVERY")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        print(json.dumps(list_screens(), indent=2))
        return 0
    engine = DiscoveryEngine()
    result = engine.run_screen(args.screen, force=args.force, persist=True)
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
