"""FTEP-V1 activation manifest and preflight tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge.activation import (  # noqa: E402
    ActivationManifest,
    ActivationManifestError,
    compute_manifest_fingerprint,
    derive_campaign_id,
    freeze_manifest,
    load_activation_manifest,
    normalize_manifest,
    write_activation_manifest,
)
from market_platform_foundation.intelligence.paper_forward_bridge.protocol_ref import (  # noqa: E402
    ProtocolRefError,
    write_test_protocol_ref,
)
from market_platform_foundation.intelligence.paper_forward_bridge.preflight import (  # noqa: E402
    PreflightDisposition,
    assert_forward_test_preflight_ready,
    run_forward_test_preflight,
)
from market_platform_foundation.intelligence.paper_forward_bridge import (  # noqa: E402
    ForwardTestMode,
    ForwardTestService,
    ForwardTestServiceError,
    ForwardTestStore,
)
from market_platform_foundation.intelligence.paper_forward_bridge.protocol_ref import (  # noqa: E402
    write_test_protocol_ref,
)
from market_platform_foundation.intelligence.paper_forward_bridge.types import (  # noqa: E402
    ForwardTestCohortArm,
)

HOUR = 3_600_000_000_000
T0 = 1_700_000_000_000_000_000


def _base_manifest_dict(
    *,
    campaign_slug: str = "test-campaign",
    activation_status: str = "PENDING_OWNER_DECISIONS",
    baseline_policy_id: str = "s1@1.0.0",
    ai_policy_id: str = "s2@1.0.0",
    universe: list[str] | None = None,
    horizons_ns: list[int] | None = None,
) -> dict:
    return {
        "manifest_schema_version": 1,
        "campaign_slug": campaign_slug,
        "campaign_id": None,
        "protocol_id": "FTEP-V1/0.1.0-PREREG",
        "activation_status": activation_status,
        "owner_decisions_required": ["FTEP-OD-01"],
        "unresolved_fields": ["FTEP-OD-01"],
        "recommended_not_binding": {
            "universe": universe or ["ACME"],
            "baseline_policy_id": baseline_policy_id,
            "ai_policy_id": ai_policy_id,
        },
        "horizons_ns": horizons_ns or [HOUR],
        "resolved_fields": {
            "FTEP-ACT-05": {"resolution": "IMP_PERSIST_STATE_REQUIRED"},
        },
        "safety_constraints": {
            "mode": "INTERNAL_SIMULATION",
            "live_execution": False,
            "cost_usd": 0,
        },
    }


def _install_manifest(tmp_dir: str, manifest: dict) -> str:
    slug = str(manifest["campaign_slug"])
    root = Path(tmp_dir)
    write_test_protocol_ref(root, campaign_slug=slug)
    path = root / slug / "ACTIVATION_MANIFEST.json"
    write_activation_manifest(path, manifest, campaigns_root_override=root)
    return slug


def _frozen_manifest(
    tmp_dir: str,
    *,
    campaign_slug: str = "test-campaign",
    baseline_policy_id: str = "s1@1.0.0",
    universe: list[str] | None = None,
) -> tuple[str, dict]:
    manifest = _base_manifest_dict(
        campaign_slug=campaign_slug,
        activation_status="PENDING_OWNER_DECISIONS",
        baseline_policy_id=baseline_policy_id,
        universe=universe,
    )
    manifest["owner_decisions_required"] = []
    manifest["unresolved_fields"] = []
    slug = _install_manifest(tmp_dir, manifest)
    loaded = load_activation_manifest(slug, campaigns_root_override=Path(tmp_dir))
    frozen = freeze_manifest(loaded, frozen_at="2026-09-10T00:00:00Z")
    write_activation_manifest(
        Path(tmp_dir) / slug / "ACTIVATION_MANIFEST.json",
        frozen,
        campaigns_root_override=Path(tmp_dir),
    )
    return slug, frozen


class ForwardTestActivationManifestTests(unittest.TestCase):
    def test_manifest_fingerprint_is_uppercase_sha256(self) -> None:
        manifest = _base_manifest_dict()
        fingerprint = compute_manifest_fingerprint(manifest)
        self.assertEqual(len(fingerprint), 64)
        self.assertEqual(fingerprint, fingerprint.upper())

    def test_derive_campaign_id_from_fingerprint(self) -> None:
        manifest = _base_manifest_dict()
        fingerprint = compute_manifest_fingerprint(manifest)
        campaign_id = derive_campaign_id(manifest)
        self.assertEqual(campaign_id, f"FTCAMP-{fingerprint.lower()}")

    def test_pending_manifest_campaign_id_may_be_null(self) -> None:
        manifest = ActivationManifest(
            raw=normalize_manifest(_base_manifest_dict()),
            path=Path("pending.json"),
        )
        self.assertIsNone(manifest.campaign_id)
        self.assertEqual(manifest.status.value, "PENDING_OWNER_DECISIONS")
        self.assertIn("ACME", manifest.binding["universe"]["symbols"])


class ForwardTestActivationPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_FORWARD_TEST_CAMPAIGNS_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        self._tmp.cleanup()

    def test_pending_manifest_blocks_preflight(self) -> None:
        slug = _install_manifest(self._tmp.name, _base_manifest_dict())
        result = run_forward_test_preflight(campaign_slug=slug, mode="PAPER")
        self.assertEqual(result.disposition, PreflightDisposition.NOT_READY)
        self.assertIn("ACTIVATION_MANIFEST_PENDING_OWNER_DECISIONS", result.blockers)
        with self.assertRaises(ActivationManifestError):
            assert_forward_test_preflight_ready(result)

    def test_frozen_manifest_allows_preflight(self) -> None:
        slug, manifest = _frozen_manifest(self._tmp.name)
        result = run_forward_test_preflight(
            campaign_slug=slug,
            mode="PAPER",
            cohort_arm="BASELINE",
        )
        self.assertEqual(result.disposition, PreflightDisposition.READY)
        self.assertEqual(
            result.manifest_fingerprint,
            manifest["manifest_fingerprint"],
        )
        assert_forward_test_preflight_ready(result)

    def test_agent_a_skeleton_loads_without_binding_block(self) -> None:
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        skeleton_path = ROOT / "artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json"
        loaded = json.loads(skeleton_path.read_text(encoding="utf-8"))
        manifest = load_activation_manifest("FTEP-V1-001")
        self.assertEqual(manifest.protocol_id, loaded["protocol_id"])
        self.assertIsNone(manifest.campaign_id)
        self.assertEqual(manifest.binding["run_kind"], "FORWARD_TEST")


class ForwardTestActivationRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_FORWARD_TEST_CAMPAIGNS_DIR"] = self._tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ["IMP_FORWARD_TEST_EVAL_FORCE"] = "1"
        self.store = ForwardTestStore()
        self.service = ForwardTestService(self.store)

    def tearDown(self) -> None:
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_FORWARD_TEST_EVAL_FORCE", None)
        self._tmp.cleanup()

    def test_create_session_requires_frozen_manifest(self) -> None:
        slug = _install_manifest(self._tmp.name, _base_manifest_dict())
        with self.assertRaises(ForwardTestServiceError) as ctx:
            self.service.create_session(
                account_id="paper-a",
                mode="PAPER",
                strategy_id="s1",
                strategy_version="1.0.0",
                universe=("ACME",),
                evaluation_horizon_ns=HOUR,
                created_at_ns=T0,
                campaign_id=slug,
                cohort_arm="BASELINE",
            )
        self.assertIn("ACTIVATION_MANIFEST_PENDING_OWNER_DECISIONS", str(ctx.exception))

    def test_frozen_manifest_allows_session_and_lock(self) -> None:
        slug, _manifest = _frozen_manifest(self._tmp.name)
        session = self.service.create_session(
            account_id="paper-a",
            mode="PAPER",
            strategy_id="s1",
            strategy_version="1.0.0",
            universe=("ACME",),
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
            campaign_id=slug,
            cohort_arm="BASELINE",
        )
        self.assertTrue(session.campaign_id)
        self.assertEqual(session.protocol_id, "FTEP-V1/0.1.0-PREREG")
        self.assertEqual(session.cohort_arm, ForwardTestCohortArm.BASELINE)
        decision = self.service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=session.session_id,
            symbol="ACME",
            direction="BUY",
            decision_time_ns=T0,
            source_time_ns=T0 - 1,
            strategy_id="s1",
            strategy_version="1.0.0",
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        locked = self.service.lock_decision(
            forward_test_id=decision.forward_test_id,
            account_id="paper-a",
            locked_at_ns=T0,
        )
        self.assertTrue(locked.state.value == "LOCKED")

    def test_decision_provenance_includes_manifest_fingerprint(self) -> None:
        slug, manifest = _frozen_manifest(self._tmp.name)
        session = self.service.create_session(
            account_id="paper-a",
            mode="PAPER",
            strategy_id="s1",
            strategy_version="1.0.0",
            universe=("ACME",),
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
            campaign_id=slug,
            cohort_arm="BASELINE",
        )
        decision = self.service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=session.session_id,
            symbol="ACME",
            direction="BUY",
            decision_time_ns=T0,
            source_time_ns=T0 - 1,
            strategy_id="s1",
            strategy_version="1.0.0",
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        self.assertEqual(
            decision.provenance_snapshot["manifest_fingerprint"],
            manifest["manifest_fingerprint"],
        )
        self.assertEqual(decision.provenance_snapshot["campaign_slug"], slug)
        self.assertEqual(
            decision.provenance_snapshot["campaign_id"],
            manifest["campaign_id"],
        )

    def test_concurrent_campaign_blocked_on_second_session(self) -> None:
        slug, _manifest = _frozen_manifest(self._tmp.name, campaign_slug="campaign-a")
        _frozen_manifest(self._tmp.name, campaign_slug="campaign-b")
        self.service.create_session(
            account_id="paper-a",
            mode="PAPER",
            strategy_id="s1",
            strategy_version="1.0.0",
            universe=("ACME",),
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
            campaign_id="campaign-a",
            cohort_arm="BASELINE",
        )
        with self.assertRaises(ForwardTestServiceError) as ctx:
            self.service.create_session(
                account_id="paper-a",
                mode="PAPER",
                strategy_id="s1",
                strategy_version="1.0.0",
                universe=("ACME",),
                evaluation_horizon_ns=HOUR,
                created_at_ns=T0 + 1,
                campaign_id="campaign-b",
                cohort_arm="BASELINE",
            )
        self.assertIn("FORWARD_TEST_CONCURRENT_CAMPAIGN_ACTIVE", str(ctx.exception))

    def test_protocol_ref_hash_mismatch_blocks_preflight(self) -> None:
        slug = _install_manifest(self._tmp.name, _base_manifest_dict())
        ref_path = Path(self._tmp.name) / slug / "PROTOCOL_REF.json"
        ref = json.loads(ref_path.read_text(encoding="utf-8"))
        ref["protocol_doc_sha256"] = "0" * 64
        ref["sha256"] = "0" * 64
        ref_path.write_text(json.dumps(ref, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = run_forward_test_preflight(campaign_slug=slug, mode="PAPER")
        self.assertEqual(result.disposition, PreflightDisposition.NOT_READY)
        self.assertIn("PROTOCOL_REF_DOC_SHA256_MISMATCH", result.blockers)


if __name__ == "__main__":
    unittest.main()
