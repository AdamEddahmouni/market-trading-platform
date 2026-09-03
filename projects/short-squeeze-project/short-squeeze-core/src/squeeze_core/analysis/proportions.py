from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from .models import AnalysisUnit, ProportionEstimate, UndefinedReason


class ProportionContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cohort_id: str
    analysis_unit: AnalysisUnit
    interval_policy_version: str
    confidence_level: Decimal
    sample_size_policy_version: str
    independence_assumption_satisfied: bool = True
    intervals_requested: bool = True


def build_proportion(
    metric_name: str,
    numerator: int,
    denominator: int,
    context: ProportionContext,
) -> ProportionEstimate:
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise ValueError(
            f"ANALYSIS_PROPORTION_COUNTS_INVALID:{numerator}/{denominator}"
        )
    exact_fraction = f"{numerator}/{denominator}"
    if denominator == 0:
        return ProportionEstimate(
            metric_name=metric_name,
            numerator=numerator,
            denominator=denominator,
            exact_fraction=exact_fraction,
            decimal_value=None,
            percentage_value=None,
            defined=False,
            undefined_reason=UndefinedReason.ZERO_DENOMINATOR,
            cohort_id=context.cohort_id,
            analysis_unit=context.analysis_unit,
            interval=None,
            interval_policy_version=context.interval_policy_version,
            confidence_level=context.confidence_level,
            sample_size_policy_version=context.sample_size_policy_version,
        )
    decimal_value = Decimal(numerator) / Decimal(denominator)
    return ProportionEstimate(
        metric_name=metric_name,
        numerator=numerator,
        denominator=denominator,
        exact_fraction=exact_fraction,
        decimal_value=decimal_value,
        percentage_value=decimal_value * Decimal("100"),
        defined=True,
        undefined_reason=None,
        cohort_id=context.cohort_id,
        analysis_unit=context.analysis_unit,
        interval=None,
        interval_policy_version=context.interval_policy_version,
        confidence_level=context.confidence_level,
        sample_size_policy_version=context.sample_size_policy_version,
    )


def build_binomial_proportion(
    metric_name: str,
    numerator: int,
    denominator: int,
    context: ProportionContext,
) -> ProportionEstimate:
    base = build_proportion(metric_name, numerator, denominator, context)
    if not base.defined:
        return base
    from .intervals import wilson_score_interval

    values = base.model_dump(exclude={"deterministic_id", "interval"})
    return ProportionEstimate(
        **values,
        interval=wilson_score_interval(numerator, denominator, context),
    )


__all__ = ["ProportionContext", "build_binomial_proportion", "build_proportion"]
