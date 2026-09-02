"""XA-01 CLI."""

from __future__ import annotations

import argparse
import json
import sys

from .operations import execute


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xa01")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    resolve = sub.add_parser("resolve")
    resolve.add_argument("provider_id")
    resolve.add_argument("alias_value")
    resolve.add_argument("--identifier-type", default="PROVIDER_SYMBOL")
    resolve.add_argument("--json", action="store_true")
    show = sub.add_parser("show")
    show.add_argument("canonical_id")
    show.add_argument("--json", action="store_true")
    domains = sub.add_parser("list-domains")
    domains.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "status":
        result = execute("XA01.OP.STATUS")
    elif args.command == "validate":
        result = execute("XA01.OP.VALIDATE_REGISTRY")
    elif args.command == "resolve":
        result = execute(
            "XA01.OP.RESOLVE",
            {
                "provider_id": args.provider_id,
                "alias_value": args.alias_value,
                "identifier_type": args.identifier_type,
            },
        )
    elif args.command == "show":
        result = execute("XA01.OP.SHOW_INSTRUMENT", {"canonical_id": args.canonical_id})
    elif args.command == "list-domains":
        result = execute("XA01.OP.LIST_DOMAINS")
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
