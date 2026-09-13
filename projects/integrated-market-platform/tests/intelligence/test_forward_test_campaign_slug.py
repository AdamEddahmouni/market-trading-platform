"""CG-01/CG-02 forward-test bridge regression tests."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge import (  # noqa: E402
    ForwardTestMode,
    ForwardTestService,
    ForwardTestServiceError,
    ForwardTestStore,
)
from market_platform_foundation.intelligence.paper_forward_bridge.activation import (  # noqa: E402
    derive_campaign_id,
)
from dataclasses import replace

from market_platform_foundation.intelligence.paper_forward_bridge.types import (  # noqa: E402
    ForwardTestState,
)
from tests.intelligence.test_forward_test_activation import (  # noqa: E402
    HOUR,
    T0,
    _frozen_manifest,
)


class ForwardTestCampaignSlugTests(unittest.TestCase):
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

    def test_ftcamp_hash_session_reloads_manifest_by_slug(self) -> None:
        slug, manifest = _frozen_manifest(self._tmp.name)
        derived_id = derive_campaign_id(manifest)
        session = self.service.create_session(
            account_id="paper-a",
            mode="PAPER",
            strategy_id="s1",
            strategy_version="1.0.0",
            universe=("ACME",),
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
            campaign_id=derived_id,
            campaign_slug=slug,
            cohort_arm="BASELINE",
        )
        self.assertEqual(session.campaign_id, derived_id)
        self.assertEqual(session.config.get("campaign_slug"), slug)
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
        self.assertEqual(locked.state, ForwardTestState.LOCKED)
        provenance = locked.provenance_snapshot
        self.assertEqual(provenance.get("campaign_slug"), slug)
        self.assertEqual(provenance.get("campaign_id"), derived_id)

    def test_missing_slug_with_ftcamp_hash_fails_closed(self) -> None:
        slug, manifest = _frozen_manifest(self._tmp.name)
        derived_id = derive_campaign_id(manifest)
        session = self.service.create_session(
            account_id="paper-b",
            mode="PAPER",
            strategy_id="s1",
            strategy_version="1.0.0",
            universe=("ACME",),
            evaluation_horizon_ns=HOUR,
            created_at_ns=T0,
            campaign_id=derived_id,
            campaign_slug=slug,
            cohort_arm="BASELINE",
        )
        broken = replace(session, config={})
        self.store.put_session(broken)
        with self.assertRaises(ForwardTestServiceError) as ctx:
            self.service.create_decision(
                account_id="paper-b",
                mode="PAPER",
                session_id=broken.session_id,
                symbol="ACME",
                direction="BUY",
                decision_time_ns=T0,
                source_time_ns=T0 - 1,
                strategy_id="s1",
                strategy_version="1.0.0",
                test_mode=ForwardTestMode.SIGNAL_ONLY,
            )
        self.assertIn("FORWARD_TEST_CAMPAIGN_SLUG_REQUIRED", str(ctx.exception))

    def test_lock_persists_sample_floor_disposition(self) -> None:
        slug, _manifest = _frozen_manifest(self._tmp.name)
        session = self.service.create_session(
            account_id="paper-c",
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
            account_id="paper-c",
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
        self.service.lock_decision(
            forward_test_id=decision.forward_test_id,
            account_id="paper-c",
            locked_at_ns=T0,
        )
        summary = self.service.get_session_summary(
            session_id=session.session_id,
            account_id="paper-c",
        )
        disposition = summary.get("sample_floor_disposition")
        self.assertIsInstance(disposition, dict)
        self.assertIn("statistical_disposition_ready", disposition)
        self.assertFalse(disposition["statistical_disposition_ready"])


if __name__ == "__main__":
    unittest.main()
