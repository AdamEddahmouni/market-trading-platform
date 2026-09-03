from .models import AnalysisUnit, SampleSizeAssessment, SampleSizeState
from .policies import load_sample_size_policy


def _state(sample_size: int) -> SampleSizeState:
    if sample_size == 0:
        return SampleSizeState.NO_OBSERVATIONS
    if sample_size == 1:
        return SampleSizeState.ONE_OBSERVATION
    if sample_size <= 4:
        return SampleSizeState.VERY_SMALL
    if sample_size <= 19:
        return SampleSizeState.SMALL
    if sample_size <= 49:
        return SampleSizeState.LIMITED
    return SampleSizeState.DESCRIPTIVE_ONLY


def assess_sample_size(
    sample_size: int,
    unique_symbol_count: int,
    analysis_unit: AnalysisUnit,
    policy_version: str,
) -> SampleSizeAssessment:
    policy = load_sample_size_policy(policy_version)
    if (
        sample_size < 0
        or unique_symbol_count < 0
        or unique_symbol_count > sample_size
    ):
        raise ValueError(
            f"ANALYSIS_SAMPLE_SIZE_INVALID:{sample_size}/{unique_symbol_count}"
        )
    state = _state(sample_size)
    if state is SampleSizeState.NO_OBSERVATIONS:
        limitations = ("No observations are available for this analysis unit.",)
        allowed = ("DESCRIBE_ABSENCE",)
    elif state is SampleSizeState.ONE_OBSERVATION:
        limitations = (
            "One observation permits case description only and cannot support generalization.",
        )
        allowed = ("DESCRIBE_OBSERVED_CASE",)
    else:
        limitations = (
            "The cohort remains descriptive only and is not a predictive-validation sample.",
        )
        allowed = ("DESCRIBE_COHORT_COUNTS", "DESCRIBE_UNCERTAINTY")
    return SampleSizeAssessment(
        sample_size=sample_size,
        unique_symbol_count=unique_symbol_count,
        analysis_unit=analysis_unit,
        state=state,
        limitations=limitations,
        allowed_interpretation=allowed,
        forbidden_interpretation=(
            "CAUSAL_INFERENCE",
            "PREDICTIVE_VALIDATION",
            "STATISTICAL_VALIDATION",
        ),
        policy_version=policy.policy_version,
    )


__all__ = ["assess_sample_size"]
