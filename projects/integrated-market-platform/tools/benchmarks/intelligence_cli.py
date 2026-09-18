"""CLI: imp benchmark intelligence (IBP harness integration)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.benchmark_protocol import (  # noqa: E402
    adapt_historical_research_run_manifest_v1,
    assess_benchmark_smoke10_readiness,
    build_smoke10_invocation_contract,
    load_suite_catalog,
    suite_catalog_fingerprint,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)

    readiness = actions.add_parser("readiness", help="Smoke10 wiring readiness (no scores)")
    readiness.add_argument("--json", action="store_true")

    adapt = actions.add_parser(
        "adapt",
        help="adapt historical_research_run_manifest_v1 JSON to IBP run record",
    )
    adapt.add_argument("--manifest", type=Path, required=True)
    adapt.add_argument("--json", action="store_true")

    smoke10 = actions.add_parser(
        "smoke10-plan",
        help="emit Smoke10 invocation contract (scores NOT executed)",
    )
    smoke10.add_argument("--manifest", type=Path, help="optional historical harness manifest")
    smoke10.add_argument("--json", action="store_true")

    suite_info = actions.add_parser("suite-info", help="print suite catalog metadata")
    suite_info.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.action == "readiness":
        payload = assess_benchmark_smoke10_readiness(ROOT)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"BENCHMARK_SMOKE10_READY={payload['BENCHMARK_SMOKE10_READY']}")
            for reason in payload.get("reasons", []):
                print(f"reason: {reason}")
        return 0 if payload["BENCHMARK_SMOKE10_READY"] == "YES" else 1

    if args.action == "suite-info":
        catalog = load_suite_catalog(ROOT)
        payload = {
            "suite_id": catalog.get("suite_id"),
            "case_count": len(catalog.get("cases", [])),
            "smoke10_case_ids": catalog.get("smoke10_case_ids"),
            "suite_catalog_fingerprint": suite_catalog_fingerprint(catalog),
            "scores_executed": False,
        }
        print(json.dumps(payload, indent=2, sort_keys=True) if args.json else json.dumps(payload))
        return 0

    if args.action == "adapt":
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        catalog = load_suite_catalog(ROOT)
        record = adapt_historical_research_run_manifest_v1(
            manifest,
            suite_id=catalog.get("suite_id"),
            suite_catalog_fingerprint=suite_catalog_fingerprint(catalog),
        )
        print(json.dumps(record, indent=2, sort_keys=True))
        return 0

    if args.action == "smoke10-plan":
        historical_record = None
        if args.manifest is not None:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            catalog = load_suite_catalog(ROOT)
            historical_record = adapt_historical_research_run_manifest_v1(
                manifest,
                suite_id=catalog.get("suite_id"),
                suite_catalog_fingerprint=suite_catalog_fingerprint(catalog),
            )
        contract = build_smoke10_invocation_contract(ROOT, historical_run_record=historical_record)
        print(json.dumps(contract, indent=2, sort_keys=True))
        return 0

    print(f"unknown action: {args.action}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
