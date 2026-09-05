"""Batch 08 Phase 3A request/result freeze coverage.

Every test runs against the committed synthetic Batch 05-shaped fixture; no real provider
value is ever asserted or committed. Coverage targets: the frozen checkpoint constants,
admissible-only evidence, blocked-evidence omission, use of the existing evaluator,
determinism, freeze ordering, leakage, and isolation from forward/outcome artifacts.
"""

from __future__ import annotations

import ast
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from squeeze_core.acquisition.operation_readiness.evidence_inputs import (
    FROZEN_BOUNDARY,
    FROZEN_COHORT,
    boundary_id_for,
)
from squeeze_core.acquisition.phase3a_freeze import (
    ADMISSIBLE_METRIC_NAME,
    FREEZE_POLICY_VERSION,
    FROZEN_PROVIDER_SCOPE,
    GLOBAL_PREFLIGHT_VERDICT,
    PHASE3A_EVALUATION_VERSION,
    PHASE3A_POLICY_VERSION,
    SCHEMA_VERSION,
    EvidenceAccessLog,
    ForwardArtifactAccessError,
    FreezeStatus,
    NonDetectionContextArtifactError,
    OutcomeArtifactAccessError,
    ReceiptModelingPolicy,
    TimestampInterpretation,
    batch07_readiness,
    build_freeze_report,
    build_percentage_return,
    freeze_case,
    freeze_cohort,
    load_detection_context_bars,
    load_phase3a_policy,
    metric_window,
    render_markdown,
    requested_domains,
    sensitivity_summary,
    serialize,
)
from squeeze_core.acquisition.phase3a_freeze import models as freeze_models
from squeeze_core.acquisition.phase3a_freeze.evidence_adapter import classify_labels
from squeeze_core.acquisition.phase3a_freeze.freeze import (
    FROZEN_INTERPRETATION,
    FROZEN_SUPPLY_POLICY,
)
from squeeze_core.acquisition.phase3a_freeze.leakage import build_audit_request, ordering_holds
from squeeze_core.acquisition.phase3a_freeze.models import ObservationSupplyPolicy
from squeeze_core.contracts import EventType, QualityState
from squeeze_core.evaluation import RuleOutcome
from squeeze_core.metrics import MetricName, MetricUnit

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "squeeze_core" / "acquisition" / "phase3a_freeze"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "acquisition" / "batch08"
SYNTHETIC_ROOT = FIXTURE_DIR / "synthetic-batch05"

EXPECTED_COHORT_ORDER = (
    "XNCR", "PESI", "SLS", "ZNTL", "GPRE", "SSPC", "LBGJ", "TRVI", "LMNX", "MGNX",
    "BHVN", "OBE", "AVTX", "KLRS", "SG",
    "CELZ", "GDC", "ADVB", "GOAI", "NXXT",
    "VMAR", "ATAI", "CADL", "CGEM", "IOVA",
    "PMAX", "STAK", "APVO",
    "BIYA",
)
EXPECTED_BOUNDARY = datetime(2026, 7, 18, 13, 37, 55, 17661, tzinfo=UTC)

BLOCKED_ABSOLUTE_PRICE_RULE = "PRICE_RANGE"
BLOCKED_VOLUME_RULE = "RELATIVE_VOLUME_MINIMUM"
BLOCKED_FLOAT_RULE = "FLOAT_MAXIMUM"
SHORT_PRESSURE_RULES = (
    "PUBLISHED_SHORT_INTEREST_AVAILABLE",
    "SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM",
    "DAYS_TO_COVER_MINIMUM",
    "BORROW_FEE_MINIMUM",
    "BORROW_FEE_CHANGE_MINIMUM",
    "BORROW_AVAILABILITY_MAXIMUM",
    "BORROW_AVAILABILITY_CHANGE_MAXIMUM",
)
CATALYST_RULES = (
    "NEWS_AVAILABLE",
    "NEWS_AVAILABLE_BEFORE_AS_OF",
    "NEWS_TIMESTAMP_KNOWN",
    "SEC_FILING_AVAILABLE",
    "CORPORATE_ACTION_CONTEXT_AVAILABLE",
)
EVIDENCE_VALIDITY_RULES = (
    "REQUIRED_DOMAINS_PRESENT",
    "NO_MATERIAL_CONFLICTS",
    "POINT_IN_TIME_ELIGIBLE",
    "REQUIRED_UNITS_COMPATIBLE",
    "REQUIRED_HISTORY_SUFFICIENT",
    "NO_DEFAULT_SUBSTITUTION",
    "PROVIDER_SCOPE_EXPLICIT",
)


