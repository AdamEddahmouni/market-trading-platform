"""P0/P11 persist-contract invariants for OpportunityV1."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    IntelligenceScope,
    OpportunityV1,
    QualityState,
    QualitySummary,
)

SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)


class OpportunityEngineInvariantsTests(unittest.TestCase):
    def test_opportunity_metadata_rejects_universal_score(self) -> None:
        with self.assertRaises(ValueError):
            OpportunityV1(
                opportunity_id="opp-score",
                schema_version="1",
                scope=SCOPE,
                created_at_ns=10_000,
                quality=QUALITY,
                metadata={"universal_score": 88},
            )

    def test_opportunity_metadata_rejects_rank_score(self) -> None:
        with self.assertRaises(ValueError):
            OpportunityV1(
                opportunity_id="opp-rank",
                schema_version="1",
                scope=SCOPE,
                created_at_ns=10_000,
                quality=QUALITY,
                metadata={"rank_score": 12},
            )


if __name__ == "__main__":
    unittest.main()
