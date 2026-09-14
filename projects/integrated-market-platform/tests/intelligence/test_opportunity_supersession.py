"""Thesis supersession policy on operator review rows."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.opportunity.dedup import (
    DUPLICATE_THESIS_SUPPRESSED,
    keep_ranked_thesis_winners,
)
from market_platform_foundation.intelligence.opportunity.read_model import OpportunitySummary
from market_platform_foundation.intelligence.opportunity.supersession import (
    SUPERSEDED_BY_NEWER_THESIS,
    SupersessionPolicyError,
    apply_thesis_supersession,
    decision_time_ns_from_row,
    select_thesis_group_winner,
)


def _opp(
    summary_id: str,
    *,
    opportunity_id: str,
    thesis: str,
    decision_time_ns: int | None = None,
) -> OpportunitySummary:
    metadata: dict[str, object] = {"thesis_identity": thesis}
    if decision_time_ns is not None:
        metadata["decision_time_ns"] = decision_time_ns
    return OpportunitySummary(
        summary_id=summary_id,
        instrument_id="AAPL",
        headline=summary_id,
        opportunity_id=opportunity_id,
        identity_kind="OPPORTUNITY_V1",
        metadata=metadata,
    )


class OpportunitySupersessionTests(unittest.TestCase):
    def test_decision_time_invalid_raises(self) -> None:
        row = OpportunitySummary(
            summary_id="x",
            instrument_id="AAPL",
            headline="x",
            metadata={"decision_time_ns": "not-int"},
        )
        with self.assertRaises(SupersessionPolicyError):
            decision_time_ns_from_row(row)

    def test_newer_decision_time_wins_over_better_rank(self) -> None:
        older = _opp("opp-old", opportunity_id="opp-old", thesis="t1", decision_time_ns=100)
        newer = _opp("opp-new", opportunity_id="opp-new", thesis="t1", decision_time_ns=200)
        kept = keep_ranked_thesis_winners((older, newer))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].opportunity_id, "opp-new")
        self.assertEqual(kept[0].metadata.get("supersession_reason"), SUPERSEDED_BY_NEWER_THESIS)
        self.assertEqual(kept[0].duplicates, ("opp-old",))

    def test_missing_time_fail_closed_to_rank_order(self) -> None:
        first = _opp("opp-a", opportunity_id="opp-a", thesis="t1", decision_time_ns=None)
        second = _opp("opp-b", opportunity_id="opp-b", thesis="t1", decision_time_ns=200)
        kept = keep_ranked_thesis_winners((first, second))
        self.assertEqual(kept[0].opportunity_id, "opp-a")
        self.assertEqual(kept[0].metadata.get("duplicate_reason"), DUPLICATE_THESIS_SUPPRESSED)
        self.assertNotEqual(kept[0].metadata.get("supersession_reason"), SUPERSEDED_BY_NEWER_THESIS)

    def test_tied_decision_time_keeps_rank_order(self) -> None:
        first = _opp("opp-a", opportunity_id="opp-a", thesis="t1", decision_time_ns=100)
        second = _opp("opp-b", opportunity_id="opp-b", thesis="t1", decision_time_ns=100)
        kept = select_thesis_group_winner((first, second))
        self.assertEqual(kept.opportunity_id, "opp-a")
        self.assertEqual(kept.metadata.get("duplicate_reason"), DUPLICATE_THESIS_SUPPRESSED)

    def test_distinct_theses_unchanged(self) -> None:
        left = _opp("opp-a", opportunity_id="opp-a", thesis="t-a", decision_time_ns=50)
        right = _opp("opp-b", opportunity_id="opp-b", thesis="t-b", decision_time_ns=500)
        kept = apply_thesis_supersession((left, right))
        self.assertEqual([row.opportunity_id for row in kept], ["opp-a", "opp-b"])


if __name__ == "__main__":
    unittest.main()
