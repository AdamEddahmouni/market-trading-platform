"""XA-05 CLI."""

from __future__ import annotations

import argparse
import json
import sys

from .operations import execute


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xa05")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    construct = sub.add_parser("construct-state")
    construct.add_argument("decision_time")
    construct.add_argument("--construction-time", default="")
    construct.add_argument("--json", action="store_true")
    show = sub.add_parser("show-state")
    show.add_argument("decision_time")
    show.add_argument("--json", action="store_true")
    compare = sub.add_parser("compare-states")
    compare.add_argument("earlier_decision_time")
    compare.add_argument("later_decision_time")
    compare.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "status":
        result = execute("XA05.OP.STATUS")
    elif args.command == "validate":
        result = execute("XA05.OP.VALIDATE")
    elif args.command == "construct-state":
        result = execute(
            "XA05.OP.CONSTRUCT_STATE",
            {
                "decision_time": args.decision_time,
                "construction_time": args.construction_time or args.decision_time,
            },
        )
    elif args.command == "show-state":
        result = execute(
            "XA05.OP.SHOW_STATE",
            {"decision_time": args.decision_time},
        )
    elif args.command == "compare-states":
        result = execute(
            "XA05.OP.COMPARE_STATES",
            {
                "earlier_decision_time": args.earlier_decision_time,
                "later_decision_time": args.later_decision_time,
            },
        )
    else:
        return 2
    payload = {
        "outcome": result.outcome_code,
        "capability_id": result.capability_id,
        "verification": dict(result.verification),
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(json.dumps(payload, default=str))
    return 0 if result.outcome_code == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
