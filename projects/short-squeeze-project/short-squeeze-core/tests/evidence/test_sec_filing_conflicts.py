from datetime import datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.sec import normalize_sec_filing_record, normalize_sec_filing_records
from squeeze_core.contracts import EntitlementState, IngestionMethod
from squeeze_core.evidence import (
    ConflictClassification,
    EvidenceDiagnosticCode,
    PointInTimeEvidencePolicy,
    build_conflicts,
    build_point_in_time_evidence,
    semantic_values,
)


def context(received: str = "2026-01-20T15:00:00Z") -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(received.replace("Z", "+00:00")),
        source_timezone=None,
        provider="sec-shaped-offline-fixture",
        adapter_version="1.0.0",
        normalization_version="sec-filings-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
    )


def record(**overrides: object) -> dict[str, object]:
    raw: dict[str, object] = {
        "source_record_id": "filing-1",
        "provider_schema": "SEC_FILING_V1",
        "record_type": "SEC_FILING",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "symbol": "TESTA",
        "issuer_cik": "1",
        "form_type": "10-Q",
        "accession_number": "0000000001-26-000001",
        "filed_at": "2026-01-20T14:25:00Z",
        "accepted_at": "2026-01-20T14:30:00Z",
        "period_of_report": "2026-01-15",
        "primary_document": "testa-10q.htm",
        "filing_status": "ORIGINAL",
    }
    raw.update(overrides)
    return raw


def observation(raw: dict[str, object]):
    result = normalize_sec_filing_record(raw, context())
    assert result.accepted
    return result.observations[0]


def policy() -> PointInTimeEvidencePolicy:
    return PointInTimeEvidencePolicy(
        as_of=datetime.fromisoformat("2026-02-01T15:00:00+00:00"), allow_stale=True
    )


def test_semantic_extraction_uses_accession_as_comparison_period() -> None:
    extracted = {value.semantic_field: value for value in semantic_values(observation(record()))}
    assert extracted["sec_form_type"].value == "10-Q"
    assert extracted["sec_primary_document"].value == "testa-10q.htm"
    assert extracted["sec_issuer_cik"].value == "0000000001"
    assert extracted["sec_form_type"].comparison_period == "0000000001-26-000001"


def test_same_accession_different_metadata_is_duplicate_conflict_without_winner() -> None:
    left = observation(record())
    right = observation(record(source_record_id="filing-2", primary_document="different.htm"))
    conflicts = build_conflicts([left, right], policy())
    conflict = next(item for item in conflicts if item.semantic_field == "sec_primary_document")
    assert conflict.classification is ConflictClassification.DUPLICATE_CONFLICT
    assert not hasattr(conflict, "winner")


def test_different_accessions_are_temporal_differences() -> None:
    first = observation(record())
    second = observation(
        record(
            source_record_id="filing-2",
            accession_number="0000000001-26-000002",
            accepted_at="2026-01-27T14:30:00Z",
            form_type="8-K",
        )
    )
    conflict = next(
        item for item in build_conflicts([first, second], policy()) if item.semantic_field == "sec_form_type"
    )
    assert conflict.classification is ConflictClassification.TEMPORAL_DIFFERENCE
    assert conflict.comparison_period == "0000000001-26-000001|0000000001-26-000002"


def test_declared_amendment_relationship_is_not_unresolved_conflict() -> None:
    amended = record(
        source_record_id="filing-a",
        accession_number="0000000001-26-000002",
        form_type="10-Q/A",
        accepted_at="2026-01-27T14:30:00Z",
        is_amendment=True,
        amends_accession_number="0000000001-26-000001",
        filing_status="AMENDED",
    )
    result = normalize_sec_filing_records([record(), amended], context("2026-01-28T15:00:00Z"))
    conflicts = build_conflicts(result.observations, policy())
    assert all(item.semantic_field != "sec_form_type" for item in conflicts)


def test_sec_metadata_does_not_compare_with_market_borrow_or_short_interest(make_observation) -> None:
    filing = observation(record())
    unrelated = make_observation("unrelated-trade")
    assert {item.semantic_field for item in semantic_values(filing)}.isdisjoint(
        {item.semantic_field for item in semantic_values(unrelated)}
    )
    assert build_conflicts([filing, unrelated], policy()) == ()


def test_conflict_ids_and_order_are_deterministic() -> None:
    left = observation(record())
    right = observation(record(source_record_id="filing-2", primary_document="different.htm"))
    assert build_conflicts([left, right], policy()) == build_conflicts([right, left], policy())


def test_bundle_uses_sec_specific_conflict_diagnostic() -> None:
    left = observation(record())
    right = observation(record(source_record_id="filing-2", primary_document="different.htm"))
    bundle = build_point_in_time_evidence("TESTA", [left, right], policy())
    assert EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_CONFLICT in {
        item.code for item in bundle.diagnostics
    }
