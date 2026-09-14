"""CLI: Item 7 production forecast path progression report (Lane D diagnostics)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.production.progression import (
    ITEM7_STATUS_PARTIAL,
    build_item7_progression_report,
)


def _parse_bindings(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("BINDINGS_MUST_BE_JSON_OBJECT")
    return {str(k): str(v) for k, v in payload.items()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Emit Item 7 production forecast progression (machine + readable JSON).",
    )
    parser.add_argument("--as-of-ns", type=int, required=True, help="PIT as-of time (ns).")
    parser.add_argument(
        "--session-start-ns",
        type=int,
        required=True,
        help="Prospective session start (ns); pre-session envelopes refused.",
    )
    parser.add_argument("--capture-path", type=Path, default=None, help="OpenD capture JSONL path.")
    parser.add_argument("--contributor-path", type=Path, default=None, help="PRODUCTION contributor JSON dir.")
    parser.add_argument("--forecast-path", type=Path, default=None, help="Fused ForecastV1 JSON dir.")
    parser.add_argument("--calibration-path", type=Path, default=None, help="Calibration artifact JSON.")
    parser.add_argument(
        "--forecast-bindings",
        type=str,
        default=None,
        help='JSON map candidate_id → forecast_id, e.g. \'{"OCLC-...":"PSFC-..."}\'.',
    )
    parser.add_argument(
        "--materialize-capture",
        action="store_true",
        help="Persist capture events and register ledger when bindings are lawful.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON report to path (stdout if omitted).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bindings = _parse_bindings(args.forecast_bindings)
    repo = InMemoryIntelligenceRepository()
    report = build_item7_progression_report(
        repository=repo,
        as_of_ns=args.as_of_ns,
        session_start_ns=args.session_start_ns,
        capture_path=args.capture_path,
        contributor_path=args.contributor_path,
        forecast_path=args.forecast_path,
        calibration_path=args.calibration_path,
        forecast_bindings=bindings,
        materialize_capture=args.materialize_capture,
    )
    if report.item7_status != ITEM7_STATUS_PARTIAL:
        print("ITEM7_STATUS_UNEXPECTED", file=sys.stderr)
        return 2
    body = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body + "\n", encoding="utf-8")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
