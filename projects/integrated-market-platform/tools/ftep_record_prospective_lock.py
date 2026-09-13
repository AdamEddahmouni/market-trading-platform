"""FTEP prospective decision-lock gate (dry-run only; no lock writes)."""

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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate lock gates only (required; no durable writes)",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Force campaign attention fixture for catalyst qualification",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Optional JSON file with attention-candidate rows",
    )
    args = parser.parse_args(argv)

    if not args.dry_run:
        print(
            "record-prospective-lock requires --dry-run (no live lock writes in this wave)",
            file=sys.stderr,
        )
        return 2

    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from market_platform_foundation.intelligence.paper_forward_bridge.ftep_prospective_lock import (
        collect_ftep_prospective_lock_gates,
    )

    payload = collect_ftep_prospective_lock_gates(
        ROOT,
        args.campaign_slug,
        fixture_only=args.fixture,
        input_path=args.input,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"would_record_lock={payload['would_record_lock']} "
            f"blockers={payload['blockers']}"
        )
    return 0 if payload["would_record_lock"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
