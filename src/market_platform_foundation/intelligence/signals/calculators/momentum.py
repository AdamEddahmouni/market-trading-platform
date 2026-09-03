"""Momentum return calculator (BUILD 06)."""

from __future__ import annotations

import math

from ..models import ComputationDiagnosticCode
from ..trade_direction import _payload_bid_ask
from .base import CalculatorContext, CalculatorOutput, build_signal, skip_diagnostic

CALCULATOR_ID = "momentum-calculator"
CALCULATOR_VERSION = "1"
SIGNAL_MOMENTUM_SIMPLE = "momentum_simple"


def _trade_price(event) -> float | None:
  try:
    return float(event.payload.get("price"))
  except (TypeError, ValueError):
    return None


def _quote_mid(event) -> float | None:
  bid, ask = _payload_bid_ask(event.payload)
  if bid is None or ask is None or bid <= 0 or ask <= 0:
    return None
  return (bid + ask) / 2.0


class MomentumSimpleCalculator:
  signal_type = SIGNAL_MOMENTUM_SIMPLE
  calculator_id = CALCULATOR_ID
  calculator_version = CALCULATOR_VERSION

  def compute(self, ctx: CalculatorContext) -> CalculatorOutput:
    window_trades = ctx.prepared.events_in_time_window(
      ctx.prepared.trades,
      window_ns=ctx.window_ns,
    )
    prices: list[tuple[int, float, str, str]] = []
    for trade in sorted(window_trades, key=lambda row: (row.event_time_ns, row.event_id)):
      price = _trade_price(trade)
      if price is not None and price > 0:
        prices.append((trade.event_time_ns, price, trade.event_id, "trade"))
    if len(prices) < 2:
      window_quotes = ctx.prepared.events_in_time_window(
        ctx.prepared.quotes,
        window_ns=ctx.window_ns,
      )
      for quote in sorted(window_quotes, key=lambda row: (row.event_time_ns, row.event_id)):
        mid = _quote_mid(quote)
        if mid is not None and mid > 0:
          prices.append((quote.event_time_ns, mid, quote.event_id, "quote_mid"))
    if len(prices) < 2:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INSUFFICIENT_INPUT,
        "Need at least two price observations in window",
      )
    start_price = prices[0][1]
    end_price = prices[-1][1]
    if start_price <= 0:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.ZERO_DENOMINATOR,
        "Start price is zero",
      )
    momentum = end_price / start_price - 1.0
    if not math.isfinite(momentum):
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INVALID_NUMERIC_INPUT,
        "Non-finite momentum",
      )
    source_events = (prices[0][2], prices[-1][2])
    return CalculatorOutput(
      signal=build_signal(
        ctx=ctx,
        signal_type=self.signal_type,
        calculator_id=self.calculator_id,
        calculator_version=self.calculator_version,
        value=momentum,
        unit="decimal_return",
        raw_value=momentum,
        normalized_value=momentum,
        source_events=source_events,
        metadata={
          "price_source_start": prices[0][3],
          "price_source_end": prices[-1][3],
          "return_type": "simple",
        },
      )
    )


__all__ = ["MomentumSimpleCalculator", "SIGNAL_MOMENTUM_SIMPLE"]
