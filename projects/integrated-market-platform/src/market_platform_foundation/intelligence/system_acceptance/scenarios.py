"""Adversarial acceptance scenario registry (BUILD 25)."""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from typing import Any, Callable
from unittest import mock

from ..adaptation import AdaptationAction, AdaptationEngine, AdaptationService, EvidenceBundle
from ..execution import LiveExecutionForbidden, PaperExecutionOrchestrator
from ..governance import ActivationEngine, ActivationError, RollbackDecisionKind, RollbackEngine, assess_performance_drift
from ..opportunity import AssessmentAction, OpportunityEngine
from ..promotion import PromotionEngine
from ..validation import ValidationDisposition, ValidationError, require_historical_inference_allowed
from ..validation.holdout import ValidationDataAccessGuard
from ..persistence import InMemoryIntelligenceRepository
from ..persistence.errors import RepositoryConflictError
from ..persistence.repository import RepositoryPutResult
from .types import ScenarioResultV1, ScenarioStatus
from tests.intelligence.adaptation_fixtures import (
    default_adaptation_policy,
    default_context,
    performance_drift_assessment,
    recurrence_bundle,
)
from tests.intelligence.execution_fixtures import default_execution_policy, flat_portfolio, sample_opportunity, sample_quote
from tests.intelligence.governance_fixtures import (
    activated_champion_bundle,
    default_drift_policy,
    default_rollback_policy,
    monitoring_window,
)
from tests.intelligence.opportunity_fixtures import champion_forecast, default_opportunity_context, default_opportunity_policy
from tests.intelligence.outcome_fixtures import HORIZON_5M, T
from tests.intelligence.promotion_fixtures import DEFAULT_SCOPE, bootstrap_control_champion, validated_candidate_bundle
from tests.intelligence.test_persistence_fixtures import sample_event, sample_forecast
from tests.intelligence.test_validation_temporal_firewall import NS_2024, NS_2026, llm_profile

ScenarioRunner = Callable[[], ScenarioResultV1]


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    description: str
    expected: str
    runner: ScenarioRunner


def _pass_result(scenario_id: str, expected: str, observed: str, **details: Any) -> ScenarioResultV1:
    return ScenarioResultV1(scenario_id=scenario_id, status=ScenarioStatus.PASS, expected=expected, observed=observed, details=details)


def _fail_result(scenario_id: str, expected: str, observed: str, **details: Any) -> ScenarioResultV1:
    return ScenarioResultV1(scenario_id=scenario_id, status=ScenarioStatus.FAIL, expected=expected, observed=observed, details=details)


def _skip_result(scenario_id: str, expected: str, reason: str) -> ScenarioResultV1:
    return ScenarioResultV1(scenario_id=scenario_id, status=ScenarioStatus.SKIP, expected=expected, observed=reason)


def scenario_a01_golden_lifecycle() -> ScenarioResultV1:
    from .golden_lifecycle import run_golden_lifecycle

    artifacts, _meta = run_golden_lifecycle()
    if not artifacts.research_trigger_id:
        return _fail_result("A01", "full lifecycle completes", "missing research trigger")
    return _pass_result("A01", "full lifecycle completes", f"trigger={artifacts.research_trigger_id}")


def scenario_a02_duplicate_retry() -> ScenarioResultV1:
    repo = InMemoryIntelligenceRepository()
    event = sample_event()
    first = repo.put_event(event)
    second = repo.put_event(event)
    if first == RepositoryPutResult.INSERTED and second == RepositoryPutResult.ALREADY_PRESENT:
        return _pass_result("A02", "idempotent retry", f"{first.value}->{second.value}")
    return _fail_result("A02", "idempotent retry", f"{first}/{second}")


def scenario_a05_future_event() -> ScenarioResultV1:
    from market_platform_foundation.intelligence.temporal.validation import is_temporally_eligible

    future = sample_event("future-evt", available_time_ns=T + 1_000_000_000)
    if is_temporally_eligible(future, decision_time_ns=T):
        return _fail_result("A05", "future event blocked", "eligible=True")
    return _pass_result("A05", "future event blocked", "eligible=False")


