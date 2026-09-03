"""Tests for Participant Intelligence evidence builders (PI3)."""

from __future__ import annotations

import json
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
from market_platform_foundation.features.institutional import (  # noqa: E402
    configure_institutional_ledger,
    get_institutional_ledger,
    query_institutional_evidence,
    REGULATORY_DISCLOSURE_FAMILY,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.participant.evidence import (  # noqa: E402
    PRODUCER_VERSION,
    build_activist_evidence,
    build_insider_evidence,
    participant_cross_lane_evidence_from_actions,
    summarize_participant_actions,
)
from market_platform_foundation.participant.bridge import (  # noqa: E402
    query_participant_actions_from_ledger,
)
from market_platform_foundation.providers.adapters.edgar_disclosure import (  # noqa: E402
    DEFAULT_FIXTURE,
)
from market_platform_foundation.providers.whale_ledger import (  # noqa: E402
    build_ledger_from_edgar_fixture,
)


class ParticipantEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_ledger = get_institutional_ledger()
        self.cutoff = iso_to_epoch_ns("2026-07-16T23:59:59Z")
        self.ledger = build_ledger_from_edgar_fixture(
            fixture_path=DEFAULT_FIXTURE,
            as_of_time_ns=self.cutoff,
        )
        configure_institutional_ledger(self.ledger)

    def tearDown(self) -> None:
        configure_institutional_ledger(self._original_ledger)

    def _actions(self) -> list[dict]:
        return query_participant_actions_from_ledger(
            self.ledger.events,
            instrument_id="BIYA",
            prediction_cutoff=self.cutoff,
        )

    def test_enriched_form4_maps_quantity_and_notional(self) -> None:
        actions = self._actions()
        jane = next(row for row in actions if row.get("display_name") == "Jane Officer" and row.get("quantity") == 5000.0)
        self.assertEqual(jane["action_type"], ParticipantActionType.OPEN_MARKET_BUY.value)
        self.assertEqual(jane["quantity"], 5000.0)
        self.assertEqual(jane["transaction_price"], 12.5)
        self.assertEqual(jane["notional"], 62500.0)
        self.assertEqual(jane["insider_discretion"], InsiderDiscretion.DISCRETIONARY.value)

    def test_10b5_1_maps_to_plan_discretion(self) -> None:
        actions = self._actions()
        grant = next(row for row in actions if row.get("display_name") == "Grant Executive")
        self.assertEqual(grant["action_type"], ParticipantActionType.INSIDER_AWARD_GRANT.value)
        self.assertTrue(grant.get("is_10b5_1"))
        self.assertEqual(grant["insider_discretion"], InsiderDiscretion.PLAN_10B5_1.value)

    def test_13d_publishes_activist_signal(self) -> None:
        actions = self._actions()
        activist = next(row for row in actions if row.get("display_name") == "Activist Capital LP")
        evidence = build_activist_evidence(activist)
        assert evidence is not None
        self.assertEqual(evidence.cross_lane_signal, EvidenceSignal.ACTIVIST_STAKE_DISCLOSED.value)
        self.assertEqual(evidence.stake_percent, 8.2)

    def test_13g_does_not_publish_activist_signal(self) -> None:
        actions = self._actions()
        passive = next(row for row in actions if row.get("display_name") == "Passive Index Fund LLC")
        evidence = build_activist_evidence(passive)
        assert evidence is not None
        self.assertIsNone(evidence.cross_lane_signal)

    def test_compensation_insider_emits_non_directional_signal(self) -> None:
        actions = self._actions()
        grant = next(row for row in actions if row.get("display_name") == "Grant Executive")
        insider = build_insider_evidence(grant)
        assert insider is not None
        self.assertEqual(
            insider.cross_lane_signal,
            EvidenceSignal.INSIDER_SALE_NON_DISCRETIONARY.value,
        )

    def test_pit_excludes_future_insider(self) -> None:
        actions = self._actions()
        filers = {row.get("display_name") for row in actions}
        self.assertNotIn("Future Insider", filers)

    def test_golden_summary_matches_fixture(self) -> None:
        expected_path = ROOT / "tests" / "fixtures" / "participant" / "biya_participant_evidence_expected.json"
        expected = json.loads(expected_path.read_text(encoding="utf-8"))
        actions = self._actions()
        summary = summarize_participant_actions(actions)
        self.assertEqual(summary["discretionary_buy_count"], expected["summary"]["discretionary_buy_count"])
        self.assertEqual(summary["activist_disclosure_count"], expected["summary"]["activist_disclosure_count"])
        self.assertEqual(summary["compensation_count"], expected["summary"]["compensation_count"])
        self.assertEqual(summary["action_count"], expected["summary"]["action_count"])
        signals = {
            row["signal"]
            for row in participant_cross_lane_evidence_from_actions(actions)
            if row.get("signal") != EvidenceSignal.PARTICIPANT_DATA_CONFIDENCE.value
        }
        self.assertIn(EvidenceSignal.ACTIVIST_STAKE_DISCLOSED.value, signals)
        self.assertIn(EvidenceSignal.INSIDER_DISCRETIONARY_PURCHASE.value, signals)
        self.assertEqual(PRODUCER_VERSION, expected["producer_version"])

    def test_institutional_query_uses_participant_semantics(self) -> None:
        row = query_institutional_evidence(
            REGULATORY_DISCLOSURE_FAMILY,
            prediction_cutoff=self.cutoff,
            instrument_id="BIYA",
        )
        self.assertEqual(row["status"], "available")
        self.assertNotEqual(row["direction"], "neutral")
        self.assertGreater(int(row["discretionary_buy_count"]), 0)


if __name__ == "__main__":
    unittest.main()
