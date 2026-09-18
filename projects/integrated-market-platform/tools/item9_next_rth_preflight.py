"""CLI entry for Item 9 next-RTH prospective collection preflight."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.item9_next_rth_preflight import (  # noqa: E402
    main,
)

if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv or argv[0] == "next-rth-preflight" or argv[0].startswith("-"):
        if argv and argv[0] == "next-rth-preflight":
            argv = argv[1:]
        argv = ["next-rth-preflight", *argv]
    raise SystemExit(main(argv))
