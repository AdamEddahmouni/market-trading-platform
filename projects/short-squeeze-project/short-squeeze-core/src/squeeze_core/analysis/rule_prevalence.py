from collections import Counter

from squeeze_core.evaluation import RuleOutcome
from squeeze_core.research.models import OutcomeLabel, ResearchDatasetRow

from .models import OutcomeConditionedRulePrevalence, RuleOutcomePrevalence
from .proportions import (
    ProportionContext,
    build_binomial_proportion,
)
from .sample_size import assess_sample_size


def build_rule_outcome_prevalence(
    rows: tuple[ResearchDatasetRow, ...],
    rule_order: tuple[str, ...],
    context: ProportionContext,
) -> tuple[RuleOutcomePrevalence, ...]:
    results = []
    total = len(rows)
    for rule_id in rule_order:
        outcomes = Counter(row.rule_outcomes.get(rule_id) for row in rows)
        passed = outcomes[RuleOutcome.PASS.value]
        failed = outcomes[RuleOutcome.FAIL.value]
        unknown = outcomes[RuleOutcome.UNKNOWN.value]
        conflicted = outcomes[RuleOutcome.CONFLICTED.value]
        insufficient = outcomes[RuleOutcome.INSUFFICIENT_DATA.value]
        not_applicable = outcomes[RuleOutcome.NOT_APPLICABLE.value]
        evaluable = passed + failed
        rate_definitions = (
            ("pass_rate_among_all_cases", passed, total),
            ("pass_rate_among_evaluable_cases", passed, evaluable),
            ("fail_rate_among_evaluable_cases", failed, evaluable),
            ("unknown_rate_among_all_cases", unknown, total),
            ("conflicted_rate_among_all_cases", conflicted, total),
            ("insufficient_data_rate_among_all_cases", insufficient, total),
            ("not_applicable_rate_among_all_cases", not_applicable, total),
        )
        results.append(RuleOutcomePrevalence(
            rule_id=rule_id,
            pass_count=passed,
            fail_count=failed,
            unknown_count=unknown,
            conflicted_count=conflicted,
            insufficient_data_count=insufficient,
            not_applicable_count=not_applicable,
            total_case_count=total,
            evaluable_count=evaluable,
            proportions=tuple(
                build_binomial_proportion(name, numerator, denominator, context)
                for name, numerator, denominator in rate_definitions
            ),
        ))
    return tuple(results)


def build_outcome_conditioned_rule_prevalence(
    rows: tuple[ResearchDatasetRow, ...],
    rule_order: tuple[str, ...],
    context: ProportionContext,
) -> tuple[OutcomeConditionedRulePrevalence, ...]:
    groups = []
    for label in OutcomeLabel:
        group_rows = tuple(row for row in rows if row.outcome_label is label)
        if not group_rows:
            continue
        group_context = context.model_copy(
            update={"cohort_id": f"{context.cohort_id}:{label.value}"}
        )
        groups.append(OutcomeConditionedRulePrevalence(
            outcome_label=label.value,
            group_case_count=len(group_rows),
            rule_prevalence=build_rule_outcome_prevalence(
                group_rows, rule_order, group_context
            ),
            sample_size_assessment=assess_sample_size(
                len(group_rows),
                len({row.symbol for row in group_rows}),
                context.analysis_unit,
                context.sample_size_policy_version,
            ),
            dependence_warning=(
                None
                if context.independence_assumption_satisfied
                else "Outcome-conditioned case-boundary counts contain dependent observations."
            ),
            provenance_classifications=tuple(sorted({
                row.fixture_classification.value for row in group_rows
            })),
        ))
    return tuple(groups)


__all__ = [
    "build_outcome_conditioned_rule_prevalence",
    "build_rule_outcome_prevalence",
]
