from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.platform.control_service import ALLOWED_ACTIONS, build_control_status, normalize_action
from market_platform_foundation.platform.security.route_policy import policy_for_route


class OperatorControlServiceTests(unittest.TestCase):
    def test_normalize_action_allows_only_finite_lifecycle_commands(self) -> None:
        self.assertEqual(normalize_action(" restart "), "restart")
        self.assertIsNone(normalize_action("run arbitrary command"))
        self.assertIn("apply_update", ALLOWED_ACTIONS)

    def test_control_status_is_sanitized_and_reports_not_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = build_control_status(Path(tmp))

        self.assertEqual(payload["schema_version"], "operator-lifecycle/1.0")
        self.assertEqual(payload["status"], "STOPPED")
        self.assertNotIn("secrets_included", payload)
        self.assertEqual(payload["services"], [])

    def test_operator_routes_use_narrow_capabilities(self) -> None:
        self.assertEqual(policy_for_route("GET", "/operator/readiness").capability, "state.read")
        self.assertEqual(policy_for_route("GET", "/operator/lifecycle/status").capability, "state.read")
        self.assertEqual(
            policy_for_route("POST", "/operator/lifecycle/actions").capability,
            "operator.lifecycle.write",
        )
        self.assertEqual(
            policy_for_route("POST", "/operator/config/provider").capability,
            "security.config.write",
        )

    def test_windows_setup_entrypoint_is_present_and_guided(self) -> None:
        script = Path(__file__).resolve().parents[2] / "SETUP_PLATFORM.cmd"
        contents = script.read_text(encoding="utf-8")
        self.assertIn("bootstrap.py", contents)
        self.assertIn("choice /c DC", contents)
        self.assertIn("START_PLATFORM.cmd", contents)


if __name__ == "__main__":
    unittest.main()
