"""Bounded canonical statistic and exchange registries for Cboe options evidence."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import (
    CboeExchangeCode,
    CoverageScope,
    ExchangeGroupCode,
    ExchangeScope,
    MarketScope,
    OptionsStatisticFamily,
    ProductScope,
)


@dataclass(frozen=True, slots=True)
class StatisticRegistryEntry:
    canonical_statistic_id: str
    statistic_family: OptionsStatisticFamily
    metric: str
    product_scope: ProductScope
    exchange_scope: ExchangeScope
    market_scope: MarketScope
    coverage_scope: CoverageScope
    unit: str
    tier: int = 1
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ExchangeRegistryEntry:
    exchange_code: CboeExchangeCode
    exchange_scope: ExchangeScope
    display_name: str
    symbol_data_mkt_param: str
    reference_cdn_prefix: str


@dataclass(frozen=True, slots=True)
class ExchangeGroupRegistryEntry:
    exchange_group: ExchangeGroupCode
    source_labels: tuple[str, ...]
    notes: str = ""


CBOE_EXCHANGE_REGISTRY: dict[CboeExchangeCode, ExchangeRegistryEntry] = {
    CboeExchangeCode.C1: ExchangeRegistryEntry(
        exchange_code=CboeExchangeCode.C1,
        exchange_scope=ExchangeScope.CBOE_OPTIONS,
        display_name="Cboe Options",
        symbol_data_mkt_param="cone",
        reference_cdn_prefix="cone",
    ),
    CboeExchangeCode.BZX: ExchangeRegistryEntry(
        exchange_code=CboeExchangeCode.BZX,
        exchange_scope=ExchangeScope.BZX_OPTIONS,
        display_name="BZX Options",
        symbol_data_mkt_param="opt",
        reference_cdn_prefix="opt",
    ),
    CboeExchangeCode.C2: ExchangeRegistryEntry(
        exchange_code=CboeExchangeCode.C2,
        exchange_scope=ExchangeScope.C2_OPTIONS,
        display_name="C2 Options",
        symbol_data_mkt_param="ctwo",
        reference_cdn_prefix="ctwo",
    ),
    CboeExchangeCode.EDGX: ExchangeRegistryEntry(
        exchange_code=CboeExchangeCode.EDGX,
        exchange_scope=ExchangeScope.EDGX_OPTIONS,
        display_name="EDGX Options",
        symbol_data_mkt_param="exo",
        reference_cdn_prefix="exo",
    ),
}


EXCHANGE_GROUP_REGISTRY: dict[ExchangeGroupCode, ExchangeGroupRegistryEntry] = {
    ExchangeGroupCode.CBOE_GROUP: ExchangeGroupRegistryEntry(
        exchange_group=ExchangeGroupCode.CBOE_GROUP,
        source_labels=("Cboe", "CBOE", "Cboe Group", "CBOE Group"),
        notes="Cboe options exchange family aggregate — not a single venue",
    ),
    ExchangeGroupCode.NASDAQ_GROUP: ExchangeGroupRegistryEntry(
        exchange_group=ExchangeGroupCode.NASDAQ_GROUP,
        source_labels=("Nasdaq", "NASDAQ", "Nasdaq PHLX"),
    ),
    ExchangeGroupCode.NYSE_GROUP: ExchangeGroupRegistryEntry(
        exchange_group=ExchangeGroupCode.NYSE_GROUP,
        source_labels=("NYSE", "NYSE American", "NYSE Arca"),
    ),
    ExchangeGroupCode.MIAX_GROUP: ExchangeGroupRegistryEntry(
        exchange_group=ExchangeGroupCode.MIAX_GROUP,
        source_labels=("MIAX", "Miami International"),
    ),
    ExchangeGroupCode.BOX: ExchangeGroupRegistryEntry(
        exchange_group=ExchangeGroupCode.BOX,
        source_labels=("BOX", "Boston Options Exchange"),
    ),
    ExchangeGroupCode.MEMX: ExchangeGroupRegistryEntry(
        exchange_group=ExchangeGroupCode.MEMX,
        source_labels=("MEMX",),
    ),
    ExchangeGroupCode.ALL_MARKET: ExchangeGroupRegistryEntry(
        exchange_group=ExchangeGroupCode.ALL_MARKET,
        source_labels=("Total", "All Market", "Total Market", "All Exchanges"),
    ),
}


STATISTIC_REGISTRY: dict[str, StatisticRegistryEntry] = {
    "TOTAL_PUT_CALL_RATIO": StatisticRegistryEntry(
        canonical_statistic_id="TOTAL_PUT_CALL_RATIO",
        statistic_family=OptionsStatisticFamily.PUT_CALL_RATIO,
        metric="PUT_CALL_RATIO",
        product_scope=ProductScope.TOTAL,
        exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        unit="ratio",
        notes="Put/call ratio is activity mix — not direction",
    ),
    "INDEX_PUT_CALL_RATIO": StatisticRegistryEntry(
        canonical_statistic_id="INDEX_PUT_CALL_RATIO",
        statistic_family=OptionsStatisticFamily.PUT_CALL_RATIO,
        metric="PUT_CALL_RATIO",
        product_scope=ProductScope.INDEX,
        exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        unit="ratio",
    ),
    "ETP_PUT_CALL_RATIO": StatisticRegistryEntry(
        canonical_statistic_id="ETP_PUT_CALL_RATIO",
        statistic_family=OptionsStatisticFamily.PUT_CALL_RATIO,
        metric="PUT_CALL_RATIO",
        product_scope=ProductScope.EXCHANGE_TRADED_PRODUCT,
        exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        unit="ratio",
    ),
    "EQUITY_PUT_CALL_RATIO": StatisticRegistryEntry(
        canonical_statistic_id="EQUITY_PUT_CALL_RATIO",
        statistic_family=OptionsStatisticFamily.PUT_CALL_RATIO,
        metric="PUT_CALL_RATIO",
        product_scope=ProductScope.EQUITY,
        exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        unit="ratio",
    ),
    "VIX_OPTIONS_PUT_CALL_RATIO": StatisticRegistryEntry(
        canonical_statistic_id="VIX_OPTIONS_PUT_CALL_RATIO",
        statistic_family=OptionsStatisticFamily.PUT_CALL_RATIO,
        metric="PUT_CALL_RATIO",
        product_scope=ProductScope.VIX,
        exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        unit="ratio",
        notes="VIX options activity — not VIX index level",
    ),
    "SPX_SPXW_PUT_CALL_RATIO": StatisticRegistryEntry(
        canonical_statistic_id="SPX_SPXW_PUT_CALL_RATIO",
        statistic_family=OptionsStatisticFamily.PUT_CALL_RATIO,
        metric="PUT_CALL_RATIO",
        product_scope=ProductScope.SPX_SPXW,
        exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        unit="ratio",
    ),
    "TOTAL_CALL_VOLUME": StatisticRegistryEntry(
        canonical_statistic_id="TOTAL_CALL_VOLUME",
        statistic_family=OptionsStatisticFamily.OPTION_VOLUME,
        metric="CALL_VOLUME",
        product_scope=ProductScope.TOTAL,
        exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        unit="contracts",
    ),
    "TOTAL_PUT_VOLUME": StatisticRegistryEntry(
        canonical_statistic_id="TOTAL_PUT_VOLUME",
        statistic_family=OptionsStatisticFamily.OPTION_VOLUME,
        metric="PUT_VOLUME",
        product_scope=ProductScope.TOTAL,
        exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        unit="contracts",
    ),
    "TOTAL_OPEN_INTEREST": StatisticRegistryEntry(
        canonical_statistic_id="TOTAL_OPEN_INTEREST",
        statistic_family=OptionsStatisticFamily.OPEN_INTEREST,
        metric="TOTAL_OPEN_INTEREST",
        product_scope=ProductScope.TOTAL,
        exchange_scope=ExchangeScope.ALL_CBOE_EXCHANGES,
        market_scope=MarketScope.CBOE_EXCHANGES,
        coverage_scope=CoverageScope.CBOE_EXCHANGES,
        unit="contracts",
        notes="Open interest is outstanding contracts — not period volume",
    ),
    "US_OPTIONS_TOTAL_MATCHED_VOLUME": StatisticRegistryEntry(
        canonical_statistic_id="US_OPTIONS_TOTAL_MATCHED_VOLUME",
        statistic_family=OptionsStatisticFamily.MATCHED_VOLUME,
        metric="MATCHED_VOLUME",
        product_scope=ProductScope.TOTAL,
        exchange_scope=ExchangeScope.UNSPECIFIED,
        market_scope=MarketScope.US_OPTIONS_MARKET,
        coverage_scope=CoverageScope.US_OPTIONS_MARKET,
        unit="contracts",
        notes="Publisher CBOE — market-wide matched volume",
    ),
    "CBOE_GROUP_MATCHED_VOLUME": StatisticRegistryEntry(
        canonical_statistic_id="CBOE_GROUP_MATCHED_VOLUME",
        statistic_family=OptionsStatisticFamily.MATCHED_VOLUME,
        metric="MATCHED_VOLUME",
        product_scope=ProductScope.TOTAL,
        exchange_scope=ExchangeScope.CBOE_GROUP,
        market_scope=MarketScope.US_OPTIONS_MARKET,
        coverage_scope=CoverageScope.US_OPTIONS_MARKET,
        unit="contracts",
    ),
    "CBOE_GROUP_MARKET_SHARE": StatisticRegistryEntry(
        canonical_statistic_id="CBOE_GROUP_MARKET_SHARE",
        statistic_family=OptionsStatisticFamily.MARKET_SHARE,
        metric="MARKET_SHARE",
        product_scope=ProductScope.TOTAL,
        exchange_scope=ExchangeScope.CBOE_GROUP,
        market_scope=MarketScope.US_OPTIONS_MARKET,
        coverage_scope=CoverageScope.US_OPTIONS_MARKET,
        unit="fraction",
    ),
}


PRODUCT_NAME_ALIASES: dict[str, ProductScope] = {
    "TOTAL": ProductScope.TOTAL,
    "SUM OF ALL PRODUCTS": ProductScope.TOTAL,
    "INDEX": ProductScope.INDEX,
    "INDEX OPTIONS": ProductScope.INDEX,
    "EXCHANGE TRADED PRODUCTS": ProductScope.EXCHANGE_TRADED_PRODUCT,
    "EQUITY": ProductScope.EQUITY,
    "EQUITY OPTIONS": ProductScope.EQUITY,
    "CBOE VOLATILITY INDEX (VIX)": ProductScope.VIX,
    "VIX": ProductScope.VIX,
    "SPX + SPXW": ProductScope.SPX_SPXW,
    "SPX+SPXW": ProductScope.SPX_SPXW,
}


RATIO_PRODUCT_TO_CANONICAL: dict[ProductScope, str] = {
    ProductScope.TOTAL: "TOTAL_PUT_CALL_RATIO",
    ProductScope.INDEX: "INDEX_PUT_CALL_RATIO",
    ProductScope.EXCHANGE_TRADED_PRODUCT: "ETP_PUT_CALL_RATIO",
    ProductScope.EQUITY: "EQUITY_PUT_CALL_RATIO",
    ProductScope.VIX: "VIX_OPTIONS_PUT_CALL_RATIO",
    ProductScope.SPX_SPXW: "SPX_SPXW_PUT_CALL_RATIO",
}


def resolve_exchange_group(label: str) -> ExchangeGroupCode | None:
    normalized = label.strip()
    lowered = normalized.lower()
    for entry in EXCHANGE_GROUP_REGISTRY.values():
        if normalized in entry.source_labels:
            return entry.exchange_group
        if any(normalized.lower() == candidate.lower() for candidate in entry.source_labels):
            return entry.exchange_group
        if any(candidate.lower() in lowered for candidate in entry.source_labels if len(candidate) >= 4):
            return entry.exchange_group
    return None


def resolve_product_scope(label: str) -> ProductScope:
    key = label.strip().upper()
    if key in PRODUCT_NAME_ALIASES:
        return PRODUCT_NAME_ALIASES[key]
    for alias, scope in PRODUCT_NAME_ALIASES.items():
        if alias.upper() == key:
            return scope
    return ProductScope.OTHER


def registry_entry(statistic_id: str) -> StatisticRegistryEntry | None:
    return STATISTIC_REGISTRY.get(statistic_id)


__all__ = [
    "CBOE_EXCHANGE_REGISTRY",
    "EXCHANGE_GROUP_REGISTRY",
    "ExchangeGroupRegistryEntry",
    "ExchangeRegistryEntry",
    "PRODUCT_NAME_ALIASES",
    "RATIO_PRODUCT_TO_CANONICAL",
    "STATISTIC_REGISTRY",
    "StatisticRegistryEntry",
    "registry_entry",
    "resolve_exchange_group",
    "resolve_product_scope",
]
