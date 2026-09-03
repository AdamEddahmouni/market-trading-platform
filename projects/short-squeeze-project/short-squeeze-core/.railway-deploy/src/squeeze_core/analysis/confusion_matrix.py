from collections import Counter

from squeeze_core.research.models import (
    FixtureClassification,
    ResearchCaseClassification,
    ResearchDatasetRow,
)

from .models import ConfusionMatrixSummary
from .proportions import ProportionContext, build_binomial_proportion
from .sample_size import assess_sample_size


class AnalysisConfusionMatrixError(ValueError):
    pass


_CELL_BY_CLASSIFICATION = {
    ResearchCaseClassification.TRUE_POSITIVE: "tp",
    ResearchCaseClassification.FALSE_POSITIVE: "fp",
    ResearchCaseClassification.TRUE_NEGATIVE: "tn",
    ResearchCaseClassification.FALSE_NEGATIVE: "fn",
}


def build_confusion_matrix(
    rows: tuple[ResearchDatasetRow, ...],
    context: ProportionContext,
) -> ConfusionMatrixSummary:
    provenance = {row.fixture_classification for row in rows}
    if (
        FixtureClassification.SYNTHETIC_EDGE_CASE in provenance
        and len(provenance) > 1
    ):
        raise AnalysisConfusionMatrixError(
            "ANALYSIS_CONFUSION_MATRIX_MIXED_PROVENANCE"
        )
    counts = Counter(
        _CELL_BY_CLASSIFICATION.get(row.research_classification, "unevaluable")
        for row in rows
    )
    tp, fp, tn, fn = (counts[name] for name in ("tp", "fp", "tn", "fn"))
    definitions = (
        ("sensitivity_descriptive_research_classification_rate", tp, tp + fn),
        ("specificity_descriptive_research_classification_rate", tn, tn + fp),
        ("positive_predictive_value_descriptive_research_classification_rate", tp, tp + fp),
        ("negative_predictive_value_descriptive_research_classification_rate", tn, tn + fn),
        ("false_positive_descriptive_research_classification_rate", fp, fp + tn),
        ("false_negative_descriptive_research_classification_rate", fn, fn + tp),
    )
    rates = tuple(
        build_binomial_proportion(metric_name, numerator, denominator, context)
        for metric_name, numerator, denominator in definitions
    )
    evaluable_rows = tuple(
        row for row in rows if row.research_classification in _CELL_BY_CLASSIFICATION
    )
    sample_size = assess_sample_size(
        len(evaluable_rows),
        len({row.symbol for row in evaluable_rows}),
        context.analysis_unit,
        context.sample_size_policy_version,
    )
    return ConfusionMatrixSummary(
        true_positive_count=tp,
        false_positive_count=fp,
        true_negative_count=tn,
        false_negative_count=fn,
        unevaluable_count=counts["unevaluable"],
        descriptive_rates=rates,
        sample_size_assessment=sample_size,
        dependence_warning=(
            None
            if context.independence_assumption_satisfied
            else "Case-boundary descriptive rates contain dependent repeated-symbol observations."
        ),
    )


__all__ = ["AnalysisConfusionMatrixError", "build_confusion_matrix"]
