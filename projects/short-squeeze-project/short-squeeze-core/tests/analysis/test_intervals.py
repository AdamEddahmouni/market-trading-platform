import ast
from decimal import Decimal
from pathlib import Path

import pytest

from squeeze_core.analysis import IntervalMethod
from squeeze_core.analysis.intervals import AnalysisIntervalError, wilson_score_interval
from tests.analysis.test_proportions import CONTEXT


@pytest.mark.parametrize(
    ("numerator", "denominator", "lower", "upper"),
    (
        (0, 1, Decimal("0E-12"), Decimal("0.793450685623")),
        (1, 1, Decimal("0.206549314377"), Decimal("1.000000000000")),
        (1, 2, Decimal("0.094531205734"), Decimal("0.905468794266")),
        (2, 5, Decimal("0.117620774233"), Decimal("0.769275718724")),
        (50, 100, Decimal("0.403831530366"), Decimal("0.596168469634")),
    ),
)
def test_wilson_bounds_use_fixed_policy_arithmetic(
    numerator, denominator, lower, upper
):
    interval = wilson_score_interval(numerator, denominator, CONTEXT)
    assert interval is not None
    assert interval.method is IntervalMethod.WILSON_SCORE
    assert interval.numerator == numerator
    assert interval.denominator == denominator
    assert interval.confidence_level == Decimal("0.95")
    assert interval.lower_bound == lower
    assert interval.upper_bound == upper
    assert Decimal("0") <= interval.lower_bound <= interval.upper_bound <= Decimal("1")


def test_zero_denominator_has_no_interval():
    assert wilson_score_interval(0, 0, CONTEXT) is None


def test_unsupported_confidence_level_is_rejected():
    context = CONTEXT.model_copy(update={"confidence_level": Decimal("0.90")})
    with pytest.raises(AnalysisIntervalError, match="ANALYSIS_INTERVAL_CONFIDENCE_UNSUPPORTED"):
        wilson_score_interval(1, 2, context)


def test_invalid_counts_are_rejected():
    with pytest.raises(AnalysisIntervalError, match="ANALYSIS_INTERVAL_COUNTS_INVALID"):
        wilson_score_interval(3, 2, CONTEXT)


def test_dependence_marker_is_preserved_and_changes_identity():
    independent = wilson_score_interval(1, 2, CONTEXT)
    dependent_context = CONTEXT.model_copy(
        update={"independence_assumption_satisfied": False}
    )
    dependent = wilson_score_interval(1, 2, dependent_context)
    assert independent is not None and dependent is not None
    assert independent.independence_assumption_satisfied
    assert not dependent.independence_assumption_satisfied
    assert independent.deterministic_id != dependent.deterministic_id


def test_interval_runtime_contains_no_random_or_inverse_normal_calculation():
    source_path = Path(__file__).resolve().parents[2] / "src" / "squeeze_core" / "analysis" / "intervals.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not imported.intersection({"random", "statistics.NormalDist", "scipy", "numpy"})
    assert "inv_cdf" not in source_path.read_text(encoding="utf-8")
