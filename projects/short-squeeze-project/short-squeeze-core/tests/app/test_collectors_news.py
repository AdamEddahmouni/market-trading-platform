from __future__ import annotations

from apps.research_screener.news_live import NewsOrchestrator


def test_register_external_headlines_dedupes() -> None:
    orch = NewsOrchestrator()
    items = [
        {"headline": "GME rises on volume", "timestamp": "2026-01-01T00:00:00Z", "provider": "RssNews"},
        {"headline": "GME rises on volume", "timestamp": "2026-01-02T00:00:00Z", "provider": "RssNews"},
    ]
    orch.register_external_headlines("GME", items)
    with orch._lock:
        cached = orch._cache.get("GME", (0, []))[1]
    assert len(cached) == 1
