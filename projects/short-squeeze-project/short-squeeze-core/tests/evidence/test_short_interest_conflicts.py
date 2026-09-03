from datetime import datetime
from decimal import Decimal

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.finra import normalize_finra_short_interest_record
from squeeze_core.contracts import EntitlementState, IngestionMethod, Observation
from squeeze_core.evidence import (
    ConflictClassification,
    PointInTimeEvidencePolicy,
    EvidenceDiagnosticCode,
    build_point_in_time_evidence,
    build_conflicts,
    semantic_values,
)


def context(received: str = "2026-01-22T20:00:00Z") -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(received.replace("Z", "+00:00")),
        source_timezone=None,
        provider="finra-shaped-offline-fixture",
        adapter_version="1.0.0",
        normalization_version="finra-short-interest-v1",
        entitlement_status=EntitlementState.UNKNOWN,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="conflict-cases",
    )


def record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "short-record-1",
        "provider_schema": "FINRA_SHORT_INTEREST_V1",
        "record_type": "PUBLISHED_SHORT_INTEREST",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "symbol": "TESTA",
        "short_shares": "2500000",
        "settlement_date": "2026-01-15",
        "publication_date": "2026-01-22T19:00:00Z",
        "days_to_cover": "2.5",
        "short_float_percent": "12.5",
        "short_float_percent_unit": "PERCENT_POINTS",
        "revision_status": "ORIGINAL",
    }
    value.update(overrides)
    return value


def observation(raw: dict[str, object], received: str = "2026-01-22T20:00:00Z"):
    result = normalize_finra_short_interest_record(raw, context(received))
    assert result.accepted
    return result.observations[0]


def other_source(item, source: str) -> Observation:
    values = item.model_dump(mode="python")
    values["observation_id"] = None
    values["source"] = source
    return Observation.model_validate(values)


def policy() -> PointInTimeEvidencePolicy:
    return PointInTimeEvidencePolicy(
        as_of=datetime.fromisoformat("2026-02-01T15:30:00+00:00"),
        allow_stale=True,
    )


def test_semantic_extraction_names_published_fields_without_conflating_snapshot_fields() -> None:
    item = observation(record())
    extracted = {value.semantic_field: value for value in semantic_values(item)}

    assert extracted["published_short_shares"].value == 2500000
    assert extracted["published_short_shares"].unit == "SHARES"
    assert extracted["published_short_shares"].comparison_period == "2026-01-15"
    assert extracted["published_short_float_percent"].value == Decimal("12.5")
    assert extracted["published_days_to_cover"].value == Decimal("2.5")


def test_same_settlement_period_different_provider_values_are_value_conflict() -> None:
    left = observation(record())
    right = other_source(
        observation(record(source_record_id="short-record-2", short_shares="2600000")),
        "other-published-short-interest-provider",
    )
    conflicts = build_conflicts([left, right], policy())
    conflict = next(item for item in conflicts if item.semantic_field == "published_short_shares")

    assert conflict.classification is ConflictClassification.VALUE_CONFLICT
    assert conflict.comparison_period == "2026-01-15"
    assert conflict.absolute_difference == Decimal("100000")
    assert not hasattr(conflict, "winner")


def test_same_provider_same_period_is_duplicate_conflict_without_averaging() -> None:
    left = observation(record())
    right = observation(record(source_record_id="short-record-2", short_shares="2600000"))
    conflict = next(
        item
        for item in build_conflicts([left, right], policy())
        if item.semantic_field == "published_short_shares"
    )

    assert conflict.classification is ConflictClassification.DUPLICATE_CONFLICT
    assert conflict.values == (2500000, 2600000)
    assert Decimal("2550000") not in conflict.values


def test_different_settlement_period_is_temporal_difference_even_when_publication_time_differs() -> None:
    first = observation(record())
    second = observation(
        record(
            source_record_id="short-record-2",
            settlement_date="2026-01-31",
            publication_date="2026-02-07T19:00:00Z",
            short_shares="2600000",
        ),
        "2026-02-07T20:00:00Z",
    )
    conflict = next(
        item
        for item in build_conflicts([first, second], policy())
        if item.semantic_field == "published_short_shares"
    )

    assert conflict.classification is ConflictClassification.TEMPORAL_DIFFERENCE
    assert conflict.comparison_period == "2026-01-15|2026-01-31"


def test_declared_correction_is_revision_relationship_not_unresolved_conflict() -> None:
    original = observation(record())
    correction = observation(
        record(
            source_record_id="short-correction",
            short_shares="2600000",
            publication_date="2026-01-29T19:00:00Z",
            revision_status="CORRECTED",
            supersedes_source_record_id="short-record-1",
        ),
        "2026-01-30T15:00:00Z",
    )

    conflicts = build_conflicts([original, correction], policy())
    assert all(
        item.semantic_field != "published_short_shares" for item in conflicts
    )


def test_published_fields_do_not_compare_against_borrow_or_finviz_short_float(
    make_observation,
) -> None:
    published = observation(record())
    unrelated = make_observation("unrelated-trade")

    fields = {item.semantic_field for item in semantic_values(published)}
    unrelated_fields = {item.semantic_field for item in semantic_values(unrelated)}
    conflicts = build_conflicts([published, unrelated], policy())

    assert fields.isdisjoint(unrelated_fields)
    assert conflicts == ()


def test_short_interest_conflict_ids_and_order_are_deterministic() -> None:
    left = observation(record())
    right = other_source(
        observation(record(source_record_id="short-record-2", short_shares="2600000")),
        "other-published-short-interest-provider",
    )

    first = build_conflicts([left, right], policy())
    second = build_conflicts([right, left], policy())
    assert first == second


def test_bundle_uses_short_interest_specific_conflict_and_temporal_diagnostics() -> None:
    left = observation(record())
    conflict = other_source(
        observation(record(source_record_id="short-record-2", short_shares="2600000")),
        "other-published-short-interest-provider",
    )
    later = observation(
        record(
            source_record_id="short-record-3",
            settlement_date="2026-01-31",
            publication_date="2026-01-30T19:00:00Z",
            short_shares="2700000",
        ),
        "2026-01-30T20:00:00Z",
    )
    bundle = build_point_in_time_evidence("TESTA", [left, conflict, later], policy())
    codes = {item.code for item in bundle.diagnostics}

    assert EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_PROVIDER_CONFLICT in codes
    assert EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_TEMPORAL_DIFFERENCE in codes
