import pytest

from squeeze_core.analysis import AnalysisUnit, SampleSizeState
from squeeze_core.analysis.sample_size import assess_sample_size
from squeeze_core.analysis.policies import SAMPLE_SIZE_POLICY_VERSION


@pytest.mark.parametrize(
    ("sample_size", "expected"),
    (
        (0, SampleSizeState.NO_OBSERVATIONS),
        (1, SampleSizeState.ONE_OBSERVATION),
        (2, SampleSizeState.VERY_SMALL),
        (4, SampleSizeState.VERY_SMALL),
        (5, SampleSizeState.SMALL),
        (19, SampleSizeState.SMALL),
        (20, SampleSizeState.LIMITED),
        (49, SampleSizeState.LIMITED),
        (50, SampleSizeState.DESCRIPTIVE_ONLY),
        (500, SampleSizeState.DESCRIPTIVE_ONLY),
    ),
)
def test_fixed_sample_size_boundaries(sample_size, expected):
    result = assess_sample_size(
        sample_size,
        unique_symbol_count=min(sample_size, 3),
        analysis_unit=AnalysisUnit.CASE_BOUNDARY,
        policy_version=SAMPLE_SIZE_POLICY_VERSION,
    )
    assert result.state is expected
    assert result.sample_size == sample_size
    assert result.unique_symbol_count == min(sample_size, 3)
    assert result.analysis_unit is AnalysisUnit.CASE_BOUNDARY
    assert result.policy_version == SAMPLE_SIZE_POLICY_VERSION
    assert "PREDICTIVE_VALIDATION" in result.forbidden_interpretation
    assert "STATISTICAL_VALIDATION" in result.forbidden_interpretation


def test_historical_unique_symbol_sample_is_one_observation():
    result = assess_sample_size(
        1,
        unique_symbol_count=1,
        analysis_unit=AnalysisUnit.UNIQUE_SYMBOL_POLICY_SELECTED_BOUNDARY,
        policy_version=SAMPLE_SIZE_POLICY_VERSION,
    )
    assert result.state is SampleSizeState.ONE_OBSERVATION
    assert result.allowed_interpretation == ("DESCRIBE_OBSERVED_CASE",)
    assert "one observation" in result.limitations[0].lower()


def test_sample_size_identity_preserves_analysis_unit_and_unique_symbols():
    case_boundary = assess_sample_size(
        2, 1, AnalysisUnit.CASE_BOUNDARY, SAMPLE_SIZE_POLICY_VERSION
    )
    unique_symbol = assess_sample_size(
        2, 1, AnalysisUnit.UNIQUE_SYMBOL, SAMPLE_SIZE_POLICY_VERSION
    )
    two_symbols = assess_sample_size(
        2, 2, AnalysisUnit.CASE_BOUNDARY, SAMPLE_SIZE_POLICY_VERSION
    )
    assert case_boundary.deterministic_id != unique_symbol.deterministic_id
    assert case_boundary.deterministic_id != two_symbols.deterministic_id


def test_unique_symbol_count_cannot_exceed_sample_size():
    with pytest.raises(ValueError, match="ANALYSIS_SAMPLE_SIZE_INVALID"):
        assess_sample_size(1, 2, AnalysisUnit.CASE_BOUNDARY, SAMPLE_SIZE_POLICY_VERSION)

