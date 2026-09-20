"""Backend-owned operator truth tokens (Lane E contract)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from market_platform_foundation.platform.operator_diagnostics import (
    build_operator_diagnostics_snapshot,
    map_item9_corpus_progress_truth,
)
from market_platform_foundation.platform.operator_diagnostics.operator_truth import (
    build_operator_truth_section,
    item9_corpus_progress_detail,
    map_lifecycle_truth,
    next_safe_action_for_operator_row,
)
from market_platform_foundation.ui_api.store import ReplayStore

from tests.platform.test_operator_diagnostics_snapshot import _SAMPLE_RESILIENCE
from tests.ui1.test_ui_api import COLLECTION_ROOT


class OperatorTruthContractTests(unittest.TestCase):
    def test_item9_partial_corpus_is_idle_not_degraded(self) -> None:
        corpus = {
            "availability": "AVAILABLE",
            "sample_gate_progress": {"distinct_rth_dates": "2/3"},
        }
        self.assertEqual(map_item9_corpus_progress_truth(corpus), "IDLE")
        self.assertNotEqual(map_item9_corpus_progress_truth(corpus), "DEGRADED")
        nested = {
            "availability": "AVAILABLE",
            "report": {"sample_gate_progress": {"distinct_rth_dates": "2/3"}},
        }
        self.assertEqual(map_item9_corpus_progress_truth(nested), "IDLE")

    def test_item9_complete_corpus_is_healthy(self) -> None:
        corpus = {
            "availability": "AVAILABLE",
            "sample_gate_progress": {"distinct_rth_dates": "3/3"},
        }
        self.assertEqual(map_item9_corpus_progress_truth(corpus), "HEALTHY")

    def test_item9_zero_admitted_is_not_observed(self) -> None:
        corpus = {
            "availability": "AVAILABLE",
            "sample_gate_progress": {"distinct_rth_dates": "0/3"},
        }
        self.assertEqual(map_item9_corpus_progress_truth(corpus), "NOT_OBSERVED")

    def test_lifecycle_stopped_is_blocked(self) -> None:
        self.assertEqual(map_lifecycle_truth("STOPPED"), "BLOCKED")
        self.assertEqual(map_lifecycle_truth("HEALTHY"), "HEALTHY")

    def test_truth_section_2_of_3_is_idle_independent_of_severity_inputs(self) -> None:
        section = build_operator_truth_section(
            as_of_utc="2026-09-18T00:00:00+00:00",
            lifecycle_status="HEALTHY",
            readiness_status="READY",
            runtime_git_sha="abc",
            item9_disposition="NOT_RTH",
            item9_corpus_status={
                "availability": "AVAILABLE",
                "sample_gate_progress": {"distinct_rth_dates": "2/3"},
            },
            collector_detected=False,
            collector_probe_status="COMPLETED",
            live_execution_env=False,
            expected_cycle_failure="NOT_OBSERVED",
            cycle_gap_note="Collector log not configured.",
            evidence_gaps=[],
        )
        self.assertEqual(section["by_id"]["item9-corpus"], "IDLE")
        self.assertNotEqual(section["by_id"]["item9-corpus"], "DEGRADED")
        self.assertEqual(section["by_id"]["live-execution"], "BLOCKED")
        self.assertEqual(section["clock"]["kind"], "wall_utc")
        corpus_row = next(row for row in section["rows"] if row["id"] == "item9-corpus")
        self.assertEqual(corpus_row["detail"], "2/3")
        self.assertIn("Do not calibrate", corpus_row["next_safe_action"])
        self.assertIn("do not enable Live", corpus_row["next_safe_action"])


class Item9UnavailableHonestyTests(unittest.TestCase):
    def test_unavailable_corpus_detail_is_unavailable_not_two_of_three(self) -> None:
        corpus = {"availability": "UNAVAILABLE"}
        self.assertEqual(map_item9_corpus_progress_truth(corpus), "UNAVAILABLE")
        self.assertEqual(item9_corpus_progress_detail(corpus, "UNAVAILABLE"), "UNAVAILABLE")
        self.assertNotEqual(item9_corpus_progress_detail(corpus, "UNAVAILABLE"), "2/3")
        self.assertNotEqual(item9_corpus_progress_detail(corpus, "UNAVAILABLE"), "NOT_OBSERVED")
        section = build_operator_truth_section(
            as_of_utc="2026-09-19T00:00:00+00:00",
            lifecycle_status="UNKNOWN",
            readiness_status=None,
            runtime_git_sha=None,
            item9_disposition="UNKNOWN",
            item9_corpus_status=corpus,
            collector_detected=False,
            collector_probe_status=None,
            live_execution_env=False,
            expected_cycle_failure="NOT_OBSERVED",
            cycle_gap_note=None,
            evidence_gaps=[],
        )
        corpus_row = next(row for row in section["rows"] if row["id"] == "item9-corpus")
        self.assertEqual(section["by_id"]["item9-corpus"], "UNAVAILABLE")
        self.assertEqual(corpus_row["detail"], "UNAVAILABLE")
        self.assertNotIn("2/3", corpus_row["detail"])
        self.assertNotEqual(corpus_row["truth"], "IDLE")
        self.assertNotEqual(corpus_row["truth"], "DEGRADED")
        self.assertIn("do not mint 2/3", corpus_row["next_safe_action"])
        live_row = next(row for row in section["rows"] if row["id"] == "live-execution")
        self.assertEqual(live_row["detail"], "Live OFF")
        self.assertIn("Leave Live OFF", live_row["next_safe_action"])
        healthy_action = next_safe_action_for_operator_row("item9-corpus", "HEALTHY")
        self.assertIn("NOT CALIBRATED", healthy_action)
        self.assertIn("Do not enable Live", healthy_action)
        self.assertNotIn("2/3", healthy_action)


class OperatorDiagnosticsSnapshotTruthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()

    @patch("tools.platform.control_service.build_control_status")
    @patch(
        "market_platform_foundation.platform.operator_diagnostics.snapshot.build_runtime_resilience_diagnostic",
    )
    @patch(
        "market_platform_foundation.platform.operator_diagnostics.snapshot._item9_corpus_status_section",
    )
    def test_snapshot_exposes_operator_truth_and_strips_internals(
        self,
        mock_corpus,
        mock_resilience,
        mock_lifecycle,
    ) -> None:
        mock_lifecycle.return_value = {
            "schema_version": "operator-lifecycle/1.1",
            "status": "HEALTHY",
            "services": [],
            "update": {"status": "UNAVAILABLE"},
        }
        mock_resilience.return_value = dict(_SAMPLE_RESILIENCE)
        mock_corpus.return_value = {
            "availability": "AVAILABLE",
            "receipt_scope": "FROZEN_COLLECTOR_WORKTREE_READ_ONLY",
            "sample_gate_progress": {"distinct_rth_dates": "2/3"},
            "calibration_state": "NOT_CALIBRATED",
            "fitting_allowed": False,
            "does_not_infer_calibrated": True,
        }
        payload = build_operator_diagnostics_snapshot(self.store)
        self.assertEqual(payload["schema_version"], "operator-diagnostics/1.1.0")
        self.assertEqual(payload["as_of_clock_kind"], "wall_utc")
        self.assertNotIn("generated_at_monotonic", payload)
        corpus = payload["sections"]["runtime"]["item9_corpus_status"]
        self.assertNotIn("receipt_dir", corpus)
        self.assertEqual(payload["operator_truth"]["by_id"]["item9-corpus"], "IDLE")
        self.assertNotEqual(payload["operator_truth"]["by_id"]["item9-corpus"], "DEGRADED")
        self.assertNotEqual(payload["operator_truth"]["by_id"]["item9-corpus"], "HEALTHY")
        # Snapshot severity is independent of Item 9 2/3: readiness != READY or
        # non-empty evidence_gaps may honestly yield DEGRADED. Do not require OK.
        serialized = json.dumps(payload)
        self.assertNotIn("generated_at_monotonic", serialized)


if __name__ == "__main__":
    unittest.main()
