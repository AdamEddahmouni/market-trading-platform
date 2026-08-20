"""Tests for O1 versioned option product spec registry."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options.spec_registry import resolve_option_spec  # noqa: E402


class OptionsSpecRegistryTests(unittest.TestCase):
    def test_biya_and_nvda_resolve(self) -> None:
        for symbol in ("BIYA", "NVDA", "BIYA_ADJ"):
            spec = resolve_option_spec(symbol, date(2025, 6, 1))
            self.assertIsNotNone(spec, symbol)
            assert spec is not None
            self.assertEqual(spec.multiplier, spec.shares_per_contract)

    def test_unknown_underlying_returns_none(self) -> None:
        self.assertIsNone(resolve_option_spec("ZZZZ", date(2025, 6, 1)))


if __name__ == "__main__":
    unittest.main()
