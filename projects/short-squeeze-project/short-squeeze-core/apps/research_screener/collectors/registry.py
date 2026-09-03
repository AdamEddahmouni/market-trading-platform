from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .api_optional import AlphaVantageQuoteCollector, PolygonQuoteCollector
from .config import CollectorConfig
from .finra_published_si import FinraDailyVolumeCollector, FinraPublishedSICollector
from .rss_news import RssNewsCollector
from .sec_rss import SecRssCollector
from .social_api import RedditApiCollector, StocktwitsApiCollector
from .yfinance_collector import YfinanceCollector

if TYPE_CHECKING:
    from .base import EvidenceCollector


def build_collectors(
    config: CollectorConfig,
    *,
    sec_user_agent: str | None = None,
) -> list[EvidenceCollector]:
    if not config.enabled:
        return []
    default_si_fixture = os.environ.get("FINRA_SI_FIXTURE_PATH")
    if not default_si_fixture:
        from ..paths import repository_root

        candidate = (
            repository_root()
            / "tests"
            / "fixtures"
            / "collectors"
            / "finra_si_sample.txt"
        )
        if candidate.is_file():
            default_si_fixture = str(candidate)

    si_url = config.finra_si_url
    si_fixture = config.finra_si_fixture_path or default_si_fixture
    if not si_url and not si_fixture:
        si_url = None
        si_fixture = None

    registry: dict[str, EvidenceCollector] = {
        "FinraPublishedSI": FinraPublishedSICollector(
            enabled=config.finra_si_enabled,
            data_url=si_url,
            fixture_path=si_fixture if not si_url else None,
        ),
        "FinraDailyVolume": FinraDailyVolumeCollector(
            enabled=config.finra_daily_volume_enabled,
            url_template=config.finra_daily_url_template,
        ),
        "RssNews": RssNewsCollector(enabled=config.rss_news_enabled),
        "SecRss": SecRssCollector(
            enabled=config.sec_rss_enabled,
            user_agent=sec_user_agent or os.environ.get("SEC_USER_AGENT", ""),
        ),
        "Polygon": PolygonQuoteCollector(
            enabled=config.polygon_enabled,
        ),
        "AlphaVantage": AlphaVantageQuoteCollector(
            enabled=config.alpha_vantage_enabled,
        ),
        "Yfinance": YfinanceCollector(enabled=config.yfinance_enabled),
        "Reddit": RedditApiCollector(enabled=config.reddit_enabled),
        "Stocktwits": StocktwitsApiCollector(enabled=config.stocktwits_enabled),
    }
    ordered: list[EvidenceCollector] = []
    seen: set[str] = set()
    for name in config.collector_order:
        collector = registry.get(name)
        if collector is None or name in seen:
            continue
        seen.add(name)
        ordered.append(collector)
    for name, collector in registry.items():
        if name not in seen:
            ordered.append(collector)
    return ordered


__all__ = ["build_collectors"]
