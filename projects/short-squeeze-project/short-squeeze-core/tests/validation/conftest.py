from datetime import UTC, datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.finra import normalize_finra_short_interest_records
from squeeze_core.adapters.ibkr import normalize_ibkr_borrow_records
from squeeze_core.adapters.market_bars import normalize_market_bar_record
from squeeze_core.adapters.sec import normalize_sec_filing_record
from squeeze_core.contracts import EntitlementState, EventType, IngestionMethod, Observation
from squeeze_core.validation import (
    ArtifactAvailability,
    ArtifactReliabilityClass,
    OriginalFieldValue,
    OriginalValueState,
    ValidationArtifact,
)

# The two real BIYA detection bounds, as UTC instants. America/New_York on 2026-07-17
# is UTC-4, so 10:23:58 local is 14:23:58Z and 12:54:58 local is 16:54:58Z.
BIYA_WINDOW_START = datetime(2026, 7, 17, 14, 23, 58, tzinfo=UTC)
BIYA_WINDOW_END = datetime(2026, 7, 17, 16, 54, 58, tzinfo=UTC)
BIYA_MEETING_START = datetime(2026, 7, 17, 16, 46, 15, tzinfo=UTC)


def artifact(
    artifact_id: str = "ART-TEST",
    *,
    artifact_type: str = "APPLICATION_LOG",
    relative_path: str = "app/logs/app.log",
    reliability_class: ArtifactReliabilityClass = ArtifactReliabilityClass.DIRECT_PLATFORM_RECORD,
    **overrides: object,
) -> ValidationArtifact:
    values: dict[str, object] = {
        "artifact_id": artifact_id,
        "artifact_type": artifact_type,
        "repository_or_source": "test-repo",
        "relative_path": relative_path,
        "reliability_class": reliability_class,
    }
    values.update(overrides)
    return ValidationArtifact(**values)  # type: ignore[arg-type]


def biya_log_artifact(**overrides: object) -> ValidationArtifact:
    """ART-001: the only direct platform record, carrying no embedded event time."""

    values: dict[str, object] = {
        "artifact_id": "ART-001",
        "content_hash": "sha256:9cbd7d0c88956e6ce8350078ca9c4f6f029a3045655d5c6069a00c4821d66129",
        "created_time_if_known": BIYA_WINDOW_START,
        "modified_time_if_known": BIYA_WINDOW_END,
        "timezone_if_known": "America/New_York",
        "sensitive": True,
    }
    values.update(overrides)
    return artifact(**values)  # type: ignore[arg-type]


def biya_meeting_artifact(**overrides: object) -> ValidationArtifact:
    values: dict[str, object] = {
        "artifact_id": "ART-002",
        "artifact_type": "MEETING_TRANSCRIPT",
        "relative_path": "advisor-meetings.txt",
        "reliability_class": ArtifactReliabilityClass.DERIVED_FROM_PLATFORM_RECORD,
        "embedded_event_time_if_known": BIYA_MEETING_START,
        "timezone_if_known": "America/New_York",
        "sensitive": True,
    }
    values.update(overrides)
    return artifact(**values)  # type: ignore[arg-type]


def unavailable_artifact(
    artifact_id: str, availability: ArtifactAvailability
) -> ValidationArtifact:
    return artifact(artifact_id, availability=availability)


def recovered_field(
    field_id: str = "price",
    value: object = "4.20",
    **overrides: object,
) -> OriginalFieldValue:
    values: dict[str, object] = {
        "field_id": field_id,
        "state": OriginalValueState.RECOVERED,
        "value": value,
    }
    values.update(overrides)
    return OriginalFieldValue(**values)  # type: ignore[arg-type]


# --- Observation factories for replay tests -------------------------------------
# Defined here rather than imported from tests/readiness because `tests` is not a
# package, so a cross-suite relative import is not available. Kept deliberately
# minimal: replay tests need real point-in-time behaviour, not broad coverage.


def _context(at: str, provider: str) -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone="UTC",
        provider=provider,
        adapter_version="1.0.0",
        normalization_version="phase-2v-fixture-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2v-synthetic-fixture",
    )


