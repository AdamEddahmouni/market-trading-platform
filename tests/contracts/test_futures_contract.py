"""Tests for futures contract schema (F1 foundation)."""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.futures import (  # noqa: E402
    BasisDefinition,
    BasisObservation,
    FuturesContract,
    FuturesContractSpec,
    FuturesCurveSnapshot,
    FuturesFamily,
    FuturesPositioningSnapshot,
    RollState,
    cot_point_in_time_valid,
    futures_contract_to_dict,
    futures_curve_to_dict,
    positioning_snapshot_from_dict,
    positioning_snapshot_to_dict,
    trend_baseline_from_dict,
    trend_baseline_to_dict,
    FuturesTrendBaselineSnapshot,
)
from market_platform_foundation.contracts.futures_quality import (  # noqa: E402
    FuturesQualityFlag,
    quality_blocks_curve_analytics,
    quality_blocks_leverage_stress,
)
from market_platform_foundation.futures.notional import (  # noqa: E402
    ES_CONTRACT_SPEC,
    exposure_summary,
    notional_exposure,
    pnl_from_price_change,
)
from market_platform_foundation.futures.roll import (  # noqa: E402
    ContractLiquidity,
    select_lead_contract,
)


class FuturesContractTests(unittest.TestCase):
    def test_contract_distinguishes_family_from_instance(self) -> None:
        contract = FuturesContract(
            instrument_family="ES",
            contract_id="ESU26",
            underlying_id="SPX",
            asset_class="future",
            family=FuturesFamily.EQUITY_INDEX,
            exchange="CME",
            expiration="2026-09-18",
            spec=ES_CONTRACT_SPEC,
            price=Decimal("6000.00"),
            lead_contract=True,
            roll_state=RollState.POST_ROLL,
            event_time="2025-06-02T14:41:00Z",
            available_time="2025-06-02T14:41:00Z",
        )
        payload = futures_contract_to_dict(contract)
        self.assertEqual(payload["instrument_family"], "ES")
        self.assertEqual(payload["contract_id"], "ESU26")
        self.assertNotEqual(payload["instrument_family"], payload["contract_id"])
        self.assertEqual(payload["spec"]["multiplier"], "50")

    def test_cot_publication_delay(self) -> None:
        self.assertFalse(
            cot_point_in_time_valid(
                observation_time="2025-06-03T00:00:00Z",
                publication_time="2025-06-06T17:30:00Z",
                decision_time="2025-06-04T12:00:00Z",
            )
        )
        self.assertTrue(
            cot_point_in_time_valid(
                observation_time="2025-06-03T00:00:00Z",
                publication_time="2025-06-06T17:30:00Z",
                decision_time="2025-06-06T18:00:00Z",
            )
        )

    def test_basis_definition_explicit(self) -> None:
        basis = BasisObservation(
            instrument_family="CL",
            contract_id="CLU25",
            basis_value=Decimal("1.25"),
            basis_definition=BasisDefinition.FUTURES_MINUS_SPOT,
            event_time="2025-06-02T14:00:00Z",
            available_time="2025-06-02T14:00:05Z",
        )
        self.assertEqual(basis.basis_definition, BasisDefinition.FUTURES_MINUS_SPOT)


class FuturesNotionalTests(unittest.TestCase):
    def test_notional_exposure(self) -> None:
        notional = notional_exposure(2, Decimal("50"), Decimal("6000"))
        self.assertEqual(notional, Decimal("600000"))

    def test_pnl_from_ticks_not_percentage(self) -> None:
        pnl = pnl_from_price_change(1, Decimal("10.00"), ES_CONTRACT_SPEC)
        self.assertEqual(pnl, Decimal("500.00"))

    def test_exposure_summary_missing_spec(self) -> None:
        contract = FuturesContract(
            instrument_family="ES",
            contract_id="ESU26",
            underlying_id="SPX",
            asset_class="future",
        )
        summary = exposure_summary(contract, 2)
        self.assertIsNone(summary["notional"])
        self.assertEqual(summary["quality_note"], "CONTRACT_SPEC_OR_PRICE_MISSING")


