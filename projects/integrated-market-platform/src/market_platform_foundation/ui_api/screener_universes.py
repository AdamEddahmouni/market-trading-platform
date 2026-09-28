"""The three admitted Main Screener universes and their market semantics."""

from __future__ import annotations

from dataclasses import dataclass

US_EQUITIES = "US_EQUITIES"
FUTURES = "FUTURES"
US_ETFS = "US_ETFS"


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
            "Short": ("symbol", "price", "change_pct", "float_shares", "short_float_pct", "short_ratio", "rel_volume", "volume"),
            "Fundamentals": ("symbol", "company", "sector", "industry", "market_cap", "eps_ttm", "pe", "fwd_pe", "earnings_date", "recommendation"),
            "Custom": ("symbol", "price", "change_pct", "volume"),
        },
        "US_EQUITY_L1", "US_EQUITY_CURRENT_KLINE",
        ("order_flow", "cvd", "level2", "charts", "futures"),
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
        "US_FUTURES_QUOTE", "FUTURES_CURRENT_KLINE_UNVERIFIED", (),
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
        "US_EQUITY_L1", "US_EQUITY_CURRENT_KLINE", ("order_flow", "cvd", "level2", "charts"),
    ),
}


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
        }
        for spec in UNIVERSES.values()
    ]
