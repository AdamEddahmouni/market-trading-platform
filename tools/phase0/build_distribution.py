"""Build the deterministic Phase 0 local artifact."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.offline_guard import install_guard


def main() -> int:
    install_guard([])
    from market_platform_foundation.canonical import write_canonical_json
    from market_platform_foundation.distribution import build_distribution

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    result = build_distribution(ROOT, output)
    write_canonical_json(output / "build-result.json", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
