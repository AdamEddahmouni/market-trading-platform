"""Fixture ingestion conformance tests for O1 OptionContract."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.options import (  # noqa: E402
    option_contract_from_dict,
    option_contract_to_dict,
)
from market_platform_foundation.providers.adapters.fixture_options import (  # noqa: E402
    DEFAULT_OPTIONS_FIXTURE,
)
from market_platform_foundation.providers.adapters.option_contract_builder import (  # noqa: E402
    activity_to_option_contract,
)


class OptionsFixtureIngestionTests(unittest.TestCase):
    def test_biya_fixture_round_trip(self) -> None:
        payload = json.loads(DEFAULT_OPTIONS_FIXTURE.read_text(encoding="utf-8"))
        activity = payload["activities"][0]
        contract = activity_to_option_contract(
            activity,
            symbol="BIYA",
            fixture_id="FIXTURE-OPTIONS-BIYA",
            provider_id="options.fixture.activity",
        )
        restored = option_contract_from_dict(option_contract_to_dict(contract))
        self.assertEqual(restored.option_id, contract.option_id)
        self.assertEqual(restored.strike, contract.strike)

    def test_from_dict_missing_fields(self) -> None:
        with self.assertRaises(ValueError):
            option_contract_from_dict({"underlying_id": "BIYA"})


if __name__ == "__main__":
    unittest.main()
