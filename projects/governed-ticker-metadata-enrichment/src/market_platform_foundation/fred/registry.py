"""Tier 1 canonical macro indicator registry — bounded, governed FRED mappings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .contracts import MacroDomain


@dataclass(frozen=True, slots=True)
class MacroRegistryEntry:
    canonical_indicator_id: str
    domain: MacroDomain
    fred_series_id: str
    title: str
    original_source: str
    frequency: str
    units: str
    seasonal_adjustment: str
    fred_release_id: int | None
    revision_sensitive: bool
    v1_pit_supported: bool
    v2_release_membership: bool
    copyright_id: str
    usage_rights: str
    inclusion_rationale: str
    valid_from: str = ""
    valid_to: str = ""
    replacement_series: str = ""


def _entry(
    canonical: str,
    domain: MacroDomain,
    series_id: str,
    title: str,
    source: str,
    frequency: str,
    units: str,
    sa: str,
    release_id: int | None,
    *,
    revision_sensitive: bool = True,
    v2: bool = True,
    copyright_id: str = "",
    rights: str = "internal_research",
    rationale: str = "",
) -> MacroRegistryEntry:
    return MacroRegistryEntry(
        canonical_indicator_id=canonical,
        domain=domain,
        fred_series_id=series_id,
        title=title,
        original_source=source,
        frequency=frequency,
        units=units,
        seasonal_adjustment=sa,
        fred_release_id=release_id,
        revision_sensitive=revision_sensitive,
        v1_pit_supported=True,
        v2_release_membership=v2,
        copyright_id=copyright_id,
        usage_rights=rights,
        inclusion_rationale=rationale or f"Tier 1 {domain.value.lower()} context",
    )


TIER1_REGISTRY: tuple[MacroRegistryEntry, ...] = (
    # Rates
    _entry("US_EFFECTIVE_FED_FUNDS_RATE", MacroDomain.RATES, "DFF", "Effective Federal Funds Rate", "Federal Reserve", "Daily", "Percent", "NSA", 18, revision_sensitive=False),
    _entry("US_POLICY_RATE_UPPER", MacroDomain.RATES, "DFEDTARU", "Federal Funds Target Range - Upper Limit", "Federal Reserve", "Daily", "Percent", "NSA", 101, revision_sensitive=False),
    _entry("US_SOFR", MacroDomain.RATES, "SOFR", "Secured Overnight Financing Rate", "Federal Reserve Bank of New York", "Daily", "Percent", "NSA", 445, revision_sensitive=False),
    _entry("US_3M_TREASURY_YIELD", MacroDomain.RATES, "DGS3MO", "3-Month Treasury Constant Maturity Rate", "Board of Governors", "Daily", "Percent", "NSA", 18, revision_sensitive=False),
    _entry("US_2Y_TREASURY_YIELD", MacroDomain.YIELD_CURVE, "DGS2", "2-Year Treasury Constant Maturity Rate", "Board of Governors", "Daily", "Percent", "NSA", 18, revision_sensitive=False),
    _entry("US_5Y_TREASURY_YIELD", MacroDomain.YIELD_CURVE, "DGS5", "5-Year Treasury Constant Maturity Rate", "Board of Governors", "Daily", "Percent", "NSA", 18, revision_sensitive=False),
    _entry("US_10Y_TREASURY_YIELD", MacroDomain.YIELD_CURVE, "DGS10", "10-Year Treasury Constant Maturity Rate", "Board of Governors", "Daily", "Percent", "NSA", 18, revision_sensitive=False),
    _entry("US_30Y_TREASURY_YIELD", MacroDomain.YIELD_CURVE, "DGS30", "30-Year Treasury Constant Maturity Rate", "Board of Governors", "Daily", "Percent", "NSA", 18, revision_sensitive=False),
    _entry("US_REAL_5Y_YIELD", MacroDomain.YIELD_CURVE, "DFII5", "5-Year Treasury Inflation-Indexed Security", "Board of Governors", "Daily", "Percent", "NSA", 18, revision_sensitive=False),
    _entry("US_REAL_10Y_YIELD", MacroDomain.YIELD_CURVE, "DFII10", "10-Year Treasury Inflation-Indexed Security", "Board of Governors", "Daily", "Percent", "NSA", 18, revision_sensitive=False),
    # Inflation
    _entry("US_HEADLINE_CPI", MacroDomain.INFLATION, "CPIAUCSL", "Consumer Price Index for All Urban Consumers: All Items", "Bureau of Labor Statistics", "Monthly", "Index 1982-84=100", "SA", 10),
    _entry("US_CORE_CPI", MacroDomain.INFLATION, "CPILFESL", "Consumer Price Index: All Items Less Food and Energy", "Bureau of Labor Statistics", "Monthly", "Index 1982-84=100", "SA", 10),
    _entry("US_HEADLINE_PCE", MacroDomain.INFLATION, "PCEPI", "Personal Consumption Expenditures: Chain-type Price Index", "BEA", "Monthly", "Index 2017=100", "SA", 54),
    _entry("US_CORE_PCE", MacroDomain.INFLATION, "PCEPILFE", "PCE excluding Food and Energy", "BEA", "Monthly", "Index 2017=100", "SA", 54),
    _entry("US_PPI_FINAL_DEMAND", MacroDomain.INFLATION, "PPIFIS", "Producer Price Index: Final Demand", "Bureau of Labor Statistics", "Monthly", "Index 1982=100", "SA", 46),
    _entry("US_5Y_BREAKEVEN", MacroDomain.INFLATION, "T5YIE", "5-Year Breakeven Inflation Rate", "Board of Governors", "Daily", "Percent", "NSA", 304, revision_sensitive=False),
    _entry("US_10Y_BREAKEVEN", MacroDomain.INFLATION, "T10YIE", "10-Year Breakeven Inflation Rate", "Board of Governors", "Daily", "Percent", "NSA", 304, revision_sensitive=False),
    _entry("US_5Y5Y_FORWARD_INFLATION", MacroDomain.INFLATION, "T5YIFR", "5-Year, 5-Year Forward Inflation Expectation Rate", "Board of Governors", "Daily", "Percent", "NSA", 304, revision_sensitive=False),
    # Labor
    _entry("US_UNEMPLOYMENT_RATE", MacroDomain.LABOR, "UNRATE", "Unemployment Rate", "Bureau of Labor Statistics", "Monthly", "Percent", "SA", 50),
    _entry("US_NONFARM_PAYROLLS", MacroDomain.LABOR, "PAYEMS", "All Employees, Total Nonfarm", "Bureau of Labor Statistics", "Monthly", "Thousands of Persons", "SA", 50),
    _entry("US_INITIAL_CLAIMS", MacroDomain.LABOR, "ICSA", "Initial Claims", "Department of Labor", "Weekly", "Number", "SA", 180),
    _entry("US_CONTINUING_CLAIMS", MacroDomain.LABOR, "CCSA", "Continued Claims", "Department of Labor", "Weekly", "Number", "SA", 180),
    _entry("US_LABOR_FORCE_PARTICIPATION", MacroDomain.LABOR, "CIVPART", "Labor Force Participation Rate", "Bureau of Labor Statistics", "Monthly", "Percent", "SA", 50),
    _entry("US_AVERAGE_HOURLY_EARNINGS", MacroDomain.LABOR, "CES0500000003", "Average Hourly Earnings of All Employees, Total Private", "Bureau of Labor Statistics", "Monthly", "Dollars per Hour", "SA", 50),
    _entry("US_JOB_OPENINGS", MacroDomain.LABOR, "JTSJOL", "Job Openings: Total Nonfarm", "Bureau of Labor Statistics", "Monthly", "Level in Thousands", "SA", 192),
    # Growth
    _entry("US_REAL_GDP", MacroDomain.GROWTH, "GDPC1", "Real Gross Domestic Product", "BEA", "Quarterly", "Billions of Chained 2017 Dollars", "SA", 53),
    _entry("US_INDUSTRIAL_PRODUCTION", MacroDomain.GROWTH, "INDPRO", "Industrial Production Index", "Board of Governors", "Monthly", "Index 2017=100", "SA", 13),
    _entry("US_RETAIL_SALES", MacroDomain.GROWTH, "RSAFS", "Advance Retail Sales: Retail and Food Services", "Census Bureau", "Monthly", "Millions of Dollars", "SA", 9),
    _entry("US_CAPACITY_UTILIZATION", MacroDomain.GROWTH, "TCU", "Capacity Utilization: Total Industry", "Board of Governors", "Monthly", "Percent of Capacity", "SA", 13),
    _entry("US_HOUSING_STARTS", MacroDomain.GROWTH, "HOUST", "Housing Starts: Total", "Census Bureau", "Monthly", "Thousands of Units", "SA", 27),
    _entry("US_BUILDING_PERMITS", MacroDomain.GROWTH, "PERMIT", "New Private Housing Units Authorized by Building Permits", "Census Bureau", "Monthly", "Thousands of Units", "SA", 27),
    _entry("US_DURABLE_GOODS_ORDERS", MacroDomain.GROWTH, "DGORDER", "Manufacturers' New Orders: Durable Goods", "Census Bureau", "Monthly", "Millions of Dollars", "SA", 95),
    # Liquidity
    _entry("US_FED_TOTAL_ASSETS", MacroDomain.LIQUIDITY, "WALCL", "Assets: Total Assets: Total Assets (Less Eliminations from Consolidation)", "Federal Reserve", "Weekly", "Millions of Dollars", "NSA", 20, revision_sensitive=False),
    _entry("US_RESERVE_BALANCES", MacroDomain.LIQUIDITY, "WRESBAL", "Reserve Balances with Federal Reserve Banks", "Federal Reserve", "Weekly", "Millions of Dollars", "NSA", 20, revision_sensitive=False),
    _entry("US_OVERNIGHT_RRP", MacroDomain.LIQUIDITY, "RRPONTSYD", "Overnight Reverse Repurchase Agreements", "Federal Reserve", "Daily", "Billions of Dollars", "NSA", 379, revision_sensitive=False),
    _entry("US_TREASURY_GENERAL_ACCOUNT", MacroDomain.LIQUIDITY, "WTREGEN", "Treasury General Account", "U.S. Treasury", "Weekly", "Millions of Dollars", "NSA", 20, revision_sensitive=False),
    _entry("US_M2", MacroDomain.LIQUIDITY, "M2SL", "M2 Money Stock", "Federal Reserve", "Monthly", "Billions of Dollars", "SA", 21, revision_sensitive=False),
    # Credit / financial conditions — note third-party licensing on spreads
    _entry("US_HY_SPREAD", MacroDomain.CREDIT, "BAMLH0A0HYM2", "ICE BofA US High Yield Index Option-Adjusted Spread", "ICE Data Indices, LLC", "Daily", "Percent", "NSA", 209, copyright_id="BAML", rights="redistribution_review_required"),
    _entry("US_IG_SPREAD", MacroDomain.CREDIT, "BAMLC0A0CM", "ICE BofA US Corporate Index Option-Adjusted Spread", "ICE Data Indices, LLC", "Daily", "Percent", "NSA", 209, copyright_id="BAML", rights="redistribution_review_required"),
    _entry("US_NFCI", MacroDomain.FINANCIAL_CONDITIONS, "NFCI", "Chicago Fed National Financial Conditions Index", "Chicago Fed", "Weekly", "Index", "NSA", 221, revision_sensitive=False),
    _entry("US_STLOUIS_FSI", MacroDomain.FINANCIAL_CONDITIONS, "STLFSI4", "St. Louis Fed Financial Stress Index", "St. Louis Fed", "Weekly", "Index", "NSA", 187, revision_sensitive=False),
    # USD
    _entry("US_TRADE_WEIGHTED_DOLLAR", MacroDomain.USD, "DTWEXBGS", "Nominal Broad U.S. Dollar Index", "Board of Governors", "Daily", "Index Jan 2006=100", "NSA", 17, revision_sensitive=False),
    _entry("US_BROAD_DOLLAR_MAJOR", MacroDomain.USD, "DTWEXAFEGS", "Nominal Advanced Foreign Economies U.S. Dollar Index", "Board of Governors", "Daily", "Index Jan 2006=100", "NSA", 17, revision_sensitive=False),
)


REGISTRY_BY_CANONICAL = {entry.canonical_indicator_id: entry for entry in TIER1_REGISTRY}
REGISTRY_BY_SERIES = {entry.fred_series_id: entry for entry in TIER1_REGISTRY}


def iter_registry(domain: MacroDomain | None = None) -> Iterator[MacroRegistryEntry]:
    for entry in TIER1_REGISTRY:
        if domain is None or entry.domain == domain:
            yield entry


def lookup_canonical(canonical_indicator_id: str) -> MacroRegistryEntry | None:
    return REGISTRY_BY_CANONICAL.get(canonical_indicator_id)


def lookup_series(series_id: str) -> MacroRegistryEntry | None:
    return REGISTRY_BY_SERIES.get(series_id)


def registry_table_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for entry in TIER1_REGISTRY:
        rows.append(
            {
                "domain": entry.domain.value,
                "canonical_indicator_id": entry.canonical_indicator_id,
                "fred_series_id": entry.fred_series_id,
                "title": entry.title,
                "original_source": entry.original_source,
                "frequency": entry.frequency,
                "units": entry.units,
                "seasonal_adjustment": entry.seasonal_adjustment,
                "fred_release_id": entry.fred_release_id,
                "revision_sensitive": entry.revision_sensitive,
                "v1_pit_supported": entry.v1_pit_supported,
                "v2_release_membership": entry.v2_release_membership,
                "copyright_id": entry.copyright_id,
                "usage_rights": entry.usage_rights,
                "inclusion_rationale": entry.inclusion_rationale,
            }
        )
    return rows


__all__ = [
    "MacroRegistryEntry",
    "REGISTRY_BY_CANONICAL",
    "REGISTRY_BY_SERIES",
    "TIER1_REGISTRY",
    "iter_registry",
    "lookup_canonical",
    "lookup_series",
    "registry_table_rows",
]
