"""IBKR observational safety boundary tests (G6 §6, §20, §28).

Proves the adapter is incapable of providing trading authority: no execution
method exists on the public surface, the transport protocol is observational
only, execution capability is never registered, and offline mode prevents all
provider I/O.
"""

from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PACKAGE = ROOT / "src" / "market_platform_foundation" / "providers" / "ibkr_observational"


class NoExecutionSurfaceTests(unittest.TestCase):
    def test_adapter_public_surface_has_no_execution_methods(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.adapter import (
            IbkrObservationalAdapter,
            IbkrTransport,
        )

        forbidden = (
            "placeOrder",
            "modifyOrder",
            "cancelOrder",
            "exerciseOptions",
            "reqFundTransfer",
            "place_order",
            "modify_order",
            "cancel_order",
        )
        forbidden_set = set(forbidden)
        for cls in (IbkrObservationalAdapter, IbkrTransport):
            members = {name for name in dir(cls)}
            self.assertTrue(
                members.isdisjoint(forbidden_set),
                f"{cls.__name__}: {members & forbidden_set}",
            )

    def test_adapter_authorized_capabilities_exclude_execution(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.adapter import (
            IbkrObservationalAdapter,
        )

        self.assertTrue(
            IbkrObservationalAdapter.authorized_capabilities.isdisjoint(
                {"EXECUTION", "ORDER_MANAGEMENT", "ACCOUNT_TRADING"}
            )
        )

    def test_source_tree_never_mentions_execution_verbs(self) -> None:
        forbidden = (
            "placeOrder",
            "modifyOrder",
            "cancelOrder",
            "exerciseOptions",
            "reqFundTransfer",
        )
        for path in sorted(PACKAGE.rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, source, f"{path.name} contains {marker}")

    def test_transport_protocol_has_observational_methods_only(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.adapter import (
            IbkrTransport,
        )

        required = {
            "connect",
            "disconnect",
            "is_connected",
            "req_mkt_data",
            "cancel_mkt_data",
            "req_mkt_depth",
            "cancel_mkt_depth",
        }
        self.assertTrue(required.issubset(set(IbkrTransport.__annotations__) or set(dir(IbkrTransport))))

    def test_capability_registry_never_registers_execution(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.capability import (
            IBKR_FORBIDDEN_CAPABILITIES,
            register_ibkr_observational,
        )
        from market_platform_foundation.providers.registry import ProviderRegistry

        registry = ProviderRegistry()
        descriptor = register_ibkr_observational(registry)
        ids = {capability.capability_id for capability in descriptor.capabilities}
        self.assertIn("IBKR_L1", ids)
        self.assertIn("IBKR_L2", ids)
        self.assertIn("IBKR_CONTRACT_RESOLUTION", ids)
        self.assertTrue(ids.isdisjoint(IBKR_FORBIDDEN_CAPABILITIES))
        self.assertTrue(ids.isdisjoint({"EXECUTION", "IBKR_EXECUTION"}))

    def test_config_forces_loopback_and_readonly_default(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.adapter import (
            IbkrObservationalConfig,
        )

        config = IbkrObservationalConfig()
        self.assertTrue(config.readonly)
        with self.assertRaises(ValueError):
            IbkrObservationalConfig(host="8.8.8.8")
        with self.assertRaises(ValueError):
            IbkrObservationalConfig(port=9999)


class OfflineGateTests(unittest.TestCase):
    def test_offline_adapter_never_touches_transport(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.adapter import (
            IbkrOfflineError,
        )
        from market_platform_foundation.providers.ibkr_observational.contracts import (
            EntitlementState,
        )

        from ibkr_observational_support import FakeLookup, FakeTransport, make_adapter, make_record

        transport = FakeTransport()
        adapter, _ = make_adapter(
            live=False,
            store=None,
            lookup=FakeLookup(make_record("AAPL")),
            transport=transport,
        )
        with self.assertRaises(IbkrOfflineError):
            adapter.connect()
        with self.assertRaises(IbkrOfflineError):
            adapter.subscribe_l1(instrument_id="AAPL")
        with self.assertRaises(IbkrOfflineError):
            adapter.subscribe_l2(instrument_id="AAPL")
        with self.assertRaises(IbkrOfflineError):
            adapter.handle_reconnect()
        self.assertEqual(transport.connect_calls, [])
        self.assertEqual(transport.mkt_data_requests, [])
        self.assertEqual(transport.mkt_depth_requests, [])

    def test_offline_replay_registration_is_permitted(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.contracts import (
            CapabilityKind,
        )

        from ibkr_observational_support import FakeLookup, FakeTransport, make_adapter, make_record

        transport = FakeTransport()
        adapter, _ = make_adapter(
            live=False,
            store=None,
            lookup=FakeLookup(make_record("AAPL")),
            transport=transport,
        )
        result = adapter.register_replay_subscription(
            instrument_id="AAPL", capability=CapabilityKind.L1, req_id=5000
        )
        self.assertTrue(result.accepted, result.reason)
        self.assertEqual(transport.mkt_data_requests, [])


if __name__ == "__main__":
    unittest.main()