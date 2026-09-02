"""Regression coverage for repository test-package discovery."""

from __future__ import annotations

import importlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RepositoryTestPackageTests(unittest.TestCase):
    def test_repository_tests_package_owns_fixture_imports(self) -> None:
        package = importlib.import_module("tests")
        package_paths = {Path(path).resolve() for path in package.__path__}
        self.assertIn(ROOT / "tests", package_paths)

        intelligence = importlib.import_module("tests.intelligence")
        intelligence_paths = {Path(path).resolve() for path in intelligence.__path__}
        self.assertIn(ROOT / "tests" / "intelligence", intelligence_paths)


if __name__ == "__main__":
    unittest.main()
