"""Read-only FTEP catalyst watch (fixture dry-run; no locks or orders)."""

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
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Acknowledge read-only mode (no durable writes; default behavior)",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Force campaign attention fixture even when a governed session is active",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Optional JSON file with attention-candidate rows",
    )
    args = parser.parse_args(argv)

    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch import (
        collect_ftep_catalyst_watch,
    )

    payload = collect_ftep_catalyst_watch(
        ROOT,
        args.campaign_slug,
        fixture_only=args.fixture,
        input_path=args.input,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"mode={payload['watch_mode']} disposition={payload['disposition']}")
        print(f"summaries={payload['summary_count']} sessions={payload['governed_session_ids']}")
    return 0 if payload["disposition"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
