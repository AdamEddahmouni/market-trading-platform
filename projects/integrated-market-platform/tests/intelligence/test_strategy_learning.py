"""Focused tests for the bounded, governed strategy learning boundary."""

from __future__ import annotations

from dataclasses import replace
import unittest

from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    Direction,
    ForecastEstimate,
    ForecastTarget,
    ForecastV1,
    IntelligenceScope,
    OutcomeResolutionStatus,
    OutcomeV1,
    QualityState,
    QualitySummary,
    TimeHorizonNs,
)
from market_platform_foundation.intelligence.quality.models import AvailabilityState
from market_platform_foundation.intelligence.research_experiments.types import EvidenceTier
from market_platform_foundation.intelligence.contracts.strategy_match import (
    StrategyMatch,
    StrategyMatchDisposition,
)
from market_platform_foundation.portfolio.attribution import StrategyAttributionV1
from market_platform_foundation.strategy.learning import (
    LearningEligibility,
    LearningJoinV1,
    LearningLabelState,
    LearningObservationV1,
    LearningPolicyV1,
    LearningSettlementState,
    ResearchHandoffV1,
    evaluate_learning_join,
    evaluate_learning_joins,
    emit_research_handoff,
    learning_evaluation_v1_from_dict,
    learning_evaluation_v1_to_dict,
    learning_join_v1_from_dict,
    learning_join_v1_to_dict,
    learning_observation_v1_from_dict,
    learning_observation_v1_to_dict,
    learning_policy_v1_from_dict,
    learning_policy_v1_to_dict,
    research_handoff_v1_from_dict,
    research_handoff_v1_to_dict,
)


T = 1_700_000_000_000_000_000
HORIZON = 300_000_000_000
QUALITY = QualitySummary(state=QualityState.GOOD)


def _forecast(*, forecast_id: str = "forecast-1", decision_time_ns: int = T) -> ForecastV1:
    return ForecastV1(
        forecast_id=forecast_id,
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=("AAPL",)),
        decision_time_ns=decision_time_ns,
        snapshot_id="snapshot-1",
        target=ForecastTarget(
            target_kind="direction",
            instrument_id="AAPL",
            parameters={},
        ),
        horizon=TimeHorizonNs(duration_ns=HORIZON),
        estimate=ForecastEstimate(estimate_kind="classification_probability", probability=0.7),
        quality=QUALITY,
        metadata={"account_id": "acct-1", "mode": "PAPER"},
    )


def _outcome(*, forecast_id: str = "forecast-1", settled: bool = True) -> OutcomeV1:
    return OutcomeV1(
        outcome_id=f"outcome-{forecast_id}",
        schema_version="1",
        forecast_id=forecast_id,
        adjudicated_at_ns=T + HORIZON,
        resolution_status=(
            OutcomeResolutionStatus.SETTLED
            if settled
            else OutcomeResolutionStatus.UNLABELABLE
        ),
        quality=QUALITY,
        realized_return=0.01 if settled else None,
        realized_direction=Direction.LONG if settled else None,
        unlabelable_reason=None if settled else "MISSING_TERMINAL_OBSERVATION",
    )


def _match(*, strategy_hash: str = "strategy-hash-1", decision_time_ns: int = T) -> StrategyMatch:
    return StrategyMatch(
        match_id="match-1",
        strategy_id="strategy-1",
        strategy_identity_hash=strategy_hash,
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=("AAPL",)),
        decision_time_ns=decision_time_ns,
        disposition=StrategyMatchDisposition.MATCHED,
        capability_state=AvailabilityState.AVAILABLE,
        quality=QUALITY,
        source_forecast_refs=(ContractReference(kind="forecast", id="forecast-1"),),
        context={"account_id": "acct-1", "mode": "PAPER"},
    )


def _attribution(*, account_id: str = "acct-1", mode: str = "PAPER") -> StrategyAttributionV1:
    return StrategyAttributionV1.create(
        schema_version="1",
        account_id=account_id,
        mode=mode,
        instrument_id="AAPL",
        allocation_ref=ContractReference(kind="allocation", id="allocation-1"),
        strategy_match_ref=ContractReference(kind="strategy_match", id="match-1"),
        strategy_id="strategy-1",
        strategy_identity_hash="strategy-hash-1",
        allocation_quantity=1,
        allocation_direction="LONG",
        allocation_time_ns=T,
        point_in_time_ns=T,
    )


