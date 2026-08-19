"""Tests for Participant Intelligence contracts (PI1–PI2 foundation)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.participant import (  # noqa: E402
    ActionDirection,
    IdentityConfidence,
    InsiderDiscretion,
    ParticipantActionType,
    ParticipantQualityFlag,
    ParticipantType,
    disclosure_quality_flags,
    infer_action_from_form4_transaction,
    infer_participant_type_from_form,
    mechanism_inference_unavailable,
    participant_id_from_source,
)
from market_platform_foundation.participant.bridge import (  # noqa: E402
    disclosure_envelope_to_participant_action,
    disclosure_envelope_to_participant_identity,
    query_participant_actions_from_ledger,
)


class ParticipantContractTests(unittest.TestCase):
    def test_form4_open_market_purchase_semantics(self) -> None:
        action_type, direction, clarity = infer_action_from_form4_transaction("P")
        self.assertEqual(action_type, ParticipantActionType.OPEN_MARKET_BUY)
        self.assertEqual(direction, ActionDirection.BUY)
        self.assertEqual(clarity.value, "CLEAR")

    def test_form4_compensation_not_directional(self) -> None:
        action_type, direction, clarity = infer_action_from_form4_transaction("I")
        self.assertEqual(action_type, ParticipantActionType.INSIDER_AWARD_GRANT)
        self.assertEqual(direction, ActionDirection.AMBIGUOUS)
        self.assertIn(ParticipantQualityFlag.ACTION_AMBIGUOUS.value, disclosure_quality_flags(
            form_type="4",
            transaction_code="I",
            available_time="2026-07-11T00:00:00Z",
            action_time="2026-07-10T00:00:00Z",
        ))

    def test_13f_fails_closed_on_copyability(self) -> None:
        flags = disclosure_quality_flags(
            form_type="13F-HR",
            transaction_code=None,
            available_time="2026-08-15T00:00:00Z",
            action_time="2026-06-30T00:00:00Z",
        )
        self.assertIn(ParticipantQualityFlag.QUARTER_END_NOT_COPYABLE.value, flags)
        self.assertIn(ParticipantQualityFlag.ENTRY_BASIS_UNKNOWN.value, flags)

    def test_participant_id_deterministic(self) -> None:
        first = participant_id_from_source(
            source="regulatory_disclosure",
            source_record_id="acc-1",
            participant_label="Jane Officer",
        )
        second = participant_id_from_source(
            source="regulatory_disclosure",
            source_record_id="acc-1",
            participant_label="Jane Officer",
        )
        self.assertEqual(first, second)

    def test_13d_maps_to_activist_type(self) -> None:
        self.assertEqual(
            infer_participant_type_from_form("13D"),
            ParticipantType.ACTIVIST,
        )

    def test_mechanism_unknown_fails_closed(self) -> None:
        inference, flags = mechanism_inference_unavailable()
        self.assertIsNone(inference)
        self.assertIn(ParticipantQualityFlag.INTENT_UNKNOWN.value, flags)

    def test_disclosure_bridge_preserves_available_time(self) -> None:
        envelope = {
            "instrument_id": "BIYA",
            "event_time": "2026-07-10T16:30:00Z",
            "available_time": 1720626600,
            "provider_id": "fixture_edgar",
            "source_record_id": "0001849639-26-000010",
            "source_revision_id": "1",
            "disclosure_event": {
                "accession_number": "0001849639-26-000010",
                "accepted_at": "2026-07-10T16:30:00Z",
                "filer": "Jane Officer",
                "form_type": "4",
                "event_type": "insider_buy",
                "transaction_code": "P",
                "source_url": "https://example.com/form4",
            },
        }
        action = disclosure_envelope_to_participant_action(envelope, instrument_id="BIYA")
        assert action is not None
        self.assertEqual(action.action_type, ParticipantActionType.OPEN_MARKET_BUY)
        self.assertEqual(action.insider_discretion, InsiderDiscretion.DISCRETIONARY)
        self.assertEqual(action.identity_confidence, IdentityConfidence.KNOWN_IDENTITY)
        self.assertEqual(str(action.available_time), "1720626600")

    def test_query_participant_actions_respects_prediction_cutoff(self) -> None:
        envelopes = [
            {
                "instrument_id": "BIYA",
                "event_time": "2026-07-10T16:30:00Z",
                "available_time": 100,
                "provider_id": "fixture_edgar",
                "source_record_id": "past",
                "source_revision_id": "1",
                "disclosure_event": {
                    "accession_number": "past",
                    "accepted_at": "2026-07-10T16:30:00Z",
                    "filer": "Jane Officer",
                    "form_type": "4",
                    "event_type": "insider_buy",
                    "transaction_code": "P",
                },
            },
            {
                "instrument_id": "BIYA",
                "event_time": "2026-07-20T12:00:00Z",
                "available_time": 200,
                "provider_id": "fixture_edgar",
                "source_record_id": "future",
                "source_revision_id": "1",
                "disclosure_event": {
                    "accession_number": "future",
                    "accepted_at": "2026-07-20T12:00:00Z",
                    "filer": "Future Insider",
                    "form_type": "4",
                    "event_type": "insider_buy",
                    "transaction_code": "P",
                },
            },
        ]
        visible = query_participant_actions_from_ledger(
            envelopes,
            instrument_id="BIYA",
            prediction_cutoff=150,
        )
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]["source_record_id"], "past")

    def test_identity_from_named_filer(self) -> None:
        identity = disclosure_envelope_to_participant_identity(
            {
                "filer": "Alpha Fund LP",
                "form_type": "13F-HR",
                "accession_number": "acc-13f",
                "accepted_at": "2026-07-01T12:00:00Z",
            }
        )
        self.assertEqual(identity.participant_type, ParticipantType.HEDGE_FUND)
        self.assertEqual(identity.identity_confidence, IdentityConfidence.KNOWN_IDENTITY)


if __name__ == "__main__":
    unittest.main()
