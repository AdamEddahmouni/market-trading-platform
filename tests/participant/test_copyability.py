"""Tests for PI9 copyability / entry quality."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.participant import (  # noqa: E402
    CopyabilityClass,
    IdentityConfidence,
    InsiderDiscretion,
    ParticipantActionType,
    ParticipantMechanism,
    ParticipantQualityFlag,
    ParticipantType,
)
from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.donor_bridge.participant_adapter import (  # noqa: E402
    build_participant_cross_lane_bundle,
)
from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.participant.bridge import query_participant_actions_from_ledger  # noqa: E402
from market_platform_foundation.participant.copyability import (  # noqa: E402
    build_copyability_evidence,
    build_participant_copyability_bundle,
    infer_mechanism_from_action,
    mechanism_is_copyable,
    publish_copyability_signals,
    score_copyability_action,
    whale_aligned_copyability_gate,
)
from market_platform_foundation.participant.skill import load_price_outcome_fixture  # noqa: E402
from market_platform_foundation.providers.whale_ledger import build_ledger_from_edgar_fixture  # noqa: E402
from market_platform_foundation.strategy.abstention import (  # noqa: E402
    ABSTAIN_COPYABILITY_UNAVAILABLE,
    evaluate_abstention,
)

SKILL_HISTORY_FIXTURE = (
    ROOT / "tests" / "fixtures" / "providers" / "edgar" / "biya_participant_skill_history.json"
)
PRICE_FIXTURE = ROOT / "tests" / "fixtures" / "participant" / "biya_price_outcomes.json"
COPYABILITY_SLICE = ROOT / "tests" / "fixtures" / "participant" / "biya_copyability_slice.json"
GOLDEN_FIXTURE = ROOT / "tests" / "fixtures" / "participant" / "biya_copyability_expected.json"


class CopyabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        self.cutoff = iso_to_epoch_ns("2026-06-15T23:59:59Z")
        configure_institutional_ledger(
            build_ledger_from_edgar_fixture(
                fixture_path=SKILL_HISTORY_FIXTURE,
                as_of_time_ns=self.cutoff,
            )
        )
        price_fixture = load_price_outcome_fixture(PRICE_FIXTURE)
        self.daily_closes = {
            str(k): float(v) for k, v in price_fixture["daily_closes"].items()
        }
        with GOLDEN_FIXTURE.open(encoding="utf-8") as handle:
            self.golden = json.load(handle)

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def _actions(self) -> list[dict]:
        ledger = get_institutional_ledger()
        assert ledger is not None
        return query_participant_actions_from_ledger(
            ledger.events,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
        )

    def test_form4_discretionary_buy_copyable(self) -> None:
        actions = self._actions()
        bundle = build_participant_copyability_bundle(
            actions,
            prediction_cutoff=self.cutoff,
            price_fixture_path=PRICE_FIXTURE,
            copyability_fixture_path=COPYABILITY_SLICE,
        )
        jane_expected = self.golden["participants"]["Jane Officer"]
        jane_rows = [
            row
            for row in bundle["summaries"]
            if row["display_name"] == "Jane Officer"
            and row["copyability_class"] == CopyabilityClass.COPYABLE.value
        ]
        self.assertTrue(jane_rows)
        jane = jane_rows[0]
        self.assertAlmostEqual(
            jane["follower_return_at_available"],
            jane_expected["follower_return_at_available"],
            places=4,
        )
        self.assertAlmostEqual(
            jane["copyability_score"],
            jane_expected["copyability_score"],
            places=4,
        )
        self.assertEqual(jane["cross_lane_signal"], EvidenceSignal.PARTICIPANT_COPYABILITY_HIGH.value)

    def test_13f_not_copyable(self) -> None:
        action = {
            "action_id": "13f-test-001",
            "participant_id": "participant:hedge:test",
            "display_name": "Test Fund",
            "instrument_id": "BIYA",
            "form_type": "13F-HR",
            "action_type": ParticipantActionType.INSTITUTIONAL_HOLDING_SNAPSHOT.value,
            "action_time": "2025-10-01T00:00:00.000000000Z",
            "event_time": "2025-10-01T00:00:00.000000000Z",
            "available_time": "2025-11-15T14:00:00.000000000Z",
            "identity_confidence": IdentityConfidence.KNOWN_IDENTITY.value,
            "quality_flags": [
                ParticipantQualityFlag.QUARTER_END_NOT_COPYABLE.value,
                ParticipantQualityFlag.POSITION_STALE.value,
            ],
        }
        item = score_copyability_action(
            action,
            daily_closes=self.daily_closes,
            prediction_cutoff=self.cutoff,
        )
        assert item is not None
        self.assertEqual(item.copyability_class, CopyabilityClass.NOT_COPYABLE)
        self.assertEqual(item.cross_lane_signal, EvidenceSignal.PARTICIPANT_COPYABILITY_LOW.value)

    def test_pit_excludes_future_actions(self) -> None:
        action = {
            "action_id": "future-action",
            "participant_id": "participant:insider:ceo",
            "display_name": "Future Insider",
            "instrument_id": "BIYA",
            "form_type": "4",
            "action_type": ParticipantActionType.OPEN_MARKET_BUY.value,
            "insider_discretion": InsiderDiscretion.DISCRETIONARY.value,
            "action_time": "2026-07-20T10:00:00.000000000Z",
            "event_time": "2026-07-20T10:00:00.000000000Z",
            "available_time": "2026-07-20T10:00:00.000000000Z",
            "identity_confidence": IdentityConfidence.KNOWN_IDENTITY.value,
            "quality_flags": [],
        }
        item = score_copyability_action(
            action,
            daily_closes=self.daily_closes,
            prediction_cutoff=self.cutoff,
        )
        self.assertIsNone(item)

    def test_mechanism_unknown_no_copyable_signal(self) -> None:
        action = {
            "action_id": "unknown-mechanism",
            "participant_id": "participant:unknown",
            "display_name": "Unknown Actor",
            "instrument_id": "BIYA",
            "form_type": "4",
            "action_type": ParticipantActionType.INSIDER_AWARD_GRANT.value,
            "action_time": "2025-10-14T00:00:00.000000000Z",
            "event_time": "2025-10-14T00:00:00.000000000Z",
            "available_time": "2025-10-15T14:00:00.000000000Z",
            "identity_confidence": IdentityConfidence.KNOWN_IDENTITY.value,
            "quality_flags": [],
        }
        item = score_copyability_action(
            action,
            daily_closes=self.daily_closes,
            prediction_cutoff=self.cutoff,
        )
        self.assertIsNone(item)
        mechanism = infer_mechanism_from_action(action)
        self.assertEqual(mechanism, ParticipantMechanism.UNKNOWN)
        self.assertFalse(mechanism_is_copyable(mechanism))

    def test_golden_summary(self) -> None:
        actions = self._actions()
        bundle = build_participant_copyability_bundle(
            actions,
            prediction_cutoff=self.cutoff,
            price_fixture_path=PRICE_FIXTURE,
            copyability_fixture_path=COPYABILITY_SLICE,
        )
        summary = bundle["summary"]
        expected = self.golden["summary"]
        self.assertEqual(summary["action_count"], expected["action_count"])
        self.assertEqual(summary["copyable_count"], expected["copyable_count"])
        self.assertEqual(summary["stale_count"], expected["stale_count"])
        self.assertTrue(summary["whale_aligned_copyability_gate"])

    def test_publish_signals_respects_mechanism_gate(self) -> None:
        _, summaries = build_copyability_evidence(
            self._actions(),
            prediction_cutoff=self.cutoff,
            price_fixture_path=PRICE_FIXTURE,
            copyability_fixture_path=COPYABILITY_SLICE,
        )
        signals = publish_copyability_signals(summaries, prediction_cutoff=self.cutoff)
        signal_names = {row["signal"] for row in signals}
        self.assertIn(EvidenceSignal.PARTICIPANT_COPYABILITY_HIGH.value, signal_names)

        unknown_action = {
            "action_id": "ambiguous",
            "participant_id": "participant:unknown",
            "display_name": "Ambiguous",
            "instrument_id": "BIYA",
            "form_type": "4",
            "action_type": ParticipantActionType.OPEN_MARKET_BUY.value,
            "action_time": "2025-10-14T00:00:00.000000000Z",
            "event_time": "2025-10-14T00:00:00.000000000Z",
            "available_time": "2025-10-15T14:00:00.000000000Z",
            "identity_confidence": IdentityConfidence.UNKNOWN.value,
            "quality_flags": [],
        }
        item = score_copyability_action(
            unknown_action,
            daily_closes=self.daily_closes,
            prediction_cutoff=self.cutoff,
        )
        assert item is not None
        from market_platform_foundation.participant.copyability import CopyabilitySummary

        ambiguous_summary = CopyabilitySummary(
            action_id=item.action_id,
            participant_id=item.participant_id,
            display_name="Ambiguous",
            instrument_id=item.instrument_id,
            mechanism=item.mechanism.value,
            copyability_class=item.copyability_class.value,
            participant_gross_return=item.participant_gross_return,
            follower_return_at_available=item.follower_return_at_available,
            cost_adjusted_follower_return=item.cost_adjusted_follower_return,
            copyability_score=item.copyability_score,
            event_time=item.event_time,
            available_time=item.available_time,
            quality_flags=item.quality_flags,
            cross_lane_signal=item.cross_lane_signal,
        )
        ambiguous_signals = publish_copyability_signals(
            [ambiguous_summary],
            prediction_cutoff=self.cutoff,
        )
        self.assertEqual(ambiguous_signals, [])

    def test_whale_aligned_abstains_without_copyability(self) -> None:
        should_abstain, reasons = evaluate_abstention(
            prereg_status="PASS",
            forecast_status="PASS",
            alignment_type="WHALE_ALIGNED",
            institutional_rows=[{"status": "available"}],
            prediction_cutoff=self.cutoff,
            observation_time=self.cutoff,
            copyability_gate_ok=False,
        )
        self.assertTrue(should_abstain)
        self.assertIn(ABSTAIN_COPYABILITY_UNAVAILABLE, reasons)

    def test_cross_lane_bundle_includes_copyability(self) -> None:
        snapshot, evidence = build_participant_cross_lane_bundle(
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            price_fixture_path=PRICE_FIXTURE,
        )
        self.assertTrue(snapshot.get("participant_copyability_available"))
        signals = {row.get("signal") for row in evidence}
        self.assertIn(EvidenceSignal.PARTICIPANT_COPYABILITY_HIGH.value, signals)


if __name__ == "__main__":
    unittest.main()
