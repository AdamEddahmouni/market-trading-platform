"""Unit tests for campaign observation readiness / start gate."""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from market_platform_foundation.platform.operator_diagnostics.campaign_observation_readiness import (
    BLOCKING_ALERT_NOT_ARMED,
    build_campaign_observation_readiness,
)

ET = ZoneInfo("America/New_York")


def _supervision(*, arm_status: str = "NOT_ARMED", progress_status: str = "NOT_APPLICABLE") -> dict:
    ownership = None
    if arm_status != "NOT_ARMED" or progress_status != "NOT_APPLICABLE":
        ownership = {
            "campaign_id": "RTH-OBS-NEWS-TEST",
            "runtime_sha": "abc123",
            "supervisor_identity": "imp-campaign-supervisor",
            "arm_status": arm_status,
            "observation_window_id": "OBS-TEST",
            "state_directory": "<IMP_STATE_DIR>/campaign-supervision",
            "execution_authority": "BLOCKED",
            "allows_network_submit": False,
        }
    return {
        "status": progress_status,
        "healthy": progress_status == "HEALTHY",
        "ownership": ownership,
        "heartbeat": {"last_heartbeat_utc": "2026-09-23T12:00:00Z"} if arm_status == "ARMED_RUNNING" else None,
        "progress": {
            "status": progress_status,
            "arm_status": arm_status,
            "reason": "REQUIRED_PROCESS_DEAD" if progress_status == "PROCESS_DEAD" else None,
        },
    }


class CampaignObservationReadinessTests(unittest.TestCase):
    def test_not_armed_before_rth_is_blocking_alert(self) -> None:
        # 09:00 ET on intended day — within T-60 of cash open.
        now = datetime(2026, 9, 23, 9, 0, tzinfo=ET)
        payload = build_campaign_observation_readiness(
            campaign_supervision=_supervision(),
            lifecycle={
                "services": [
                    {
                        "name": "api",
                        "health": {
                            "port_bound": False,
                            "http_alive": False,
                            "process_alive": False,
                            "identity_owned": False,
                        },
                    },
                    {
                        "name": "ui",
                        "health": {
                            "port_bound": False,
                            "http_alive": False,
                            "process_alive": False,
                            "identity_owned": False,
                        },
                    },
                ]
            },
            provider_readiness={"status": "READY"},
            ingress_enabled=False,
            item9_collector={"status": "NOT_OBSERVED"},
            intent={
                "campaign_id": "RTH-OBS-NEWS-20260923",
                "intended_date_et": "2026-09-23",
                "frozen": True,
                "runtime_sha": "bf405f46",
                "observation_window_id": "RTH-20260923",
                "source": "EXPLICIT",
            },
            now_et=now,
        )
        self.assertTrue(payload["has_blocking_alert"])
        self.assertEqual(payload["blocking_alerts"][0]["code"], BLOCKING_ALERT_NOT_ARMED)
        self.assertEqual(payload["arm_status"], "NOT_ARMED")
        self.assertFalse(payload["armed"])
        self.assertEqual(payload["frozen"], True)
        self.assertFalse(payload["api_ready"])
        self.assertFalse(payload["ui_ready"])
        self.assertEqual(payload["ingress_enabled"], False)
        self.assertIn("NOT_ARMED", payload["blockers"])
        self.assertIn("API_UNAVAILABLE", payload["blockers"])
        self.assertIn("UI_UNAVAILABLE", payload["blockers"])
        self.assertIn("INGRESS_NOT_ENABLED", payload["blockers"])
        self.assertEqual(payload["execution_authority"], "BLOCKED")
        self.assertEqual(payload["arm_observation"]["label"], "ARM OBSERVATION")
        self.assertEqual(payload["arm_observation"]["execution_authority_after_arm"], "BLOCKED")
        self.assertFalse(payload["arm_observation"]["grants_execution_authority"])
        self.assertFalse(payload["arm_observation"]["ui_mutation_wired"])
        self.assertTrue(payload["arm_observation"]["wires_existing_cli_arm"])
        self.assertEqual(payload["phase"], "READY_TO_ARM")

    def test_no_intent_no_false_blocking_alert(self) -> None:
        now = datetime(2026, 9, 23, 9, 0, tzinfo=ET)
        payload = build_campaign_observation_readiness(
            campaign_supervision=_supervision(),
            now_et=now,
            intent={"source": "NONE"},
        )
        self.assertFalse(payload["has_blocking_alert"])
        self.assertEqual(payload["phase"], "NOT_ARMED")
        self.assertFalse(payload["intended_today"])

    def test_armed_process_dead_is_active_stalled(self) -> None:
        now = datetime(2026, 9, 23, 10, 0, tzinfo=ET)
        payload = build_campaign_observation_readiness(
            campaign_supervision=_supervision(arm_status="ARMED_RUNNING", progress_status="PROCESS_DEAD"),
            intent={
                "campaign_id": "RTH-OBS-NEWS-TEST",
                "intended_date_et": "2026-09-23",
                "frozen": True,
                "source": "EXPLICIT",
            },
            now_et=now,
        )
        self.assertTrue(payload["armed"])
        self.assertEqual(payload["phase"], "ACTIVE_STALLED")
        self.assertIn("PROCESS_DEAD", payload["blockers"])
        self.assertIn("REQUIRED_PROCESS_DEAD", payload["blockers"])
        self.assertEqual(payload["heartbeat"], "PROCESS_DEAD")
        self.assertFalse(payload["has_blocking_alert"])  # armed — different failure class

    def test_missed_window_after_close(self) -> None:
        now = datetime(2026, 9, 23, 16, 30, tzinfo=ET)
        payload = build_campaign_observation_readiness(
            campaign_supervision=_supervision(),
            intent={
                "campaign_id": "RTH-OBS-NEWS-20260923",
                "intended_date_et": "2026-09-23",
                "frozen": True,
                "source": "EXPLICIT",
            },
            now_et=now,
        )
        self.assertEqual(payload["phase"], "MISSED_WINDOW")
        self.assertFalse(payload["has_blocking_alert"])

    def test_execution_always_blocked_for_observation(self) -> None:
        payload = build_campaign_observation_readiness(
            campaign_supervision=_supervision(arm_status="ARMED_RUNNING", progress_status="HEALTHY"),
            now_et=datetime(2026, 9, 23, 11, 0, tzinfo=ET),
        )
        self.assertEqual(payload["execution_authority"], "BLOCKED")
        self.assertFalse(payload["allows_network_submit"])
        self.assertTrue(payload["live_submit_forbidden"])
        self.assertTrue(payload["item9_display_only"])
        self.assertEqual(payload["phase"], "ACTIVE_PROGRESSING")


if __name__ == "__main__":
    unittest.main()
