import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .models import (
    BoundarySelectionPolicy,
    BoundarySelectionPolicyDefinition,
    ConfidenceIntervalPolicy,
    DescriptiveStatisticsPolicy,
    SampleSizePolicy,
)


STATISTICS_POLICY_VERSION = "phase_3c_descriptive_statistics_policy.v1"
INTERVAL_POLICY_VERSION = "phase_3c_interval_policy.v1"
SAMPLE_SIZE_POLICY_VERSION = "phase_3c_sample_size_policy.v1"
BOUNDARY_SELECTION_POLICY_VERSION = "earliest_detection_boundary_per_symbol.v1"
_POLICY_ROOT = Path(__file__).with_name("policies")
_Policy = TypeVar("_Policy", bound=BaseModel)


class AnalysisPolicyError(ValueError):
    def __init__(self, version: str):
        super().__init__(f"ANALYSIS_POLICY_UNSUPPORTED:{version}")


def _load(version: str, expected: str, filename: str, model: type[_Policy]) -> _Policy:
    if version != expected:
        raise AnalysisPolicyError(version)
    return model.model_validate(json.loads((_POLICY_ROOT / filename).read_text(encoding="utf-8")))


def load_statistics_policy(version: str) -> DescriptiveStatisticsPolicy:
    return _load(version, STATISTICS_POLICY_VERSION, "phase_3c_statistics_policy_v1.json", DescriptiveStatisticsPolicy)


def load_interval_policy(version: str) -> ConfidenceIntervalPolicy:
    return _load(version, INTERVAL_POLICY_VERSION, "phase_3c_interval_policy_v1.json", ConfidenceIntervalPolicy)


def load_sample_size_policy(version: str) -> SampleSizePolicy:
    return _load(version, SAMPLE_SIZE_POLICY_VERSION, "phase_3c_sample_size_policy_v1.json", SampleSizePolicy)


def load_boundary_selection_policy(version: str) -> BoundarySelectionPolicyDefinition:
    return _load(version, BOUNDARY_SELECTION_POLICY_VERSION, "phase_3c_boundary_selection_policy_v1.json", BoundarySelectionPolicyDefinition)


__all__ = [
    "AnalysisPolicyError", "BOUNDARY_SELECTION_POLICY_VERSION", "INTERVAL_POLICY_VERSION",
    "SAMPLE_SIZE_POLICY_VERSION", "STATISTICS_POLICY_VERSION", "load_boundary_selection_policy",
    "load_interval_policy", "load_sample_size_policy", "load_statistics_policy",
]
