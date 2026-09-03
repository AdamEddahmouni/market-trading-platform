from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: str) -> bool:
    raw = os.environ.get(name, default).strip().lower()
    return raw in {"true", "1", "yes", "on"}


def _int(name: str, default: str, *, minimum: int, maximum: int) -> int:
    value = int(os.environ.get(name, default))
    return max(minimum, min(maximum, value))


@dataclass(frozen=True, slots=True)
class CollectorConfig:
    enabled: bool
    tick_seconds: int
    max_symbols_per_tick: int
    max_requests_per_minute: int
    collector_order: list[str]
    override_policy: str
    finra_si_enabled: bool
    finra_daily_volume_enabled: bool
    rss_news_enabled: bool
    sec_rss_enabled: bool
    yfinance_enabled: bool
    reddit_enabled: bool
    stocktwits_enabled: bool
    polygon_enabled: bool
    alpha_vantage_enabled: bool
    finra_si_url: str | None
    finra_si_fixture_path: str | None
    finra_daily_url_template: str | None


def resolve_collector_config() -> CollectorConfig:
    order_raw = os.environ.get(
        "COLLECTOR_ORDER",
        "FinraPublishedSI,FinraDailyVolume,RssNews,SecRss,Polygon,AlphaVantage,"
        "Yfinance,Reddit,Stocktwits",
    )
    return CollectorConfig(
        enabled=_bool("COLLECTORS_ENABLED", "true"),
        tick_seconds=_int("COLLECTOR_TICK_SECONDS", "30", minimum=5, maximum=600),
        max_symbols_per_tick=_int(
            "COLLECTOR_MAX_SYMBOLS_PER_TICK", "10", minimum=1, maximum=50
        ),
        max_requests_per_minute=_int(
            "COLLECTOR_MAX_REQUESTS_PER_MINUTE", "60", minimum=1, maximum=600
        ),
        collector_order=[p.strip() for p in order_raw.split(",") if p.strip()],
        override_policy=os.environ.get(
            "COLLECTOR_OVERRIDE_POLICY", "never"
        ).strip().lower(),
        finra_si_enabled=_bool("FINRA_SI_COLLECTOR_ENABLED", "true"),
        finra_daily_volume_enabled=_bool("FINRA_DAILY_VOLUME_COLLECTOR_ENABLED", "true"),
        rss_news_enabled=_bool("RSS_NEWS_ENABLED", "true"),
        sec_rss_enabled=_bool("SEC_RSS_COLLECTOR_ENABLED", "true"),
        yfinance_enabled=_bool("YFINANCE_COLLECTOR_ENABLED", "false"),
        reddit_enabled=_bool("REDDIT_COLLECTOR_ENABLED", "false"),
        stocktwits_enabled=_bool("STOCKTWITS_COLLECTOR_ENABLED", "false"),
        polygon_enabled=_bool("POLYGON_COLLECTOR_ENABLED", "false"),
        alpha_vantage_enabled=_bool("ALPHA_VANTAGE_COLLECTOR_ENABLED", "false"),
        finra_si_url=os.environ.get("FINRA_SI_DATA_URL") or None,
        finra_si_fixture_path=os.environ.get("FINRA_SI_FIXTURE_PATH") or None,
        finra_daily_url_template=os.environ.get("FINRA_DAILY_VOLUME_URL_TEMPLATE")
        or None,
    )


__all__ = ["CollectorConfig", "resolve_collector_config"]
