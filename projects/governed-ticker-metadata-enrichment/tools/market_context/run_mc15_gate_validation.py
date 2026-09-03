"""Run MC15 cross-entity propagation gate validation on admitted BOXL/NVDA fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "evidence/market_context/mc15-gate-validation-report.json"

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import write_canonical_json  # noqa: E402
from market_platform_foundation.market_context.propagation import (  # noqa: E402
    run_mc15_gate_validation,
)
from market_platform_foundation.offline_guard import install_guard  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MC15 cross-entity propagation gate report")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path for canonical validation report JSON",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print report summary to stdout without writing output file",
    )
    return parser.parse_args()


def main() -> int:
    install_guard([])
    args = parse_args()
    report = run_mc15_gate_validation()
    if args.dry_run:
        summary = {
            "aggregate_status": report.get("aggregate_status"),
            "gate_summary": report.get("gate_summary"),
            "propagation_count": report.get("propagation_count"),
            "fixture_refs": report.get("fixture_refs"),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        output_path = Path(args.output).resolve()
        write_canonical_json(output_path, report)
        print(
            json.dumps(
                {
                    "aggregate_status": report.get("aggregate_status"),
                    "output": str(output_path.relative_to(ROOT)),
                },
                sort_keys=True,
            )
        )
    return 0 if report.get("aggregate_status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
