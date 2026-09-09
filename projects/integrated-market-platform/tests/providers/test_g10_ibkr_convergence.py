"""G10 IBKR provider surface convergence tests (BL-0301)."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.providers.ibkr_observational.account_observation import (
    READ_ONLY_OBSERVATIONAL,
    normalize_ibkr_account_discovery,
)
from market_platform_foundation.providers.ibkr_observational.capability import (
    IBKR_CAPABILITY_ACCOUNT_READ,
    IBKR_CAPABILITY_HISTORICAL_BARS,
    IBKR_CAPABILITY_L1,
    IBKR_CAPABILITY_L2,
    IBKR_CAPABILITY_TRADES,
    IBKR_FORBIDDEN_CAPABILITIES,
    register_ibkr_observational,
)
from market_platform_foundation.providers.ibkr_observational.historical_bars import (
    normalize_ibkr_history_payload,
)
from market_platform_foundation.providers.registry import ProviderRegistry


class G10IbkrConvergenceTests(unittest.TestCase):
    def test_capability_matrix_registers_expected_caps(self) -> None:
        registry = ProviderRegistry()
        descriptor = register_ibkr_observational(registry)
        cap_ids = {cap.capability_id for cap in descriptor.capabilities}
        self.assertIn(IBKR_CAPABILITY_L1, cap_ids)
        self.assertIn(IBKR_CAPABILITY_L2, cap_ids)
        self.assertIn(IBKR_CAPABILITY_TRADES, cap_ids)
        self.assertIn(IBKR_CAPABILITY_HISTORICAL_BARS, cap_ids)
        self.assertIn(IBKR_CAPABILITY_ACCOUNT_READ, cap_ids)
        for forbidden in IBKR_FORBIDDEN_CAPABILITIES:
            self.assertNotIn(forbidden, cap_ids)

    def test_historical_bar_normalization(self) -> None:
        bars = normalize_ibkr_history_payload(
            {"data": [{"t": 1_700_000_000, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}]},
            instrument_id="AAPL",
            interval="1h",
            received_time_ns=2_000_000_000,
        )
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].instrument_id, "AAPL")
        self.assertEqual(bars[0].pit_semantics, "POINT_IN_TIME")
        self.assertIsNotNone(bars[0].source_time_ns)

    def test_account_read_is_read_only_observational(self) -> None:
        observation = normalize_ibkr_account_discovery(
            {"accounts": ["DU1234567"]},
            received_time_ns=1,
        )
        self.assertEqual(observation.authority, READ_ONLY_OBSERVATIONAL)
        self.assertFalse(observation.entitlement_context.get("execution_authority"))

    def test_no_src_tools_ibkr_imports(self) -> None:
        foundation = SRC / "market_platform_foundation"
        violations: list[str] = []
        for path in foundation.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "tools.ibkr" in alias.name:
                            violations.append(f"{path}: import {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module and "tools.ibkr" in node.module:
                    violations.append(f"{path}: from {node.module}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
