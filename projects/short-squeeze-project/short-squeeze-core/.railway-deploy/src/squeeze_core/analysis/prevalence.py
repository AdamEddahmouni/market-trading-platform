from collections import Counter
from enum import StrEnum

from squeeze_core.research.models import (
    DetectionStatus,
    OutcomeLabel,
    ResearchCaseClassification,
    ResearchDatasetRow,
)

from .models import (
    ClassificationPrevalenceSummary,
    DetectionPrevalenceSummary,
    OutcomePrevalenceSummary,
    PrevalenceSummary,
)
from .proportions import ProportionContext, build_binomial_proportion


def _summary(
    rows: tuple[ResearchDatasetRow, ...],
    attribute: str,
    enum_type: type[StrEnum],
    model_type: type[PrevalenceSummary],
    context: ProportionContext,
) -> PrevalenceSummary:
    values = tuple(getattr(row, attribute) for row in rows)
    counts = Counter(values)
    total = len(rows)
    count_rows = tuple((item.value, counts[item]) for item in enum_type)
    proportions = tuple(
        build_binomial_proportion(
            f"{item.value.lower()}_prevalence_among_all_cases",
            counts[item],
            total,
            context,
        )
        for item in enum_type
    )
    return model_type(counts=count_rows, proportions=proportions)


def build_detection_prevalence(
    rows: tuple[ResearchDatasetRow, ...], context: ProportionContext
) -> DetectionPrevalenceSummary:
    base = _summary(
        rows, "research_detection_status", DetectionStatus,
        DetectionPrevalenceSummary, context,
    )
    counts = dict(base.counts)
    evaluable = counts[DetectionStatus.DETECTED.value] + counts[DetectionStatus.NOT_DETECTED.value]
    additional = build_binomial_proportion(
        "detection_rate_among_evaluable_cases",
        counts[DetectionStatus.DETECTED.value],
        evaluable,
        context,
    )
    return DetectionPrevalenceSummary(
        counts=base.counts,
        proportions=base.proportions + (additional,),
    )


def build_outcome_prevalence(
    rows: tuple[ResearchDatasetRow, ...], context: ProportionContext
) -> OutcomePrevalenceSummary:
    base = _summary(rows, "outcome_label", OutcomeLabel, OutcomePrevalenceSummary, context)
    counts = dict(base.counts)
    incomplete = {
        OutcomeLabel.OUTCOME_UNKNOWN.value,
        OutcomeLabel.OUTCOME_INSUFFICIENT_DATA.value,
    }
    complete_denominator = sum(count for name, count in base.counts if name not in incomplete)
    upward = build_binomial_proportion(
        "substantial_upward_move_prevalence_among_complete_outcomes",
        counts[OutcomeLabel.SUBSTANTIAL_UPWARD_MOVE.value],
        complete_denominator,
        context,
    )
    return OutcomePrevalenceSummary(
        counts=base.counts,
        proportions=base.proportions + (upward,),
    )


def build_classification_prevalence(
    rows: tuple[ResearchDatasetRow, ...], context: ProportionContext
) -> ClassificationPrevalenceSummary:
    base = _summary(
        rows, "research_classification", ResearchCaseClassification,
        ClassificationPrevalenceSummary, context,
    )
    counts = dict(base.counts)
    evaluable = sum(
        counts[item.value]
        for item in (
            ResearchCaseClassification.TRUE_POSITIVE,
            ResearchCaseClassification.FALSE_POSITIVE,
            ResearchCaseClassification.TRUE_NEGATIVE,
            ResearchCaseClassification.FALSE_NEGATIVE,
        )
    )
    evaluability = build_binomial_proportion(
        "research_classification_evaluability_rate_among_all_cases",
        evaluable,
        len(rows),
        context,
    )
    return ClassificationPrevalenceSummary(
        counts=base.counts,
        proportions=base.proportions + (evaluability,),
    )


__all__ = [
    "build_classification_prevalence", "build_detection_prevalence",
    "build_outcome_prevalence",
]
