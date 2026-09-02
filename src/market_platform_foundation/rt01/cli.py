"""RT-01 CLI."""

from __future__ import annotations

import argparse
import json
import sys

from .operations import execute


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rt01")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    baseline = sub.add_parser("baseline")
    baseline.add_argument("--profile", default="receive_to_canonical_state")
    baseline.add_argument("--json", action="store_true")
    overhead = sub.add_parser("overhead")
    overhead.add_argument("--json", action="store_true")
    export = sub.add_parser("export")
    export.add_argument("path")
    export.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "status":
        result = execute("RT01.OP.STATUS")
    elif args.command == "validate":
        result = execute("RT01.OP.VALIDATE_TRACE")
    elif args.command == "baseline":
        result = execute("RT01.OP.BASELINE", {"profile_id": args.profile})
    elif args.command == "overhead":
        result = execute("RT01.OP.OVERHEAD")
    elif args.command == "export":
        result = execute("RT01.OP.EXPORT", {"path": args.path})
    else:
        return 2
    payload = {"outcome": result.outcome_code, "capability_id": result.capability_id, "verification": dict(result.verification)}
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload))
    return 0 if result.outcome_code == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
