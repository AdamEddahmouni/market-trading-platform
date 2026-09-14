#!/usr/bin/env python3
"""OpenD 1m BAR_OHLCV operator: display bars, transport proof, prospective proof."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.clock import monotonic_wall_ns  # noqa: E402
from market_platform_foundation.paper.calibration.bar_ohlcv_experiment import (  # noqa: E402
    default_collection_root,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    DEFAULT_RECEIPT_DIR,
    PROOF_MODE_RETROSPECTIVE,
    REASON_POLL_REQUIRED,
    REASON_PROSPECTIVE_EXPLICIT_SIGNAL,
    READINESS_RTH_REQUIRED,
    imp_package_root,
    item9_prospective_readiness,
    load_latest_completed_bars_for_display,
    persist_receipt,
    poll_prospective_proof,
    prospective_run_without_poll_outcome,
    resolve_runtime_git_sha,
    run_transport_proof,
)

PROOF_MODE_RETROSPECTIVE_LABEL = PROOF_MODE_RETROSPECTIVE


def _cmd_readiness(_: argparse.Namespace) -> int:
    payload = item9_prospective_readiness(now_ns=monotonic_wall_ns())
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_display(args: argparse.Namespace) -> int:
    observation_ns = args.observation_time_ns if args.observation_time_ns is not None else monotonic_wall_ns()
    loaded, rows = load_latest_completed_bars_for_display(
        instrument_id=str(args.instrument_id),
        observation_time_ns=observation_ns,
    )
    payload = {
        "instrument_id": args.instrument_id,
        "observation_time_ns": observation_ns,
        "load_ok": loaded.ok,
        "reason_code": loaded.reason_code,
        "provenance": dict(loaded.provenance),
        "bars": [row.to_dict() for row in rows],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if loaded.ok else 1


def _cmd_transport_proof(args: argparse.Namespace) -> int:
    observation_ns = (
        args.observation_time_ns if args.observation_time_ns is not None else monotonic_wall_ns()
    )
    collection_root = args.collection_root if args.collection_root is not None else default_collection_root()
    payload = run_transport_proof(
        signal_time_ns=int(args.signal_time_ns),
        observation_time_ns=observation_ns,
        instrument_id=str(args.instrument_id),
        source=str(args.source),
        collection_root=collection_root,
        env=dict(os.environ),
        experiment_id=args.experiment_id,
        runtime_git_sha=resolve_runtime_git_sha(start=ROOT),
    )
    payload["proof_mode_label"] = PROOF_MODE_RETROSPECTIVE_LABEL
    payload["not_prospective_evidence"] = True
    receipt = payload["receipt"]
    if args.receipt_out is not None:
        path = persist_receipt(receipt, out_dir=args.receipt_out)
        payload["receipt_path"] = str(path)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_prospective(args: argparse.Namespace) -> int:
    if args.signal_time_ns is not None:
        print(
            json.dumps(
                {"ok": False, "reason_code": REASON_PROSPECTIVE_EXPLICIT_SIGNAL},
                indent=2,
                sort_keys=True,
            ),
        )
        return 2

    signal_established_at_ns = monotonic_wall_ns()
    signal_time_ns = signal_established_at_ns
    collection_root = args.collection_root if args.collection_root is not None else default_collection_root()
    receipt_dir = args.receipt_out if args.receipt_out is not None else imp_package_root() / DEFAULT_RECEIPT_DIR

    runtime_sha = resolve_runtime_git_sha(start=ROOT)
    if args.poll:
        outcome = poll_prospective_proof(
            instrument_id=str(args.instrument_id),
            collection_root=collection_root,
            env=dict(os.environ),
            signal_time_ns=signal_time_ns,
            signal_established_at_ns=signal_established_at_ns,
            max_wait_s=float(args.timeout_s),
            poll_interval_s=float(args.poll_interval_s),
            experiment_id=args.experiment_id,
            runtime_git_sha=runtime_sha,
        )
    else:
        outcome = prospective_run_without_poll_outcome(
            now_ns=monotonic_wall_ns(),
            signal_time_ns=signal_time_ns,
            signal_established_at_ns=signal_established_at_ns,
        )

    if outcome.get("receipt"):
        path = persist_receipt(outcome["receipt"], out_dir=receipt_dir)
        outcome["receipt_path"] = str(path)
    print(json.dumps(outcome, indent=2, sort_keys=True))
    if outcome.get("ok"):
        return 0
    if outcome.get("reason_code") == READINESS_RTH_REQUIRED:
        return 3
    if outcome.get("reason_code") == REASON_POLL_REQUIRED:
        return 4
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Item 9 OpenD 1m BAR_OHLCV display and prospective/transport proof helper.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    readiness = sub.add_parser("readiness", help="Report SOFTWARE_READY_RTH_REQUIRED vs RTH-active.")
    readiness.set_defaults(func=_cmd_readiness)

    display = sub.add_parser("display", help="Show latest completed OpenD 1m bars with provenance.")
    display.add_argument("--instrument-id", default="AAPL")
    display.add_argument("--observation-time-ns", type=int, default=None)
    display.set_defaults(func=_cmd_display)

    transport = sub.add_parser(
        "transport-proof",
        help=f"Mode A — {PROOF_MODE_RETROSPECTIVE_LABEL} (NOT prospective evidence).",
    )
    transport.add_argument("--signal-time-ns", type=int, required=True)
    transport.add_argument("--observation-time-ns", type=int, default=None)
    transport.add_argument("--instrument-id", default="AAPL")
    transport.add_argument(
        "--source",
        choices=("admitted-fixture", "moomoo-opend"),
        default="moomoo-opend",
    )
    transport.add_argument("--experiment-id", default=None)
    transport.add_argument("--collection-root", type=Path, default=None)
    transport.add_argument(
        "--receipt-out",
        type=Path,
        default=None,
        help="Directory for versioned JSON receipt (optional).",
    )
    transport.set_defaults(func=_cmd_transport_proof)

    prospective = sub.add_parser(
        "prospective",
        help="Mode B — record signal_time NOW; refuse retrospective timestamps.",
    )
    prospective.add_argument("--instrument-id", default="AAPL")
    prospective.add_argument(
        "--signal-time-ns",
        type=int,
        default=None,
        help="Refused — prospective mode records signal at run start.",
    )
    prospective.add_argument("--experiment-id", default=None)
    prospective.add_argument("--collection-root", type=Path, default=None)
    prospective.add_argument(
        "--receipt-out",
        type=Path,
        default=None,
        help=f"Receipt directory (default: {DEFAULT_RECEIPT_DIR}).",
    )
    prospective.add_argument(
        "--poll",
        action="store_true",
        help="Poll OpenD during RTH until first bar with available_time > signal_time.",
    )
    prospective.add_argument("--poll-interval-s", type=float, default=5.0)
    prospective.add_argument("--timeout-s", type=float, default=3900.0)
    prospective.set_defaults(func=_cmd_prospective)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
