from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from src.ticker_metadata.contract import classify_exception, classify_response
from src.ticker_metadata.models import ProviderCallResult


class YFinanceMetadataAdapter:
    def __init__(
        self,
        *,
        ticker_factory: Callable[[str], object] | None = None,
        utcnow: Callable[[], datetime] | None = None,
    ):
        self._ticker_factory = ticker_factory
        self._utcnow = utcnow or (lambda: datetime.now(timezone.utc))

    def _make_ticker(self, symbol: str) -> object:
        if self._ticker_factory is not None:
            return self._ticker_factory(symbol)
        import yfinance as yf

        return yf.Ticker(symbol)

    def call(self, symbol: str, ordinal: int) -> ProviderCallResult:
        started_at = self._utcnow()
        try:
            ticker = self._make_ticker(symbol)
            response = ticker.get_info()  # type: ignore[attr-defined]
        except Exception as exc:
            classified = classify_exception(exc)
        else:
            classified = classify_response(symbol, response)
        completed_at = self._utcnow()
        return ProviderCallResult(
            ordinal=ordinal,
            started_at_utc=started_at,
            completed_at_utc=completed_at,
            classified=classified,
        )