def _observation(
    *,
    forecast_id: str = "forecast-1",
    outcome_id: str | None = "outcome-forecast-1",
    settled: bool = True,
    labelable: bool = True,
    evidence_tier: EvidenceTier = EvidenceTier.OBSERVED_REPLAY,
    evidence_mode: str = "PAPER",
    account_id: str = "acct-1",
    mode: str = "PAPER",
    trading: bool = False,
) -> LearningObservationV1:
    return LearningObservationV1.create(
        account_id=account_id,
        mode=mode,
        strategy_id="strategy-1",
        strategy_identity_hash="strategy-hash-1",
        strategy_match_ref=ContractReference(kind="strategy_match", id="match-1"),
        forecast_ref=ContractReference(kind="forecast", id=forecast_id),
        prediction_outcome_ref=(
            ContractReference(kind="outcome", id=outcome_id) if outcome_id else None
        ),
        trading_attribution_ref=(
            ContractReference(kind="strategy_attribution", id="ATR-pending")
            if trading
            else None
        ),
        opportunity_ref=ContractReference(kind="opportunity", id="opportunity-1"),
        cluster_ref=ContractReference(kind="cluster", id="cluster-1"),
        evidence_tier=evidence_tier,
        evidence_mode=evidence_mode,
        decision_time_ns=T,
        settlement_time_ns=T + HORIZON if settled else None,
        settlement_state=(
            LearningSettlementState.SETTLED
            if settled
            else LearningSettlementState.UNSETTLED
        ),
        label_state=(
            LearningLabelState.PENDING
            if not settled
            else (LearningLabelState.LABELABLE if labelable else LearningLabelState.UNLABELABLE)
        ),
    )


def _join(
    *,
    observation: LearningObservationV1 | None = None,
    outcome: OutcomeV1 | None = None,
    attribution: StrategyAttributionV1 | None = None,
) -> LearningJoinV1:
    observation = observation or _observation(
        trading=attribution is not None,
        outcome_id=outcome.outcome_id if outcome is not None else "outcome-forecast-1",
    )
    if attribution is not None:
        observation = replace(
            observation,
            trading_attribution_ref=ContractReference(
                kind="strategy_attribution",
                id=attribution.attribution_id,
            ),
        )
    return LearningJoinV1(
        observation=observation,
        strategy_match=replace(
            _match(),
            source_forecast_refs=(observation.forecast_ref,),
        ),
        forecast=_forecast(forecast_id=observation.forecast_ref.id),
        prediction_outcome=outcome or _outcome(forecast_id=observation.forecast_ref.id),
        trading_attribution=attribution,
    )


def _policy(**overrides) -> LearningPolicyV1:
    values = {
        "policy_id": "learning-policy-1",
        "policy_version": "1.0.0",
        "account_id": "acct-1",
        "mode": "PAPER",
        "minimum_samples": 1,
        "allowed_evidence_tiers": (EvidenceTier.OBSERVED_REPLAY,),
        "allowed_evidence_modes": ("PAPER",),
    }
    values.update(overrides)
    return LearningPolicyV1(**values)


