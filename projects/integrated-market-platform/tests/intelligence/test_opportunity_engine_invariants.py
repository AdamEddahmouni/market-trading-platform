"""FAST-bound Opportunity Engine invariants."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    IntelligenceScope,
    OpportunityV1,
    QualityState,
    QualitySummary,
    opportunity_v1_to_dict,
)


class OpportunityEngineInvariantsTests(unittest.TestCase):
    def test_opportunity_is_not_an_order(self) -> None:
        opportunity = OpportunityV1(
            opportunity_id="opp-1",
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=("AAPL",), context_id="regular"),
            created_at_ns=1,
            quality=QualitySummary(state=QualityState.GOOD),
        )
        payload = opportunity_v1_to_dict(opportunity)
        self.assertNotIn("order_id", payload)
        self.assertNotIn("quantity", payload)


if __name__ == "__main__":
    unittest.main()
