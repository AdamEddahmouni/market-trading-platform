from datetime import UTC, datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.finra import normalize_finra_short_interest_record
from squeeze_core.contracts import EntitlementState, IngestionMethod
from squeeze_core.evidence import (
    CoverageDomain,
    CoverageState,
    EvidenceDiagnosticCode,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)
from squeeze_core.serialization import canonical_json_bytes


def context(ingested_at: str) -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(ingested_at.replace("Z", "+00:00")),
        source_timezone=None,
        provider="finra-shaped-offline-fixture",
        adapter_version="1.0.0",
        normalization_version="finra-short-interest-v1",
        entitlement_status=EntitlementState.UNKNOWN,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="publication-timeline",
    )


def record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "testa-original",
        "provider_schema": "FINRA_SHORT_INTEREST_V1",
        "record_type": "PUBLISHED_SHORT_INTEREST",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "symbol": "TESTA",
        "short_shares": "2500000",
        "settlement_date": "2026-01-15",
        "publication_date": "2026-01-22T14:00:00-05:00",
        "days_to_cover": "2.5",
        "revision_status": "ORIGINAL",
    }
    value.update(overrides)
    return value


def normalize(raw: dict[str, object], received: str):
    result = normalize_finra_short_interest_record(raw, context(received))
    assert result.accepted and len(result.observations) == 1
    return result.observations[0]


def policy(as_of: str, **overrides: object) -> PointInTimeEvidencePolicy:
    values: dict[str, object] = {
        "as_of": datetime.fromisoformat(as_of.replace("Z", "+00:00")),
        "allow_stale": True,
        "allow_delayed": True,
        "allow_unknown_freshness": True,
    }
    values.update(overrides)
    return PointInTimeEvidencePolicy.model_validate(values)


def code_values(bundle) -> set[EvidenceDiagnosticCode]:
    return {item.code for item in bundle.diagnostics}


def coverage(bundle, domain: CoverageDomain):
    return next(item for item in bundle.source_coverage if item.domain is domain)


def test_settlement_before_as_of_does_not_make_unpublished_record_eligible() -> None:
    original = normalize(record(), "2026-01-22T20:00:00Z")
    bundle = build_point_in_time_evidence(
        "TESTA", [original], policy("2026-01-20T15:00:00Z")
    )

    assert bundle.observations == ()
    assert EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_NOT_YET_PUBLISHED in code_values(bundle)
    assert coverage(bundle, CoverageDomain.PUBLISHED_SHORT_INTEREST).state is CoverageState.MISSING


def test_publication_before_as_of_but_receipt_after_as_of_is_excluded() -> None:
    original = normalize(record(), "2026-01-22T22:00:00Z")
    bundle = build_point_in_time_evidence(
        "TESTA", [original], policy("2026-01-22T20:00:00Z")
    )

    assert bundle.observations == ()
    assert EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_NOT_YET_RECEIVED in code_values(bundle)


def test_publication_receipt_and_effective_before_as_of_are_eligible() -> None:
    original = normalize(record(), "2026-01-22T20:00:00Z")
    bundle = build_point_in_time_evidence(
        "TESTA", [original], policy("2026-01-25T15:30:00Z")
    )

    assert bundle.observations == (original,)
    assert coverage(bundle, CoverageDomain.PUBLISHED_SHORT_INTEREST).state is CoverageState.PRESENT
    assert bundle.observation_ages[0].observation_id == original.observation_id
    assert bundle.observation_ages[0].availability_age_ms == 243_000_000
    assert bundle.observation_ages[0].reporting_period_age_days == 10


def test_effective_timestamp_gate_remains_independent() -> None:
    original = normalize(record(), "2026-01-22T20:00:00Z")
    future_effective = original.model_copy(
        update={"effective_timestamp": datetime(2026, 1, 26, tzinfo=UTC)}
    )
    bundle = build_point_in_time_evidence(
        "TESTA", [future_effective], policy("2026-01-25T15:30:00Z")
    )

    assert bundle.observations == ()
    assert EvidenceDiagnosticCode.EVIDENCE_EXCLUDED_AFTER_AS_OF in code_values(bundle)


def test_later_correction_does_not_change_historical_bundle_membership() -> None:
    original = normalize(record(), "2026-01-22T20:00:00Z")
    correction = normalize(
        record(
            source_record_id="testa-correction",
            short_shares="2600000",
            publication_date="2026-01-29T14:00:00-05:00",
            revision_status="CORRECTED",
            revision_number=1,
            supersedes_source_record_id="testa-original",
        ),
        "2026-01-30T15:00:00Z",
    )

    before = build_point_in_time_evidence(
        "TESTA", [original, correction], policy("2026-01-25T15:30:00Z")
    )
    rebuilt = build_point_in_time_evidence(
        "TESTA", [correction, original], policy("2026-01-25T15:30:00Z")
    )
    after = build_point_in_time_evidence(
        "TESTA", [original, correction], policy("2026-02-01T15:30:00Z")
    )

    assert before.observations == (original,)
    assert rebuilt.bundle_hash == before.bundle_hash
    assert canonical_json_bytes(rebuilt) == canonical_json_bytes(before)
    assert after.observations == (original, correction)
    assert len(after.revision_relationships) == 1
    relationship = after.revision_relationships[0]
    assert relationship.prior_observation_id == original.observation_id
    assert relationship.revision_observation_id == correction.observation_id
    assert relationship.status == "CORRECTED"
    assert EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_REVISION_SUPERSEDES in code_values(after)


def test_newly_received_old_reporting_period_has_separate_ages() -> None:
    old = normalize(
        record(
            source_record_id="old-report",
            settlement_date="2025-12-31",
            publication_date="2026-01-30T14:00:00-05:00",
        ),
        "2026-01-30T20:00:00Z",
    )
    bundle = build_point_in_time_evidence(
        "TESTA", [old], policy("2026-01-30T21:00:00Z")
    )

    age = bundle.observation_ages[0]
    assert age.availability_age_ms == 3_600_000
    assert age.reporting_period_age_days == 30


def test_reporting_period_staleness_is_independent_of_availability_staleness() -> None:
    old = normalize(
        record(
            settlement_date="2025-12-31",
            publication_date="2026-01-30T19:00:00Z",
        ),
        "2026-01-30T20:00:00Z",
    )
    retained = build_point_in_time_evidence(
        "TESTA",
        [old],
        policy(
            "2026-01-30T21:00:00Z",
            maximum_reporting_period_age_days=20,
            allow_stale=True,
        ),
    )
    excluded = build_point_in_time_evidence(
        "TESTA",
        [old],
        policy(
            "2026-01-30T21:00:00Z",
            maximum_reporting_period_age_days=20,
            allow_stale=False,
        ),
    )

    assert coverage(retained, CoverageDomain.PUBLISHED_SHORT_INTEREST).state is CoverageState.STALE
    assert EvidenceDiagnosticCode.EVIDENCE_SHORT_INTEREST_STALE_REPORTING_PERIOD in code_values(retained)
    assert excluded.observations == ()


def test_policy_can_require_missing_short_interest_domain_without_any_input_record() -> None:
    bundle = build_point_in_time_evidence(
        "TESTA",
        [],
        policy(
            "2026-01-25T15:30:00Z",
            include_published_short_interest_domain=True,
        ),
    )

    assert coverage(bundle, CoverageDomain.PUBLISHED_SHORT_INTEREST).state is CoverageState.MISSING
    assert EvidenceDiagnosticCode.EVIDENCE_MISSING_PUBLISHED_SHORT_INTEREST in code_values(bundle)
