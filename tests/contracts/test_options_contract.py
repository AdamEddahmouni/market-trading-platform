"""Tests for options contract schema (O1 foundation)."""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.options import (  # noqa: E402
    DeliverableSpec,
    OptionContract,
    option_contract_to_dict,
)
from market_platform_foundation.contracts.options_quality import (  # noqa: E402
    OptionQualityFlag,
    quality_blocks_surface_fit,
)


class OptionContractTests(unittest.TestCase):
    def test_option_contract_round_trip_dict(self) -> None:
        contract = OptionContract(
            underlying_id="BIYA",
            option_id="BIYA250117C00005000",
            call_put="call",
            strike=Decimal("5.00"),
            expiration="2025-01-17",
            dte=30,
            multiplier=Decimal("100"),
            deliverable=DeliverableSpec(shares_per_contract=Decimal("100")),
            bid=Decimal("0.45"),
            ask=Decimal("0.55"),
            volume=1200,
            open_interest=4500,
            provider="options.fixture.activity",
            event_time="2025-01-01T15:00:00Z",
            available_time="2025-01-01T15:00:05Z",
            quality_flags=(OptionQualityFlag.FLOW_DIRECTION_UNCERTAIN.value,),
            provenance_ref="fixture:biya_options_slice",
        )
        payload = option_contract_to_dict(contract)
        self.assertEqual(payload["underlying_id"], "BIYA")
        self.assertEqual(payload["call_put"], "call")
        self.assertEqual(payload["multiplier"], "100")
        self.assertEqual(payload["deliverable"]["shares_per_contract"], "100")
        self.assertIn(OptionQualityFlag.FLOW_DIRECTION_UNCERTAIN.value, payload["quality_flags"])


class OptionQualityTests(unittest.TestCase):
    def test_surface_blocking_flags(self) -> None:
        self.assertTrue(
            quality_blocks_surface_fit((OptionQualityFlag.SURFACE_SPARSE.value,))
        )
        self.assertFalse(
            quality_blocks_surface_fit((OptionQualityFlag.WIDE_OPTION_SPREAD.value,))
        )


if __name__ == "__main__":
    unittest.main()
