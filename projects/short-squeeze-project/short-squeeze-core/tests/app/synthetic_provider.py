"""A synthetic read-only provider for the current-screen tests.

The whole suite must run with no IB Gateway and no network. This stands in for
``LiveProvider`` with the same surface, so every current-mode test exercises the real
session, evaluation and presentation code paths.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from apps.research_screener import discovery as discovery_module
from apps.research_screener.finviz_live import FinvizRow
from apps.research_screener.live_providers import ProviderBundle
from apps.research_screener.ibkr_session import QuoteTicks
from apps.research_screener.provider_session import (
    CallStatus,
    CurrentBar,
    ProviderCallState,
    SymbolCollection,
)

STATUS_NAMES = (
    "connection", "scanner", "quote", "historical", "borrow", "news",
    "short_interest", "float", "sec", "halts", "pacing",
)


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def rising_bars(
    count: int = 40, *, start_price: float = 5.0, step: float = 1.004,
    end: datetime | None = None,
) -> list[CurrentBar]:
    """A trailing 1-minute series ending one minute before ``end``."""
    end = end or datetime.now(tz=UTC).replace(second=0, microsecond=0)
    bars: list[CurrentBar] = []
    price = start_price
    for index in range(count):
        moment = end - timedelta(minutes=count + 1 - index)
        price *= step
        bars.append(
            CurrentBar(
                timestamp_utc=moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
                open=price, high=price * 1.001, low=price * 0.999, close=price,
            )
        )
    return bars


def quote(
    symbol: str, *, last: float | None = 7.0, market_data_type: int | None = 3,
    shortable: float | None = None, shortable_shares: float | None = None,
    volume: float | None = None,
) -> QuoteTicks:
    ticks = QuoteTicks(symbol=symbol, con_id=1)
    if last is not None:
        ticks.prices = {
            "last": last, "bid": last - 0.01, "ask": last + 0.01,
            "previous_close": last * 0.9, "open": last * 0.95,
            "high": last * 1.02, "low": last * 0.93,
        }
    if volume is not None:
        ticks.sizes["volume"] = volume
    if shortable is not None:
        ticks.generics["shortable_indicator"] = shortable
    if shortable_shares is not None:
        ticks.sizes["shortable_shares"] = shortable_shares
    ticks.market_data_type = market_data_type
    ticks.received_at = _iso(datetime.now(tz=UTC))
    return ticks


class _Row:
    def __init__(self, rank: int, symbol: str) -> None:
        self.rank = rank
        self.con_id = 1000 + rank
        self.symbol = symbol
        self.sec_type = "STK"
        self.currency = "USD"
        self.primary_exchange = "NASDAQ"
        self.long_name = f"{symbol} Inc"


class SyntheticProvider:
    """Same surface as ``LiveProvider``; deterministic and entirely offline."""

    def __init__(
        self,
        symbols: tuple[str, ...] = ("AAA", "BBB", "CCC"),
        *,
        scanner_fails: bool = False,
        collect_fails: bool = False,
        bars_factory=None,
        quote_factory=None,
        budget: int = 60,
    ) -> None:
        self.symbols = symbols
        self.scanner_fails = scanner_fails
        self.collect_fails = collect_fails
        self.bars_factory = bars_factory or (lambda symbol: rising_bars())
        self.quote_factory = quote_factory or (lambda symbol: quote(symbol))
        self.budget = budget
        self.collect_calls: list[str] = []
        self.discovery_calls = 0
        self.reconnects = 0
        for name in STATUS_NAMES:
            setattr(self, f"{name}_status", CallStatus(name))

    # -- discovery ---------------------------------------------------------

    def run_discovery(self, profile, *, limit: int | None = None):
        self.discovery_calls += 1
        if profile.scanner is None:
            self.scanner_status.failed("manual profile", ProviderCallState.NOT_CONFIGURED)
            return []
        if self.scanner_fails:
            self.scanner_status.failed("synthetic scanner outage", ProviderCallState.FAILED)
            return []
        rows = [_Row(index, symbol) for index, symbol in enumerate(self.symbols, start=1)]
        self.scanner_status.succeeded(f"{len(rows)} row(s)")
        cap = limit or (profile.scanner.number_of_rows if profile.scanner else len(rows))
        return discovery_module.candidates_from_scanner(rows, profile.profile_id, limit=cap)

    # -- symbol pass -------------------------------------------------------

    def collect_symbol(self, symbol: str, *, want_quote: bool = True) -> SymbolCollection:
        self.collect_calls.append(symbol)
        if self.budget <= 0:
            return SymbolCollection(
                symbol=symbol,
                reason="Refused by the provider pacing budget: 0 of 60 remain.",
            )
        self.budget -= 1
        if self.collect_fails:
            return SymbolCollection(symbol=symbol, reason="synthetic provider outage")
        return SymbolCollection(
            symbol=symbol, resolved=True, con_id=1, long_name=f"{symbol} Inc",
            primary_exchange="NASDAQ", currency="USD",
            bars=self.bars_factory(symbol),
            quote=self.quote_factory(symbol) if want_quote else None,
            retrieved_at=_iso(datetime.now(tz=UTC)),
        )

    # -- status ------------------------------------------------------------

    def ensure_connected(self) -> None:
        self.reconnects += 1
        self.connection_status.succeeded("synthetic")

    def close(self) -> None:
        self.connection_status.failed("closed", ProviderCallState.UNAVAILABLE)

    def pacing_state(self) -> dict[str, Any]:
        return {"remaining": self.budget, "limit": 60, "window_seconds": 600,
                "detail": f"{self.budget} of 60 remain."}

    def historical_budget_remaining(self) -> int:
        return max(0, int(self.budget))

    def statuses(self) -> list[dict[str, Any]]:
        return [
            {**getattr(self, f"{name}_status").as_dict(), "surface": name}
            for name in STATUS_NAMES
        ]

    def connection_info(self) -> dict[str, Any]:
        return {"status": "SYNTHETIC", "port": None, "server_version": None,
                "provider_current_time": None}


class FakeFinvizProvider:
    configured = True
    cached_at = "2026-07-25T14:00:00Z"

    def __init__(self, rows: dict[str, FinvizRow] | None = None) -> None:
        self.rows = rows or {
            "AAA": FinvizRow(
                ticker="AAA", company="AAA Inc", sector="Technology",
                industry="Software", country="USA", price=7.0, change_pct=12.5,
                volume=2_000_000, avg_volume=1_000_000, rel_volume=2.0,
                market_cap=70_000_000, shares_outstanding=10_000_000,
                float_shares=8_000_000, short_float_pct=14.0, short_ratio=3.2,
                earnings_date="Jul 30 AMC",
            )
        }

    def get_row(self, symbol: str):
        return self.rows.get(symbol)

    def get_cached_rows(self):
        return list(self.rows.values())

    def get_news_for(self, symbol: str):
        return []

    def fetch_screener(self, force: bool = False):
        return {"success": True, "rows": len(self.rows), "error": None}

    def fetch_news(self, force: bool = False):
        return {"success": True, "count": 0, "error": None}

    def status(self):
        return {"provider": "Finviz Elite", "configured": True, "rows": len(self.rows)}


class FakeNewsProvider:
    configured = True

    def fetch_news(self, symbol: str, force: bool = False):
        return [{
            "provider_news_id": f"fake:{symbol}:1",
            "headline": f"{symbol} files deterministic test update",
            "url": f"https://example.invalid/{symbol}",
            "timestamp": "2026-07-25T13:00:00Z",
            "retrieved_at": "2026-07-25T14:00:00Z",
            "provider": "FakeNews",
            "tickers": [symbol],
        }]

    def status(self):
        return {"provider": "FakeNews", "configured": True, "cached_symbols": 1}


def fake_external_providers(
    finviz_rows: dict[str, FinvizRow] | None = None,
) -> ProviderBundle:
    return ProviderBundle(
        finviz=FakeFinvizProvider(finviz_rows), news=FakeNewsProvider()
    )


__all__ = [
    "FakeFinvizProvider", "FakeNewsProvider", "SyntheticProvider",
    "fake_external_providers", "quote", "rising_bars",
]
