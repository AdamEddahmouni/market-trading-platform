"""Tests for PI10 consensus / disagreement / crowding."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.participant import (  # noqa: E402
    ParticipantAlignmentRegime,
    ParticipantCrowdingEvidence,
    ParticipantQualityFlag,
    ParticipantStanceDirection,
    participant_crowding_evidence_to_dict,
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
from market_platform_foundation.participant.crowding import (  # noqa: E402
    build_participant_crowding_bundle,
    classify_participant_stance,
    compute_crowding_evidence,
    publish_crowding_signals,
    summarize_crowding,
)
from market_platform_foundation.providers.adapters.edgar_disclosure import DEFAULT_FIXTURE  # noqa: E402
from market_platform_foundation.providers.whale_ledger import build_ledger_from_edgar_fixture  # noqa: E402

DISCLOSURE_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "edgar" / "biya_disclosures.json"
CROWDING_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "edgar" / "biya_institutional_crowding.json"
CROWDING_SLICE = ROOT / "tests" / "fixtures" / "participant" / "biya_crowding_slice.json"
GOLDEN_FIXTURE = ROOT / "tests" / "fixtures" / "participant" / "biya_crowding_expected.json"


class CrowdingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        with GOLDEN_FIXTURE.open(encoding="utf-8") as handle:
            self.golden = json.load(handle)
        self.cutoff = iso_to_epoch_ns(self.golden["prediction_cutoff"])

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def _configure_fixture(self, fixture_path: Path, *, cutoff: int | None = None) -> list[dict]:
        cutoff_ns = cutoff if cutoff is not None else self.cutoff
        configure_institutional_ledger(
            build_ledger_from_edgar_fixture(fixture_path=fixture_path, as_of_time_ns=cutoff_ns)
        )
        ledger = get_institutional_ledger()
        assert ledger is not None
        return query_participant_actions_from_ledger(
            ledger.events,
            instrument_id="BIYA",
            prediction_cutoff=cutoff_ns,
        )

    def test_golden_disagreement_fixture(self) -> None:
        actions = self._configure_fixture(DISCLOSURE_FIXTURE)
        bundle = build_participant_crowding_bundle(
            actions,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            crowding_fixture_path=CROWDING_SLICE,
        )
        self.assertEqual(bundle["summary"], self.golden["summary"])

    def test_disagreement_regime_and_signal(self) -> None:
        actions = self._configure_fixture(DISCLOSURE_FIXTURE)
        evidence = compute_crowding_evidence(
            actions,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            crowding_fixture_path=CROWDING_SLICE,
        )
        assert evidence is not None
        self.assertEqual(evidence.alignment_regime, ParticipantAlignmentRegime.DISAGREEMENT)
        self.assertEqual(evidence.insider_direction, None)
        self.assertEqual(evidence.activist_direction, ParticipantStanceDirection.BULLISH.value)
        self.assertEqual(
            evidence.cross_lane_signal,
            EvidenceSignal.PARTICIPANT_DISAGREEMENT_ELEVATED.value,
        )
        self.assertIsNone(evidence.crowding_score)

    def test_institutional_crowding_scenario(self) -> None:
        cutoff = iso_to_epoch_ns("2026-08-14T23:59:59Z")
        actions = self._configure_fixture(CROWDING_FIXTURE, cutoff=cutoff)
        evidence = compute_crowding_evidence(
            actions,
            instrument_id="BIYA",
            prediction_cutoff=cutoff,
            crowding_fixture_path=CROWDING_SLICE,
        )
        assert evidence is not None
        self.assertEqual(evidence.alignment_regime, ParticipantAlignmentRegime.CONSENSUS)
        self.assertEqual(evidence.institutional_direction, ParticipantStanceDirection.BULLISH.value)
        self.assertEqual(evidence.crowding_score, 1.0)
        self.assertEqual(evidence.independent_participant_count, 3)
        self.assertEqual(evidence.affiliated_participant_count, 1)
        self.assertEqual(
            evidence.cross_lane_signal,
            EvidenceSignal.PARTICIPANT_CROWDING_ELEVATED.value,
        )

    def test_affiliation_dedup_reduces_independent_count(self) -> None:
        cutoff = iso_to_epoch_ns("2026-08-14T23:59:59Z")
        actions = self._configure_fixture(CROWDING_FIXTURE, cutoff=cutoff)
        evidence = compute_crowding_evidence(
            actions,
            instrument_id="BIYA",
            prediction_cutoff=cutoff,
            crowding_fixture_path=CROWDING_SLICE,
        )
        assert evidence is not None
        self.assertEqual(evidence.independent_participant_count, 3)
        self.assertEqual(evidence.affiliated_participant_count, 1)

    def test_pit_excludes_future_accession(self) -> None:
        actions = self._configure_fixture(DISCLOSURE_FIXTURE)
        future_accession = self.golden["pit_excludes_accession"]
        future_actions = [
            row for row in actions if row.get("source_record_id") == future_accession
        ]
        self.assertEqual(future_actions, [])

    def test_crowding_data_stale_propagates(self) -> None:
        actions = self._configure_fixture(DISCLOSURE_FIXTURE)
        evidence = compute_crowding_evidence(
            actions,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            crowding_fixture_path=CROWDING_SLICE,
        )
        assert evidence is not None
        self.assertIn(
            ParticipantQualityFlag.CROWDING_DATA_STALE.value,
            evidence.quality_flags,
        )

    def test_fail_closed_single_participant(self) -> None:
        action = {
            "action_id": "a1",
            "participant_id": "p1",
            "display_name": "Solo Buyer",
            "participant_type": "CORPORATE_INSIDER",
            "action_type": "OPEN_MARKET_BUY",
            "insider_discretion": "DISCRETIONARY",
            "available_time": str(self.cutoff),
            "event_time": "2026-07-10T00:00:00Z",
            "quality_flags": [],
        }
        evidence = compute_crowding_evidence(
            [action],
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            crowding_fixture_path=CROWDING_SLICE,
        )
        assert evidence is not None
        self.assertEqual(evidence.alignment_regime, ParticipantAlignmentRegime.INSUFFICIENT_DATA)
        self.assertIsNone(evidence.cross_lane_signal)
        published = publish_crowding_signals(evidence, prediction_cutoff=self.cutoff)
        self.assertEqual(published, [])

    def test_cross_lane_bundle_publishes_disagreement_signal(self) -> None:
        configure_institutional_ledger(
            build_ledger_from_edgar_fixture(fixture_path=DEFAULT_FIXTURE, as_of_time_ns=self.cutoff)
        )
        snapshot, evidence = build_participant_cross_lane_bundle(
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            crowding_fixture_path=CROWDING_SLICE,
        )
        self.assertTrue(snapshot.get("participant_crowding_available"))
        signals = {row.get("signal") for row in evidence}
        self.assertIn(EvidenceSignal.PARTICIPANT_DISAGREEMENT_ELEVATED.value, signals)
        self.assertNotIn(EvidenceSignal.PARTICIPANT_ALIGNMENT_CANDIDATE.value, signals)
        self.assertNotIn(EvidenceSignal.PARTICIPANT_CONTRARIAN_CANDIDATE.value, signals)

    def test_contract_round_trip(self) -> None:
        actions = self._configure_fixture(DISCLOSURE_FIXTURE)
        evidence = compute_crowding_evidence(
            actions,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            crowding_fixture_path=CROWDING_SLICE,
        )
        assert evidence is not None
        payload = participant_crowding_evidence_to_dict(evidence)
        self.assertEqual(payload["payload_type"], "ParticipantCrowdingEvidence")
        self.assertEqual(payload["alignment_regime"], ParticipantAlignmentRegime.DISAGREEMENT.value)

    def test_classify_participant_stance_skips_compensation(self) -> None:
        self.assertIsNone(
            classify_participant_stance(
                {
                    "action_type": "OPEN_MARKET_SELL",
                    "insider_discretion": "COMPENSATION",
                }
            )
        )

    def test_summarize_crowding_unavailable(self) -> None:
        summary = summarize_crowding(None)
        self.assertFalse(summary["crowding_available"])
        self.assertEqual(
            summary["alignment_regime"],
            ParticipantAlignmentRegime.INSUFFICIENT_DATA.value,
        )


class ParticipantCrowdingContractTests(unittest.TestCase):
    def test_participant_crowding_evidence_serialization(self) -> None:
        item = ParticipantCrowdingEvidence(
            instrument_id="BIYA",
            alignment_regime=ParticipantAlignmentRegime.CONSENSUS,
            insider_direction=None,
            institutional_direction=ParticipantStanceDirection.BULLISH.value,
            activist_direction=None,
            independent_participant_count=3,
            affiliated_participant_count=1,
            crowding_score=1.0,
            disagreement_score=0.0,
            event_time="2026-08-13T12:00:00Z",
            available_time="1786622400000000000",
            producer_version="participant_crowding_v1",
            quality_flags=(ParticipantQualityFlag.CROWDING_DATA_STALE.value,),
            cross_lane_signal=EvidenceSignal.PARTICIPANT_CROWDING_ELEVATED.value,
            supporting_action_ids=("action-1",),
        )
        payload = participant_crowding_evidence_to_dict(item)
        self.assertEqual(payload["instrument_id"], "BIYA")
        self.assertEqual(payload["crowding_score"], 1.0)
        self.assertEqual(payload["supporting_action_ids"], ["action-1"])


if __name__ == "__main__":
    unittest.main()
