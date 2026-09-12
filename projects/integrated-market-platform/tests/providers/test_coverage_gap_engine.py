"""Tests for coverage gap engine and campaign readiness (Wave B package 2)."""

from __future__ import annotations

import unittest
from pathlib import Path

from market_platform_foundation.intelligence.paper_forward_bridge.campaign_readiness import (
    CampaignReadinessDisposition,
    evaluate_campaign_readiness,
)
from market_platform_foundation.providers.capability_contract import (
    CapabilityAccessState,
    CapabilityMatrixSnapshot,
    CapabilitySupportLevel,
    CampaignRole,
    ProviderCapabilityEntry,
    ProviderCapabilityRecord,
)
from market_platform_foundation.providers.capability_requirements import (
    FTEP_V1_001_ES_NEWS_PROFILE,
    get_campaign_requirement_profile,
)
from market_platform_foundation.providers.coverage_gap_engine import (
    GapDisposition,
    load_wave_a_gap_catalog,
    resolve_coverage_gaps,
    resolve_coverage_gaps_for_campaign,
)


class CoverageGapEngineTests(unittest.TestCase):
    def test_ftep_profile_includes_es_news_templates(self) -> None:
        profile = get_campaign_requirement_profile("FTEP-V1-001")
        self.assertEqual(profile.profile_id, FTEP_V1_001_ES_NEWS_PROFILE.profile_id)
        req_ids = {row.requirement_id for row in profile.capability_requirements}
        self.assertIn("futures.es_quote.moomoo", req_ids)
        self.assertIn("news.finviz_export", req_ids)

    def test_us_futures_quote_unknown_is_blocking(self) -> None:
        root = Path(__file__).resolve().parents[2]
        report = resolve_coverage_gaps_for_campaign(
            "FTEP-V1-001",
            repository_root=root,
            readiness_report={"providers": []},
        )
        self.assertEqual(report.disposition, GapDisposition.BLOCKING)
        self.assertIn("CAP-REQ-futures.es_quote.moomoo", report.blockers)
        self.assertIn("G-A6", report.blockers)
        self.assertIn("WAVE-A-001", report.blockers)
        self.assertIn("WAVE-A-002", report.blockers)
        self.assertNotIn("CG-01", report.blockers)
        self.assertNotIn("CG-02", report.blockers)

    def test_gap_resolution_is_deterministic(self) -> None:
        root = Path(__file__).resolve().parents[2]
        first = resolve_coverage_gaps_for_campaign(
            "FTEP-V1-001",
            repository_root=root,
            readiness_report={"providers": []},
        )
        second = resolve_coverage_gaps_for_campaign(
            "FTEP-V1-001",
            repository_root=root,
            readiness_report={"providers": []},
        )
        self.assertEqual(first.blockers, second.blockers)
        self.assertEqual(
            [row.gap_id for row in first.gaps],
            [row.gap_id for row in second.gaps],
        )

    def test_satisfied_capability_requirement_when_promoted(self) -> None:
        snapshot = CapabilityMatrixSnapshot(
            observed_at="2026-09-11T23:00:00Z",
            sources=(),
            providers=(
                ProviderCapabilityRecord(
                    provider_id="MOOMOO",
                    access_state=CapabilityAccessState.CAMPAIGN_BOUND,
                    campaign_role=CampaignRole.AUTHORITY,
                    support_level=CapabilitySupportLevel.KNOWN_SUPPORTED,
                    capabilities=(
                        ProviderCapabilityEntry(
                            "US_FUTURES_QUOTE",
                            CapabilitySupportLevel.KNOWN_SUPPORTED,
                            access_state=CapabilityAccessState.SAMPLE_VERIFIED,
                        ),
                        ProviderCapabilityEntry(
                            "US_EQUITY_L1",
                            CapabilitySupportLevel.KNOWN_SUPPORTED,
                            access_state=CapabilityAccessState.CAMPAIGN_BOUND,
                        ),
                    ),
                    verification_evidence=("evidence/fixture.json",),
                ),
            ),
        )
        catalog = load_wave_a_gap_catalog(Path(__file__).resolve().parents[2])
        report = resolve_coverage_gaps(
            profile=FTEP_V1_001_ES_NEWS_PROFILE,
            snapshot=snapshot,
            wave_a_catalog={key: catalog[key] for key in ("WAVE-A-001",) if key in catalog},
        )
        futures_gap = next(
            row for row in report.gaps if row.gap_id == "CAP-REQ-futures.es_quote.moomoo"
        )
        self.assertEqual(futures_gap.disposition, GapDisposition.SATISFIED)
        g_a6 = next(row for row in report.gaps if row.gap_id == "G-A6")
        self.assertEqual(g_a6.disposition, GapDisposition.SATISFIED)


class CampaignReadinessTests(unittest.TestCase):
    def test_ftep_v1_001_fail_closed(self) -> None:
        root = Path(__file__).resolve().parents[2]
        result = evaluate_campaign_readiness(
            "FTEP-V1-001",
            repository_root=root,
            readiness_report={"providers": []},
        )
        self.assertEqual(result.disposition, CampaignReadinessDisposition.NOT_READY)
        self.assertTrue(any("ACTIVATION_MANIFEST" in item for item in result.blockers))
        self.assertTrue(any(item.startswith("COVERAGE_GAP:") for item in result.blockers))
        self.assertIn("COVERAGE_GAP:WAVE-A-002", result.blockers)

    def test_known_es_news_blockers_present(self) -> None:
        root = Path(__file__).resolve().parents[2]
        result = evaluate_campaign_readiness(
            "FTEP-V1-001",
            repository_root=root,
            readiness_report={"providers": []},
        )
        coverage_blockers = {
            item.removeprefix("COVERAGE_GAP:")
            for item in result.blockers
            if item.startswith("COVERAGE_GAP:")
        }
        self.assertIn("CAP-REQ-futures.es_quote.moomoo", coverage_blockers)
        self.assertIn("WAVE-A-003", coverage_blockers)


if __name__ == "__main__":
    unittest.main()
