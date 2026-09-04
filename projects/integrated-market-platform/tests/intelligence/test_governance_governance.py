"""BUILD 23 governance, monitoring, and rollback tests."""

from __future__ import annotations

import inspect
import unittest

from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION
from market_platform_foundation.intelligence.evaluation.metrics import compute_brier_contribution
from market_platform_foundation.intelligence.execution import OpportunityGateError, PaperExecutionOrchestrator, PreTradeRiskEngine
from market_platform_foundation.intelligence.governance import (
    ActivationEngine,
    ActivationError,
    DriftSeverity,
    DriftType,
    FailSafeDecisionKind,
    FailSafeEngine,
    GovernanceEngine,
    GovernanceEventType,
    HealthState,
    RollbackDecisionKind,
    RollbackEngine,
    RuntimeActivationPolicyV1,
    RuntimeReportedIdentityV1,
    assess_calibration_drift,
    assess_data_quality_health,
    assess_execution_health,
    assess_feature_drift,
    assess_performance_drift,
    assess_provider_health,
    build_activation_policy,
    derive_activation_policy_id,
    derive_drift_policy_id,
    derive_runtime_activation_id,
    resolve_governance_state,
    runtime_activation_policy_v1_from_dict,
    runtime_activation_policy_v1_to_dict,
    runtime_activation_v1_from_dict,
    runtime_activation_v1_to_dict,
)
from market_platform_foundation.intelligence.opportunity import AssessmentAction, AssessmentReasonCode, OpportunityEngine
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.promotion import PromotionEngine
from market_platform_foundation.intelligence.quality.models import ConnectionState, DecisionAction, ProviderHealthSnapshot
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from tests.intelligence.execution_fixtures import default_execution_policy, flat_portfolio, sample_opportunity, sample_quote
from tests.intelligence.governance_fixtures import (
    DEFAULT_SCOPE,
    activated_champion_bundle,
    default_activation_policy,
    default_drift_policy,
    default_fail_safe_policy,
    default_rollback_policy,
    feature_reference,
    matching_runtime_identity,
    monitoring_window,
)
from tests.intelligence.opportunity_fixtures import champion_forecast, default_opportunity_context, default_opportunity_policy
from tests.intelligence.outcome_fixtures import T
from tests.intelligence.promotion_fixtures import validated_candidate_bundle


class ActivationPolicyTests(unittest.TestCase):
    def test_paper_only_policy_round_trip(self) -> None:
        policy = default_activation_policy()
        restored = runtime_activation_policy_v1_from_dict(runtime_activation_policy_v1_to_dict(policy))
        self.assertEqual(policy.activation_policy_id, restored.activation_policy_id)

    def test_live_execution_policy_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RuntimeActivationPolicyV1(
                activation_policy_id="bad",
                schema_version=INTELLIGENCE_SCHEMA_VERSION,
                champion_scope=DEFAULT_SCOPE,
                allowed_execution_modes=("LIVE",),
                paper_execution_only=True,
                live_execution_forbidden=True,
            )

    def test_policy_id_determinism(self) -> None:
        p1 = default_activation_policy()
        p2 = default_activation_policy()
        self.assertEqual(p1.activation_policy_id, p2.activation_policy_id)

    def test_semantic_change_changes_id(self) -> None:
        p1 = default_activation_policy()
        p2 = default_activation_policy(require_artifact_integrity=False)
        self.assertNotEqual(p1.activation_policy_id, p2.activation_policy_id)


class RuntimeActivationTests(unittest.TestCase):
    def test_valid_champion_activation(self) -> None:
        _, champion, _, artifact_bytes, policy, activation = activated_champion_bundle()
        self.assertTrue(activation.activation_id.startswith("RTACT-"))
        self.assertEqual(activation.champion_assignment_id, champion.assignment_id)

    def test_artifact_hash_mismatch_fails(self) -> None:
        repo, manifest, candidate, artifact_bytes, report, plan = validated_candidate_bundle()
        champion = PromotionEngine().bootstrap_champion(
            champion_scope=DEFAULT_SCOPE,
            candidate=candidate,
            effective_from_ns=T,
        )
        engine = ActivationEngine()
        with self.assertRaises(ActivationError):
            engine.create_activation(
                policy=default_activation_policy(),
                champion_assignment=champion,
                effective_from_ns=T,
                artifact_bytes=b"wrong-bytes",
            )

    def test_activation_id_determinism(self) -> None:
        _, champion, _, artifact_bytes, policy, a1 = activated_champion_bundle()
        a2 = ActivationEngine().create_activation(
            policy=policy,
            champion_assignment=champion,
            effective_from_ns=T,
            artifact_bytes=artifact_bytes,
        )
        self.assertEqual(a1.activation_id, a2.activation_id)

    def test_activation_round_trip(self) -> None:
        _, _, _, _, _, activation = activated_champion_bundle()
        restored = runtime_activation_v1_from_dict(runtime_activation_v1_to_dict(activation))
        self.assertEqual(activation.activation_id, restored.activation_id)


