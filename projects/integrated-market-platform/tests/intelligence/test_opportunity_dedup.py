"""Review-row dedup: one ranked winner per opportunity_id or thesis."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.opportunity.dedup import dedup_review_rows
from market_platform_foundation.intelligence.opportunity.read_model import OpportunitySummary


class OpportunityDedupTests(unittest.TestCase):
    def test_same_opportunity_id_collapses(self) -> None:
        rows = dedup_review_rows(
            (
                OpportunitySummary(summary_id="a", instrument_id="AAPL", headline="one", opportunity_id="OPP-1"),
                OpportunitySummary(summary_id="b", instrument_id="AAPL", headline="two", opportunity_id="OPP-1"),
            )
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0].duplicates), 1)


if __name__ == "__main__":
    unittest.main()
