from collections.abc import Iterable

from .models import ProportionEstimate, ResearchAnalysisResult


REPORT_SECTION_ORDER = (
    "Scope",
    "Cohort Definition",
    "Analysis Unit",
    "Included Cases",
    "Excluded Cases",
    "Boundary Selection",
    "Sample Size",
    "Dependence",
    "Counts",
    "Defined Rates",
    "Undefined Rates",
    "Confidence Intervals",
    "Missingness Findings",
    "Limitations",
    "Forbidden Interpretations",
    "No Recommendation",
)


def _line_items(values: Iterable[str]) -> list[str]:
    items = list(values)
    return [f"- {item}" for item in items] if items else ["- None."]


def _proportions(result: ResearchAnalysisResult):
    if result.confusion_matrix is not None:
        for value in result.confusion_matrix.descriptive_rates:
            yield "confusion_matrix", value
    for summary_name, summary in (
        ("detection_prevalence", result.detection_prevalence),
        ("outcome_prevalence", result.outcome_prevalence),
        ("classification_prevalence", result.classification_prevalence),
    ):
        if summary is not None:
            for value in summary.proportions:
                yield summary_name, value
    for rule in result.rule_outcome_prevalence:
        for value in rule.proportions:
            yield f"rule:{rule.rule_id}", value


def _rate_label(scope: str, value: ProportionEstimate) -> str:
    return f"{scope}/{value.metric_name}"


def render_markdown_report(result: ResearchAnalysisResult) -> bytes:
    lines = ["# Phase 3C Descriptive Research Analysis", ""]

    lines.extend(("## Scope", ""))
    lines.extend(_line_items((
        f"Analysis result ID: `{result.deterministic_id}`.",
        f"Source dataset ID: `{result.source_dataset_id}`.",
        f"Source registry ID: `{result.source_registry_id}`.",
        "This analysis is deterministic and descriptive only.",
    )))
    lines.append("")

    lines.extend(("## Cohort Definition", ""))
    lines.extend(_line_items((
        f"Cohort type: `{result.cohort_membership.cohort_definition.cohort_type.value}`.",
        "Provenance classifications: " + ", ".join(
            f"`{item.value}`" for item in result.provenance_classifications
        ) + ".",
    )))
    lines.append("")

    lines.extend(("## Analysis Unit", ""))
    lines.extend(_line_items((
        f"Analysis unit: `{result.analysis_unit.value}`.",
        f"Statistics policy: `{result.statistics_policy_version}`.",
        f"Interval policy: `{result.interval_policy_version}` at confidence `{result.confidence_level}`.",
        f"Sample-size policy: `{result.sample_size_policy_version}`.",
    )))
    lines.append("")

    lines.extend(("## Included Cases", ""))
    lines.extend(_line_items(
        f"`{case_id}`" for case_id in result.cohort_membership.included_case_ids
    ))
    lines.append("")

    lines.extend(("## Excluded Cases", ""))
    lines.extend(_line_items(
        f"`{item.case_id}` — `{item.reason_code}`"
        for item in result.cohort_membership.exclusions
    ))
    lines.append("")

    lines.extend(("## Boundary Selection", ""))
    lines.extend(_line_items((
        f"Policy: `{result.boundary_selection_policy_version.value}`.",
        "Selection is outcome-blind.",
        f"Boundary count before policy selection: {result.boundary_count}.",
    )))
    lines.append("")

    lines.extend(("## Sample Size", ""))
    lines.extend(_line_items(
        f"`{item.state.value}`: n={item.sample_size}, unique symbols={item.unique_symbol_count}, unit=`{item.analysis_unit.value}`."
        for item in result.sample_size_assessments
    ))
    lines.append("")

    lines.extend(("## Dependence", ""))
    dependence = result.symbol_dependence_summary
    if dependence is None:
        lines.append("- No dependence summary is available.")
    else:
        lines.extend(_line_items((
            f"Dependence detected: `{str(dependence.dependence_detected).lower()}`.",
            f"Independence assumption satisfied: `{str(dependence.independence_assumption_satisfied).lower()}`.",
            f"Repeated-boundary count: {dependence.repeated_boundary_count}.",
            f"Recommended analysis unit: `{dependence.recommended_analysis_unit.value}`.",
        )))
    lines.append("")

    lines.extend(("## Counts", ""))
    count_lines = [
        f"Cases: {result.case_count}.",
        f"Unique symbols: {result.unique_symbol_count}.",
        f"Boundaries: {result.boundary_count}.",
    ]
    if result.confusion_matrix is not None:
        matrix = result.confusion_matrix
        count_lines.append(
            "Confusion matrix: "
            f"TP={matrix.true_positive_count}, FP={matrix.false_positive_count}, "
            f"TN={matrix.true_negative_count}, FN={matrix.false_negative_count}, "
            f"unevaluable={matrix.unevaluable_count}."
        )
    if result.data_quality_summary is not None:
        quality = result.data_quality_summary
        count_lines.append(
            f"Registry: registered={quality.registered_case_count}, complete={quality.complete_case_count}, "
            f"synthetic={quality.synthetic_case_count}, partial={quality.partial_case_count}, "
            f"blocked={quality.blocked_case_count}."
        )
    lines.extend(_line_items(count_lines))
    lines.append("")

    proportions = tuple(_proportions(result))
    lines.extend(("## Defined Rates", ""))
    lines.extend(_line_items(
        f"{_rate_label(scope, value)}: {value.exact_fraction} ({value.percentage_value}%)."
        for scope, value in proportions if value.defined
    ))
    lines.append("")

    lines.extend(("## Undefined Rates", ""))
    lines.extend(_line_items(
        f"{_rate_label(scope, value)}: Undefined ({value.exact_fraction}; {value.undefined_reason.value})."
        for scope, value in proportions if not value.defined
    ))
    lines.append("")

    lines.extend(("## Confidence Intervals", ""))
    lines.extend(_line_items(
        f"{_rate_label(scope, value)}: [{value.interval.lower_bound}, {value.interval.upper_bound}] "
        f"using `{value.interval.method.value}` at {value.interval.confidence_level}; "
        f"independence satisfied=`{str(value.interval.independence_assumption_satisfied).lower()}`."
        for scope, value in proportions if value.interval is not None
    ))
    lines.append("")

    lines.extend(("## Missingness Findings", ""))
    lines.extend(_line_items(
        f"`{item.domain_id}`: {item.missing_count}/{item.denominator}; cases="
        + (", ".join(f"`{case_id}`" for case_id in item.affected_case_ids) or "none")
        + "."
        for item in result.domain_missingness_summary
    ))
    lines.append("")

    lines.extend(("## Limitations", ""))
    lines.extend(_line_items(item.statement for item in result.limitations))
    lines.append("")

    lines.extend(("## Forbidden Interpretations", ""))
    lines.extend(_line_items((
        "Do not interpret these counts as predictive validation.",
        "Do not infer short-squeeze causation.",
        "Do not infer rule importance from prevalence.",
        "Do not combine synthetic cases with historical empirical estimates.",
        "Do not use these results for threshold selection or trading decisions.",
    )))
    lines.append("")

    lines.extend(("## No Recommendation", ""))
    lines.append("No candidate score, rank, alert, or trading recommendation is produced.")
    lines.append("")
    return "\n".join(lines).encode("utf-8")


__all__ = ["REPORT_SECTION_ORDER", "render_markdown_report"]
