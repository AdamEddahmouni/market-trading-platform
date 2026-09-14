"""FTEP integrity check read model."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.intelligence.paper_forward_bridge.activation import (
    load_activation_manifest,
)
from market_platform_foundation.intelligence.paper_forward_bridge.campaign_status import (
    collect_ftep_campaign_status,
)
from market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity import (
    collect_ftep_integrity_checks,
)
from market_platform_foundation.local_state.paths import REPO_ROOT
from market_platform_foundation.local_state.startup import (
    open_local_state,
    reset_local_state_for_tests,
)

T0 = 1_700_000_000_000_000_000
HOUR_NS = 3_600_000_000_000
RTH_BASELINE_SESSION_ID = "fts-195828068F2223FC"
RTH_AI_SESSION_ID = "fts-2AA0308AB3779C14"


def _durable_state_check(payload: dict) -> dict:
    return next(
        item
        for item in payload["checks"]
        if item["check_id"] == "signal_only_session_requires_durable_state"
    )


def _seed_v1_002_sessions(
    connection,
    *,
    campaign_id: str,
    session_ids: tuple[str, ...],
    campaign_id_override: str | None = None,
) -> None:
    bound_campaign = campaign_id_override or campaign_id
    for index, session_id in enumerate(session_ids):
        connection.execute(
            """
            INSERT INTO forward_test_sessions(
                session_id, account_id, mode, strategy_id, strategy_version,
                universe_json, evaluation_horizon_ns, created_at_ns, status,
                config_json, campaign_id
            ) VALUES (?, ?, 'PAPER', 'news_deterministic_baseline', '1.0.0',
                      '["AAPL"]', ?, ?, 'ACTIVE', '{}', ?)
            """,
            (
                session_id,
                f"paper-signal-only-{index}",
                HOUR_NS,
                T0 + index,
                bound_campaign,
            ),
        )


class FtepIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"

    def test_v1_002_integrity_surfaces_persistence_hint_without_env(self) -> None:
        prior_persist = os.environ.pop("IMP_PERSIST_STATE", None)
        prior_state_dir = os.environ.pop("IMP_STATE_DIR", None)
        try:
            payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
        finally:
            if prior_persist is not None:
                os.environ["IMP_PERSIST_STATE"] = prior_persist
            if prior_state_dir is not None:
                os.environ["IMP_STATE_DIR"] = prior_state_dir
        self.assertEqual(payload["disposition"], "FAIL")
        self.assertIn("campaign_readiness_ready", payload["failed_check_ids"])
        self.assertTrue(payload.get("operator_hints"))
        self.assertIn("IMP_PERSIST_STATE", payload["operator_hints"][0])

    def test_v1_002_integrity_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["IMP_STATE_DIR"] = tmp
            os.environ["IMP_PERSIST_STATE"] = "1"
            reset_local_state_for_tests()
            try:
                payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
            finally:
                reset_local_state_for_tests()
                os.environ.pop("IMP_STATE_DIR", None)
        self.assertEqual(payload["disposition"], "PASS")
        self.assertEqual(payload["failed_check_ids"], [])

    def test_signal_only_started_accepts_rth_durable_session_pair(self) -> None:
        manifest = load_activation_manifest("FTEP-V1-002")
        campaign_id = str(manifest.campaign_id or "")
        self.assertTrue(campaign_id)

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["IMP_STATE_DIR"] = tmp
            os.environ["IMP_PERSIST_STATE"] = "1"
            reset_local_state_for_tests()
            try:
                local = open_local_state(force=True)
                self.assertIsNotNone(local)
                _seed_v1_002_sessions(
                    local.connection,
                    campaign_id=campaign_id,
                    session_ids=(RTH_BASELINE_SESSION_ID, RTH_AI_SESSION_ID),
                )
                status = collect_ftep_campaign_status(REPO_ROOT, "FTEP-V1-002")
                self.assertTrue(status["signal_only_session_started"])
                self.assertEqual(status["governed_session_count"], 2)
                self.assertEqual(status["empirical_counts_source"], "durable")

                payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
            finally:
                reset_local_state_for_tests()
                os.environ.pop("IMP_STATE_DIR", None)

        check = _durable_state_check(payload)
        self.assertTrue(check["passed"])
        self.assertIn("sessions=2", check["detail"])
        self.assertNotIn(
            "signal_only_session_requires_durable_state",
            payload["failed_check_ids"],
        )

    def test_signal_only_started_fails_without_durable_sessions(self) -> None:
        mocked_status = {
            "signal_only_session_started": True,
            "governed_session_count": 0,
            "empirical_lock_count": 0,
            "empirical_counts_source": "durable",
            "us_equity_rth_open": True,
        }
        with patch(
            "market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity.collect_ftep_campaign_status",
            return_value=mocked_status,
        ):
            payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
        check = _durable_state_check(payload)
        self.assertFalse(check["passed"])
        self.assertIn(
            "signal_only_session_requires_durable_state",
            payload["failed_check_ids"],
        )

    def test_signal_only_started_fails_when_persistence_unavailable(self) -> None:
        mocked_status = {
            "signal_only_session_started": True,
            "governed_session_count": 2,
            "empirical_lock_count": 0,
            "empirical_counts_source": "persistence_disabled",
            "us_equity_rth_open": True,
        }
        with patch(
            "market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity.collect_ftep_campaign_status",
            return_value=mocked_status,
        ):
            payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
        check = _durable_state_check(payload)
        self.assertFalse(check["passed"])

    def test_signal_only_started_fails_when_durable_counts_unavailable(self) -> None:
        mocked_status = {
            "signal_only_session_started": True,
            "governed_session_count": 2,
            "empirical_lock_count": 0,
            "empirical_counts_source": "unavailable",
            "us_equity_rth_open": True,
        }
        with patch(
            "market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity.collect_ftep_campaign_status",
            return_value=mocked_status,
        ):
            payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
        check = _durable_state_check(payload)
        self.assertFalse(check["passed"])

    def test_corrupted_persistence_store_fails_closed_before_started_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            corrupt_path = Path(tmp) / "imp-state.sqlite3"
            corrupt_path.write_bytes(b"not-a-sqlite-database")
            os.environ["IMP_STATE_DIR"] = tmp
            os.environ["IMP_PERSIST_STATE"] = "1"
            reset_local_state_for_tests()
            try:
                with self.assertRaises(Exception):
                    collect_ftep_campaign_status(REPO_ROOT, "FTEP-V1-002")
            finally:
                reset_local_state_for_tests()
                os.environ.pop("IMP_STATE_DIR", None)

    def test_wrong_campaign_sessions_do_not_satisfy_durable_state(self) -> None:
        manifest_v2 = load_activation_manifest("FTEP-V1-002")
        campaign_id_v2 = str(manifest_v2.campaign_id or "")
        manifest_v1 = load_activation_manifest("FTEP-V1-001")
        wrong_campaign_id = str(manifest_v1.campaign_id or "")
        self.assertNotEqual(campaign_id_v2, wrong_campaign_id)

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["IMP_STATE_DIR"] = tmp
            os.environ["IMP_PERSIST_STATE"] = "1"
            reset_local_state_for_tests()
            try:
                local = open_local_state(force=True)
                self.assertIsNotNone(local)
                _seed_v1_002_sessions(
                    local.connection,
                    campaign_id=campaign_id_v2,
                    session_ids=(RTH_BASELINE_SESSION_ID, RTH_AI_SESSION_ID),
                    campaign_id_override=wrong_campaign_id,
                )
                status = collect_ftep_campaign_status(REPO_ROOT, "FTEP-V1-002")
                self.assertEqual(status["governed_session_count"], 0)
                self.assertFalse(status["signal_only_session_started"])

                payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
            finally:
                reset_local_state_for_tests()
                os.environ.pop("IMP_STATE_DIR", None)

        check = _durable_state_check(payload)
        self.assertTrue(check["passed"])
        self.assertIn("signal_only_session_started=false", check["detail"])

    def test_wrong_campaign_sessions_fail_when_started_flag_set_without_v1_002_counts(
        self,
    ) -> None:
        manifest_v2 = load_activation_manifest("FTEP-V1-002")
        campaign_id_v2 = str(manifest_v2.campaign_id or "")
        manifest_v1 = load_activation_manifest("FTEP-V1-001")
        wrong_campaign_id = str(manifest_v1.campaign_id or "")

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["IMP_STATE_DIR"] = tmp
            os.environ["IMP_PERSIST_STATE"] = "1"
            reset_local_state_for_tests()
            try:
                local = open_local_state(force=True)
                self.assertIsNotNone(local)
                _seed_v1_002_sessions(
                    local.connection,
                    campaign_id=campaign_id_v2,
                    session_ids=(RTH_BASELINE_SESSION_ID, RTH_AI_SESSION_ID),
                    campaign_id_override=wrong_campaign_id,
                )
                status = collect_ftep_campaign_status(REPO_ROOT, "FTEP-V1-002")
                self.assertEqual(status["governed_session_count"], 0)
            finally:
                reset_local_state_for_tests()
                os.environ.pop("IMP_STATE_DIR", None)

        mocked_status = dict(status)
        mocked_status["signal_only_session_started"] = True
        with patch(
            "market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity.collect_ftep_campaign_status",
            return_value=mocked_status,
        ):
            payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
        check = _durable_state_check(payload)
        self.assertFalse(check["passed"])

    def test_signal_only_authorization_requirements_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["IMP_STATE_DIR"] = tmp
            os.environ["IMP_PERSIST_STATE"] = "1"
            reset_local_state_for_tests()
            try:
                baseline = collect_ftep_campaign_status(REPO_ROOT, "FTEP-V1-002")
                payload = collect_ftep_integrity_checks(REPO_ROOT, "FTEP-V1-002")
            finally:
                reset_local_state_for_tests()
                os.environ.pop("IMP_STATE_DIR", None)

        self.assertTrue(baseline["signal_only_authorized"])
        self.assertFalse(baseline["signal_only_session_started"])
        self.assertTrue(baseline["empirical_lock_authorized"])
        fabricated = next(
            item
            for item in payload["checks"]
            if item["check_id"] == "no_fabricated_empirical_locks"
        )
        self.assertTrue(fabricated["passed"])
        self.assertEqual(payload["disposition"], "PASS")

    def test_integrity_cli_module_runs(self) -> None:
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["IMP_PERSIST_STATE"] = "1"
            env["IMP_STATE_DIR"] = tmp
            result = subprocess.run(
                [
                    sys.executable,
                    str(root / "tools" / "ftep_integrity_check.py"),
                    "FTEP-V1-002",
                    "--json",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ftep_integrity_report", result.stdout)


if __name__ == "__main__":
    unittest.main()