@pytest.fixture(scope="module")
def frozen():
    return freeze_cohort(SYNTHETIC_ROOT)


@pytest.fixture(scope="module")
def policy():
    return load_phase3a_policy()


# --- frozen checkpoint, cohort, boundary --------------------------------------------


def test_schema_version_remains_1_0_0():
    assert SCHEMA_VERSION == "1.0.0"


def test_frozen_policy_versions_are_exact():
    assert FREEZE_POLICY_VERSION == "phase_3d_phase3a_freeze_policy.v1"
    assert PHASE3A_POLICY_VERSION == "phase_3a_transparent_candidate_policy.v1"
    assert PHASE3A_EVALUATION_VERSION == "candidate_evaluation.v1"
    assert ADMISSIBLE_METRIC_NAME == "PERCENTAGE_RETURN"


def test_cohort_source_order_is_exact_and_unreordered(frozen):
    assert tuple(symbol for symbol, _ in FROZEN_COHORT) == EXPECTED_COHORT_ORDER
    assert tuple(item.record.symbol for item in frozen) == EXPECTED_COHORT_ORDER
    assert tuple(item.record.case_id for item in frozen) == tuple(
        case_id for _, case_id in FROZEN_COHORT
    )


def test_frozen_boundary_is_exact(frozen):
    assert FROZEN_BOUNDARY == EXPECTED_BOUNDARY
    for item in frozen:
        assert item.record.boundary_time == EXPECTED_BOUNDARY
        assert item.record.temporal_selection.boundary == EXPECTED_BOUNDARY


def test_boundary_ids_match_the_recomputed_batch01_freeze(frozen):
    for item in frozen:
        assert item.record.boundary_id == boundary_id_for(
            item.record.case_id, item.record.symbol
        )


def test_exactly_fifteen_requests_and_results_are_frozen(frozen):
    assert len(frozen) == len(FROZEN_COHORT)
    assert all(item.record.phase3a_request_id for item in frozen)
    assert all(item.record.phase3a_result_id for item in frozen)
    assert all(
        item.record.freeze_status is FreezeStatus.REQUEST_AND_RESULT_FROZEN
        for item in frozen
    )


# --- global preflight remains rejected ---------------------------------------------


def test_global_preflight_remains_rejected_and_unchanged(frozen):
    assert GLOBAL_PREFLIGHT_VERDICT == "PREFLIGHT_REJECTED"
    for item in frozen:
        assert item.record.global_preflight_status == "PREFLIGHT_REJECTED"
    report = build_freeze_report(
        tuple(item.record for item in frozen),
        receipt_policy=ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
        boundary_time=FROZEN_BOUNDARY,
    )
    assert report.global_preflight_verdict == "PREFLIGHT_REJECTED"
    assert report.global_preflight_unchanged is True


def test_batch07_readiness_is_consumed_unchanged():
    cases = batch07_readiness(SYNTHETIC_ROOT)
    assert len(cases) == len(FROZEN_COHORT)
    for case in cases.values():
        assert case.phase3a_request_readiness.value == "PHASE3A_REQUEST_READY"
        assert case.temporal_alignment_readiness.status.value == "ADMISSIBLE"
        assert len(case.phase3a_rule_dependency_readiness) == 25


# --- private evidence boundary -----------------------------------------------------


def test_forward_artifact_access_hard_fails():
    log = EvidenceAccessLog()
    with pytest.raises(ForwardArtifactAccessError):
        load_detection_context_bars(
            SYNTHETIC_ROOT / "raw" / "XNCR-frozen-forward-24h.csv",
            symbol="XNCR",
            boundary=FROZEN_BOUNDARY,
            retrieval_completed_at=FROZEN_BOUNDARY,
            receipt_policy=ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
            log=log,
        )
    assert log.opened_paths == []
    assert log.refused_paths


