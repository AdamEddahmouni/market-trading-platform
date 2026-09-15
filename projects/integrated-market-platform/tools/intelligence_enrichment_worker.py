"""Operator CLI for the durable intelligence enrichment worker."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from market_platform_foundation.intelligence.enrichment.runtime import (  # noqa: E402
    build_enrichment_worker,
    enrichment_poll_interval_sec,
    enrichment_worker_enabled,
    open_sqlite_enrichment_outbox,
    worker_status_snapshot,
)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("status", "once", "run", "drain"),
        help="status: snapshot; once: single tick; run: loop; drain: bounded batch",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow worker ticks without IMP_INTELLIGENCE_ENRICHMENT_WORKER=1",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=256,
        help="Upper bound for drain (default 256)",
    )
    return parser.parse_args(argv)


def _require_gate(force: bool) -> int | None:
    if enrichment_worker_enabled() or force:
        return None
    print(
        "enrichment worker disabled (set IMP_INTELLIGENCE_ENRICHMENT_WORKER=1 or pass --force)",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    outbox = open_sqlite_enrichment_outbox()
    if args.command == "status":
        print(json.dumps(worker_status_snapshot(outbox), sort_keys=True))
        return 0 if outbox is not None or not enrichment_worker_enabled() else 1
    if outbox is None:
        print("local_state persistence unavailable (IMP_PERSIST_STATE=1 or IMP_STATE_DIR)", file=sys.stderr)
        return 1
    gate = _require_gate(args.force)
    if gate is not None:
        return gate
    worker = build_enrichment_worker(outbox)
    if args.command == "once":
        processed = int(worker.run_once())
        print(json.dumps({"processed": processed}, sort_keys=True))
        return 0
    if args.command == "drain":
        processed = worker.drain(max_iterations=max(1, args.max_iterations))
        print(json.dumps({"processed": processed}, sort_keys=True))
        return 0
    interval = enrichment_poll_interval_sec()
    while True:
        worker.run_once()
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
