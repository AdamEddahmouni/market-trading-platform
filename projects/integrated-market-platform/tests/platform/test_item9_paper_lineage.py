"""Prospective Paper lineage reconstruction stays NOT_OBSERVED for missing links."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts.common import (  # noqa: E402
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
)
from market_platform_foundation.intelligence.execution.types import (  # noqa: E402
    OrderReadyStatus,
    OrderReadyV1,
)
from market_platform_foundation.paper.calibration.item9_paper_lineage import (  # noqa: E402
    LINEAGE_STEPS,
    load_prospective_paper_run_package,
    order_ready_lineage_from_record,
    paper_lifecycle_gap_report,
    reconstruct_lineage_map,
)
from market_platform_foundation.paper.calibration.item9_validation_readiness_contract import (  # noqa: E402
    FIELD_NOT_APPLICABLE,
    FIELD_NOT_OBSERVED,
)


class Item9PaperLineageTests(unittest.TestCase):
    def test_run_package_template_not_started(self) -> None:
        package = load_prospective_paper_run_package(imp_root=ROOT)
        self.assertTrue(package["loaded"])
        self.assertFalse(package["session_started"])
        self.assertEqual(package["package_role"], "TEMPLATE")
        self.assertFalse(package["calibrated"])
        self.assertFalse(package["paper_validated"])

    def test_missing_links_stay_not_observed(self) -> None:
        mapping = reconstruct_lineage_map({"OpportunityV1": "opp-1"})
        self.assertEqual(mapping["links"]["OpportunityV1"]["status"], "PRESENT")
        self.assertEqual(mapping["links"]["order_ready"]["status"], FIELD_NOT_OBSERVED)
        self.assertEqual(mapping["links"]["thesis"]["status"], FIELD_NOT_OBSERVED)
        self.assertEqual(mapping["mode_b_strategy_fields"], FIELD_NOT_APPLICABLE)
        self.assertEqual(len(mapping["links"]), len(LINEAGE_STEPS))

    def test_order_ready_opportunity_lineage_without_invention(self) -> None:
        order_ready = OrderReadyV1(
            order_ready_id="OR-item9-lineage",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            allocation_decision_id="alloc-item9",
            trade_proposal_id="tp-item9",
            risk_decision_id="risk-item9",
            account_id="acct-paper",
            mode="PAPER",
            decision_time_ns=1_700_000_000_000_000_000,
            instrument_id="inst-aapl",
            symbol="AAPL",
            approved_quantity=1,
            approved_notional_minor=100,
            status=OrderReadyStatus.READY,
            execution_authority="PAPER_ONLY",
            execution_mode="INTERNAL_SIMULATION",
            idempotency_key="idem-item9",
            correlation_id="corr-item9",
            lineage_refs=(ContractReference(kind="opportunity", id="opp-item9"),),
        )
        extracted = order_ready_lineage_from_record(order_ready)
        self.assertEqual(extracted["OpportunityV1"]["status"], "PRESENT")
        self.assertEqual(extracted["OpportunityV1"]["value"], "opp-item9")
        self.assertEqual(extracted["order_ready"]["status"], "PRESENT")

    def test_order_ready_without_opportunity_stays_not_observed(self) -> None:
        order_ready = OrderReadyV1(
            order_ready_id="OR-item9-missing",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            allocation_decision_id="alloc-item9b",
            trade_proposal_id="tp-item9b",
            risk_decision_id="risk-item9b",
            account_id="acct-paper",
            mode="PAPER",
            decision_time_ns=1_700_000_000_000_000_000,
            instrument_id="inst-aapl",
            symbol="AAPL",
            approved_quantity=1,
            approved_notional_minor=100,
            status=OrderReadyStatus.READY,
            execution_authority="PAPER_ONLY",
            execution_mode="INTERNAL_SIMULATION",
            idempotency_key="idem-item9b",
            correlation_id="corr-item9b",
            lineage_refs=(),
        )
        extracted = order_ready_lineage_from_record(order_ready)
        self.assertEqual(extracted["OpportunityV1"]["status"], FIELD_NOT_OBSERVED)


    def test_lifecycle_gaps_stay_not_observed(self) -> None:
        report = paper_lifecycle_gap_report()
        self.assertEqual(report["missing_link_token"], FIELD_NOT_OBSERVED)
        self.assertFalse(report["session_started"])
        self.assertIn("StrategyMatch", report["missing_canonical_nodes"])
        self.assertIn("ForecastV1", report["missing_canonical_nodes"])
        self.assertEqual(
            report["reconstruction_helpers"]["thesis"], FIELD_NOT_OBSERVED
        )
        self.assertEqual(
            report["reconstruction_helpers"]["OpportunityV1"],
            "order_ready_lineage_from_record",
        )


if __name__ == "__main__":
    unittest.main()
