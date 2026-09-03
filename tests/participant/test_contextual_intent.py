"""Tests for PI8 contextual intent."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.participant import (  # noqa: E402
    InsiderDiscretion,
    ParticipantActionType,
)
from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.market_context.catalyst import CatalystSummary  # noqa: E402
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.participant.contextual_intent import (  # noqa: E402
    build_contextual_intent_evidence,
    publish_contextual_intent_signals,
)

CUTOFF = iso_to_epoch_ns("2026-07-16T23:59:59Z")


def _sample_catalyst() -> CatalystSummary:
    return CatalystSummary(
        event_id="catalyst-test-001",
        canonical_event_type="earnings_beat",
        entity_ids=("BIYA",),
        headline="earnings beat",
        lean="BULLISH",
        catalyst_strength=0.8,
        novelty_score=0.7,
        materiality_score=0.6,
        credibility_score=0.9,
        surprise_score=0.5,
        gate_ok=True,
        event_time="2026-07-15T14:30:00.000000000Z",
        available_time="2026-07-15T14:45:00.000000000Z",
        publication_state="PUBLISHED",
        quality_flags=(),
        catalyst_available=True,
    )


class TestPI8ContextualIntent(unittest.TestCase):
    def test_pre_catalyst_discretionary_buy_publishes_alignment(self) -> None:
        action = {
            "action_id": "action-001",
            "participant_id": "participant:insider:ceo",
            "form_type": "4",
            "action_type": ParticipantActionType.OPEN_MARKET_BUY.value,
            "insider_discretion": InsiderDiscretion.DISCRETIONARY.value,
            "action_time": "2026-07-10T10:00:00.000000000Z",
            "available_time": "2026-07-12T10:00:00.000000000Z",
        }
        _, summaries = build_contextual_intent_evidence(
            [action],
            [_sample_catalyst()],
            prediction_cutoff=CUTOFF,
        )
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].timing_relation, "PRE_CATALYST")
        self.assertEqual(summaries[0].intent_classification, "INFORMED_TIMING_CANDIDATE")
        signals = publish_contextual_intent_signals(summaries, prediction_cutoff=CUTOFF)
        self.assertEqual(signals[0]["signal"], EvidenceSignal.PARTICIPANT_ALIGNMENT_CANDIDATE.value)

    def test_unrelated_when_outside_window(self) -> None:
        action = {
            "action_id": "action-002",
            "participant_id": "participant:insider:ceo",
            "form_type": "4",
            "action_type": ParticipantActionType.OPEN_MARKET_BUY.value,
            "insider_discretion": InsiderDiscretion.DISCRETIONARY.value,
            "action_time": "2026-06-01T10:00:00.000000000Z",
            "available_time": "2026-06-03T10:00:00.000000000Z",
        }
        _, summaries = build_contextual_intent_evidence(
            [action],
            [_sample_catalyst()],
            prediction_cutoff=CUTOFF,
        )
        self.assertEqual(summaries[0].timing_relation, "UNRELATED")
        self.assertEqual(publish_contextual_intent_signals(summaries, prediction_cutoff=CUTOFF), [])

    def test_pit_excludes_future_actions(self) -> None:
        action = {
            "action_id": "action-003",
            "participant_id": "participant:insider:ceo",
            "form_type": "4",
            "action_type": ParticipantActionType.OPEN_MARKET_BUY.value,
            "insider_discretion": InsiderDiscretion.DISCRETIONARY.value,
            "action_time": "2026-07-20T10:00:00.000000000Z",
            "available_time": "2026-07-20T10:00:00.000000000Z",
        }
        _, summaries = build_contextual_intent_evidence(
            [action],
            [_sample_catalyst()],
            prediction_cutoff=CUTOFF,
        )
        self.assertEqual(summaries[0].timing_relation, "UNRELATED")


if __name__ == "__main__":
    unittest.main()
