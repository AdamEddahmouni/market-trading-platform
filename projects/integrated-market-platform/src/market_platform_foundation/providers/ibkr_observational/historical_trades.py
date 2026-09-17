"""Canonical IBKR historical TRADE print normalization (Lane C spike).

Normalizes injected historical tick/trade rows from outer ``tools/ibkr`` surfaces.
Bar OHLCV payloads are rejected — Path A labels require eligible TRADE prints.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

BAR_OHLCV_PAYLOAD_REFUSED = "BAR_OHLCV_PAYLOAD_REFUSED"
MALFORMED_HISTORICAL_TRADE_ROW = "MALFORMED_HISTORICAL_TRADE_ROW"


@dataclass(frozen=True, slots=True)
class ObservationalHistoricalTrade:
    instrument_id: str
    provider: str
    observation_kind: str
    price: float
    size: float
    event_time_ns: int
    available_time_ns: int
    received_time_ns: int | None
    trade_id: str
    exchange: str | None
    raw_timestamp_semantics: str
    availability_semantics: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "provider": self.provider,
            "observation_kind": self.observation_kind,
            "price": self.price,
            "size": self.size,
            "event_time_ns": self.event_time_ns,
            "available_time_ns": self.available_time_ns,
            "received_time_ns": self.received_time_ns,
            "trade_id": self.trade_id,
            "exchange": self.exchange,
            "raw_timestamp_semantics": self.raw_timestamp_semantics,
            "availability_semantics": self.availability_semantics,
        }


def _coerce_time_ns(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        if value > 10_000_000_000_000:
            return value
        if value > 10_000_000_000:
            return value * 1_000_000
        return value * 1_000_000_000
    text = str(value).strip()
    if text.isdigit():
        parsed = int(text)
        if parsed > 10_000_000_000_000:
            return parsed
        if parsed > 10_000_000_000:
            return parsed * 1_000_000
        return parsed * 1_000_000_000
    return None


def normalize_ibkr_historical_trade_row(
    row: Mapping[str, Any],
    *,
    instrument_id: str,
    provider: str = "IBKR",
    received_time_ns: int | None = None,
) -> ObservationalHistoricalTrade:
    if row.get("o") is not None or row.get("open") is not None:
        raise ValueError(BAR_OHLCV_PAYLOAD_REFUSED)
    price_raw = row.get("price") or row.get("p") or row.get("last")
    size_raw = row.get("size") or row.get("s") or row.get("volume") or 0
    event_time_ns = _coerce_time_ns(row.get("t") or row.get("time") or row.get("timestamp"))
    if event_time_ns is None:
        raise ValueError(MALFORMED_HISTORICAL_TRADE_ROW)
    try:
        price = float(price_raw)
        size = float(size_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(MALFORMED_HISTORICAL_TRADE_ROW) from exc
    if price <= 0.0:
        raise ValueError(MALFORMED_HISTORICAL_TRADE_ROW)
    trade_id = str(row.get("trade_id") or row.get("id") or f"{event_time_ns}:{price}:{size}")
    available_time_ns = _coerce_time_ns(row.get("available_time_ns")) or event_time_ns
    return ObservationalHistoricalTrade(
        instrument_id=instrument_id.upper(),
        provider=provider,
        observation_kind="TRADE",
        price=price,
        size=size,
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns,
        received_time_ns=received_time_ns,
        trade_id=trade_id,
        exchange=str(row.get("exchange")) if row.get("exchange") is not None else None,
        raw_timestamp_semantics=str(row.get("raw_timestamp_semantics") or "exchange_event_time"),
        availability_semantics=str(row.get("availability_semantics") or "historical_retrieval"),
    )


def normalize_ibkr_historical_trades_payload(
    payload: Mapping[str, Any],
    *,
    instrument_id: str,
    provider: str = "IBKR",
    received_time_ns: int | None = None,
) -> list[ObservationalHistoricalTrade]:
    rows = payload.get("data")
    if not isinstance(rows, Sequence):
        raise ValueError("historical trades payload missing data sequence")
    return [
        normalize_ibkr_historical_trade_row(
            row,
            instrument_id=instrument_id,
            provider=provider,
            received_time_ns=received_time_ns,
        )
        for row in rows
        if isinstance(row, Mapping)
    ]


__all__ = [
    "BAR_OHLCV_PAYLOAD_REFUSED",
    "MALFORMED_HISTORICAL_TRADE_ROW",
    "ObservationalHistoricalTrade",
    "normalize_ibkr_historical_trade_row",
    "normalize_ibkr_historical_trades_payload",
]
