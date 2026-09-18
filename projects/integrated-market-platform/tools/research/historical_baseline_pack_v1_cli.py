"""Lane C: Frozen Historical Baseline Pack v1 (HISTORICAL_DEVELOPMENT / fixture corpus)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.historical_research_harness import (  # noqa: E402
    historical_research_governance_lines,
)
from market_platform_foundation.intelligence.historical_research_harness.baseline_pack import (  # noqa: E402
    DEFAULT_MULTI_SESSION_FIXTURE_REL,
    HISTORICAL_BASELINE_PACK_V1,
    build_frozen_baseline_pack_experiment_definition,
    experiment_definition_hash,
    freeze_baseline_pack_definition_to_disk,
    run_frozen_historical_baseline_pack_v1,
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
    parser.add_argument("--instrument", default="AAPL")
    parser.add_argument("--start", default="2026-09-11", dest="start_date")
    parser.add_argument("--end", default="2026-09-15", dest="end_date")
    parser.add_argument(
        "--fixture-path",
        type=Path,
        default=ROOT / DEFAULT_MULTI_SESSION_FIXTURE_REL,
    )
    parser.add_argument("--corpus-artifact-root", type=Path)
    parser.add_argument("--pack-artifact-root", type=Path)
    parser.add_argument(
        "--frozen-definition",
        type=Path,
        help="Optional pre-frozen experiment definition JSON (must match dataset fingerprint).",
    )
    parser.add_argument("--freeze-only", action="store_true", help="Write frozen definition and exit.")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for line in historical_research_governance_lines():
        print(line, file=sys.stderr)
    print(f"EVIDENCE_LABEL: {HISTORICAL_BASELINE_PACK_V1}", file=sys.stderr)
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
        print(json.dumps({"ok": False, "stage": "corpus_build", "reason_code": build.reason_code}))
        return 1

    dataset_identity = {
        "dataset_id": str(build.manifest.get("dataset_id") or build.run_id),
        "dataset_fingerprint": str(build.manifest.get("dataset_fingerprint") or build.normalized_fingerprint),
        "provider_id": "fixture.historical",
        "fixture_path": str(args.fixture_path.relative_to(ROOT)),
        "instrument": args.instrument,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "session_dates": list((build.manifest.get("interval") or {}).get("session_dates") or []),
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    }

    if args.frozen_definition is not None:
        frozen = json.loads(args.frozen_definition.read_text(encoding="utf-8"))
    else:
        frozen_path, frozen = freeze_baseline_pack_definition_to_disk(
            repository_root=ROOT,
            dataset_identity=dataset_identity,
            artifact_root=args.pack_artifact_root,
        )
        if not args.freeze_only:
            print(f"frozen_experiment_definition: {frozen_path}", file=sys.stderr)

    if args.freeze_only:
        payload = {
            "ok": True,
            "stage": "freeze",
            "evidence_label": HISTORICAL_BASELINE_PACK_V1,
            "experiment_definition_hash": experiment_definition_hash(frozen),
            "dataset_fingerprint": dataset_identity["dataset_fingerprint"],
            "frozen_definition_path": str(
                (args.pack_artifact_root or ROOT / "artifacts/historical-research-harness/baseline-pack-v1")
                / "frozen_experiment_definition.json"
            ),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    pack_result = run_frozen_historical_baseline_pack_v1(
        repository_root=ROOT,
        build=build,
        frozen_definition=frozen,
        artifact_root=args.pack_artifact_root,
        deterministic_rerun=True,
    )
    payload = {
        "ok": pack_result.ok,
        "evidence_label": HISTORICAL_BASELINE_PACK_V1,
        "authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "pack_run_id": pack_result.pack_run_id,
        "experiment_definition_hash": pack_result.experiment_definition_hash,
        "dataset_fingerprint": pack_result.dataset_fingerprint,
        "dataset_identity": dataset_identity,
        "reproducibility": pack_result.body.get("reproducibility") if pack_result.ok else None,
        "contamination_audit": pack_result.body.get("contamination_audit") if pack_result.ok else None,
        "baseline_results": pack_result.body.get("baseline_results") if pack_result.ok else None,
        "artifact_dir": str(pack_result.artifact_dir) if pack_result.ok else None,
        "reason_code": pack_result.reason_code,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if pack_result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
