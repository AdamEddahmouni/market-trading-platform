"""Non-semantic Opportunity Engine contracts: wiring, fail-closed, no scores."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.errors import OpportunityError
from market_platform_foundation.intelligence.opportunity.ingest import assemble_opportunity_review_rows
from market_platform_foundation.intelligence.opportunity.lifecycle import (
    OperatorLifecycleError,
    OperatorLifecycleState,
    apply_operator_ack,
)
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction
from market_platform_foundation.ui_api.operator_opportunity_state import (
    record_operator_ack,
    reset_operator_acks,
)


SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)


def _opportunity(opportunity_id: str = "opp-ns-1") -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=SCOPE,
        created_at_ns=10_000,
        quality=QUALITY,
        side=OpportunitySide.LONG,
        reason_summary="AAPL candidate",
    )


class OpportunityNonSemanticContractTests(unittest.TestCase):
    def test_ingest_does_not_stamp_decision_or_created_timestamps(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity(),),
            assessments_by_opportunity={"opp-ns-1": AssessmentAction.EMIT},
        )
        self.assertEqual(len(rows), 1)
        metadata = rows[0].metadata
        self.assertNotIn("decision_time_ns", metadata)
        self.assertNotIn("created_at_ns", metadata)
        self.assertNotIn("rank_score", rows[0].to_dict())
        self.assertNotIn("universal_score", rows[0].to_dict())

    def test_opportunity_error_preserves_code_without_invented_details(self) -> None:
        err = OpportunityError("FORECAST_NOT_FROM_GOVERNED_CHAMPION")
        self.assertEqual(err.code, "FORECAST_NOT_FROM_GOVERNED_CHAMPION")
        self.assertEqual(err.details, {})
        self.assertEqual(str(err), "FORECAST_NOT_FROM_GOVERNED_CHAMPION")

    def test_operator_enum_does_not_invent_monitored_or_outcome_recorded(self) -> None:
        names = {member.name for member in OperatorLifecycleState}
        self.assertNotIn("MONITORED", names)
        self.assertNotIn("OUTCOME_RECORDED", names)
        self.assertNotIn("PAPER_SUBMITTED", names)

    def test_expired_is_not_an_operator_ack(self) -> None:
        with self.assertRaises(OperatorLifecycleError):
            apply_operator_ack(
                OperatorLifecycleState.ELIGIBLE,
                OperatorLifecycleState.EXPIRED,
            )

    def test_record_operator_ack_rejects_paper_previewed(self) -> None:
        reset_operator_acks()
        with self.assertRaises(ValueError) as ctx:
            record_operator_ack(
                summary_id="sum-1",
                opportunity_id="opp-ns-1",
                paper_account_id="paper-default",
                action=OperatorLifecycleState.PAPER_PREVIEWED.value,
                created_at_ns=1,
            )
        self.assertEqual(str(ctx.exception), "OPERATOR_ACK_INVALID")


if __name__ == "__main__":
    unittest.main()