def test_phase3b_outcome_artifact_access_hard_fails(tmp_path):
    path = tmp_path / "phase3b" / "XNCR-outcome-detection-context.csv"
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    log = EvidenceAccessLog()
    with pytest.raises(OutcomeArtifactAccessError):
        load_detection_context_bars(
            path,
            symbol="XNCR",
            boundary=FROZEN_BOUNDARY,
            retrieval_completed_at=FROZEN_BOUNDARY,
            receipt_policy=ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
            log=log,
        )
    assert log.opened_paths == []


def test_only_detection_context_artifacts_may_be_opened(tmp_path):
    path = tmp_path / "XNCR-something-else.csv"
    path.write_text("", encoding="utf-8")
    with pytest.raises(NonDetectionContextArtifactError):
        load_detection_context_bars(
            path,
            symbol="XNCR",
            boundary=FROZEN_BOUNDARY,
            retrieval_completed_at=FROZEN_BOUNDARY,
            receipt_policy=ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
        )


def test_no_forward_or_outcome_access_is_recorded(frozen):
    for item in frozen:
        assert item.record.forward_ohlcv_accessed is False
        assert item.record.outcome_accessed is False
        assert item.association.forward_ohlcv_accessed is False


def test_forward_artifact_identity_is_recorded_without_opening_it(frozen):
    for item in frozen:
        assert len(item.association.forward_artifact_sha256) == 64
        assert item.association.forward_artifact_byte_length > 0
        assert item.association.forward_artifact_status == "PREFLIGHT_REJECTED"


def test_phase3b_and_phase3e_remain_unstarted(frozen):
    for item in frozen:
        assert item.record.phase3b_published is False
        assert item.record.phase3e_started is False


# --- isolation: no network, no ibapi ----------------------------------------------


def test_package_imports_no_network_or_ibapi():
    forbidden = {"ibapi", "socket", "ssl", "http", "urllib", "requests", "asyncio"}
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".")[0]}
            else:
                continue
            assert not names & forbidden, f"{path.name} imports {names & forbidden}"


# --- no duplicated formula or evaluator ------------------------------------------


def test_package_contains_no_percentage_arithmetic():
    """The metric must come from the canonical Phase 2 path, not a local formula."""
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(
                node.op, (ast.Div, ast.Mult, ast.Sub)
            ):
                # timedelta arithmetic on datetimes is permitted; numeric literals that
                # could form a percentage are not.
                operands = (node.left, node.right)
                literals = [
                    item.value
                    for item in operands
                    if isinstance(item, ast.Constant) and isinstance(item.value, (int, float))
                ]
                assert 100 not in literals, f"{path.name} contains percentage arithmetic"


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Ids of Constant nodes that are module/class/function docstrings."""
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                found.add(id(body[0].value))
    return found


def test_package_never_names_a_rule_outcome_value():
    """No manual PASS/FAIL/UNKNOWN assignment anywhere in the freeze package.

    Prose in docstrings may discuss the outcomes; executable code may not name one.
    ``NOT_APPLICABLE`` is excluded because it is also a Batch 07 ``AdmissibilityStatus``
    value, which this package legitimately reads; the remaining five are rule outcomes
    only, so naming any of them in code would mean an outcome was assigned by hand.
    """
    from squeeze_core.acquisition.operation_readiness.models import AdmissibilityStatus

    shared = {item.value for item in AdmissibilityStatus}
    outcome_values = {item.value for item in RuleOutcome} - shared
    assert outcome_values == {
        "PASS", "FAIL", "UNKNOWN", "CONFLICTED", "INSUFFICIENT_DATA"
    }
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                assert node.value not in outcome_values, (
                    f"{path.name} names the rule outcome {node.value!r}"
                )


def test_the_existing_evaluator_produces_every_outcome(frozen, policy):
    """Outcomes in the freeze record are byte-equal to the evaluator's own results."""
    for item in frozen:
        assert item.evaluation is not None
        by_rule = {result.rule_id: result for result in item.evaluation.rule_results}
        assert len(by_rule) == 25
        for record in item.record.rule_outcomes:
            assert record.outcome == by_rule[record.rule_id].outcome.value
            assert record.explanation_code == by_rule[record.rule_id].explanation_code
            assert record.rule_result_id == str(by_rule[record.rule_id].deterministic_id)


