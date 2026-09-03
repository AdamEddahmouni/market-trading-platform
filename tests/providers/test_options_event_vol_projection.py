"""Tests for options event volatility workspace projection (O7 wiring)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.options.event_vol import load_earnings_event_fixture  # noqa: E402
from market_platform_foundation.providers.projections import build_workspace_options_payload  # noqa: E402
from market_platform_foundation.providers.whale_ledger import bootstrap_default_providers  # noqa: E402

_CUTOFF = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
_EARNINGS_FIXTURE = (
    ROOT / "tests" / "fixtures" / "providers" / "options" / "nvda_earnings_event_slice.json"
)


class OptionsEventVolProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original = get_institutional_ledger()
        configure_institutional_ledger(bootstrap_default_providers(as_of_time_ns=_CUTOFF))

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original)

    def test_nvda_chain_payload_includes_event_vol_snapshot(self) -> None:
        payload = build_workspace_options_payload(
            "NVDA",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        self.assertFalse(payload["available"])
        self.assertTrue(payload["chain_available"])
        self.assertIn("event_vol_snapshot", payload)
        event_vol = payload["event_vol_snapshot"]
        self.assertIsInstance(event_vol, dict)
        self.assertTrue(event_vol.get("available"))
        self.assertEqual(event_vol.get("event_type"), "earnings")
        self.assertIn(event_vol.get("event_state"), {"EVENT_APPROACHING", "NO_EVENT"})

    def test_biya_workspace_event_vol_unavailable(self) -> None:
        payload = build_workspace_options_payload(
            "BIYA",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        self.assertTrue(payload["available"])
        event_vol = payload["event_vol_snapshot"]
        self.assertFalse(event_vol.get("available"))
        self.assertEqual(event_vol.get("status"), "UNAVAILABLE")

    def test_earnings_fixture_pit_discipline(self) -> None:
        fixture = json.loads(_EARNINGS_FIXTURE.read_text(encoding="utf-8"))
        pre_scenario = fixture["scenarios"]["pre_event_imminent"]["as_of_time"]
        pre_ns = iso_to_epoch_ns(pre_scenario)
        self.assertLessEqual(pre_ns, iso_to_epoch_ns(fixture["earnings_event_time"]))
        loaded = load_earnings_event_fixture("NVDA")
        self.assertIsNotNone(loaded)


if __name__ == "__main__":
    unittest.main()
