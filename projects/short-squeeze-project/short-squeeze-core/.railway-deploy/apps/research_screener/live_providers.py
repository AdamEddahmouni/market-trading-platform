"""Live provider orchestrator.

Wires Finviz Elite, NewsAPI, Finnhub and SEC EDGAR to the screener's
field-by-field provider selection. Each field carries full source provenance,
retrieval time, and readiness status.
"""
from __future__ import annotations

import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .finviz_live import FinvizClient, FinvizRow
from .finnhub_live import FinnhubClient
from .news_live import (
    FinvizNewsProvider, FinnhubNewsProvider, NewsApiProvider,
    NewsOrchestrator, configure_news_orchestrator, get_news_orchestrator,
)
from .private_config import (
    ProviderCredentials, credential_status, load_provider_credentials,
    private_env_path_info,
)
from .sec_edgar import EdgardClient
from .sentiment_live import (
    SentimentAnalyzer, configure_sentiment, get_sentiment_analyzer,
)
from .truth import DataMode, FieldValue, Freshness, ValueStatus, known, missing
from .config import ApplicationConfig
from . import data_logger


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _now_dt() -> datetime:
    return datetime.now(tz=UTC)


def enrich_candidate(
    symbol: str,
    existing_fields: dict[str, FieldValue],
    *,
    finviz: FinvizRow | None = None,
    sec: dict[str, Any] | None = None,
    news_headlines: list[dict[str, Any]] | None = None,
    finnhub_price: float | None = None,
) -> dict[str, FieldValue]:
    fields = dict(existing_fields)

    retrieved_at = _now()

    if finviz is not None:
        fields.update(_finviz_fields(finviz, retrieved_at))

    if sec is not None:
        fields.update(_sec_fields(sec, symbol))

    if news_headlines:
        fields.update(_news_fields(news_headlines, symbol, retrieved_at))

    if finnhub_price is not None:
        fields.update(_finnhub_price_field(finnhub_price, symbol, retrieved_at))

    return fields


