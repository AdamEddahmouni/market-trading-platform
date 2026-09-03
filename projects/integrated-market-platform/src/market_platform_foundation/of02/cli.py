"""OF-02 operator CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .operations import execute


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="of02")
    parser.add_argument("--json", action="store_true", dest="json_output")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    dry = sub.add_parser("retrospective-dry-run")
    dry.add_argument("paths", nargs="+")
    execute_cmd = sub.add_parser("retrospective-execute")
    execute_cmd.add_argument("paths", nargs="+")
    resume = sub.add_parser("retrospective-resume")
    resume.add_argument("paths", nargs="+")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "status":
        result = execute("OF02.OP.STATUS")
    elif args.command == "retrospective-dry-run":
        result = execute("OF02.OP.RETROSPECTIVE_DRY_RUN", arguments={"paths": args.paths})
    elif args.command == "retrospective-execute":
        result = execute("OF02.OP.RETROSPECTIVE_EXECUTE", arguments={"paths": args.paths})
    elif args.command == "retrospective-resume":
        result = execute("OF02.OP.RETROSPECTIVE_RESUME", arguments={"paths": args.paths})
    else:
        parser.error(f"unknown command {args.command}")
        return 2
    payload = {"capability_id": args.command, "outcome_code": result.outcome_code, "verification": result.verification}
    if args.json_output:
        sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    else:
        sys.stdout.write(f"{result.outcome_code}\n")
    return 0 if result.outcome_code == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
