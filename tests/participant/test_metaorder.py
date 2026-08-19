"""Tests for PI6 metaorder cooperation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.contracts.participant import (
    IdentityConfidence,
    MetaorderLifecycleState,
    ParticipantMechanism,
    ParticipantType,
)
from market_platform_foundation.cross_lane.evidence import EvidenceSignal
from market_platform_foundation.donor_bridge.participant_adapter import build_metaorder_bundle
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns
from market_platform_foundation.order_flow.metaorder import classified_trades_from_bars, detect_metaorder_primitives
from market_platform_foundation.participant.evidence import publish_metaorder_signals
from market_platform_foundation.participant.metaorder import interpret_metaorder_primitives

METAORDER_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "order_flow" / "nvda_metaorder_slice.json"


class TestPI6Metaorder(unittest.TestCase):
    def test_lifecycle_interpretation(self) -> None:
        payload = json.loads(METAORDER_FIXTURE.read_text(encoding="utf-8"))
        trades = classified_trades_from_bars(payload["bars"], instrument="NVDA")
        primitives = detect_metaorder_primitives(
            trades,
            instrument="NVDA",
            min_signed_volume=500.0,
            min_trade_count=3,
            min_duration_seconds=2.0,
        )
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        evidence = interpret_metaorder_primitives(primitives, prediction_cutoff=cutoff)
        self.assertEqual(len(evidence), 1)
        item = evidence[0]
        self.assertEqual(item.lifecycle_state, MetaorderLifecycleState.PAUSED)
        self.assertEqual(item.participant_type, ParticipantType.UNKNOWN_LARGE_PARTICIPANT)
        self.assertEqual(item.identity_confidence, IdentityConfidence.ANONYMOUS_INSTITUTIONAL_SCALE)
        self.assertEqual(item.mechanism, ParticipantMechanism.MECHANICAL_FLOW)

    def test_no_identity_invention(self) -> None:
        bundle = build_metaorder_bundle(
            instrument_id="NVDA",
            prediction_cutoff=str(iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")),
            fixture_path=METAORDER_FIXTURE,
        )
        for item in bundle["evidence"]:
            self.assertNotIn("CEO", item.participant_id)
            self.assertTrue(item.participant_id.startswith("participant:"))

    def test_pit_excludes_future_primitives(self) -> None:
        payload = json.loads(METAORDER_FIXTURE.read_text(encoding="utf-8"))
        trades = classified_trades_from_bars(payload["bars"], instrument="NVDA")
        primitives = detect_metaorder_primitives(
            trades,
            instrument="NVDA",
            min_signed_volume=500.0,
            min_trade_count=3,
            min_duration_seconds=2.0,
        )
        early_cutoff = iso_to_epoch_ns("2026-07-21T20:30:02.000000000Z")
        evidence = interpret_metaorder_primitives(primitives, prediction_cutoff=early_cutoff)
        self.assertEqual(evidence, [])

    def test_cross_lane_publish_active_signal(self) -> None:
        payload = json.loads(METAORDER_FIXTURE.read_text(encoding="utf-8"))
        trades = classified_trades_from_bars(payload["bars"], instrument="NVDA")
        primitives = detect_metaorder_primitives(
            trades,
            instrument="NVDA",
            min_signed_volume=500.0,
            min_trade_count=3,
            min_duration_seconds=2.0,
        )
        # Force ACTIVE state for signal gate test
        active_primitive = primitives[0]
        from market_platform_foundation.order_flow.contracts import MetaorderPrimitive, MetaorderFlowState

        active_primitive = MetaorderPrimitive(
            primitive_id=active_primitive.primitive_id,
            instrument=active_primitive.instrument,
            venue=active_primitive.venue,
            aggressor_side=active_primitive.aggressor_side,
            signed_volume=active_primitive.signed_volume,
            trade_count=active_primitive.trade_count,
            start_time=active_primitive.start_time,
            end_time=active_primitive.end_time,
            available_time=active_primitive.available_time,
            flow_state=MetaorderFlowState.FLOW_ACTIVE,
            detection_method=active_primitive.detection_method,
            detection_version=active_primitive.detection_version,
        )
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        evidence = interpret_metaorder_primitives([active_primitive], prediction_cutoff=cutoff)
        published = publish_metaorder_signals(evidence)
        signals = {row["signal"] for row in published}
        self.assertIn(EvidenceSignal.METAORDER_LIKELY_ACTIVE.value, signals)


if __name__ == "__main__":
    unittest.main()
