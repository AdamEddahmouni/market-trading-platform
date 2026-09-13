"""Emit deterministic FTEP integrity checks (read-only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug (default: FTEP-V1-002)",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity import (
        collect_ftep_integrity_checks,
    )

    payload = collect_ftep_integrity_checks(ROOT, args.campaign_slug)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"disposition={payload['disposition']} failed={payload['failed_check_ids']}")
        for hint in payload.get("operator_hints") or ():
            print(f"hint: {hint}", file=sys.stderr)
    return 0 if payload["disposition"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
