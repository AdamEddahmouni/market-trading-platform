"""Ingest assembler: not a production scanner."""

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
from market_platform_foundation.intelligence.contracts.opportunity import opportunity_v1_to_dict
from market_platform_foundation.intelligence.opportunity.ingest import assemble_opportunity_review_rows
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository


SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)


def _opportunity(opportunity_id: str, instrument_id: str = "AAPL") -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=(instrument_id,), context_id="regular"),
        created_at_ns=10_000,
        quality=QUALITY,
        side=OpportunitySide.LONG,
        reason_summary=f"{instrument_id} candidate",
    )


class OpportunityIngestTests(unittest.TestCase):
    def test_empty_repo_and_no_adapters_is_empty(self) -> None:
        self.assertEqual(assemble_opportunity_review_rows(), ())

    def test_discover_shaped_dicts_are_ignored(self) -> None:
        ignored = assemble_opportunity_review_rows(
            attention_rows=(
                {
                    "attention_id": "discover-1",
                    "symbol": "MSFT",
                    "headline": "screener",
                    "attention_score": 99,
                    "screen_ids": ["foo"],
                },
            )
        )
        self.assertEqual(ignored, ())

    def test_unknown_instrument_fail_closed(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity("opp-bad", instrument_id="UNKNOWN"),)
        )
        self.assertEqual(rows, ())

    def test_ingest_does_not_import_scanner(self) -> None:
        import market_platform_foundation.intelligence.opportunity.ingest as ingest

        source = inspect.getsource(ingest)
        self.assertNotIn("UniversalStrategyScanner", source)
        self.assertNotIn("StrategyPaperRuntime", source)

    def test_ingest_does_not_stamp_decision_time_metadata(self) -> None:
        import market_platform_foundation.intelligence.opportunity.ingest as ingest

        source = inspect.getsource(ingest)
        self.assertNotIn("decision_time_ns", source)
        self.assertNotIn("created_at_ns", source)
        self.assertNotIn("opportunity_decision_time_ns", source)

    def test_storage_id_is_stripped_and_not_added_to_opportunity_v1(self) -> None:
        class FakeRepo:
            _stores = {
                "opportunities": {
                    "opp-repo": {
                        **opportunity_v1_to_dict(_opportunity("opp-repo")),
                        "_id": "opp-repo",
                    }
                }
            }

        rows = assemble_opportunity_review_rows(
            repository=FakeRepo(),
            assessments_by_opportunity={"opp-repo": AssessmentAction.EMIT},
        )
        self.assertEqual([row.opportunity_id for row in rows], ["opp-repo"])
        self.assertNotIn("_id", rows[0].to_dict())

    def test_attention_rows_are_not_accepted_opportunity_v1(self) -> None:
        rows = assemble_opportunity_review_rows(
            attention_rows=(
                {
                    "attention_id": "att-honest",
                    "symbol": "NVDA",
                    "headline": "catalyst attention",
                    "catalyst_ids": ("earnings",),
                },
            )
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].identity_kind, "NOT_OPPORTUNITY_V1")
        self.assertFalse(rows[0].accepted)
        self.assertEqual(rows[0].eligibility_state, "UNAVAILABLE")
        self.assertIsNone(rows[0].evidence_class)

    def test_repository_does_not_mint_second_opportunity(self) -> None:
        repo = InMemoryIntelligenceRepository()
        opportunity = _opportunity("opp-repo")
        repo.put_opportunity(opportunity)
        rows = assemble_opportunity_review_rows(
            opportunities=(opportunity,),
            repository=repo,
            assessments_by_opportunity={"opp-repo": AssessmentAction.EMIT},
        )
        self.assertEqual([row.opportunity_id for row in rows].count("opp-repo"), 1)


if __name__ == "__main__":
    unittest.main()
