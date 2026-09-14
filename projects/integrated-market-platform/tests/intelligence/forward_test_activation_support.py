"""Shared helpers for forward-test activation in unit tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.intelligence.paper_forward_bridge import (
    ForwardTestService,
    seed_test_frozen_manifest,
)

CAMPAIGN_SLUG = "FTEP-V1-001"
BASELINE_POLICY = "news_deterministic_baseline"
POLICY_VERSION = "1.0.0"
HOUR_NS = 3_600_000_000_000


def enable_test_campaigns_root(root: Path) -> Path:
    campaigns_root = root / "forward-test-campaigns"
    campaigns_root.mkdir(parents=True, exist_ok=True)
    os.environ["IMP_FORWARD_TEST_CAMPAIGNS_DIR"] = str(campaigns_root)
    return campaigns_root


def seed_baseline_campaign(
    campaigns_root: Path,
    *,
    paper_account_id: str = "paper-a",
    universe_symbols: tuple[str, ...] = ("ACME", "ES"),
) -> None:
    seed_test_frozen_manifest(
        campaigns_root,
        campaign_slug=CAMPAIGN_SLUG,
        paper_account_id=paper_account_id,
        universe_symbols=universe_symbols,
        evaluation_horizon_ns=HOUR_NS,
    )


class ActivatedForwardTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from market_platform_foundation.local_state.startup import reset_local_state_for_tests

        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        self.campaigns_root = enable_test_campaigns_root(Path(self._tmp.name))
        seed_baseline_campaign(self.campaigns_root)
        os.environ["IMP_FORWARD_TEST_EVAL_FORCE"] = "1"
        reset_local_state_for_tests()

    def tearDown(self) -> None:
        from market_platform_foundation.local_state.startup import reset_local_state_for_tests

        reset_local_state_for_tests()
        os.environ.pop("IMP_STATE_DIR", None)
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        os.environ.pop("IMP_FORWARD_TEST_EVAL_FORCE", None)
        self._tmp.cleanup()


def create_activated_session(
    service: ForwardTestService,
    campaigns_root: Path,
    *,
    account_id: str = "paper-a",
    universe: tuple[str, ...] = ("ACME",),
    evaluation_horizon_ns: int,
    created_at_ns: int,
) -> object:
    return service.create_session(
        account_id=account_id,
        mode="PAPER",
        strategy_id=BASELINE_POLICY,
        strategy_version=POLICY_VERSION,
        universe=universe,
        evaluation_horizon_ns=evaluation_horizon_ns,
        created_at_ns=created_at_ns,
        campaign_id=CAMPAIGN_SLUG,
        cohort_arm="BASELINE",
        campaigns_root_override=campaigns_root,
    )
