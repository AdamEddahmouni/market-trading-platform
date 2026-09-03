from datetime import datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.halts import (
    normalize_trading_halt_record,
    normalize_trading_halt_records,
)
from squeeze_core.contracts import EntitlementState, IngestionMethod
from squeeze_core.evidence import (
    ConflictClassification,
    CoverageDomain,
    CoverageState,
    HaltState,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)


def context(received: str = "2026-01-15T15:30:00Z") -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(received.replace("Z", "+00:00")),
        source_timezone="UTC",
        provider="exchange-shaped-offline-fixture",
        adapter_version="1.0.0",
        normalization_version="trading-halts-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
    )


def raw(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "halt-001",
        "provider_schema": "TRADING_HALT_V1",
        "record_type": "TRADING_HALT",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "symbol": "TESTA",
        "exchange": "XTEST",
        "provider_halt_id": "event-001",
        "halt_code": "T1",
        "reason_text": "News pending",
        "announcement_at": "2026-01-15T15:01:00Z",
        "halt_at": "2026-01-15T15:00:00Z",
        "publication_at": "2026-01-15T15:01:00Z",
        "session_date": "2026-01-15",
        "timezone": "UTC",
        "status": "HALT_ACTIVE",
        "revision_status": "ORIGINAL",
    }
    value.update(overrides)
    return value


def normalize(value: dict[str, object], received: str = "2026-01-15T15:30:00Z"):
    return normalize_trading_halt_record(value, context(received)).observations[0]


def bundle(observations):
    return build_point_in_time_evidence(
        "TESTA",
        observations,
        PointInTimeEvidencePolicy(
            as_of=datetime.fromisoformat("2026-01-15T16:00:00+00:00"),
            include_trading_halts_domain=True,
        ),
    )


def halt_coverage(value):
    return next(
        item for item in value.source_coverage if item.domain is CoverageDomain.TRADING_HALTS
    )


def test_conflicting_halt_codes_are_preserved_without_winner() -> None:
    first = normalize(raw(source_record_id="halt-code-a", halt_code="T1"))
    second = normalize(raw(source_record_id="halt-code-b", halt_code="T2"))
    result = bundle([first, second])

    conflict = next(item for item in result.conflicts if item.semantic_field == "halt_code")
    assert conflict.classification is ConflictClassification.DUPLICATE_CONFLICT
    assert conflict.values == ("T1", "T2")
    assert conflict.status == "UNRESOLVED"
    assert result.halt_state.state is HaltState.CONFLICTED
    assert halt_coverage(result).state is CoverageState.CONFLICTED


def test_conflicting_scheduled_times_are_not_averaged() -> None:
    first = normalize(
        raw(
            source_record_id="schedule-a",
            status="QUOTE_RESUMPTION_SCHEDULED",
            quote_resumption_scheduled_at="2026-01-15T15:25:00Z",
        )
    )
    second = normalize(
        raw(
            source_record_id="schedule-b",
            status="QUOTE_RESUMPTION_SCHEDULED",
            quote_resumption_scheduled_at="2026-01-15T15:27:00Z",
        )
    )
    result = bundle([first, second])
    conflict = next(
        item
        for item in result.conflicts
        if item.semantic_field == "halt_quote_resumption_scheduled_at"
    )
    assert set(conflict.values) == {
        datetime.fromisoformat("2026-01-15T15:25:00+00:00"),
        datetime.fromisoformat("2026-01-15T15:27:00+00:00"),
    }
    assert conflict.absolute_difference is None


def test_scheduled_and_actual_lifecycle_progression_is_not_a_conflict() -> None:
    scheduled = normalize(
        raw(
            source_record_id="schedule",
            status="QUOTE_RESUMPTION_SCHEDULED",
            quote_resumption_scheduled_at="2026-01-15T15:25:00Z",
        ),
        "2026-01-15T15:10:00Z",
    )
    actual = normalize(
        raw(
            source_record_id="actual",
            status="QUOTE_RESUMED",
            quote_resumed_at="2026-01-15T15:26:00Z",
            publication_at="2026-01-15T15:26:00Z",
            announcement_at="2026-01-15T15:26:00Z",
        ),
        "2026-01-15T15:26:00Z",
    )
    result = bundle([scheduled, actual])
    assert not any(
        item.semantic_field.startswith("halt_quote") for item in result.conflicts
    )
    assert result.halt_state.state is HaltState.QUOTES_RESUMED


def test_declared_schedule_revision_is_relationship_not_unresolved_conflict() -> None:
    original = raw(
        source_record_id="schedule-original",
        status="QUOTE_RESUMPTION_SCHEDULED",
        quote_resumption_scheduled_at="2026-01-15T15:25:00Z",
    )
    revision = raw(
        source_record_id="schedule-update",
        status="QUOTE_RESUMPTION_SCHEDULED",
        quote_resumption_scheduled_at="2026-01-15T15:27:00Z",
        publication_at="2026-01-15T15:20:00Z",
        announcement_at="2026-01-15T15:20:00Z",
        revision_status="UPDATED",
        supersedes_source_record_id="schedule-original",
    )
    normalized = normalize_trading_halt_records([original, revision], context())
    result = bundle(normalized.observations)

    assert not any(
        item.semantic_field == "halt_quote_resumption_scheduled_at"
        for item in result.conflicts
    )
    assert len(result.revision_relationships) == 1
    assert result.revision_relationships[0].status == "UPDATED"


def test_distinct_halt_events_are_temporal_not_merged() -> None:
    first = normalize(raw(source_record_id="event-a", provider_halt_id="event-a"))
    second = normalize(
        raw(
            source_record_id="event-b",
            provider_halt_id="event-b",
            halt_at="2026-01-15T15:45:00Z",
            publication_at="2026-01-15T15:46:00Z",
            announcement_at="2026-01-15T15:46:00Z",
        ),
        "2026-01-15T15:46:00Z",
    )
    result = bundle([first, second])
    assert len(result.halt_state.halt_event_keys) == 2
    assert all(
        item.classification is ConflictClassification.TEMPORAL_DIFFERENCE
        for item in result.conflicts
        if item.semantic_field.startswith("halt_")
    )


def test_conflict_ids_and_order_are_deterministic() -> None:
    first = normalize(raw(source_record_id="halt-code-a", halt_code="T1"))
    second = normalize(raw(source_record_id="halt-code-b", halt_code="T2"))
    forward = bundle([first, second])
    reverse = bundle([second, first])
    assert forward.conflicts == reverse.conflicts
    assert forward.bundle_hash == reverse.bundle_hash
