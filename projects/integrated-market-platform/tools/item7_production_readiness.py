"""CLI: Item 7 Lane B PRODUCTION forecast artifact readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.fusion.types import CalibrationMethod
from market_platform_foundation.intelligence.production.readiness import (
    STATUS_ARTIFACT_READY,
    assess_production_readiness,
    forecast_binding_refusal_reasons,
    scan_contributor_directory,
)
from market_platform_foundation.intelligence.production.training_build import build_path_a_production_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Item 7 PRODUCTION forecast readiness (Lane B).")
    sub = parser.add_subparsers(dest="command", required=True)

    assess = sub.add_parser("assess", help="Validate contributor + calibration operator paths.")
    assess.add_argument("--decision-time-ns", type=int, required=True)
    assess.add_argument("--as-of-ns", type=int, default=None)
    assess.add_argument("--contributor-path", type=Path, default=None)
    assess.add_argument("--calibration-path", type=Path, default=None)
    assess.add_argument("--model-path", type=Path, default=None)
    assess.add_argument("--training-manifest", type=Path, default=None)
    assess.add_argument("--account-id", type=str, default=None)
    assess.add_argument("--mode", type=str, default="paper")
    assess.add_argument("--output", type=Path, default=None)

    scan = sub.add_parser("scan-contributors", help="List contributor JSON refusal reasons.")
    scan.add_argument("--contributor-path", type=Path, required=True)
    scan.add_argument("--as-of-ns", type=int, default=None)
    scan.add_argument("--account-id", type=str, default=None)
    scan.add_argument("--mode", type=str, default="paper")
    scan.add_argument("--output", type=Path, default=None)

    bind = sub.add_parser("validate-binding", help="Fail closed on unlawful forecast binding.")
    bind.add_argument("--contributor-path", type=Path, required=True)
    bind.add_argument("--forecast-id", type=str, required=True)

    build = sub.add_parser("build", help="Train from governed training manifest (operator output dir).")
    build.add_argument("--training-manifest", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    build.add_argument("--decision-time-ns", type=int, required=True)
    build.add_argument("--mode", type=str, default="paper")
    build.add_argument(
        "--calibration-method",
        choices=("LOGISTIC_PROBABILITY", "ISOTONIC"),
        default="LOGISTIC_PROBABILITY",
    )
    build.add_argument("--output", type=Path, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "assess":
        report = assess_production_readiness(
            contributor_path=args.contributor_path,
            calibration_path=args.calibration_path,
            model_path=args.model_path,
            training_manifest_path=args.training_manifest,
            decision_time_ns=args.decision_time_ns,
            as_of_time_ns=args.as_of_ns,
            expected_account_id=args.account_id,
            expected_mode=args.mode,
        )
        body = json.dumps(report.to_dict(), indent=2, sort_keys=True)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(body + "\n", encoding="utf-8")
        else:
            print(body)
        return 0 if report.disposition == STATUS_ARTIFACT_READY else 1

    if args.command == "scan-contributors":
        rows = scan_contributor_directory(
            args.contributor_path,
            as_of_time_ns=args.as_of_ns,
            expected_account_id=args.account_id,
            expected_mode=args.mode,
        )
        payload = {
            "artifact_kind": "item7_contributor_scan_v1",
            "rows": [
                {
                    "forecast_id": row.forecast_id,
                    "lawful": row.lawful,
                    "refusal_reasons": list(row.refusal_reasons),
                }
                for row in rows
            ],
        }
        body = json.dumps(payload, indent=2, sort_keys=True)
        if args.output is not None:
            args.output.write_text(body + "\n", encoding="utf-8")
        else:
            print(body)
        return 0

    if args.command == "validate-binding":
        reasons = forecast_binding_refusal_reasons(
            forecast_id=args.forecast_id,
            contributor_path=args.contributor_path,
        )
        payload = {
            "artifact_kind": "item7_forecast_binding_validation_v1",
            "forecast_id": args.forecast_id,
            "lawful": not reasons,
            "refusal_reasons": list(reasons),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if not reasons else 1

    method = CalibrationMethod[str(args.calibration_method)]
    result = build_path_a_production_artifacts(
        args.training_manifest,
        output_dir=args.output_dir,
        mode=args.mode,
        decision_time_ns=args.decision_time_ns,
        calibration_method=method,
    )
    payload = {
        "artifact_kind": "item7_production_build_v1",
        "status": result.status,
        "reason_codes": list(result.reason_codes),
        "model_id": result.model_id,
        "training_dataset_fingerprint": result.training_dataset_fingerprint,
        "calibration_model_id": result.calibration_model_id,
        "contributor_forecast_id": result.contributor_forecast_id,
        "artifact_hashes": result.artifact_hashes or {},
    }
    body = json.dumps(payload, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.write_text(body + "\n", encoding="utf-8")
    else:
        print(body)
    return 0 if result.built else 1


if __name__ == "__main__":
    raise SystemExit(main())
