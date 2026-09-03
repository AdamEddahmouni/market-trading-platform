import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
COLLECTOR = ROOT / "pipelines" / "stock_data"


class MonorepoBoundaryTests(unittest.TestCase):
    def test_collector_is_nested_without_mutable_data(self):
        self.assertTrue((COLLECTOR / "pyproject.toml").is_file())
        self.assertTrue((COLLECTOR / "src" / "pipeline.py").is_file())
        self.assertFalse((COLLECTOR / ".git").exists())
        self.assertFalse((COLLECTOR / "database" / "market_data.db").exists())

    def test_platform_core_does_not_import_collector_dependencies(self):
        prohibited = ("duckdb", "numpy", "pandas", "requests", "sqlalchemy", "yfinance")
        platform = ROOT / "src" / "market_platform_foundation"
        violations = []
        for path in platform.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            if any(f"import {name}" in text or f"from {name}" in text for name in prohibited):
                violations.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(violations, [])
