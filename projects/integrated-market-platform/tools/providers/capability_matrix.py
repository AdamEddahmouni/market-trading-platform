"""Emit a deterministic provider capability-matrix snapshot (Wave B foundation)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _ensure_src_on_path() -> None:
    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def main(argv: list[str] | None = None) -> int:
    _ensure_src_on_path()
    from market_platform_foundation.providers.capability_snapshot import (
        build_capability_matrix_snapshot,
        serialize_snapshot,
    )
    from tools.provider_readiness import collect_readiness

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write snapshot JSON to this path (default: stdout)",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=ROOT,
        help="IMP repository root (defaults to parent of tools/)",
    )
    parser.add_argument(
        "--skip-readiness",
        action="store_true",
        help="Do not merge value-blind provider_readiness gate rows",
    )
    args = parser.parse_args(argv)

    readiness = None
    if not args.skip_readiness:
        readiness = collect_readiness(os.environ, repository_root=args.repository_root)

    snapshot = build_capability_matrix_snapshot(
        repository_root=args.repository_root,
        readiness_report=readiness,
    )
    payload = serialize_snapshot(snapshot)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
