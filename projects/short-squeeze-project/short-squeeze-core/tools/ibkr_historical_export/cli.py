"""Command-line interface for the read-only IBKR historical export tool.

Stages: ``connection-probe``, ``qualify-contracts``, ``collect-bars``,
``verify-private-batch``. ``run`` executes the full serial pipeline over one
connection. No stage places orders or reads account data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import policy
from .collector import ResilientConnection, probe_and_connect, run_collection
from .paths import PrivateLayout, default_private_root
from .serialization import sha256_and_length
from .statuses import CollectionStatus


def _session_factory():
    # Imported lazily so non-connecting stages need no live ibapi socket.
    from .session import IbkrSession
    return IbkrSession()


def _layout(args) -> PrivateLayout:
    root = Path(args.private_root) if args.private_root else default_private_root()
    layout = PrivateLayout(root)
    layout.ensure()
    return layout


def _connect(layout: PrivateLayout):
    session, result = probe_and_connect(_session_factory)
    if result.status is not CollectionStatus.CONNECTION_SUCCESS:
        print("CONNECTION_FAILED", file=sys.stderr)
        for attempt in result.attempts:
            print(f"  attempt: {attempt}", file=sys.stderr)
        return None, result
    print(
        f"CONNECTION_SUCCESS port={result.observed_port} client_id={result.client_id} "
        f"server_version={result.server_version}"
    )
    return session, result


def cmd_connection_probe(args) -> int:
    layout = _layout(args)
    session, result = _connect(layout)
    if session is None:
        return 2
    try:
        run_collection  # noqa: B018 - ensure import side effects are intentional
    finally:
        session.shutdown()
    print(f"probe recorded observed_port={result.observed_port}")
    return 0


def cmd_run(args) -> int:
    layout = _layout(args)
    session, result = _connect(layout)
    if session is None:
        return 2
    resilient = ResilientConnection(_session_factory, result)
    resilient._session = session
    try:
        summary = run_collection(resilient, layout)
    finally:
        resilient.shutdown()
    resolved = sum(1 for s in summary["symbols"] if s["contract_status"] == "CONTRACT_RESOLVED")
    print(f"collection complete: {resolved}/{len(summary['symbols'])} contracts resolved")
    print(f"summary: {layout.collection_summary}")
    return 0


def cmd_resolve_semantics(args) -> int:
    """Offline: apply the Batch 06 semantic resolver and write private overlays."""
    from .semantics_overlay import generate_overlays

    layout = _layout(args)
    summary = generate_overlays(layout)
    rejected = sum(
        1
        for item in summary["detection_context_preflight"]
        if item["preflight_status"] == "PREFLIGHT_REJECTED"
    )
    total = summary["detection_context_count"]
    print(f"semantics resolved: {total} detection-context artifacts re-preflighted")
    print(f"  unresolved fields: {summary['unresolved_fields']}")
    print(f"  PREFLIGHT_REJECTED: {rejected}/{total}")
    print(f"  overlays: {layout.root / 'semantics' / 'batch-06'}")
    return 0


def cmd_verify_private_batch(args) -> int:
    """Offline: recompute SHA-256 of every raw CSV and compare to the sha256 manifest."""
    layout = _layout(args)
    manifest_path = layout.sha256_manifest
    if not manifest_path.exists():
        print("no sha256-manifest.json present; nothing to verify", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatches = 0
    for relative, expected in sorted(manifest.items()):
        path = layout.root / relative
        if not path.exists():
            print(f"MISSING {relative}")
            mismatches += 1
            continue
        sha, length = sha256_and_length(path.read_bytes())
        ok = sha == expected["sha256"] and length == expected["byte_length"]
        print(f"{'OK  ' if ok else 'FAIL'} {relative} sha256={sha[:12]}... len={length}")
        if not ok:
            mismatches += 1
    print(f"verify complete: {len(manifest)} artifacts, {mismatches} mismatches")
    return 0 if mismatches == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ibkr_historical_export",
        description="Read-only IBKR historical-bar collection (Phase 3D Batch 05).",
    )
    parser.add_argument("--private-root", default=None, help="override private intake root")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("connection-probe", help="probe localhost Gateway and record result")
    sub.add_parser("qualify-contracts", help="probe + qualify all frozen contracts (via run)")
    sub.add_parser("collect-bars", help="full serial collection over one connection")
    sub.add_parser("verify-private-batch", help="offline re-hash of raw artifacts")
    sub.add_parser(
        "resolve-semantics",
        help="offline Batch 06 semantic resolution + re-preflight overlays",
    )
    sub.add_parser("run", help="full serial pipeline (probe -> qualify -> collect -> preflight)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "connection-probe":
        return cmd_connection_probe(args)
    if args.command in ("collect-bars", "qualify-contracts", "run"):
        return cmd_run(args)
    if args.command == "verify-private-batch":
        return cmd_verify_private_batch(args)
    if args.command == "resolve-semantics":
        return cmd_resolve_semantics(args)
    print(f"unknown command {args.command!r}", file=sys.stderr)
    return 2


__all__ = ["build_parser", "main"]
