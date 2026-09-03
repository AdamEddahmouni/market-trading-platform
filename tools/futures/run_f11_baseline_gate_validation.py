"""Run F11-S1 baseline gate validation on admitted ES and CL fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "evidence/futures/baseline-gate-validation-report.json"
DEFAULT_ENERGY_OUTPUT = ROOT / "evidence/futures/energy-baseline-gate-validation-report.json"

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import write_canonical_json  # noqa: E402
from market_platform_foundation.offline_guard import install_guard  # noqa: E402
from market_platform_foundation.futures.research.baseline_harness import (  # noqa: E402
    run_f11_baseline_gate_validation,
    run_f11_energy_baseline_gate_validation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F11-S1 baseline gate validation report")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path for canonical ES validation report JSON",
    )
    parser.add_argument(
        "--energy-output",
        default=str(DEFAULT_ENERGY_OUTPUT),
        help="Path for canonical CL/ENERGY validation report JSON",
    )
    parser.add_argument(
        "--energy-only",
        action="store_true",
        help="Validate admitted CL/ENERGY fixtures only",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print report summary to stdout without writing output file",
    )
    return parser.parse_args()


def _summarize(report: dict[str, object]) -> dict[str, object]:
    return {
        "aggregate_status": report.get("aggregate_status"),
        "gate_summary": report.get("gate_summary"),
        "fixture_refs": [
            {
                "role": ref.get("role"),
                "admission_id": ref.get("admission_id"),
                "admitted_fixture_id": ref.get("admitted_fixture_id"),
            }
            for ref in report.get("fixture_refs", [])
            if isinstance(ref, dict)
        ],
    }


def main() -> int:
    install_guard([])
    args = parse_args()
    es_report = None if args.energy_only else run_f11_baseline_gate_validation()
    energy_report = run_f11_energy_baseline_gate_validation()

    if args.dry_run:
        payload: dict[str, object] = {"energy": _summarize(energy_report)}
        if es_report is not None:
            payload["es"] = _summarize(es_report)
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        energy_output = Path(args.energy_output).resolve()
        energy_output.parent.mkdir(parents=True, exist_ok=True)
        write_canonical_json(energy_output, energy_report)
        print(
            json.dumps(
                {
                    "energy_aggregate_status": energy_report.get("aggregate_status"),
                    "energy_output": str(energy_output.relative_to(ROOT)),
                },
                sort_keys=True,
            )
        )
        if es_report is not None:
            output_path = Path(args.output).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            write_canonical_json(output_path, es_report)
            print(
                json.dumps(
                    {
                        "aggregate_status": es_report.get("aggregate_status"),
                        "output": str(output_path.relative_to(ROOT)),
                    },
                    sort_keys=True,
                )
            )

    statuses = [energy_report.get("aggregate_status")]
    if es_report is not None:
        statuses.append(es_report.get("aggregate_status"))
    return 0 if all(status == "PASS" for status in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
