#!/usr/bin/env python3
"""Run live-screener Adam calibration (Evidence-Gated Prime v1)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.research_screener.methodologies.adam_calibration import (
    load_experiment,
    run_classification_threshold_sweep,
    run_weight_floor_sweep,
    write_report,
    write_threshold_report,
)

DEFAULT_WEIGHT_EXPERIMENT = (
    ROOT / "tests" / "fixtures" / "calibration" / "adam_live_evidence_profiles.json"
)
DEFAULT_WEIGHT_OUTPUT = ROOT / "reports" / "calibration" / "adam_weight_floor_live_profiles.json"
DEFAULT_THRESHOLD_EXPERIMENT = (
    ROOT / "tests" / "fixtures" / "calibration" / "adam_classification_threshold_profiles.json"
)
DEFAULT_THRESHOLD_OUTPUT = (
    ROOT / "reports" / "calibration" / "adam_classification_threshold_live_profiles.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("weight-floor", "classification-thresholds"),
        default="weight-floor",
        help="Calibration sweep mode",
    )
    parser.add_argument(
        "--experiment",
        type=Path,
        default=None,
        help="Experiment fixture path (defaults per mode)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON + Markdown report paths (defaults per mode)",
    )
    args = parser.parse_args()

    if args.mode == "weight-floor":
        experiment_path = args.experiment or DEFAULT_WEIGHT_EXPERIMENT
        output_path = args.output or DEFAULT_WEIGHT_OUTPUT
        experiment = load_experiment(experiment_path.resolve())
        report = run_weight_floor_sweep(experiment)
        write_report(report, output_path.resolve())
    else:
        experiment_path = args.experiment or DEFAULT_THRESHOLD_EXPERIMENT
        output_path = args.output or DEFAULT_THRESHOLD_OUTPUT
        experiment = load_experiment(experiment_path.resolve())
        report = run_classification_threshold_sweep(experiment)
        write_threshold_report(report, output_path.resolve())

    print(f"Wrote {output_path.resolve()}")
    print(f"Wrote {output_path.resolve().with_suffix('.md')}")
    print(f"Recommendation: {report.recommendation['action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
