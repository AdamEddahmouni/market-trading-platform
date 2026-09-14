"""Non-semantic FTEP contracts: identity, provenance, readiness fail-closed.

Does not mutate FTEP-V1-002 artifacts. Does not declare EMPIRICAL_ACTIVE.
"""

from __future__ import annotations

import hashlib
import os
import unittest
from pathlib import Path
from unittest.mock import Mock

from market_platform_foundation.intelligence.paper_forward_bridge.campaign_readiness import (
    CampaignReadinessDisposition,
    CampaignReadinessResult,
    assert_campaign_readiness_ready,
    evaluate_campaign_readiness,
)
from market_platform_foundation.intelligence.paper_forward_bridge.identity import (
    forward_test_decision_id,
    forward_test_observation_id,
    forward_test_session_id,
)
from market_platform_foundation.intelligence.paper_forward_bridge.paper_ledger_join import (
    paper_execution_from_ledger,
    paper_execution_from_observations,
)
from market_platform_foundation.intelligence.paper_forward_bridge.run_identity import (
    run_identity,
    stamp_provenance,
)

ROOT = Path(__file__).resolve().parents[2]
V1_002_MANIFEST = ROOT / "artifacts/forward-test-campaigns/FTEP-V1-002/ACTIVATION_MANIFEST.json"


class FtepIdentityAndProvenanceTests(unittest.TestCase):
    def test_identity_prefixes_are_deterministic(self) -> None:
        first = forward_test_session_id(
            account_id="acct-1",
            strategy_id="strat",
            strategy_version="1",
            created_at_ns=1_000,
            universe=("AAPL", "MSFT"),
        )
        second = forward_test_session_id(
            account_id="acct-1",
            strategy_id="strat",
            strategy_version="1",
            created_at_ns=1_000,
            universe=("AAPL", "MSFT"),
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("fts-"))
        decision = forward_test_decision_id(
            account_id="acct-1",
            session_id=first,
            symbol="AAPL",
            decision_time_ns=2_000,
            strategy_id="strat",
            strategy_version="1",
            direction="LONG",
        )
        self.assertTrue(decision.startswith("ftd-"))
        observation = forward_test_observation_id(
            forward_test_id=decision,
            observed_at_ns=3_000,
            source_time_ns=2_000,
        )
        self.assertTrue(observation.startswith("fto-"))

    def test_run_identity_is_software_provenance_not_empirical(self) -> None:
        identity = run_identity()
        self.assertIn("git_sha", identity)
        self.assertIn("simulator_version", identity)
        self.assertNotIn("empirical_active", identity)
        self.assertNotIn("calibrated", identity)
        stamped = stamp_provenance({"git_sha": "KEEP-ME", "extra": "1"})
        self.assertEqual(stamped["git_sha"], "KEEP-ME")
        self.assertEqual(stamped["extra"], "1")
        self.assertIn("simulator_version", stamped)


class FtepReadinessFailClosedTests(unittest.TestCase):
    def test_assert_campaign_readiness_ready_fails_closed(self) -> None:
        result = CampaignReadinessResult(
            disposition=CampaignReadinessDisposition.NOT_READY,
            blockers=("COVERAGE_GAP:CAP-REQ-futures.es_quote.moomoo",),
            warnings=(),
            campaign_slug="FTEP-V1-001",
            preflight=Mock(),
            coverage_gaps=Mock(),
            metadata={},
        )
        with self.assertRaises(ValueError) as ctx:
            assert_campaign_readiness_ready(result)
        self.assertIn("CAMPAIGN_READINESS_FAILED:", str(ctx.exception))
        self.assertIn("COVERAGE_GAP:CAP-REQ-futures.es_quote.moomoo", str(ctx.exception))

    def test_v1_002_readiness_does_not_mutate_activation_manifest(self) -> None:
        before = hashlib.sha256(V1_002_MANIFEST.read_bytes()).hexdigest()
        os.environ["IMP_PERSIST_STATE"] = "1"
        try:
            evaluate_campaign_readiness(
                "FTEP-V1-002",
                repository_root=ROOT,
                readiness_report={"providers": []},
            )
        finally:
            os.environ.pop("IMP_PERSIST_STATE", None)
        after = hashlib.sha256(V1_002_MANIFEST.read_bytes()).hexdigest()
        self.assertEqual(before, after)


class PaperLedgerJoinTests(unittest.TestCase):
    def test_missing_order_id_is_empty_not_fabricated(self) -> None:
        connection = Mock()
        realized, fill_count, unrealized = paper_execution_from_ledger(
            connection,
            paper_order_id=None,
        )
        self.assertIsNone(realized)
        self.assertEqual(fill_count, 0)
        self.assertIsNone(unrealized)
        connection.execute.assert_not_called()

    def test_observations_do_not_invent_fills(self) -> None:
        realized, fill_count = paper_execution_from_observations(())
        self.assertIsNone(realized)
        self.assertEqual(fill_count, 0)
        realized, fill_count = paper_execution_from_observations(
            ({"realized_pnl_minor": 12, "fill_count": 2},)
        )
        self.assertEqual(realized, 12)
        self.assertEqual(fill_count, 2)


if __name__ == "__main__":
    unittest.main()
