"""EVIDENCE-01 longer forward qualification tests."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from market_platform_foundation.intelligence.contracts.common import ForecastEstimate, QualityState
from market_platform_foundation.intelligence.forward_qualification import (
    EvidenceClass,
    ForwardEvidenceDisposition,
    ForwardObservationInputV1,
    assess_forward_evidence_qualification,
    build_forward_evidence_qualification_policy,
    build_forward_evidence_qualification_report,
    build_forward_prediction_receipt,
    build_forward_qualification_spec,
)
from market_platform_foundation.intelligence.outcomes.ledger import build_prediction_ledger_entry
from market_platform_foundation.intelligence.outcomes.service import OutcomeSettlementService
from market_platform_foundation.intelligence.outcomes.types import SettlementMode
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.outcome_fixtures import (
    HORIZON_5M,
    ONE_MIN,
    T,
    cutoff_for,
    seed_terminal_trade,
    synthetic_final_forecast,
    target_time_for,
)

DAY_NS = 24 * 60 * 60 * 1_000_000_000
BUILD26_REPORT_PATH = (
    Path(__file__).resolve().parents[2]
    / "artifacts/forward-qualification/BUILD26_QUALIFICATION_REPORT.json"
)


def _forecast_at(
    repo: InMemoryIntelligenceRepository,
    *,
    forecast_id: str,
    decision_time_ns: int,
    probability: float,
):
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
        source_event_refs=(ContractReference(kind=ContractKind.EVENT.value, id=f"anchor-{forecast_id}"),),
    )
    seed_anchor_trade(
        repo,
        event_id=f"anchor-{forecast_id}",
        event_time_ns=decision_time_ns - ONE_MIN,
        available_time_ns=decision_time_ns - ONE_MIN,
    )
    repo.put_snapshot(snapshot)
    direction = "UP" if probability >= 0.5 else "DOWN"
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
        metadata={
            "contributor_role": "PRODUCTION",
            "forecast_stage": "FINAL_FUSED_CALIBRATED",
            "predicted_direction": direction,
        },
    )
    repo.put_forecast(forecast)
    return forecast


def _settled_observation(
    repo: InMemoryIntelligenceRepository,
    *,
    forecast_id: str,
    decision_time_ns: int,
    probability: float,
    session_id: str | None = None,
    quality_state: str = "GOOD",
) -> ForwardObservationInputV1:
    forecast = _forecast_at(
        repo,
        forecast_id=forecast_id,
        decision_time_ns=decision_time_ns,
        probability=probability,
    )
    ledger_entry = build_prediction_ledger_entry(
        forecast,
        repo,
        mode=SettlementMode.ACTUAL_LIVE,
        registered_at_ns=forecast.decision_time_ns,
    )
    repo.put_prediction_ledger_entry(ledger_entry)
    receipt = build_forward_prediction_receipt(
        forecast=forecast,
        ledger_entry=ledger_entry,
        qualification_run_ref="FQRUN-evidence01-test",
        recorded_at_ns=forecast.decision_time_ns,
        evidence_class=EvidenceClass.ACTUAL_FORWARD,
    )
    target_time = target_time_for(forecast)
    seed_terminal_trade(
        repo,
        price=101.0 if probability >= 0.5 else 99.0,
        event_time_ns=target_time,
        available_time_ns=target_time,
        event_id=f"terminal-{forecast_id}",
    )
    settlement_service = OutcomeSettlementService(repo)
    settlement_service.settle(ledger_entry, now_ns=cutoff_for(forecast) + ONE_MIN)
    return ForwardObservationInputV1(
        receipt=receipt,
        forecast=forecast,
        ledger_entry=ledger_entry,
        quality_state=quality_state,
        session_id=session_id,
    )


def _build_cohort(
    count: int,
    *,
    day_span: int = 5,
    sessions: int = 5,
) -> tuple[InMemoryIntelligenceRepository, tuple[ForwardObservationInputV1, ...], int]:
    repo = InMemoryIntelligenceRepository()
    observations: list[ForwardObservationInputV1] = []
    for index in range(count):
        day_offset = (index * day_span) // max(count, 1)
        session = f"session-{index % sessions}"
        decision_time = T + day_offset * DAY_NS + (index % 10) * ONE_MIN
        probability = 0.7 if index % 2 == 0 else 0.3
        observations.append(
            _settled_observation(
                repo,
                forecast_id=f"fc-{index}",
                decision_time_ns=decision_time,
                probability=probability,
                session_id=session,
            )
        )
    last_decision = observations[-1].receipt.decision_time_ns
    settlement_cutoff = last_decision + HORIZON_5M + ONE_MIN * 2
    return repo, tuple(observations), settlement_cutoff


class Evidence01PolicyTests(unittest.TestCase):
    def test_policy_identity_deterministic(self) -> None:
        p1 = build_forward_evidence_qualification_policy()
        p2 = build_forward_evidence_qualification_policy()
        self.assertEqual(p1.policy_id, p2.policy_id)
        self.assertTrue(p1.policy_id.startswith("FEPOL-"))

    def test_policy_extends_build26_thresholds(self) -> None:
        policy = build_forward_evidence_qualification_policy()
        build26 = build_forward_qualification_spec(
            release_candidate_ref="15e7a4f6fc88e5a1c90c6bc3b1b4f8c3a861d2f2",
            source_head="15e7a4f6fc88e5a1c90c6bc3b1b4f8c3a861d2f2",
            qualification_start_ns=T,
        )
        self.assertGreaterEqual(policy.minimum_eligible_predictions, build26.minimum_prediction_count)
        self.assertGreaterEqual(policy.minimum_settled_predictions, build26.minimum_labelable_count)
        self.assertGreaterEqual(policy.minimum_duration_ns, build26.minimum_duration_ns)


class Evidence01ThresholdTests(unittest.TestCase):
    def test_duration_one_below_threshold_insufficient(self) -> None:
        policy = build_forward_evidence_qualification_policy(minimum_duration_ns=DAY_NS * 2)
        repo, observations, settlement_cutoff = _build_cohort(10, day_span=1)
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertEqual(
            assessment.qualification_disposition,
            ForwardEvidenceDisposition.INSUFFICIENT_FORWARD_EVIDENCE,
        )

    def test_eligible_sample_one_below_minimum(self) -> None:
        policy = build_forward_evidence_qualification_policy(minimum_eligible_predictions=6)
        repo, observations, settlement_cutoff = _build_cohort(5)
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertEqual(
            assessment.qualification_disposition,
            ForwardEvidenceDisposition.INSUFFICIENT_FORWARD_EVIDENCE,
        )

    def test_exact_minimum_sample_eligible_path(self) -> None:
        policy = build_forward_evidence_qualification_policy(
            minimum_eligible_predictions=6,
            minimum_settled_predictions=6,
            minimum_distinct_trading_days=1,
            minimum_distinct_sessions=1,
            minimum_duration_ns=0,
            minimum_class_support=1,
        )
        repo, observations, settlement_cutoff = _build_cohort(6, day_span=1, sessions=1)
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertEqual(assessment.observation_summary.eligible_predictions, 6)
        self.assertIn(
            assessment.qualification_disposition,
            {
                ForwardEvidenceDisposition.QUALIFIED,
                ForwardEvidenceDisposition.QUALIFIED_WITH_LIMITATIONS,
            },
        )

    def test_insufficient_settled_outcomes(self) -> None:
        policy = build_forward_evidence_qualification_policy(
            minimum_eligible_predictions=3,
            minimum_settled_predictions=3,
            minimum_distinct_trading_days=1,
            minimum_distinct_sessions=1,
            minimum_duration_ns=0,
        )
        repo = InMemoryIntelligenceRepository()
        observations = []
        for index in range(3):
            forecast = _forecast_at(
                repo,
                forecast_id=f"unsettled-{index}",
                decision_time_ns=T + index * ONE_MIN,
                probability=0.7,
            )
            ledger_entry = build_prediction_ledger_entry(
                forecast,
                repo,
                mode=SettlementMode.ACTUAL_LIVE,
                registered_at_ns=forecast.decision_time_ns,
            )
            repo.put_prediction_ledger_entry(ledger_entry)
            receipt = build_forward_prediction_receipt(
                forecast=forecast,
                ledger_entry=ledger_entry,
                qualification_run_ref="FQRUN-test",
                recorded_at_ns=forecast.decision_time_ns,
            )
            observations.append(
                ForwardObservationInputV1(
                    receipt=receipt,
                    forecast=forecast,
                    ledger_entry=ledger_entry,
                    quality_state="GOOD",
                )
            )
        settlement_cutoff = T + HORIZON_5M + ONE_MIN
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=tuple(observations),
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertEqual(
            assessment.qualification_disposition,
            ForwardEvidenceDisposition.INCOMPLETE_SETTLEMENT,
        )

    def test_inside_unresolved_horizon_excluded(self) -> None:
        policy = build_forward_evidence_qualification_policy(minimum_eligible_predictions=1)
        repo = InMemoryIntelligenceRepository()
        forecast = synthetic_final_forecast(repo, forecast_id="inside-horizon")
        ledger_entry = build_prediction_ledger_entry(
            forecast,
            repo,
            mode=SettlementMode.ACTUAL_LIVE,
            registered_at_ns=forecast.decision_time_ns,
        )
        repo.put_prediction_ledger_entry(ledger_entry)
        receipt = build_forward_prediction_receipt(
            forecast=forecast,
            ledger_entry=ledger_entry,
            qualification_run_ref="FQRUN-test",
            recorded_at_ns=forecast.decision_time_ns,
        )
        observation = ForwardObservationInputV1(
            receipt=receipt,
            forecast=forecast,
            ledger_entry=ledger_entry,
            quality_state="GOOD",
        )
        early_cutoff = forecast.decision_time_ns
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=(observation,),
            repository=repo,
            observation_cutoff_ns=early_cutoff,
            settlement_cutoff_ns=early_cutoff,
        )
        self.assertEqual(assessment.observation_summary.eligible_predictions, 0)

    def test_invalid_quality_excluded(self) -> None:
        policy = build_forward_evidence_qualification_policy(minimum_eligible_predictions=1)
        repo, observations, settlement_cutoff = _build_cohort(1)
        bad = ForwardObservationInputV1(
            receipt=observations[0].receipt,
            forecast=observations[0].forecast,
            ledger_entry=observations[0].ledger_entry,
            quality_state=QualityState.INVALID.value,
        )
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=(bad,),
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertEqual(assessment.observation_summary.excluded_observations, 1)

    def test_duplicate_prediction_ids_deduped(self) -> None:
        policy = build_forward_evidence_qualification_policy(minimum_eligible_predictions=1)
        repo, observations, settlement_cutoff = _build_cohort(1)
        duplicate = observations[0]
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=(duplicate, duplicate),
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertEqual(assessment.observation_summary.eligible_predictions, 1)
        self.assertEqual(
            assessment.observation_summary.exclusions_by_reason.get("DUPLICATE_FORECAST"),
            1,
        )

    def test_future_event_time_ineligible(self) -> None:
        policy = build_forward_evidence_qualification_policy(minimum_eligible_predictions=1)
        repo = InMemoryIntelligenceRepository()
        forecast = synthetic_final_forecast(repo, forecast_id="future-event")
        ledger_entry = build_prediction_ledger_entry(
            forecast,
            repo,
            mode=SettlementMode.ACTUAL_LIVE,
            registered_at_ns=forecast.decision_time_ns,
        )
        ledger_entry = replace(
            ledger_entry,
            anchor_observation={
                **ledger_entry.anchor_observation,
                "event_time_ns": forecast.decision_time_ns + ONE_MIN,
                "available_time_ns": forecast.decision_time_ns - ONE_MIN,
            },
        )
        repo.put_prediction_ledger_entry(ledger_entry)
        receipt = build_forward_prediction_receipt(
            forecast=forecast,
            ledger_entry=ledger_entry,
            qualification_run_ref="FQRUN-test",
            recorded_at_ns=forecast.decision_time_ns,
        )
        observation = ForwardObservationInputV1(
            receipt=receipt,
            forecast=forecast,
            ledger_entry=ledger_entry,
            quality_state="GOOD",
        )
        settlement_cutoff = cutoff_for(forecast) + ONE_MIN
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=(observation,),
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertEqual(
            assessment.observation_summary.exclusions_by_reason.get("FUTURE_EVENT_TIME"),
            1,
        )

    def test_class_support_limitation_not_fabricated_balance(self) -> None:
        policy = build_forward_evidence_qualification_policy(
            minimum_eligible_predictions=4,
            minimum_settled_predictions=4,
            minimum_distinct_trading_days=1,
            minimum_distinct_sessions=1,
            minimum_duration_ns=0,
            minimum_class_support=2,
        )
        repo = InMemoryIntelligenceRepository()
        observations = [
            _settled_observation(
                repo,
                forecast_id=f"up-only-{index}",
                decision_time_ns=T + index * ONE_MIN,
                probability=0.9,
            )
            for index in range(4)
        ]
        settlement_cutoff = observations[-1].receipt.decision_time_ns + HORIZON_5M + ONE_MIN
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=tuple(observations),
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertEqual(
            assessment.qualification_disposition,
            ForwardEvidenceDisposition.QUALIFIED_WITH_LIMITATIONS,
        )
        self.assertIn("INSUFFICIENT_CLASS_SUPPORT", assessment.limitations)

    def test_deterministic_assessment_identity(self) -> None:
        policy = build_forward_evidence_qualification_policy()
        repo, observations, settlement_cutoff = _build_cohort(3)
        a1 = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        a2 = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertEqual(a1.assessment_id, a2.assessment_id)

    def test_changed_cutoff_new_assessment_identity(self) -> None:
        policy = build_forward_evidence_qualification_policy()
        repo, observations, settlement_cutoff = _build_cohort(3)
        a1 = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        a2 = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=settlement_cutoff + ONE_MIN,
            settlement_cutoff_ns=settlement_cutoff + ONE_MIN,
        )
        self.assertNotEqual(a1.assessment_id, a2.assessment_id)

    def test_late_data_after_cutoff_historical_unchanged(self) -> None:
        policy = build_forward_evidence_qualification_policy(minimum_eligible_predictions=2)
        repo, observations, settlement_cutoff = _build_cohort(2)
        historical = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        extra = _settled_observation(
            repo,
            forecast_id="late-arrival",
            decision_time_ns=settlement_cutoff + DAY_NS,
            probability=0.8,
        )
        reassess_same_cutoff = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations + (extra,),
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertEqual(historical.assessment_id, reassess_same_cutoff.assessment_id)
        self.assertEqual(
            historical.qualification_disposition,
            reassess_same_cutoff.qualification_disposition,
        )

    def test_performance_not_evaluated(self) -> None:
        policy = build_forward_evidence_qualification_policy()
        repo, observations, settlement_cutoff = _build_cohort(2)
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        self.assertFalse(assessment.performance_evaluated)


class Evidence01AuthoritySeparationTests(unittest.TestCase):
    def test_no_broker_submit_path(self) -> None:
        import market_platform_foundation.intelligence.forward_qualification.evidence01.assessment as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("submit_order", source)
        self.assertNotIn("broker", source.lower())

    def test_no_model_promotion_path(self) -> None:
        with mock.patch(
            "market_platform_foundation.intelligence.promotion.engine.PromotionEngine.evaluate_promotion"
        ) as promote:
            policy = build_forward_evidence_qualification_policy()
            repo, observations, settlement_cutoff = _build_cohort(1)
            assess_forward_evidence_qualification(
                policy=policy,
                observations=observations,
                repository=repo,
                observation_cutoff_ns=settlement_cutoff,
                settlement_cutoff_ns=settlement_cutoff,
            )
            promote.assert_not_called()


class Evidence01HistoricalPreservationTests(unittest.TestCase):
    def test_build26_artifact_unchanged(self) -> None:
        self.assertTrue(BUILD26_REPORT_PATH.exists())
        payload = json.loads(BUILD26_REPORT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["disposition"], "INSUFFICIENT_FORWARD_EVIDENCE")

    def test_report_preserves_build26_disposition(self) -> None:
        policy = build_forward_evidence_qualification_policy()
        repo, observations, settlement_cutoff = _build_cohort(1)
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=observations,
            repository=repo,
            observation_cutoff_ns=settlement_cutoff,
            settlement_cutoff_ns=settlement_cutoff,
        )
        report = build_forward_evidence_qualification_report(policy=policy, assessment=assessment)
        self.assertEqual(report.build26_historical_disposition, "INSUFFICIENT_FORWARD_EVIDENCE")
        self.assertEqual(report.limitation_status, "STILL_OPEN")


class Evidence01DefaultPolicyCurrentEvidenceTests(unittest.TestCase):
    def test_empty_observations_still_insufficient(self) -> None:
        policy = build_forward_evidence_qualification_policy()
        repo = InMemoryIntelligenceRepository()
        assessment = assess_forward_evidence_qualification(
            policy=policy,
            observations=(),
            repository=repo,
            observation_cutoff_ns=T,
            settlement_cutoff_ns=T,
        )
        self.assertEqual(
            assessment.qualification_disposition,
            ForwardEvidenceDisposition.INSUFFICIENT_FORWARD_EVIDENCE,
        )
        self.assertTrue(assessment.remaining_requirements)
