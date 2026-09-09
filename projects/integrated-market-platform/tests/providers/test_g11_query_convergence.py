"""G11 query protocol boundary and convergence tests."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.market_data.runtime_composition import (
    ObservationalRuntimeComposition,
)
from market_platform_foundation.providers.ibkr_observational.identity import (
    IdentityAdmissionError,
)
from market_platform_foundation.providers.ibkr_observational.query_provider import (
    IbkrObservationalQueryService,
)

from ibkr_observational_support import FakeLookup, FakeQueryProvider, make_record


AAPL = make_record("AAPL")


class G11QueryConvergenceTests(unittest.TestCase):
    def test_query_service_resolves_equity_contract(self) -> None:
        provider = FakeQueryProvider(
            secdef_rows={
                "AAPL": [
                    {
                        "symbol": "AAPL",
                        "conid": 265598,
                        "secType": "STK",
                        "exchange": "SMART",
                        "currency": "USD",
                    }
                ]
            }
        )
        service = IbkrObservationalQueryService(
            provider=provider,
            lookup=FakeLookup(AAPL),
        )
        result = service.resolve_contract("AAPL")
        self.assertTrue(result.accepted)
        self.assertEqual(result.instrument_id, "AAPL")
        self.assertIsNotNone(result.qualification)
        self.assertEqual(result.qualification.con_id, 265598)

    def test_ambiguous_equity_lookup_rejected(self) -> None:
        provider = FakeQueryProvider(secdef_rows={"UNKNOWN": []})
        service = IbkrObservationalQueryService(
            provider=provider,
            lookup=FakeLookup(),
        )
        result = service.resolve_contract("UNKNOWN")
        self.assertFalse(result.accepted)

    def test_specific_option_requires_complete_identity(self) -> None:
        provider = FakeQueryProvider()
        service = IbkrObservationalQueryService(
            provider=provider,
            lookup=FakeLookup(AAPL),
        )
        option = SimpleNamespace(
            symbol="AAPL",
            secType="OPT",
            exchange="SMART",
            currency="USD",
        )
        result = service.resolve_contract("AAPL", contract_builder=option)
        self.assertFalse(result.accepted)

    def test_future_family_rejected(self) -> None:
        provider = FakeQueryProvider()
        service = IbkrObservationalQueryService(
            provider=provider,
            lookup=FakeLookup(AAPL),
        )
        future = SimpleNamespace(
            symbol="ES",
            secType="FUT",
            exchange="GLOBEX",
            currency="USD",
        )
        result = service.resolve_contract("ES", contract_builder=future)
        self.assertFalse(result.accepted)

    def test_no_request_invents_canonical_identity(self) -> None:
        provider = FakeQueryProvider(
            secdef_rows={
                "AAPL": [
                    {
                        "symbol": "AAPL",
                        "conid": 999,
                        "secType": "STK",
                        "exchange": "SMART",
                        "currency": "USD",
                    }
                ]
            }
        )
        service = IbkrObservationalQueryService(
            provider=provider,
            lookup=FakeLookup(AAPL),
        )
        result = service.resolve_contract("AAPL")
        self.assertEqual(result.instrument_id, "AAPL")
        self.assertNotEqual(result.qualification.symbol, result.instrument_id + "_FAKE")

    def test_composition_query_delegates(self) -> None:
        composition = ObservationalRuntimeComposition()
        provider = FakeQueryProvider(
            secdef_rows={
                "AAPL": [
                    {
                        "symbol": "AAPL",
                        "conid": 265598,
                        "secType": "STK",
                        "exchange": "SMART",
                        "currency": "USD",
                    }
                ]
            }
        )
        composition.attach_ibkr_query_service(provider, lookup=FakeLookup(AAPL))
        result = composition.resolve_contract("AAPL")
        self.assertTrue(result.accepted)

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
