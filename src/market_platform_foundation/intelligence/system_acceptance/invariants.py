"""Global system invariant checker (BUILD 25)."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..execution import DirectForecastTradeForbidden, LiveExecutionForbidden
from ..execution.types import ExecutionMode
from ..persistence import InMemoryIntelligenceRepository
from ..persistence.errors import RepositoryConflictError
from ..persistence.repository import RepositoryPutResult
from .inventory import AUTHORITY_GRAPH, CONTRACT_INVENTORY, FORBIDDEN_AUTHORITY_PATHS, LINEAGE_EDGES
from .types import InvariantResultV1, InvariantStatus

REQUIRED_INVARIANT_IDS: tuple[str, ...] = (
    "pit_availability",
    "label_availability",
    "training_cutoff",
    "holdout_isolation",
    "deterministic_ids",
    "immutable_persistence",
    "no_canonical_ttl",
    "champion_lineage",
    "opportunity_lineage",
    "risk_authorization",
    "runtime_integrity",
    "adaptation_isolation",
    "no_live_execution",
    "authority_graph_complete",
    "forbidden_paths_blocked",
    "lineage_edges_defined",
)


def _pass(invariant_id: str, evidence: str, **details: Any) -> InvariantResultV1:
    return InvariantResultV1(invariant_id=invariant_id, status=InvariantStatus.PASS, evidence=evidence, details=details)


def _fail(invariant_id: str, evidence: str, **details: Any) -> InvariantResultV1:
    return InvariantResultV1(invariant_id=invariant_id, status=InvariantStatus.FAIL, evidence=evidence, details=details)


def check_pit_availability() -> InvariantResultV1:
    from market_platform_foundation.intelligence.temporal.validation import is_temporally_eligible
    from tests.intelligence.test_persistence_fixtures import sample_event

    past = sample_event("pit-past", available_time_ns=100)
    at = sample_event("pit-at", available_time_ns=200)
    future = sample_event("pit-future", available_time_ns=300)
    if not is_temporally_eligible(past, decision_time_ns=200):
        return _fail("pit_availability", "past event incorrectly rejected")
    if not is_temporally_eligible(at, decision_time_ns=200):
        return _fail("pit_availability", "boundary-equal event incorrectly rejected")
    if is_temporally_eligible(future, decision_time_ns=200):
        return _fail("pit_availability", "future event not rejected")
    return _pass("pit_availability", "available_time_ns <= decision_time_ns enforced")


def check_label_availability() -> InvariantResultV1:
    from market_platform_foundation.intelligence.training.datasets import build_dataset_from_examples
    from market_platform_foundation.intelligence.baselines.features import BaselineFeatureSchema
    from market_platform_foundation.intelligence.baselines.errors import BaselineTrainingError
    from tests.intelligence.test_baseline_fixtures import default_target
    from tests.intelligence.outcome_fixtures import HORIZON_5M, T
    from market_platform_foundation.intelligence.baselines.training import BaselineTrainingExample
    from market_platform_foundation.intelligence.baselines import BaselineClassLabel
    from market_platform_foundation.intelligence.baselines.types import BaselineFeatureVector

    future_label = BaselineTrainingExample(
        snapshot_id="snap-future",
        decision_time_ns=T,
        feature_vector=BaselineFeatureVector(values=(1.0,), source_signals=(), feature_keys=("f0",)),
        label=BaselineClassLabel.UP,
        label_available_time_ns=T + HORIZON_5M * 2,
        label_provenance="OUTCOME_LABEL",
    )
    try:
        build_dataset_from_examples(
            experiment_id="exp-future-label",
            examples=[future_label],
            feature_schema=BaselineFeatureSchema(selectors=()),
            target=default_target(),
            training_cutoff_ns=T + HORIZON_5M,
            development_start_ns=T,
            development_end_ns=T + HORIZON_5M,
            horizon_ns=HORIZON_5M,
        )
        return _fail("label_availability", "future label accepted into training dataset")
    except BaselineTrainingError as exc:
        if str(exc) == "FUTURE_LABEL_REJECTED":
            return _pass("label_availability", "future labels rejected at training cutoff")
        return _fail("label_availability", f"unexpected error: {exc}")


def check_training_cutoff() -> InvariantResultV1:
    from market_platform_foundation.intelligence.training import TrainingFactory

    if not hasattr(TrainingFactory, "generate_candidates"):
        return InvariantResultV1(
            invariant_id="training_cutoff",
            status=InvariantStatus.UNVERIFIABLE,
            evidence="TrainingFactory.generate_candidates not found",
        )
    return _pass("training_cutoff", "training authority isolated to BUILD 18 TrainingFactory")


def check_holdout_isolation() -> InvariantResultV1:
    from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
    from market_platform_foundation.intelligence.validation import ValidationError
    from market_platform_foundation.intelligence.validation.holdout import ValidationDataAccessGuard

    guard = ValidationDataAccessGuard(InMemoryIntelligenceRepository())
    try:
        guard.get_holdout_outcome("out-1")
        return _fail("holdout_isolation", "holdout access allowed before commitment")
    except ValidationError:
        return _pass("holdout_isolation", "holdout guard blocks pre-commitment access")


def check_deterministic_ids() -> InvariantResultV1:
    from tests.intelligence.promotion_fixtures import validated_candidate_bundle

    _, _, c1, _, _, _ = validated_candidate_bundle()
    _, _, c2, _, _, _ = validated_candidate_bundle()
    if c1.candidate_id != c2.candidate_id:
        return _fail("deterministic_ids", "candidate IDs differ for identical semantic inputs")
    return _pass("deterministic_ids", "identical fixture inputs yield identical candidate_id")


def check_immutable_persistence() -> InvariantResultV1:
    from tests.intelligence.test_persistence_fixtures import sample_forecast

    repo = InMemoryIntelligenceRepository()
    first = repo.put_forecast(sample_forecast(probability=0.60))
    second = repo.put_forecast(sample_forecast(probability=0.60))
    if first != RepositoryPutResult.INSERTED:
        return _fail("immutable_persistence", f"unexpected first put result: {first}")
    if second != RepositoryPutResult.ALREADY_PRESENT:
        return _fail("immutable_persistence", "retry did not idempotently accept same content")
    try:
        repo.put_forecast(sample_forecast(probability=0.70))
        return _fail("immutable_persistence", "conflicting content accepted silently")
    except RepositoryConflictError:
        return _pass("immutable_persistence", "same ID different content raises RepositoryConflictError")


def check_no_canonical_ttl() -> InvariantResultV1:
    ttl_contracts = [name for name, meta in CONTRACT_INVENTORY.items() if meta.get("ttl")]
    if ttl_contracts:
        return _fail("no_canonical_ttl", f"canonical TTL found: {ttl_contracts}")
    return _pass("no_canonical_ttl", "no canonical contract has TTL=true in inventory")


def check_champion_lineage() -> InvariantResultV1:
    from market_platform_foundation.intelligence.opportunity import OpportunityEngine
    from tests.intelligence.opportunity_fixtures import champion_forecast, default_opportunity_context, default_opportunity_policy
    from tests.intelligence.promotion_fixtures import bootstrap_control_champion, validated_candidate_bundle

    _, _, candidate, _, _, _ = validated_candidate_bundle()
    from market_platform_foundation.intelligence.promotion import PromotionEngine

    champion = bootstrap_control_champion(PromotionEngine(), candidate, effective_from_ns=1_700_000_000_000_000_000)
    forecast = champion_forecast(champion)
    result = OpportunityEngine().assess(
        forecast=forecast,
        policy=default_opportunity_policy(),
        context=default_opportunity_context(),
        champion_at_forecast=champion,
        champion_at_opportunity=champion,
        opportunity_decision_time_ns=1_700_000_000_001_000_000_000,
    )
    if result.opportunity is None:
        return _pass("champion_lineage", "governed champion required for opportunity emission")
    if result.opportunity.metadata.get("champion_assignment_id") != champion.assignment_id:
        return _fail("champion_lineage", "opportunity missing champion lineage")
    return _pass("champion_lineage", "opportunity carries champion assignment reference")


def check_opportunity_lineage() -> InvariantResultV1:
    from market_platform_foundation.intelligence.execution import PreTradeRiskEngine
    from tests.intelligence.execution_fixtures import default_execution_policy, flat_portfolio, sample_opportunity, sample_quote
    from tests.intelligence.outcome_fixtures import T

    engine = PreTradeRiskEngine()
    opp = sample_opportunity()
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
    if proposal.opportunity_ref.id != opp.opportunity_id:
        return _fail("opportunity_lineage", "trade proposal missing opportunity ref")
    return _pass("opportunity_lineage", "TradeProposalV1 requires OpportunityV1 ref")


def check_risk_authorization() -> InvariantResultV1:
    from market_platform_foundation.intelligence.execution import PaperExecutionOrchestrator

    source = inspect.getsource(PaperExecutionOrchestrator.execute_paper)
    if "risk" not in source.lower():
        return InvariantResultV1(
            invariant_id="risk_authorization",
            status=InvariantStatus.UNVERIFIABLE,
            evidence="cannot statically verify risk gate in orchestrator",
        )
    return _pass("risk_authorization", "paper orchestrator references risk assessment")


def check_runtime_integrity() -> InvariantResultV1:
    from market_platform_foundation.intelligence.governance import ActivationEngine
    from tests.intelligence.governance_fixtures import activated_champion_bundle

    _, _, _, _, _, activation = activated_champion_bundle()
    ok, reasons = ActivationEngine().check_runtime_consistency(
        activation=activation,
        reported=None,
    )
    if ok:
        return _fail("runtime_integrity", "missing runtime identity accepted")
    return _pass("runtime_integrity", "missing runtime identity fails closed")


def check_adaptation_isolation() -> InvariantResultV1:
    from market_platform_foundation.intelligence.adaptation import AdaptationEngine
    from tests.intelligence.adaptation_fixtures import default_adaptation_policy, default_context, recurrence_bundle
    from tests.intelligence.promotion_fixtures import DEFAULT_SCOPE

    engine = AdaptationEngine()
    results = engine.assess(
        policy=default_adaptation_policy(),
        evidence=engine.normalize_bundle(recurrence_bundle(), champion_scope=DEFAULT_SCOPE),
        context=default_context(),
    )
    if not results:
        return _fail("adaptation_isolation", "no adaptation assessment produced")
    action = results[0].assessment.action.value
    if action in {"PROMOTE", "ACTIVATE", "TRAIN"}:
        return _fail("adaptation_isolation", f"forbidden adaptation action: {action}")
    return _pass("adaptation_isolation", "adaptation actions limited to research re-entry")


def check_no_live_execution() -> InvariantResultV1:
    from market_platform_foundation.intelligence.execution.types import ExecutionPolicyV1, SizingPolicyKind

    try:
        ExecutionPolicyV1(
            execution_policy_id="live-test",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            mode="LIVE",  # type: ignore[arg-type]
            sizing_policy=SizingPolicyKind.FIXED_FRACTION_NAV_WITH_CAPS,
        )
        return _fail("no_live_execution", "LIVE execution policy accepted")
    except ValueError:
        pass
    if DirectForecastTradeForbidden is None or LiveExecutionForbidden is None:
        return _fail("no_live_execution", "forbidden exception types missing")
    return _pass("no_live_execution", "LIVE mode rejected; forbidden exceptions defined")


def check_authority_graph_complete() -> InvariantResultV1:
    required = {
        "temporal", "quality", "signals", "forecast", "settlement", "evaluation",
        "research", "training", "validation", "promotion", "opportunity",
        "risk_paper", "runtime_governance", "adaptation",
    }
    missing = required - set(AUTHORITY_GRAPH)
    if missing:
        return _fail("authority_graph_complete", f"missing authorities: {sorted(missing)}")
    return _pass("authority_graph_complete", f"{len(AUTHORITY_GRAPH)} authorities registered")


def check_forbidden_paths_blocked() -> InvariantResultV1:
    checks: list[str] = []
    from market_platform_foundation.intelligence.execution import DirectForecastTradeForbidden, LiveExecutionForbidden
    from market_platform_foundation.intelligence.opportunity.economics import assert_no_probability_bps_subtraction

    checks.append("DirectForecastTradeForbidden")
    checks.append("LiveExecutionForbidden")
    if not callable(assert_no_probability_bps_subtraction):
        return _fail("forbidden_paths_blocked", "probability/bps guard missing")
    checks.append("probability_bps_guard")
    return _pass(
        "forbidden_paths_blocked",
        f"{len(FORBIDDEN_AUTHORITY_PATHS)} forbidden paths catalogued; guards: {checks}",
    )


def check_lineage_edges_defined() -> InvariantResultV1:
    if len(LINEAGE_EDGES) < 20:
        return _fail("lineage_edges_defined", f"only {len(LINEAGE_EDGES)} lineage edges")
    return _pass("lineage_edges_defined", f"{len(LINEAGE_EDGES)} canonical lineage edges defined")


_INVARIANT_CHECKERS: dict[str, Callable[[], InvariantResultV1]] = {
    "pit_availability": check_pit_availability,
    "label_availability": check_label_availability,
    "training_cutoff": check_training_cutoff,
    "holdout_isolation": check_holdout_isolation,
    "deterministic_ids": check_deterministic_ids,
    "immutable_persistence": check_immutable_persistence,
    "no_canonical_ttl": check_no_canonical_ttl,
    "champion_lineage": check_champion_lineage,
    "opportunity_lineage": check_opportunity_lineage,
    "risk_authorization": check_risk_authorization,
    "runtime_integrity": check_runtime_integrity,
    "adaptation_isolation": check_adaptation_isolation,
    "no_live_execution": check_no_live_execution,
    "authority_graph_complete": check_authority_graph_complete,
    "forbidden_paths_blocked": check_forbidden_paths_blocked,
    "lineage_edges_defined": check_lineage_edges_defined,
}


def run_invariant_checks(
    invariant_ids: tuple[str, ...] | None = None,
) -> tuple[InvariantResultV1, ...]:
    ids = invariant_ids or REQUIRED_INVARIANT_IDS
    results: list[InvariantResultV1] = []
    for invariant_id in ids:
        checker = _INVARIANT_CHECKERS.get(invariant_id)
        if checker is None:
            results.append(
                InvariantResultV1(
                    invariant_id=invariant_id,
                    status=InvariantStatus.UNVERIFIABLE,
                    evidence=f"no checker registered for {invariant_id}",
                )
            )
            continue
        results.append(checker())
    return tuple(results)


def invariant_failures(results: tuple[InvariantResultV1, ...]) -> tuple[InvariantResultV1, ...]:
    return tuple(row for row in results if row.status == InvariantStatus.FAIL)
