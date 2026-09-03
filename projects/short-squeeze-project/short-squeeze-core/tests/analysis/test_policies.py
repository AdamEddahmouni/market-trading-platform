from decimal import Decimal

import pytest

from squeeze_core.analysis import BoundarySelectionPolicy, IntervalMethod
from squeeze_core.analysis.policies import (
    BOUNDARY_SELECTION_POLICY_VERSION,
    INTERVAL_POLICY_VERSION,
    SAMPLE_SIZE_POLICY_VERSION,
    STATISTICS_POLICY_VERSION,
    AnalysisPolicyError,
    load_boundary_selection_policy,
    load_interval_policy,
    load_sample_size_policy,
    load_statistics_policy,
)


def test_approved_phase_3c_policies_are_explicit_and_unoptimized():
    statistics = load_statistics_policy(STATISTICS_POLICY_VERSION)
    interval = load_interval_policy(INTERVAL_POLICY_VERSION)
    sample_size = load_sample_size_policy(SAMPLE_SIZE_POLICY_VERSION)
    boundary = load_boundary_selection_policy(BOUNDARY_SELECTION_POLICY_VERSION)

    assert statistics.provisional and not statistics.optimized
    assert "THRESHOLD_SEARCH" in statistics.forbidden_statistics
    assert interval.method is IntervalMethod.WILSON_SCORE
    assert interval.confidence_level == Decimal("0.95")
    assert interval.z_value == Decimal("1.95996398454005423552")
    assert interval.decimal_precision == 50
    assert interval.serialization_quantum == Decimal("0.000000000001")
    assert sample_size.thresholds == (
        (0, "NO_OBSERVATIONS"),
        (1, "ONE_OBSERVATION"),
        (4, "VERY_SMALL"),
        (19, "SMALL"),
        (49, "LIMITED"),
        (-1, "DESCRIPTIVE_ONLY"),
    )
    assert boundary.policy_version is BoundarySelectionPolicy.EARLIEST_DETECTION_BOUNDARY_PER_SYMBOL
    assert boundary.tie_break_fields == ("evaluation_as_of", "case_id")
    assert boundary.outcome_blind


@pytest.mark.parametrize(
    "loader,version",
    (
        (load_statistics_policy, "statistics.unknown"),
        (load_interval_policy, "interval.unknown"),
        (load_sample_size_policy, "sample.unknown"),
        (load_boundary_selection_policy, "boundary.unknown"),
    ),
)
def test_unknown_policy_versions_are_rejected(loader, version):
    with pytest.raises(AnalysisPolicyError, match="ANALYSIS_POLICY_UNSUPPORTED"):
        loader(version)