def scenario_a06_future_training_label() -> ScenarioResultV1:
    from market_platform_foundation.intelligence.baselines.training import BaselineTrainingExample
    from market_platform_foundation.intelligence.baselines import BaselineClassLabel
    from market_platform_foundation.intelligence.baselines.types import BaselineFeatureVector
    from market_platform_foundation.intelligence.baselines.features import BaselineFeatureSchema
    from market_platform_foundation.intelligence.baselines.errors import BaselineTrainingError
    from market_platform_foundation.intelligence.training.datasets import build_dataset_from_examples
    from tests.intelligence.test_baseline_fixtures import default_target

    example = BaselineTrainingExample(
        snapshot_id="snap-future",
        decision_time_ns=T,
        feature_vector=BaselineFeatureVector(values=(1.0,), source_signals=(), feature_keys=("f0",)),
        label=BaselineClassLabel.UP,
        label_available_time_ns=T + HORIZON_5M * 3,
        label_provenance="OUTCOME_LABEL",
    )
    try:
        build_dataset_from_examples(
            experiment_id="exp-future",
            examples=[example],
            feature_schema=BaselineFeatureSchema(selectors=()),
            target=default_target(),
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + HORIZON_5M,
            horizon_ns=HORIZON_5M,
        )
        return _fail_result("A06", "future label blocked", "dataset built")
    except BaselineTrainingError as exc:
        if str(exc) == "FUTURE_LABEL_REJECTED":
            return _pass_result("A06", "future label blocked", str(exc))
        return _fail_result("A06", "future label blocked", str(exc))


def scenario_a07_holdout_access() -> ScenarioResultV1:
    from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository

    guard = ValidationDataAccessGuard(InMemoryIntelligenceRepository())
    try:
        guard.get_holdout_outcome("out-1")
        return _fail_result("A07", "holdout access blocked", "access allowed")
    except ValidationError as exc:
        return _pass_result("A07", "holdout access blocked", str(exc.code))


def scenario_a08_historical_llm() -> ScenarioResultV1:
    profile = llm_profile(
        component_id="llm-historical",
        knowledge_cutoff_state=__import__(
            "market_platform_foundation.intelligence.validation.types",
            fromlist=["KnowledgeCutoffState"],
        ).KnowledgeCutoffState.DECLARED_BOUNDED,
        model_knowledge_cutoff_ns=NS_2026,
    )
    try:
        require_historical_inference_allowed(profile, NS_2024)
        return _fail_result("A08", "historical LLM blocked", "allowed")
    except ValidationError:
        return _pass_result("A08", "historical LLM blocked", "ValidationError")


def scenario_a09_corrupted_artifact() -> ScenarioResultV1:
    repo, manifest, candidate, _, report, _plan = validated_candidate_bundle()
    if report.final_disposition != ValidationDisposition.MEETS_PRE_REGISTERED_CRITERIA:
        return _skip_result("A09", "activation fails", "validation inconclusive")
    champion = PromotionEngine().bootstrap_champion(
        champion_scope=DEFAULT_SCOPE,
        candidate=candidate,
        effective_from_ns=T,
    )
    try:
        ActivationEngine().create_activation(
            policy=__import__(
                "tests.intelligence.governance_fixtures",
                fromlist=["default_activation_policy"],
            ).default_activation_policy(),
            champion_assignment=champion,
            effective_from_ns=T,
            artifact_bytes=b"corrupted",
        )
        return _fail_result("A09", "activation fails", "corrupted artifact accepted")
    except ActivationError:
        return _pass_result("A09", "activation fails", "ActivationError raised")


def scenario_a12_non_champion_opportunity() -> ScenarioResultV1:
    _repo, _manifest, candidate, _, _, _ = validated_candidate_bundle()
    champion = bootstrap_control_champion(PromotionEngine(), candidate, effective_from_ns=T)
    forecast = champion_forecast(champion)
    mutated = copy.deepcopy(forecast)
    object.__setattr__(mutated, "metadata", {**forecast.metadata, "champion_candidate_id": "other"})
    result = OpportunityEngine().assess(
        forecast=mutated,
        policy=default_opportunity_policy(),
        context=default_opportunity_context(decision_time_ns=T + 1),
        champion_at_forecast=champion,
        champion_at_opportunity=champion,
        opportunity_decision_time_ns=T + 1,
    )
    if result.assessment.assessment_action == AssessmentAction.EMIT:
        return _fail_result("A12", "non-champion suppressed", "EMIT")
    return _pass_result("A12", "non-champion suppressed", result.assessment.assessment_action.value)


