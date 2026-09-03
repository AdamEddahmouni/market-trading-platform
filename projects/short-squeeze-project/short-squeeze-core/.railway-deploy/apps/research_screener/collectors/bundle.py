from __future__ import annotations

import threading
from typing import Any, Callable

from .config import CollectorConfig, resolve_collector_config
from .registry import build_collectors
from .scheduler import CollectorScheduler
from .store import EvidenceStore

_BUNDLE: CollectorBundle | None = None
_LOCK = threading.Lock()


class CollectorBundle:
    """Parallel to ProviderBundle: background evidence harvest + store."""

    def __init__(
        self,
        *,
        config: CollectorConfig,
        store: EvidenceStore,
        collectors: list,
        scheduler: CollectorScheduler,
    ) -> None:
        self.config = config
        self.store = store
        self.collectors = collectors
        self.scheduler = scheduler

    @classmethod
    def offline(cls) -> CollectorBundle:
        config = resolve_collector_config()
        config = CollectorConfig(
            enabled=False,
            tick_seconds=config.tick_seconds,
            max_symbols_per_tick=config.max_symbols_per_tick,
            max_requests_per_minute=config.max_requests_per_minute,
            collector_order=config.collector_order,
            override_policy=config.override_policy,
            finra_si_enabled=False,
            finra_daily_volume_enabled=False,
            rss_news_enabled=False,
            sec_rss_enabled=False,
            yfinance_enabled=False,
            reddit_enabled=False,
            stocktwits_enabled=False,
            polygon_enabled=False,
            alpha_vantage_enabled=False,
            finra_si_url=None,
            finra_si_fixture_path=None,
            finra_daily_url_template=None,
        )
        store = EvidenceStore()
        scheduler = CollectorScheduler(
            config=config,
            store=store,
            collectors=[],
            universe_fn=lambda: [],
            gap_buckets_fn=lambda _s: [],
        )
        return cls(config=config, store=store, collectors=[], scheduler=scheduler)

    @classmethod
    def from_environment(
        cls,
        *,
        universe_fn: Callable[[], list[str]] | None = None,
        gap_buckets_fn: Callable[[str], list[str]] | None = None,
        on_headlines: Callable[[str, list[dict[str, Any]]], None] | None = None,
        sec_user_agent: str | None = None,
    ) -> CollectorBundle:
        config = resolve_collector_config()
        store = EvidenceStore()
        collectors = build_collectors(config, sec_user_agent=sec_user_agent)
        scheduler = CollectorScheduler(
            config=config,
            store=store,
            collectors=collectors,
            universe_fn=universe_fn or (lambda: []),
            gap_buckets_fn=gap_buckets_fn or (lambda _s: []),
            on_headlines=on_headlines,
        )
        return cls(
            config=config,
            store=store,
            collectors=collectors,
            scheduler=scheduler,
        )

    def start(self) -> None:
        self.scheduler.start()

    def stop(self) -> None:
        self.scheduler.stop()

    def status(self) -> dict[str, Any]:
        return self.scheduler.status()


def configure_collector_bundle(bundle: CollectorBundle) -> CollectorBundle:
    global _BUNDLE
    with _LOCK:
        if _BUNDLE is not None:
            _BUNDLE.stop()
        _BUNDLE = bundle
        return bundle


def get_collector_bundle() -> CollectorBundle:
    global _BUNDLE
    with _LOCK:
        if _BUNDLE is None:
            _BUNDLE = CollectorBundle.offline()
        return _BUNDLE


__all__ = [
    "CollectorBundle",
    "configure_collector_bundle",
    "get_collector_bundle",
]
