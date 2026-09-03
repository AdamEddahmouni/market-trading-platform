#!/usr/bin/env python3
"""Run the Phase 3D calibration suite in evidence-optimal order.

Order:
  1. Outcome sensitivity (synthetic) — establishes outcome label stability
  2. Outcome sensitivity (historical) — tests real-case threshold boundaries
  3. Detection predicate candidates (synthetic) — evaluates predicate variants
  4. Detection predicate candidates (historical) — validates on BIYA boundaries
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.calibration import run_calibration_from_path, write_report

FIXTURES = ROOT / "tests" / "fixtures" / "calibration"

SUITE = (
    ("outcome_sensitivity_synthetic", FIXTURES / "outcome_sensitivity_synthetic.json"),
    ("outcome_sensitivity_historical", FIXTURES / "outcome_sensitivity_historical.json"),
    (
        "detection_predicate_candidates_synthetic",
        FIXTURES / "detection_predicate_candidates_synthetic.json",
    ),
    (
        "detection_predicate_candidates_historical",
        FIXTURES / "detection_predicate_candidates_historical.json",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "reports" / "calibration",
        help="Directory for JSON + Markdown reports",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, experiment_path in SUITE:
        output_path = output_dir / f"{name}.json"
        report = run_calibration_from_path(experiment_path.resolve())
        write_report(report, output_path)
        print(f"Wrote {output_path}")
        print(f"Wrote {output_path.with_suffix('.md')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
