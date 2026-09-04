"""Deterministic trade-side classification for signed volume (BUILD 06)."""

from __future__ import annotations

from enum import StrEnum

from ...donor_patterns.cvd_formulas import classify_aggressor
from ...market_data.quality import assess_quote
from ..contracts.event import EventV1
from .prepared import PreparedSnapshotState


class TradeSide(StrEnum):
  BUY = "BUY"
  SELL = "SELL"
  UNKNOWN = "UNKNOWN"


def _quote_payload_for_validator(payload: dict) -> dict:
  adapted = dict(payload)
  if "bid" in payload and "bid_price" not in payload:
    adapted["bid_price"] = payload["bid"]
  if "ask" in payload and "ask_price" not in payload:
    adapted["ask_price"] = payload["ask"]
  if "bid_size" in payload and "bid_vol" not in payload:
    adapted["bid_vol"] = payload["bid_size"]
  if "ask_size" in payload and "ask_vol" not in payload:
    adapted["ask_vol"] = payload["ask_size"]
  return adapted


def quote_is_operational(payload: dict) -> bool:
  flags = assess_quote(_quote_payload_for_validator(payload))
  blocked = {"CROSSED_BOOK", "INVALID_QUOTE"}
  return not any(flag in blocked for flag in flags)


def _payload_bid_ask(payload: dict) -> tuple[float | None, float | None]:
  bid = payload.get("bid") or payload.get("bid_price")
  ask = payload.get("ask") or payload.get("ask_price")
  try:
    bid_f = float(bid) if bid is not None else None
    ask_f = float(ask) if ask is not None else None
  except (TypeError, ValueError):
    return None, None
  return bid_f, ask_f


def nearest_quote_before(
  quotes: tuple[EventV1, ...],
  *,
  event_time_ns: int,
  decision_time_ns: int,
) -> EventV1 | None:
  eligible = [
    quote
    for quote in quotes
    if quote.available_time_ns <= decision_time_ns
    and quote.event_time_ns <= event_time_ns
    and quote.event_time_ns <= decision_time_ns
  ]
  if not eligible:
    return None
  return max(eligible, key=lambda row: (row.event_time_ns, row.available_time_ns, row.event_id))


def classify_trade_side(
  trade: EventV1,
  *,
  prepared: PreparedSnapshotState,
  prev_price: float | None,
  prev_dir: float,
) -> tuple[TradeSide, float, str]:
  """
  Trade direction hierarchy:
  1. provider aggressor_side when BUY/SELL
  2. Lee-Ready quote test when operational quote exists
  3. tick-rule fallback when prior price exists
  4. UNKNOWN — excluded from signed/classified volume
  """
  payload = trade.payload
  provider_side = str(payload.get("aggressor_side") or "").upper()
  if provider_side == "BUY":
    qty = float(payload.get("quantity") or 0)
    return TradeSide.BUY, qty, "provider_aggressor"
  if provider_side == "SELL":
    qty = float(payload.get("quantity") or 0)
    return TradeSide.SELL, -qty, "provider_aggressor"

  try:
    price = float(payload.get("price"))
    quantity = float(payload.get("quantity") or 0)
  except (TypeError, ValueError):
    return TradeSide.UNKNOWN, 0.0, "invalid_numeric"

  quote = nearest_quote_before(
    prepared.quotes,
    event_time_ns=trade.event_time_ns,
    decision_time_ns=prepared.decision_time_ns,
  )
  bid: float | None = None
  ask: float | None = None
  if quote is not None and quote_is_operational(quote.payload):
    bid, ask = _payload_bid_ask(quote.payload)

  signed = classify_aggressor(price, quantity, bid, ask, prev_price, prev_dir)
  if signed > 0:
    return TradeSide.BUY, signed, "lee_ready_or_tick"
  if signed < 0:
    return TradeSide.SELL, signed, "lee_ready_or_tick"
  return TradeSide.UNKNOWN, 0.0, "unknown"


def classify_trades_in_window(
  prepared: PreparedSnapshotState,
  *,
  window_ns: int,
) -> tuple[list[tuple[EventV1, TradeSide, float, str]], float | None, float]:
  """Classify trades in window; return classifications, last price, last direction."""
  window_trades = prepared.events_in_time_window(prepared.trades, window_ns=window_ns)
  ordered = sorted(window_trades, key=lambda event: (event.event_time_ns, event.event_id))
  classified: list[tuple[EventV1, TradeSide, float, str]] = []
  prev_price: float | None = None
  prev_dir = 0.0
  for trade in ordered:
    side, signed, method = classify_trade_side(
      trade,
      prepared=prepared,
      prev_price=prev_price,
      prev_dir=prev_dir,
    )
    classified.append((trade, side, signed, method))
    try:
      price = float(trade.payload.get("price"))
      if prev_price is not None:
        if price > prev_price:
          prev_dir = 1.0
        elif price < prev_price:
          prev_dir = -1.0
      prev_price = price
    except (TypeError, ValueError):
      pass
  return classified, prev_price, prev_dir


__all__ = [
  "TradeSide",
  "classify_trade_side",
  "classify_trades_in_window",
  "nearest_quote_before",
  "quote_is_operational",
]
