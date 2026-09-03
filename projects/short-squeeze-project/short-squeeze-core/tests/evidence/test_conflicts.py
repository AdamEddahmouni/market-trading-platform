from datetime import timedelta
from decimal import Decimal

from squeeze_core.contracts import Observation
from squeeze_core.evidence import (
    ConflictClassification,
    CoverageDomain,
    CoverageState,
    EvidenceDiagnosticCode,
    build_conflicts,
    build_point_in_time_evidence,
    semantic_values,
)

from .test_selection_and_coverage import AS_OF, observations, policy, rebuild


def second_source_snapshot(
    original: Observation, *, float_shares: int, source: str = "synthetic-second-source"
) -> Observation:
    payload = original.payload.model_copy(update={"float_shares": float_shares})
    provenance = original.provenance.model_copy(update={"provider": source})
    return rebuild(
        original,
        source=source,
        source_record_id=f"{source}:market_snapshot",
        payload=payload,
        provenance=provenance,
    )


def test_same_compatible_field_and_time_with_different_values_is_preserved() -> None:
    snapshot = observations()[0]
    second = second_source_snapshot(snapshot, float_shares=10_500_000)
    bundle = build_point_in_time_evidence("TESTA", [snapshot, second], policy())
    conflict = next(item for item in bundle.conflicts if item.semantic_field == "float_shares")

    assert conflict.classification is ConflictClassification.VALUE_CONFLICT
    assert conflict.values == (8_000_000, 10_500_000)
    assert conflict.absolute_difference == Decimal("2500000")
    assert conflict.status == "UNRESOLVED"
    assert {item.payload.float_shares for item in bundle.observations} == {
        8_000_000,
        10_500_000,
    }
    assert not hasattr(bundle, "selected_provider")
    assert not hasattr(conflict, "winning_observation_id")
    coverage = {item.domain: item.state for item in bundle.source_coverage}
    assert coverage[CoverageDomain.CANDIDATE_SNAPSHOT] is CoverageState.CONFLICTED
    assert EvidenceDiagnosticCode.EVIDENCE_FIELD_CONFLICT in {
        item.code for item in bundle.diagnostics
    }


def test_same_provider_same_time_is_duplicate_source_inconsistency() -> None:
    snapshot = observations()[0]
    duplicate_conflict = second_source_snapshot(
        snapshot, float_shares=9_000_000, source=snapshot.source
    )
    conflicts = build_conflicts([snapshot, duplicate_conflict], policy())
    conflict = next(item for item in conflicts if item.semantic_field == "float_shares")

    assert conflict.classification is ConflictClassification.DUPLICATE_CONFLICT


def test_different_timestamps_are_temporal_differences_not_value_conflicts() -> None:
    snapshot = observations()[0]
    later = rebuild(
        snapshot,
        source_record_id="later-snapshot",
        source_timestamp=snapshot.source_timestamp + timedelta(minutes=1),
        effective_timestamp=snapshot.effective_timestamp + timedelta(minutes=1),
    )
    conflicts = build_conflicts([snapshot, later], policy())
    float_conflict = next(item for item in conflicts if item.semantic_field == "float_shares")

    assert float_conflict.classification is ConflictClassification.TEMPORAL_DIFFERENCE
    assert float_conflict.values == (8_000_000, 8_000_000)


def test_incompatible_short_float_fee_and_availability_are_never_compared() -> None:
    snapshot, fee, availability = observations()
    conflicts = build_conflicts([snapshot, fee, availability], policy())
    fields = {item.semantic_field for item in conflicts}
    snapshot_fields = {item.semantic_field for item in semantic_values(snapshot)}
    fee_fields = {item.semantic_field for item in semantic_values(fee)}
    availability_fields = {item.semantic_field for item in semantic_values(availability)}

    assert "short_float_percent" in snapshot_fields
    assert "annualized_borrow_fee_percent" in fee_fields
    assert "borrow_available_shares" in availability_fields
    assert snapshot_fields.isdisjoint(fee_fields)
    assert snapshot_fields.isdisjoint(availability_fields)
    assert fee_fields.isdisjoint(availability_fields)
    assert fields == set()


def test_conflict_ids_order_and_bundle_hash_are_stable() -> None:
    snapshot = observations()[0]
    second = second_source_snapshot(snapshot, float_shares=10_500_000)
    first = build_point_in_time_evidence("TESTA", [snapshot, second], policy())
    reversed_input = build_point_in_time_evidence("TESTA", [second, snapshot], policy())

    assert first == reversed_input
    assert all(item.conflict_id.startswith("conflict-") for item in first.conflicts)


def test_configured_tolerance_suppresses_small_value_conflict_without_winner() -> None:
    snapshot = observations()[0]
    second = second_source_snapshot(snapshot, float_shares=8_000_100)
    tolerant = policy(conflict_tolerance={"float_shares": Decimal("100")})

    assert not any(
        item.semantic_field == "float_shares"
        for item in build_conflicts([snapshot, second], tolerant)
    )
