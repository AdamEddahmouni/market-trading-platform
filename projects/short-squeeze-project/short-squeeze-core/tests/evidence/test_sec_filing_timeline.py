from datetime import datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.sec import normalize_sec_filing_record, normalize_sec_filing_records
from squeeze_core.contracts import EntitlementState, IngestionMethod
from squeeze_core.evidence import (
    CoverageDomain,
    CoverageState,
    EvidenceDiagnosticCode,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)
from squeeze_core.serialization import canonical_json_bytes


def context(received: str) -> AdapterContext:
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
        "source_record_id": "testa-original",
        "provider_schema": "SEC_FILING_V1",
        "record_type": "SEC_FILING",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "symbol": "TESTA",
        "issuer_cik": "0000000001",
        "form_type": "10-Q",
        "accession_number": "0000000001-26-000001",
        "filed_at": "2026-01-20T14:25:00Z",
        "accepted_at": "2026-01-20T14:30:00Z",
        "period_of_report": "2026-01-15",
        "primary_document": "testa-10q.htm",
        "is_amendment": False,
        "filing_status": "ORIGINAL",
    }
    raw.update(overrides)
    return raw


def observation(raw: dict[str, object], received: str):
    result = normalize_sec_filing_record(raw, context(received))
    assert result.accepted
    return result.observations[0]


def policy(as_of: str, **overrides: object) -> PointInTimeEvidencePolicy:
    values: dict[str, object] = {
        "as_of": datetime.fromisoformat(as_of.replace("Z", "+00:00")),
        "allow_stale": True,
        "allow_delayed": True,
        "allow_unknown_freshness": True,
        "include_sec_filings_domain": True,
    }
    values.update(overrides)
    return PointInTimeEvidencePolicy.model_validate(values)


def codes(bundle) -> set[EvidenceDiagnosticCode]:
    return {item.code for item in bundle.diagnostics}


def coverage(bundle):
    return next(item for item in bundle.source_coverage if item.domain is CoverageDomain.SEC_FILINGS)


def test_period_and_filed_time_before_as_of_do_not_make_unaccepted_filing_eligible() -> None:
    filing = observation(record(accepted_at="2026-01-20T16:00:00Z"), "2026-01-20T17:00:00Z")
    bundle = build_point_in_time_evidence("TESTA", [filing], policy("2026-01-20T15:00:00Z"))

    assert bundle.observations == ()
    assert EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_NOT_YET_ACCEPTED in codes(bundle)
    assert coverage(bundle).state is CoverageState.MISSING


def test_accepted_before_as_of_but_received_after_is_excluded() -> None:
    filing = observation(record(), "2026-01-20T16:00:00Z")
    bundle = build_point_in_time_evidence("TESTA", [filing], policy("2026-01-20T15:00:00Z"))
    assert bundle.observations == ()
    assert EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_NOT_YET_RECEIVED in codes(bundle)


def test_available_filing_has_independent_availability_filing_and_reporting_ages() -> None:
    filing = observation(record(), "2026-01-20T15:00:00Z")
    bundle = build_point_in_time_evidence("TESTA", [filing], policy("2026-01-23T15:00:00Z"))

    assert bundle.observations == (filing,)
    assert coverage(bundle).state is CoverageState.PRESENT
    age = bundle.observation_ages[0]
    assert age.availability_age_ms == 259_200_000
    assert age.filing_age_ms == 261_000_000
    assert age.reporting_period_age_days == 8


def test_partial_filing_has_partial_independent_coverage() -> None:
    filing = observation(record(issuer_cik=None), "2026-01-20T15:00:00Z")
    bundle = build_point_in_time_evidence("TESTA", [filing], policy("2026-01-23T15:00:00Z"))
    assert coverage(bundle).state is CoverageState.PARTIAL
    assert EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_PARTIAL_COVERAGE in codes(bundle)


def test_later_amendment_does_not_change_historical_bundle() -> None:
    amendment = record(
        source_record_id="testa-amendment",
        form_type="10-Q/A",
        accession_number="0000000001-26-000002",
        filed_at="2026-01-27T14:25:00Z",
        accepted_at="2026-01-27T14:30:00Z",
        is_amendment=True,
        amends_accession_number="0000000001-26-000001",
        filing_status="AMENDED",
        primary_document="testa-10qa.htm",
    )
    normalized = normalize_sec_filing_records(
        [record(), amendment], context("2026-01-28T15:00:00Z")
    )
    original, amended = sorted(normalized.observations, key=lambda item: item.source_timestamp)
    original = original.model_copy(update={"received_timestamp": datetime.fromisoformat("2026-01-20T15:00:00+00:00"), "effective_timestamp": datetime.fromisoformat("2026-01-20T15:00:00+00:00")})

    before = build_point_in_time_evidence("TESTA", [original, amended], policy("2026-01-23T15:00:00Z"))
    rebuilt = build_point_in_time_evidence("TESTA", [amended, original], policy("2026-01-23T15:00:00Z"))
    after = build_point_in_time_evidence("TESTA", [original, amended], policy("2026-01-30T15:00:00Z"))

    assert before.observations == (original,)
    assert rebuilt.bundle_hash == before.bundle_hash
    assert canonical_json_bytes(rebuilt) == canonical_json_bytes(before)
    assert len(after.observations) == 2
    assert len(after.revision_relationships) == 1
    assert after.revision_relationships[0].status == "AMENDED"
    assert EvidenceDiagnosticCode.EVIDENCE_SEC_FILING_AMENDMENT_AVAILABLE in codes(after)


def test_policy_can_require_missing_sec_domain_without_input() -> None:
    bundle = build_point_in_time_evidence("TESTA", [], policy("2026-01-23T15:00:00Z"))
    assert coverage(bundle).state is CoverageState.MISSING
    assert EvidenceDiagnosticCode.EVIDENCE_MISSING_SEC_FILINGS in codes(bundle)
