"""CLI entry for FTEP-V1-002 Finviz prospective observation preflight."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge.ftep_finviz_prospective_preflight import (  # noqa: E402
    main,
)

if __name__ == "__main__":
    raise SystemExit(main())
