from datetime import datetime

import pytest

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.diagnostics import DiagnosticCode
from squeeze_core.adapters.halts import (
    normalize_trading_halt_record,
    normalize_trading_halt_records,
)
from squeeze_core.contracts import (
    EntitlementState,
    EventType,
    IngestionMethod,
    QualityState,
)
from squeeze_core.serialization import canonical_hash


def context(received: str = "2026-01-15T15:01:30Z") -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(received.replace("Z", "+00:00")),
        source_timezone="-05:00",
        provider="exchange-shaped-offline-fixture",
        adapter_version="1.0.0",
        normalization_version="trading-halts-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="representative-halt-table",
    )


def record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "testa-halt-001",
        "provider_schema": "TRADING_HALT_V1",
        "record_type": "TRADING_HALT",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "symbol": "TESTA",
        "exchange": "XTEST",
        "provider_halt_id": "halt-001",
        "provider_record_id": "row-001",
        "halt_code": "T1",
        "reason_text": "News pending",
        "announcement_at": "2026-01-15T10:01:00-05:00",
        "halt_at": "2026-01-15T10:00:00-05:00",
        "publication_at": "2026-01-15T15:01:00Z",
        "session_date": "2026-01-15",
        "timezone": "-05:00",
        "status": "HALT_ACTIVE",
        "revision_status": "ORIGINAL",
        "revision_number": 0,
    }
    value.update(overrides)
    return value


def codes(result) -> set[DiagnosticCode]:
    return {item.code for item in result.diagnostics}


def test_complete_halt_normalizes_without_extending_canonical_payload() -> None:
    raw = record()
    result = normalize_trading_halt_record(raw, context())

    assert result.accepted and len(result.observations) == 1
    observation = result.observations[0]
    assert observation.event_type is EventType.TRADING_HALT
    assert observation.payload.halt_status == "HALT_ACTIVE"
    assert observation.payload.halt_reason == "News pending"
    assert observation.payload.halt_time.isoformat() == "2026-01-15T15:00:00+00:00"
    assert observation.payload.resume_time is None
    assert observation.source_timestamp.isoformat() == "2026-01-15T15:01:00+00:00"
    assert observation.received_timestamp.isoformat() == "2026-01-15T15:01:30+00:00"
    assert observation.effective_timestamp == observation.received_timestamp
    assert observation.raw_payload_hash == canonical_hash(raw)
    metadata = observation.provenance.provider_metadata
    assert metadata["halt_code"] == "T1"
    assert metadata["halt_event_key"] == "provider:halt-001"
    assert metadata["session_date"] == "2026-01-15"
    assert not hasattr(observation.payload, "halt_code")
    assert not hasattr(observation.payload, "quote_resumption_scheduled_at")


@pytest.mark.parametrize(
    ("status", "field", "value", "diagnostic", "actual"),
    [
        (
            "QUOTE_RESUMPTION_SCHEDULED",
            "quote_resumption_scheduled_at",
            "2026-01-15T10:20:00-05:00",
            DiagnosticCode.HALT_QUOTE_RESUMPTION_SCHEDULED,
            False,
        ),
        (
            "QUOTE_RESUMED",
            "quote_resumed_at",
            "2026-01-15T10:30:00-05:00",
            DiagnosticCode.HALT_QUOTE_RESUMED,
            True,
        ),
        (
            "TRADE_RESUMPTION_SCHEDULED",
            "trade_resumption_scheduled_at",
            "2026-01-15T10:35:00-05:00",
            DiagnosticCode.HALT_TRADE_RESUMPTION_SCHEDULED,
            False,
        ),
        (
            "TRADING_RESUMED",
            "trading_resumed_at",
            "2026-01-15T10:40:00-05:00",
            DiagnosticCode.HALT_TRADING_RESUMED,
            True,
        ),
    ],
)
def test_lifecycle_keeps_scheduled_and_actual_times_separate(
    status: str,
    field: str,
    value: str,
    diagnostic: DiagnosticCode,
    actual: bool,
) -> None:
    result = normalize_trading_halt_record(
        record(
            source_record_id=f"testa-{status.lower()}",
            status=status,
            publication_at="2026-01-15T15:10:00Z",
            **{field: value},
        ),
        context("2026-01-15T15:10:30Z"),
    )
    observation = result.observations[0]

    assert diagnostic in codes(result)
    assert (observation.payload.resume_time is not None) is actual
    assert observation.provenance.provider_metadata[field].isoformat().endswith("+00:00")


