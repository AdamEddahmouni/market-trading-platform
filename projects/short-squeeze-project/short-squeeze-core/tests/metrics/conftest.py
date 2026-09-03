from datetime import datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.finra import normalize_finra_short_interest_records
from squeeze_core.adapters.ibkr import normalize_ibkr_borrow_record, normalize_ibkr_borrow_records
from squeeze_core.adapters.market_bars import normalize_market_bar_record
from squeeze_core.contracts import EntitlementState, EventType, IngestionMethod, Observation


def context(at: str = "2026-01-20T22:00:00Z", provider: str = "market-bars-offline") -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone=None,
        provider=provider,
        adapter_version="1.0.0",
        normalization_version="metrics-fixture-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2a-synthetic-fixture",
    )


def bar_record(**overrides) -> dict:
    values = {
        "source_record_id": "bar-1",
        "provider_schema": "MARKET_BAR_V1",
        "record_type": "MARKET_BAR",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "provider": "ALPACA_SHAPED",
        "provider_record_id": None,
        "symbol": "TESTA",
        "asset_class": "EQUITY",
        "exchange": "XNAS",
        "interval": "1_DAY",
        "bar_start": "2026-01-15T00:00:00-05:00",
        "bar_end": "2026-01-16T00:00:00-05:00",
        "open": "10.00",
        "high": "10.50",
        "low": "9.90",
        "close": "10.25",
        "volume": "100000",
        "trade_count": "500",
        "vwap": "10.20",
        "volume_unit": "SHARES",
        "session": "REGULAR",
        "session_date": "2026-01-15",
        "timezone": "America/New_York",
        "status": "COMPLETED",
        "publication_timestamp": "2026-01-15T16:01:00-05:00",
    }
    values.update(overrides)
    return values


def make_bar(
    *, ingested_at: str = "2026-01-20T22:00:00Z", context_provider: str = "market-bars-offline", **overrides
) -> Observation:
    result = normalize_market_bar_record(bar_record(**overrides), context(at=ingested_at, provider=context_provider))
    assert result.accepted, result.rejection
    return result.observations[0]


def bar_boundary(observation: Observation) -> tuple[datetime, datetime]:
    metadata = observation.provenance.provider_metadata
    return metadata["bar_start"], metadata["bar_end"]


def pressure_context(
    at: str = "2026-02-15T12:00:00Z", provider: str = "finra-provider-test"
) -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone="UTC",
        provider=provider,
        adapter_version="1.0.0",
        normalization_version="metrics-fixture-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2c-synthetic-fixture",
    )


def short_interest_record(**overrides) -> dict:
    values = {
        "source_record_id": "si-1",
        "provider_schema": "FINRA_SHORT_INTEREST_V1",
        "record_type": "PUBLISHED_SHORT_INTEREST",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "symbol": "TESTC",
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


def make_short_interest_records(
    records: list[dict], *, ingested_at: str = "2026-02-15T12:00:00Z", provider: str = "finra-provider-test"
) -> tuple[Observation, ...]:
    """Normalizes a batch through normalize_finra_short_interest_records so revision links
    (parent_observation_ids/correlation_id) are established across records."""

    result = normalize_finra_short_interest_records(records, pressure_context(at=ingested_at, provider=provider))
    assert result.accepted, result.rejection
    return result.observations


def make_short_interest(
    *, ingested_at: str = "2026-02-15T12:00:00Z", provider: str = "finra-provider-test", **overrides
) -> Observation:
    return make_short_interest_records([short_interest_record(**overrides)], ingested_at=ingested_at, provider=provider)[0]


def borrow_record(**overrides) -> dict:
    values = {
        "source_record_id": "ib-1",
        "symbol": "TESTC",
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


def make_borrow_observations(
    *, ingested_at: str = "2026-02-15T12:00:00Z", provider: str = "ibkr-provider-test", **overrides
) -> tuple[Observation, ...]:
    result = normalize_ibkr_borrow_record(borrow_record(**overrides), pressure_context(at=ingested_at, provider=provider))
    assert result.accepted, result.rejection
    return result.observations


def make_borrow_records(
    records: list[dict], *, ingested_at: str = "2026-02-15T12:00:00Z", provider: str = "ibkr-provider-test"
) -> tuple[Observation, ...]:
    """Normalizes a batch through normalize_ibkr_borrow_records so same-boundary conflicts are
    detected across records (single-record normalization never sees siblings)."""

    result = normalize_ibkr_borrow_records(records, pressure_context(at=ingested_at, provider=provider))
    assert result.accepted, result.rejection
    return result.observations


def make_borrow_fee(**kwargs) -> Observation:
    observations = make_borrow_observations(**kwargs)
    return next(obs for obs in observations if obs.event_type is EventType.BORROW_FEE)


def make_borrow_availability(**kwargs) -> Observation:
    observations = make_borrow_observations(**kwargs)
    return next(obs for obs in observations if obs.event_type is EventType.BORROW_AVAILABILITY)
