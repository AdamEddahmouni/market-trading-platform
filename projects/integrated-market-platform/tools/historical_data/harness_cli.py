"""Governed CLI: imp historical-data harness (HISTORICAL_DEVELOPMENT research pipeline)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.historical_research_harness import (  # noqa: E402
    ChronologicalSplitPolicy,
    HistoricalResearchRunConfig,
    historical_research_governance_lines,
    run_historical_research_harness,
)
from market_platform_foundation.market_data.historical_development import (  # noqa: E402
    FixtureHistoricalMarketDataProvider,
    build_historical_rth_dataset,
)
from market_platform_foundation.market_data.historical_development.provider import (  # noqa: E402
    load_fixture_rows_from_json,
)
from market_platform_foundation.paper.calibration.dual_corpus import (  # noqa: E402
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    evaluate_item9_prospective_corpus_admission,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="fixture", choices=("fixture",))
    parser.add_argument("--instrument", default="AAPL")
    parser.add_argument("--start", required=True, dest="start_date")
    parser.add_argument("--end", required=True, dest="end_date")
    parser.add_argument("--fixture-path", type=Path, required=True)
    parser.add_argument("--corpus-artifact-root", type=Path)
    parser.add_argument("--harness-artifact-root", type=Path)
    parser.add_argument("--experiment-id", default="hist-research-default-experiment")
    parser.add_argument("--hypothesis-id", default="hist-research-default-hypothesis")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for line in historical_research_governance_lines():
        print(line)
    admission = evaluate_item9_prospective_corpus_admission(
        corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
    )
    if admission.get("disposition") != "REFUSED":
        print("historical authority must refuse Item 9 admission", file=sys.stderr)
        return 1
    provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(args.fixture_path))
    build = build_historical_rth_dataset(
        repository_root=ROOT,
        provider=provider,
        instrument=args.instrument,
        start_date=args.start_date,
        end_date=args.end_date,
        artifact_root=args.corpus_artifact_root,
        fixture_only=True,
    )
    if not build.ok:
        payload = {"ok": False, "stage": "lane_b_build", "reason_code": build.reason_code}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    config = HistoricalResearchRunConfig(
        experiment_id=args.experiment_id,
        hypothesis_id=args.hypothesis_id,
        split_policy=ChronologicalSplitPolicy(),
    )
    result = run_historical_research_harness(
        repository_root=ROOT,
        build=build,
        config=config,
        artifact_root=args.harness_artifact_root,
    )
    payload = {
        "ok": result.ok,
        "evidence_class": "HISTORICAL_DEVELOPMENT_ONLY",
        "run_id": result.run_id,
        "dataset_fingerprint": build.manifest.get("dataset_fingerprint"),
        "run_fingerprint": result.body.get("run_fingerprint") if result.ok else None,
        "config_fingerprint": result.body.get("config_fingerprint") if result.ok else None,
        "research_code_sha": result.body.get("research_code_sha") if result.ok else None,
        "simulator_result_kind": (
            result.body.get("simulator", {}).get("result_kind") if result.ok else None
        ),
        "manifest_path": str(result.artifact_path) if result.ok else None,
        "reason_code": result.reason_code,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