def _finviz_fields(row: FinvizRow, retrieved_at: str) -> dict[str, FieldValue]:
    provider = "Finviz Elite"
    freshness = Freshness.CURRENT
    mode = DataMode.HISTORICAL
    event = retrieved_at

    def fv(value, unit, name, evidence_id, readiness="DISPLAY_ONLY_PROVIDER_SNAPSHOT"):
        if value is None:
            return missing(
                ValueStatus.NOT_COLLECTED,
                f"Finviz did not return {name} for this symbol.",
                reason_code=f"FINVIZ_{name.upper()}_UNAVAILABLE",
                provider=provider, data_mode=mode,
            )
        return known(
            value, unit=unit, provider=provider,
            event_time=event, received_time=retrieved_at,
            freshness=freshness, data_mode=mode,
            evidence_id=f"finviz:{row.ticker}:{evidence_id}:{retrieved_at}",
            readiness=readiness,
        )

    # NOTE: float_shares is set by short_pressure_fields() with richer metadata
    # (provider_field, selection_reason, research_admissibility). Do not
    # overwrite it here.
    result: dict[str, FieldValue] = {
        "shares_outstanding_provider": fv(
            row.shares_outstanding, "SHARES", "shares_outstanding",
            "shares_outstanding",
            readiness="PROVIDER_SNAPSHOT_SHARES_OUT_FINVIZ",
        ),
        "short_float_pct": fv(
            row.short_float_pct, "PERCENT", "short_float",
            "short_float",
            readiness="PROVIDER_SNAPSHOT_SHORT_FLOAT_FINVIZ",
        ),
        "short_ratio_provider": fv(
            row.short_ratio, "RATIO", "short_ratio",
            "short_ratio",
            readiness="PROVIDER_SNAPSHOT_SHORT_RATIO_FINVIZ",
        ),
        "relative_volume_provider": fv(
            row.rel_volume, "RATIO", "relative_volume",
            "rel_volume",
            readiness="PROVIDER_SNAPSHOT_REL_VOLUME_FINVIZ",
        ),
        "market_cap_provider": fv(
            row.market_cap, "USD", "market_cap", "market_cap",
        ),
        "finviz_price": fv(
            row.price, "PRICE", "price", "price",
            readiness="PROVIDER_SNAPSHOT_PRICE_FINVIZ",
        ),
        "finviz_change_pct": fv(
            row.change_pct, "PERCENT", "change", "change",
            readiness="PROVIDER_SNAPSHOT_CHANGE_FINVIZ",
        ),
        "finviz_volume": fv(
            row.volume, "SHARES", "volume", "volume",
        ),
        "finviz_company": known(
            row.company, unit="TEXT", provider=provider,
            event_time=event, received_time=retrieved_at,
            freshness=freshness, data_mode=mode,
            evidence_id=f"finviz:{row.ticker}:company:{retrieved_at}",
            readiness="DISPLAY_ONLY",
        ) if row.company else missing(
            ValueStatus.NOT_COLLECTED,
            "Finviz did not return company name for this symbol.",
            reason_code="FINVIZ_COMPANY_UNAVAILABLE",
            provider=provider,
        ),
        "finviz_sector": known(
            row.sector, unit="TEXT", provider=provider,
            event_time=event, received_time=retrieved_at,
            freshness=freshness, data_mode=mode,
            evidence_id=f"finviz:{row.ticker}:sector:{retrieved_at}",
            readiness="DISPLAY_ONLY",
        ) if row.sector else missing(
            ValueStatus.NOT_COLLECTED, "No sector.", reason_code="FINVIZ_SECTOR_UNAVAILABLE",
            provider=provider,
        ),
        "finviz_industry": known(
            row.industry, unit="TEXT", provider=provider,
            event_time=event, received_time=retrieved_at,
            freshness=freshness, data_mode=mode,
            evidence_id=f"finviz:{row.ticker}:industry:{retrieved_at}",
            readiness="DISPLAY_ONLY",
        ) if row.industry else missing(
            ValueStatus.NOT_COLLECTED, "No industry.", reason_code="FINVIZ_INDUSTRY_UNAVAILABLE",
            provider=provider,
        ),
        "finviz_rsi": fv(row.rsi_14, "UNITLESS", "rsi_14", "rsi"),
        "finviz_earnings_date": known(
            row.earnings_date, unit="DATE", provider=provider,
            event_time=event, received_time=retrieved_at,
            freshness=freshness, data_mode=mode,
            evidence_id=f"finviz:{row.ticker}:earnings:{retrieved_at}",
            readiness="DISPLAY_ONLY",
        ) if row.earnings_date else missing(
            ValueStatus.NOT_COLLECTED, "No earnings date.",
            reason_code="FINVIZ_EARNINGS_UNAVAILABLE",
            provider=provider,
        ),
    }
    return result


def _sec_fields(sec_data: dict[str, Any], symbol: str) -> dict[str, FieldValue]:
    provider = "SEC_EDGAR"
    received = sec_data.get("retrieved_at", _now())

    if sec_data.get("error"):
        return {
            "sec_filings": missing(
                ValueStatus.NOT_CONFIGURED, sec_data["error"],
                reason_code="SEC_EDGAR_ERROR", provider=provider,
            ),
            "sec_catalyst": missing(
                ValueStatus.NOT_CONFIGURED, sec_data["error"],
                reason_code="SEC_EDGAR_ERROR", provider=provider,
            ),
        }

    count = sec_data.get("catalyst_count", 0)
    filings = sec_data.get("all_filings", [])

    filings_field = known(
        count, unit="FILING_COUNT", provider=provider,
        event_time=received, received_time=received,
        freshness=Freshness.CURRENT, data_mode=DataMode.HISTORICAL,
        evidence_id=f"sec:{symbol}:filings:{received}",
        readiness="DISPLAY_ONLY_PUBLIC_FILINGS",
    ) if sec_data.get("available") else missing(
        ValueStatus.NOT_COLLECTED,
        "No recent SEC filings found for this symbol.",
        reason_code="SEC_FILINGS_NONE", provider=provider,
    )

    catalyst_field = known(
        1.0 if count > 0 else 0.0,
        unit="BOOL", provider=provider,
        event_time=received, received_time=received,
        freshness=Freshness.CURRENT, data_mode=DataMode.HISTORICAL,
        evidence_id=f"sec:{symbol}:catalyst:{received}",
        readiness="DISPLAY_ONLY_PUBLIC_FILINGS",
    ) if sec_data.get("available") else missing(
        ValueStatus.NOT_COLLECTED,
        "No SEC filings found for this symbol.",
        reason_code="SEC_FILINGS_NONE", provider=provider,
    )

    return {"sec_filings": filings_field, "sec_catalyst": catalyst_field}


