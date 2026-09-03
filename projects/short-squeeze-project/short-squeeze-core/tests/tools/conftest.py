"""Test support for the isolated collection tool.

Adds the repository root to ``sys.path`` so ``import tools.ibkr_historical_export`` works
(the tool lives at the repo root, outside the editable ``src`` package). Shared synthetic
fakes live in ``tests/tools/ibkr_historical_export/_fakes.py`` (imported relatively by the
packaged test modules), so no socket is ever opened and no real bars are replayed.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
