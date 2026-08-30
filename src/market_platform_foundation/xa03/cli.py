"""XA-03 CLI."""

from __future__ import annotations

import argparse
import json
import sys

from .operations import execute


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xa03")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    show_source = sub.add_parser("show-source")
    show_source.add_argument("market_report_id")
    show_source.add_argument("--json", action="store_true")
    show_obs = sub.add_parser("show-observation")
    show_obs.add_argument("observation_id")
    show_obs.add_argument("--json", action="store_true")
    relationships = sub.add_parser("list-relationships")
    relationships.add_argument("--market-report-id", default="")
    relationships.add_argument("--target-xa-canonical-id", default="")
    relationships.add_argument("--json", action="store_true")
    admit = sub.add_parser("admit-fixture")
    admit.add_argument("--fixture", default="positioning_reference_vertical.json")
    admit.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "status":
        result = execute("XA03.OP.STATUS")
    elif args.command == "validate":
        result = execute("XA03.OP.VALIDATE")
    elif args.command == "show-source":
        result = execute("XA03.OP.SHOW_SOURCE", {"market_report_id": args.market_report_id})
    elif args.command == "show-observation":
        result = execute("XA03.OP.SHOW_OBSERVATION", {"observation_id": args.observation_id})
    elif args.command == "list-relationships":
        result = execute(
            "XA03.OP.LIST_RELATIONSHIPS",
            {
                "market_report_id": args.market_report_id,
                "target_xa_canonical_id": args.target_xa_canonical_id,
            },
        )
    elif args.command == "admit-fixture":
        result = execute("XA03.OP.ADMIT_FIXTURE", {"fixture_name": args.fixture})
    else:
        return 2
    payload = {
        "outcome": result.outcome_code,
        "capability_id": result.capability_id,
        "verification": dict(result.verification),
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload))
    return 0 if result.outcome_code == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
