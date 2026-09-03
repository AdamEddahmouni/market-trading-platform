from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from squeeze_core.adapters import (
    AdapterContext,
    DiagnosticCode,
    DiagnosticSeverity,
    NormalizationDiagnostic,
    NormalizationResult,
    RejectedRecord,
)
from squeeze_core.contracts import EntitlementState, IngestionMethod


def context() -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime(2026, 1, 2, 15, 0, tzinfo=UTC),
        source_timezone="America/New_York",
        provider="INTERACTIVE_BROKERS",
        adapter_version="ibkr-offline-v1",
        normalization_version="ibkr-normalization-v1",
        entitlement_status=EntitlementState.UNKNOWN,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        request_id="fixture-request-1",
        expected_delay_ms=900_000,
        source_endpoint_name="short-stock-file-shape",
    )


def test_adapter_context_is_immutable_and_requires_aware_ingestion_time() -> None:
    value = context()
    with pytest.raises(ValidationError):
        value.provider = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="timezone-aware"):
        AdapterContext(
            **{
                **value.model_dump(),
                "ingested_at": datetime(2026, 1, 2, 15, 0),
            }
        )


def test_normalization_diagnostic_has_stable_structured_fields() -> None:
    diagnostic = NormalizationDiagnostic(
        code=DiagnosticCode.MISSING_PROVIDER_TIMESTAMP,
        severity=DiagnosticSeverity.WARNING,
        field="provider_timestamp",
        message="Provider timestamp is absent.",
        normalization_continued=True,
        context={"source_record_id": "fixture-1"},
    )

    assert diagnostic.code.value == "MISSING_PROVIDER_TIMESTAMP"
    assert diagnostic.normalization_continued is True
    assert diagnostic.context == {"source_record_id": "fixture-1"}


def test_rejected_result_is_typed_and_cannot_also_contain_observations(make_observation) -> None:
    rejection = RejectedRecord(
        code=DiagnosticCode.UNKNOWN_TIMEZONE,
        message="Naive provider timestamp has no timezone assumption.",
        raw_record_hash="a" * 64,
        source_record_id="fixture-1",
    )
    result = NormalizationResult(rejection=rejection)

    assert result.accepted is False
    assert result.observations == ()
    with pytest.raises(ValidationError, match="rejected result cannot contain observations"):
        NormalizationResult(
            observations=(make_observation("record-1"),),
            rejection=rejection,
        )


def test_success_result_exposes_typed_tuples(make_observation) -> None:
    result = NormalizationResult(observations=(make_observation("record-1"),))

    assert result.accepted is True
    assert isinstance(result.observations, tuple)
    assert result.diagnostics == ()
