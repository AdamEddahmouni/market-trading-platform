"""Non-semantic provider coverage-gap and planner fail-closed contracts."""

from __future__ import annotations

import unittest

from market_platform_foundation.providers.capability_requirements import (
    get_campaign_requirement_profile,
)
from market_platform_foundation.providers.coverage_gap_engine import (
    CoverageGap,
    CoverageGapReport,
    GapDisposition,
)
from market_platform_foundation.providers.identity import InstrumentIdentity
from market_platform_foundation.providers.planner import QueryRequest


class CoverageGapFailClosedTests(unittest.TestCase):
    def test_unknown_campaign_profile_fail_closed(self) -> None:
        with self.assertRaises(KeyError) as ctx:
            get_campaign_requirement_profile("FTEP-V1-999")
        self.assertIn("UNKNOWN_CAMPAIGN_REQUIREMENT_PROFILE:FTEP-V1-999", str(ctx.exception))

    def test_gap_and_report_to_dict_are_structural_not_scores(self) -> None:
        gap = CoverageGap(
            gap_id="CAP-REQ-equity.us_l1.moomoo",
            disposition=GapDisposition.BLOCKING,
            source="capability_requirement",
            summary="US equity L1 not campaign-bound",
            reason_code="ACCESS_STATE_BELOW_MINIMUM",
            evidence_refs=("evidence/fixture.json",),
        )
        payload = gap.to_dict()
        self.assertEqual(
            set(payload),
            {
                "disposition",
                "evidence_refs",
                "gap_id",
                "reason_code",
                "source",
                "summary",
            },
        )
        self.assertNotIn("score", payload)
        self.assertNotIn("rank", payload)
        report = CoverageGapReport(
            profile_id="FTEP-V1-002",
            campaign_slug="FTEP-V1-002",
            disposition=GapDisposition.SATISFIED,
            gaps=(gap,),
            blockers=(),
            metadata={"wave_a_overlay": "DEFERRED"},
        )
        body = report.to_dict()
        self.assertEqual(body["campaign_slug"], "FTEP-V1-002")
        self.assertEqual(body["blockers"], [])
        self.assertNotIn("empirical_active", body)

    def test_v1_002_lists_wave_a_002_without_making_it_a_blocker_id(self) -> None:
        profile = get_campaign_requirement_profile("FTEP-V1-002")
        self.assertIn("WAVE-A-002", profile.wave_a_gap_ids)
        req_ids = {row.requirement_id for row in profile.capability_requirements}
        self.assertNotIn("WAVE-A-002", req_ids)


class QueryRequestFailClosedTests(unittest.TestCase):
    def _instrument(self) -> InstrumentIdentity:
        return InstrumentIdentity("venue", "AAPL", "equity", "NASDAQ", "USD")

    def test_live_as_of_unsupported(self) -> None:
        with self.assertRaisesRegex(ValueError, "LIVE_AS_OF_UNSUPPORTED"):
            QueryRequest(
                capability_id="quote",
                instrument=self._instrument(),
                as_of_time_ns=1,
                freshness_max_age_ns=None,
                license_purpose="research",
                mode="live",
            )

    def test_unknown_query_mode_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "QUERY_MODE_INVALID"):
            QueryRequest(
                capability_id="quote",
                instrument=self._instrument(),
                as_of_time_ns=None,
                freshness_max_age_ns=None,
                license_purpose="research",
                mode="production",
            )


if __name__ == "__main__":
    unittest.main()
