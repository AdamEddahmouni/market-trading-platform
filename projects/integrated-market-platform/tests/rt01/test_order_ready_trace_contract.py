"""Trace-contract tests: opportunity → risk → order_ready correlation."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts.common import ContractReference
from market_platform_foundation.intelligence.execution.order_ready_correlation import (
    assert_order_ready_opportunity_correlation,
    correlation_snapshot_from_mapping,
    opportunity_id_from_order_ready,
    order_ready_correlation_snapshot,
)
from market_platform_foundation.intelligence.execution.serialization import order_ready_v1_to_dict
from market_platform_foundation.intelligence.execution.types import OrderReadyStatus, OrderReadyV1
from market_platform_foundation.intelligence.system_acceptance.inventory import (
    CONTRACT_INVENTORY,
    LINEAGE_EDGES,
)

from tests.intelligence.test_equity_paper_runtime import _runtime_fixture


class OrderReadyTraceContractTests(unittest.TestCase):
    def test_inventory_registers_order_ready_lineage_edges(self) -> None:
        self.assertIn("OrderReadyV1", CONTRACT_INVENTORY)
        self.assertIn(("RiskDecisionV1", "OrderReadyV1", "risk_decision_id"), LINEAGE_EDGES)
        self.assertIn(("OpportunityV1", "OrderReadyV1", "lineage_refs"), LINEAGE_EDGES)

    def test_helper_requires_opportunity_lineage_ref(self) -> None:
        ready = OrderReadyV1(
            order_ready_id="OR-trace-contract-1",
            schema_version="1",
            allocation_decision_id="alloc-1",
            trade_proposal_id="tp-1",
            risk_decision_id="risk-1",
            account_id="acct-paper",
            mode="PAPER",
            decision_time_ns=1_700_000_000_000_000_000,
            instrument_id="AAPL",
            symbol="AAPL",
            approved_quantity=1,
            approved_notional_minor=100,
            status=OrderReadyStatus.READY,
            execution_authority="PAPER_ONLY",
            execution_mode="INTERNAL_SIMULATION",
            idempotency_key="idem-1",
            correlation_id="corr-1",
            lineage_refs=(),
        )
        self.assertIsNone(opportunity_id_from_order_ready(ready))
        with self.assertRaisesRegex(ValueError, "ORDER_READY_OPPORTUNITY_LINEAGE_MISSING"):
            assert_order_ready_opportunity_correlation(
                ready,
                opportunity_id="opp-1",
                correlation_id="corr-1",
            )

    def test_strategy_entry_persists_opportunity_through_order_ready(self) -> None:
        runtime, repository, request, _forecast = _runtime_fixture(
            session_id="rt01-order-ready-trace-contract",
        )
        result = runtime.run_entry(request)
        self.assertEqual(result.status, "FILLED")
        order_ready = repository.get_order_ready(result.ids["order_ready_id"])
        self.assertIsNotNone(order_ready)
        assert order_ready is not None
        snapshot = order_ready_correlation_snapshot(order_ready)
        self.assertEqual(snapshot["opportunity_id"], result.ids["opportunity_id"])
        self.assertEqual(snapshot["correlation_id"], result.ids["correlation_id"])
        self.assertEqual(snapshot["risk_decision_id"], result.ids["risk_decision_id"])
        self.assertEqual(snapshot["trade_proposal_id"], result.ids["trade_proposal_id"])
        self.assertEqual(snapshot["order_ready_id"], result.ids["order_ready_id"])
        assert_order_ready_opportunity_correlation(
            order_ready,
            opportunity_id=result.ids["opportunity_id"],
            correlation_id=result.ids["correlation_id"],
        )
        serialized = correlation_snapshot_from_mapping(order_ready_v1_to_dict(order_ready))
        self.assertEqual(serialized["opportunity_id"], result.ids["opportunity_id"])
        self.assertIn(
            ContractReference(kind="opportunity", id=result.ids["opportunity_id"]),
            order_ready.lineage_refs,
        )


if __name__ == "__main__":
    unittest.main()
