from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .base import EvidenceCollector
from .models import CollectorRecord


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


class YfinanceCollector(EvidenceCollector):
    """Opt-in display-only collector (no HTML scraping). Uses yfinance if installed."""

    name = "Yfinance"

    def __init__(self, *, enabled: bool = False) -> None:
        self._enabled = enabled
        self._last_error: str | None = None

    @property
    def configured(self) -> bool:
        if not self._enabled:
            return False
        try:
            import yfinance  # noqa: F401
        except ImportError:
            return False
        return True

    @property
    def capabilities(self) -> list[str]:
        return ["yfinance_news", "yfinance_quote"]

    def poll(
        self, symbols: list[str], *, force: bool = False
    ) -> list[CollectorRecord]:
        if not self.configured:
            return []
        import yfinance as yf

        received = _now()
        records: list[CollectorRecord] = []
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                news = list(getattr(ticker, "news", []) or [])
                info = getattr(ticker, "fast_info", {}) or {}
                last_price = getattr(info, "last_price", None) if not isinstance(info, dict) else info.get("last_price")
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"{type(exc).__name__}: {exc}"
                continue
            headlines = [
                {
                    "headline": item.get("title", ""),
                    "timestamp": str(item.get("providerPublishTime", "")),
                    "provider": self.name,
                }
                for item in news
                if item.get("title")
            ]
            records.append(
                CollectorRecord(
                    symbol=symbol.upper(),
                    payload={"news_count": len(headlines), "last_price": last_price},
                    received_at=received,
                    source_id=self.name,
                    field_hints={
                        "headlines": headlines,
                        "collector_last_price": last_price,
                        "research_admissibility": "RESEARCH_INADMISSIBLE",
                    },
                )
            )
        return records

    @property
    def rate_limit_state(self) -> dict[str, Any]:
        return {"configured": self.configured, "last_error": self._last_error}


__all__ = ["YfinanceCollector"]
