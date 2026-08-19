"""End-to-end participant cross-lane publish tests (PI3)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.evidence import EvidenceSignal, LaneId  # noqa: E402
from market_platform_foundation.donor_bridge.participant_adapter import (  # noqa: E402
    build_participant_cross_lane_bundle,
)
from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.adapters.edgar_disclosure import DEFAULT_FIXTURE  # noqa: E402
from market_platform_foundation.providers.whale_ledger import build_ledger_from_edgar_fixture  # noqa: E402


class ParticipantCrossLaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        self.cutoff = iso_to_epoch_ns("2026-07-16T23:59:59Z")
        configure_institutional_ledger(
            build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE, as_of_time_ns=self.cutoff)
        )

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def test_cross_lane_bundle_publishes_participant_lane(self) -> None:
        snapshot, evidence = build_participant_cross_lane_bundle(
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
        )
        self.assertTrue(snapshot.get("participant_available"))
        self.assertGreater(snapshot.get("participant_action_count", 0), 0)
        lanes = {row.get("lane") for row in evidence}
        self.assertIn(LaneId.PARTICIPANT_INTELLIGENCE.value, lanes)
        signals = {row.get("signal") for row in evidence}
        self.assertIn(EvidenceSignal.INSIDER_DISCRETIONARY_PURCHASE.value, signals)
        self.assertIn(EvidenceSignal.ACTIVIST_STAKE_DISCLOSED.value, signals)
        self.assertIn(EvidenceSignal.PARTICIPANT_DATA_CONFIDENCE.value, signals)

    def test_cross_lane_bundle_unavailable_without_ledger(self) -> None:
        configure_institutional_ledger(None)
        snapshot, evidence = build_participant_cross_lane_bundle(
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
        )
        self.assertEqual(snapshot, {})
        self.assertEqual(evidence, [])


if __name__ == "__main__":
    unittest.main()