def test_indefinite_halt_and_missing_code_are_partial_not_zero() -> None:
    result = normalize_trading_halt_record(
        record(halt_code=None, reason_text=None), context()
    )
    observation = result.observations[0]
    assert result.accepted
    assert observation.quality.state is QualityState.MISSING
    assert observation.payload.resume_time is None
    assert {
        DiagnosticCode.HALT_MISSING_CODE,
        DiagnosticCode.HALT_INDEFINITE,
        DiagnosticCode.HALT_PARTIAL_RECORD,
    } <= codes(result)


def test_unknown_code_is_preserved_without_inventing_reason() -> None:
    result = normalize_trading_halt_record(
        record(halt_code="X99", reason_text=None), context()
    )
    assert result.accepted
    assert result.observations[0].provenance.provider_metadata["halt_code"] == "X99"
    assert result.observations[0].payload.halt_reason is None
    assert DiagnosticCode.HALT_UNKNOWN_CODE in codes(result)


def test_ambiguous_availability_rejects_and_missing_halt_time_is_partial() -> None:
    rejected = normalize_trading_halt_record(
        record(publication_at=None, announcement_at=None), context()
    )
    assert not rejected.accepted
    assert rejected.rejection.code is DiagnosticCode.HALT_MISSING_ANNOUNCEMENT_TIMESTAMP

    partial = normalize_trading_halt_record(record(halt_at=None), context())
    assert partial.accepted
    assert partial.observations[0].payload.halt_time is None
    assert DiagnosticCode.HALT_MISSING_EFFECTIVE_TIMESTAMP in codes(partial)


def test_receipt_before_publication_waits_for_public_availability() -> None:
    result = normalize_trading_halt_record(
        record(publication_at="2026-01-15T15:05:00Z"),
        context("2026-01-15T15:01:30Z"),
    )
    observation = result.observations[0]
    assert observation.effective_timestamp == observation.source_timestamp
    assert DiagnosticCode.HALT_RECEIVED_BEFORE_PUBLICATION in codes(result)


def test_batch_links_revision_suppresses_exact_duplicate_and_preserves_same_id_conflict() -> None:
    original = record()
    update = record(
        source_record_id="testa-halt-002",
        provider_record_id="row-002",
        status="QUOTE_RESUMPTION_SCHEDULED",
        quote_resumption_scheduled_at="2026-01-15T10:20:00-05:00",
        publication_at="2026-01-15T15:10:00Z",
        revision_status="UPDATED",
        revision_number=1,
        supersedes_source_record_id="testa-halt-001",
    )
    conflict = record(reason_text="Different reason")
    result = normalize_trading_halt_records(
        [original, original, update, conflict], context("2026-01-15T15:11:00Z")
    )

    assert len(result.observations) == 3
    prior = next(item for item in result.observations if item.raw_payload_hash == canonical_hash(original))
    revision = next(item for item in result.observations if item.source_record_id == "testa-halt-002")
    assert revision.parent_observation_ids == (prior.observation_id,)
    assert revision.correlation_id == prior.correlation_id
    assert any(item.quality.state is QualityState.CONFLICTED for item in result.observations)
    assert {
        DiagnosticCode.HALT_DUPLICATE_RECORD,
        DiagnosticCode.HALT_CONFLICTING_RECORD,
        DiagnosticCode.HALT_REVISION_RECORD,
    } <= codes(result)


def test_revision_without_present_parent_is_retained_with_diagnostic() -> None:
    result = normalize_trading_halt_records(
        [
            record(
                source_record_id="testa-update-only",
                revision_status="UPDATED",
                supersedes_source_record_id="missing-original",
            )
        ],
        context(),
    )
    assert result.accepted
    assert DiagnosticCode.HALT_REVISION_LINK_MISSING in codes(result)
