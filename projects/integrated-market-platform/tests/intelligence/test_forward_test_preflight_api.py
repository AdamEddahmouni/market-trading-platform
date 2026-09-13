"""Preflight HTTP projection tests for Paper forward-testing bridge."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "intelligence"))

from market_platform_foundation.intelligence.paper_forward_bridge.activation import (  # noqa: E402
    normalize_manifest,
    write_activation_manifest,
)
from market_platform_foundation.intelligence.paper_forward_bridge.preflight import (  # noqa: E402
    PreflightDisposition,
)
from market_platform_foundation.intelligence.paper_forward_bridge.protocol_ref import (  # noqa: E402
    write_test_protocol_ref,
)
from market_platform_foundation.ui_api.forward_test_projections import (  # noqa: E402
    build_forward_test_preflight_payload,
)
from market_platform_foundation.ui_api.paper_projections import open_paper_session  # noqa: E402
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402
from forward_test_activation_support import (  # noqa: E402
    CAMPAIGN_SLUG,
    enable_test_campaigns_root,
    seed_baseline_campaign,
)


class ForwardTestPreflightApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_PERSIST_STATE"] = "1"
        self.campaigns_root = enable_test_campaigns_root(Path(self._tmp.name))
        fixture_root = ROOT.parent
        self.store = ReplayStore(collection_root=fixture_root)
        self.store.load()
        open_paper_session(self.store, {"execution_mode": "INTERNAL_SIMULATION"})
        self.account_id = self.store.paper_ledger.paper_account_id
        seed_baseline_campaign(self.campaigns_root, paper_account_id=self.account_id)

    def tearDown(self) -> None:
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        self._tmp.cleanup()

    def test_preflight_ready_payload(self) -> None:
        payload = build_forward_test_preflight_payload(
            self.store,
            account_id=self.account_id,
            campaign_slug=CAMPAIGN_SLUG,
            cohort_arm="BASELINE",
        )
        preflight = payload["preflight"]
        self.assertEqual(preflight["disposition"], PreflightDisposition.READY.value)
        self.assertEqual(preflight["blockers"], [])
        self.assertTrue(preflight["manifest_fingerprint"])

    def test_preflight_requires_campaign_slug(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_forward_test_preflight_payload(
                self.store,
                account_id=self.account_id,
                campaign_slug="",
            )
        self.assertIn("FORWARD_TEST_CAMPAIGN_ID_REQUIRED", str(ctx.exception))

    def test_pending_manifest_preflight_not_ready_via_api(self) -> None:
        manifest = {
            "manifest_schema_version": 1,
            "campaign_slug": CAMPAIGN_SLUG,
            "protocol_id": "FTEP-V1/0.1.0-PREREG",
            "activation_status": "PENDING_OWNER_DECISIONS",
            "owner_decisions_required": ["FTEP-OD-01"],
            "recommended_not_binding": {
                "universe": ["ACME"],
                "baseline_policy_id": "news_deterministic_baseline@1.0.0",
                "ai_policy_id": "news_ai_enhanced@1.0.0",
            },
            "horizons_ns": [3_600_000_000_000],
            "safety_constraints": {
                "mode": "INTERNAL_SIMULATION",
                "live_execution": False,
                "cost_usd": 0,
            },
        }
        write_test_protocol_ref(self.campaigns_root, campaign_slug=CAMPAIGN_SLUG)
        write_activation_manifest(
            self.campaigns_root / CAMPAIGN_SLUG / "ACTIVATION_MANIFEST.json",
            normalize_manifest(manifest),
        )
        payload = build_forward_test_preflight_payload(
            self.store,
            account_id=self.account_id,
            campaign_slug=CAMPAIGN_SLUG,
        )
        preflight = payload["preflight"]
        self.assertEqual(preflight["disposition"], PreflightDisposition.NOT_READY.value)
        self.assertIn("ACTIVATION_MANIFEST_PENDING_OWNER_DECISIONS", preflight["blockers"])


if __name__ == "__main__":
    unittest.main()