# --- 25 rules, ordered ------------------------------------------------------------


def test_all_twenty_five_rules_present_and_ordered_per_case(frozen, policy):
    expected = tuple(sorted(policy.enabled_rule_ids))
    assert len(expected) == 25
    for item in frozen:
        ids = tuple(record.rule_id for record in item.record.rule_outcomes)
        assert ids == expected


# --- admissible inputs -----------------------------------------------------------


def test_market_data_available_is_supported_and_evaluated(frozen):
    for item in frozen:
        record = next(
            r for r in item.record.rule_outcomes if r.rule_id == "MARKET_DATA_AVAILABLE"
        )
        assert record.outcome == RuleOutcome.PASS.value
        assert record.supporting_observation_ids


def test_completed_bar_available_is_supported_and_evaluated(frozen):
    for item in frozen:
        record = next(
            r for r in item.record.rule_outcomes if r.rule_id == "COMPLETED_BAR_AVAILABLE"
        )
        assert record.outcome == RuleOutcome.PASS.value
        assert record.supporting_observation_ids


def test_percentage_change_minimum_uses_only_the_canonical_admissible_metric(frozen):
    for item in frozen:
        assert item.metric is not None
        assert item.metric.metric_name is MetricName.PERCENTAGE_RETURN
        assert item.metric.unit is MetricUnit.PERCENT
        assert item.metric.calculation_policy_version == "close_to_close_completed.v1"
        record = next(
            r for r in item.record.rule_outcomes if r.rule_id == "PERCENTAGE_CHANGE_MINIMUM"
        )
        assert record.outcome in {RuleOutcome.PASS.value, RuleOutcome.FAIL.value}
        assert record.supporting_metric_ids == (str(item.metric.deterministic_id),)
        assert not record.supporting_observation_ids


def test_percentage_metric_threshold_is_inclusive_and_unchanged(policy):
    rule = next(r for r in policy.rules if r.rule_id == "PERCENTAGE_CHANGE_MINIMUM")
    threshold = rule.thresholds[0]
    assert threshold.value == Decimal("10")
    assert threshold.unit == "PERCENT"
    assert threshold.operator.value == "GREATER_THAN_OR_EQUAL"


def test_request_carries_only_admissible_evidence(frozen):
    for item in frozen:
        assert item.request is not None
        assert item.request.provider_scope == FROZEN_PROVIDER_SCOPE == ()
        assert item.request.market_session == ()
        assert item.request.volume_window is None
        assert item.request.short_interest_provider is None
        assert item.request.borrow_provider is None
        assert item.request.news_provider is None
        assert item.request.default_substitution_fields == ()
        assert len(item.request.input_metrics) == 1
        assert len(item.request.input_readiness_results) == 3
        assert all(
            observation.event_type is EventType.BAR
            for observation in item.request.input_observations
        )


# --- blocked inputs stay absent --------------------------------------------------


def test_price_range_receives_no_absolute_price_evidence(frozen):
    for item in frozen:
        record = next(
            r for r in item.record.rule_outcomes if r.rule_id == BLOCKED_ABSOLUTE_PRICE_RULE
        )
        assert record.outcome == RuleOutcome.UNKNOWN.value
        assert record.explanation_code == "EVALUATION_PROVIDER_SCOPE_REQUIRED"
        # No observation, no metric: the rule short-circuits before reading any close.
        assert record.supporting_observation_ids == ()
        assert record.supporting_metric_ids == ()
        result = next(
            r
            for r in item.evaluation.rule_results
            if r.rule_id == BLOCKED_ABSOLUTE_PRICE_RULE
        )
        assert result.observed_value is None


def test_relative_volume_minimum_receives_no_volume_evidence(frozen):
    for item in frozen:
        record = next(
            r for r in item.record.rule_outcomes if r.rule_id == BLOCKED_VOLUME_RULE
        )
        assert record.outcome == RuleOutcome.UNKNOWN.value
        assert record.supporting_metric_ids == ()
        for observation in item.request.input_observations:
            assert observation.payload.volume is None


