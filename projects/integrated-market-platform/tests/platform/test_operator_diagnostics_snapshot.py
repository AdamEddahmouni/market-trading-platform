"""Operator diagnostics snapshot composition (Lane C)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from market_platform_foundation.platform.operator_diagnostics import build_operator_diagnostics_snapshot
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT


class OperatorDiagnosticsSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()

    @patch("tools.platform.control_service.build_control_status")
    @patch(
        "market_platform_foundation.platform.operator_diagnostics.snapshot.run_item9_next_rth_preflight",
    )
    def test_snapshot_schema_and_questions(self, mock_item9, mock_lifecycle) -> None:
        mock_lifecycle.return_value = {
            "schema_version": "operator-lifecycle/1.1",
            "status": "HEALTHY",
            "services": [],
            "update": {"status": "UNAVAILABLE"},
        }
        mock_item9.return_value = {
            "disposition": "NOT_RTH",
            "runtime": {
                "runtime_matches_frozen_authority": False,
                "frozen_collector_available": True,
                "frozen_collector_git_sha": "fed2d9f7",
            },
            "active_collector": {"detected": False, "process_probe_status": "NOT_RUN"},
            "output_path_gate": {"ok": True},
            "calendar": {"rth_active": False},
        }
        payload = build_operator_diagnostics_snapshot(self.store)
        self.assertEqual(payload["schema_version"], "operator-diagnostics/1.0.0")
        self.assertFalse(payload["secrets_included"])
        questions = payload["operator_questions"]
        self.assertIn("q01_imp_running", questions)
        self.assertIn("q16_human_headline", questions)
        self.assertEqual(questions["q08_collector_active"]["process_probe_status"], "NOT_RUN")
        # Credential *identifiers* (e.g. APCA_API_KEY_ID) may appear; values must not.
        config_section = payload["sections"]["configuration"]["summary"]
        for row in config_section.get("providers", []):
            self.assertNotIn("value", row)
        serialized = json.dumps(payload).lower()
        self.assertNotIn('"sk-', serialized)

    def test_endpoint_registered_in_route_policy(self) -> None:
        from market_platform_foundation.platform.security.route_policy import policy_for_route

        policy = policy_for_route("GET", "/operator/diagnostics")
        self.assertEqual(policy.capability, "state.read")


if __name__ == "__main__":
    unittest.main()
