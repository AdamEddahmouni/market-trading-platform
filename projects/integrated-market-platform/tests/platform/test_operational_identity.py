"""Tests for canonical operational identity (TD-003)."""

from __future__ import annotations

import unittest

from market_platform_foundation.operational_identity import (
    OperationalIdentity,
    OperationalIdentityError,
    attach_operational_identity,
    derive_demo_identity,
    derive_live_canary_identity,
    derive_paper_identity,
    parse_operational_identity,
)


class OperationalIdentityTests(unittest.TestCase):
    def test_paper_and_demo_identities_differ_for_same_ledger(self) -> None:
        paper = derive_paper_identity(
            paper_account_id="acct-123",
            execution_provider="INTERNAL",
            data_mode="FIXTURE_REPLAY",
        )
        demo = derive_demo_identity(paper_account_id="acct-123", data_mode="FIXTURE_REPLAY")
        self.assertEqual(paper.mode, "PAPER")
        self.assertEqual(demo.mode, "DEMO")
        self.assertNotEqual(paper.account_id, demo.account_id)
        self.assertNotEqual(paper.cache_key("portfolio"), demo.cache_key("portfolio"))

    def test_live_accounts_have_distinct_cache_keys(self) -> None:
        account_a = derive_live_canary_identity(account_ref="fp-canary-local", broker="tradier.paper")
        account_b = derive_live_canary_identity(account_ref="fp-canary-alt", broker="tradier.paper")
        self.assertNotEqual(account_a.cache_key("canary.snapshot"), account_b.cache_key("canary.snapshot"))

    def test_invalid_account_id_rejected(self) -> None:
        with self.assertRaises(OperationalIdentityError):
            OperationalIdentity(mode="PAPER", broker="internal.simulation", account_id="")

    def test_parse_requires_account_id(self) -> None:
        with self.assertRaises(OperationalIdentityError):
            parse_operational_identity(mode="LIVE", broker="tradier.paper", account_id=None)

    def test_attach_operational_identity(self) -> None:
        identity = derive_live_canary_identity(account_ref="fp-canary-local", broker="tradier.paper")
        payload = attach_operational_identity({"snapshot": {}}, identity)
        self.assertEqual(payload["operational_identity"]["account_id"], "fp-canary-local")


if __name__ == "__main__":
    unittest.main()