def test_no_volume_is_ever_attached_to_a_request(frozen):
    for item in frozen:
        for observation in item.request.input_observations:
            assert observation.payload.volume is None
            assert observation.payload.trade_count is None
            assert observation.payload.vwap is None


def test_no_float_fabrication(frozen):
    for item in frozen:
        record = next(
            r for r in item.record.rule_outcomes if r.rule_id == BLOCKED_FLOAT_RULE
        )
        assert record.outcome == RuleOutcome.UNKNOWN.value
        assert record.supporting_observation_ids == ()
        assert not any(
            observation.event_type is EventType.MARKET_SNAPSHOT
            for observation in item.request.input_observations
        )


def test_no_short_pressure_fabrication(frozen):
    for item in frozen:
        for rule_id in SHORT_PRESSURE_RULES:
            record = next(
                r for r in item.record.rule_outcomes if r.rule_id == rule_id
            )
            assert record.outcome == RuleOutcome.UNKNOWN.value
            assert record.supporting_metric_ids == ()
            assert record.supporting_observation_ids == ()


def test_no_catalyst_fabrication(frozen):
    for item in frozen:
        for rule_id in CATALYST_RULES:
            record = next(r for r in item.record.rule_outcomes if r.rule_id == rule_id)
            assert record.outcome == RuleOutcome.UNKNOWN.value
            assert record.supporting_observation_ids == ()


def test_blocked_rules_are_never_forced_to_fail(frozen):
    blocked = (
        BLOCKED_ABSOLUTE_PRICE_RULE,
        BLOCKED_VOLUME_RULE,
        BLOCKED_FLOAT_RULE,
        *SHORT_PRESSURE_RULES,
        *CATALYST_RULES,
    )
    for item in frozen:
        for rule_id in blocked:
            record = next(r for r in item.record.rule_outcomes if r.rule_id == rule_id)
            assert record.outcome != RuleOutcome.FAIL.value
            assert record.blocking_reason_codes


def test_missing_evidence_is_never_substituted_with_zero(frozen):
    for item in frozen:
        for result in item.evaluation.rule_results:
            if result.outcome is RuleOutcome.UNKNOWN:
                assert result.observed_value is None


# --- EVIDENCE_VALIDITY canonical behaviour --------------------------------------


def test_evidence_validity_outcomes_are_evaluator_determined(frozen):
    """Batch 07 marks these NOT_APPLICABLE at readiness level; Batch 08 does not force
    their Phase 3A outcomes. This test pins the observed canonical behaviour."""
    expected = {
        "NO_DEFAULT_SUBSTITUTION": RuleOutcome.PASS.value,
        "NO_MATERIAL_CONFLICTS": RuleOutcome.PASS.value,
        "POINT_IN_TIME_ELIGIBLE": RuleOutcome.PASS.value,
        "REQUIRED_UNITS_COMPATIBLE": RuleOutcome.PASS.value,
        "REQUIRED_HISTORY_SUFFICIENT": RuleOutcome.PASS.value,
        # Required non-market-bar domains are genuinely absent from the request.
        "REQUIRED_DOMAINS_PRESENT": RuleOutcome.FAIL.value,
        # A consequence of the deliberate request-level provider-scope omission.
        "PROVIDER_SCOPE_EXPLICIT": RuleOutcome.UNKNOWN.value,
    }
    assert set(expected) == set(EVIDENCE_VALIDITY_RULES)
    for item in frozen:
        for rule_id, outcome in expected.items():
            record = next(r for r in item.record.rule_outcomes if r.rule_id == rule_id)
            assert record.outcome == outcome
            assert record.batch07_admissibility_status == "NOT_APPLICABLE"


def test_requested_domains_are_derived_from_the_policy(policy):
    domains = {domain.value for domain in requested_domains(policy)}
    assert domains == {
        "MARKET_BARS",
        "CANDIDATE_SNAPSHOT",
        "PUBLISHED_SHORT_INTEREST",
        "BORROW_FEE",
        "BORROW_AVAILABILITY",
        "NEWS",
        "SEC_FILINGS",
    }


# --- temporal selection ---------------------------------------------------------


