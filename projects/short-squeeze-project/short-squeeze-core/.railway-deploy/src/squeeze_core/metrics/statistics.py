from collections.abc import Sequence
from decimal import Decimal, localcontext

# Calculation-only guard precision for a local decimal.localcontext(); never mutates the ambient
# Decimal context. Higher than Phase 2A's prec=28 (used for single divisions) because variance
# squares each deviation before summing -- see docs/phase-2b-design.md Section 8 and
# docs/adr/0033-decimal-population-standard-deviation.md for the full rationale.
DECIMAL_STATISTICS_PRECISION = 50


def decimal_mean(values: Sequence[Decimal]) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = DECIMAL_STATISTICS_PRECISION
        return sum(values, Decimal(0)) / Decimal(len(values))


def decimal_population_variance(values: Sequence[Decimal], mean: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = DECIMAL_STATISTICS_PRECISION
        total = sum(((value - mean) ** 2 for value in values), Decimal(0))
        return total / Decimal(len(values))


def decimal_sqrt(value: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = DECIMAL_STATISTICS_PRECISION
        return value.sqrt()


def population_standard_deviation(values: Sequence[Decimal]) -> tuple[Decimal, Decimal, Decimal]:
    """Returns (mean, variance, standard_deviation) under `population_standard_deviation_decimal.v1`."""
    mean = decimal_mean(values)
    variance = decimal_population_variance(values, mean)
    return mean, variance, decimal_sqrt(variance)
