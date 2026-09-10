"""Fixture/reference news provider for deterministic tests and replay."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import NewsArticleEvent
from .normalize import normalize_raw_item

DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "news"
    / "canonical_replay_pack.json"
)


class FixtureNewsProvider:
    """Offline provider that normalizes fixture payloads into canonical events."""

    provider_id = "news.fixture"
    capability = "deterministic_news_fixture"
    entitlement = "NEWS_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_FIXTURE_PATH
        self._fixture = self._load_fixture()

    def _load_fixture(self) -> dict[str, Any]:
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("NEWS_FIXTURE_INVALID")
        return payload

    def fetch_events(self) -> list[NewsArticleEvent]:
        items = self._fixture.get("items", [])
        if not isinstance(items, list):
            return []
        events: list[NewsArticleEvent] = []
        for row in items:
            if not isinstance(row, dict):
                continue
            provider_id = str(row.get("provider_id") or self.provider_id)
            source_id = str(row.get("source_id") or "fixture_wire")
            retrieved_time = str(row.get("retrieved_time") or "")
            events.append(
                normalize_raw_item(
                    row,
                    provider_id=provider_id,
                    source_id=source_id,
                    retrieved_time=retrieved_time,
                )
            )
        return events

    def fixture_metadata(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "fixture_path": str(self.fixture_path),
            "scenario_count": len(self._fixture.get("items", [])),
            "description": str(self._fixture.get("description", "")),
        }


__all__ = ["DEFAULT_FIXTURE_PATH", "FixtureNewsProvider"]
