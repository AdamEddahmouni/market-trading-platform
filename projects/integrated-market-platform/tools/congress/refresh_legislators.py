"""Refresh the local public congress-legislators registry (CC0-1.0) used for member identity.

The Screener refreshes a missing or week-old copy in the background on its own when
``IMP_PUBLIC_RECORDS_LIVE=1``; this command does the same explicitly.

    python tools/congress/refresh_legislators.py           # download + validate + manifest
    python tools/congress/refresh_legislators.py --check   # report the local copy; no network
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.congressional_ptr import legislators_registry as legislators  # noqa: E402
from market_platform_foundation.local_state.external_cache import imp_cache_dir  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report the local copy only; never download")
    args = parser.parse_args(argv)
    cache_dir = imp_cache_dir() / legislators.CACHE_RELATIVE
    if not args.check:
        try:
            legislators.refresh(cache_dir)
        except legislators.RegistryRefreshError as exc:
            print(json.dumps({"state": "REFRESH_FAILED", "reason": str(exc)}))
            return 2
    cached = legislators.load(cache_dir)
    print(json.dumps({**cached.describe(), "members": len(cached.registry.members) if cached.registry else 0,
                      "cache_dir": str(cache_dir)}, indent=2))
    return 0 if cached.registry is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
