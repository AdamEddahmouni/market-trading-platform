from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from squeeze_core.contracts import AssetClass
from squeeze_core.research.models import (
    CandidateCaseRegistryEntry,
    CandidateCaseStatus,
    CandidateCaseType,
    DetectionStatus,
    FixtureClassification,
    OriginalPlatformStatus,
    OutcomeLabel,
    ResearchCaseClassification,
)


AS_OF = datetime(2026, 7, 17, 14, 23, 58, tzinfo=timezone.utc)


def entry(**updates):
    values = {
        "case_id": "CASE-A",
        "symbol": "biya",
        "asset_class": AssetClass.EQUITY,
        "case_type": CandidateCaseType.ORIGINAL_PLATFORM_SURFACED,
        "case_status": CandidateCaseStatus.COMPLETE,
        "original_platform_status": OriginalPlatformStatus.SURFACED,
        "detection_time_evidence_id": "detection-a",
        "evaluation_as_of": AS_OF,
        "evaluation_result_path": "../evaluation/case-a.json",
        "outcome_observation_path": "../validation/outcome-a.json",
        "original_platform_artifact_ids": ("artifact-b", "artifact-a"),
        "historical_dataset_ids": ("dataset-a",),
        "phase_3a_policy_version": "phase_3a_transparent_candidate_policy.v1",
        "limitations": ("limitation-b", "limitation-a"),
        "fixture_classification": FixtureClassification.SANITIZED_PUBLIC_HISTORICAL_DATA,
    }
    values.update(updates)
    return CandidateCaseRegistryEntry(**values)


def test_exact_research_vocabularies():
    assert [item.value for item in DetectionStatus] == [
        "DETECTED", "NOT_DETECTED", "UNEVALUABLE"
    ]
    assert [item.value for item in OutcomeLabel] == [
        "SUBSTANTIAL_UPWARD_MOVE", "NO_SUBSTANTIAL_UPWARD_MOVE",
        "SUBSTANTIAL_DOWNWARD_MOVE", "MIXED_OR_VOLATILE", "OUTCOME_UNKNOWN",
        "OUTCOME_INSUFFICIENT_DATA",
    ]
    assert [item.value for item in ResearchCaseClassification] == [
        "TRUE_POSITIVE", "FALSE_POSITIVE", "TRUE_NEGATIVE", "FALSE_NEGATIVE",
        "UNEVALUABLE", "NOT_APPLICABLE",
    ]


def test_registry_entry_is_frozen_normalized_sorted_and_deterministic():
    first = entry()
    second = entry(
        symbol=" BIYA ",
        original_platform_artifact_ids=("artifact-a", "artifact-b"),
        limitations=("limitation-a", "limitation-b"),
    )
    assert first.symbol == "BIYA"
    assert first == second
    assert first.deterministic_id == second.deterministic_id
    assert first.deterministic_id
    with pytest.raises(ValidationError):
        CandidateCaseRegistryEntry(**{
            **first.model_dump(), "deterministic_id": first.deterministic_id, "score": 1
        })
    with pytest.raises(ValidationError):
        first.case_id = "CASE-B"


def test_research_contract_has_no_prohibited_fields():
    prohibited = {
        "score", "weight", "points", "rank", "recommendation", "alert", "pnl",
        "profit", "entry", "exit", "position_size", "trade",
    }
    names = {name.lower() for name in CandidateCaseRegistryEntry.model_fields}
    assert names.isdisjoint(prohibited)
