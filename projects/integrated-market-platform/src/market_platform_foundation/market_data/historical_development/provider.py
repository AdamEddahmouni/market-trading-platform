"""Provider-neutral historical market data access."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from .instrument import symbol_from_instrument_id


@dataclass(frozen=True, slots=True)
class ProviderFetchStatus:
    verified: bool
    reason_code: str | None
    provider_id: str


@dataclass(frozen=True, slots=True)
class HistoricalFetchPage:
    session_date: str
    raw_rows: tuple[dict[str, Any], ...]
    provider_response_identity: str
    page_index: int
    reason_code: str | None = None
    provider_gap: bool = False


class HistoricalMarketDataProvider(Protocol):
    provider_id: str
    capability_id: str

    def status(self) -> ProviderFetchStatus: ...

    def fetch_session_day(
        self,
        instrument_id: str,
        session_date: str,
    ) -> tuple[HistoricalFetchPage, ...]: ...


class FixtureHistoricalMarketDataProvider:
    """Bounded fixture rows for CI (no OpenD)."""

    provider_id = "fixture.historical"
    capability_id = "BAR_OHLCV_1M"

    def __init__(self, rows_by_day: Mapping[str, Sequence[Mapping[str, Any]]]) -> None:
        self._rows_by_day = {str(k): tuple(dict(r) for r in v) for k, v in rows_by_day.items()}

    def status(self) -> ProviderFetchStatus:
        return ProviderFetchStatus(verified=True, reason_code=None, provider_id=self.provider_id)

    def fetch_session_day(
        self,
        instrument_id: str,
        session_date: str,
    ) -> tuple[HistoricalFetchPage, ...]:
        rows = self._rows_by_day.get(session_date, ())
        identity = f"fixture:{instrument_id}:{session_date}"
        return (
            HistoricalFetchPage(
                session_date=session_date,
                raw_rows=tuple(dict(r) for r in rows),
                provider_response_identity=identity,
                page_index=0,
            ),
        )


class MoomooOpendHistoricalMarketDataProvider:
    provider_id = "moomoo.opend"
    capability_id = "BAR_OHLCV_1M"
    _MAX_RETRIES = 3
    _RETRY_SLEEP_S = 0.35
    _PAGE_PACE_S = 0.15

    def __init__(self, *, repository_root: Path) -> None:
        self._repository_root = repository_root
        self._last_status: ProviderFetchStatus | None = None

    def status(self) -> ProviderFetchStatus:
        if self._last_status is not None:
            return self._last_status
        from ...providers.adapters.moomoo_opend_equity_quote import (
            opend_endpoint,
            opend_is_loopback,
            opend_reachable,
        )

        host, port = opend_endpoint()
        if not opend_is_loopback(host) or not opend_reachable(host=host, port=port):
            self._last_status = ProviderFetchStatus(
                verified=False,
                reason_code="PROVIDER_UNVERIFIED:OPEND_UNAVAILABLE",
                provider_id=self.provider_id,
            )
            return self._last_status
        module = self._load_kline_module()
        if module is None or not callable(getattr(module, "fetch_history_kline_day_paginated", None)):
            self._last_status = ProviderFetchStatus(
                verified=False,
                reason_code="PROVIDER_UNVERIFIED:TRANSPORT_MISSING",
                provider_id=self.provider_id,
            )
            return self._last_status
        self._last_status = ProviderFetchStatus(
            verified=True,
            reason_code=None,
            provider_id=self.provider_id,
        )
        return self._last_status

    def _load_kline_module(self) -> Any | None:
        import importlib.util
        import sys

        src = str(self._repository_root / "src")
        moomoo_tools = str(self._repository_root / "tools" / "moomoo")
        for entry in (src, moomoo_tools):
            if entry not in sys.path:
                sys.path.insert(0, entry)
        path = self._repository_root / "tools" / "moomoo" / "historical_rth_kline.py"
        if not path.is_file():
            return None
        spec = importlib.util.spec_from_file_location("imp_historical_rth_kline", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:  # noqa: BLE001
            return None
        return module

    def fetch_session_day(
        self,
        instrument_id: str,
        session_date: str,
    ) -> tuple[HistoricalFetchPage, ...]:
        gate = self.status()
        if not gate.verified:
            return (
                HistoricalFetchPage(
                    session_date=session_date,
                    raw_rows=(),
                    provider_response_identity=f"unverified:{session_date}",
                    page_index=0,
                    reason_code=gate.reason_code,
                ),
            )
        module = self._load_kline_module()
        fetcher = getattr(module, "fetch_history_kline_day_paginated", None)
        if not callable(fetcher):
            return (
                HistoricalFetchPage(
                    session_date=session_date,
                    raw_rows=(),
                    provider_response_identity=f"missing-fetcher:{session_date}",
                    page_index=0,
                    reason_code="TRANSPORT_MISSING",
                ),
            )
        symbol = symbol_from_instrument_id(instrument_id)
        pages: list[HistoricalFetchPage] = []
        for attempt in range(self._MAX_RETRIES):
            payload = fetcher(symbol, session_date=session_date, repository_root=self._repository_root)
            reason = payload.get("reason_code") if isinstance(payload, dict) else "MOOMOO_PROTOCOL_ERROR"
            if isinstance(payload, dict) and not reason:
                for index, page in enumerate(payload.get("pages") or ()):
                    rows = page.get("rows") if isinstance(page, dict) else None
                    if not isinstance(rows, list):
                        continue
                    pages.append(
                        HistoricalFetchPage(
                            session_date=session_date,
                            raw_rows=tuple(dict(r) for r in rows if isinstance(r, Mapping)),
                            provider_response_identity=str(
                                page.get("provider_response_identity") or f"{session_date}:{index}"
                            ),
                            page_index=int(index),
                            provider_gap=bool(page.get("provider_gap")),
                        )
                    )
                if pages:
                    return tuple(pages)
            if attempt + 1 < self._MAX_RETRIES:
                time.sleep(self._RETRY_SLEEP_S)
        return (
            HistoricalFetchPage(
                session_date=session_date,
                raw_rows=(),
                provider_response_identity=f"failed:{session_date}",
                page_index=0,
                reason_code=str(reason or "MOOMOO_PROTOCOL_ERROR"),
            ),
        )


def load_fixture_rows_from_json(path: Path) -> dict[str, tuple[dict[str, Any], ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("FIXTURE_SHAPE_INVALID")
    by_day: dict[str, tuple[dict[str, Any], ...]] = {}
    for day, rows in payload.items():
        if isinstance(rows, list):
            by_day[str(day)] = tuple(dict(r) for r in rows if isinstance(r, Mapping))
    return by_day


__all__ = [
    "FixtureHistoricalMarketDataProvider",
    "HistoricalFetchPage",
    "HistoricalMarketDataProvider",
    "MoomooOpendHistoricalMarketDataProvider",
    "ProviderFetchStatus",
    "load_fixture_rows_from_json",
]
