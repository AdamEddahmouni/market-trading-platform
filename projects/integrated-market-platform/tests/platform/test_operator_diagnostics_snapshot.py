"""Operator diagnostics snapshot composition (Lane C)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from market_platform_foundation.platform.operator_diagnostics import build_operator_diagnostics_snapshot
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

_SAMPLE_RESILIENCE = {
    "artifact_kind": "imp_runtime_resilience_diagnostic",
    "schema_version": "1.0.0",
    "observed_at_ns": 1,
    "evidence_class": "SOFTWARE",
    "runtime_identity": {
        "runtime_git_sha": "270ce2a6acdb975230495373613f1a65bfde8294",
        "frozen_collector_worktree_sha": "fed2d9f7",
        "frozen_collector_imp_root": "/worktrees/.imp-actual-01-phase-d",
        "runtime_matches_frozen_authority": False,
    },
    "provider_connectivity": {"state": "REACHABLE", "failure_class": "NONE"},
    "collector_process": {
        "active_collector_detected": False,
        "active_collector_matches": [
            "python tools/moomoo/opend_bar_1m_prospective_proof.py prospective --poll secret=abc123"
        ],
        "probe_status": "COMPLETED",
    },
    "item9_next_rth_preflight": {
        "disposition": "NOT_RTH",
        "blockers": [],
        "reason_codes": [],
    },
    "expected_cycle": {
        "receipt_inventory": {"availability": "AVAILABLE", "receipt_file_count": 0},
        "collector_log_gaps": None,
    },
    "readiness_vs_liveness": {"readiness": {}, "liveness": {}},
}


class OperatorDiagnosticsSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()

    @patch("tools.platform.control_service.build_control_status")
    @patch(
        "market_platform_foundation.platform.operator_diagnostics.snapshot.build_runtime_resilience_diagnostic",
    )
    def test_snapshot_schema_and_questions(self, mock_resilience, mock_lifecycle) -> None:
        mock_lifecycle.return_value = {
            "schema_version": "operator-lifecycle/1.1",
            "status": "HEALTHY",
            "services": [],
            "update": {"status": "UNAVAILABLE"},
        }
        mock_resilience.return_value = dict(_SAMPLE_RESILIENCE)
        payload = build_operator_diagnostics_snapshot(self.store)
        self.assertEqual(payload["schema_version"], "operator-diagnostics/1.1.0")
        self.assertNotIn("generated_at_monotonic", payload)
        self.assertIn("operator_truth", payload)
        self.assertFalse(payload["secrets_included"])
        questions = payload["operator_questions"]
        self.assertIn("q01_imp_running", questions)
        self.assertIn("q16_human_headline", questions)
        self.assertEqual(questions["q08_collector_active"]["process_probe_status"], "COMPLETED")
        resilience_section = payload["sections"]["runtime"]["runtime_resilience"]
        self.assertNotIn("active_collector_matches", resilience_section["collector_process"])
        self.assertEqual(resilience_section["collector_process"]["active_collector_match_count"], 1)
        summaries = resilience_section["collector_process"]["active_collector_match_summaries"]
        self.assertEqual(summaries, ["item9_prospective_poll_process"])
        serialized = json.dumps(payload).lower()
        self.assertNotIn("abc123", serialized)
        config_section = payload["sections"]["configuration"]["summary"]
        for row in config_section.get("providers", []):
            self.assertNotIn("value", row)

    def test_endpoint_registered_in_route_policy(self) -> None:
        from market_platform_foundation.platform.security.route_policy import policy_for_route

        policy = policy_for_route("GET", "/operator/diagnostics")
        self.assertEqual(policy.capability, "state.read")


if __name__ == "__main__":
    unittest.main()
