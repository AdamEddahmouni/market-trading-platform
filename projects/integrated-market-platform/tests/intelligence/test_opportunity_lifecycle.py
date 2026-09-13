"""Operator review-row lifecycle. Not an OpportunityV1 enum."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.opportunity.lifecycle import (
    OperatorLifecycleError,
    OperatorLifecycleState,
    apply_operator_ack,
    derive_lifecycle_from_assessment,
)
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction


class OpportunityLifecycleTests(unittest.TestCase):
    def test_emit_is_eligible_and_abstain_is_ineligible(self) -> None:
        self.assertEqual(derive_lifecycle_from_assessment(AssessmentAction.EMIT), OperatorLifecycleState.ELIGIBLE)
        self.assertEqual(derive_lifecycle_from_assessment(AssessmentAction.ABSTAIN), OperatorLifecycleState.INELIGIBLE)
        self.assertEqual(derive_lifecycle_from_assessment(AssessmentAction.SUPPRESS), OperatorLifecycleState.INELIGIBLE)
        self.assertEqual(derive_lifecycle_from_assessment(AssessmentAction.FAIL_CLOSED), OperatorLifecycleState.INELIGIBLE)

    def test_watch_does_not_mutate_opportunity_identity(self) -> None:
        watched = apply_operator_ack(OperatorLifecycleState.ELIGIBLE, OperatorLifecycleState.WATCHED)
        self.assertEqual(watched, OperatorLifecycleState.WATCHED)

    def test_illegal_transition_from_dismissed_fails_closed(self) -> None:
        with self.assertRaises(OperatorLifecycleError):
            apply_operator_ack(OperatorLifecycleState.DISMISSED, OperatorLifecycleState.WATCHED)


if __name__ == "__main__":
    unittest.main()
