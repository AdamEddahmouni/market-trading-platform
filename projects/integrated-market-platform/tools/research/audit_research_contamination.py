"""Audit a research run manifest for contractual contamination (IMP-OFFHOURS-RESEARCH-03).

Usage:
    python tools/research/audit_research_contamination.py --manifest path/to/manifest.json
    python tools/research/audit_research_contamination.py --manifest path/to/manifest.json --report out.json

Exit code 0 when CONTAMINATION_STATUS=PASS; non-zero otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import load_json_strict, write_canonical_json
from market_platform_foundation.paper.calibration.dual_corpus.contamination_auditor import (
    CONTAMINATION_STATUS_PASS,
    audit_research_contamination_run,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Research contamination auditor")
    parser.add_argument("--manifest", type=Path, required=True, help="Research contamination run manifest JSON")
    parser.add_argument("--report", type=Path, default=None, help="Optional output report path")
    args = parser.parse_args(argv)

    manifest = load_json_strict(args.manifest)
    report = audit_research_contamination_run(manifest)
    if args.report is not None:
        write_canonical_json(args.report, report)
    else:
        import json

        print(json.dumps(report, indent=2, sort_keys=True))

    return 0 if report.get("CONTAMINATION_STATUS") == CONTAMINATION_STATUS_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
