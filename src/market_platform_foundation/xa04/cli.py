"""XA-04 CLI."""

from __future__ import annotations

import argparse
import json
import sys

from .operations import execute


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xa04")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    show = sub.add_parser("show-record")
    show.add_argument("record_kind")
    show.add_argument("record_id")
    show.add_argument("--json", action="store_true")
    catalog = sub.add_parser("list-catalog")
    catalog.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "status":
        result = execute("XA04.OP.STATUS")
    elif args.command == "validate":
        result = execute("XA04.OP.VALIDATE")
    elif args.command == "show-record":
        result = execute(
            "XA04.OP.SHOW_RECORD",
            {"record_kind": args.record_kind, "record_id": args.record_id},
        )
    elif args.command == "list-catalog":
        result = execute("XA04.OP.LIST_CATALOG")
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