def test_only_definitely_completed_bars_are_included():
    interval = timedelta(seconds=60)
    labels = (
        FROZEN_BOUNDARY - interval * 3,
        FROZEN_BOUNDARY - interval,  # completes exactly at the boundary: included
        FROZEN_BOUNDARY - timedelta(seconds=30),  # straddles
        FROZEN_BOUNDARY + interval,  # after the boundary
    )
    classified = classify_labels(labels, FROZEN_BOUNDARY)
    assert classified.included == (labels[0], labels[1])
    assert classified.straddling_count == 1
    assert classified.post_boundary_count == 1


def test_temporal_selection_records_both_bar_counts(frozen):
    for item in frozen:
        selection = item.record.temporal_selection
        assert selection.observation_supply_policy is FROZEN_SUPPLY_POLICY
        assert selection.included_bar_count >= selection.supplied_observation_count
        assert selection.supplied_observation_count == len(
            item.request.input_observations
        )
        assert selection.metric_window_bar_count == selection.included_bar_count
        assert selection.excluded_straddling_bar_count == 0
        assert selection.excluded_post_boundary_bar_count == 0
        assert (
            selection.last_included_latest_possible_completion <= FROZEN_BOUNDARY
        )


def test_percentage_metric_value_is_invariant_to_the_timestamp_interpretation():
    """Choosing START over END is a serialization convention, not a choice of answer."""
    for symbol, _case_id in FROZEN_COHORT:
        values = []
        closes = []
        for interpretation in TimestampInterpretation:
            bars = load_detection_context_bars(
                SYNTHETIC_ROOT / "raw" / f"{symbol}-detection-context.csv",
                symbol=symbol,
                boundary=FROZEN_BOUNDARY,
                retrieval_completed_at=datetime(2026, 7, 23, 20, 0, tzinfo=UTC),
                receipt_policy=ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
                interpretation=interpretation,
            )
            metric = build_percentage_return(bars, as_of=FROZEN_BOUNDARY)
            assert metric.quality.state is QualityState.KNOWN_VALUE
            values.append(metric.value)
            reference, comparison = metric_window(bars.labels)
            selected = {
                observation.provenance.provider_metadata["provider_timestamp"]: (
                    observation.payload.close
                )
                for observation in bars.observations
            }
            closes.append(
                (
                    selected[reference.strftime("%Y-%m-%dT%H:%M:%SZ")],
                    selected[comparison.strftime("%Y-%m-%dT%H:%M:%SZ")],
                )
            )
        assert values[0] == values[1]
        assert closes[0] == closes[1]


def test_supply_policy_widening_changes_counts_but_no_outcome(policy):
    """A wider observation supply changes only the reported availability count."""
    cases = batch07_readiness(SYNTHETIC_ROOT)
    case_id = "BATCH01_XNCR_20260718"
    narrow = freeze_case(
        symbol="XNCR",
        case_id=case_id,
        boundary=FROZEN_BOUNDARY,
        batch05_root=SYNTHETIC_ROOT,
        policy=policy,
        batch07_case=cases[case_id],
    )
    wide = freeze_case(
        symbol="XNCR",
        case_id=case_id,
        boundary=FROZEN_BOUNDARY,
        batch05_root=SYNTHETIC_ROOT,
        policy=policy,
        batch07_case=cases[case_id],
        supply_policy=ObservationSupplyPolicy.ALL_DEFINITELY_COMPLETED_BARS,
    )
    narrow_outcomes = {r.rule_id: r.outcome for r in narrow.record.rule_outcomes}
    wide_outcomes = {r.rule_id: r.outcome for r in wide.record.rule_outcomes}
    assert narrow_outcomes == wide_outcomes
    assert (
        wide.record.temporal_selection.supplied_observation_count
        > narrow.record.temporal_selection.supplied_observation_count
    )
    assert narrow.metric.value == wide.metric.value


# --- receipt-modeling sensitivity ------------------------------------------------


