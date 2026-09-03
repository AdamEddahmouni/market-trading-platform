from decimal import Decimal

from squeeze_core.research.batch import run_research_batch
from squeeze_core.research.summaries import (
    build_category_frequency_summary,
    build_missingness_summary,
    build_outcome_conditioned_rule_summary,
    build_rule_frequency_summary,
)

from .test_batch import complete_entry, request, write_registry


def test_rule_frequencies_preserve_counts_denominators_and_exact_rates(tmp_path):
    batch = run_research_batch(request(), write_registry(tmp_path, (complete_entry(),)))
    summary = build_rule_frequency_summary(batch)
    by_rule = {item.rule_id: item for item in summary.rules}
    price = by_rule["PRICE_RANGE"]
    assert price.pass_count == 1
    assert price.fail_count == 0
    assert price.evaluable_case_count == 1
    assert price.pass_rate_among_evaluable == Decimal("1")
    short_interest = by_rule["PUBLISHED_SHORT_INTEREST_AVAILABLE"]
    assert short_interest.pass_count == 1
    assert short_interest.unknown_count == 0
    assert short_interest.evaluable_case_count == 1
    assert short_interest.pass_rate_among_evaluable == Decimal("1")


def test_outcome_category_and_missingness_summaries_are_descriptive(tmp_path):
    batch = run_research_batch(request(), write_registry(tmp_path, (complete_entry(),)))
    conditioned = build_outcome_conditioned_rule_summary(batch)
    categories = build_category_frequency_summary(batch)
    missingness = build_missingness_summary(batch)
    assert conditioned.groups[0].outcome_label.value == "SUBSTANTIAL_UPWARD_MOVE"
    assert {item.category.value for item in categories.categories} == {
        "MOMENTUM_DISCOVERY", "SHORT_PRESSURE_CONFIRMATION",
        "CATALYST_EVIDENCE", "EVIDENCE_VALIDITY",
    }
    by_domain = dict(missingness.missing_domain_counts)
    assert by_domain.get("PUBLISHED_SHORT_INTEREST", 0) == 0
    assert by_domain["BORROW_FEE"] >= 1
    assert by_domain["BORROW_AVAILABILITY"] >= 1
    assert missingness.deterministic_id == build_missingness_summary(batch).deterministic_id
