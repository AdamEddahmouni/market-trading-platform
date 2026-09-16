"""CLI — append lawful Item 7 SNAPSHOT_BBO capture envelopes to operator JSONL."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from market_platform_foundation.intelligence.production.item7_opend_capture_writer import (  # noqa: E402
    DISPOSITION_APPENDED,
    DISPOSITION_DRY_RUN,
    append_from_probe_diagnostic,
    append_vendor_snapshot_capture,
)

_ITEM7_PROBE = _ROOT / "tools" / "moomoo" / "item7_bbo_snapshot.py"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import importlib.util

_spec = importlib.util.spec_from_file_location("imp_item7_bbo_snapshot_cli", _ITEM7_PROBE)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load Item 7 probe from {_ITEM7_PROBE}")
_item7_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_item7_probe)
BboClocks = _item7_probe.BboClocks
DEFAULT_SYMBOL = _item7_probe.DEFAULT_SYMBOL
fetch_vendor_market_snapshot = _item7_probe.fetch_vendor_market_snapshot
run_live_probe = _item7_probe.run_live_probe
monotonic_wall_ns = _item7_probe.monotonic_wall_ns
provider_time_ns_from_row = _item7_probe.provider_time_ns_from_row
VendorSnapshotFetch = _item7_probe.VendorSnapshotFetch


def _default_host() -> str:
    return (os.environ.get("IMP_MOOMOO_HOST") or "127.0.0.1").strip() or "127.0.0.1"


def _default_port() -> int:
    raw = (os.environ.get("IMP_MOOMOO_PORT") or "11111").strip()
    try:
        return int(raw)
    except ValueError:
        return 11111


def _load_vendor_row(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("VENDOR_ROW_MUST_BE_JSON_OBJECT")
    return payload


def _clocks_for_vendor_row(row: dict) -> BboClocks:
    request_ns = monotonic_wall_ns()
    receive_ns = monotonic_wall_ns()
    provider_ns = provider_time_ns_from_row(row, receive_time_ns=receive_ns)
    available_ns = monotonic_wall_ns()
    return BboClocks(
        request_time_ns=request_ns,
        provider_time_ns=provider_ns,
        receive_time_ns=receive_ns,
        available_time_ns=available_ns,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Append lawful Item 7 SNAPSHOT_BBO capture envelope (fail-closed).",
    )
    parser.add_argument(
        "--vendor-row-json",
        type=Path,
        help="Vendor get_market_snapshot row JSON (fixture or recorded probe row).",
    )
    parser.add_argument(
        "--live-probe",
        action="store_true",
        help="Run read-only OpenD SNAPSHOT_BBO probe, then append when validated.",
    )
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL)
    parser.add_argument("--host", default=_default_host())
    parser.add_argument("--port", type=int, default=_default_port())
    parser.add_argument(
        "--require-rth",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="When live-probe, refuse outside US cash RTH.",
    )
    parser.add_argument(
        "--capture-path",
        type=Path,
        default=None,
        help="Override capture JSONL (default: IMP_STATE_DIR/captures/item7-opend-prospective-capture.jsonl).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate without appending capture JSONL.")
    parser.add_argument(
        "--write-failure-receipt",
        action="store_true",
        help="Append structured refusal receipt JSONL (never a fake quote).",
    )
    parser.add_argument("--output", type=Path, help="Optional receipt JSON output path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.vendor_row_json and not args.live_probe:
        print("Specify --vendor-row-json or --live-probe", file=sys.stderr)
        return 2
    if args.vendor_row_json and args.live_probe:
        print("Use only one of --vendor-row-json or --live-probe", file=sys.stderr)
        return 2

    if args.live_probe:
        captured_row: dict | None = None

        def _capture_fetch(*fetch_args: object, **fetch_kwargs: object) -> VendorSnapshotFetch:
            nonlocal captured_row
            fetched = fetch_vendor_market_snapshot(*fetch_args, **fetch_kwargs)
            if fetched.row is not None:
                captured_row = dict(fetched.row)
            return fetched

        diagnostic = run_live_probe(
            symbol=args.symbol,
            host=args.host,
            port=args.port,
            require_rth=args.require_rth,
            fetcher=_capture_fetch,
        )
        row = captured_row if captured_row is not None else {"code": args.symbol}
        result = append_from_probe_diagnostic(
            row,
            diagnostic,
            capture_path=args.capture_path,
            dry_run=args.dry_run,
            write_failure_receipt=args.write_failure_receipt,
        )
    else:
        row = _load_vendor_row(args.vendor_row_json)
        result = append_vendor_snapshot_capture(
            row,
            clocks=_clocks_for_vendor_row(row),
            capture_path=args.capture_path,
            dry_run=args.dry_run,
            write_failure_receipt=args.write_failure_receipt,
        )

    payload = json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)

    if result.disposition in {DISPOSITION_APPENDED, DISPOSITION_DRY_RUN}:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
