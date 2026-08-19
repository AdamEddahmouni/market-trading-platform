"""Tests for PI4 13F foundation — holdings snapshots and QoQ position changes."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.participant import (  # noqa: E402
    ParticipantActionType,
    ParticipantQualityFlag,
)
from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.participant.bridge import query_participant_actions_from_ledger  # noqa: E402
from market_platform_foundation.participant.evidence import (  # noqa: E402
    build_institutional_holding_evidence,
    participant_cross_lane_evidence_from_actions,
)
from market_platform_foundation.providers.whale_ledger import build_ledger_from_edgar_fixture  # noqa: E402

ALPHA_FIXTURE = (
    ROOT / "tests" / "fixtures" / "providers" / "edgar" / "alpha_fund_13f_q1_q2.json"
)


class Institutional13FTests(unittest.TestCase):
    def _ledger(self, *, as_of_iso: str) -> object:
        return build_ledger_from_edgar_fixture(
            fixture_path=ALPHA_FIXTURE,
            as_of_time_ns=iso_to_epoch_ns(as_of_iso),
        )

    def _actions(self, *, instrument_id: str, as_of_iso: str) -> list[dict]:
        ledger = self._ledger(as_of_iso=as_of_iso)
        cutoff = iso_to_epoch_ns(as_of_iso)
        return query_participant_actions_from_ledger(
            ledger.events,
            instrument_id=instrument_id,
            prediction_cutoff=cutoff,
        )

    def test_13f_snapshot_uses_quarter_end_action_time(self) -> None:
        actions = self._actions(instrument_id="BIYA", as_of_iso="2026-05-21T00:00:00Z")
        snapshots = [
            row
            for row in actions
            if row["action_type"] == ParticipantActionType.INSTITUTIONAL_HOLDING_SNAPSHOT.value
        ]
        self.assertGreater(len(snapshots), 0)
        snapshot = snapshots[0]
        self.assertEqual(snapshot["action_time"], "2026-03-31")
        self.assertEqual(str(snapshot["available_time"]), str(iso_to_epoch_ns("2026-05-20T14:00:00Z")))

    def test_13f_quality_flags_include_not_copyable(self) -> None:
        actions = self._actions(instrument_id="BIYA", as_of_iso="2026-05-21T00:00:00Z")
        for row in actions:
            if row["action_type"] == ParticipantActionType.INSTITUTIONAL_HOLDING_SNAPSHOT.value:
                self.assertIn(ParticipantQualityFlag.QUARTER_END_NOT_COPYABLE.value, row["quality_flags"])
                self.assertIn(ParticipantQualityFlag.POSITION_STALE.value, row["quality_flags"])

    def test_pit_hides_q2_before_filing(self) -> None:
        actions = self._actions(instrument_id="BIYA", as_of_iso="2026-08-14T23:59:59Z")
        q2_snapshots = [
            row
            for row in actions
            if row.get("quarter_end") == "2026-06-30"
        ]
        q2_changes = [
            row
            for row in actions
            if row["action_type"] in {
                ParticipantActionType.POSITION_INCREASED.value,
                ParticipantActionType.POSITION_INITIATED.value,
            }
            and row.get("quarter_end") == "2026-06-30"
        ]
        self.assertEqual(q2_snapshots, [])
        self.assertEqual(q2_changes, [])

    def test_position_initiated_first_quarter(self) -> None:
        actions = self._actions(instrument_id="BIYA", as_of_iso="2026-05-21T00:00:00Z")
        initiated = [
            row
            for row in actions
            if row["action_type"] == ParticipantActionType.POSITION_INITIATED.value
        ]
        self.assertEqual(len(initiated), 1)
        self.assertEqual(initiated[0]["quantity"], 105000.0)
        self.assertEqual(initiated[0]["action_time"], "2026-03-31")

    def test_position_increased_reduced_exited(self) -> None:
        biya_actions = self._actions(instrument_id="BIYA", as_of_iso="2026-08-16T00:00:00Z")
        increased = next(
            row
            for row in biya_actions
            if row["action_type"] == ParticipantActionType.POSITION_INCREASED.value
        )
        self.assertEqual(increased["quantity"], 45000.0)
        self.assertEqual(increased["prior_shares"], 105000.0)
        self.assertEqual(increased["current_shares"], 150000.0)
        self.assertEqual(str(increased["available_time"]), str(iso_to_epoch_ns("2026-08-15T10:00:00Z")))

        aapl_actions = self._actions(instrument_id="AAPL", as_of_iso="2026-08-16T00:00:00Z")
        aapl_initiated = next(
            row
            for row in aapl_actions
            if row["action_type"] == ParticipantActionType.POSITION_INITIATED.value
        )
        self.assertEqual(aapl_initiated["quantity"], 25000.0)

        nvda_actions = self._actions(instrument_id="NVDA", as_of_iso="2026-08-16T00:00:00Z")
        exited = next(
            row
            for row in nvda_actions
            if row["action_type"] == ParticipantActionType.POSITION_EXITED.value
        )
        self.assertEqual(exited["quantity"], 5000.0)
        self.assertEqual(exited["prior_shares"], 5000.0)
        self.assertIsNone(exited["current_shares"])

    def test_amendment_supersedes_prior_revision(self) -> None:
        actions = self._actions(instrument_id="BIYA", as_of_iso="2026-05-21T00:00:00Z")
        snapshots = [
            row
            for row in actions
            if row["action_type"] == ParticipantActionType.INSTITUTIONAL_HOLDING_SNAPSHOT.value
            and row.get("quarter_end") == "2026-03-31"
        ]
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["shares"], 105000.0)
        self.assertEqual(snapshots[0]["source_revision_id"], "2")

    def test_cross_lane_holding_change_signal(self) -> None:
        actions = self._actions(instrument_id="BIYA", as_of_iso="2026-05-21T00:00:00Z")
        evidence = build_institutional_holding_evidence(
            next(
                row
                for row in actions
                if row["action_type"] == ParticipantActionType.POSITION_INITIATED.value
            )
        )
        assert evidence is not None
        self.assertEqual(
            evidence.cross_lane_signal,
            EvidenceSignal.INSTITUTIONAL_HOLDING_CHANGE.value,
        )
        signals = {
            row["signal"]
            for row in participant_cross_lane_evidence_from_actions(actions)
            if row.get("signal") != EvidenceSignal.PARTICIPANT_DATA_CONFIDENCE.value
        }
        self.assertIn(EvidenceSignal.INSTITUTIONAL_HOLDING_CHANGE.value, signals)

    def test_no_lookahead_via_quarter_end(self) -> None:
        actions = self._actions(instrument_id="BIYA", as_of_iso="2026-07-01T12:00:00Z")
        q2_rows = [row for row in actions if row.get("quarter_end") == "2026-06-30"]
        self.assertEqual(q2_rows, [])


if __name__ == "__main__":
    unittest.main()
