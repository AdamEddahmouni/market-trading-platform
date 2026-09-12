"""Emit read-only FTEP campaign status JSON."""

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
    parser.add_argument(
        "--probe-local",
        action="store_true",
        help="Probe loopback ports when composing readiness (never external hosts)",
    )
    args = parser.parse_args(argv)

    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from market_platform_foundation.intelligence.paper_forward_bridge.campaign_status import (
        collect_ftep_campaign_status,
    )

    payload = collect_ftep_campaign_status(ROOT, args.campaign_slug)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"campaign={payload['campaign_slug']} "
            f"rth_open={payload['us_equity_rth_open']} "
            f"readiness={payload['campaign_readiness_disposition']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
