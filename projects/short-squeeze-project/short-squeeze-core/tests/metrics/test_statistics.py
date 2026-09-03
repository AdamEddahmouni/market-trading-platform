from decimal import Decimal, localcontext

from squeeze_core.metrics.statistics import (
    DECIMAL_STATISTICS_PRECISION,
    decimal_mean,
    decimal_population_variance,
    decimal_sqrt,
    population_standard_deviation,
)


def test_decimal_mean_exact():
    assert decimal_mean([Decimal(1), Decimal(2), Decimal(3)]) == Decimal(2)


def test_decimal_mean_nonterminating_stays_exact_decimal():
    value = decimal_mean([Decimal(1000), Decimal(1000), Decimal(1001)])
    with localcontext() as ctx:
        ctx.prec = DECIMAL_STATISTICS_PRECISION
        expected = Decimal(3001) / Decimal(3)
    assert value == expected
    assert isinstance(value, Decimal)


def test_decimal_population_variance_matches_known_value():
    # Population variance of [2, 4, 4, 4, 5, 5, 7, 9] is 4 (textbook example).
    values = [Decimal(v) for v in (2, 4, 4, 4, 5, 5, 7, 9)]
    mean = decimal_mean(values)
    assert mean == Decimal(5)
    variance = decimal_population_variance(values, mean)
    assert variance == Decimal(4)


def test_decimal_sqrt_exact_perfect_square():
    assert decimal_sqrt(Decimal(4)) == Decimal(2)
    assert decimal_sqrt(Decimal(0)) == Decimal(0)


def test_population_standard_deviation_matches_known_value():
    values = [Decimal(v) for v in (2, 4, 4, 4, 5, 5, 7, 9)]
    mean, variance, stddev = population_standard_deviation(values)
    assert mean == Decimal(5)
    assert variance == Decimal(4)
    assert stddev == Decimal(2)


def test_population_standard_deviation_two_identical_samples_is_zero():
    mean, variance, stddev = population_standard_deviation([Decimal(100), Decimal(100)])
    assert mean == Decimal(100)
    assert variance == Decimal(0)
    assert stddev == Decimal(0)


def test_no_float_conversion_anywhere():
    # Values that would lose precision under float64 must survive exactly.
    values = [Decimal("1.1"), Decimal("1.2"), Decimal("1.3")]
    mean = decimal_mean(values)
    assert mean == Decimal("1.2")


def test_input_order_does_not_affect_result():
    values = [Decimal(1000), Decimal(2000), Decimal(3000), Decimal(4000)]
    mean_a, var_a, std_a = population_standard_deviation(values)
    mean_b, var_b, std_b = population_standard_deviation(list(reversed(values)))
    assert (mean_a, var_a, std_a) == (mean_b, var_b, std_b)


def test_local_context_does_not_mutate_ambient_context():
    import decimal

    ambient_before = decimal.getcontext().prec
    population_standard_deviation([Decimal(1), Decimal(2), Decimal(3)])
    assert decimal.getcontext().prec == ambient_before