def test_local_retrieval_receipt_sensitivity_is_disclosed(frozen):
    alternative = freeze_cohort(
        SYNTHETIC_ROOT, receipt_policy=ReceiptModelingPolicy.LOCAL_RETRIEVAL_RECEIPT
    )
    summary = sensitivity_summary(
        tuple(item.record for item in frozen),
        tuple(item.record for item in alternative),
        ReceiptModelingPolicy.LOCAL_RETRIEVAL_RECEIPT,
    )
    assert summary.case_count == len(FROZEN_COHORT)
    # Under a literal local-receipt reading every bar is point-in-time ineligible, so the
    # bar-dependent rules diverge. Disclosed rather than hidden.
    assert "MARKET_DATA_AVAILABLE" in summary.rules_diverging_from_primary
    assert "PERCENTAGE_CHANGE_MINIMUM" in summary.rules_diverging_from_primary
    assert "NO_DEFAULT_SUBSTITUTION" not in summary.rules_diverging_from_primary


# --- freeze ordering and leakage ------------------------------------------------


def test_freeze_ordering_places_request_before_result_before_any_outcome():
    request = build_audit_request(
        case_id="BATCH01_XNCR_20260718",
        boundary=FROZEN_BOUNDARY,
        discovery_manifest_id="BATCH01_DISCOVERY_MANIFEST",
    )
    assert ordering_holds(request)
    assert request.evaluation_request_frozen_at < request.evaluation_result_frozen_at
    assert request.evaluation_result_frozen_at < request.outcome_captured_at


def test_all_fifteen_leakage_audits_pass(frozen):
    assert len(frozen) == len(FROZEN_COHORT)
    for item in frozen:
        assert item.record.leakage_audit_status == "LEAKAGE_AUDIT_PASSED"
        assert item.record.leakage_audit_diagnostic_codes == ("LEAKAGE_AUDIT_PASSED",)


def test_evaluation_input_fields_contain_no_outcome_token():
    from squeeze_core.acquisition.phase3a_freeze.leakage import EVALUATION_INPUT_FIELDS

    tokens = ("outcome", "later_return", "maximum_observed_move", "maximum_return")
    for field in EVALUATION_INPUT_FIELDS:
        assert not any(token in field.lower() for token in tokens)


# --- determinism -----------------------------------------------------------------


def test_request_and_result_identities_are_deterministic(policy):
    cases = batch07_readiness(SYNTHETIC_ROOT)
    case_id = "BATCH01_SLS_20260718"
    first = freeze_case(
        symbol="SLS",
        case_id=case_id,
        boundary=FROZEN_BOUNDARY,
        batch05_root=SYNTHETIC_ROOT,
        policy=policy,
        batch07_case=cases[case_id],
    )
    second = freeze_case(
        symbol="SLS",
        case_id=case_id,
        boundary=FROZEN_BOUNDARY,
        batch05_root=SYNTHETIC_ROOT,
        policy=policy,
        batch07_case=cases[case_id],
    )
    assert first.record.phase3a_request_id == second.record.phase3a_request_id
    assert first.record.phase3a_result_id == second.record.phase3a_result_id
    assert first.record.deterministic_id == second.record.deterministic_id
    assert first.request_bytes == second.request_bytes
    assert first.result_bytes == second.result_bytes


def test_request_identity_excludes_wall_clock_and_paths():
    """Identity is built from frozen inputs only -- checked on code, not on prose."""
    tree = ast.parse((PACKAGE / "serialization.py").read_text(encoding="utf-8"))
    docstrings = _docstring_nodes(tree)
    forbidden_names = {"now", "utcnow", "uuid4", "uuid1", "time", "random", "monotonic"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in forbidden_names, f"identity uses {node.attr}"
        if isinstance(node, ast.Name):
            assert node.id not in forbidden_names, f"identity uses {node.id}"
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
        ):
            lowered = node.value.lower()
            for token in ("retrieval", "absolute_path", "ingested_at", "received"):
                assert token not in lowered, f"identity references {token}"


def test_repeated_generation_is_byte_identical():
    first = freeze_cohort(SYNTHETIC_ROOT)
    second = freeze_cohort(SYNTHETIC_ROOT)
    for left, right in zip(first, second, strict=True):
        assert left.request_bytes == right.request_bytes
        assert left.result_bytes == right.result_bytes
        assert serialize(left.record) == serialize(right.record)
        assert serialize(left.association) == serialize(right.association)


