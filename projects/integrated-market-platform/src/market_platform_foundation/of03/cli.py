"""OF-03 operator CLI. Structured --json output. No execute-workflow verb."""

from __future__ import annotations

import argparse
import json
import sys

from .errors import OF03Error
from .operations import execute


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="of03")
    parser.add_argument("--json", action="store_true", dest="json_output")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("validate")
    sub.add_parser("list-capabilities")
    sub.add_parser("list-sops")
    sub.add_parser("list-workflows")
    show = sub.add_parser("show-definition")
    show.add_argument("--kind", required=True, choices=("capability", "sop", "workflow"))
    show.add_argument("--id", required=True, dest="definition_id")
    show.add_argument("--version", type=int)
    show.add_argument("--active", action="store_true")
    sub.add_parser("snapshot")
    sub.add_parser("verify-bindings")
    sub.add_parser("check-drift")
    return parser


_COMMAND_MAP = {
    "status": "OF03.OP.STATUS",
    "validate": "OF03.OP.VALIDATE",
    "list-capabilities": "OF03.OP.LIST_CAPABILITIES",
    "list-sops": "OF03.OP.LIST_SOPS",
    "list-workflows": "OF03.OP.LIST_WORKFLOWS",
    "show-definition": "OF03.OP.SHOW_DEFINITION",
    "snapshot": "OF03.OP.SNAPSHOT",
    "verify-bindings": "OF03.OP.VERIFY_BINDINGS",
    "check-drift": "OF03.OP.CHECK_DRIFT",
}


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    capability_id = _COMMAND_MAP[args.command]
    arguments: dict[str, object] = {}
    if args.command == "show-definition":
        arguments = {
            "kind": args.kind,
            "id": args.definition_id,
            "version": args.version,
            "use_active": bool(args.active),
        }
    try:
        result = execute(capability_id, arguments=arguments)
    except OF03Error as exc:
        payload = {"capability_id": capability_id, "outcome_code": exc.code.value, "verification": {"message": exc.message, "details": dict(exc.details)}}
        _emit(parser, args, payload)
        return 1
    payload = {"capability_id": capability_id, "outcome_code": result.outcome_code, "verification": result.verification}
    _emit(parser, args, payload)
    return 0 if result.outcome_code == "OK" else 1


def _emit(parser: argparse.ArgumentParser, args: argparse.Namespace, payload: dict[str, object]) -> None:
    if args.json_output:
        sys.stdout.write(json.dumps(payload, sort_keys=True, default=str) + "\n")
    else:
        sys.stdout.write(f"{payload['outcome_code']}\n")


if __name__ == "__main__":
    raise SystemExit(main())
