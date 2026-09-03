from datetime import datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.diagnostics import DiagnosticCode
from squeeze_core.adapters.sec import (
    normalize_sec_filing_record,
    normalize_sec_filing_records,
)
from squeeze_core.contracts import (
    EntitlementState,
    EventType,
    IngestionMethod,
    QualityState,
)
from squeeze_core.serialization import canonical_hash


def context(received: str = "2026-01-20T15:00:00Z") -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(received.replace("Z", "+00:00")),
        source_timezone=None,
        provider="sec-shaped-offline-fixture",
        adapter_version="1.0.0",
        normalization_version="sec-filings-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="submissions-metadata",
    )


def record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "testa-original",
        "provider_schema": "SEC_FILING_V1",
        "record_type": "SEC_FILING",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "symbol": "TESTA",
        "issuer_cik": "1",
        "company_name": "Test A Corp.",
        "form_type": "10-Q",
        "accession_number": "0000000001-26-000001",
        "filed_at": "2026-01-20",
        "accepted_at": "2026-01-20T14:30:00Z",
        "period_of_report": "2026-01-15",
        "primary_document": "testa-20260115x10q.htm",
        "is_amendment": False,
        "document_count": "3",
        "file_number": "001-00001",
        "filing_status": "ORIGINAL",
    }
    value.update(overrides)
    return value


def codes(result) -> set[DiagnosticCode]:
    return {item.code for item in result.diagnostics}


def test_complete_record_normalizes_to_canonical_sec_filing() -> None:
    raw = record()
    result = normalize_sec_filing_record(raw, context())

    assert result.accepted and len(result.observations) == 1
    observation = result.observations[0]
    assert observation.event_type is EventType.SEC_FILING
    assert observation.payload.issuer_cik == "0000000001"
    assert observation.payload.accession_number == "0000000001-26-000001"
    assert observation.payload.form_type == "10-Q"
    assert str(observation.payload.period_of_report) == "2026-01-15"
    assert observation.source_timestamp.isoformat() == "2026-01-20T14:30:00+00:00"
    assert observation.received_timestamp.isoformat() == "2026-01-20T15:00:00+00:00"
    assert observation.effective_timestamp == observation.received_timestamp
    assert observation.raw_payload_hash == canonical_hash(raw)
    assert observation.provenance.provider_metadata["acceptance_timestamp"] == observation.source_timestamp
    assert not hasattr(observation.payload, "sentiment")
    assert not hasattr(observation.payload, "catalyst")


def test_compact_accession_and_unpadded_cik_are_diagnosed() -> None:
    result = normalize_sec_filing_record(
        record(accession_number="000000000126000001", issuer_cik="1"), context()
    )
    assert result.accepted
    assert result.observations[0].payload.accession_number == "0000000001-26-000001"
    assert {DiagnosticCode.SEC_ACCESSION_NORMALIZED, DiagnosticCode.SEC_CIK_NORMALIZED} <= codes(result)


def test_missing_cik_is_partial_but_defensible() -> None:
    result = normalize_sec_filing_record(record(issuer_cik=None), context())
    assert result.accepted
    assert result.observations[0].payload.issuer_cik is None
    assert result.observations[0].quality.state is QualityState.MISSING
    assert {DiagnosticCode.SEC_MISSING_CIK, DiagnosticCode.SEC_PARTIAL_RECORD} <= codes(result)


def test_invalid_accession_rejects_without_guessing() -> None:
    result = normalize_sec_filing_record(record(accession_number="bad"), context())
    assert not result.accepted
    assert result.observations == ()
    assert result.rejection.code is DiagnosticCode.SEC_INVALID_ACCESSION


def test_explicit_publication_is_source_boundary_and_receipt_can_precede_it() -> None:
    result = normalize_sec_filing_record(
        record(published_at="2026-01-20T15:30:00Z"), context("2026-01-20T15:00:00Z")
    )
    observation = result.observations[0]
    assert observation.source_timestamp.isoformat() == "2026-01-20T15:30:00+00:00"
    assert observation.effective_timestamp == observation.source_timestamp
    assert DiagnosticCode.SEC_RECEIVED_BEFORE_ACCEPTANCE in codes(result)


def test_amendment_is_immutable_and_links_to_original_in_batch() -> None:
    original_raw = record()
    amendment_raw = record(
        source_record_id="testa-amendment",
        form_type="10-Q/A",
        accession_number="0000000001-26-000002",
        accepted_at="2026-01-27T14:30:00Z",
        is_amendment=True,
        amends_accession_number="0000000001-26-000001",
        filing_status="AMENDED",
        primary_document="testa-20260115x10qa.htm",
    )
    result = normalize_sec_filing_records(
        [amendment_raw, original_raw], context("2026-01-28T15:00:00Z")
    )
    original = next(item for item in result.observations if item.source_record_id == "testa-original")
    amendment = next(item for item in result.observations if item.source_record_id == "testa-amendment")

    assert amendment.parent_observation_ids == (original.observation_id,)
    assert amendment.correlation_id == original.correlation_id
    assert original.payload.form_type == "10-Q"
    assert amendment.payload.form_type == "10-Q/A"
    assert DiagnosticCode.SEC_AMENDMENT_RECORD in codes(result)


def test_batch_suppresses_exact_duplicate_and_preserves_same_accession_conflict() -> None:
    original = record()
    conflict = record(source_record_id="testa-conflict", primary_document="different.htm")
    result = normalize_sec_filing_records([original, original, conflict], context())

    assert len(result.observations) == 2
    assert all(item.quality.state is QualityState.CONFLICTED for item in result.observations)
    assert {DiagnosticCode.SEC_DUPLICATE_RECORD, DiagnosticCode.SEC_CONFLICTING_RECORD} <= codes(result)


def test_amendment_without_relationship_is_retained_with_diagnostic() -> None:
    result = normalize_sec_filing_record(
        record(form_type="S-1/A", is_amendment=True, amends_accession_number=None),
        context(),
    )
    assert result.accepted
    assert DiagnosticCode.SEC_AMENDMENT_LINK_MISSING in codes(result)
