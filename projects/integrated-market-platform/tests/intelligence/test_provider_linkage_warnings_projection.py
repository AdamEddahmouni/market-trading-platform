"""Operator projection of provider-linkage quality flags."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.data_quality import (
    project_opportunity_data_quality,
)
from market_platform_foundation.intelligence.opportunity.ingest import (
    assemble_opportunity_review_rows,
)
from market_platform_foundation.intelligence.opportunity.provider_linkage_warnings import (
    project_provider_linkage_warnings,
)
from market_platform_foundation.news.provider_linkage_quality import (
    FLAG_ALTERNATE_ENTITY_PROMINENT,
    FLAG_LOW_CONTEXTUAL_CONFIDENCE,
    FLAG_MULTIPLE_CONTRADICTORY,
    FLAG_SOURCE_URL_MISSING,
    FLAG_TICKER_NOT_IN_TEXT,
)
from market_platform_foundation.ui_api.opportunity_projections import (
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.store import ReplayStore
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository

from tests.ui1.test_ui_api import COLLECTION_ROOT


def _opportunity(
    *,
    opportunity_id: str = "opp-link-1",
    instrument_id: str = "NVDA",
    headline: str = "MillerKnoll announces lineup",
    flags: tuple[str, ...] = (),
) -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=(instrument_id,), context_id="regular"),
        created_at_ns=1_700_000_000_000_000_000,
        quality=QualitySummary(state=QualityState.GOOD, flags=flags),
        side=OpportunitySide.LONG,
        reason_summary=headline,
        lineage_refs=(ContractReference(kind="event", id="evt-link-1"),),
    )


class ProviderLinkageWarningsProjectionTests(unittest.TestCase):
    def test_flags_project_into_operator_phrases(self) -> None:
        phrases = project_provider_linkage_warnings(
            (
                FLAG_TICKER_NOT_IN_TEXT,
                FLAG_ALTERNATE_ENTITY_PROMINENT,
                FLAG_LOW_CONTEXTUAL_CONFIDENCE,
                FLAG_MULTIPLE_CONTRADICTORY,
                FLAG_SOURCE_URL_MISSING,
            )
        )
        self.assertEqual(
            phrases,
            (
                "uncorroborated",
                "contextual concern",
                "low confidence",
                "source mismatch",
                "source URL missing",
            ),
        )

    def test_non_linkage_flags_are_excluded(self) -> None:
        phrases = project_provider_linkage_warnings(
            (
                "PUBLICATION_TIME_UNKNOWN",
                "PUBLICATION_TIME_INFERRED",
                "SOME_OTHER_FLAG",
                FLAG_TICKER_NOT_IN_TEXT,
            )
        )
        self.assertEqual(phrases, ("uncorroborated",))

    def test_empty_when_no_linkage_flags(self) -> None:
        self.assertEqual(project_provider_linkage_warnings(()), ())
        self.assertEqual(project_provider_linkage_warnings(None), ())
        self.assertEqual(
            project_provider_linkage_warnings(("PUBLICATION_TIME_UNKNOWN",)),
            (),
        )

    def test_uncorroborated_phrase_is_not_wrong_ticker(self) -> None:
        phrases = project_provider_linkage_warnings((FLAG_TICKER_NOT_IN_TEXT,))
        self.assertEqual(phrases, ("uncorroborated",))
        self.assertNotIn("wrong ticker", " ".join(phrases).lower())

    def test_summary_and_detail_carry_phrases_without_touching_freshness(self) -> None:
        baseline_quality = project_opportunity_data_quality(source="REPLAY")
        opportunity = _opportunity(
            flags=(
                FLAG_TICKER_NOT_IN_TEXT,
                FLAG_ALTERNATE_ENTITY_PROMINENT,
                FLAG_LOW_CONTEXTUAL_CONFIDENCE,
                "PUBLICATION_TIME_UNKNOWN",
            )
        )
        repo = InMemoryIntelligenceRepository()
        repo.put_opportunity(opportunity)
        store = ReplayStore(collection_root=COLLECTION_ROOT)
        store.load()
        store.strategy_repository = repo

        rows = assemble_opportunity_review_rows(repository=repo, source="REPLAY")
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0].provider_linkage_warnings,
            ("uncorroborated", "contextual concern", "low confidence"),
        )
        self.assertEqual(rows[0].data_quality["freshness"], baseline_quality["freshness"])
        self.assertEqual(rows[0].data_quality["status"], baseline_quality["status"])
        self.assertEqual(
            rows[0].data_quality["operator_surface_flag"],
            baseline_quality["operator_surface_flag"],
        )
        self.assertNotIn("PROVIDER_LINKAGE", str(rows[0].data_quality))

        payload = build_opportunities_summary_payload(store)
        item = next(
            row for row in payload["items"] if row.get("opportunity_id") == opportunity.opportunity_id
        )
        self.assertEqual(
            item["provider_linkage_warnings"],
            ["uncorroborated", "contextual concern", "low confidence"],
        )
        self.assertNotIn("wrong ticker", " ".join(item["provider_linkage_warnings"]))
        self.assertEqual(item["data_quality"]["freshness"], baseline_quality["freshness"])
        self.assertEqual(item["instrument_id"], "NVDA")

    def test_normal_issuer_case_emits_no_warning(self) -> None:
        opportunity = _opportunity(
            instrument_id="AAPL",
            headline="Apple reports quarterly revenue",
            flags=(),
        )
        rows = assemble_opportunity_review_rows(opportunities=(opportunity,), source="REPLAY")
        self.assertEqual(rows[0].provider_linkage_warnings, ())
        self.assertEqual(rows[0].data_quality["freshness"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
