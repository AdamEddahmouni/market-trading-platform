"""Tests for F1 versioned futures spec registry."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.futures.notional import ES_CONTRACT_SPEC  # noqa: E402
from market_platform_foundation.futures.spec_registry import resolve_futures_spec  # noqa: E402


class FuturesSpecRegistryTests(unittest.TestCase):
    def test_es_spec_resolves(self) -> None:
        spec = resolve_futures_spec("ES", date(2025, 6, 1))
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.spec_version, ES_CONTRACT_SPEC.spec_version)
        self.assertEqual(spec.multiplier, ES_CONTRACT_SPEC.multiplier)

    def test_unknown_family_returns_none(self) -> None:
        self.assertIsNone(resolve_futures_spec("NQ", date(2025, 6, 1)))

    def test_date_boundary_before_effective_from(self) -> None:
        self.assertIsNone(resolve_futures_spec("ES", date(2019, 12, 31)))


if __name__ == "__main__":
    unittest.main()
