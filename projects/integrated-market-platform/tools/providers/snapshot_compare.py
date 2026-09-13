"""CLI for frozen provider snapshot comparison (fixture/offline captures)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _ensure_src_on_path() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def main(argv: list[str] | None = None) -> int:
    _ensure_src_on_path()
    from market_platform_foundation.providers.snapshot_compare import (
        compare_frozen_provider_snapshot,
        frozen_compare_snapshot_from_dict,
        summarize_missingness,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "snapshot",
        type=Path,
        help="Frozen compare snapshot JSON (providers.frozen_observation_compare)",
    )
    parser.add_argument(
        "--reference",
        help="Reference provider_id (default: lexicographically first arm)",
    )
    parser.add_argument(
        "--numeric-tolerance",
        type=float,
        default=1e-9,
        help="Absolute tolerance for numeric value disagreement",
    )
    args = parser.parse_args(argv)

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    snapshot = frozen_compare_snapshot_from_dict(payload)
    report = compare_frozen_provider_snapshot(
        snapshot,
        reference_provider_id=args.reference,
        numeric_tolerance=args.numeric_tolerance,
    )
    out = report.to_dict()
    out["missingness_summary"] = summarize_missingness(report)
    sys.stdout.write(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
