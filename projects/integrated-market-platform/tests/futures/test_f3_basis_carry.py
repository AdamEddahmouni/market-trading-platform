"""F3 basis and carry engine tests."""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.futures import FuturesCurveSnapshot  # noqa: E402
from market_platform_foundation.donor_bridge.cross_lane_adapter import (  # noqa: E402
    build_cross_lane_snapshot_from_futures,
)
from market_platform_foundation.futures.basis import basis_payload, build_basis_observation  # noqa: E402
from market_platform_foundation.futures.carry import carry_from_curve, carry_payload  # noqa: E402
from market_platform_foundation.futures.curve import curve_regime, curve_snapshot_payload  # noqa: E402
from market_platform_foundation.providers.adapters.fixture_futures_chain import (  # noqa: E402
    FixtureFuturesChainProvider,
)
from market_platform_foundation.features.institutional import configure_institutional_ledger  # noqa: E402
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.whale_ledger import build_combined_fixture_ledger  # noqa: E402
from market_platform_foundation.providers.projections import build_workspace_futures_payload  # noqa: E402


class FuturesF3BasisCarryTests(unittest.TestCase):
    def test_es_fixture_basis_from_spot(self) -> None:
        provider = FixtureFuturesChainProvider()
        chain = provider.fetch_chain("ES")
        from market_platform_foundation.futures.curve import build_curve_snapshot_from_chain

        snapshot = build_curve_snapshot_from_chain(chain)
        assert snapshot is not None
        observation = build_basis_observation(snapshot, Decimal("5995.0"), spot_reference_id="SPX_PROXY")
        assert observation is not None
        self.assertEqual(str(observation.basis_value), "6.75")

    def test_basis_fail_closed_without_spot(self) -> None:
        snapshot = FuturesCurveSnapshot(
            instrument_family="ES",
            observation_time="2025-06-02T14:41:00.000000000Z",
            available_time="2025-06-02T14:41:00.000000000Z",
            contract_ids=("ES202506", "ES202509"),
            expirations=("2025-06-20", "2025-09-20"),
            prices=(Decimal("6001.75"), Decimal("6008.0")),
        )
        payload = basis_payload(snapshot, None)
        self.assertFalse(payload.get("available"))
        self.assertEqual(payload.get("reason"), "BASIS_REFERENCE_MISSING")

    def test_es_contango_positive_carry(self) -> None:
        provider = FixtureFuturesChainProvider()
        chain = provider.fetch_chain("ES")
        curve = curve_snapshot_payload(chain)
        self.assertEqual(curve.get("regime"), "contango")
        from market_platform_foundation.futures.curve import build_curve_snapshot_from_chain

        snapshot = build_curve_snapshot_from_chain(chain)
        assert snapshot is not None
        carry = carry_from_curve(snapshot)
        assert carry is not None
        self.assertGreater(carry.annualized_carry, 0)
        self.assertEqual(carry.formula_tag, "CALENDAR_SPREAD_IMPLIED")

    def test_carry_matches_curve_regime_sign(self) -> None:
        snapshot = FuturesCurveSnapshot(
            instrument_family="ES",
            observation_time="2025-06-02T14:41:00.000000000Z",
            available_time="2025-06-02T14:41:00.000000000Z",
            contract_ids=("ES202506", "ES202509"),
            expirations=("2025-06-20", "2025-09-20"),
            prices=(Decimal("6001.75"), Decimal("6008.0")),
        )
        carry = carry_from_curve(snapshot)
        assert carry is not None
        regime = curve_regime(snapshot)
        if regime == "contango":
            self.assertGreater(carry.annualized_carry, 0)
        elif regime == "backwardation":
            self.assertLess(carry.annualized_carry, 0)

    def test_workspace_futures_payload_carry_available(self) -> None:
        ledger = build_combined_fixture_ledger()
        configure_institutional_ledger(ledger)
        cutoff = iso_to_epoch_ns("2025-06-02T14:41:07.000000000Z")
        payload = build_workspace_futures_payload(
            "ES",
            as_of_context={"mode": "REPLAY"},
            prediction_cutoff=cutoff,
        )
        configure_institutional_ledger(None)
        self.assertTrue(payload.get("available"))
        self.assertTrue(payload.get("futures_carry_available"))
        carry = payload.get("carry_observation", {})
        self.assertTrue(carry.get("available"))
        basis = payload.get("basis_observation", {})
        self.assertTrue(basis.get("available"))

    def test_cross_lane_carry_evidence(self) -> None:
        payload = {
            "available": True,
            "snapshot_count": 1,
            "imbalance_signal": "neutral",
            "book_pressure_side": "neutral",
            "curve_snapshot": {"available": True, "regime": "contango"},
            "carry_observation": {
                "available": True,
                "annualized_carry": 0.05,
            },
            "futures_carry_available": True,
        }
        snapshot, evidence = build_cross_lane_snapshot_from_futures(payload)
        assert snapshot is not None
        self.assertTrue(snapshot.get("futures_carry_available"))
        signals = [row.get("signal") for row in evidence]
        self.assertIn("FUTURES_CARRY_POSITIVE", signals)


if __name__ == "__main__":
    unittest.main()
