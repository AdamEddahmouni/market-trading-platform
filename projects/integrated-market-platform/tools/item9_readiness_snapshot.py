"""CLI: Item 9 validation readiness snapshot (read-only; no fitting)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.item9_readiness_snapshot import (  # noqa: E402
    build_item9_readiness_snapshot,
    resolve_governed_receipt_dir,
)
from market_platform_foundation.paper.calibration.item9_validation_readiness_contract import (  # noqa: E402
    AUTHORIZATION_ABSENT,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Item 9 validation readiness snapshot (read-only). "
            "Never fits, writes receipts, synthesizes gap bars, or claims CALIBRATED."
        ),
    )
    parser.add_argument(
        "--receipt-dir",
        type=Path,
        default=None,
        help="Governed receipt directory (default: frozen collector path when present).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="IMP package root (default: auto-detect).",
    )
    parser.add_argument(
        "--prefer-local-default",
        action="store_true",
        help="Use IMP-local DEFAULT_RECEIPT_DIR instead of frozen collector checkout.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Write JSON to path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    imp_root = args.repo_root
    if imp_root is None:
        from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (
            imp_package_root,
        )

        imp_root = imp_package_root()
    receipt_dir = resolve_governed_receipt_dir(
        receipt_dir=args.receipt_dir,
        imp_root=imp_root,
        prefer_frozen_collector=not args.prefer_local_default,
    )
    snapshot = build_item9_readiness_snapshot(
        receipt_dir,
        imp_root=imp_root,
        authorization_state=AUTHORIZATION_ABSENT,
    )
    text = json.dumps(snapshot, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
