"""Governed CLI: imp historical-data demo (Lane D e2e, HISTORICAL_DEVELOPMENT only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.market_data.historical_development import (  # noqa: E402
    FixtureHistoricalMarketDataProvider,
    build_historical_rth_dataset,
)
from market_platform_foundation.market_data.historical_development.e2e_demo import (  # noqa: E402
    default_demo_artifact_root,
    historical_development_governance_lines,
    run_historical_development_e2e_demo,
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
    parser.add_argument("--corpus-artifact-root", type=Path, help="Lane B artifact root override")
    parser.add_argument("--demo-artifact-root", type=Path, help="Lane D e2e result root override")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for line in historical_development_governance_lines():
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
    demo_root = args.demo_artifact_root or default_demo_artifact_root(ROOT)
    e2e = run_historical_development_e2e_demo(
        repository_root=ROOT,
        build=build,
        demo_artifact_root=demo_root,
    )
    payload = {
        "ok": e2e.ok,
        "evidence_class": "HISTORICAL_DEVELOPMENT_ONLY",
        "lane_b_run_id": build.run_id,
        "dataset_fingerprint": build.manifest.get("dataset_fingerprint"),
        "normalized_fingerprint": build.normalized_fingerprint,
        "quality_fingerprint": build.quality.get("quality_fingerprint"),
        "feature_root_hash": e2e.body.get("feature_replay", {}).get("feature_root_hash"),
        "risk_simulation_root_hash": e2e.body.get("risk_simulation", {}).get(
            "risk_simulation_root_hash"
        ),
        "result_fingerprint": e2e.body.get("result_fingerprint"),
        "e2e_artifact_path": str(e2e.artifact_path) if e2e.ok else None,
        "reason_code": e2e.reason_code,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if e2e.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
