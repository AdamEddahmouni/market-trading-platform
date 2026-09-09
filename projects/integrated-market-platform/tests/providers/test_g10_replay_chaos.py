"""G10 deterministic offline failure/recovery scenarios."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.providers.ibkr_observational.constants import (
    ERROR_CODE_1100_CONNECTIVITY_LOST,
    ERROR_CODE_1101_RESTORED_DATA_LOST,
    ERROR_CODE_354_NOT_SUBSCRIBED,
)
from market_platform_foundation.providers.ibkr_observational.contracts import (
    EntitlementState,
    IbkrConnectionState,
)

from ibkr_observational_support import FakeLookup, connected_adapter, make_adapter, make_record


AAPL = make_record("AAPL")


class G10ReplayChaosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter, self.transport = connected_adapter(lookup=FakeLookup(AAPL))

    def test_a_provider_starts_unavailable(self) -> None:
        adapter, _transport = make_adapter(lookup=FakeLookup(AAPL))
        self.assertEqual(
            adapter.diagnostics()["connection_state"],
            IbkrConnectionState.DISCONNECTED.value,
        )

    def test_b_connect_succeeds(self) -> None:
        self.adapter.connect()
        self.assertTrue(self.transport.connected)

    def test_c_subscription_succeeds(self) -> None:
        self.adapter.connect()
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.assertTrue(sub.accepted)

    def test_d_entitlement_denied(self) -> None:
        self.adapter.connect()
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.adapter.on_error(sub.req_id, ERROR_CODE_354_NOT_SUBSCRIBED, "denied")
        record = self.adapter.subscription_status()[sub.subscription_id]
        self.assertEqual(record["entitlement"], EntitlementState.NOT_ENTITLED.value)

    def test_f_connection_lost(self) -> None:
        self.adapter.connect()
        self.adapter.on_error(-1, ERROR_CODE_1100_CONNECTIVITY_LOST, "lost")
        self.assertEqual(
            self.adapter.diagnostics()["connection_state"],
            IbkrConnectionState.DISCONNECTED.value,
        )

    def test_g_connection_restored_data_lost(self) -> None:
        self.adapter.connect()
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.adapter.on_error(-1, ERROR_CODE_1100_CONNECTIVITY_LOST, "lost")
        self.adapter.on_error(-1, ERROR_CODE_1101_RESTORED_DATA_LOST, "restored")
        self.adapter.handle_reconnect()
        status = self.adapter.subscription_status()
        self.assertTrue(status)
        self.assertNotIn(sub.subscription_id, status)
        self.assertTrue(any(row.get("capability") == "L2" for row in status.values()))

    def test_o_repeated_shutdown(self) -> None:
        self.adapter.connect()
        self.adapter.subscribe_l1(instrument_id="AAPL")
        self.adapter.shutdown()
        self.adapter.shutdown()
        self.assertEqual(self.adapter.callback_metrics()["callbacks_processed"], 0)


if __name__ == "__main__":
    unittest.main()
