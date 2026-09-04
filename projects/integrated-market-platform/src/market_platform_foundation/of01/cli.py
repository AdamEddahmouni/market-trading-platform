"""Thin OF-01 operator CLI adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .health import HealthService
from .migrations import open_authority
from .operations import OperationsService
from .sqlite_store import SQLiteAuthorityStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="of01")
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--authority-id", required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("metadata")
    sub.add_parser("integrity-quick")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    db_path = Path(args.db_path)
    conn = open_authority(db_path, ledger_authority_id=args.authority_id)
    store = SQLiteAuthorityStore(conn, ledger_authority_id=args.authority_id)
    try:
        service = OperationsService(store=store)
        if args.command == "status":
            result = service.execute("OF01.OP.STATUS")
            capability = "OF01.OP.STATUS"
        elif args.command == "metadata":
            result = service.execute("OF01.OP.LEDGER_METADATA")
            capability = "OF01.OP.LEDGER_METADATA"
        elif args.command == "integrity-quick":
            result = service.execute("OF01.OP.INTEGRITY_QUICK")
            capability = "OF01.OP.INTEGRITY_QUICK"
        else:
            parser.error(f"unknown command {args.command}")
            return 2
        payload = {
            "capability_id": capability,
            "outcome_code": result.outcome_code,
            "verification": result.verification,
        }
        if args.json_output:
            sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
        else:
            sys.stdout.write(f"{result.outcome_code}\n")
        return 0 if result.outcome_code == "OK" else 1
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
