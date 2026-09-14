"""Track E Wave 1 experiment harness CLI (infrastructure smoke / reproducibility receipt).

Does not authorize OOS on non-empirical exports. Real OOS requires Track D
Research Export with ``metadata.pit_status == PIT-PASS``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import load_json_strict, write_canonical_json
from market_platform_foundation.research.wave1.config import load_frozen_registry
from market_platform_foundation.research.wave1.runner import (
    run_wave1_from_export_stub,
    run_wave1_registry,
    wave1_run_report_to_dict,
)

DEFAULT_EXPORT = ROOT / "tests" / "fixtures" / "research" / "wave1_non_empirical_export.json"
DEFAULT_EXAMPLES = ROOT / "tests" / "fixtures" / "research" / "wave1_examples.json"
DEFAULT_REPORT = ROOT / "artifacts" / "research" / "wave1-harness-report.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track E Wave 1 experiment harness")
    parser.add_argument("--export", type=Path, default=DEFAULT_EXPORT)
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--registry", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--allow-oos",
        action="store_true",
        help="Attempt OOS evaluation (fail-closed unless export is PIT-PASS and empirical)",
    )
    args = parser.parse_args(argv)

    registry = load_frozen_registry(args.registry)
    export_manifest = load_json_strict(args.export)
    if not isinstance(export_manifest, dict):
        raise SystemExit("EXPORT_MANIFEST_INVALID")
    examples_raw = load_json_strict(args.examples)
    if not isinstance(examples_raw, list):
        raise SystemExit("EXAMPLES_FIXTURE_INVALID")

    if export_manifest.get("wave1_examples"):
        report = run_wave1_from_export_stub(
            export_manifest,
            registry_path=args.registry,
            allow_oos=args.allow_oos,
        )
    else:
        report = run_wave1_registry(
            [dict(row) for row in examples_raw],
            registry=registry,
            export_manifest=export_manifest,
            allow_oos=args.allow_oos,
        )

    payload = wave1_run_report_to_dict(report)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    write_canonical_json(args.report, payload)
    print(f"wave1_harness run_id={report.run_id} oos_mode={report.oos_mode} families={len(report.family_results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
