#!/usr/bin/env python3
"""Run a Phase 3D calibration experiment and write evidence reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.calibration import run_calibration_from_path, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--experiment",
        required=True,
        type=Path,
        help="Path to calibration experiment JSON",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output JSON report path (Markdown written alongside with .md suffix)",
    )
    args = parser.parse_args()
    report = run_calibration_from_path(args.experiment.resolve())
    write_report(report, args.output.resolve())
    print(f"Wrote {args.output.resolve()}")
    print(f"Wrote {args.output.resolve().with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
