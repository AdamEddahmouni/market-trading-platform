"""Review-row dedup. Does not rewrite clustering."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.opportunity.dedup import dedup_review_rows
from market_platform_foundation.intelligence.opportunity.read_model import OpportunitySummary


class OpportunityDedupTests(unittest.TestCase):
    def test_same_opportunity_id_is_one_row(self) -> None:
        a = OpportunitySummary(summary_id="s1", instrument_id="AAPL", headline="a", opportunity_id="opp-1")
        b = OpportunitySummary(summary_id="s2", instrument_id="AAPL", headline="b", opportunity_id="opp-1")
        deduped = dedup_review_rows((a, b))
        self.assertEqual(len(deduped), 1)
        self.assertEqual(len(deduped[0].duplicates), 1)

    def test_same_thesis_tuple_without_opportunity_id_dedups(self) -> None:
        a = OpportunitySummary(
            summary_id="a",
            instrument_id="AAPL",
            headline="one",
            side="LONG",
            valid_until_ns=10,
            catalyst_ids=("earnings",),
        )
        b = OpportunitySummary(
            summary_id="b",
            instrument_id="AAPL",
            headline="two",
            side="LONG",
            valid_until_ns=10,
            catalyst_ids=("earnings",),
        )
        deduped = dedup_review_rows((a, b))
        self.assertEqual(len(deduped), 1)
        self.assertEqual(len(deduped[0].duplicates), 1)


if __name__ == "__main__":
    unittest.main()
