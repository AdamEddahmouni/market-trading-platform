"""Opportunity Engine freshness binding tests (G7 axes, not a new G-gate)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "intelligence"))

from market_platform_foundation.intelligence.contracts import (
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.data_quality import (
    project_opportunity_data_quality,
)
from market_platform_foundation.intelligence.opportunity.freshness import (
    CLOCK_UTC_NS,
    DEFAULT_STALE_AFTER_NS,
    FRESHNESS_FRESH,
    FRESHNESS_NOT_APPLICABLE,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    OpportunityFreshnessPolicy,
    evaluate_opportunity_freshness,
    merge_freshness_into_payload,
)
from market_platform_foundation.intelligence.opportunity.ingest import assemble_opportunity_review_rows
from market_platform_foundation.intelligence.opportunity.ranking import rank_review_rows
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction
from market_platform_foundation.providers.runtime_capability import (
    DataTimeliness,
    EntitlementState,
    RuntimeCapabilityState,
)

T0 = 1_700_000_000_000_000_000
SCOPE = IntelligenceScope(instrument_ids=("AAPL",), context_id="regular")
QUALITY = QualitySummary(state=QualityState.GOOD)


def _opportunity(opportunity_id: str = "opp-fresh") -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=SCOPE,
        created_at_ns=T0,
        quality=QUALITY,
        side=OpportunitySide.LONG,
        reason_summary="test",
    )


class OpportunityFreshnessEvaluatorTests(unittest.TestCase):
    def test_fresh_within_threshold(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0 + 1_000,
            last_source_time_ns=T0,
        )
        self.assertEqual(result.status, FRESHNESS_FRESH)
        self.assertTrue(result.actionable)
        self.assertEqual(result.clock, CLOCK_UTC_NS)
        self.assertEqual(result.age_ns, 1_000)
        self.assertEqual(result.reason_code, "FRESH")

    def test_stale_beyond_threshold(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0 + DEFAULT_STALE_AFTER_NS + 1,
            last_source_time_ns=T0,
        )
        self.assertEqual(result.status, FRESHNESS_STALE)
        self.assertFalse(result.actionable)
        self.assertEqual(result.reason_code, "STALE_AFTER_THRESHOLD")

    def test_unknown_missing_as_of(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            last_source_time_ns=T0,
        )
        self.assertEqual(result.status, FRESHNESS_UNKNOWN)
        self.assertFalse(result.actionable)
        self.assertEqual(result.reason_code, "MISSING_AS_OF")

    def test_unknown_missing_source_time(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0,
            runtime_capability={"timeliness": DataTimeliness.REAL_TIME},
        )
        self.assertEqual(result.status, FRESHNESS_UNKNOWN)
        self.assertEqual(result.reason_code, "MISSING_SOURCE_TIME")

    def test_replay_is_not_applicable(self) -> None:
        result = evaluate_opportunity_freshness(source="REPLAY", as_of_time_ns=T0, last_source_time_ns=T0)
        self.assertEqual(result.status, FRESHNESS_NOT_APPLICABLE)
        self.assertFalse(result.actionable)
        self.assertNotEqual(result.status, FRESHNESS_FRESH)

    def test_fixture_is_not_applicable(self) -> None:
        result = evaluate_opportunity_freshness(source="FIXTURE")
        self.assertEqual(result.status, FRESHNESS_NOT_APPLICABLE)

    def test_session_closed_is_not_applicable(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0,
            last_source_time_ns=T0,
            session_state="CLOSED",
        )
        self.assertEqual(result.status, FRESHNESS_NOT_APPLICABLE)
        self.assertEqual(result.reason_code, "SESSION_NOT_OPEN")

    def test_session_outside_is_not_applicable(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0,
            last_source_time_ns=T0,
            session_state="OUTSIDE",
        )
        self.assertEqual(result.status, FRESHNESS_NOT_APPLICABLE)

    def test_delayed_when_realtime_required_fail_closed(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0,
            last_source_time_ns=T0,
            runtime_capability={"timeliness": DataTimeliness.DELAYED},
            policy=OpportunityFreshnessPolicy(realtime_required=True),
        )
        self.assertEqual(result.status, FRESHNESS_UNKNOWN)
        self.assertFalse(result.actionable)
        self.assertEqual(result.reason_code, "DELAYED_WHEN_REALTIME_REQUIRED")
        self.assertNotEqual(result.status, FRESHNESS_FRESH)

    def test_delayed_allowed_is_honest_fresh(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0 + 1,
            last_source_time_ns=T0,
            runtime_capability={"timeliness": DataTimeliness.DELAYED},
            policy=OpportunityFreshnessPolicy(realtime_required=False),
        )
        self.assertEqual(result.status, FRESHNESS_FRESH)
        self.assertEqual(result.reason_code, "DELAYED_ALLOWED")
        self.assertEqual(result.timeliness, "DELAYED")

    def test_missing_snapshot_is_unknown_not_fresh(self) -> None:
        result = evaluate_opportunity_freshness(source="OBSERVATIONAL", as_of_time_ns=T0)
        self.assertEqual(result.status, FRESHNESS_UNKNOWN)
        self.assertEqual(result.reason_code, "NO_EVENT")
        self.assertFalse(result.actionable)

    def test_not_entitled_does_not_claim_fresh(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0,
            last_source_time_ns=T0,
            runtime_capability={"entitlement": EntitlementState.NOT_ENTITLED},
        )
        self.assertNotEqual(result.status, FRESHNESS_FRESH)
        self.assertEqual(result.reason_code, "NOT_ENTITLED")

    def test_same_inputs_two_clocks_fresh_then_stale(self) -> None:
        policy = OpportunityFreshnessPolicy(stale_after_ns=10)
        fresh = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0 + 1,
            last_source_time_ns=T0,
            policy=policy,
        )
        stale = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0 + 11,
            last_source_time_ns=T0,
            policy=policy,
        )
        self.assertEqual(fresh.status, FRESHNESS_FRESH)
        self.assertEqual(stale.status, FRESHNESS_STALE)

    def test_g7_registry_stale_maps_to_stale(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0,
            last_source_time_ns=T0,
            runtime_capability={
                "timeliness": DataTimeliness.STALE,
                "runtime_state": RuntimeCapabilityState.STALE,
            },
        )
        self.assertEqual(result.status, FRESHNESS_STALE)
        self.assertEqual(result.reason_code, "G7_RUNTIME_STALE")
        self.assertFalse(result.actionable)

    def test_book_invalid_never_fresh(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0,
            last_source_time_ns=T0,
            book_validity="INVALID",
        )
        self.assertNotEqual(result.status, FRESHNESS_FRESH)
        self.assertEqual(result.reason_code, "BOOK_INVALID")

    def test_utc_ns_clock_and_payload_round_trip(self) -> None:
        result = evaluate_opportunity_freshness(
            source="OBSERVATIONAL",
            as_of_time_ns=T0,
            last_source_time_ns=T0,
        )
        payload = merge_freshness_into_payload({"opportunity_id": "opp-1"}, result)
        self.assertEqual(payload["freshness"]["clock"], CLOCK_UTC_NS)
        self.assertEqual(payload["freshness"]["status"], FRESHNESS_FRESH)
        self.assertEqual(payload["opportunity_id"], "opp-1")


class OpportunityFreshnessHonestyAndGateTests(unittest.TestCase):
    def test_recorded_artifacts_honesty_unchanged(self) -> None:
        quality = project_opportunity_data_quality(
            source="RECORDED_ARTIFACTS",
            live_observational_env=True,
        )
        self.assertEqual(quality["freshness"], "UNAVAILABLE")
        self.assertEqual(quality["entitlement"], "UNAVAILABLE")
        self.assertEqual(quality["freshness_evaluation"]["status"], FRESHNESS_NOT_APPLICABLE)

    def test_replay_honesty_unchanged(self) -> None:
        quality = project_opportunity_data_quality(source="REPLAY")
        self.assertEqual(quality["freshness"], "UNAVAILABLE")
        self.assertEqual(quality["freshness_evaluation"]["status"], FRESHNESS_NOT_APPLICABLE)

    def test_live_observational_source_still_unavailable(self) -> None:
        live = project_opportunity_data_quality(source="LIVE_OBSERVATIONAL")
        self.assertEqual(live["status"], "UNAVAILABLE")
        self.assertEqual(live["reason_codes"], ["LIVE_OBSERVATIONAL_NOT_ENGINE_QUALITY"])
        self.assertEqual(live["freshness_evaluation"]["status"], FRESHNESS_UNKNOWN)

    def test_stale_fail_closes_eligibility_and_ranking(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity(),),
            assessments_by_opportunity={"opp-fresh": AssessmentAction.EMIT},
            source="OBSERVATIONAL",
            as_of_time_ns=T0 + DEFAULT_STALE_AFTER_NS + 1,
            last_source_time_ns=T0,
        )
        self.assertEqual(rows[0].lifecycle_state, "INELIGIBLE")
        self.assertFalse(rows[0].accepted)
        self.assertEqual(rows[0].data_quality["freshness_evaluation"]["status"], FRESHNESS_STALE)
        self.assertEqual(rank_review_rows(rows), ())

    def test_unknown_fail_closes_eligibility(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity("opp-unknown"),),
            assessments_by_opportunity={"opp-unknown": AssessmentAction.EMIT},
            source="OBSERVATIONAL",
            as_of_time_ns=T0,
        )
        self.assertEqual(rows[0].lifecycle_state, "INELIGIBLE")
        self.assertEqual(rows[0].data_quality["freshness_evaluation"]["reason_code"], "NO_EVENT")

    def test_replay_emit_stays_eligible(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity("opp-replay"),),
            assessments_by_opportunity={"opp-replay": AssessmentAction.EMIT},
            source="REPLAY",
        )
        self.assertEqual(rows[0].lifecycle_state, "ELIGIBLE")
        self.assertEqual(rows[0].data_quality["freshness_evaluation"]["status"], FRESHNESS_NOT_APPLICABLE)

    def test_summary_carries_explainable_freshness(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(_opportunity("opp-explain"),),
            source="OBSERVATIONAL",
            as_of_time_ns=T0 + 1,
            last_source_time_ns=T0,
        )
        evaluation = rows[0].data_quality["freshness_evaluation"]
        self.assertEqual(evaluation["status"], FRESHNESS_FRESH)
        self.assertEqual(evaluation["reason_code"], "FRESH")
        self.assertEqual(evaluation["clock"], CLOCK_UTC_NS)


class OpportunityFreshnessReconstructionTests(unittest.TestCase):
    def test_reconstruct_surfaces_payload_freshness(self) -> None:
        import os
        import sys
        import tempfile
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(root / "src"))
        sys.path.insert(0, str(root / "tests" / "intelligence"))

        from market_platform_foundation.intelligence.paper_forward_bridge import (
            ForwardTestMode,
            ForwardTestService,
            create_forward_test_repository,
        )
        from market_platform_foundation.intelligence.paper_forward_bridge.reconstruction import (
            reconstruct_campaign,
        )
        from market_platform_foundation.local_state.startup import (
            open_local_state,
            reset_local_state_for_tests,
        )
        from forward_test_activation_support import (
            BASELINE_POLICY,
            CAMPAIGN_SLUG,
            create_activated_session,
            enable_test_campaigns_root,
            seed_baseline_campaign,
        )

        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["IMP_STATE_DIR"] = tmp.name
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ["IMP_FORWARD_TEST_EVAL_FORCE"] = "1"
        campaigns_root = enable_test_campaigns_root(Path(tmp.name))
        seed_baseline_campaign(campaigns_root)
        reset_local_state_for_tests()
        try:
            local = open_local_state(force=True)
            assert local is not None
            service = ForwardTestService(create_forward_test_repository(connection=local.connection))
            session = create_activated_session(
                service,
                campaigns_root,
                evaluation_horizon_ns=3_600_000_000_000,
                created_at_ns=T0,
            )
            evaluation = evaluate_opportunity_freshness(
                source="OBSERVATIONAL",
                as_of_time_ns=T0,
                last_source_time_ns=T0,
            )
            payload = merge_freshness_into_payload(
                {"opportunity_id": "opp-link-fresh", "signal_id": "sig-fresh"},
                evaluation,
            )
            decision = service.create_decision(
                account_id="paper-a",
                mode="PAPER",
                session_id=session.session_id,
                symbol="ACME",
                direction="BUY",
                decision_time_ns=T0,
                source_time_ns=T0 - 1,
                strategy_id=BASELINE_POLICY,
                strategy_version=POLICY_VERSION,
                test_mode=ForwardTestMode.SIGNAL_ONLY,
                decision_payload=payload,
            )
            reconstructed = reconstruct_campaign(
                local.connection,
                account_id="paper-a",
                campaign_id=CAMPAIGN_SLUG,
            )
            row = reconstructed["decisions"][0]
            self.assertEqual(row["opportunity_id"], "opp-link-fresh")
            self.assertEqual(row["freshness"]["status"], FRESHNESS_FRESH)
            self.assertEqual(row["freshness"]["reason_code"], "FRESH")
            self.assertEqual(decision.decision_payload["freshness"]["status"], FRESHNESS_FRESH)
        finally:
            reset_local_state_for_tests()
            os.environ.pop("IMP_STATE_DIR", None)
            os.environ.pop("IMP_PERSIST_STATE", None)
            os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
            os.environ.pop("IMP_FORWARD_TEST_EVAL_FORCE", None)
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
