"""Tests for options execution workspace projection (O9 wiring)."""

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
from market_platform_foundation.options.execution import load_execution_fixture  # noqa: E402
from market_platform_foundation.providers.projections import build_workspace_options_payload  # noqa: E402
from market_platform_foundation.providers.whale_ledger import bootstrap_default_providers  # noqa: E402

_CUTOFF = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
_EXECUTION_FIXTURE = (
    ROOT / "tests" / "fixtures" / "providers" / "options" / "nvda_options_execution_slice.json"
)


class OptionsExecutionProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original = get_institutional_ledger()
        configure_institutional_ledger(bootstrap_default_providers(as_of_time_ns=_CUTOFF))

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original)

    def test_nvda_chain_payload_includes_execution_snapshot(self) -> None:
        payload = build_workspace_options_payload(
            "NVDA",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        self.assertFalse(payload["available"])
        self.assertTrue(payload["chain_available"])
        self.assertIn("execution_snapshot", payload)
        execution = payload["execution_snapshot"]
        self.assertIsInstance(execution, dict)
        self.assertIn("status", execution)
        self.assertIn("method", execution)

    def test_biya_workspace_execution_when_activities_available(self) -> None:
        payload = build_workspace_options_payload(
            "BIYA",
            as_of_context={},
            prediction_cutoff=_CUTOFF,
        )
        self.assertTrue(payload["available"])
        self.assertIn("execution_snapshot", payload)
        execution = payload["execution_snapshot"]
        self.assertIsInstance(execution, dict)

    def test_execution_fixture_pit_discipline(self) -> None:
        fixture = json.loads(_EXECUTION_FIXTURE.read_text(encoding="utf-8"))
        as_of_ns = iso_to_epoch_ns(fixture["as_of_time"])
        self.assertLessEqual(as_of_ns, _CUTOFF)
        loaded = load_execution_fixture("NVDA")
        self.assertIsNotNone(loaded)


if __name__ == "__main__":
    unittest.main()
