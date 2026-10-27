"""Whole-store integrity check that never opens the store for writing: the keeper's nightly scan and a release's
bootstrap of the verified-store receipt.

  verify_state_store.py --store <imp-state.sqlite3> [--label L] [--wait]

It opens the store read-only (``mode=ro``), takes the store's verify lock (one full check at a time, shared with
every LocalStateConnection), runs ``PRAGMA integrity_check`` and records the outcome next to the store:

  exit 0  ok: a fresh receipt (``<store>.verified.json``), so opens this boot check only the critical tables
  exit 2  not ok: the receipt is INVALIDATED and the next open fails closed after its own full check
  exit 3  BUSY: another full check holds the lock (``--wait`` waits for it instead)
  exit 4  the store does not exist

It prints one JSON line. It changes no table, runs no migration and needs no platform process.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _entry in (ROOT / "src", ROOT):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from market_platform_foundation.local_state import integrity_receipt as receipts  # noqa: E402
from market_platform_foundation.local_state.connection import corruption_error  # noqa: E402

EXIT_OK, EXIT_NOT_OK, EXIT_BUSY, EXIT_MISSING = 0, 2, 3, 4


def default_store() -> Path | None:
    directory = os.environ.get("IMP_STATE_DIR")
    return Path(directory) / "imp-state.sqlite3" if directory else None


def verify(store: Path, *, label: str, wait: bool = False) -> tuple[int, dict]:
    store = store.resolve()
    if not store.is_file():
        return EXIT_MISSING, {"result": "STORE_MISSING", "store": str(store)}
    before = receipts.receipt_problem(store)
    lock = receipts.VerifyLock(store)
    if not lock.acquire(blocking=wait):
        return EXIT_BUSY, {"result": "BUSY", "store": str(store), "status": receipts.read_status(store)}
    try:
        started_epoch, started = time.time(), time.monotonic()
        connection = sqlite3.connect(store.as_uri() + "?mode=ro", uri=True, timeout=30)
        try:
            with receipts.VerifyHeartbeat(store, label=label) as beat:
                try:
                    status = receipts.full_check(connection)
                except sqlite3.DatabaseError as exc:
                    if not corruption_error(exc):
                        beat.result = str(exc)
                        raise
                    status = f"{type(exc).__name__}:{exc}"
                beat.result = status
        finally:
            connection.close()
        elapsed = round(time.monotonic() - started, 3)
        if status != "ok":
            receipts.invalidate(store, f"FULL_CHECK:{status}", label=label)
            return EXIT_NOT_OK, {"result": receipts.INVALIDATED, "store": str(store), "status": status[:500],
                                 "elapsed_seconds": elapsed, "receipt_before": before}
        receipt = receipts.write_receipt(store, elapsed_seconds=elapsed, label=label, started_at=started_epoch)
        return EXIT_OK, {"result": "ok", "store": str(store), "elapsed_seconds": elapsed,
                         "receipt_before": before, "size_bytes": receipt["identity"]["size_bytes"],
                         "sqlite_version": receipt["sqlite_version"]}
    finally:
        lock.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--store", type=Path, default=default_store())
    parser.add_argument("--label", default="verify_state_store")
    parser.add_argument("--wait", action="store_true", help="wait for a running check instead of reporting BUSY")
    args = parser.parse_args(argv)
    if args.store is None:
        parser.error("--store is required when IMP_STATE_DIR is not set")
    code, body = verify(args.store, label=args.label, wait=args.wait)
    print(json.dumps({"exit_code": code, **body}, sort_keys=True, default=str), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
