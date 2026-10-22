"""AUTO-01 route authorization: one capability table for the API dispatch and the capability resolver.

The defect this pins: the automation dispatch set used to be a hand-written literal in ``ui_api/server.py``
and the automation capabilities another literal in ``platform/security/route_policy.py``. ``policy_for_route``
falls through to ``RoutePolicy(capability="state.read")`` for an unmatched path, so a route present in only one
of the two tables could be authorized with a weaker capability than it needs. Both now derive from
``PAPER_AUTOMATION_CAPABILITIES``, which is what makes drift impossible rather than merely unlikely.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.platform.security.route_policy import (  # noqa: E402
    PAPER_AUTOMATION_BASE,
    PAPER_AUTOMATION_CAPABILITIES,
    PAPER_AUTOMATION_READ_PATHS,
    AccountScopeKind,
    paper_automation_operations,
    policy_for_route,
)
from market_platform_foundation.ui_api import server as server_module  # noqa: E402

# The declared boundary, written out so a silent capability change fails here instead of shipping.
ORDER_OPERATIONS = frozenset({"arm", "start", "resume"})
CONTROL_OPERATIONS = frozenset({"configure", "disarm", "pause", "stop", "emergency-stop"})
READ_OPERATIONS = frozenset({"status", "history", "report"})


def policy(operation: str, method: str):
    return policy_for_route(method, PAPER_AUTOMATION_BASE + operation)


class CapabilityTableTests(unittest.TestCase):
    def test_every_operation_resolves_to_its_declared_capability_and_the_paper_ledger(self):
        for operation, (method, capability) in PAPER_AUTOMATION_CAPABILITIES.items():
            with self.subTest(operation=operation):
                resolved = policy(operation, method)
                self.assertEqual(resolved.capability, capability)
                self.assertEqual(resolved.account_scope, AccountScopeKind.PAPER_LEDGER)

    def test_the_capability_boundary_is_exactly_orders_controls_and_reads(self):
        self.assertEqual(frozenset(PAPER_AUTOMATION_CAPABILITIES), ORDER_OPERATIONS | CONTROL_OPERATIONS | READ_OPERATIONS)
        for operation in sorted(ORDER_OPERATIONS):
            self.assertEqual(policy(operation, "POST").capability, "paper.order.submit", operation)
        for operation in sorted(CONTROL_OPERATIONS):
            self.assertEqual(policy(operation, "POST").capability, "state.write", operation)
        for operation in sorted(READ_OPERATIONS):
            self.assertEqual(policy(operation, "GET").capability, "audit.read", operation)

    def test_a_wrong_method_never_inherits_the_operations_capability(self):
        # A GET on an order operation, or a POST on a read, must not collect that operation's capability.
        for operation in sorted(ORDER_OPERATIONS):
            self.assertNotEqual(policy(operation, "GET").capability, "paper.order.submit", operation)
        for operation in sorted(READ_OPERATIONS):
            self.assertNotEqual(policy(operation, "POST").capability, "audit.read", operation)

    def test_an_unknown_operation_gets_no_order_capability(self):
        for unknown in ("launch", "liquidate", "arm/extra", ""):
            with self.subTest(unknown=unknown):
                self.assertIsNone(PAPER_AUTOMATION_CAPABILITIES.get(unknown))
                self.assertNotEqual(policy_for_route("POST", PAPER_AUTOMATION_BASE + unknown).capability,
                                    "paper.order.submit")


class DispatchDriftTests(unittest.TestCase):
    def test_the_api_dispatch_set_is_the_capability_tables_post_subset(self):
        expected = frozenset(operation for operation, (method, _capability) in PAPER_AUTOMATION_CAPABILITIES.items()
                             if method == "POST")
        self.assertEqual(expected, ORDER_OPERATIONS | CONTROL_OPERATIONS)
        self.assertEqual(server_module.PAPER_AUTOMATION_POST_OPERATIONS, expected)

    def test_the_api_read_set_is_the_capability_tables_get_paths(self):
        expected = frozenset(PAPER_AUTOMATION_BASE + operation
                             for operation, (method, _capability) in PAPER_AUTOMATION_CAPABILITIES.items()
                             if method == "GET")
        self.assertEqual(expected, frozenset(PAPER_AUTOMATION_BASE + operation for operation in READ_OPERATIONS))
        self.assertEqual(server_module.PAPER_AUTOMATION_READ_PATHS, expected)

    def test_a_read_operation_is_not_dispatchable_as_a_mutation(self):
        for operation in sorted(READ_OPERATIONS):
            self.assertNotIn(operation, server_module.PAPER_AUTOMATION_POST_OPERATIONS, operation)

    def test_the_two_tables_cannot_drift(self):
        # The invariant that replaces the pair of hand-written literals: the API's dispatchable sets are a
        # function of the capability table, so an operation can never exist in one table but not the other.
        self.assertEqual(server_module.PAPER_AUTOMATION_POST_OPERATIONS, paper_automation_operations("POST"))
        self.assertNotEqual(paper_automation_operations("GET"), paper_automation_operations("POST"))
        self.assertEqual(paper_automation_operations("GET") | paper_automation_operations("POST"),
                         frozenset(PAPER_AUTOMATION_CAPABILITIES))


if __name__ == "__main__":
    unittest.main()
