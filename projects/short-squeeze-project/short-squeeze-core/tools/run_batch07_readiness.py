#!/usr/bin/env python3
"""Generate Batch 07 operation-readiness report from the private Batch 05 intake root."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.acquisition.operation_readiness.report import build_report
from squeeze_core.acquisition.operation_readiness.serialization import render_markdown, serialize_report

DEFAULT_BATCH05_ROOT = ROOT / "intake" / "local-bars" / "ibkr-batch-05"
DEFAULT_JSON_OUT = ROOT / "reports" / "acquisition" / "batch07-operation-readiness-report.json"
DEFAULT_MD_OUT = ROOT / "reports" / "acquisition" / "batch07-operation-readiness-report.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch05-root",
        type=Path,
        default=DEFAULT_BATCH05_ROOT,
        help="Private Batch 05 intake root",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=DEFAULT_JSON_OUT,
        help="Canonical JSON report path",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=DEFAULT_MD_OUT,
        help="Markdown report path",
    )
    parser.add_argument(
        "--cohort",
        choices=("frozen", "batch3f05", "all"),
        default="all",
        help="Cohort track for readiness audit (default: combined frozen + batch3f05).",
    )
    args = parser.parse_args()

    report = build_report(args.batch05_root.resolve(), cohort_track=args.cohort)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_bytes(serialize_report(report))
    args.md_out.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    print(f"Wrote {args.json_out.resolve()}")
    print(f"Wrote {args.md_out.resolve()}")
    print(f"cases={len(report.cases)} report_id={report.deterministic_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
