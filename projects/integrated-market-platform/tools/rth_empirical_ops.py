"""CLI: RTH empirical operations command center (Phase 5 Lane H)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.operations.rth_empirical_ops import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