class FuturesRollTests(unittest.TestCase):
    def test_lead_contract_not_always_nearest(self) -> None:
        contracts = [
            ContractLiquidity("ESM25", "2025-06-20", volume=500000, open_interest=2000000, days_to_expiration=3),
            ContractLiquidity("ESU25", "2025-09-19", volume=800000, open_interest=3500000, days_to_expiration=90),
        ]
        selection = select_lead_contract(contracts, today=__import__("datetime").date(2025, 6, 17))
        self.assertIsNotNone(selection)
        assert selection is not None
        self.assertEqual(selection.lead_contract_id, "ESU25")
        self.assertEqual(selection.nearest_expiry_id, "ESM25")
        self.assertIn(selection.roll_state, {RollState.ROLLING, RollState.EXPIRING})


class FuturesQualityTests(unittest.TestCase):
    def test_curve_blocking_flags(self) -> None:
        self.assertTrue(
            quality_blocks_curve_analytics((FuturesQualityFlag.CURVE_SPARSE.value,))
        )
        self.assertFalse(
            quality_blocks_curve_analytics((FuturesQualityFlag.BASIS_STALE.value,))
        )

    def test_leverage_stress_blocking(self) -> None:
        self.assertTrue(
            quality_blocks_leverage_stress((FuturesQualityFlag.MARGIN_STALE.value,))
        )


class FuturesCurveTests(unittest.TestCase):
    def test_curve_snapshot_serialization(self) -> None:
        curve = FuturesCurveSnapshot(
            instrument_family="CL",
            observation_time="2025-06-02T14:00:00Z",
            available_time="2025-06-02T14:00:05Z",
            contract_ids=("CLU25", "CLZ25"),
            expirations=("2025-08-20", "2025-12-19"),
            prices=(Decimal("75.50"), Decimal("72.25")),
            lead_contract_id="CLU25",
            roll_state=RollState.POST_ROLL,
        )
        payload = futures_curve_to_dict(curve)
        self.assertEqual(len(payload["contract_ids"]), 2)
        self.assertEqual(payload["prices"], ["75.50", "72.25"])

    def test_positioning_snapshot_round_trip(self) -> None:
        snapshot = FuturesPositioningSnapshot(
            instrument_family="ES",
            report_type="disaggregated_futures_only",
            participant_category="managed_money",
            long_positions=190000,
            short_positions=115000,
            spreading=17000,
            net=75000,
            net_percentile=1.0,
            observation_time="2025-05-27T00:00:00Z",
            publication_time="2025-05-30T17:30:00Z",
            data_age_days=6,
            provenance_ref="cot.fixture:ADMITTED-COT-ES-001",
        )
        payload = positioning_snapshot_to_dict(snapshot)
        restored = positioning_snapshot_from_dict(payload)
        self.assertEqual(restored.net, 75000)
        self.assertEqual(restored.participant_category, "managed_money")
        self.assertEqual(restored.publication_time, "2025-05-30T17:30:00Z")

    def test_trend_baseline_round_trip(self) -> None:
        snapshot = FuturesTrendBaselineSnapshot(
            instrument_family="ES",
            trend_1m=1.32,
            trend_3m=3.31,
            trend_6m=8.23,
            trend_12m=17.18,
            vol_estimate=0.00511,
            lookback_bars_used=(("trend_1m", 21), ("trend_3m", 63)),
            observation_time="2025-06-02T14:40:00.000000000Z",
            provenance_ref="bars.fixture.futures_settlement",
        )
        payload = trend_baseline_to_dict(snapshot)
        restored = trend_baseline_from_dict(payload)
        self.assertEqual(restored.trend_3m, 3.31)
        self.assertEqual(restored.instrument_family, "ES")
        self.assertEqual(restored.lookback_bars_used, (("trend_1m", 21), ("trend_3m", 63)))


if __name__ == "__main__":
    unittest.main()