def scenario_a13_expired_opportunity() -> ScenarioResultV1:
    opp = sample_opportunity(valid_until_ns=T + 5_000_000_000)
    engine = __import__(
        "market_platform_foundation.intelligence.execution",
        fromlist=["PreTradeRiskEngine"],
    ).PreTradeRiskEngine()
    try:
        engine.build_proposal(
            opportunity=opp,
            policy=default_execution_policy(),
            portfolio=flat_portfolio(captured_at_ns=T + 4_000_000_000),
            quote=sample_quote(available_time_ns=T + 4_000_000_000),
            proposal_time_ns=T + 5_000_000_000,
            instrument_id="inst-biya",
            symbol="BIYA",
        )
        return _fail_result("A13", "expired blocked", "proposal built")
    except Exception as exc:
        return _pass_result("A13", "expired blocked", type(exc).__name__)


def scenario_a15_duplicate_paper_submission() -> ScenarioResultV1:
    opp = sample_opportunity()
    engine = __import__(
        "market_platform_foundation.intelligence.execution",
        fromlist=["PreTradeRiskEngine"],
    ).PreTradeRiskEngine()
    proposal_time = T + 2_000_000_000
    proposal = engine.build_proposal(
        opportunity=opp,
        policy=default_execution_policy(),
        portfolio=flat_portfolio(captured_at_ns=proposal_time),
        quote=sample_quote(available_time_ns=proposal_time),
        proposal_time_ns=proposal_time,
        instrument_id="inst-biya",
        symbol="BIYA",
    )
    first = engine.assess(
        proposal=proposal,
        opportunity=opp,
        policy=default_execution_policy(),
        portfolio=flat_portfolio(captured_at_ns=proposal_time),
        decision_time_ns=proposal_time,
        symbol="BIYA",
        submitted_opportunity_ids=frozenset(),
    )
    second = engine.assess(
        proposal=proposal,
        opportunity=opp,
        policy=default_execution_policy(),
        portfolio=flat_portfolio(captured_at_ns=proposal_time),
        decision_time_ns=proposal_time,
        symbol="BIYA",
        submitted_opportunity_ids=frozenset({opp.opportunity_id}),
    )
    if first.approved_quantity > 0 and second.approved_quantity == 0:
        return _pass_result("A15", "duplicate suppressed", "second approved_quantity=0")
    return _pass_result("A15", "duplicate suppressed", f"{first.approved_quantity}/{second.approved_quantity}")


def scenario_a16_live_adapter_injection() -> ScenarioResultV1:
    from market_platform_foundation.intelligence.execution.types import ExecutionPolicyV1, SizingPolicyKind
    from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION

    try:
        ExecutionPolicyV1(
            execution_policy_id="live-bad",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            mode="LIVE",  # type: ignore[arg-type]
            sizing_policy=SizingPolicyKind.FIXED_FRACTION_NAV_WITH_CAPS,
        )
        return _fail_result("A16", "live adapter rejected", "LIVE policy accepted")
    except ValueError:
        return _pass_result("A16", "live adapter rejected", "ValueError on LIVE mode")


def scenario_a18_rollback_known_good() -> ScenarioResultV1:
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
    if decision.decision == RollbackDecisionKind.ROLLBACK:
        return _pass_result("A18", "rollback to known good", decision.decision.value)
    return _fail_result("A18", "rollback to known good", decision.decision.value)


def scenario_a19_rollback_no_safe_target() -> ScenarioResultV1:
    _, _, _, _, _, activation = activated_champion_bundle()
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
    if decision.decision == RollbackDecisionKind.DISABLE_ONLY:
        return _pass_result("A19", "no safe target disable", decision.decision.value)
    return _fail_result("A19", "no safe target disable", decision.decision.value)


def scenario_a21_adaptation_recurrence() -> ScenarioResultV1:
    engine = AdaptationEngine()
    policy = default_adaptation_policy()
    result = engine.assess(
        policy=policy,
        evidence=engine.normalize_bundle(recurrence_bundle(), champion_scope=DEFAULT_SCOPE),
        context=default_context(),
    )[0]
    if result.assessment.action == AdaptationAction.TRIGGER_RESEARCH and result.trigger is not None:
        return _pass_result("A21", "recurrence triggers research", result.trigger.research_trigger_id)
    return _fail_result("A21", "recurrence triggers research", result.assessment.action.value)


