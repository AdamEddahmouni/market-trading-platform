"""Read-only market-news provider clients and aggregation."""

from .aggregator import NewsAggregator, aggregate_news_items
from .providers import FinnhubNewsClient, NewsApiClient

__all__ = [
    "FinnhubNewsClient",
    "NewsAggregator",
    "NewsApiClient",
    "aggregate_news_items",
]
