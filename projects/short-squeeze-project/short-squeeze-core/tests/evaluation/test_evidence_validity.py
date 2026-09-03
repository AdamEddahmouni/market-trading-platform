from squeeze_core.contracts import AssetClass
from squeeze_core.evaluation import RuleEvaluationRequest, RuleOutcome
from squeeze_core.evaluation.policies import lookup_policy, lookup_rule
from squeeze_core.evaluation.rules.evidence_validity import evaluate_evidence_validity_rule
from squeeze_core.evidence import CoverageDomain
from squeeze_core.readiness import (
    DomainCoverageSnapshot, EvidenceConflictSummary, InputSufficiencyResult,
    StructuralState,
)

from .helpers import AS_OF, quality

POLICY = lookup_policy("phase_3a_transparent_candidate_policy.v1")


def coverage(*, present=(), missing=(), unavailable=(), unknown=(), conflicted=()):
    requested = tuple(sorted(set(present + missing + unavailable + unknown + conflicted), key=lambda x: x.value))
    return DomainCoverageSnapshot(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        requested_domains=requested, present_domains=present, missing_domains=missing,
        unavailable_domains=unavailable, unknown_domains=unknown,
        conflicted_domains=conflicted, quality=quality(),
    )


def conflicts(count=0):
    return EvidenceConflictSummary(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        conflict_count=count,
        conflict_ids=tuple(f"conflict-{index}" for index in range(count)), quality=quality(),
    )


def sufficiency(*, incompatible=(), insufficient=(), point_in_time=()):
    state = StructuralState.SUFFICIENT if not (incompatible or insufficient or point_in_time) else StructuralState.INSUFFICIENT
    return InputSufficiencyResult(
        operation="candidate-evaluation", policy_version="readiness.v1", symbol="TESTA",
        asset_class=AssetClass.EQUITY, as_of=AS_OF, structural_state=state,
        incompatible_inputs=incompatible, insufficient_history_inputs=insufficient,
        point_in_time_failures=point_in_time, quality=quality(),
    )


def evaluate(rule_id: str, *, readiness=(), providers=("provider-a",), defaults=()):
    request = RuleEvaluationRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        policy_version=POLICY.policy_version, enabled_rule_ids=(rule_id,),
        provider_scope=providers, input_readiness_results=readiness,
        default_substitution_fields=defaults,
    )
    return evaluate_evidence_validity_rule(request, lookup_rule(POLICY, rule_id))


def test_required_domains_present_missing_unknown_and_conflicted():
    domain = CoverageDomain.MARKET_BARS
    assert evaluate("REQUIRED_DOMAINS_PRESENT", readiness=(coverage(present=(domain,)),)).outcome is RuleOutcome.PASS
    assert evaluate("REQUIRED_DOMAINS_PRESENT", readiness=(coverage(missing=(domain,)),)).outcome is RuleOutcome.FAIL
    assert evaluate("REQUIRED_DOMAINS_PRESENT", readiness=(coverage(unavailable=(domain,)),)).outcome is RuleOutcome.UNKNOWN
    assert evaluate("REQUIRED_DOMAINS_PRESENT", readiness=(coverage(unknown=(domain,)),)).outcome is RuleOutcome.UNKNOWN
    assert evaluate("REQUIRED_DOMAINS_PRESENT", readiness=(coverage(conflicted=(domain,)),)).outcome is RuleOutcome.CONFLICTED


def test_no_material_conflicts_reuses_phase_2d_summary():
    assert evaluate("NO_MATERIAL_CONFLICTS", readiness=(conflicts(0),)).outcome is RuleOutcome.PASS
    assert evaluate("NO_MATERIAL_CONFLICTS", readiness=(conflicts(1),)).outcome is RuleOutcome.CONFLICTED
    # Temporal differences are excluded by Phase 2D and therefore arrive with count zero.
    assert evaluate("NO_MATERIAL_CONFLICTS", readiness=(conflicts(0),)).outcome is RuleOutcome.PASS


def test_units_history_and_point_in_time_are_independent():
    assert evaluate("REQUIRED_UNITS_COMPATIBLE", readiness=(sufficiency(),)).outcome is RuleOutcome.PASS
    assert evaluate("REQUIRED_UNITS_COMPATIBLE", readiness=(sufficiency(incompatible=("metric-unit",)),)).outcome is RuleOutcome.INSUFFICIENT_DATA
    assert evaluate("REQUIRED_HISTORY_SUFFICIENT", readiness=(sufficiency(),)).outcome is RuleOutcome.PASS
    assert evaluate("REQUIRED_HISTORY_SUFFICIENT", readiness=(sufficiency(insufficient=("volume-history",)),)).outcome is RuleOutcome.INSUFFICIENT_DATA
    assert evaluate("POINT_IN_TIME_ELIGIBLE", readiness=(sufficiency(),)).outcome is RuleOutcome.PASS
    assert evaluate("POINT_IN_TIME_ELIGIBLE", readiness=(sufficiency(point_in_time=("future-input",)),)).outcome is RuleOutcome.FAIL


def test_no_default_substitution_and_provider_scope_explicit():
    assert evaluate("NO_DEFAULT_SUBSTITUTION").outcome is RuleOutcome.PASS
    assert evaluate("NO_DEFAULT_SUBSTITUTION", defaults=("price",)).outcome is RuleOutcome.FAIL
    assert evaluate("PROVIDER_SCOPE_EXPLICIT").outcome is RuleOutcome.PASS
    assert evaluate("PROVIDER_SCOPE_EXPLICIT", providers=()).outcome is RuleOutcome.UNKNOWN


def test_missing_phase_2d_result_is_unknown_not_failure():
    for rule_id in (
        "REQUIRED_DOMAINS_PRESENT", "NO_MATERIAL_CONFLICTS", "POINT_IN_TIME_ELIGIBLE",
        "REQUIRED_UNITS_COMPATIBLE", "REQUIRED_HISTORY_SUFFICIENT",
    ):
        assert evaluate(rule_id).outcome is RuleOutcome.UNKNOWN
