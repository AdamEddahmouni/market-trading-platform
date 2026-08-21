"""Tests for futures asset-family plugin models (F6)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.futures import FuturesFamily
from market_platform_foundation.futures.families.registry import (
    family_context_payload,
    resolve_family_for_symbol,
    resolve_family_model,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.providers.composition import configure_fixture_provider_composition
from market_platform_foundation.providers.projections import build_workspace_futures_payload
from market_platform_foundation.features.institutional import configure_institutional_ledger
from market_platform_foundation.providers.whale_ledger import build_combined_fixture_ledger


class FamilyModelTests(unittest.TestCase):
    def test_resolve_equity_index_for_es(self) -> None:
        self.assertEqual(resolve_family_for_symbol("ES"), FuturesFamily.EQUITY_INDEX)
        model = resolve_family_model(FuturesFamily.EQUITY_INDEX)
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.family, FuturesFamily.EQUITY_INDEX)

    def test_unimplemented_family_fail_closed(self) -> None:
        payload = family_context_payload(
            "ZN",
            {"futures_carry_available": True},
        )
        self.assertFalse(payload.get("futures_family_available"))

    def test_energy_family_resolves_for_cl(self) -> None:
        self.assertEqual(resolve_family_for_symbol("CL"), FuturesFamily.ENERGY)
        model = resolve_family_model(FuturesFamily.ENERGY)
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.family, FuturesFamily.ENERGY)

    def test_es_family_context_golden_fixture_regression(self) -> None:
        expected_path = ROOT / "tests" / "fixtures" / "futures" / "es_family_context_expected.json"
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        cutoff = iso_to_epoch_ns(str(expected["cutoff"]))

        configure_fixture_provider_composition()
        configure_institutional_ledger(build_combined_fixture_ledger(as_of_time_ns=cutoff))
        payload = build_workspace_futures_payload(
            "ES",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=cutoff,
        )
        configure_institutional_ledger(None)

        exp = expected["expected"]
        self.assertTrue(payload.get("futures_family_available"))
        snapshot = payload.get("family_context_snapshot")
        self.assertIsInstance(snapshot, dict)
        assert isinstance(snapshot, dict)
        exp_snapshot = exp["family_context_snapshot"]
        self.assertEqual(snapshot.get("family"), exp_snapshot["family"])
        self.assertEqual(snapshot.get("model_version"), exp_snapshot["model_version"])
        self.assertIn(exp_snapshot["curve_read_contains"], str(snapshot.get("curve_read", "")).lower())
        self.assertIn(
            exp_snapshot["positioning_read_contains"],
            str(snapshot.get("positioning_read", "")).lower(),
        )
        self.assertIn(
            exp_snapshot["event_context_read_contains"],
            str(snapshot.get("event_context_read", "")),
        )
        self.assertIn(
            exp_snapshot["risk_context_contains"],
            str(snapshot.get("risk_context", "")).lower(),
        )


if __name__ == "__main__":
    unittest.main()
