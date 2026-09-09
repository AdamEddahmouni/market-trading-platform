#!/usr/bin/env python3
"""Emit the Phase 4 walk-forward fold plan and structural diagnostics (sprint 1.2).

Reads the committed historical outcome-observation fixtures, builds the
chronological symbol-grouped walk-forward plan with the pre-registered
purge/embargo windows (O-2 addendum: 30 / 15 calendar days), and writes the
plan + diagnostics to ``reports/calibration/phase_4_walk_forward_plan.json``
and ``.md``.

This is **structure only**: no model is fit, no probability is produced, and
no outcome label is consumed (preregistration §1; sprint item 1.3 is gated on
the open items in its §10).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.calibration.walkforward import (
    EMBARGO_CALENDAR_DAYS,
    PURGE_CALENDAR_DAYS,
    RegimeSlice,
    boundary_observations_from_bytes,
    plan_walk_forward_folds,
    walk_forward_diagnostics,
)

FIXTURE_DIR = ROOT / "tests" / "fixtures" / "research"


def _load_boundaries() -> tuple:
    observations = []
    for path in sorted(FIXTURE_DIR.glob("*_outcome_observation.json")):
        observations.extend(
            boundary_observations_from_bytes(path.read_bytes(), str(path))
        )
    if not observations:
        raise SystemExit(f"no outcome-observation fixtures found under {FIXTURE_DIR}")
    return tuple(observations)


def _markdown(diag, plan) -> str:
    lines = [
        "# Phase 4 — Walk-forward fold plan (structure only)",
        "",
        f"- Harness: `{diag.harness_version}`",
        f"- Preregistration: `{diag.preregistration_version}`",
        f"- Boundaries: {diag.boundary_count} ({diag.symbol_count} symbol clusters)",
        f"- Folds: {diag.fold_count} "
        f"({diag.non_empty_evaluation_fold_count} non-empty evaluation; "
        f"{diag.folds_with_empty_training} with empty training)",
        f"- Purge/embargo: {diag.purge_calendar_days} / {diag.embargo_calendar_days} "
        "calendar days (O-2 addendum §4)",
        f"- Degenerate: **{'YES' if diag.degenerate else 'no'}**"
        + (f" — {diag.degeneracy_reason}" if diag.degeneracy_reason else ""),
        "",
        "## Regime slices (recorded, never padded)",
        "",
        "| Slice | Boundaries |",
        "|---|---:|",
    ]
    for regime in RegimeSlice:
        count = diag.regime_counts.get(regime, 0)
        marker = " (empty)" if count == 0 and regime is not RegimeSlice.UNASSIGNED else ""
        lines.append(f"| `{regime.value}` | {count}{marker} |")
    lines.extend(
        [
            "",
            "## Folds",
            "",
            "| Fold | Evaluation | Training | Purge window | Embargo window |",
            "|---|---|---|---|---|",
        ]
    )
    for fold, row in zip(plan.folds, diag.folds):
        lines.append(
            f"| {fold.fold_index} | {row.evaluation_boundary_count} boundaries "
            f"({', '.join(fold.evaluation_symbols)}) | {row.train_boundary_count} boundaries | "
            f"{fold.purge_window_start.date()} → {fold.purge_window_end.date()} | "
            f"{fold.embargo_window_start.date()} → {fold.embargo_window_end.date()} |"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
        ]
    )
    for code in diag.limitations:
        lines.append(f"- `{code}`")
    lines.extend(
        [
            "",
            "## Honest structural note",
            "",
            "This plan partitions the owned 24-hour outcome labels only. Where a",
            "fold shows zero admissible training boundaries, that fact is the",
            "finding: fitting (sprint item 1.3) must report the structure as-is,",
            "keep the evaluator's `RESEARCH_ONLY` horizon slots, and never",
            "re-shuffle splits or backfill probabilities into unsupported",
            "horizons (preregistration §2.3, §7, §8).",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "reports" / "calibration",
        help="Directory for the JSON plan + Markdown summary",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    boundaries = _load_boundaries()
    plan = plan_walk_forward_folds(boundaries)
    diag = walk_forward_diagnostics(plan)

    json_path = output_dir / "phase_4_walk_forward_plan.json"
    json_path.write_text(
        plan.model_dump_json(indent=2, by_alias=False) + "\n", encoding="utf-8"
    )
    md_path = output_dir / "phase_4_walk_forward_plan.md"
    md_path.write_text(_markdown(diag, plan), encoding="utf-8")

    print(f"Boundaries: {diag.boundary_count} across {diag.symbol_count} symbol clusters")
    print(f"Folds: {diag.fold_count} (degenerate={diag.degenerate})")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
