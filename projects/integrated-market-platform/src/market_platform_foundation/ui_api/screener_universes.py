"""The admitted Main Screener universes and their market semantics.

See docs/engineering/SCREENER_UNIVERSE_ARCHITECTURE.md: the canonical core
universes are US Equities, ETFs, Futures, Bonds / Fixed Income, and Crypto
(all five implemented; Crypto in S10). Intelligence lenses (Options, Short
Squeeze, Whales, Institutions, Order Flow, News, ...) are views or panels, never
universes; a new universe requires explicit owner authorization.
"""

from __future__ import annotations

from dataclasses import dataclass

US_EQUITIES = "US_EQUITIES"
FUTURES = "FUTURES"
US_ETFS = "US_ETFS"
BONDS = "BONDS"
CRYPTO = "CRYPTO"


@dataclass(frozen=True, slots=True)
class Universe:
    id: str
    label: str
    asset_class: str
    instrument_kind: str
    source: str
    session_model: str
    default_sort: str
    default_columns: tuple[str, ...]
    views: dict[str, tuple[str, ...]]
    quote_capability: str
    bars_capability: str
    panels: tuple[str, ...]
    #: Real XA-01 classes/kinds a row may carry (a universe may admit several).
    admitted_asset_classes: tuple[str, ...] = ()
    admitted_instrument_kinds: tuple[str, ...] = ()
    identity_fields: tuple[str, ...] = ("symbol",)
    data_sources: tuple[str, ...] = ()
    tradability: str = "PER_INSTRUMENT"
    #: S12 universe-wide intelligence views (only where universe-complete evidence exists).
    intelligence_views: tuple[str, ...] = ()

    @property
    def columns(self) -> frozenset[str]:
        return frozenset(field for fields in self.views.values() for field in fields)


