"""Tests for PI13 forced-flow / dislocation engine."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.contracts.participant import (  # noqa: E402
    ForcedFlowRegime,
    IdentityConfidence,
    ParticipantMechanism,
    ParticipantResearchClassification,
    ParticipantType,
    forced_flow_evidence_to_dict,
)
from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.participant.evidence import publish_forced_flow_signals  # noqa: E402
from market_platform_foundation.participant.forced_flow import (  # noqa: E402
    ANONYMOUS_FORCED_FLOW_PARTICIPANT_ID,
    build_forced_flow_bundle,
    interpret_forced_flow,
    load_forced_flow_slice,
)

FORCED_FLOW_SLICE = ROOT / "tests" / "fixtures" / "participant" / "nvda_forced_flow_slice.json"
FORCED_FLOW_EXPECTED = ROOT / "tests" / "fixtures" / "participant" / "nvda_forced_flow_expected.json"
CATALYST_PRESENT_SLICE = (
    ROOT / "tests" / "fixtures" / "participant" / "nvda_forced_flow_catalyst_present_slice.json"
)
AMBIGUOUS_SLICE = ROOT / "tests" / "fixtures" / "participant" / "nvda_forced_flow_ambiguous_slice.json"


class TestPI13ForcedFlow(unittest.TestCase):
    def test_forced_flow_golden_regression(self) -> None:
        expected = json.loads(FORCED_FLOW_EXPECTED.read_text(encoding="utf-8"))
        cutoff = iso_to_epoch_ns(expected["prediction_cutoff"])
        bundle = build_forced_flow_bundle(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            forced_flow_fixture_path=FORCED_FLOW_SLICE,
        )
        self.assertEqual(bundle["summary"], expected["summary"])
        evidence = bundle["evidence"]
        self.assertEqual(len(evidence), 1)
        item = evidence[0]
        self.assertEqual(item.flow_regime, ForcedFlowRegime.FORCED_FLOW_LIKELY)
        self.assertEqual(
            item.cross_lane_signal,
            EvidenceSignal.FORCED_FLOW_PROBABILITY_ELEVATED.value,
        )

    def test_anonymous_identity_no_invention(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        bundle = build_forced_flow_bundle(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            forced_flow_fixture_path=FORCED_FLOW_SLICE,
        )
        for item in bundle["evidence"]:
            self.assertEqual(item.participant_id, ANONYMOUS_FORCED_FLOW_PARTICIPANT_ID)
            self.assertEqual(item.participant_type, ParticipantType.UNKNOWN_LARGE_PARTICIPANT)
            self.assertEqual(
                item.identity_confidence,
                IdentityConfidence.ANONYMOUS_INSTITUTIONAL_SCALE,
            )

    def test_catalyst_present_fail_closed(self) -> None:
        fixture = load_forced_flow_slice(CATALYST_PRESENT_SLICE)
        cutoff = iso_to_epoch_ns(fixture["prediction_cutoff"])
        evidence = interpret_forced_flow(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            lane_inputs=fixture["lane_inputs"],
        )
        self.assertEqual(len(evidence), 1)
        item = evidence[0]
        self.assertEqual(item.flow_regime, ForcedFlowRegime.INSUFFICIENT_DATA)
        self.assertIsNone(item.cross_lane_signal)
        self.assertTrue(item.active_catalyst_at_cutoff)

    def test_missing_catalyst_registry_fail_closed(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        evidence = interpret_forced_flow(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            lane_inputs={
                "metaorder": {
                    "lifecycle_state": "LIKELY_COMPLETE",
                    "event_time": "2026-07-21T20:30:06.000000000Z",
                    "available_time": "2026-07-21T20:30:06.000000000Z",
                }
            },
        )
        self.assertEqual(len(evidence), 1)
        item = evidence[0]
        self.assertEqual(item.flow_regime, ForcedFlowRegime.INSUFFICIENT_DATA)
        self.assertIn("CATALYST_CONTEXT_MISSING", item.quality_flags)

    def test_ambiguous_partial_inputs(self) -> None:
        fixture = load_forced_flow_slice(AMBIGUOUS_SLICE)
        cutoff = iso_to_epoch_ns(fixture["prediction_cutoff"])
        evidence = interpret_forced_flow(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            lane_inputs=fixture["lane_inputs"],
        )
        self.assertEqual(len(evidence), 1)
        item = evidence[0]
        self.assertEqual(item.flow_regime, ForcedFlowRegime.DISLOCATION_AMBIGUOUS)
        self.assertIsNone(item.cross_lane_signal)
        self.assertIn("FORCED_FLOW_UNCONFIRMED", item.quality_flags)

    def test_pit_excludes_future_lane_inputs(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:29:59.000000000Z")
        fixture = load_forced_flow_slice(FORCED_FLOW_SLICE)
        evidence = interpret_forced_flow(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            lane_inputs=fixture["lane_inputs"],
        )
        self.assertEqual(evidence, [])

    def test_cross_lane_publish_forced_flow_signal(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        bundle = build_forced_flow_bundle(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            forced_flow_fixture_path=FORCED_FLOW_SLICE,
        )
        published = publish_forced_flow_signals(
            bundle["evidence"],
            prediction_cutoff=cutoff,
        )
        self.assertEqual(len(published), 1)
        self.assertEqual(
            published[0]["signal"],
            EvidenceSignal.FORCED_FLOW_PROBABILITY_ELEVATED.value,
        )

    def test_contract_serialization(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        bundle = build_forced_flow_bundle(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            forced_flow_fixture_path=FORCED_FLOW_SLICE,
        )
        payload = forced_flow_evidence_to_dict(bundle["evidence"][0])
        self.assertEqual(payload["payload_type"], "ForcedFlowEvidence")
        self.assertIn("schema_version", payload)

    def test_research_classification_contrarian_on_likely(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        bundle = build_forced_flow_bundle(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            forced_flow_fixture_path=FORCED_FLOW_SLICE,
        )
        item = bundle["evidence"][0]
        self.assertEqual(
            item.research_classification,
            ParticipantResearchClassification.POST_FLOW_CONTRARIAN_CANDIDATE,
        )
        self.assertEqual(item.mechanism, ParticipantMechanism.FORCED_LIQUIDATION)

    def test_no_duplicate_of_signals_in_module(self) -> None:
        source = (
            ROOT / "src" / "market_platform_foundation" / "participant" / "forced_flow.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("EXHAUSTION_BUY", source)
        self.assertNotIn("FUTURES_LONG_LIQUIDATION_RISK", source)


if __name__ == "__main__":
    unittest.main()
