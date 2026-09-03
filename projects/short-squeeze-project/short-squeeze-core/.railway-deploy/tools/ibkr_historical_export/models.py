"""ibapi-free data structures for captured contracts, bars, and request results.

All numeric provider values are carried as strings/ints exactly as the provider
delivered them (the ``ibapi`` -> primitive conversion happens in the session layer).
Nothing here rounds, cleans, or infers values.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .statuses import ContractStatus, HistoricalStatus


@dataclass(frozen=True, slots=True)
class ContractCandidate:
    """One contract-details candidate, preserved verbatim."""

    con_id: int
    symbol: str
    local_symbol: str
    sec_type: str
    currency: str
    exchange: str
    primary_exchange: str
    trading_class: str
    long_name: str
    time_zone_id: str
    trading_hours: str
    liquid_hours: str
    valid_exchanges: str

    def as_dict(self) -> dict:
        return {
            "con_id": self.con_id,
            "symbol": self.symbol,
            "local_symbol": self.local_symbol,
            "sec_type": self.sec_type,
            "currency": self.currency,
            "exchange": self.exchange,
            "primary_exchange": self.primary_exchange,
            "trading_class": self.trading_class,
            "long_name": self.long_name,
            "time_zone_id": self.time_zone_id,
            "trading_hours": self.trading_hours,
            "liquid_hours": self.liquid_hours,
            "valid_exchanges": self.valid_exchanges,
        }


@dataclass(frozen=True, slots=True)
class ContractResolution:
    """Deterministic, outcome-blind resolution for one frozen symbol."""

    requested_symbol: str
    status: ContractStatus
    candidates: tuple[ContractCandidate, ...] = ()
    resolved: ContractCandidate | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class BarRecord:
    """One historical bar, values preserved exactly as returned by the provider."""

    request_id: int
    request_name: str
    requested_symbol: str
    resolved_con_id: int
    timestamp_epoch: int
    timestamp_utc: str
    open: str
    high: str
    low: str
    close: str
    volume: str | None
    wap: str | None
    bar_count: int

    def as_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "request_name": self.request_name,
            "requested_symbol": self.requested_symbol,
            "resolved_con_id": self.resolved_con_id,
            "timestamp_epoch": self.timestamp_epoch,
            "timestamp_utc": self.timestamp_utc,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "wap": self.wap,
            "bar_count": self.bar_count,
        }


@dataclass(frozen=True, slots=True)
class ApiDiagnostic:
    """One provider API message (error/notification). Preserved in private evidence."""

    request_id: int
    error_code: int
    error_message: str
    error_time: int = 0
    request_name: str = ""
    requested_symbol: str = ""


@dataclass(frozen=True, slots=True)
class HistoricalRequestResult:
    """Result of one historical request for one resolved contract."""

    request_name: str
    requested_symbol: str
    resolved_con_id: int
    status: HistoricalStatus
    bars: tuple[BarRecord, ...] = ()
    error_codes: tuple[int, ...] = ()
    retrieval_started_at: str = ""
    retrieval_completed_at: str = ""
    first_timestamp_utc: str | None = None
    last_timestamp_utc: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def bar_count(self) -> int:
        return len(self.bars)


__all__ = [
    "ContractCandidate",
    "ContractResolution",
    "BarRecord",
    "ApiDiagnostic",
    "HistoricalRequestResult",
]