UNIVERSES: dict[str, Universe] = {
    US_EQUITIES: Universe(
        US_EQUITIES, "US Equities", "EQUITY", "TRADABLE_SECURITY", "FINVIZ_ELITE",
        "US_EQUITY", "volume",
        ("symbol", "price", "change_pct", "volume", "rel_volume", "float_shares", "market_cap", "short_float_pct", "bid", "ask", "spread_pct", "rsi_14"),
        {
            "Overview": ("symbol", "price", "change_pct", "volume", "rel_volume", "float_shares", "market_cap", "short_float_pct", "bid", "ask", "spread_pct", "rsi_14"),
            "Performance": ("symbol", "price", "change_pct", "perf_week", "volume", "rel_volume", "rsi_14", "market_cap"),
            "Technical": ("symbol", "price", "change_pct", "rsi_14", "perf_week", "volume", "rel_volume"),
            "Volume": ("symbol", "price", "volume", "avg_volume", "rel_volume", "float_shares", "change_pct"),
            # S8: the squeeze-discovery perspective. Every column is a universe-wide
            # Finviz snapshot field or a visible-row L1 quote; selected-instrument
            # squeeze evidence (FINRA, Reg SHO, FTD, borrow, order flow, options)
            # lives in the Short Squeeze panel and never becomes a column.
            "Short Squeeze": ("symbol", "price", "change_pct", "rel_volume", "volume", "float_shares", "short_float_pct",
                              "short_ratio", "bid", "ask", "spread_pct"),
            "Fundamentals": ("symbol", "company", "sector", "industry", "market_cap", "eps_ttm", "pe", "fwd_pe", "earnings_date", "recommendation"),
            "Custom": ("symbol", "price", "change_pct", "volume"),
        },
        "US_EQUITY_L1", "US_EQUITY_CURRENT_KLINE",
        # S12: Institutional & Whale and Congress & Government are panels (intelligence
        # lenses), never universes; see SCREENER_S12_PARTICIPANT_GOVERNMENT_INTELLIGENCE.md.
        ("order_flow", "cvd", "level2", "charts", "futures", "options", "short_squeeze", "news", "institutional",
         "congress_gov", "connectivity"),
        intelligence_views=("ownership", "congress"),
    ),
    FUTURES: Universe(
        FUTURES, "Futures", "FUTURE", "FUTURE_CONTRACT", "MOOMOO_OPEND_CONTRACT_CATALOG",
        "PROVIDER_STATE", "root",
        ("symbol", "root", "company", "exchange", "expiry", "dte", "lead", "price", "change_pct", "volume", "open_interest"),
        {
            "Overview": ("symbol", "root", "company", "exchange", "expiry", "dte", "lead", "price", "change_pct", "volume", "open_interest"),
            "Contract": ("symbol", "root", "company", "exchange", "contract_month", "expiry", "dte", "lead", "tick_size", "multiplier"),
            "Performance": ("symbol", "root", "price", "change_pct", "volume", "open_interest"),
            "Custom": ("symbol", "root", "expiry", "dte"),
        },
        # S12: CFTC positioning only; congressional securities disclosures do not map to futures.
        "US_FUTURES_QUOTE", "FUTURES_CURRENT_KLINE_UNVERIFIED", ("news", "institutional", "connectivity"),
        intelligence_views=("positioning",),
    ),
    US_ETFS: Universe(
        US_ETFS, "ETFs", "ETF_FUND", "TRADABLE_SECURITY", "MOOMOO_OPEND_ETF_CATALOG",
        "US_EQUITY", "symbol",
        ("symbol", "company", "exchange", "price", "change_pct", "volume", "bid", "ask", "spread_pct"),
        {
            "Overview": ("symbol", "company", "exchange", "price", "change_pct", "volume", "bid", "ask", "spread_pct"),
            "Performance": ("symbol", "company", "price", "change_pct", "volume"),
            "Custom": ("symbol", "company", "exchange", "price"),
        },
        "US_EQUITY_L1", "US_EQUITY_CURRENT_KLINE",
        ("order_flow", "cvd", "level2", "charts", "options", "news", "institutional", "congress_gov", "connectivity"),
        intelligence_views=("congress",),
    ),
    # S9: one Bonds / Fixed Income universe. Categories (Treasury, corporate,
    # agency, municipal, securitized — S16) are filters inside it, never separate
    # universes. Rows are reference-only: there is no bond execution path.
    BONDS: Universe(
        BONDS, "Bonds", "FIXED_INCOME", "FIXED_INCOME_SECURITY", "US_TREASURY_FISCAL_DATA",
        "PUBLICATION", "maturity",
        ("symbol", "category", "security_type", "coupon", "maturity", "years_to_maturity", "auction_yield", "auction_date",
         "outstanding"),
        {
            "Overview": ("symbol", "category", "security_type", "coupon", "maturity", "years_to_maturity", "auction_yield",
                         "auction_date", "outstanding"),
            "Treasuries": ("symbol", "security_type", "term", "coupon", "issue_date", "maturity", "tips", "frn",
                           "auction_yield", "auction_real_yield", "auction_discount_margin", "bid_to_cover",
                           "reference_tenor", "reference_rate"),
            # Curve points are reference observations for the matched tenor,
            # never this security's own yield.
            "Rates & Curve": ("symbol", "security_type", "maturity", "years_to_maturity", "maturity_bucket",
                              "reference_tenor", "reference_rate", "indicative_rate", "auction_yield"),
            # S16: fund-reported terms and holdings (Form N-PORT). Values are the
            # funds' own, at their report dates — never a current price.
            "Credit & Munis": ("symbol", "issuer", "category", "security_type", "coupon", "coupon_type", "maturity",
                               "years_to_maturity", "fund_count", "fund_par_held", "fund_value_pct", "report_date"),
            # Dated operation prices (buybacks, Fed purchases) and what follows from them.
            "Observed": ("symbol", "security_type", "maturity", "observed_price", "observed_yield", "benchmark_spread",
                         "observed_date", "reference_tenor", "reference_rate"),
            "Custom": ("symbol", "security_type", "coupon", "maturity"),
        },
        "NO_STREAMING_QUOTE", "NO_PRICE_HISTORY", ("rates_curve", "news", "connectivity"),
        admitted_asset_classes=("SOVEREIGN_DEBT", "BOND"),
        admitted_instrument_kinds=("SOVEREIGN_SECURITY", "BOND"),
        identity_fields=("cusip", "isin"),
        data_sources=("US_TREASURY_FISCAL_DATA_AUCTIONS", "US_TREASURY_FISCAL_DATA_MSPD", "US_TREASURY_DAILY_RATES",
                      "FRED", "FINRA_TRACE_AGGREGATES", "SEC_FORM_NPORT", "US_TREASURY_FISCAL_DATA_TIPS_CPI",
                      "US_TREASURY_FISCAL_DATA_FRN_INDEXES", "US_TREASURY_FISCAL_DATA_BUYBACKS",
                      "NY_FED_TREASURY_OPERATIONS", "NY_FED_REFERENCE_RATES", "NY_FED_SOMA_HOLDINGS", "OPENFIGI"),
        tradability="REFERENCE_ONLY",
    ),
    CRYPTO: Universe(
        CRYPTO, "Crypto", "CRYPTO", "CRYPTO_PAIR", "KRAKEN_SPOT_PUBLIC",
        "24_7", "symbol",
        ("symbol", "price", "change_pct", "quote_volume", "bid", "ask", "spread_pct", "venue"),
        {
            "Overview": ("symbol", "price", "change_pct", "quote_volume", "bid", "ask", "spread_pct", "venue"),
            "Performance": ("symbol", "price", "change_pct", "high_24h", "low_24h", "base_volume", "quote_volume"),
            "Liquidity": ("symbol", "bid", "ask", "spread_pct", "quote_volume", "trade_count", "venue"),
            "Custom": ("symbol", "base_asset", "quote_asset", "price", "change_pct", "quote_volume"),
        },
        # S10: panels only where the venue publishes the evidence: OHLC bars
        # (Charts), trades with the exchange-native taker side (Order Flow, CVD),
        # and a checksummed snapshot+delta book (Level 2). No Futures Context,
        # Options, or Short Squeeze semantics exist for a spot pair.
        "KRAKEN_PUBLIC_TICKER", "KRAKEN_PUBLIC_OHLC", ("order_flow", "cvd", "level2", "charts", "news"),
        identity_fields=("base_asset", "quote_asset", "venue", "product_type"),
        data_sources=("KRAKEN_SPOT_ASSET_PAIRS", "KRAKEN_SPOT_TICKER", "KRAKEN_SPOT_OHLC",
                      "KRAKEN_WS_V2_TRADE", "KRAKEN_WS_V2_BOOK"),
        tradability="DISCOVERY_ONLY",
    ),
}