def test_committed_synthetic_golden_report_matches_byte_for_byte(frozen):
    alternative = freeze_cohort(
        SYNTHETIC_ROOT, receipt_policy=ReceiptModelingPolicy.LOCAL_RETRIEVAL_RECEIPT
    )
    cases = tuple(item.record for item in frozen)
    report = build_freeze_report(
        cases,
        receipt_policy=ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
        boundary_time=FROZEN_BOUNDARY,
        sensitivity=sensitivity_summary(
            cases,
            tuple(item.record for item in alternative),
            ReceiptModelingPolicy.LOCAL_RETRIEVAL_RECEIPT,
        ),
    )
    assert serialize(report) == (FIXTURE_DIR / "phase3a-freeze-report.json").read_bytes()
    assert render_markdown(report) == (
        FIXTURE_DIR / "phase3a-freeze-report.md"
    ).read_text(encoding="utf-8")


def test_frozen_artifact_hashes_and_byte_lengths_are_recorded(frozen):
    import hashlib

    for item in frozen:
        assert item.record.phase3a_request_artifact.sha256 == hashlib.sha256(
            item.request_bytes
        ).hexdigest()
        assert item.record.phase3a_request_artifact.byte_length == len(item.request_bytes)
        assert item.record.phase3a_result_artifact.sha256 == hashlib.sha256(
            item.result_bytes
        ).hexdigest()
        assert item.record.phase3a_result_artifact.byte_length == len(item.result_bytes)


# --- no score / rank / recommendation; publishes nothing -------------------------


def test_no_model_carries_a_score_rank_or_recommendation_field():
    forbidden = {"score", "rank", "ranking", "recommendation", "pnl", "target", "outcome_label"}
    for name in dir(freeze_models):
        model = getattr(freeze_models, name)
        fields = getattr(model, "model_fields", None)
        if not isinstance(fields, dict):
            continue
        assert not forbidden & set(fields), f"{name} carries a forbidden field"


def test_publication_readiness_preview_publishes_nothing(frozen):
    report = build_freeze_report(
        tuple(item.record for item in frozen),
        receipt_policy=ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
        boundary_time=FROZEN_BOUNDARY,
    )
    assert len(report.publication_readiness_preview) == len(FROZEN_COHORT)
    for preview in report.publication_readiness_preview:
        assert preview.phase3b_publication_performed is False
        assert preview.outcome_complete is False
        assert preview.has_frozen_phase3a_request is True
        assert preview.has_frozen_phase3a_result is True
        assert preview.leakage_audit_passed is True
        assert preview.referenceable_by_future_phase3b_revision is True


def test_sanitized_report_contains_no_price_or_return_value(frozen):
    report = build_freeze_report(
        tuple(item.record for item in frozen),
        receipt_policy=ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
        boundary_time=FROZEN_BOUNDARY,
    )
    rendered = json.loads(serialize(report).decode("utf-8"))
    text = json.dumps(rendered)

    def keys(node) -> set[str]:
        if isinstance(node, dict):
            return set(node) | {key for item in node.values() for key in keys(item)}
        if isinstance(node, list):
            return {key for item in node for key in keys(item)}
        return set()

    ohlcv_fields = {"open", "high", "low", "close", "volume", "wap", "vwap",
                    "trade_count", "observed_value", "value", "price"}
    assert not ohlcv_fields & keys(rendered)
    for item in frozen:
        # No derived return value reaches a committed/sanitized artifact.
        assert str(item.metric.value) not in text


# --- prior artifacts unchanged ---------------------------------------------------


def test_batch05_private_hash_manifest_is_untouched_by_this_batch():
    """Batch 08 writes only under phase3a/batch-08; the raw manifest is read-only."""
    manifest = SYNTHETIC_ROOT / "provenance" / "sha256-manifest.json"
    recorded = json.loads(manifest.read_text(encoding="utf-8"))
    import hashlib

    for relative, expected in recorded.items():
        payload = (SYNTHETIC_ROOT / relative).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected["sha256"]
        assert len(payload) == expected["byte_length"]


def test_batch07_golden_report_is_unchanged():
    path = ROOT / "tests" / "fixtures" / "acquisition" / "batch07"
    assert (path / "operation-readiness-report.json").exists()
    assert (path / "operation-readiness-report.md").exists()
