"""Tests for O1 corporate action adjustment semantics."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.options import option_contract_from_dict  # noqa: E402
from market_platform_foundation.contracts.options_quality import (  # noqa: E402
    OptionQualityFlag,
    quality_blocks_surface_fit,
)
from market_platform_foundation.providers.adapters.option_contract_builder import (  # noqa: E402
    activity_to_option_contract,
    activities_to_chain_dicts,
)


class CorporateActionOptionsTests(unittest.TestCase):
    def test_adjusted_deliverable_sets_flag(self) -> None:
        contract = activity_to_option_contract(
            {
                "event_time": "2026-07-21T20:31:00.000000000Z",
                "expiry": "2026-09-19",
                "option_type": "call",
                "strike": 2.0,
                "bid": 0.39,
                "ask": 0.42,
                "open_interest": 320,
                "corporate_action_adjusted": True,
                "deliverable_shares": 50,
            },
            symbol="BIYA_ADJ",
            fixture_id="FIXTURE-TEST",
            provider_id="test",
        )
        self.assertIn(OptionQualityFlag.CORPORATE_ACTION_ADJUSTED.value, contract.quality_flags)
        self.assertIsNotNone(contract.deliverable)
        assert contract.deliverable is not None
        self.assertEqual(contract.deliverable.shares_per_contract, 50)

    def test_unknown_deliverable_blocks_surface(self) -> None:
        contract = activity_to_option_contract(
            {
                "event_time": "2026-07-21T20:31:01.000000000Z",
                "expiry": "2026-09-19",
                "option_type": "put",
                "strike": 1.75,
                "bid": 0.16,
                "ask": 0.18,
                "open_interest": 150,
                "corporate_action_adjusted": True,
                "deliverable_unknown": True,
            },
            symbol="BIYA_ADJ",
            fixture_id="FIXTURE-TEST",
            provider_id="test",
        )
        self.assertIn(OptionQualityFlag.ADJUSTED_DELIVERABLE_UNKNOWN.value, contract.quality_flags)
        self.assertTrue(quality_blocks_surface_fit(contract.quality_flags))

    def test_round_trip_from_chain_dict(self) -> None:
        rows = activities_to_chain_dicts(
            [
                {
                    "event_time": "2026-07-21T20:31:00.000000000Z",
                    "expiry": "2026-09-19",
                    "option_type": "call",
                    "strike": 2.0,
                    "bid": 0.39,
                    "ask": 0.42,
                    "open_interest": 320,
                    "corporate_action_adjusted": True,
                    "deliverable_shares": 50,
                }
            ],
            symbol="BIYA_ADJ",
            fixture_id="FIXTURE-TEST",
            provider_id="test",
        )
        restored = option_contract_from_dict(rows[0])
        self.assertIn(OptionQualityFlag.CORPORATE_ACTION_ADJUSTED.value, restored.quality_flags)


if __name__ == "__main__":
    unittest.main()
