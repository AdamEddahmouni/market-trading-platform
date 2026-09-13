"""Operator lifecycle derivation and ack transitions."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.opportunity.lifecycle import (
    OperatorLifecycleState,
    apply_operator_ack,
    derive_lifecycle_from_assessment,
)
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction


class OpportunityLifecycleTests(unittest.TestCase):
    def test_abstain_is_ineligible(self) -> None:
        self.assertEqual(
            derive_lifecycle_from_assessment(AssessmentAction.ABSTAIN),
            OperatorLifecycleState.INELIGIBLE,
        )

    def test_watch_does_not_boost_rank_state_machine(self) -> None:
        watched = apply_operator_ack(OperatorLifecycleState.RANKED, OperatorLifecycleState.WATCHED)
        self.assertEqual(watched, OperatorLifecycleState.WATCHED)


if __name__ == "__main__":
    unittest.main()