def _news_fields(
    headlines: list[dict[str, Any]], symbol: str, retrieved_at: str
) -> dict[str, FieldValue]:
    provider = "NEWS"
    providers_seen = set(h.get("provider", "UNKNOWN") for h in headlines)
    provider_label = ", ".join(sorted(providers_seen)) if providers_seen else "NONE"

    if not headlines:
        return {
            "catalyst": missing(
                ValueStatus.NOT_COLLECTED,
                "No news headlines found for this symbol.",
                reason_code="NEWS_NONE",
                provider=provider_label,
            ),
            "news_count": missing(
                ValueStatus.NOT_COLLECTED,
                "No news headlines found.",
                reason_code="NEWS_COUNT_ZERO",
                provider=provider_label,
            ),
        }

    return {
        "catalyst": known(
            len(headlines), unit="HEADLINE_COUNT", provider=provider_label,
            event_time=retrieved_at, received_time=retrieved_at,
            freshness=Freshness.CURRENT, data_mode=DataMode.HISTORICAL,
            evidence_id=f"news:{symbol}:catalyst:{retrieved_at}",
            readiness="DISPLAY_ONLY_NEWS_HEADLINES",
        ),
        "news_count": known(
            len(headlines), unit="HEADLINE_COUNT", provider=provider_label,
            event_time=retrieved_at, received_time=retrieved_at,
            freshness=Freshness.CURRENT, data_mode=DataMode.HISTORICAL,
            evidence_id=f"news:{symbol}:count:{retrieved_at}",
            readiness="DISPLAY_ONLY",
        ),
    }


def _finnhub_price_field(
    price: float, symbol: str, retrieved_at: str
) -> dict[str, FieldValue]:
    return {
        "finnhub_price": known(
            round(float(price), 4), unit="PRICE", provider="Finnhub",
            event_time=retrieved_at, received_time=retrieved_at,
            freshness=Freshness.CURRENT, data_mode=DataMode.LIVE,
            evidence_id=f"finnhub:{symbol}:price:{retrieved_at}",
            readiness="DISPLAY_ONLY_REALTIME_PRICE",
        ),
    }


class _NullFinvizProvider:
    configured = False
    cached_at = None

    def get_row(self, symbol: str) -> None:
        return None

    def get_cached_rows(self) -> list:
        return []

    def get_news_for(self, symbol: str) -> list[dict[str, Any]]:
        return []

    def fetch_screener(self, force: bool = False) -> dict[str, Any]:
        return {"success": False, "rows": 0, "error": "NOT_CONFIGURED"}

    def fetch_news(self, force: bool = False) -> dict[str, Any]:
        return {"success": False, "count": 0, "error": "NOT_CONFIGURED"}

    def status(self) -> dict[str, Any]:
        return {"provider": "Finviz Elite", "configured": False, "row_count": 0}


class _NullNewsProvider:
    configured = False

    def fetch_news(self, symbol: str, force: bool = False) -> list[dict[str, Any]]:
        return []

    def status(self) -> dict[str, Any]:
        return {"provider": "NewsAPI", "configured": False, "cached_symbols": 0}


class _NullNewsOrchestrator:
    configured = False

    def fetch_news(self, symbol: str, force: bool = False) -> list[dict[str, Any]]:
        return []

    def status(self) -> dict[str, Any]:
        return {"providers": {}, "any_configured": False, "provider_order": []}


class _NullFinnhubProvider:
    configured = False

    def fetch_price(self, symbol: str) -> None:
        return None

    def status(self) -> dict[str, Any]:
        return {"provider": "Finnhub", "configured": False}


