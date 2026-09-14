"""CLI entry for Path A US equity RTH preflight (software only)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.strategy.path_a_rth_preflight import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
