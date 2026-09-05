#!/usr/bin/env python3
"""Run live-screener Adam classification-threshold calibration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apps.research_screener.methodologies.adam_calibration import (
    load_experiment,
    run_classification_threshold_sweep,
    write_threshold_report,
)

DEFAULT_EXPERIMENT = (
    ROOT / "tests" / "fixtures" / "calibration" / "adam_classification_threshold_profiles.json"
)
DEFAULT_OUTPUT = (
    ROOT / "reports" / "calibration" / "adam_classification_threshold_live_profiles.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--experiment",
        type=Path,
        default=DEFAULT_EXPERIMENT,
        help="Adam classification threshold profile fixture",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Write JSON + Markdown report paths",
    )
    args = parser.parse_args()

    experiment = load_experiment(args.experiment.resolve())
    report = run_classification_threshold_sweep(experiment)
    write_threshold_report(report, args.output.resolve())
    print(f"Wrote {args.output.resolve()}")
    print(f"Wrote {args.output.resolve().with_suffix('.md')}")
    print(f"Recommendation: {report.recommendation['action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