def make_short_interest(**overrides: object) -> Observation:
    record = {
        "source_record_id": "si-1",
        "provider_schema": "FINRA_SHORT_INTEREST_V1",
        "record_type": "PUBLISHED_SHORT_INTEREST",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "symbol": "TESTD",
        "short_shares": "1000000",
        "settlement_date": "2026-01-15",
        "publication_date": "2026-01-25",
        "publication_timezone": "UTC",
        "date_only_publication_policy": "END_OF_PUBLICATION_DATE",
        "float_shares": "10000000",
        "short_float_percent": "10",
        "short_float_percent_unit": "PERCENT_POINTS",
        "days_to_cover": "2.5",
    }
    record.update(overrides)  # type: ignore[arg-type]
    result = normalize_finra_short_interest_records(
        [record], _context("2026-01-26T00:00:00Z", "finra-validation-fixture")
    )
    assert result.accepted, result.rejection
    return result.observations[0]


def make_bar(**overrides: object) -> Observation:
    record = {
        "source_record_id": "bar-1",
        "provider_schema": "MARKET_BAR_V1",
        "record_type": "MARKET_BAR",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "provider": "SIM-VOLUME-PROVIDER",
        "provider_record_id": None,
        "symbol": "TESTD",
        "asset_class": "EQUITY",
        "exchange": "XNAS",
        "interval": "1_DAY",
        "bar_start": "2026-02-10T00:00:00Z",
        "bar_end": "2026-02-11T00:00:00Z",
        "open": "10.00",
        "high": "11.00",
        "low": "9.00",
        "close": "10.50",
        "volume": "500000",
        "trade_count": "500",
        "vwap": "10.00",
        "volume_unit": "SHARES",
        "session": "REGULAR",
        "session_date": "2026-02-10",
        "timezone": "UTC",
        "status": "COMPLETED",
        "publication_timestamp": "2026-02-10T20:01:00Z",
    }
    record.update(overrides)  # type: ignore[arg-type]
    result = normalize_market_bar_record(
        record, _context("2026-02-10T21:02:00Z", "SIM-VOLUME-PROVIDER")
    )
    assert result.accepted, result.rejection
    return result.observations[0]


def make_borrow(**overrides: object) -> tuple[Observation, Observation]:
    record = {
        "source_record_id": "ib-1",
        "symbol": "TESTD",
        "fee_rate": "5.0",
        "fee_rate_unit": "PERCENT_POINTS",
        "available_shares": "100000",
        "lender_count": "10",
        "hard_to_borrow": False,
        "provider_timestamp": "2026-01-10T00:00:00Z",
        "provider_timezone": "UTC",
        "delay_status": "NOT_DELAYED",
    }
    record.update(overrides)  # type: ignore[arg-type]
    result = normalize_ibkr_borrow_records(
        [record], _context("2026-01-11T00:00:00Z", "ibkr-validation-fixture")
    )
    assert result.accepted, result.rejection
    fee = next(o for o in result.observations if o.event_type is EventType.BORROW_FEE)
    availability = next(
        o for o in result.observations if o.event_type is EventType.BORROW_AVAILABILITY
    )
    return fee, availability


def make_sec_filing(**overrides: object) -> Observation:
    record = {
        "source_record_id": "sec-1",
        "provider_schema": "SEC_FILING_V1",
        "record_type": "SEC_FILING",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "symbol": "TESTD",
        "issuer_cik": "1",
        "company_name": "Test D Corp.",
        "form_type": "10-Q",
        "accession_number": "0000000001-26-000001",
        "filed_at": "2026-01-20",
        "accepted_at": "2026-01-20T14:30:00Z",
        "period_of_report": "2026-01-15",
        "primary_document": "testd-20260115x10q.htm",
        "is_amendment": False,
        "document_count": "3",
        "file_number": "001-00001",
        "filing_status": "ORIGINAL",
    }
    record.update(overrides)  # type: ignore[arg-type]
    result = normalize_sec_filing_record(
        record, _context("2026-01-20T15:00:00Z", "sec-validation-fixture")
    )
    assert result.accepted, result.rejection
    return result.observations[0]
