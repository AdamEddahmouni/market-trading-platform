"""CLI — bind lawful Item 7 capture grid points to PRODUCTION contributor forecasts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from market_platform_foundation.intelligence.production.item7_p0_anchor import (  # noqa: E402
    materialize_item7_lawful_capture_ledger,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.intelligence.production.item7_capture_forecast_binding import (  # noqa: E402
    BINDING_ARTIFACT_KIND,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize capture JSONL with auto-bound PRODUCTION_RAW forecasts "
            "(fail-closed; never mints forecasts from quotes)."
        ),
    )
    parser.add_argument("--capture-path", type=Path, required=True)
    parser.add_argument("--contributor-path", type=Path, default=None)
    parser.add_argument("--forecast-path", type=Path, default=None)
    parser.add_argument("--as-of-ns", type=int, required=True)
    parser.add_argument("--session-start-ns", type=int, required=True)
    parser.add_argument("--account-id", type=str, default=None)
    parser.add_argument("--mode", type=str, default="paper")
    parser.add_argument(
        "--register-ledger",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Register BUILD 15 ledger rows when binding succeeds.",
    )
    parser.add_argument(
        "--use-production-ingress",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Dispatch through production observation ingress (default off for operator bind).",
    )
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.capture_path.is_file():
        print(f"Capture file not found: {args.capture_path}", file=sys.stderr)
        return 2

    repository = InMemoryIntelligenceRepository()
    result = materialize_item7_lawful_capture_ledger(
        (args.capture_path,),
        repository,
        as_of_ns=args.as_of_ns,
        session_start_ns=args.session_start_ns,
        contributor_path=args.contributor_path,
        forecast_path=args.forecast_path,
        bind_expected_account_id=args.account_id,
        bind_expected_mode=args.mode,
        register_ledger=args.register_ledger,
        use_production_ingress=args.use_production_ingress,
    )
    payload = {
        "artifact_kind": BINDING_ARTIFACT_KIND,
        "capture_path": str(args.capture_path),
        "contributor_path": str(args.contributor_path) if args.contributor_path else None,
        "events_persisted": result.events_persisted,
        "ledger_registered": result.ledger_registered,
        "refusal_reasons": dict(result.refusal_reasons),
        "candidates": [candidate.to_dict() for candidate in result.candidates],
        "funnel": result.funnel.to_dict(),
    }
    body = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)

    bound = sum(1 for candidate in result.candidates if candidate.forecast_id)
    if bound == 0 and result.funnel.grid_points > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