class RuntimeConsistencyTests(unittest.TestCase):
    def test_matching_runtime_artifact(self) -> None:
        _, _, _, _, _, activation = activated_champion_bundle()
        ok, reasons = ActivationEngine().check_runtime_consistency(
            activation=activation,
            reported=matching_runtime_identity(activation),
        )
        self.assertTrue(ok)
        self.assertEqual(reasons, ())

    def test_runtime_reports_wrong_artifact(self) -> None:
        _, _, _, _, _, activation = activated_champion_bundle()
        ok, reasons = ActivationEngine().check_runtime_consistency(
            activation=activation,
            reported=RuntimeReportedIdentityV1(candidate_artifact_hash="deadbeef"),
        )
        self.assertFalse(ok)

    def test_missing_runtime_identity(self) -> None:
        _, _, _, _, _, activation = activated_champion_bundle()
        ok, reasons = ActivationEngine().check_runtime_consistency(activation=activation, reported=None)
        self.assertFalse(ok)


class ProviderHealthTests(unittest.TestCase):
    def test_connected_fresh_healthy(self) -> None:
        window = monitoring_window()
        snap = assess_provider_health(
            provider="moomoo",
            capability="QUOTES",
            observed_at_ns=T + 1,
            window=window,
            provider_health=ProviderHealthSnapshot(
                provider_id="moomoo",
                as_of_time_ns=T,
                connection=ConnectionState.CONNECTED,
            ),
            staleness_threshold_ns=10_000_000_000,
        )
        self.assertEqual(snap.health_state, HealthState.HEALTHY)

    def test_stale_provider(self) -> None:
        window = monitoring_window()
        snap = assess_provider_health(
            provider="moomoo",
            capability=None,
            observed_at_ns=T + 20_000_000_000,
            window=window,
            provider_health=ProviderHealthSnapshot(
                provider_id="moomoo",
                as_of_time_ns=T,
                connection=ConnectionState.CONNECTED,
            ),
            staleness_threshold_ns=10_000_000_000,
        )
        self.assertEqual(snap.health_state, HealthState.UNHEALTHY)

    def test_staleness_equality_boundary(self) -> None:
        window = monitoring_window()
        snap = assess_provider_health(
            provider="moomoo",
            capability=None,
            observed_at_ns=T + 10_000_000_000,
            window=window,
            provider_health=ProviderHealthSnapshot(
                provider_id="moomoo",
                as_of_time_ns=T,
                connection=ConnectionState.CONNECTED,
            ),
            staleness_threshold_ns=10_000_000_000,
        )
        self.assertEqual(snap.health_state, HealthState.DEGRADED)

    def test_no_observations_unknown(self) -> None:
        snap = assess_provider_health(
            provider="moomoo",
            capability=None,
            observed_at_ns=T,
            window=monitoring_window(),
            provider_health=None,
            staleness_threshold_ns=10_000_000_000,
        )
        self.assertEqual(snap.health_state, HealthState.UNKNOWN)


class DataQualityHealthTests(unittest.TestCase):
    def test_explicit_denominators(self) -> None:
        snap = assess_data_quality_health(
            window=monitoring_window(),
            quality_actions=(
                DecisionAction.USE.value,
                DecisionAction.DEGRADE.value,
                DecisionAction.FAIL_CLOSED.value,
            ),
            finding_codes=(),
        )
        self.assertEqual(snap.observation_count, 3)
        self.assertEqual(snap.metadata["fail_closed_rate"], 1 / 3)

    def test_empty_window_unknown(self) -> None:
        snap = assess_data_quality_health(
            window=monitoring_window(),
            quality_actions=(),
            finding_codes=(),
        )
        self.assertEqual(snap.health_state, HealthState.UNKNOWN)


class DriftPolicyTests(unittest.TestCase):
    def test_drift_policy_identity(self) -> None:
        p1 = default_drift_policy()
        p2 = default_drift_policy()
        self.assertEqual(p1.drift_policy_id, p2.drift_policy_id)

    def test_threshold_change_new_id(self) -> None:
        p1 = default_drift_policy()
        p2 = default_drift_policy(performance_degradation_threshold=0.10)
        self.assertNotEqual(p1.drift_policy_id, p2.drift_policy_id)