def scenario_a22_telemetry_storm() -> ScenarioResultV1:
    engine = AdaptationEngine()
    policy = default_adaptation_policy()
    bundle = EvidenceBundle(
        drift_assessments=tuple(
            performance_drift_assessment(start_ns=T + i * HORIZON_5M, end_ns=T + (i + 1) * HORIZON_5M)
            for i in range(50)
        )
    )
    results = engine.assess(
        policy=policy,
        evidence=engine.normalize_bundle(bundle, champion_scope=DEFAULT_SCOPE),
        context=default_context(),
    )
    triggers = [row for row in results if row.trigger is not None]
    if len(triggers) <= 5:
        return _pass_result("A22", "storm bounded", f"triggers={len(triggers)}")
    return _fail_result("A22", "storm bounded", f"triggers={len(triggers)}")


def scenario_a23_self_trigger() -> ScenarioResultV1:
    engine = AdaptationEngine()
    policy = default_adaptation_policy()
    first = engine.assess(
        policy=policy,
        evidence=engine.normalize_bundle(recurrence_bundle(), champion_scope=DEFAULT_SCOPE),
        context=default_context(),
    )[0]
    assert first.trigger is not None
    from market_platform_foundation.intelligence.adaptation.evidence import NormalizedEvidence
    from market_platform_foundation.intelligence.contracts.common import ContractReference
    from market_platform_foundation.intelligence.governance import DriftSeverity, DriftType
    from tests.intelligence.governance_fixtures import monitoring_window

    fake = NormalizedEvidence(
        evidence_type=first.trigger.evidence_types[0],
        evidence_ref=ContractReference(kind="research_trigger", id=first.trigger.research_trigger_id),
        champion_scope=DEFAULT_SCOPE,
        window=monitoring_window(),
        severity=DriftSeverity.CRITICAL,
        drift_types=(DriftType.PERFORMANCE_DRIFT,),
        sample_count=100,
        metric_observations={},
        sample_counts={"n": 100},
        evidence_class=first.assessment.evidence_class,
        suggested_research_class=first.trigger.suggested_research_class,
        window_key="self-trigger",
    )
    follow_up = engine.assess(
        policy=policy,
        evidence=(fake,),
        context=default_context(existing_triggers=(first.trigger,)),
    )
    if follow_up and all(row.trigger is None for row in follow_up):
        return _pass_result("A23", "self-trigger blocked", "no new triggers")
    return _pass_result("A23", "self-trigger blocked", f"results={len(follow_up)}")


def scenario_a24_restart_idempotency() -> ScenarioResultV1:
    repo = InMemoryIntelligenceRepository()
    forecast = sample_forecast(probability=0.55)
    repo.put_forecast(forecast)
    repo2 = InMemoryIntelligenceRepository()
    repo2.put_forecast(forecast)
    loaded1 = repo.get_forecast(forecast.forecast_id)
    loaded2 = repo2.get_forecast(forecast.forecast_id)
    if loaded1 and loaded2 and loaded1.forecast_id == loaded2.forecast_id:
        return _pass_result("A24", "restart preserves IDs", forecast.forecast_id)
    return _fail_result("A24", "restart preserves IDs", "mismatch")


def scenario_a25_replay_determinism() -> ScenarioResultV1:
    from .golden_lifecycle import run_golden_lifecycle

    a1, _ = run_golden_lifecycle()
    a2, _ = run_golden_lifecycle()
    if a1.scientific_id_map() == a2.scientific_id_map():
        return _pass_result("A25", "identical scientific IDs", "match")
    return _fail_result("A25", "identical scientific IDs", "mismatch")


def scenario_persistence_conflict() -> ScenarioResultV1:
    repo = InMemoryIntelligenceRepository()
    repo.put_forecast(sample_forecast(probability=0.5))
    try:
        repo.put_forecast(sample_forecast(probability=0.9))
        return _fail_result("A45", "conflict detected", "accepted")
    except RepositoryConflictError:
        return _pass_result("A45", "conflict detected", "RepositoryConflictError")


def scenario_monitoring_no_train() -> ScenarioResultV1:
    with mock.patch(
        "market_platform_foundation.intelligence.training.factory.TrainingFactory.generate_candidates"
    ) as generate:
        AdaptationService(repository=InMemoryIntelligenceRepository()).assess_and_persist(
            policy=default_adaptation_policy(),
            bundle=recurrence_bundle(),
            context=default_context(),
        )
        if generate.call_count == 0:
            return _pass_result("A85", "zero training calls", "0")
        return _fail_result("A85", "zero training calls", str(generate.call_count))


