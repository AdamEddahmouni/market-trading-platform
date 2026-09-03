from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import requests

from .base import EvidenceCollector
from .models import CollectorRecord


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


class PolygonQuoteCollector(EvidenceCollector):
    name = "Polygon"

    def __init__(self, *, enabled: bool = False, api_key: str | None = None) -> None:
        self._enabled = enabled
        self._api_key = api_key or os.environ.get("POLYGON_API_KEY")

    @property
    def configured(self) -> bool:
        return self._enabled and bool(self._api_key)

    @property
    def capabilities(self) -> list[str]:
        return ["last_price"]

    def poll(
        self, symbols: list[str], *, force: bool = False
    ) -> list[CollectorRecord]:
        if not self.configured:
            return []
        received = _now()
        records: list[CollectorRecord] = []
        for symbol in symbols:
            url = (
                f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev"
                f"?adjusted=true&apiKey={self._api_key}"
            )
            try:
                response = requests.get(url, timeout=20)
                response.raise_for_status()
                payload = response.json()
                close = payload.get("results", [{}])[0].get("c")
            except Exception:
                continue
            if close is None:
                continue
            records.append(
                CollectorRecord(
                    symbol=symbol.upper(),
                    payload={"close": close},
                    received_at=received,
                    source_id=self.name,
                    field_hints={
                        "collector_last_price": close,
                        "research_admissibility": "RESEARCH_INADMISSIBLE",
                    },
                )
            )
        return records


class AlphaVantageQuoteCollector(EvidenceCollector):
    name = "AlphaVantage"

    def __init__(self, *, enabled: bool = False, api_key: str | None = None) -> None:
        self._enabled = enabled
        self._api_key = api_key or os.environ.get("ALPHA_VANTAGE_API_KEY")

    @property
    def configured(self) -> bool:
        return self._enabled and bool(self._api_key)

    @property
    def capabilities(self) -> list[str]:
        return ["last_price"]

    def poll(
        self, symbols: list[str], *, force: bool = False
    ) -> list[CollectorRecord]:
        if not self.configured:
            return []
        received = _now()
        records: list[CollectorRecord] = []
        for symbol in symbols:
            url = (
                "https://www.alphavantage.co/query"
                f"?function=GLOBAL_QUOTE&symbol={symbol}&apikey={self._api_key}"
            )
            try:
                response = requests.get(url, timeout=20)
                response.raise_for_status()
                quote = response.json().get("Global Quote", {})
                close = quote.get("05. price")
            except Exception:
                continue
            if not close:
                continue
            records.append(
                CollectorRecord(
                    symbol=symbol.upper(),
                    payload={"close": close},
                    received_at=received,
                    source_id=self.name,
                    field_hints={
                        "collector_last_price": float(close),
                        "research_admissibility": "RESEARCH_INADMISSIBLE",
                    },
                )
            )
        return records


__all__ = ["AlphaVantageQuoteCollector", "PolygonQuoteCollector"]
