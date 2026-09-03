from collections import Counter
from decimal import Decimal

from squeeze_core.evaluation import RuleCategory, RuleOutcome

from .models import (
    BatchEvaluationResult,
    CategoryFrequency,
    CategoryFrequencySummary,
    MissingnessSummary,
    OutcomeConditionedRuleGroup,
    OutcomeConditionedRuleSummary,
    RuleFrequency,
    RuleFrequencySummary,
)


def _rate(numerator: int, denominator: int) -> Decimal | None:
    return None if denominator == 0 else Decimal(numerator) / Decimal(denominator)


def _rule_frequencies(cases) -> tuple[RuleFrequency, ...]:
    if not cases:
        return ()
    rule_ids = tuple(item.rule_id for item in cases[0].phase_3a_rule_results)
    results = []
    for rule_id in rule_ids:
        outcomes = [
            next(item.outcome for item in case.phase_3a_rule_results if item.rule_id == rule_id)
            for case in cases
        ]
        counts = Counter(outcomes)
        total = len(outcomes)
        evaluable = counts[RuleOutcome.PASS] + counts[RuleOutcome.FAIL]
        results.append(RuleFrequency(
            rule_id=rule_id,
            pass_count=counts[RuleOutcome.PASS],
            fail_count=counts[RuleOutcome.FAIL],
            unknown_count=counts[RuleOutcome.UNKNOWN],
            conflicted_count=counts[RuleOutcome.CONFLICTED],
            insufficient_data_count=counts[RuleOutcome.INSUFFICIENT_DATA],
            not_applicable_count=counts[RuleOutcome.NOT_APPLICABLE],
            total_case_count=total,
            evaluable_case_count=evaluable,
            pass_rate_among_evaluable=_rate(counts[RuleOutcome.PASS], evaluable),
            fail_rate_among_evaluable=_rate(counts[RuleOutcome.FAIL], evaluable),
            unknown_rate=_rate(counts[RuleOutcome.UNKNOWN], total),
            conflict_rate=_rate(counts[RuleOutcome.CONFLICTED], total),
            insufficient_data_rate=_rate(counts[RuleOutcome.INSUFFICIENT_DATA], total),
        ))
    return tuple(results)


def build_rule_frequency_summary(batch: BatchEvaluationResult) -> RuleFrequencySummary:
    return RuleFrequencySummary(rules=_rule_frequencies(batch.case_results))


def build_outcome_conditioned_rule_summary(
    batch: BatchEvaluationResult,
) -> OutcomeConditionedRuleSummary:
    labels = tuple(sorted({case.outcome_label for case in batch.case_results}, key=lambda item: item.value))
    return OutcomeConditionedRuleSummary(groups=tuple(
        OutcomeConditionedRuleGroup(
            outcome_label=label,
            rules=_rule_frequencies(tuple(case for case in batch.case_results if case.outcome_label is label)),
        ) for label in labels
    ))


def build_category_frequency_summary(batch: BatchEvaluationResult) -> CategoryFrequencySummary:
    categories = []
    for category in RuleCategory:
        per_case = [
            tuple(item for item in case.phase_3a_rule_results if item.category is category)
            for case in batch.case_results
        ]
        all_results = tuple(item for results in per_case for item in results)
        counts = Counter(item.outcome for item in all_results)
        categories.append(CategoryFrequency(
            category=category,
            rule_count=0 if not per_case else len(per_case[0]),
            pass_count=counts[RuleOutcome.PASS],
            fail_count=counts[RuleOutcome.FAIL],
            unknown_count=counts[RuleOutcome.UNKNOWN],
            conflicted_count=counts[RuleOutcome.CONFLICTED],
            insufficient_data_count=counts[RuleOutcome.INSUFFICIENT_DATA],
            not_applicable_count=counts[RuleOutcome.NOT_APPLICABLE],
            cases_with_any_pass=sum(any(item.outcome is RuleOutcome.PASS for item in results) for results in per_case),
            cases_with_all_required_rules_pass=sum(bool(results) and all(item.outcome is RuleOutcome.PASS for item in results) for results in per_case),
            cases_with_any_unknown=sum(any(item.outcome is RuleOutcome.UNKNOWN for item in results) for results in per_case),
            cases_with_any_conflict=sum(any(item.outcome is RuleOutcome.CONFLICTED for item in results) for results in per_case),
        ))
    return CategoryFrequencySummary(categories=tuple(categories))


_MISSING_DOMAINS = {
    "PUBLISHED_SHORT_INTEREST_AVAILABLE": "PUBLISHED_SHORT_INTEREST",
    "DAYS_TO_COVER_MINIMUM": "DAYS_TO_COVER",
    "BORROW_FEE_MINIMUM": "BORROW_FEE",
    "BORROW_FEE_CHANGE_MINIMUM": "BORROW_FEE",
    "BORROW_AVAILABILITY_MAXIMUM": "BORROW_AVAILABILITY",
    "BORROW_AVAILABILITY_CHANGE_MAXIMUM": "BORROW_AVAILABILITY",
    "FLOAT_MAXIMUM": "FLOAT",
    "RELATIVE_VOLUME_MINIMUM": "RELATIVE_VOLUME_HISTORY",
    "NEWS_TIMESTAMP_KNOWN": "NEWS_TIMESTAMPS",
    "SEC_FILING_AVAILABLE": "SEC_FILINGS",
    "PROVIDER_SCOPE_EXPLICIT": "PROVIDER_SCOPE",
    "REQUIRED_HISTORY_SUFFICIENT": "HISTORY",
}


def build_missingness_summary(batch: BatchEvaluationResult) -> MissingnessSummary:
    counts: Counter[str] = Counter()
    conflicted = 0
    insufficient = 0
    for case in batch.case_results:
        for result in case.phase_3a_rule_results:
            if result.outcome is RuleOutcome.UNKNOWN and result.rule_id in _MISSING_DOMAINS:
                counts[_MISSING_DOMAINS[result.rule_id]] += 1
            if result.outcome is RuleOutcome.CONFLICTED:
                conflicted += 1
            if result.outcome is RuleOutcome.INSUFFICIENT_DATA:
                insufficient += 1
    for domain in set(_MISSING_DOMAINS.values()):
        counts[domain] += 0
    return MissingnessSummary(
        missing_domain_counts=tuple(counts.items()),
        conflicted_rule_count=conflicted,
        insufficient_rule_count=insufficient,
    )


__all__ = [
    "build_category_frequency_summary", "build_missingness_summary",
    "build_outcome_conditioned_rule_summary", "build_rule_frequency_summary",
]