class StrategyLearningBoundaryTests(unittest.TestCase):
    def test_observation_is_immutable_and_round_trips_with_deterministic_id(self) -> None:
        observation = _observation()
        payload = learning_observation_v1_to_dict(observation)
        restored = learning_observation_v1_from_dict(payload)

        self.assertEqual(restored, observation)
        self.assertEqual(observation.observation_id, f"LO-{observation.identity_hash}")
        with self.assertRaises(AttributeError):
            observation.account_id = "other"  # type: ignore[misc]

    def test_settled_prediction_is_eligible_and_trading_quality_stays_separate(self) -> None:
        evaluation = evaluate_learning_join(
            _join(attribution=_attribution()),
            _policy(),
        )

        self.assertEqual(evaluation.eligibility, LearningEligibility.ELIGIBLE)
        self.assertEqual(evaluation.prediction_quality, QualityState.GOOD)
        self.assertEqual(evaluation.trading_quality, QualityState.GOOD)
        self.assertNotIn("combined_score", evaluation.counters)

    def test_pit_and_account_mode_lineage_fail_closed(self) -> None:
        pit_join = _join(
            observation=_observation(),
            outcome=_outcome(),
        )
        pit_join = replace(
            pit_join,
            forecast=_forecast(decision_time_ns=T + 1),
        )
        pit = evaluate_learning_join(pit_join, _policy())
        self.assertEqual(pit.eligibility, LearningEligibility.INELIGIBLE)
        self.assertIn("FORECAST_AFTER_DECISION", pit.reasons)

        account_join = _join(
            observation=_observation(account_id="other-account"),
            outcome=_outcome(),
        )
        account = evaluate_learning_join(account_join, _policy())
        self.assertEqual(account.eligibility, LearningEligibility.INELIGIBLE)
        self.assertIn("ACCOUNT_SCOPE_MISMATCH", account.reasons)

    def test_unsettled_and_unlabelable_predictions_are_inconclusive(self) -> None:
        unsettled = _observation(settled=False, labelable=False, outcome_id=None)
        result = evaluate_learning_join(
            replace(_join(observation=unsettled, outcome=None), prediction_outcome=None),
            _policy(),
        )
        self.assertEqual(result.eligibility, LearningEligibility.INCONCLUSIVE)
        self.assertIn("PREDICTION_NOT_SETTLED", result.reasons)

        unlabelable = _observation(settled=True, labelable=False)
        result = evaluate_learning_join(
            _join(observation=unlabelable, outcome=_outcome(settled=False)),
            _policy(),
        )
        self.assertEqual(result.eligibility, LearningEligibility.INCONCLUSIVE)
        self.assertIn("PREDICTION_UNLABELABLE", result.reasons)

    def test_evidence_and_sample_gates_are_explicit(self) -> None:
        evidence = evaluate_learning_join(
            _join(observation=_observation(evidence_mode="LIVE")),
            _policy(),
        )
        self.assertEqual(evidence.eligibility, LearningEligibility.INELIGIBLE)
        self.assertIn("EVIDENCE_MODE_NOT_ALLOWED", evidence.reasons)

        joins = (
            _join(),
            _join(
                observation=_observation(
                    forecast_id="forecast-2",
                    outcome_id="outcome-forecast-2",
                )
            ),
        )
        evaluations = evaluate_learning_joins(
            tuple(
                replace(
                    join,
                    forecast=_forecast(forecast_id=join.observation.forecast_ref.id),
                    prediction_outcome=_outcome(
                        forecast_id=join.observation.forecast_ref.id
                    ),
                )
                for join in joins
            ),
            _policy(minimum_samples=3),
        )
        self.assertTrue(all(item.eligibility == LearningEligibility.INCONCLUSIVE for item in evaluations))
        self.assertTrue(all("INSUFFICIENT_SAMPLES" in item.reasons for item in evaluations))

    def test_cohort_scope_cannot_mix_accounts_or_modes(self) -> None:
        first = _join()
        second_observation = _observation(account_id="acct-2")
        second = _join(observation=second_observation)

        evaluations = evaluate_learning_joins((first, second), _policy(account_id=None))

        self.assertTrue(
            all(item.eligibility == LearningEligibility.INELIGIBLE for item in evaluations)
        )
        self.assertTrue(
            all(
                "CROSS_ACCOUNT_OR_MODE_CONTAMINATION" in item.reasons
                for item in evaluations
            )
        )

    def test_handoff_is_non_promotional_and_round_trips(self) -> None:
        evaluations = evaluate_learning_joins((_join(),), _policy())
        handoff = emit_research_handoff(
            evaluations,
            seed={"observation_count": 1, "source": "bounded_learning"},
        )

        self.assertIsInstance(handoff, ResearchHandoffV1)
        self.assertFalse(handoff.promotional)
        self.assertFalse(handoff.can_promote)
        self.assertFalse(handoff.can_execute)
        self.assertFalse(handoff.champion_change_allowed)
        self.assertEqual(
            handoff.required_downstream_authorities,
            (
                "ResearchHypothesisV1",
                "ExperimentManifestV1",
                "ValidationEngine",
                "LockedHoldout",
                "ContaminationCheck",
                "ShadowEvidence",
                "PromotionEngine",
            ),
        )
        self.assertEqual(
            research_handoff_v1_from_dict(research_handoff_v1_to_dict(handoff)),
            handoff,
        )

        with self.assertRaises(ValueError):
            emit_research_handoff(
                (replace(evaluations[0], eligibility=LearningEligibility.INELIGIBLE),)
            )

    def test_policy_and_evaluation_serialization_are_canonical(self) -> None:
        policy = _policy()
        self.assertEqual(learning_policy_v1_from_dict(learning_policy_v1_to_dict(policy)), policy)
        evaluation = evaluate_learning_join(_join(), policy)
        self.assertEqual(
            learning_evaluation_v1_from_dict(learning_evaluation_v1_to_dict(evaluation)),
            evaluation,
        )
        join = _join()
        self.assertEqual(learning_join_v1_from_dict(learning_join_v1_to_dict(join)), join)


if __name__ == "__main__":
    unittest.main()