class DriftAssessmentTests(unittest.TestCase):
    def test_schema_drift_critical(self) -> None:
        policy = default_drift_policy(minimum_sample=2)
        ref = feature_reference(fingerprint="schema-v1")
        assessment = assess_feature_drift(
            policy=policy,
            window=monitoring_window(),
            reference=ref,
            recent_means={"f1": 0.0},
            recent_missingness={"f1": 0.0},
            recent_schema_fingerprint="schema-v2",
            sample_count=10,
        )
        self.assertIn(DriftType.SCHEMA_DRIFT, assessment.drift_types)
        self.assertEqual(assessment.severity, DriftSeverity.CRITICAL)

    def test_insufficient_sample(self) -> None:
        policy = default_drift_policy(minimum_sample=20)
        assessment = assess_performance_drift(
            policy=policy,
            window=monitoring_window(),
            reference_metric=0.1,
            recent_metric=0.2,
            sample_count=5,
        )
        self.assertEqual(assessment.severity, DriftSeverity.UNKNOWN)

    def test_performance_degradation(self) -> None:
        policy = default_drift_policy(minimum_sample=4, performance_degradation_threshold=0.01)
        assessment = assess_performance_drift(
            policy=policy,
            window=monitoring_window(),
            reference_metric=0.10,
            recent_metric=0.20,
            sample_count=10,
        )
        self.assertIn(DriftType.PERFORMANCE_DRIFT, assessment.drift_types)

    def test_calibration_drift(self) -> None:
        policy = default_drift_policy(minimum_sample=4, calibration_ece_threshold=0.05)
        assessment = assess_calibration_drift(
            policy=policy,
            window=monitoring_window(),
            recent_ece=0.12,
            sample_count=20,
        )
        self.assertIn(DriftType.CALIBRATION_DRIFT, assessment.drift_types)

    def test_same_inputs_same_id(self) -> None:
        policy = default_drift_policy(minimum_sample=2)
        kwargs = dict(
            policy=policy,
            window=monitoring_window(),
            reference_metric=0.1,
            recent_metric=0.2,
            sample_count=10,
        )
        a1 = assess_performance_drift(**kwargs)
        a2 = assess_performance_drift(**kwargs)
        self.assertEqual(a1.drift_assessment_id, a2.drift_assessment_id)


class FailSafeTests(unittest.TestCase):
    def test_healthy_allow(self) -> None:
        _, _, _, _, _, activation = activated_champion_bundle()
        decision = FailSafeEngine().evaluate(
            policy=default_fail_safe_policy(),
            decision_time_ns=T,
            activation=activation,
            runtime_consistent=True,
            runtime_reasons=(),
        )
        self.assertEqual(decision.decision, FailSafeDecisionKind.ALLOW)

    def test_artifact_mismatch_disable_scope(self) -> None:
        _, _, _, _, _, activation = activated_champion_bundle()
        decision = FailSafeEngine().evaluate(
            policy=default_fail_safe_policy(),
            decision_time_ns=T,
            activation=activation,
            runtime_consistent=False,
            runtime_reasons=(),
        )
        self.assertEqual(decision.decision, FailSafeDecisionKind.DISABLE_SCOPE)

    def test_same_evidence_same_decision(self) -> None:
        _, _, _, _, _, activation = activated_champion_bundle()
        engine = FailSafeEngine()
        kwargs = dict(
            policy=default_fail_safe_policy(),
            decision_time_ns=T,
            activation=activation,
            runtime_consistent=True,
            runtime_reasons=(),
            trigger_key="x",
        )
        self.assertEqual(engine.evaluate(**kwargs).decision_id, engine.evaluate(**kwargs).decision_id)


