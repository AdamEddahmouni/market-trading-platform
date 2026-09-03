"""Tests for F9 relative-value spreads and F10 simulator extensions."""

from __future__ import annotations

import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.execution.simulator import (  # noqa: E402
    simulate_calendar_spread_pnl,
    simulate_futures_roll,
    simulate_variation_margin_change,
)
from market_platform_foundation.futures.curve import build_curve_snapshot_from_chain  # noqa: E402
from market_platform_foundation.futures.relative_value import (  # noqa: E402
    compute_calendar_spread,
    relative_value_payload,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.adapters.fixture_futures_chain import (  # noqa: E402
    FixtureFuturesChainProvider,
)
from market_platform_foundation.providers.projections import (  # noqa: E402
    _enrich_es_futures_f9_payload,
)


class RelativeValueTests(unittest.TestCase):
    def test_calendar_spread_math(self) -> None:
        spread = compute_calendar_spread(Decimal("6001.75"), Decimal("6008.0"))
        self.assertEqual(spread, Decimal("6.25"))

    def test_es_relative_value_golden(self) -> None:
        expected_path = ROOT / "tests" / "fixtures" / "futures" / "es_relative_value_expected.json"
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        cutoff = iso_to_epoch_ns(str(expected["cutoff"]))
        chain_result = FixtureFuturesChainProvider().fetch_chain(
            expected["symbol"],
            as_of_time_ns=cutoff,
        )
        curve = build_curve_snapshot_from_chain(chain_result)
        payload = relative_value_payload(curve, chain_result, decision_time=cutoff)
        self.assertTrue(payload["futures_relative_value_available"])
        snapshot = payload["relative_value_snapshot"]
        exp = expected["expected"]["relative_value_snapshot"]
        self.assertEqual(snapshot["spread_value"], exp["spread_value"])
        self.assertEqual(snapshot["front_contract_id"], exp["front_contract_id"])
        self.assertEqual(snapshot["back_contract_id"], exp["back_contract_id"])

    def test_futures_workspace_includes_relative_value(self) -> None:
        cutoff = iso_to_epoch_ns("2025-06-02T14:41:07.000000000Z")
        from market_platform_foundation.providers.projections import _enrich_es_futures_f9_payload

        payload = _enrich_es_futures_f9_payload(
            {"symbol": "ES", "available": True},
            prediction_cutoff=cutoff,
        )
        self.assertTrue(payload.get("futures_relative_value_available"))
        self.assertIsNotNone(payload.get("relative_value_snapshot"))


class FuturesSimulatorF10Tests(unittest.TestCase):
    def test_variation_margin_change(self) -> None:
        result = simulate_variation_margin_change(
            previous_price=6000.0,
            current_price=6002.0,
            quantity=2,
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["variation_margin_change"], 200.0)

    def test_roll_with_variation_margin(self) -> None:
        result = simulate_futures_roll(
            from_contract_id="ES202506",
            to_contract_id="ES202509",
            quantity=1,
            roll_gap=1.0,
            previous_price=6000.0,
            current_price=6001.0,
        )
        self.assertTrue(result["available"])
        self.assertIsNotNone(result.get("variation_margin"))

    def test_calendar_spread_pnl(self) -> None:
        result = simulate_calendar_spread_pnl(
            front_price=6001.75,
            back_price=6008.0,
            quantity=1,
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["spread_event"]["spread_pnl"], 312.5)


if __name__ == "__main__":
    unittest.main()
