"""XA-04 operations tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.xa04.operations import (  # noqa: E402
    execute,
    reset_repository_for_tests,
)


class Xa04OperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_repository_for_tests()

    def test_status_ok(self) -> None:
        result = execute("XA04.OP.STATUS")
        self.assertEqual(result.outcome_code, "OK")
        self.assertEqual(result.capability_id, "XA04.OP.STATUS")
        self.assertFalse(result.verification["paid_mongodb_required"])

    def test_list_catalog_ok(self) -> None:
        result = execute("XA04.OP.LIST_CATALOG")
        self.assertEqual(result.outcome_code, "OK")
        self.assertIn("audit_matrix", result.verification)


if __name__ == "__main__":
    unittest.main()
