from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.evidence import CoverageDomain
from squeeze_core.readiness import (
    DomainCoverageSnapshot,
    DomainCoverageState,
    EvidenceAgeAlignment,
    OperationRequirementPolicy,
    StructuralState,
    coverage_snapshot_hash,
    serialize_coverage_snapshot,
)
from squeeze_core.readiness.models import AgeDimension

AS_OF = datetime(2026, 3, 1, tzinfo=UTC)


def _snapshot(**overrides) -> DomainCoverageSnapshot:
    values = dict(
        symbol="TESTD",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        requested_domains=(CoverageDomain.MARKET_BARS,),
        present_domains=(CoverageDomain.MARKET_BARS,),
        quality=Quality(state=QualityState.KNOWN_VALUE),
    )
    values.update(overrides)
    return DomainCoverageSnapshot(**values)


def test_coverage_snapshot_is_frozen():
    snapshot = _snapshot()
    with pytest.raises(ValidationError):
        snapshot.symbol = "OTHER"


def test_structural_state_has_exactly_four_members():
    assert {member.value for member in StructuralState} == {
        "SUFFICIENT",
        "INSUFFICIENT",
        "UNKNOWN",
        "CONFLICTED",
    }


def test_domain_coverage_state_has_exactly_seven_members():
    assert {member.value for member in DomainCoverageState} == {
        "PRESENT",
        "MISSING",
        "UNAVAILABLE",
        "CONFLICTED",
        "CANCELLED",
        "PARTIAL",
        "UNKNOWN",
    }


def test_age_dimension_has_exactly_two_members():
    assert {member.value for member in AgeDimension} == {
        "AVAILABILITY_AGE",
        "REPORTING_PERIOD_AGE",
    }


def test_deterministic_id_stable_across_two_constructions():
    first = _snapshot()
    second = _snapshot()
    assert first.deterministic_id == second.deterministic_id


def test_canonical_serialization_round_trips():
    snapshot = _snapshot()
    serialized = serialize_coverage_snapshot(snapshot)
    restored = DomainCoverageSnapshot.model_validate_json(serialized)
    assert restored == snapshot


def test_hash_stable_across_two_constructions():
    assert coverage_snapshot_hash(_snapshot()) == coverage_snapshot_hash(_snapshot())


def test_no_score_rank_recommendation_or_qualitative_fields_on_any_model():
    forbidden_substrings = (
        "score",
        "rank",
        "recommend",
        "prime",
        "subprime",
        "bullish",
        "bearish",
        "confidence_percent",
        "alert",
    )
    from squeeze_core.readiness import models as models_module

    for name in models_module.__all__:
        obj = getattr(models_module, name)
        if not hasattr(obj, "model_fields"):
            continue
        for field_name in obj.model_fields:
            lowered = field_name.lower()
            for forbidden in forbidden_substrings:
                assert forbidden not in lowered, f"{name}.{field_name} looks qualitative"


def test_no_model_defines_schema_version():
    from squeeze_core.readiness import models as models_module

    for name in models_module.__all__:
        obj = getattr(models_module, name)
        if not hasattr(obj, "model_fields"):
            continue
        assert "schema_version" not in obj.model_fields


def test_operation_requirement_policy_rejects_overlapping_domains():
    with pytest.raises(ValidationError):
        OperationRequirementPolicy(
            operation="X",
            policy_version="v1",
            required_domains=(CoverageDomain.MARKET_BARS,),
            optional_domains=(CoverageDomain.MARKET_BARS,),
        )


def test_age_alignment_frozen_and_hashable():
    alignment = EvidenceAgeAlignment(
        symbol="TESTD",
        asset_class=AssetClass.EQUITY,
        as_of=AS_OF,
        age_dimension=AgeDimension.AVAILABILITY_AGE,
        domain_count=0,
        quality=Quality(state=QualityState.KNOWN_VALUE),
    )
    with pytest.raises(ValidationError):
        alignment.domain_count = 5
    assert alignment.deterministic_id is not None
