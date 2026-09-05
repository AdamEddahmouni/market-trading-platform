"""Run the Phase 3E Stage 2 pipeline (outcomes, leakage audit, Phase 3B/3C).

Usage (from ``short-squeeze-core``)::

    python scripts/acquisition/run_stage2_pipeline.py
    python scripts/acquisition/run_stage2_pipeline.py --offline
    python scripts/acquisition/run_stage2_pipeline.py --force
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from squeeze_core.acquisition.stage2.constants import STAGE2_BUILD_ROOT  # noqa: E402
from squeeze_core.acquisition.stage2.pipeline import (  # noqa: E402
    Stage2PipelineConfig,
    run_stage2_pipeline,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use synthetic Batch 05 fixtures instead of live intake.",
    )
    parser.add_argument(
        "--batch05-root",
        type=Path,
        default=None,
        help="Override Batch 05 private root.",
    )
    parser.add_argument(
        "--freeze-root",
        type=Path,
        default=None,
        help="Override Phase 3A freeze output root.",
    )
    parser.add_argument(
        "--stage2-root",
        type=Path,
        default=STAGE2_BUILD_ROOT,
        help="Stage 2 build output root.",
    )
    parser.add_argument(
        "--skip-freeze",
        action="store_true",
        help="Skip Phase 3A freeze generation (assume freeze artifacts exist).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild all Stage 2 outputs even when present.",
    )
    parser.add_argument(
        "--cohort",
        choices=("frozen", "batch3f05", "all"),
        default="frozen",
        help="Cohort track for Stage 2 (default: jul-18 frozen cohort).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = Stage2PipelineConfig(
        repo_root=REPO_ROOT,
        batch05_root=args.batch05_root,
        freeze_root=args.freeze_root,
        stage2_root=args.stage2_root,
        offline=args.offline,
        skip_freeze=args.skip_freeze,
        force=args.force,
        cohort_track=args.cohort,
    )
    result = run_stage2_pipeline(config)
    print(json.dumps(
        {
            "summary_path": str(result.summary_path),
            "leakage_passed": len(result.passed_leakage),
            "failed_symbols": list(result.failed_symbols),
            "steps": result.steps,
        },
        indent=2,
    ))
    return 1 if result.failed_symbols and not result.passed_leakage else 0


if __name__ == "__main__":
    raise SystemExit(main())
