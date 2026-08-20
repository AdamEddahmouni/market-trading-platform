"""Tests for PI12 large derivatives participant research."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.contracts.participant import (  # noqa: E402
    DerivativeFlowRegime,
    IdentityConfidence,
    ParticipantMechanism,
    ParticipantType,
    derivative_participant_evidence_to_dict,
)
from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.donor_bridge.participant_adapter import (  # noqa: E402
    build_derivatives_participant_bundle,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.participant.derivatives import (  # noqa: E402
    ANONYMOUS_OPTIONS_PARTICIPANT_ID,
    interpret_derivatives_flow,
)
from market_platform_foundation.participant.evidence import publish_derivatives_signals  # noqa: E402

DERIVATIVES_SLICE = ROOT / "tests" / "fixtures" / "participant" / "nvda_derivatives_participant_slice.json"
DERIVATIVES_EXPECTED = ROOT / "tests" / "fixtures" / "participant" / "nvda_derivatives_participant_expected.json"
SIGNED_FLOW_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "options" / "nvda_signed_flow_slice.json"
BIYA_OPTIONS_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "options" / "biya_options_slice.json"


class TestPI12DerivativesParticipant(unittest.TestCase):
    def test_confirmed_signed_flow_golden_regression(self) -> None:
        expected = json.loads(DERIVATIVES_EXPECTED.read_text(encoding="utf-8"))
        cutoff = iso_to_epoch_ns(expected["prediction_cutoff"])
        bundle = build_derivatives_participant_bundle(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            derivatives_fixture_path=DERIVATIVES_SLICE,
        )
        self.assertEqual(bundle["summary"], expected["summary"])
        evidence = bundle["evidence"]
        self.assertEqual(len(evidence), 1)
        item = evidence[0]
        self.assertEqual(item.flow_regime, DerivativeFlowRegime.CONFIRMED_DIRECTIONAL)
        self.assertEqual(item.dominant_signed_direction, "buy_initiated")
        self.assertEqual(
            item.cross_lane_signal,
            EvidenceSignal.LARGE_DERIVATIVE_FLOW_CONFIRMED.value,
        )

    def test_anonymous_identity_no_invention(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        bundle = build_derivatives_participant_bundle(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            derivatives_fixture_path=DERIVATIVES_SLICE,
        )
        for item in bundle["evidence"]:
            self.assertEqual(item.participant_id, ANONYMOUS_OPTIONS_PARTICIPANT_ID)
            self.assertEqual(item.participant_type, ParticipantType.UNKNOWN_LARGE_PARTICIPANT)
            self.assertEqual(
                item.identity_confidence,
                IdentityConfidence.ANONYMOUS_INSTITUTIONAL_SCALE,
            )
            self.assertNotIn("CEO", item.participant_id)
            self.assertNotIn("Whale", item.participant_id)

    def test_biya_unsigned_flow_fail_closed(self) -> None:
        payload = json.loads(BIYA_OPTIONS_FIXTURE.read_text(encoding="utf-8"))
        activities = payload.get("activities", [])
        cutoff = iso_to_epoch_ns("2026-08-15T23:59:59Z")
        evidence = interpret_derivatives_flow(
            activities,
            instrument_id="BIYA",
            prediction_cutoff=cutoff,
            scale_config={"min_confirmed_trade_count": 1, "min_buy_initiated_volume": 1},
        )
        self.assertEqual(len(evidence), 1)
        item = evidence[0]
        self.assertEqual(item.flow_regime, DerivativeFlowRegime.SCALE_ELEVATED_AMBIGUOUS)
        self.assertIsNone(item.dominant_signed_direction)
        self.assertEqual(
            item.cross_lane_signal,
            EvidenceSignal.LARGE_DERIVATIVE_FLOW_AMBIGUOUS.value,
        )

    def test_pit_excludes_future_activities(self) -> None:
        payload = json.loads(SIGNED_FLOW_FIXTURE.read_text(encoding="utf-8"))
        activities = payload.get("activities", [])
        early_cutoff = iso_to_epoch_ns("2026-07-21T19:44:59.000000000Z")
        evidence = interpret_derivatives_flow(
            activities,
            instrument_id="NVDA",
            prediction_cutoff=early_cutoff,
            scale_config={"min_confirmed_trade_count": 1, "min_buy_initiated_volume": 1},
        )
        self.assertEqual(evidence, [])

    def test_cross_lane_publish_confirmed_signal(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        bundle = build_derivatives_participant_bundle(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            derivatives_fixture_path=DERIVATIVES_SLICE,
        )
        published = publish_derivatives_signals(
            bundle["evidence"],
            prediction_cutoff=cutoff,
        )
        self.assertEqual(len(published), 1)
        self.assertEqual(
            published[0]["signal"],
            EvidenceSignal.LARGE_DERIVATIVE_FLOW_CONFIRMED.value,
        )

    def test_contract_serialization(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        bundle = build_derivatives_participant_bundle(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            derivatives_fixture_path=DERIVATIVES_SLICE,
        )
        payload = derivative_participant_evidence_to_dict(bundle["evidence"][0])
        self.assertEqual(payload["payload_type"], "DerivativeParticipantEvidence")
        self.assertEqual(payload["action_type"], "DERIVATIVE_POSITION")
        self.assertIn("schema_version", payload)

    def test_conservative_mechanism_not_informed_directional(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-21T20:30:10.000000000Z")
        bundle = build_derivatives_participant_bundle(
            instrument_id="NVDA",
            prediction_cutoff=cutoff,
            derivatives_fixture_path=DERIVATIVES_SLICE,
        )
        item = bundle["evidence"][0]
        self.assertNotEqual(item.mechanism, ParticipantMechanism.INFORMED_DIRECTIONAL)
        self.assertEqual(item.mechanism, ParticipantMechanism.FLOW_DRIVEN)

    def test_no_direction_label_inference_in_module(self) -> None:
        source = (ROOT / "src" / "market_platform_foundation" / "participant" / "derivatives.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("direction_label", source)


if __name__ == "__main__":
    unittest.main()
