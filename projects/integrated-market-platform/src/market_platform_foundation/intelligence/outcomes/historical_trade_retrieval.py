"""Historical TRADE retrieval port for post-horizon label evidence (Lane C)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from .label_evidence import (
    RETRIEVAL_BEFORE_TERMINAL_WINDOW_END,
    LabelEvidenceError,
    assert_retrieval_not_before_terminal_window,
)


class HistoricalTradeRetrievalPort(Protocol):
    """Injected provider adapter for explicit past-window TRADE retrieval."""

    def fetch_trades_for_window(
        self,
        *,
        instrument_id: str,
        start_time_ns: int,
        end_time_ns: int,
        request_time_ns: int,
        terminal_window_end_ns: int,
        retrieval_params: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class HistoricalTradeRetrievalResult:
    accepted: bool
    trades: tuple[dict[str, Any], ...] = ()
    provider_id: str = ""
    capability_id: str = ""
    raw_trade_ref: str = ""
    raw_trade_payload_sha256: str = ""
    reason: str | None = None
    selection: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "trade_count": len(self.trades),
            "provider_id": self.provider_id,
            "capability_id": self.capability_id,
            "raw_trade_ref": self.raw_trade_ref,
            "raw_trade_payload_sha256": self.raw_trade_payload_sha256,
            "reason": self.reason,
            "selection": dict(self.selection),
        }


def retrieve_historical_trades_bounded(
    port: HistoricalTradeRetrievalPort,
    *,
    instrument_id: str,
    start_time_ns: int,
    end_time_ns: int,
    request_time_ns: int,
    terminal_window_end_ns: int,
    retrieval_params: Mapping[str, Any] | None = None,
) -> HistoricalTradeRetrievalResult:
    try:
        assert_retrieval_not_before_terminal_window(
            request_time_ns=request_time_ns,
            terminal_window_end_ns=terminal_window_end_ns,
        )
    except LabelEvidenceError as exc:
        return HistoricalTradeRetrievalResult(
            accepted=False,
            reason=exc.reason_code,
            selection={"details": exc.details},
        )
    payload = port.fetch_trades_for_window(
        instrument_id=instrument_id,
        start_time_ns=start_time_ns,
        end_time_ns=end_time_ns,
        request_time_ns=request_time_ns,
        terminal_window_end_ns=terminal_window_end_ns,
        retrieval_params=retrieval_params,
    )
    trades_raw = payload.get("trades") or payload.get("data") or ()
    if not isinstance(trades_raw, Sequence):
        return HistoricalTradeRetrievalResult(
            accepted=False,
            reason="MALFORMED_PROVIDER_TRADE_RECORD",
        )
    trades = tuple(dict(row) for row in trades_raw if isinstance(row, Mapping))
    return HistoricalTradeRetrievalResult(
        accepted=True,
        trades=trades,
        provider_id=str(payload.get("provider_id") or ""),
        capability_id=str(payload.get("capability_id") or ""),
        raw_trade_ref=str(payload.get("raw_trade_ref") or ""),
        raw_trade_payload_sha256=str(payload.get("raw_trade_payload_sha256") or ""),
        selection=dict(payload.get("selection") or {}),
    )


__all__ = [
    "HistoricalTradeRetrievalPort",
    "HistoricalTradeRetrievalResult",
    "RETRIEVAL_BEFORE_TERMINAL_WINDOW_END",
    "retrieve_historical_trades_bounded",
]
