from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext

from .models import IntervalEstimate
from .policies import load_interval_policy
from .proportions import ProportionContext


class AnalysisIntervalError(ValueError):
    def __init__(self, code: str, value: str | None = None):
        suffix = f":{value}" if value is not None else ""
        super().__init__(f"{code}{suffix}")
        self.code = code


def wilson_score_interval(
    numerator: int,
    denominator: int,
    context: ProportionContext,
) -> IntervalEstimate | None:
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise AnalysisIntervalError(
            "ANALYSIS_INTERVAL_COUNTS_INVALID", f"{numerator}/{denominator}"
        )
    if denominator == 0 or not context.intervals_requested:
        return None
    policy = load_interval_policy(context.interval_policy_version)
    if context.confidence_level != policy.confidence_level:
        raise AnalysisIntervalError(
            "ANALYSIS_INTERVAL_CONFIDENCE_UNSUPPORTED",
            str(context.confidence_level),
        )

    decimal_context = Context(
        prec=policy.decimal_precision,
        rounding=ROUND_HALF_EVEN,
    )
    with localcontext(decimal_context):
        successes = Decimal(numerator)
        observations = Decimal(denominator)
        probability = successes / observations
        z_squared = policy.z_value * policy.z_value
        denominator_term = Decimal("1") + z_squared / observations
        center = (
            probability + z_squared / (Decimal("2") * observations)
        ) / denominator_term
        radicand = (
            probability * (Decimal("1") - probability) / observations
            + z_squared / (Decimal("4") * observations * observations)
        )
        margin = policy.z_value * radicand.sqrt() / denominator_term
        lower = max(Decimal("0"), center - margin).quantize(
            policy.serialization_quantum,
            rounding=ROUND_HALF_EVEN,
        )
        upper = min(Decimal("1"), center + margin).quantize(
            policy.serialization_quantum,
            rounding=ROUND_HALF_EVEN,
        )
    return IntervalEstimate(
        method=policy.method,
        numerator=numerator,
        denominator=denominator,
        confidence_level=policy.confidence_level,
        lower_bound=lower,
        upper_bound=upper,
        independence_assumption_satisfied=context.independence_assumption_satisfied,
        policy_version=policy.policy_version,
    )


__all__ = ["AnalysisIntervalError", "wilson_score_interval"]
