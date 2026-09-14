"""FTEP session-release operator CLI and binding release gates."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests" / "intelligence") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests" / "intelligence"))

from market_platform_foundation.intelligence.paper_forward_bridge import (  # noqa: E402
    ForwardTestService,
    create_forward_test_repository,
    seed_test_frozen_manifest,
)
from market_platform_foundation.intelligence.paper_forward_bridge.activation import (  # noqa: E402
    compute_manifest_fingerprint,
    load_activation_manifest,
)
from market_platform_foundation.intelligence.paper_forward_bridge.campaign_binding import (  # noqa: E402
    CampaignBindingState,
    get_active_binding,
)
from market_platform_foundation.local_state.startup import (  # noqa: E402
    open_local_state,
    reset_local_state_for_tests,
)
from forward_test_activation_support import (  # noqa: E402
    create_activated_session,
    enable_test_campaigns_root,
    seed_baseline_campaign,
)
from tools.ftep_session_release import (  # noqa: E402
    _repo_empirical_manifest_path,
    collect_session_release_gates,
    execute_governed_session_release,
    main as session_release_main,
)

T0 = 1_700_000_000_000_000_000
HOUR_NS = 3_600_000_000_000
V1_001_FROZEN_FINGERPRINT = (
    "69C36BA23813C009C27EE83924834D46F5804D0A0FA037E37ADB133F8BFEA99C"
)


class FtepSessionReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ["IMP_FORWARD_TEST_EVAL_FORCE"] = "1"
        self.campaigns_root = enable_test_campaigns_root(Path(self._tmp.name))
        seed_baseline_campaign(self.campaigns_root)
        reset_local_state_for_tests()

    def tearDown(self) -> None:
        reset_local_state_for_tests()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        os.environ.pop("IMP_FORWARD_TEST_EVAL_FORCE", None)
        self._tmp.cleanup()

    def _service(self) -> ForwardTestService:
        local = open_local_state(force=True)
        assert local is not None
        return ForwardTestService(create_forward_test_repository(connection=local.connection))

    def test_release_succeeds_and_clears_active_binding(self) -> None:
        evidence_path = ROOT / "artifacts/ftep-v1-001/governed-session-release-evidence.jsonl"
        prior_size = evidence_path.stat().st_size if evidence_path.exists() else 0
        service = self._service()
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR_NS,
            created_at_ns=T0,
        )
        manifest = load_activation_manifest("FTEP-V1-001", campaigns_root_override=self.campaigns_root)
        binding_fp = compute_manifest_fingerprint(manifest.raw)
        try:
            payload, exit_code = execute_governed_session_release(
                ROOT,
                "FTEP-V1-001",
                account_id="paper-a",
                session_id=session.session_id,
                campaign_id=str(manifest.campaign_id or ""),
                require_frozen_manifest_fingerprint=True,
            )
        finally:
            if evidence_path.exists():
                if prior_size == 0:
                    evidence_path.unlink()
                else:
                    evidence_path.write_bytes(evidence_path.read_bytes()[:prior_size])

        self.assertEqual(exit_code, 0)
        released = payload.get("binding_released")
        self.assertIsInstance(released, dict)
        assert isinstance(released, dict)
        self.assertEqual(released["campaign_state"], CampaignBindingState.RELEASED.value)
        local = open_local_state(force=True)
        assert local is not None
        self.assertIsNone(get_active_binding(local.connection, account_id="paper-a"))

    def test_unknown_session_id_refused(self) -> None:
        service = self._service()
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR_NS,
            created_at_ns=T0,
        )
        self.assertIsNotNone(session.session_id)
        payload, exit_code = execute_governed_session_release(
            ROOT,
            "FTEP-V1-001",
            account_id="paper-a",
            session_id="fts-NOT-A-REAL-SESSION",
            require_frozen_manifest_fingerprint=True,
        )
        self.assertEqual(exit_code, 1)
        self.assertIn("SESSION_ID_MISMATCH", payload["blockers"])
        local = open_local_state(force=True)
        assert local is not None
        active = get_active_binding(local.connection, account_id="paper-a")
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.campaign_state, CampaignBindingState.ACTIVE)

    def test_expect_manifest_fingerprint_mismatch_refused(self) -> None:
        service = self._service()
        create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR_NS,
            created_at_ns=T0,
        )
        payload = collect_session_release_gates(
            ROOT,
            "FTEP-V1-001",
            account_id="paper-a",
            expect_manifest_fingerprint=V1_001_FROZEN_FINGERPRINT,
            require_persistence=True,
        )
        self.assertFalse(payload["would_release_binding"])
        self.assertIn("MANIFEST_FINGERPRINT_MISMATCH", payload["blockers"])

    def test_v1_001_frozen_fingerprint_unchanged(self) -> None:
        manifest_path = ROOT / "artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json"
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(raw["fingerprint"], V1_001_FROZEN_FINGERPRINT)
        self.assertEqual(raw["manifest_fingerprint"], V1_001_FROZEN_FINGERPRINT)

    def test_execute_without_explicit_guard_refused(self) -> None:
        service = self._service()
        create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR_NS,
            created_at_ns=T0,
        )
        payload, exit_code = execute_governed_session_release(
            ROOT,
            "FTEP-V1-001",
            account_id="paper-a",
        )
        self.assertEqual(exit_code, 1)
        self.assertIn("RELEASE_GUARD_REQUIRED", payload["blockers"])
        local = open_local_state(force=True)
        assert local is not None
        active = get_active_binding(local.connection, account_id="paper-a")
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.campaign_state, CampaignBindingState.ACTIVE)

    def test_no_active_binding(self) -> None:
        payload = collect_session_release_gates(
            ROOT,
            "FTEP-V1-001",
            account_id="paper-a",
            require_persistence=True,
            require_frozen_manifest_fingerprint=True,
        )
        self.assertFalse(payload["would_release_binding"])
        self.assertIn("NO_ACTIVE_BINDING", payload["blockers"])

    def test_frozen_guard_happy_path_dry_run(self) -> None:
        service = self._service()
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR_NS,
            created_at_ns=T0,
        )
        payload = collect_session_release_gates(
            ROOT,
            "FTEP-V1-001",
            account_id="paper-a",
            session_id=session.session_id,
            require_frozen_manifest_fingerprint=True,
            require_persistence=True,
        )
        self.assertTrue(payload["would_release_binding"])
        self.assertEqual(payload["blockers"], [])

    def test_dry_run_leaves_active_binding_and_evidence_unchanged(self) -> None:
        evidence_path = ROOT / "artifacts/ftep-v1-001/governed-session-release-evidence.jsonl"
        prior_size = evidence_path.stat().st_size if evidence_path.exists() else 0
        service = self._service()
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR_NS,
            created_at_ns=T0,
        )
        exit_code = session_release_main(
            [
                "FTEP-V1-001",
                "--account-id",
                "paper-a",
                "--session-id",
                session.session_id,
                "--require-frozen-manifest-fingerprint",
                "--dry-run",
                "--json",
            ]
        )
        self.assertEqual(exit_code, 0)
        local = open_local_state(force=True)
        assert local is not None
        active = get_active_binding(local.connection, account_id="paper-a")
        self.assertIsNotNone(active)
        assert active is not None
        self.assertEqual(active.campaign_state, CampaignBindingState.ACTIVE)
        if evidence_path.exists():
            self.assertEqual(evidence_path.stat().st_size, prior_size)

    def test_campaign_slug_mismatch_refused(self) -> None:
        seed_test_frozen_manifest(self.campaigns_root, campaign_slug="FTEP-V1-002")
        service = self._service()
        create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR_NS,
            created_at_ns=T0,
        )
        payload = collect_session_release_gates(
            ROOT,
            "FTEP-V1-002",
            account_id="paper-a",
            require_frozen_manifest_fingerprint=True,
            require_persistence=True,
        )
        self.assertFalse(payload["would_release_binding"])
        self.assertIn("CAMPAIGN_SLUG_MISMATCH", payload["blockers"])

    def test_repo_empirical_manifest_path_detected(self) -> None:
        repo_manifest = ROOT / "artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json"
        self.assertTrue(_repo_empirical_manifest_path(ROOT, str(repo_manifest)))


if __name__ == "__main__":
    unittest.main()
