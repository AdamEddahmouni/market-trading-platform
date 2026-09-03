from __future__ import annotations

from datetime import UTC, datetime

from apps.research_screener.collectors.config import CollectorConfig
from apps.research_screener.collectors.scheduler import CollectorScheduler
from apps.research_screener.collectors.store import EvidenceStore
from apps.research_screener.collectors.base import EvidenceCollector
from apps.research_screener.collectors.models import CollectorRecord


class StubCollector(EvidenceCollector):
    name = "Stub"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    @property
    def configured(self) -> bool:
        return True

    def poll(self, symbols: list[str], *, force: bool = False) -> list[CollectorRecord]:
        self.calls.append(list(symbols))
        received = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        return [
            CollectorRecord(
                symbol=symbols[0],
                payload={},
                received_at=received,
                source_id=self.name,
            )
        ]


def test_scheduler_prioritizes_gap_buckets() -> None:
    store = EvidenceStore()
    stub = StubCollector()
    config = CollectorConfig(
        enabled=True,
        tick_seconds=30,
        max_symbols_per_tick=1,
        max_requests_per_minute=60,
        collector_order=["Stub"],
        override_policy="never",
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
    scheduler = CollectorScheduler(
        config=config,
        store=store,
        collectors=[stub],
        universe_fn=lambda: ["LOW", "HIGH"],
        gap_buckets_fn=lambda s: (
            ["SHORT_PRESSURE_INPUTS_MISSING"] if s == "HIGH" else []
        ),
    )
    scheduler._tick()
    assert stub.calls[0] == ["HIGH"]
    assert store.get("HIGH")