class _NullSecProvider:
    configured = False

    def has_recent_catalyst_filing(self, symbol: str) -> dict[str, Any]:
        return {
            "available": False, "catalyst_count": 0, "most_recent": None,
            "all_filings": [], "cik": None, "company_name": None,
            "error": "SEC EDGAR is not enabled for this runtime.",
            "retrieved_at": _now(), "provider": "SEC_EDGAR",
        }

    def status(self) -> dict[str, Any]:
        return {"provider": "SEC_EDGAR", "configured": False}


class ProviderBundle:
    """Runtime-scoped external providers.

    The default bundle is entirely offline. Production opts in by passing a private
    configuration path to :func:`configure_runtime`; tests inject controlled fakes.
    """

    def __init__(
        self,
        *,
        finviz: Any | None = None,
        news: Any | None = None,
        finnhub: Any | None = None,
        sec: Any | None = None,
        borrow_fee: Any | None = None,
        credentials: ProviderCredentials | None = None,
        configured_states: dict[str, str] | None = None,
        news_orchestrator: Any | None = None,
        sentiment_analyzer: Any | None = None,
    ) -> None:
        self.finviz = finviz or _NullFinvizProvider()
        self.news = news or _NullNewsProvider()
        self.finnhub = finnhub or _NullFinnhubProvider()
        self.sec = sec or _NullSecProvider()
        from .borrow_fee_live import NullBorrowFeeProvider
        self.borrow_fee = borrow_fee or NullBorrowFeeProvider()
        self.credentials = credentials or ProviderCredentials({})
        self._configured_states = configured_states or {}
        self._news_orchestrator = news_orchestrator or _NullNewsOrchestrator()
        # Use an explicitly injected analyzer for this runtime, otherwise start
        # from a disabled local analyzer. Falling back to the global singleton
        # leaks state across isolated test/runtime bundles.
        self._sentiment_analyzer = sentiment_analyzer or SentimentAnalyzer()
        self._lock = threading.Lock()
        self._finviz_fetched = False
        self._finviz_error: str | None = None
        self._finviz_duration_s: float | None = None
        self._finviz_rows: int = 0
        self._finviz_enrichment: dict[str, Any] = {
            "scanner_candidates": 0,
            "matched_candidates": 0,
            "with_float": 0,
            "with_short_float": 0,
            "with_relative_volume": 0,
            "with_short_ratio": 0,
            "with_shares_outstanding": 0,
            "unmatched_symbols": [],
            "mapping_conflicts": [],
        }
        self._news_fetched = False
        self._news_count: int = 0
        self._news_error: str | None = None
        self._finviz_news_fetched = False
        self._finviz_news_count = 0
        self._finviz_news_error: str | None = None
        self._news_cache: dict[str, list[dict[str, Any]]] = {}
        self._sentiment_cache: dict[str, Any] = {}
        self._sec_cache: dict[str, dict[str, Any]] = {}
        self._finnhub_cache: dict[str, float | None] = {}
        self._sec_fetched = False
        self._sec_result_count = 0
        self._sec_error: str | None = None
        self._finnhub_fetched = False
        self._finnhub_price_count = 0
        self._finnhub_error: str | None = None

    @classmethod
    def offline(cls) -> "ProviderBundle":
        return cls()

    @classmethod
    def from_private_config(cls, path: Path) -> "ProviderBundle":
        credentials = load_provider_credentials(path)
        return cls.from_credentials(credentials)

    @classmethod
    def from_credentials(cls, credentials: ProviderCredentials) -> "ProviderBundle":
        values = credentials.values
        finviz_client = FinvizClient(values.get("FINVIZ_API_KEY"))
        newsapi = NewsApiProvider(values.get("NEWSAPI_KEY"))
        finnhub = FinnhubClient(values.get("FINNHUB_KEY"))
        finnhub_news = FinnhubNewsProvider(values.get("FINNHUB_KEY"))
        orchestrator = NewsOrchestrator(
            providers=[FinvizNewsProvider(finviz_client), finnhub_news, newsapi],
            cache_ttl_s=int(values.get("NEWS_CACHE_TTL_SECONDS") or 900),
            max_headlines=int(values.get("NEWS_MAX_HEADLINES_PER_SYMBOL") or 30),
        )
        configure_news_orchestrator(orchestrator)
        return cls(
            finviz=finviz_client,
            news=newsapi,
            finnhub=finnhub,
            sec=EdgardClient(),
            credentials=credentials,
            news_orchestrator=orchestrator,
        )

    @classmethod
    def from_application_config(cls, config: ApplicationConfig) -> "ProviderBundle":
        provider_config = config.providers
        values = {
            name: value
            for name, value, enabled in (
                (
                    "FINVIZ_API_KEY",
                    provider_config.finviz.credential,
                    provider_config.finviz.enabled,
                ),
                (
                    "NEWSAPI_KEY",
                    provider_config.newsapi.credential,
                    provider_config.newsapi.enabled,
                ),
                (
                    "FINNHUB_KEY",
                    provider_config.finnhub.credential,
                    provider_config.finnhub.enabled,
                ),
            )
            if enabled and value
        }
        credentials = ProviderCredentials(values)

        finviz_client = (
            FinvizClient(provider_config.finviz.credential)
            if provider_config.finviz.enabled
            else _NullFinvizProvider()
        )
        newsapi_provider = (
            NewsApiProvider(provider_config.newsapi.credential)
            if provider_config.newsapi.enabled
            else _NullNewsProvider()
        )
        finnhub_client = (
            FinnhubClient(provider_config.finnhub.credential)
            if provider_config.finnhub.enabled
            else _NullFinnhubProvider()
        )
        finnhub_news_provider = (
            FinnhubNewsProvider(provider_config.finnhub.credential)
            if provider_config.finnhub.enabled
            else _NullNewsProvider()
        )

        providers_list = []
        if provider_config.finviz.enabled:
            providers_list.append(FinvizNewsProvider(finviz_client))
        if provider_config.finnhub.enabled:
            providers_list.append(finnhub_news_provider)
        if provider_config.newsapi.enabled:
            providers_list.append(newsapi_provider)

        provider_order = (
            config.providers.news.provider_order
            if config.providers.news.provider_order
            else ["Finviz Elite", "Finnhub News", "NewsAPI"]
        )

        orchestrator = NewsOrchestrator(
            providers=providers_list,
            provider_order=provider_order,
            cache_ttl_s=config.providers.news.cache_ttl_seconds,
            max_headlines=config.providers.news.max_headlines_per_symbol,
        )
        configure_news_orchestrator(orchestrator)

        sentiment = config.build_sentiment_analyzer()
        if sentiment is not None:
            configure_sentiment(sentiment)
            from .sentiment_live import warm_sentiment_analyzer
            warm_sentiment_analyzer(sentiment)

        return cls(
            finviz=finviz_client,
            news=newsapi_provider,
            finnhub=finnhub_client,
            sec=(
                EdgardClient(provider_config.sec.user_agent)
                if provider_config.sec.enabled
                else _NullSecProvider()
            ),
            credentials=credentials,
            configured_states={
                "finviz": provider_config.finviz.status,
                "newsapi": provider_config.newsapi.status,
                "finnhub": provider_config.finnhub.status,
                "sec_edgar": provider_config.sec.status,
            },
            news_orchestrator=orchestrator,
            sentiment_analyzer=sentiment or get_sentiment_analyzer(),
        )

    # -------------------------------------------------------- refresh all

    def refresh_all(self, symbols: list[str]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "refreshed": 0, "errors": [], "providers": {},
            "at": _now(),
        }
        self._news_fetched = False
        self._news_count = 0
        self._news_error = None
        self._finviz_news_fetched = False
        self._finviz_news_count = 0
        self._finviz_news_error = None
        self._sec_fetched = False
        self._sec_result_count = 0
        self._sec_error = None
        self._finnhub_fetched = False
        self._finnhub_price_count = 0
        self._finnhub_error = None

        try:
            finviz = self.finviz
            if finviz.configured:
                t0 = _now_dt()
                fv_resp = finviz.fetch_screener(force=True)
                t1 = _now_dt()
                self._finviz_fetched = fv_resp["success"]
                self._finviz_error = fv_resp.get("error")
                self._finviz_duration_s = (t1 - t0).total_seconds()
                self._finviz_rows = fv_resp.get("rows", 0)

                # Log raw Finviz screener data for replay
                try:
                    cached_rows = finviz.get_cached_rows()
                    row_dicts = [
                        {
                            "ticker": r.ticker, "price": r.price,
                            "float_shares": r.float_shares,
                            "short_float_pct": r.short_float_pct,
                            "short_ratio": r.short_ratio,
                            "rel_volume": r.rel_volume,
                            "market_cap": r.market_cap,
                            "company": r.company,
                        }
                        for r in (cached_rows or [])
                    ]
                    data_logger.log_provider_raw(
                        "Finviz Elite", "screener_export", row_dicts,
                        context="all", success=fv_resp["success"],
                        error=fv_resp.get("error"),
                    )
                except Exception:
                    pass
                if fv_resp["success"]:
                    ensure = finviz.ensure_symbols(symbols)
                    matched_rows = {
                        symbol: finviz.get_row(symbol) for symbol in symbols
                    }
                else:
                    ensure = {"fetched": 0, "missing_before": 0}
                    matched_rows = {}
                matched = {
                    symbol: row for symbol, row in matched_rows.items()
                    if row is not None
                }
                finviz_status = finviz.status()
                self._finviz_enrichment = {
                    "scanner_candidates": len(symbols),
                    "matched_candidates": len(matched),
                    "symbol_exports_fetched": ensure.get("fetched", 0),
                    "symbol_exports_missing_before": ensure.get("missing_before", 0),
                    "with_float": sum(row.float_shares is not None for row in matched.values()),
                    "with_short_float": sum(
                        row.short_float_pct is not None for row in matched.values()
                    ),
                    "with_relative_volume": sum(
                        row.rel_volume is not None for row in matched.values()
                    ),
                    "with_short_ratio": sum(
                        row.short_ratio is not None for row in matched.values()
                    ),
                    "with_shares_outstanding": sum(
                        row.shares_outstanding is not None for row in matched.values()
                    ),
                    "unmatched_symbols": sorted(set(symbols) - set(matched)),
                    "mapping_conflicts": finviz_status.get(
                        "mapping_conflict_symbols", []
                    ),
                }
                result["providers"]["finviz"] = {
                    "configured": True,
                    "success": fv_resp["success"],
                    "rows": fv_resp.get("rows", 0),
                    "duration_s": round(self._finviz_duration_s, 2),
                    "error": fv_resp.get("error"),
                    "retrieved_at": _now(),
                }

                if fv_resp["success"]:
                    news_response = finviz.fetch_news(force=True)
                    self._finviz_news_fetched = bool(news_response.get("success"))
                    self._finviz_news_count = int(news_response.get("count", 0))
                    self._finviz_news_error = news_response.get("error")
                    result["providers"]["finviz_news"] = {
                        "success": self._finviz_news_fetched,
                        "count": self._finviz_news_count,
                        "error": self._finviz_news_error,
                    }
        except Exception as exc:
            result["providers"]["finviz"] = {
                "configured": False,
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

        for symbol in symbols:
            # --- News (orchestrator path)
            if self._news_orchestrator.configured:
                try:
                    headlines = self._news_orchestrator.fetch_news(symbol, force=True)
                    self._news_cache[symbol] = list(headlines)
                    if headlines:
                        self._news_count += len(headlines)
                        self._news_fetched = True
                        self._news_error = None
                except Exception as exc:
                    self._news_error = f"{type(exc).__name__}: {exc}"
                    result["errors"].append({
                        "provider": "News", "symbol": symbol,
                        "error": self._news_error,
                    })
            elif self.news.configured:
                try:
                    headlines = self.news.fetch_news(symbol, force=True)
                    self._news_cache[symbol] = list(headlines)
                    provider_error = self.news.status().get("last_error")
                    if provider_error:
                        self._news_error = str(provider_error)
                        result["errors"].append({
                            "provider": "NewsAPI", "symbol": symbol,
                            "error": self._news_error,
                        })
                    else:
                        self._news_count += len(headlines)
                        self._news_fetched = True
                        self._news_error = None
                except Exception as exc:
                    self._news_error = f"{type(exc).__name__}: {exc}"
                    result["errors"].append({
                        "provider": "NewsAPI", "symbol": symbol,
                        "error": self._news_error,
                    })
            if self.sec.configured:
                try:
                    self._sec_cache[symbol] = self.sec.has_recent_catalyst_filing(symbol)
                    self._sec_fetched = True
                    self._sec_result_count += 1
                except Exception as exc:
                    self._sec_error = f"{type(exc).__name__}: {exc}"
                    result["errors"].append({
                        "provider": "SEC_EDGAR", "symbol": symbol,
                        "error": self._sec_error,
                    })
            if self.finnhub.configured:
                try:
                    price = self.finnhub.fetch_price(symbol)
                    self._finnhub_cache[symbol] = price
                    if price is not None:
                        self._finnhub_fetched = True
                        self._finnhub_price_count += 1
                except Exception as exc:
                    self._finnhub_error = f"{type(exc).__name__}: {exc}"
                    result["errors"].append({
                        "provider": "Finnhub", "symbol": symbol,
                        "error": self._finnhub_error,
                    })
            if self.borrow_fee.configured:
                try:
                    self.borrow_fee.refresh_for(symbol)
                except Exception as exc:
                    result["errors"].append({
                        "provider": "Borrow Fee", "symbol": symbol,
                        "error": f"{type(exc).__name__}: {exc}",
                    })

        result["refreshed"] = len(symbols)
        status = self.status()
        for provider_name in ("newsapi", "finnhub", "sec_edgar"):
            result["providers"][provider_name] = status[provider_name]

        # Log all per-symbol provider data in one comprehensive batch
        try:
            for symbol in symbols:
                if symbol in self._news_cache:
                    data_logger.log_provider_raw(
                        "NEWS", "headlines", self._news_cache[symbol],
                        context=symbol, success=bool(self._news_cache[symbol]),
                    )
                if symbol in self._finnhub_cache:
                    data_logger.log_provider_raw(
                        "Finnhub", "price", self._finnhub_cache[symbol],
                        context=symbol,
                        success=self._finnhub_cache[symbol] is not None,
                    )
                if symbol in self._sec_cache:
                    data_logger.log_provider_raw(
                        "SEC_EDGAR", "filings", self._sec_cache[symbol],
                        context=symbol,
                        success=self._sec_cache[symbol].get("available", False),
                    )
        except Exception:
            pass

        return result

    def finviz_row(self, symbol: str) -> FinvizRow | None:
        return self.finviz.get_row(symbol)

    def news_for(self, symbol: str) -> list[dict[str, Any]]:
        cached = self._news_cache.get(symbol)
        if cached:
            return list(cached)
        if self._news_orchestrator.configured:
            try:
                headlines = self._news_orchestrator.fetch_news(symbol)
                self._news_cache[symbol] = list(headlines)
                return list(headlines)
            except Exception:
                pass
        if self.news.configured:
            try:
                headlines = self.news.fetch_news(symbol)
                self._news_cache[symbol] = list(headlines)
                return list(headlines)
            except Exception:
                pass
        return []

    def sentiment_for(self, symbol: str) -> Any:
        if not self._sentiment_analyzer.enabled:
            return None
        cached = self._sentiment_cache.get(symbol)
        if cached is not None:
            return cached
        headlines = self.news_for(symbol)
        if headlines:
            try:
                result = self._sentiment_analyzer.analyze_symbol(symbol, headlines)
                self._sentiment_cache[symbol] = result
                return result
            except Exception:
                pass
        return None

    def sec_for(self, symbol: str) -> dict[str, Any] | None:
        return self._sec_cache.get(symbol)

    def finnhub_price_for(self, symbol: str) -> float | None:
        return self._finnhub_cache.get(symbol)

    def borrow_fee_for(self, symbol: str) -> float | None:
        return self.borrow_fee.fetch(symbol)

    def status(self) -> dict[str, Any]:
        newsapi_status = self.news.status() if hasattr(self.news, "is_rate_limited") else {}
        finnhub_status = self.finnhub.status() if hasattr(self.finnhub, "news_rate_limited") else {}
        return {
            "finviz": {
                "status": self._configured_states.get(
                    "finviz",
                    "CONFIGURED" if self.finviz.configured else "NOT_CONFIGURED",
                ),
                "configured": bool(self.finviz.configured),
                "fetched": self._finviz_fetched,
                "rows": self._finviz_rows,
                "last_error": self._finviz_error,
                "last_duration_s": self._finviz_duration_s,
                "enrichment": dict(self._finviz_enrichment),
            },
            "newsapi": {
                "status": self._configured_states.get(
                    "newsapi",
                    "CONFIGURED" if self.news.configured else "NOT_CONFIGURED",
                ),
                "configured": bool(self.news.configured),
                "fetched": self._news_fetched,
                "headline_count": self._news_count,
                "last_error": self._news_error,
                "rate_limited": newsapi_status.get("rate_limited", False),
                "rate_limited_until": newsapi_status.get("rate_limited_until"),
            },
            "finviz_news": {
                "configured": bool(self.finviz.configured),
                "fetched": self._finviz_news_fetched,
                "headline_count": self._finviz_news_count,
                "last_error": self._finviz_news_error,
            },
            "finnhub": {
                "status": self._configured_states.get(
                    "finnhub",
                    "CONFIGURED" if self.finnhub.configured else "NOT_CONFIGURED",
                ),
                "configured": bool(self.finnhub.configured),
                "fetched": self._finnhub_fetched,
                "price_count": self._finnhub_price_count,
                "last_error": self._finnhub_error,
                "news_available": (
                    self.finnhub.configured
                    if hasattr(self.finnhub, "news_rate_limited") else False
                ),
            },
            "finnhub_news": {
                "configured": bool(self.finnhub.configured),
                "rate_limited": finnhub_status.get("news_rate_limited", False),
                "last_error": finnhub_status.get("news_last_error"),
            },
            "sec_edgar": {
                "status": self._configured_states.get(
                    "sec_edgar",
                    "CONFIGURED" if self.sec.configured else "NOT_CONFIGURED",
                ),
                "configured": bool(self.sec.configured),
                "fetched": self._sec_fetched,
                "result_count": self._sec_result_count,
                "last_error": self._sec_error,
            },
            "credentials": credential_status(self.credentials),
            "private_config": private_env_path_info(self.credentials),
            "borrow_fee": self.borrow_fee.status(),
        }


LiveProviderOrchestrator = ProviderBundle

_RUNTIME = ProviderBundle.offline()
_RUNTIME_LOCK = threading.Lock()


def get_runtime() -> ProviderBundle:
    return _RUNTIME


def configure_runtime(path: Path) -> ProviderBundle:
    global _RUNTIME
    runtime = ProviderBundle.from_private_config(path)
    with _RUNTIME_LOCK:
        _RUNTIME = runtime
    return runtime


def configure_environment() -> ProviderBundle:
    """Configure cloud-safe providers from named environment variables only."""
    global _RUNTIME
    names = ("FINVIZ_API_KEY", "NEWSAPI_KEY", "FINNHUB_KEY")
    credentials = ProviderCredentials({
        name: value for name in names if (value := os.environ.get(name))
    })
    runtime = ProviderBundle.from_credentials(credentials)
    with _RUNTIME_LOCK:
        _RUNTIME = runtime
    return runtime


def configure_application(config: ApplicationConfig) -> ProviderBundle:
    """Configure providers from the already-resolved central configuration."""
    global _RUNTIME
    runtime = ProviderBundle.from_application_config(config)
    with _RUNTIME_LOCK:
        _RUNTIME = runtime
    return runtime


def reset_runtime() -> None:
    global _RUNTIME
    with _RUNTIME_LOCK:
        _RUNTIME = ProviderBundle.offline()


def get_orchestrator() -> ProviderBundle:
    """Backward-compatible name for the explicitly configured runtime."""
    return get_runtime()


__all__ = [
    "LiveProviderOrchestrator", "ProviderBundle", "configure_application",
    "configure_environment", "configure_runtime",
    "enrich_candidate", "get_orchestrator", "get_runtime", "reset_runtime",
]
