"""Operator ingest consumes OF-03 family registry. Does not mint or rank."""

from __future__ import annotations

import inspect
import unittest

from market_platform_foundation.intelligence.contracts import (
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.family_lookup import (
    STATUS_ADMITTED,
    STATUS_DENIED,
    STATUS_UNAVAILABLE,
    resolve_review_family,
)
from market_platform_foundation.intelligence.opportunity.ingest import assemble_opportunity_review_rows
from market_platform_foundation.intelligence.opportunity.lifecycle import OperatorLifecycleState
from market_platform_foundation.intelligence.opportunity.ranking import rank_review_rows
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction
from market_platform_foundation.of03.errors import OF03ErrorCode


QUALITY = QualitySummary(state=QualityState.GOOD)


def _opportunity(
    opportunity_id: str,
    *,
    metadata: dict | None = None,
    instrument_id: str = "AAPL",
) -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=(instrument_id,), context_id="regular"),
        created_at_ns=10_000,
        quality=QUALITY,
        side=OpportunitySide.LONG,
        reason_summary=f"{instrument_id} candidate",
        metadata=dict(metadata or {}),
    )


class FamilyLookupTests(unittest.TestCase):
    def test_absent_family_is_unavailable(self) -> None:
        resolution = resolve_review_family({})
        self.assertEqual(resolution.status, STATUS_UNAVAILABLE)
        self.assertIsNone(resolution.family_id)

    def test_known_family_requires_exact_version(self) -> None:
        denied = resolve_review_family({"strategy_family": "NEWS_CATALYST"})
        self.assertEqual(denied.status, STATUS_DENIED)
        self.assertEqual(denied.reason_code, OF03ErrorCode.IMPLICIT_LATEST_PROHIBITED.value)
        admitted = resolve_review_family(
            {
                "strategy_family": "NEWS_CATALYST",
                "family_definition_version": 1,
                "strategy_version": "NEWS_CATALYST_PROFILE_V1",
            }
        )
        self.assertEqual(admitted.status, STATUS_ADMITTED)
        self.assertEqual(admitted.family_id, "NEWS_CATALYST")
        self.assertEqual(admitted.admission_kind, "METADATA_ONLY")

    def test_unknown_family_fail_closed(self) -> None:
        resolution = resolve_review_family(
            {"strategy_family": "UNKNOWN_LANE", "family_definition_version": 1}
        )
        self.assertEqual(resolution.status, STATUS_DENIED)
        self.assertEqual(resolution.reason_code, OF03ErrorCode.UNKNOWN_STRATEGY_FAMILY.value)

    def test_lookup_does_not_mint_or_scan(self) -> None:
        import market_platform_foundation.intelligence.opportunity.family_lookup as module

        source = inspect.getsource(module)
        self.assertNotIn("UniversalStrategyScanner", source)
        self.assertNotIn("StrategyPaperRuntime", source)
        self.assertNotIn("OpportunityV1(", source)
        self.assertNotIn("ForecastV1(", source)
        self.assertNotIn("rank_score", source)


class FamilyIngestTests(unittest.TestCase):
    def test_missing_family_stays_honest_unavailable(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity("opp-plain"),),
            assessments_by_opportunity={"opp-plain": AssessmentAction.EMIT},
        )
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].strategy_family)
        self.assertIn("strategy_family", rows[0].unavailable_fields)
        self.assertEqual(rows[0].evidence_class, "CANDIDATE")
        self.assertEqual(rows[0].lifecycle_state, OperatorLifecycleState.ELIGIBLE.value)
        self.assertNotIn("rank_score", rows[0].to_dict())

    def test_declared_family_stamps_metadata_only(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(
                _opportunity(
                    "opp-news",
                    metadata={
                        "strategy_family": "NEWS_CATALYST",
                        "family_definition_version": 1,
                        "strategy_version": "NEWS_CATALYST_PROFILE_V1",
                    },
                ),
            ),
            assessments_by_opportunity={"opp-news": AssessmentAction.EMIT},
        )
        self.assertEqual(rows[0].strategy_family, "NEWS_CATALYST")
        self.assertEqual(rows[0].strategy_version, "NEWS_CATALYST_PROFILE_V1")
        self.assertEqual(rows[0].evidence_class, "CANDIDATE")
        self.assertNotEqual(rows[0].evidence_class, "VERIFIED")
        self.assertEqual(rows[0].metadata["family_admission_status"], STATUS_ADMITTED)
        self.assertEqual(rows[0].metadata["family_admission_kind"], "METADATA_ONLY")
        self.assertEqual(rows[0].lifecycle_state, OperatorLifecycleState.ELIGIBLE.value)
        self.assertNotIn("rank_score", rows[0].to_dict())

    def test_unknown_family_cannot_be_ranked_even_if_emit(self) -> None:
        ingested = assemble_opportunity_review_rows(
            opportunities=(
                _opportunity(
                    "opp-bad-family",
                    metadata={"strategy_family": "UNKNOWN_LANE", "family_definition_version": 1},
                ),
            ),
            assessments_by_opportunity={"opp-bad-family": AssessmentAction.EMIT},
        )
        self.assertEqual(ingested[0].lifecycle_state, OperatorLifecycleState.INELIGIBLE.value)
        self.assertFalse(ingested[0].accepted)
        ranked = rank_review_rows(ingested)
        self.assertEqual(ranked, ())

    def test_unversioned_family_claim_fail_closed(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(
                _opportunity("opp-latest", metadata={"strategy_family": "SQUEEZE"}),
            ),
            assessments_by_opportunity={"opp-latest": AssessmentAction.EMIT},
        )
        self.assertEqual(rows[0].lifecycle_state, OperatorLifecycleState.INELIGIBLE.value)
        self.assertEqual(rows[0].metadata["family_admission_reason"], OF03ErrorCode.IMPLICIT_LATEST_PROHIBITED.value)
        self.assertEqual(rank_review_rows(rows), ())


if __name__ == "__main__":
    unittest.main()
