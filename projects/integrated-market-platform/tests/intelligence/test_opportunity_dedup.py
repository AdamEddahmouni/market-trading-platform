"""Review-row dedup. Does not rewrite clustering."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.opportunity.dedup import (
    DUPLICATE_THESIS_SUPPRESSED,
    dedup_review_rows,
    keep_ranked_thesis_winners,
)
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

    def test_ranked_winner_keeps_first_shared_thesis_and_suppresses_extra(self) -> None:
        better = OpportunitySummary(
            summary_id="opp-z",
            instrument_id="AAPL",
            headline="better",
            opportunity_id="opp-z",
            identity_kind="OPPORTUNITY_V1",
            metadata={"thesis_identity": "underlying:earnings-aapl"},
        )
        worse = OpportunitySummary(
            summary_id="opp-a",
            instrument_id="AAPL",
            headline="worse",
            opportunity_id="opp-a",
            identity_kind="OPPORTUNITY_V1",
            metadata={"thesis_identity": "underlying:earnings-aapl"},
        )
        kept = keep_ranked_thesis_winners((better, worse))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].opportunity_id, "opp-z")
        self.assertEqual(kept[0].duplicates, ("opp-a",))
        self.assertEqual(kept[0].metadata["duplicate_reason"], DUPLICATE_THESIS_SUPPRESSED)

    def test_distinct_theses_remain_separate_cards(self) -> None:
        left = OpportunitySummary(
            summary_id="opp-a",
            instrument_id="AAPL",
            headline="a",
            opportunity_id="opp-a",
            identity_kind="OPPORTUNITY_V1",
            metadata={"thesis_identity": "underlying:thesis-a"},
        )
        right = OpportunitySummary(
            summary_id="opp-b",
            instrument_id="AAPL",
            headline="b",
            opportunity_id="opp-b",
            identity_kind="OPPORTUNITY_V1",
            metadata={"thesis_identity": "underlying:thesis-b"},
        )
        kept = keep_ranked_thesis_winners((left, right))
        self.assertEqual([row.opportunity_id for row in kept], ["opp-a", "opp-b"])
        self.assertEqual(kept[0].duplicates, ())


if __name__ == "__main__":
    unittest.main()
