#!/usr/bin/env python3
"""Emit the Phase 4 item 1.3 NOT_CALIBRATED report skeleton.

Runs the preregistered feasibility-gate ladder (preregistration §8.1) over the
committed dataset labels and the 1.2 walk-forward diagnostics, and writes the
report skeleton to ``reports/calibration/phase_4_fit_report_skeleton.json`` and
``.md``.

This is **not a fit**: no model is estimated, no probability is produced, and
the fitting stage stays blocked on preregistration §10 (O-2/O-3/O-4/O-6). The
report's purpose is sprint 1.3's honesty contract: the failing gate(s) are
named, `RESEARCH_ONLY` slots are retained, and nothing is force-flipped to
`CALIBRATED`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.calibration.fit_report import (
    build_fit_report_skeleton,
    render_fit_report_markdown,
)
from squeeze_core.calibration.walkforward import (
    boundary_observations_from_bytes,
    plan_walk_forward_folds,
    walk_forward_diagnostics,
)
from squeeze_core.research.serialization import deserialize_research_dataset

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "research"
DATASET_PATH = FIXTURE_DIR / "phase_3b_research_dataset.json"


def _markdown(report) -> str:
    return render_fit_report_markdown(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "reports" / "calibration",
        help="Directory for the JSON skeleton + Markdown report",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = deserialize_research_dataset(DATASET_PATH.read_bytes())

    observations = []
    for path in sorted(FIXTURE_DIR.glob("*_outcome_observation.json")):
        observations.extend(
            boundary_observations_from_bytes(path.read_bytes(), str(path))
        )
    if not observations:
        raise SystemExit(f"no outcome-observation fixtures found under {FIXTURE_DIR}")

    from squeeze_core.calibration.fit_report import _counts_from_dataset

    counts = _counts_from_dataset(dataset)
    diagnostics = walk_forward_diagnostics(plan_walk_forward_folds(observations))
    report = build_fit_report_skeleton(counts, diagnostics)

    json_path = output_dir / "phase_4_fit_report_skeleton.json"
    json_path.write_text(
        report.model_dump_json(indent=2, by_alias=False) + "\n", encoding="utf-8"
    )
    md_path = output_dir / "phase_4_fit_report_skeleton.md"
    md_path.write_text(_markdown(report), encoding="utf-8")

    print(f"Verdict: {report.verdict.value}")
    print(
        "Failing gates: "
        + (", ".join(gate.value for gate in report.failing_gates) or "none")
    )
    print(
        "Not structurally evaluable: "
        + (", ".join(gate.value for gate in report.unevaluated_gates) or "none")
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
