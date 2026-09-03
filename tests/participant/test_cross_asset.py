"""Tests for PI11 cross-asset participant context."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.participant import (  # noqa: E402
    CrossAssetAlignmentRegime,
    CrossAssetParticipantContextEvidence,
    cross_asset_participant_context_evidence_to_dict,
)
from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.donor_bridge.participant_adapter import (  # noqa: E402
    build_participant_cross_lane_bundle,
)
from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
)
from market_platform_foundation.futures.positioning import CrowdingRegime  # noqa: E402
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.participant.bridge import query_participant_actions_from_ledger  # noqa: E402
from market_platform_foundation.participant.crowding import compute_crowding_evidence  # noqa: E402
from market_platform_foundation.participant.cross_asset import (  # noqa: E402
    _classify_alignment,
    build_cross_asset_participant_context_bundle,
    compute_cross_asset_context,
    publish_cross_asset_signals,
    summarize_cross_asset_context,
    _fetch_cot_payload,
)
from market_platform_foundation.providers.whale_ledger import build_ledger_from_edgar_fixture  # noqa: E402

CROWDING_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "edgar" / "biya_institutional_crowding.json"
CROWDING_SLICE = ROOT / "tests" / "fixtures" / "participant" / "biya_crowding_slice.json"
CROSS_ASSET_SLICE = ROOT / "tests" / "fixtures" / "participant" / "biya_cross_asset_slice.json"
COT_FIXTURE = ROOT / "tests" / "fixtures" / "providers" / "futures" / "es_cot_positioning_slice.json"
COT_DIVERGENT_FIXTURE = (
    ROOT / "tests" / "fixtures" / "providers" / "futures" / "es_cot_positioning_divergent_slice.json"
)
GOLDEN_FIXTURE = ROOT / "tests" / "fixtures" / "participant" / "biya_cross_asset_expected.json"


class CrossAssetTests(unittest.TestCase):
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

    def test_golden_aligned_fixture(self) -> None:
        actions = self._configure_fixture(CROWDING_FIXTURE)
        bundle = build_cross_asset_participant_context_bundle(
            actions,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            cross_asset_fixture_path=CROSS_ASSET_SLICE,
        )
        self.assertEqual(bundle["summary"], self.golden["summary"])

    def test_aligned_bullish_regime_and_signal(self) -> None:
        actions = self._configure_fixture(CROWDING_FIXTURE)
        crowding = compute_crowding_evidence(
            actions,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            crowding_fixture_path=CROWDING_SLICE,
        )
        assert crowding is not None
        cot_payload = _fetch_cot_payload(
            futures_symbol="ES",
            decision_time="2025-05-31T23:59:59Z",
            cot_fixture_path=COT_FIXTURE,
        )
        evidence = compute_cross_asset_context(
            crowding,
            cot_payload,
            equity_symbol="BIYA",
            futures_symbol="ES",
            prediction_cutoff=self.cutoff,
        )
        assert evidence is not None
        self.assertEqual(evidence.alignment_regime, CrossAssetAlignmentRegime.ALIGNED_BULLISH)
        self.assertEqual(evidence.alignment_score, 1.0)
        self.assertEqual(evidence.futures_cot_regime, CrowdingRegime.CROWDED_LONG.value)
        self.assertEqual(
            evidence.cross_lane_signal,
            EvidenceSignal.PARTICIPANT_CROSS_ASSET_ALIGNED.value,
        )

    def test_divergent_regime_and_signal(self) -> None:
        actions = self._configure_fixture(CROWDING_FIXTURE)
        crowding = compute_crowding_evidence(
            actions,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            crowding_fixture_path=CROWDING_SLICE,
        )
        assert crowding is not None
        cot_payload = _fetch_cot_payload(
            futures_symbol="ES",
            decision_time="2025-05-31T23:59:59Z",
            cot_fixture_path=COT_DIVERGENT_FIXTURE,
        )
        evidence = compute_cross_asset_context(
            crowding,
            cot_payload,
            equity_symbol="BIYA",
            futures_symbol="ES",
            prediction_cutoff=self.cutoff,
        )
        assert evidence is not None
        self.assertEqual(evidence.alignment_regime, CrossAssetAlignmentRegime.DIVERGENT)
        self.assertEqual(evidence.alignment_score, 0.0)
        self.assertEqual(evidence.futures_cot_regime, CrowdingRegime.CROWDED_SHORT.value)
        self.assertEqual(
            evidence.cross_lane_signal,
            EvidenceSignal.PARTICIPANT_CROSS_ASSET_DIVERGENT.value,
        )

    def test_pit_excludes_future_cot_report(self) -> None:
        actions = self._configure_fixture(CROWDING_FIXTURE)
        crowding = compute_crowding_evidence(
            actions,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            crowding_fixture_path=CROWDING_SLICE,
        )
        assert crowding is not None
        cot_payload = _fetch_cot_payload(
            futures_symbol="ES",
            decision_time="2025-03-01T00:00:00Z",
            cot_fixture_path=COT_FIXTURE,
        )
        self.assertFalse(cot_payload.get("futures_positioning_available"))
        evidence = compute_cross_asset_context(
            crowding,
            cot_payload,
            equity_symbol="BIYA",
            futures_symbol="ES",
            prediction_cutoff=self.cutoff,
        )
        assert evidence is not None
        self.assertEqual(evidence.alignment_regime, CrossAssetAlignmentRegime.INSUFFICIENT_DATA)
        self.assertIsNone(evidence.cross_lane_signal)

    def test_classify_alignment_matrix(self) -> None:
        self.assertEqual(
            _classify_alignment(
                equity_direction="BULLISH",
                cot_regime=CrowdingRegime.CROWDED_LONG.value,
            ),
            CrossAssetAlignmentRegime.ALIGNED_BULLISH,
        )
        self.assertEqual(
            _classify_alignment(
                equity_direction="BEARISH",
                cot_regime=CrowdingRegime.CROWDED_SHORT.value,
            ),
            CrossAssetAlignmentRegime.ALIGNED_BEARISH,
        )
        self.assertEqual(
            _classify_alignment(
                equity_direction="BULLISH",
                cot_regime=CrowdingRegime.CROWDED_SHORT.value,
            ),
            CrossAssetAlignmentRegime.DIVERGENT,
        )
        self.assertEqual(
            _classify_alignment(
                equity_direction="BULLISH",
                cot_regime=CrowdingRegime.NEUTRAL.value,
            ),
            CrossAssetAlignmentRegime.MIXED,
        )

    def test_cross_lane_bundle_publishes_aligned_signal(self) -> None:
        configure_institutional_ledger(
            build_ledger_from_edgar_fixture(fixture_path=CROWDING_FIXTURE, as_of_time_ns=self.cutoff)
        )
        snapshot, evidence = build_participant_cross_lane_bundle(
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            crowding_fixture_path=CROWDING_SLICE,
            cross_asset_fixture_path=CROSS_ASSET_SLICE,
        )
        self.assertTrue(snapshot.get("participant_cross_asset_available"))
        signals = {row.get("signal") for row in evidence}
        self.assertIn(EvidenceSignal.PARTICIPANT_CROSS_ASSET_ALIGNED.value, signals)
        self.assertNotIn(EvidenceSignal.FUTURES_POSITIONING_CROWDED_LONG.value, signals)

    def test_publish_signals_empty_when_insufficient(self) -> None:
        evidence = CrossAssetParticipantContextEvidence(
            equity_symbol="BIYA",
            futures_symbol="ES",
            equity_crowding_regime=None,
            futures_cot_regime=None,
            alignment_regime=CrossAssetAlignmentRegime.INSUFFICIENT_DATA,
            alignment_score=None,
            equity_institutional_direction=None,
            futures_cot_net_percentile=None,
            event_time="2026-08-13T12:00:00Z",
            available_time="2026-08-13T12:00:00Z",
            producer_version="participant_cross_asset_v1",
        )
        published = publish_cross_asset_signals(evidence, prediction_cutoff=self.cutoff)
        self.assertEqual(published, [])

    def test_summarize_unavailable(self) -> None:
        summary = summarize_cross_asset_context(None)
        self.assertFalse(summary["cross_asset_available"])
        self.assertEqual(
            summary["alignment_regime"],
            CrossAssetAlignmentRegime.INSUFFICIENT_DATA.value,
        )

    def test_contract_round_trip(self) -> None:
        actions = self._configure_fixture(CROWDING_FIXTURE)
        bundle = build_cross_asset_participant_context_bundle(
            actions,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
            cross_asset_fixture_path=CROSS_ASSET_SLICE,
        )
        evidence_raw = bundle.get("evidence_object")
        assert evidence_raw is not None
        payload = cross_asset_participant_context_evidence_to_dict(evidence_raw)
        self.assertEqual(payload["payload_type"], "CrossAssetParticipantContextEvidence")
        self.assertEqual(payload["alignment_regime"], CrossAssetAlignmentRegime.ALIGNED_BULLISH.value)


if __name__ == "__main__":
    unittest.main()
