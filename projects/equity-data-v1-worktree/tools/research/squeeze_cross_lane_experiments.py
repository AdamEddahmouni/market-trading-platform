#!/usr/bin/env python3
"""Cross-lane squeeze research harness — JQ-2/JQ-3/JQ-5 incremental lift."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQUEEZE_CORE = ROOT.parent / "short-squeeze-project" / "short-squeeze-core"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SQUEEZE_CORE / "src"))

from squeeze_core.intelligence.evaluator import (  # noqa: E402
    AdamSnapshot,
    CrossLaneSnapshot,
    evaluate_squeeze_intelligence,
)

MECHANISM_FIXTURE = ROOT / "tests" / "fixtures" / "squeeze" / "mechanism_labels.json"
OUTPUT_DIR = ROOT / "reports" / "research" / "squeeze_cross_lane"


def _ignition_detected(state: str) -> bool:
    return state in {
        "IGNITION_WATCH",
        "LIVE_CONFIRMATION",
        "ACTIVE_SQUEEZE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Squeeze cross-lane experiment harness")
    parser.add_argument("--fixture", type=Path, default=MECHANISM_FIXTURE)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    payload = json.loads(args.fixture.read_text(encoding="utf-8"))
    cases = payload.get("rows", payload.get("cases", []))
    if not isinstance(cases, list):
        raise SystemExit("fixture missing cases[]")

    baseline_hits = 0
    catalyst_hits = 0
    options_hits = 0
    combined_hits = 0
    total = 0

    for case in cases:
        if not isinstance(case, dict):
            continue
        squeeze_context = case.get("squeeze_context") if isinstance(case.get("squeeze_context"), dict) else {}
        adam = AdamSnapshot(
            pressure=float(squeeze_context.get("pressure", case.get("pressure", 50.0))),
            ignition=float(squeeze_context.get("ignition", case.get("ignition", 40.0))),
            classification=str(squeeze_context.get("classification", case.get("classification", "WATCH"))),
        )
        total += 1
        base = evaluate_squeeze_intelligence(rules=(), adam=adam)
        cat = evaluate_squeeze_intelligence(
            rules=(),
            adam=adam,
            cross_lane=CrossLaneSnapshot(catalyst_available=True, catalyst_strength=75.0),
        )
        opt = evaluate_squeeze_intelligence(
            rules=(),
            adam=adam,
            cross_lane=CrossLaneSnapshot(
                options_available=True,
                options_gamma_amplification=True,
                options_hedging_pressure=2.0,
            ),
        )
        combo = evaluate_squeeze_intelligence(
            rules=(),
            adam=adam,
            cross_lane=CrossLaneSnapshot(
                catalyst_available=True,
                catalyst_strength=75.0,
                options_available=True,
                options_gamma_amplification=True,
                options_hedging_pressure=2.0,
            ),
        )
        if _ignition_detected(base.state.value):
            baseline_hits += 1
        if _ignition_detected(cat.state.value):
            catalyst_hits += 1
        if _ignition_detected(opt.state.value):
            options_hits += 1
        if _ignition_detected(combo.state.value):
            combined_hits += 1

    report = {
        "fixture": str(args.fixture),
        "case_count": total,
        "baseline_ignition_rate": baseline_hits / total if total else 0.0,
        "with_catalyst_ignition_rate": catalyst_hits / total if total else 0.0,
        "with_options_ignition_rate": options_hits / total if total else 0.0,
        "with_combined_ignition_rate": combined_hits / total if total else 0.0,
        "catalyst_lift": (catalyst_hits - baseline_hits) / total if total else 0.0,
        "options_lift": (options_hits - baseline_hits) / total if total else 0.0,
        "combined_lift": (combined_hits - baseline_hits) / total if total else 0.0,
        "research_questions": ["JQ-2", "JQ-3", "JQ-5"],
    }

    args.output.mkdir(parents=True, exist_ok=True)
    out_path = args.output / "cross_lane_lift_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
