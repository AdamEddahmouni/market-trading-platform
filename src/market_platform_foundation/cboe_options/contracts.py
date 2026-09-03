"""Provider-neutral Cboe public options statistics evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class OptionsStatisticFamily(StrEnum):
    PUT_CALL_RATIO = "PUT_CALL_RATIO"
    OPTION_VOLUME = "OPTION_VOLUME"
    OPEN_INTEREST = "OPEN_INTEREST"
    MARKET_SHARE = "MARKET_SHARE"
    MATCHED_VOLUME = "MATCHED_VOLUME"
    INTRADAY_CUMULATIVE = "INTRADAY_CUMULATIVE"
    INTRADAY_INTERVAL = "INTRADAY_INTERVAL"
    HISTORICAL_VOLUME = "HISTORICAL_VOLUME"


class ProductScope(StrEnum):
    TOTAL = "TOTAL"
    INDEX = "INDEX"
    EXCHANGE_TRADED_PRODUCT = "EXCHANGE_TRADED_PRODUCT"
    EQUITY = "EQUITY"
    VIX = "VIX"
    SPX_SPXW = "SPX_SPXW"
    OTHER = "OTHER"


class ExchangeScope(StrEnum):
    CBOE_OPTIONS = "CBOE_OPTIONS"
    BZX_OPTIONS = "BZX_OPTIONS"
    C2_OPTIONS = "C2_OPTIONS"
    EDGX_OPTIONS = "EDGX_OPTIONS"
    CBOE_GROUP = "CBOE_GROUP"
    ALL_CBOE_EXCHANGES = "ALL_CBOE_EXCHANGES"
    UNSPECIFIED = "UNSPECIFIED"


class MarketScope(StrEnum):
    CBOE_EXCHANGES = "CBOE_EXCHANGES"
    US_OPTIONS_MARKET = "US_OPTIONS_MARKET"
    EXCHANGE_SPECIFIC = "EXCHANGE_SPECIFIC"
    UNSPECIFIED = "UNSPECIFIED"


class CoverageScope(StrEnum):
    CBOE_EXCHANGES = "CBOE_EXCHANGES"
    US_OPTIONS_MARKET = "US_OPTIONS_MARKET"
    EXCHANGE_SPECIFIC = "EXCHANGE_SPECIFIC"
    COVERAGE_SCOPE_UNCERTAIN = "COVERAGE_SCOPE_UNCERTAIN"


class AvailabilityPrecision(StrEnum):
    TIMESTAMP = "TIMESTAMP"
    DATE_ONLY = "DATE_ONLY"
    HTTP_LAST_MODIFIED_PROXY = "HTTP_LAST_MODIFIED_PROXY"
    FIRST_OBSERVED = "FIRST_OBSERVED"
    DELAY_POLICY_BOUND = "DELAY_POLICY_BOUND"
    UNKNOWN = "UNKNOWN"


class PitHistoryClass(StrEnum):
    PROSPECTIVE_VERSIONED_PIT = "PROSPECTIVE_VERSIONED_PIT"
    HISTORICAL_SOURCE_TIMESTAMP_AVAILABLE = "HISTORICAL_SOURCE_TIMESTAMP_AVAILABLE"
    HISTORICAL_AVAILABILITY_INFERRED = "HISTORICAL_AVAILABILITY_INFERRED"
    HISTORICAL_PUBLICATION_TIME_UNKNOWN = "HISTORICAL_PUBLICATION_TIME_UNKNOWN"
    CURRENT_SNAPSHOT_ONLY = "CURRENT_SNAPSHOT_ONLY"
    CHARACTERIZED_ONLY = "CHARACTERIZED_ONLY"


class OptionsFeatureLayer(StrEnum):
    RAW = "RAW"
    NORMALIZED = "NORMALIZED"
    DETERMINISTIC_DERIVED = "DETERMINISTIC_DERIVED"
    PREDICTIVE_NOT_VALIDATED = "PREDICTIVE_NOT_VALIDATED"


class CboeExchangeCode(StrEnum):
    C1 = "C1"
    BZX = "BZX"
    C2 = "C2"
    EDGX = "EDGX"


class ExchangeGroupCode(StrEnum):
    CBOE_GROUP = "CBOE_GROUP"
    NASDAQ_GROUP = "NASDAQ_GROUP"
    NYSE_GROUP = "NYSE_GROUP"
    MIAX_GROUP = "MIAX_GROUP"
    BOX = "BOX"
    MEMX = "MEMX"
    ALL_MARKET = "ALL_MARKET"


class RatioReconciliationStatus(StrEnum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNDEFINED_DENOMINATOR = "UNDEFINED_DENOMINATOR"
    SOURCE_ONLY = "SOURCE_ONLY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class OptionsMarketStatisticObservation:
    """Aggregate options activity — not signed flow or directional evidence."""

    canonical_statistic_id: str
    statistic_family: OptionsStatisticFamily
    metric: str
    product_scope: ProductScope
    exchange_scope: ExchangeScope
    market_scope: MarketScope
    coverage_scope: CoverageScope
    trade_date: str
    source_value: float | None
    normalized_value: float | None
    unit: str
    available_time: str
    availability_precision: AvailabilityPrecision
    retrieved_time: str
    ingested_time: str
    content_hash: str
    publisher: str = "CBOE"
    reported_exchange_group: ExchangeGroupCode | None = None
    bucket_start: str = ""
    bucket_end: str = ""
    call_value: int | None = None
    put_value: int | None = None
    total_value: int | None = None
    source_ratio: float | None = None
    derived_ratio: float | None = None
    ratio_reconciliation_status: RatioReconciliationStatus = RatioReconciliationStatus.NOT_APPLICABLE
    source_data_as_of_time: str = ""
    provider_first_observed_time: str = ""
    source_artifact_id: str = ""
    source_delay_policy: str = ""
    feature_layer: OptionsFeatureLayer = OptionsFeatureLayer.RAW
    history_class: PitHistoryClass = PitHistoryClass.PROSPECTIVE_VERSIONED_PIT
    timezone: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    lifecycle: str = "OBSERVED"
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class OptionContractActivitySnapshot:
    """Exchange-specific contract activity — not consolidated OPRA or NBBO."""

    contract_id: str
    exchange: CboeExchangeCode
    snapshot_time: str
    available_time: str
    coverage_scope: CoverageScope
    underlying: str
    expiration_date: str
    strike: str
    option_type: str
    volume: int | None = None
    matched: int | None = None
    routed: int | None = None
    exchange_bid: float | None = None
    exchange_ask: float | None = None
    exchange_bid_size: int | None = None
    exchange_ask_size: int | None = None
    last_price: float | None = None
    source_symbol: str = ""
    style: str = ""
    retrieved_time: str = ""
    ingested_time: str = ""
    content_hash: str = ""
    history_class: PitHistoryClass = PitHistoryClass.CURRENT_SNAPSHOT_ONLY
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    lifecycle: str = "OBSERVED"
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class OptionsReferenceFileObservation:
    """Reference CSV versioning — identity/eligibility, not trading activity."""

    reference_category: str
    exchange: CboeExchangeCode
    source_file_id: str
    source_url: str
    schema_version: str
    row_count: int
    headers: tuple[str, ...]
    content_hash: str
    available_time: str
    availability_precision: AvailabilityPrecision
    retrieved_time: str
    ingested_time: str
    http_last_modified: str = ""
    provider_first_observed_time: str = ""
    source_url_version: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    lifecycle: str = "OBSERVED"
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class OptionsAggregateContext:
    """Bounded options market activity context — no score or direction."""

    decision_time: str
    put_call_activity: tuple[OptionsMarketStatisticObservation, ...] = field(default_factory=tuple)
    volume_activity: tuple[OptionsMarketStatisticObservation, ...] = field(default_factory=tuple)
    open_interest_context: tuple[OptionsMarketStatisticObservation, ...] = field(default_factory=tuple)
    market_share: tuple[OptionsMarketStatisticObservation, ...] = field(default_factory=tuple)
    exchange_intraday_activity: tuple[OptionsMarketStatisticObservation, ...] = field(default_factory=tuple)
    contract_activity_snapshot: tuple[OptionContractActivitySnapshot, ...] = field(default_factory=tuple)
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    staleness: dict[str, str | None] = field(default_factory=dict)
    provenance_ref: str = ""
    predictive: bool = False


def _enum_values(data: dict[str, Any], *names: str) -> None:
    for name in names:
        value = data.get(name)
        if value is not None and hasattr(value, "value"):
            data[name] = value.value


def market_statistic_to_dict(obs: OptionsMarketStatisticObservation) -> dict[str, Any]:
    data = {name: getattr(obs, name) for name in obs.__dataclass_fields__}
    _enum_values(
        data,
        "statistic_family",
        "product_scope",
        "exchange_scope",
        "market_scope",
        "coverage_scope",
        "availability_precision",
        "reported_exchange_group",
        "ratio_reconciliation_status",
        "feature_layer",
        "history_class",
    )
    data["quality_flags"] = list(obs.quality_flags)
    return data


def contract_snapshot_to_dict(obs: OptionContractActivitySnapshot) -> dict[str, Any]:
    data = {name: getattr(obs, name) for name in obs.__dataclass_fields__}
    _enum_values(data, "exchange", "coverage_scope", "history_class")
    data["quality_flags"] = list(obs.quality_flags)
    return data


def reference_file_to_dict(obs: OptionsReferenceFileObservation) -> dict[str, Any]:
    data = {name: getattr(obs, name) for name in obs.__dataclass_fields__}
    _enum_values(data, "exchange", "availability_precision")
    data["headers"] = list(obs.headers)
    data["quality_flags"] = list(obs.quality_flags)
    return data


def aggregate_context_to_dict(ctx: OptionsAggregateContext) -> dict[str, Any]:
    return {
        "decision_time": ctx.decision_time,
        "put_call_activity": [market_statistic_to_dict(obs) for obs in ctx.put_call_activity],
        "volume_activity": [market_statistic_to_dict(obs) for obs in ctx.volume_activity],
        "open_interest_context": [market_statistic_to_dict(obs) for obs in ctx.open_interest_context],
        "market_share": [market_statistic_to_dict(obs) for obs in ctx.market_share],
        "exchange_intraday_activity": [
            market_statistic_to_dict(obs) for obs in ctx.exchange_intraday_activity
        ],
        "contract_activity_snapshot": [
            contract_snapshot_to_dict(obs) for obs in ctx.contract_activity_snapshot
        ],
        "quality_flags": list(ctx.quality_flags),
        "staleness": dict(ctx.staleness),
        "provenance_ref": ctx.provenance_ref,
        "predictive": ctx.predictive,
    }


__all__ = [
    "AvailabilityPrecision",
    "CboeExchangeCode",
    "CoverageScope",
    "ExchangeGroupCode",
    "ExchangeScope",
    "MarketScope",
    "OptionContractActivitySnapshot",
    "OptionsAggregateContext",
    "OptionsFeatureLayer",
    "OptionsMarketStatisticObservation",
    "OptionsReferenceFileObservation",
    "OptionsStatisticFamily",
    "PitHistoryClass",
    "ProductScope",
    "RatioReconciliationStatus",
    "aggregate_context_to_dict",
    "contract_snapshot_to_dict",
    "market_statistic_to_dict",
    "reference_file_to_dict",
]
