"""Compatibility contract for the legacy full-suite entry point."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import run_all_tests


class RunAllTestsWrapperTests(unittest.TestCase):
    def test_delegates_to_validate_full_and_preserves_exit_status(self) -> None:
        self.assertTrue(hasattr(run_all_tests, "validate_main"))
        with patch.object(run_all_tests, "validate_main", return_value=7) as delegated:
            self.assertEqual(run_all_tests.main(["--workers", "2"]), 7)
        delegated.assert_called_once_with(["full", "--workers", "2"])


if __name__ == "__main__":
    unittest.main()
