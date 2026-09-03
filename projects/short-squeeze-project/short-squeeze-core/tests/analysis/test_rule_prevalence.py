from decimal import Decimal
from pathlib import Path

from squeeze_core.analysis import AnalysisUnit, UndefinedReason
from squeeze_core.analysis.proportions import ProportionContext
from squeeze_core.analysis.rule_prevalence import (
    build_outcome_conditioned_rule_prevalence,
    build_rule_outcome_prevalence,
)
from squeeze_core.evaluation.policies import load_policy
from tests.analysis.helpers import load_dataset


ROOT = Path(__file__).resolve().parents[2]
RULE_ORDER = load_policy(
    ROOT / "src" / "squeeze_core" / "evaluation" / "policies"
    / "phase_3a_transparent_candidate_policy_v1.json"
).enabled_rule_ids


def _context(*, independent=True):
    return ProportionContext(
        cohort_id="rule-prevalence-cohort",
        analysis_unit=AnalysisUnit.CASE_BOUNDARY,
        interval_policy_version="phase_3c_interval_policy.v1",
        confidence_level=Decimal("0.95"),
        sample_size_policy_version="phase_3c_sample_size_policy.v1",
        independence_assumption_satisfied=independent,
    )


def _by_rule(summary):
    return {item.rule_id: item for item in summary}


def _by_metric(item):
    return {rate.metric_name: rate for rate in item.proportions}


def test_rule_prevalence_preserves_all_outcome_counts_and_phase_3a_order():
    rows = tuple(row for row in load_dataset().rows if row.case_id.startswith("SYN_"))
    summary = build_rule_outcome_prevalence(rows, RULE_ORDER, _context())
    assert tuple(item.rule_id for item in summary) == RULE_ORDER
    assert len(summary) == 25
    for item in summary:
        assert (
            item.pass_count
            + item.fail_count
            + item.unknown_count
            + item.conflicted_count
            + item.insufficient_data_count
            + item.not_applicable_count
        ) == item.total_case_count == 11
        assert item.evaluable_count == item.pass_count + item.fail_count
        assert not hasattr(item, "rule_rank")
        assert not hasattr(item, "importance_score")


def test_zero_evaluable_rule_denominator_remains_undefined():
    rows = tuple(
        row for row in load_dataset().rows
        if row.case_id in {
            "SYN_UNEVALUABLE_UNKNOWN",
            "SYN_UNEVALUABLE_CONFLICTED",
            "SYN_UNEVALUABLE_INSUFFICIENT",
        }
    )
    price = _by_rule(
        build_rule_outcome_prevalence(rows, RULE_ORDER, _context())
    )["PRICE_RANGE"]
    assert (price.unknown_count, price.conflicted_count, price.insufficient_data_count) == (1, 1, 1)
    assert price.evaluable_count == 0
    rates = _by_metric(price)
    assert rates["pass_rate_among_evaluable_cases"].undefined_reason is UndefinedReason.ZERO_DENOMINATOR
    assert rates["fail_rate_among_evaluable_cases"].undefined_reason is UndefinedReason.ZERO_DENOMINATOR


def test_historical_and_synthetic_denominators_remain_separate():
    dataset = load_dataset()
    historical = tuple(row for row in dataset.rows if row.symbol == "BIYA")
    synthetic = tuple(row for row in dataset.rows if row.case_id.startswith("SYN_"))
    historical_price = _by_rule(
        build_rule_outcome_prevalence(historical, RULE_ORDER, _context(independent=False))
    )["PRICE_RANGE"]
    synthetic_price = _by_rule(
        build_rule_outcome_prevalence(synthetic, RULE_ORDER, _context())
    )["PRICE_RANGE"]
    assert historical_price.total_case_count == 2
    assert synthetic_price.total_case_count == 11
    assert historical_price.pass_count == 2
    assert not _by_metric(historical_price)["pass_rate_among_all_cases"].interval.independence_assumption_satisfied


def test_rule_prevalence_is_input_order_invariant():
    rows = tuple(row for row in load_dataset().rows if row.symbol == "BIYA")
    assert build_rule_outcome_prevalence(
        rows, RULE_ORDER, _context(independent=False)
    ) == build_rule_outcome_prevalence(
        tuple(reversed(rows)), RULE_ORDER, _context(independent=False)
    )


def test_outcome_conditioned_groups_skip_empty_labels_and_preserve_sample_size():
    rows = tuple(row for row in load_dataset().rows if row.symbol == "BIYA")
    groups = build_outcome_conditioned_rule_prevalence(
        rows, RULE_ORDER, _context(independent=False)
    )
    assert len(groups) == 1
    assert groups[0].outcome_label == "SUBSTANTIAL_UPWARD_MOVE"
    assert groups[0].group_case_count == 2
    assert groups[0].sample_size_assessment.sample_size == 2
    assert "dependent" in groups[0].dependence_warning.lower()

