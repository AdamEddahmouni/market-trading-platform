"""Run one Phase 0 unittest file after installing the deny-first guard."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from market_platform_foundation.offline_guard import install_guard


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: run_test_file.py TEST_FILE")
    test_path = Path(sys.argv[1]).resolve()
    if test_path.parent != (REPOSITORY_ROOT / "tests" / "phase0").resolve():
        raise SystemExit("test file must be in tests/phase0")
    install_guard([])
    suite = unittest.defaultTestLoader.discover(
        str(test_path.parent), pattern=test_path.name
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