#: Views renamed after release; saved screens and URLs holding the old name keep working.
VIEW_ALIASES: dict[str, dict[str, str]] = {US_EQUITIES: {"Short": "Short Squeeze"}}


def canonical_view(universe: str, view: object) -> object:
    return VIEW_ALIASES.get(universe, {}).get(view, view) if isinstance(view, str) else view


def universe_spec(value: str) -> Universe:
    try:
        return UNIVERSES[value]
    except KeyError as exc:
        raise ValueError("UNSUPPORTED_UNIVERSE") from exc


def universe_payload() -> list[dict[str, object]]:
    return [
        {
            "id": spec.id, "label": spec.label, "asset_class": spec.asset_class,
            "instrument_kind": spec.instrument_kind, "source": spec.source,
            "session_model": spec.session_model, "default_sort": spec.default_sort,
            "default_columns": list(spec.default_columns),
            "views": {name: list(fields) for name, fields in spec.views.items()},
            # JSON responses sort object keys; tab order travels explicitly.
            "view_order": list(spec.views),
            "quote_capability": spec.quote_capability,
            "bars_capability": spec.bars_capability, "panels": list(spec.panels),
            "view_aliases": dict(VIEW_ALIASES.get(spec.id, {})),
            "admitted_asset_classes": list(spec.admitted_asset_classes or (spec.asset_class,)),
            "admitted_instrument_kinds": list(spec.admitted_instrument_kinds or (spec.instrument_kind,)),
            "identity_fields": list(spec.identity_fields), "data_sources": list(spec.data_sources or (spec.source,)),
            "tradability": spec.tradability, "intelligence_views": list(spec.intelligence_views),
        }
        for spec in UNIVERSES.values()
    ]