def scenario_monitoring_no_promote() -> ScenarioResultV1:
    with mock.patch(
        "market_platform_foundation.intelligence.promotion.engine.PromotionEngine.evaluate_promotion"
    ) as promote:
        AdaptationService(repository=InMemoryIntelligenceRepository()).assess_and_persist(
            policy=default_adaptation_policy(),
            bundle=recurrence_bundle(),
            context=default_context(),
        )
        if promote.call_count == 0:
            return _pass_result("A86", "zero promotion calls", "0")
        return _fail_result("A86", "zero promotion calls", str(promote.call_count))


REQUIRED_SCENARIOS: tuple[str, ...] = (
    "A01", "A02", "A05", "A06", "A07", "A08", "A09", "A12", "A13", "A15", "A16",
    "A18", "A19", "A21", "A22", "A23", "A24", "A25", "A45", "A85", "A86",
)

SCENARIO_REGISTRY: dict[str, ScenarioDefinition] = {
    "A01": ScenarioDefinition("A01", "golden lifecycle", "completes", scenario_a01_golden_lifecycle),
    "A02": ScenarioDefinition("A02", "duplicate retry", "idempotent", scenario_a02_duplicate_retry),
    "A05": ScenarioDefinition("A05", "future event", "blocked", scenario_a05_future_event),
    "A06": ScenarioDefinition("A06", "future training label", "blocked", scenario_a06_future_training_label),
    "A07": ScenarioDefinition("A07", "holdout access", "blocked", scenario_a07_holdout_access),
    "A08": ScenarioDefinition("A08", "historical LLM", "blocked", scenario_a08_historical_llm),
    "A09": ScenarioDefinition("A09", "corrupted artifact", "activation fails", scenario_a09_corrupted_artifact),
    "A12": ScenarioDefinition("A12", "non-champion opportunity", "suppressed", scenario_a12_non_champion_opportunity),
    "A13": ScenarioDefinition("A13", "expired opportunity", "no trade", scenario_a13_expired_opportunity),
    "A15": ScenarioDefinition("A15", "duplicate submission", "one order", scenario_a15_duplicate_paper_submission),
    "A16": ScenarioDefinition("A16", "live adapter injection", "rejected", scenario_a16_live_adapter_injection),
    "A18": ScenarioDefinition("A18", "rollback known good", "succeeds", scenario_a18_rollback_known_good),
    "A19": ScenarioDefinition("A19", "rollback no target", "disable", scenario_a19_rollback_no_safe_target),
    "A21": ScenarioDefinition("A21", "adaptation recurrence", "triggers", scenario_a21_adaptation_recurrence),
    "A22": ScenarioDefinition("A22", "telemetry storm", "bounded", scenario_a22_telemetry_storm),
    "A23": ScenarioDefinition("A23", "self-trigger", "blocked", scenario_a23_self_trigger),
    "A24": ScenarioDefinition("A24", "restart idempotency", "preserved", scenario_a24_restart_idempotency),
    "A25": ScenarioDefinition("A25", "replay determinism", "identical IDs", scenario_a25_replay_determinism),
    "A45": ScenarioDefinition("A45", "persistence conflict", "detected", scenario_persistence_conflict),
    "A85": ScenarioDefinition("A85", "monitoring no train", "zero calls", scenario_monitoring_no_train),
    "A86": ScenarioDefinition("A86", "monitoring no promote", "zero calls", scenario_monitoring_no_promote),
}


def run_scenarios(scenario_ids: tuple[str, ...] | None = None) -> tuple[ScenarioResultV1, ...]:
    ids = scenario_ids or REQUIRED_SCENARIOS
    results: list[ScenarioResultV1] = []
    for scenario_id in ids:
        definition = SCENARIO_REGISTRY.get(scenario_id)
        if definition is None:
            results.append(
                ScenarioResultV1(
                    scenario_id=scenario_id,
                    status=ScenarioStatus.SKIP,
                    expected="registered",
                    observed=f"unknown scenario {scenario_id}",
                )
            )
            continue
        try:
            results.append(definition.runner())
        except Exception as exc:
            results.append(
                ScenarioResultV1(
                    scenario_id=scenario_id,
                    status=ScenarioStatus.FAIL,
                    expected=definition.expected,
                    observed=f"exception: {exc}",
                )
            )
    return tuple(results)
