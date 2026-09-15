"""Validate ``ftep_catalyst_watch_report`` JSON for Finviz prospective ingress."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to ftep_catalyst_watch_report JSON")
    parser.add_argument(
        "--context",
        type=Path,
        help="Optional capture-context sidecar JSON (runtime SHA, artifact hash)",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable validation JSON")
    args = parser.parse_args(argv)

    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from market_platform_foundation.intelligence.paper_forward_bridge.finviz_prospective_receipt_validator import (
        VERDICT_INVALID,
        load_context_json,
        load_report_json,
        validate_finviz_prospective_receipt,
    )

    report = load_report_json(args.report.resolve())
    context = load_context_json(args.context.resolve()) if args.context else None
    result = validate_finviz_prospective_receipt(
        report,
        artifact_path=args.report.resolve(),
        context=context,
    )
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"verdict={result['verdict']}")
        for code in result.get("reason_codes") or []:
            print(f"  {code}")
    return 1 if result["verdict"] == VERDICT_INVALID else 0


if __name__ == "__main__":
    raise SystemExit(main())
