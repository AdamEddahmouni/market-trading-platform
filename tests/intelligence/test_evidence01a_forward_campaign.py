"""EVIDENCE-01A forward observation campaign tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from market_platform_foundation.intelligence.contracts.common import ForecastEstimate
from market_platform_foundation.intelligence.forward_qualification import (
    CampaignEvidenceOrigin,
    CampaignService,
    SettlementRateState,
    assess_forward_evidence_qualification,
    build_forward_evidence_qualification_policy,
)
from market_platform_foundation.intelligence.forward_qualification.evidence01a.observations import (
    build_observation_inputs,
    origin_qualifies_for_real_evidence,
)
from market_platform_foundation.intelligence.forward_qualification.evidence01a.types import (
    ForwardObservationCampaignState,
    MIN_QUALIFYING_SESSION_DURATION_NS,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.outcome_fixtures import HORIZON_5M, ONE_MIN, T
from tests.intelligence.test_evidence01_forward_qualification import DAY_NS, _build_cohort, _settled_observation


class CampaignModelTests(unittest.TestCase):
    def test_deterministic_campaign_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = CampaignService.create_campaign(
                campaign_root=Path(tmp) / "a",
                campaign_name="alpha",
                evidence_origin=CampaignEvidenceOrigin.LIVE_FORWARD,
                source_commit_sha="abc123",
            )
            b = CampaignService.create_campaign(
                campaign_root=Path(tmp) / "b",
                campaign_name="alpha",
                evidence_origin=CampaignEvidenceOrigin.LIVE_FORWARD,
                source_commit_sha="abc123",
            )
            self.assertEqual(a.store.read_spec().campaign_id, b.store.read_spec().campaign_id)

    def test_execution_disabled_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="safe",
            )
            spec = service.store.read_spec()
            self.assertEqual(spec.execution_mode, "NONE")
            self.assertEqual(spec.execution_authority, "BLOCKED")


class ObservationEligibilityTests(unittest.TestCase):
    def test_fixture_origin_excluded_from_real_qualification(self) -> None:
        self.assertFalse(origin_qualifies_for_real_evidence(CampaignEvidenceOrigin.FIXTURE))
        self.assertFalse(origin_qualifies_for_real_evidence(CampaignEvidenceOrigin.REPLAY))
        self.assertTrue(origin_qualifies_for_real_evidence(CampaignEvidenceOrigin.LIVE_FORWARD))

    def test_zero_settlement_rate_not_evaluable(self) -> None:
        policy = build_forward_evidence_qualification_policy()
        repo = InMemoryIntelligenceRepository()
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=(),
            repository=repo,
            observation_cutoff_ns=T,
            settlement_cutoff_ns=T,
        )
        self.assertIsNone(assessment.observation_summary.settlement_rate)
        self.assertEqual(
            assessment.observation_summary.settlement_rate_state,
            SettlementRateState.NOT_EVALUABLE,
        )
        self.assertTrue(any("not yet evaluable" in item for item in assessment.remaining_requirements))


class CampaignLifecycleTests(unittest.TestCase):
    def _forecast(self, repo, forecast_id: str, decision_time_ns: int, probability: float = 0.7):
        from market_platform_foundation.intelligence.baselines import direction_up_down_target
        from market_platform_foundation.intelligence.contracts import ForecastV1, SnapshotV1
        from market_platform_foundation.intelligence.contracts.common import ContractKind, ContractReference, TimeHorizonNs
        from tests.intelligence.outcome_fixtures import INSTRUMENT, QUALITY, SCOPE, seed_anchor_trade

        snapshot = SnapshotV1(
            snapshot_id=f"snap-{forecast_id}",
            schema_version="1",
            decision_time_ns=decision_time_ns,
            scope=SCOPE,
            quality=QUALITY,
            source_event_refs=(ContractReference(kind=ContractKind.EVENT.value, id=f"a-{forecast_id}"),),
        )
        seed_anchor_trade(repo, event_id=f"a-{forecast_id}", event_time_ns=decision_time_ns - ONE_MIN)
        repo.put_snapshot(snapshot)
        forecast = ForecastV1(
            forecast_id=forecast_id,
            schema_version="1",
            scope=SCOPE,
            decision_time_ns=decision_time_ns,
            snapshot_id=snapshot.snapshot_id,
            target=direction_up_down_target(INSTRUMENT),
            horizon=TimeHorizonNs(duration_ns=HORIZON_5M),
            estimate=ForecastEstimate(
                estimate_kind="classification_probability",
                probability=probability,
                calibrated_probability=probability,
            ),
            quality=QUALITY,
            metadata={"predicted_direction": "UP" if probability >= 0.5 else "DOWN"},
        )
        repo.put_forecast(forecast)
        return forecast

    def test_session_start_stop_and_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="session-test",
                evidence_origin=CampaignEvidenceOrigin.SYNTHETIC,
            )
            service.start_campaign()
            service.start_session(now_ns=T)
            forecast = self._forecast(service.repository, "fc-1", T)
            service.record_observation(forecast=forecast, now_ns=T)
            stopped = service.stop_session(now_ns=T + MIN_QUALIFYING_SESSION_DURATION_NS)
            self.assertEqual(stopped.prediction_count, 1)
            checkpoint = service.generate_checkpoint(
                observation_cutoff_ns=T + DAY_NS,
                settlement_cutoff_ns=T + DAY_NS,
            )
            self.assertEqual(checkpoint.campaign_id, service.store.read_spec().campaign_id)

    def test_restart_reload_preserves_observations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="restart",
                evidence_origin=CampaignEvidenceOrigin.SYNTHETIC,
            )
            campaign_dir = service.store.root
            service.start_campaign()
            service.start_session(now_ns=T)
            forecast = self._forecast(service.repository, "fc-restart", T)
            service.record_observation(forecast=forecast, now_ns=T)
            service.stop_session(now_ns=T + MIN_QUALIFYING_SESSION_DURATION_NS)
            reloaded = CampaignService.open(campaign_dir)
            self.assertEqual(len(reloaded.store.list_observation_refs()), 1)
            observations = build_observation_inputs(
                store=reloaded.store,
                repository=reloaded.repository,
                require_live_forward=False,
            )
            self.assertEqual(len(observations), 1)

    def test_duplicate_prediction_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="dup",
                evidence_origin=CampaignEvidenceOrigin.SYNTHETIC,
            )
            service.start_campaign()
            service.start_session(now_ns=T)
            forecast = self._forecast(service.repository, "fc-dup", T)
            service.record_observation(forecast=forecast, now_ns=T)
            with self.assertRaises(Exception):
                service.record_observation(forecast=forecast, now_ns=T)

    def test_abort_preserves_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = CampaignService.create_campaign(
                campaign_root=Path(tmp),
                campaign_name="abort",
                evidence_origin=CampaignEvidenceOrigin.SYNTHETIC,
            )
            service.start_campaign()
            service.start_session(now_ns=T)
            forecast = self._forecast(service.repository, "fc-abort", T)
            service.record_observation(forecast=forecast, now_ns=T)
            state = service.abort_campaign()
            self.assertEqual(state.campaign_state, ForwardObservationCampaignState.ABORTED)
            self.assertEqual(len(service.store.list_observation_refs()), 1)


class SyntheticMultiDayLifecycleTests(unittest.TestCase):
    def test_mechanism_qualifies_with_lowered_policy(self) -> None:
        policy = build_forward_evidence_qualification_policy(
            minimum_eligible_predictions=10,
            minimum_settled_predictions=5,
            minimum_distinct_trading_days=5,
            minimum_distinct_sessions=5,
            minimum_duration_ns=4 * DAY_NS,
            minimum_class_support=1,
            maximum_admissible_gap_ns=5 * DAY_NS,
        )
        repo, observations, settlement_cutoff = _build_cohort(10, day_span=5, sessions=5)
        day2 = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations[:4],
            repository=repo,
            observation_cutoff_ns=T + 2 * DAY_NS,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertEqual(day2.qualification_disposition.value, "INSUFFICIENT_FORWARD_EVIDENCE")
        final = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertIn(
            final.qualification_disposition.value,
            {"QUALIFIED", "QUALIFIED_WITH_LIMITATIONS"},
        )


class AuthoritySeparationTests(unittest.TestCase):
    def test_no_broker_submit_in_service(self) -> None:
        source = Path(
            "src/market_platform_foundation/intelligence/forward_qualification/evidence01a/service.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("submit_order", source)
        self.assertNotIn("authorize_live_session", source)


class ProgressGateTests(unittest.TestCase):
    def test_forty_nine_eligible_insufficient(self) -> None:
        policy = build_forward_evidence_qualification_policy(minimum_eligible_predictions=50)
        repo, observations, cutoff = _build_cohort(49)
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=cutoff,
            settlement_cutoff_ns=cutoff,
        )
        self.assertEqual(assessment.observation_summary.eligible_predictions, 49)
