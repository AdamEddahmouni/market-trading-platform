"""Cross-account snapshot and cache isolation regression tests (TD-003)."""

from __future__ import annotations

import threading
import unittest

from market_platform_foundation.ui_api import canary_projections
from market_platform_foundation.ui_api.account_snapshot_cache import (
    AccountSnapshotCache,
    reset_account_snapshot_cache_for_tests,
)
from market_platform_foundation.operational_identity import derive_live_canary_identity


class AccountSnapshotCacheIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_account_snapshot_cache_for_tests()
        canary_projections.reset_operator_context_for_tests()

    def tearDown(self) -> None:
        reset_account_snapshot_cache_for_tests()
        canary_projections.reset_operator_context_for_tests()

    def test_live_canary_snapshots_differ_by_account(self) -> None:
        local = canary_projections.build_canary_snapshot_payload(account_id="fp-canary-local")
        alt = canary_projections.build_canary_snapshot_payload(account_id="fp-canary-alt")
        self.assertEqual(local["account_id"], "fp-canary-local")
        self.assertEqual(alt["account_id"], "fp-canary-alt")
        self.assertNotEqual(
            local["snapshot"]["broker_health"],
            alt["snapshot"]["broker_health"],
        )

    def test_unknown_account_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            canary_projections.build_canary_snapshot_payload(account_id="fp-unknown")

    def test_cache_entries_do_not_cross_accounts(self) -> None:
        cache = AccountSnapshotCache()
        identity_a = derive_live_canary_identity(account_ref="fp-canary-local", broker="tradier.paper")
        identity_b = derive_live_canary_identity(account_ref="fp-canary-alt", broker="tradier.paper")
        cache.put(identity_a, "canary.snapshot", {"balance": 100}, source_time_ns=1)
        cache.put(identity_b, "canary.snapshot", {"balance": 999}, source_time_ns=2)
        entry_a = cache.get(identity_a, "canary.snapshot")
        entry_b = cache.get(identity_b, "canary.snapshot")
        assert entry_a is not None and entry_b is not None
        self.assertEqual(entry_a.value["balance"], 100)
        self.assertEqual(entry_b.value["balance"], 999)

    def test_concurrent_refresh_per_account(self) -> None:
        cache = AccountSnapshotCache()
        identity_a = derive_live_canary_identity(account_ref="fp-canary-local", broker="tradier.paper")
        identity_b = derive_live_canary_identity(account_ref="fp-canary-alt", broker="tradier.paper")
        results: dict[str, int] = {}

        def refresh(identity, value: int) -> None:
            entry = cache.get_or_refresh(identity, "canary.snapshot", lambda: ({"v": value}, value))
            results[identity.account_id] = entry.value["v"]

        threads = [
            threading.Thread(target=refresh, args=(identity_a, 11)),
            threading.Thread(target=refresh, args=(identity_b, 22)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results["fp-canary-local"], 11)
        self.assertEqual(results["fp-canary-alt"], 22)


class CanaryReconciliationIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        canary_projections.reset_operator_context_for_tests()

    def tearDown(self) -> None:
        canary_projections.reset_operator_context_for_tests()

    def test_reconciliation_includes_operational_identity(self) -> None:
        payload = canary_projections.build_canary_reconciliation_payload(account_id="fp-canary-local")
        self.assertEqual(payload["operational_identity"]["mode"], "LIVE")
        self.assertEqual(payload["operational_identity"]["account_id"], "fp-canary-local")


if __name__ == "__main__":
    unittest.main()
