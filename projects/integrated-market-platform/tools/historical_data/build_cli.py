"""Governed CLI: imp historical-data build (HISTORICAL_DEVELOPMENT only)."""

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
    MoomooOpendHistoricalMarketDataProvider,
    build_historical_rth_dataset,
)
from market_platform_foundation.market_data.historical_development.provider import (  # noqa: E402
    load_fixture_rows_from_json,
)
from market_platform_foundation.paper.calibration.dual_corpus import (  # noqa: E402
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    evaluate_item9_prospective_corpus_admission,
)


def _print_governance_lines() -> None:
    print(f"AUTHORITY: {CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT}")
    print("PROSPECTIVE_ITEM9_ADMISSION: NOT_ALLOWED")
    print("CALIBRATION_STATE_CHANGED: NO")
    print("FTEP_STATE_CHANGED: NO")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", required=True, choices=("moomoo-opend", "fixture"))
    parser.add_argument("--instrument", required=True)
    parser.add_argument("--start", required=True, dest="start_date")
    parser.add_argument("--end", required=True, dest="end_date")
    parser.add_argument("--resolution", default="1m")
    parser.add_argument("--session", default="RTH")
    parser.add_argument("--fixture-path", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--holidays", default="", help="comma-separated YYYY-MM-DD")
    parser.add_argument("--early-closes", default="", help="comma-separated YYYY-MM-DD")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _print_governance_lines()
    if args.resolution != "1m":
        print("resolution must be 1m for Lane B", file=sys.stderr)
        return 2
    if str(args.session).upper() != "RTH":
        print("session must be RTH", file=sys.stderr)
        return 2
    holidays = frozenset(filter(None, str(args.holidays).split(",")))
    early_closes = frozenset(filter(None, str(args.early_closes).split(",")))
    if args.provider == "fixture":
        if args.fixture_path is None:
            print("--fixture-path required for fixture provider", file=sys.stderr)
            return 2
        provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(args.fixture_path))
        fixture_only = True
    else:
        provider = MoomooOpendHistoricalMarketDataProvider(repository_root=ROOT)
        fixture_only = False
    admission = evaluate_item9_prospective_corpus_admission(
        corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
    )
    if admission.get("disposition") != "REFUSED":
        print("historical authority must refuse Item 9 admission", file=sys.stderr)
        return 1
    result = build_historical_rth_dataset(
        repository_root=ROOT,
        provider=provider,
        instrument=args.instrument,
        start_date=args.start_date,
        end_date=args.end_date,
        artifact_root=args.artifact_root,
        holidays=holidays,
        early_closes=early_closes,
        fixture_only=fixture_only,
    )
    payload = {
        "ok": result.ok,
        "run_id": result.run_id,
        "reason_code": result.reason_code,
        "provider_verified": result.provider_status.verified,
        "provider_reason": result.provider_status.reason_code,
        "dataset_fingerprint": result.manifest.get("dataset_fingerprint"),
        "normalized_fingerprint": result.normalized_fingerprint,
        "quality_fingerprint": result.quality.get("quality_fingerprint"),
        "manifest_path": str(result.paths.manifests_dir / "dataset_manifest.json"),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
