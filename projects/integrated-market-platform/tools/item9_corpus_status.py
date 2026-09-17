"""CLI: Item 9 governed prospective receipt corpus status (read-only; Lane D)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    DEFAULT_RECEIPT_DIR,
    imp_package_root,
)
from market_platform_foundation.paper.calibration.item9_calibration_protocol import (  # noqa: E402
    build_item9_corpus_status_report,
    classify_item9_receipt,
    load_governed_receipt,
    validate_item9_governed_receipt_dir,
)


def _resolve_receipt_dir(receipt_dir: Path | None, repo_root: Path | None) -> Path:
    base = repo_root or imp_package_root()
    if receipt_dir is None:
        return base / DEFAULT_RECEIPT_DIR
    path = receipt_dir
    if not path.is_absolute():
        path = base / path
    return path


def _emit(payload: dict[str, object], output: Path | None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Item 9 prospective proof receipt corpus status (read-only). "
            "Scans governed JSON only; never fits, writes receipts, or claims CALIBRATED."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    status_parent = argparse.ArgumentParser(add_help=False)
    status_parent.add_argument(
        "--receipt-dir",
        type=Path,
        default=None,
        help=f"Governed receipt directory (default: {DEFAULT_RECEIPT_DIR} under IMP root).",
    )
    status_parent.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="IMP package root for relative --receipt-dir (default: auto-detect).",
    )
    status_parent.add_argument("--output", type=Path, default=None, help="Write JSON report to path.")

    sub.add_parser(
        "corpus-status",
        parents=[status_parent],
        help="Scan governed receipts and emit corpus counts + sample gate progress.",
    )
    sub.add_parser(
        "status",
        parents=[status_parent],
        help="Alias for corpus-status.",
    )

    classify = sub.add_parser(
        "classify",
        help="Classify one governed receipt JSON (stdout JSON; read-only).",
    )
    classify.add_argument("--receipt", type=Path, required=True, help="Path to receipt JSON.")
    classify.add_argument("--output", type=Path, default=None)

    validate = sub.add_parser(
        "validate",
        parents=[status_parent],
        help="Validate all governed receipts under --receipt-dir (read-only).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command in {"corpus-status", "status"}:
        receipt_dir = _resolve_receipt_dir(args.receipt_dir, args.repo_root)
        report = build_item9_corpus_status_report(receipt_dir)
        _emit(report, args.output)
        return 0

    if args.command == "classify":
        payload, load_error = load_governed_receipt(args.receipt)
        if payload is None:
            body = {
                "ok": False,
                "path": str(args.receipt),
                "load_error": load_error,
                "calibrated": False,
                "empirical_active": False,
            }
            _emit(body, args.output)
            return 2
        classified = classify_item9_receipt(payload)
        body = {
            "ok": True,
            "path": str(args.receipt),
            "classification": classified.to_dict(),
            "calibrated": False,
            "empirical_active": False,
        }
        _emit(body, args.output)
        return 0

    if args.command == "validate":
        receipt_dir = _resolve_receipt_dir(args.receipt_dir, args.repo_root)
        report = validate_item9_governed_receipt_dir(receipt_dir)
        _emit(report, args.output)
        return 0 if report["verdict"] == "VALID" else 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
