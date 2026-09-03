from datetime import datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.finra import normalize_finra_short_interest_records
from squeeze_core.adapters.ibkr import normalize_ibkr_borrow_records
from squeeze_core.adapters.market_bars import normalize_market_bar_record
from squeeze_core.adapters.sec import normalize_sec_filing_record
from squeeze_core.contracts import EntitlementState, EventType, IngestionMethod, Observation
from squeeze_core.evidence import PointInTimeEvidencePolicy, build_point_in_time_evidence


def context(
    at: str = "2026-01-20T22:00:00Z", provider: str = "readiness-offline"
) -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone="UTC",
        provider=provider,
        adapter_version="1.0.0",
        normalization_version="phase-2d-fixture-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2d-synthetic-fixture",
    )


def si_record(**overrides: object) -> dict:
    values = {
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
    values.update(overrides)
    return values


def make_short_interest(
    *, ingested_at: str = "2026-01-26T00:00:00Z", provider: str = "finra-readiness-fixture", **overrides: object
) -> Observation:
    result = normalize_finra_short_interest_records(
        [si_record(**overrides)], context(at=ingested_at, provider=provider)
    )
    assert result.accepted, result.rejection
    return result.observations[0]


def borrow_record(**overrides: object) -> dict:
    values = {
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
    values.update(overrides)
    return values


def make_borrow(
    *, ingested_at: str = "2026-01-11T00:00:00Z", provider: str = "ibkr-readiness-fixture", **overrides: object
) -> tuple[Observation, Observation]:
    """Returns (fee_observation, availability_observation) -- IBKR normalization
    always emits both event types from one borrow record."""

    result = normalize_ibkr_borrow_records(
        [borrow_record(**overrides)], context(at=ingested_at, provider=provider)
    )
    assert result.accepted, result.rejection
    fee = next(o for o in result.observations if o.event_type is EventType.BORROW_FEE)
    availability = next(
        o for o in result.observations if o.event_type is EventType.BORROW_AVAILABILITY
    )
    return fee, availability


def bar_record(**overrides: object) -> dict:
    values = {
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
    values.update(overrides)
    return values


def make_bar(
    *, ingested_at: str = "2026-02-10T21:02:00Z", provider: str = "SIM-VOLUME-PROVIDER", **overrides: object
) -> Observation:
    result = normalize_market_bar_record(bar_record(**overrides), context(at=ingested_at, provider=provider))
    assert result.accepted, result.rejection
    return result.observations[0]


def sec_record(**overrides: object) -> dict:
    values = {
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
    values.update(overrides)
    return values


def make_sec_filing(
    *, ingested_at: str = "2026-01-20T15:00:00Z", provider: str = "sec-readiness-fixture", **overrides: object
) -> Observation:
    result = normalize_sec_filing_record(sec_record(**overrides), context(at=ingested_at, provider=provider))
    assert result.accepted, result.rejection
    return result.observations[0]


def build_bundle(
    symbol: str,
    observations: list[Observation],
    as_of: str,
    **policy_overrides: object,
):
    as_of_dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
    values = dict(allow_stale=True, allow_delayed=True, allow_unknown_freshness=True)
    values.update(policy_overrides)
    policy = PointInTimeEvidencePolicy(as_of=as_of_dt, **values)
    return build_point_in_time_evidence(symbol, observations, policy)