class Build2122GovernanceGateTests(unittest.TestCase):
    def test_disabled_runtime_blocks_opportunity(self) -> None:
        _, champion, candidate, _, _, activation = activated_champion_bundle()
        forecast = champion_forecast(champion)
        state = resolve_governance_state(
            activation=activation,
            fail_safe_decision=None,
        )
        state = resolve_governance_state(
            activation=activation,
            fail_safe_decision=FailSafeEngine().evaluate(
                policy=default_fail_safe_policy(),
                decision_time_ns=T,
                activation=activation,
                runtime_consistent=False,
                runtime_reasons=(),
            ),
        )
        result = OpportunityEngine().assess(
            forecast=forecast,
            policy=default_opportunity_policy(),
            context=default_opportunity_context(),
            champion_at_forecast=champion,
            champion_at_opportunity=champion,
            opportunity_decision_time_ns=T + 1,
            runtime_governance=state,
        )
        self.assertEqual(result.assessment.assessment_action, AssessmentAction.FAIL_CLOSED)
        self.assertIn(AssessmentReasonCode.RUNTIME_GOVERNANCE_DISABLED, result.assessment.reason_codes)

    def test_disabled_paper_execution_blocks_order(self) -> None:
        state = resolve_governance_state(
            activation=None,
            fail_safe_decision=None,
        )
        engine = PreTradeRiskEngine()
        with self.assertRaises(OpportunityGateError):
            engine.build_proposal(
                opportunity=sample_opportunity(),
                policy=default_execution_policy(),
                portfolio=flat_portfolio(),
                quote=sample_quote(),
                proposal_time_ns=T + 2,
                instrument_id="inst-biya",
                symbol="BIYA",
                runtime_governance=state,
            )


class RollbackTests(unittest.TestCase):
    def test_no_target_disable_only(self) -> None:
        _, champion, _, artifact_bytes, activation_policy, activation = activated_champion_bundle()
        assessment = assess_performance_drift(
            policy=default_drift_policy(minimum_sample=2, performance_degradation_threshold=0.01),
            window=monitoring_window(),
            reference_metric=0.1,
            recent_metric=0.5,
            sample_count=10,
        )
        decision = RollbackEngine().evaluate(
            policy=default_rollback_policy(),
            current_activation=activation,
            previous_activation=None,
            champion_assignment_for_target=None,
            artifact_bytes_by_assignment={},
            drift_assessments=(assessment,),
            effective_time_ns=T + 100,
        )
        self.assertEqual(decision.decision, RollbackDecisionKind.DISABLE_ONLY)

    def test_valid_previous_known_good(self) -> None:
        _, champion, _, artifact_bytes, activation_policy, activation_b = activated_champion_bundle()
        activation_a = ActivationEngine().create_activation(
            policy=activation_policy,
            champion_assignment=champion,
            effective_from_ns=T - 100,
            artifact_bytes=artifact_bytes,
        )
        assessment = assess_performance_drift(
            policy=default_drift_policy(minimum_sample=2, performance_degradation_threshold=0.01),
            window=monitoring_window(),
            reference_metric=0.1,
            recent_metric=0.5,
            sample_count=10,
        )
        decision = RollbackEngine().evaluate(
            policy=default_rollback_policy(),
            current_activation=activation_b,
            previous_activation=activation_a,
            champion_assignment_for_target=champion,
            artifact_bytes_by_assignment={champion.assignment_id: artifact_bytes},
            drift_assessments=(assessment,),
            effective_time_ns=T + 100,
        )
        self.assertEqual(decision.decision, RollbackDecisionKind.ROLLBACK)
        self.assertEqual(decision.target_activation_id, activation_a.activation_id)


class PersistenceTests(unittest.TestCase):
    def test_activation_persisted_immutably(self) -> None:
        repo = InMemoryIntelligenceRepository()
        _, _, _, _, policy, activation = activated_champion_bundle()
        repo.put_runtime_activation_policy(policy)
        self.assertEqual(repo.put_runtime_activation(activation).value, "INSERTED")
        self.assertEqual(repo.put_runtime_activation(activation).value, "ALREADY_PRESENT")
        restored = repo.get_runtime_activation(activation.activation_id)
        self.assertEqual(restored.activation_id, activation.activation_id)

    def test_governance_event_persisted(self) -> None:
        repo = InMemoryIntelligenceRepository()
        engine = GovernanceEngine()
        event = engine.create_governance_event(
            event_type=GovernanceEventType.ACTIVATED,
            champion_scope=DEFAULT_SCOPE,
            effective_at_ns=T,
        )
        repo.put_governance_event(event)
        self.assertIsNotNone(repo.get_governance_event(event.event_id))


class TrainingAuditTests(unittest.TestCase):
    def test_no_training_in_governance_path(self) -> None:
        import market_platform_foundation.intelligence.governance as governance_pkg

        forbidden = (".fit(", "partial_fit", "train_model", "optimizer", "backprop")
        for name in dir(governance_pkg):
            obj = getattr(governance_pkg, name)
            if not inspect.ismodule(obj):
                continue
            source = inspect.getsource(obj)
            for token in forbidden:
                self.assertNotIn(token, source)


class MetricReuseTests(unittest.TestCase):
    def test_build16_brier_reused(self) -> None:
        self.assertAlmostEqual(compute_brier_contribution(0.7, 1), 0.09)


if __name__ == "__main__":
    unittest.main()
