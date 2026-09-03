"""Realized volatility calculator (BUILD 06)."""

from __future__ import annotations

import math

from ..models import ComputationDiagnosticCode
from ..trade_direction import _payload_bid_ask
from .base import CalculatorContext, CalculatorOutput, build_signal, skip_diagnostic

CALCULATOR_ID = "realized-volatility-calculator"
CALCULATOR_VERSION = "1"
SIGNAL_REALIZED_VOL = "realized_vol"


def _observation_prices(ctx: CalculatorContext) -> list[tuple[int, float, str]]:
  window_trades = ctx.prepared.events_in_time_window(
    ctx.prepared.trades,
    window_ns=ctx.window_ns,
  )
  rows: list[tuple[int, float, str]] = []
  for trade in sorted(window_trades, key=lambda row: (row.event_time_ns, row.event_id)):
    try:
      price = float(trade.payload.get("price"))
    except (TypeError, ValueError):
      continue
    if price > 0:
      rows.append((trade.event_time_ns, price, trade.event_id))
  if len(rows) < 2:
    window_quotes = ctx.prepared.events_in_time_window(
      ctx.prepared.quotes,
      window_ns=ctx.window_ns,
    )
    for quote in sorted(window_quotes, key=lambda row: (row.event_time_ns, row.event_id)):
      bid, ask = _payload_bid_ask(quote.payload)
      if bid is not None and ask is not None and bid > 0 and ask > 0:
        rows.append((quote.event_time_ns, (bid + ask) / 2.0, quote.event_id))
  return rows


def _sample_std_log_returns(prices: list[float]) -> float | None:
  if len(prices) < 2:
    return None
  log_returns: list[float] = []
  for index in range(1, len(prices)):
    if prices[index - 1] <= 0 or prices[index] <= 0:
      continue
    log_returns.append(math.log(prices[index] / prices[index - 1]))
  if len(log_returns) < 1:
    return None
  if all(abs(ret) == 0.0 for ret in log_returns):
    return 0.0
  if len(log_returns) < 2:
    return 0.0
  mean = sum(log_returns) / len(log_returns)
  variance = sum((ret - mean) ** 2 for ret in log_returns) / (len(log_returns) - 1)
  return math.sqrt(variance)


class RealizedVolCalculator:
  signal_type = SIGNAL_REALIZED_VOL
  calculator_id = CALCULATOR_ID
  calculator_version = CALCULATOR_VERSION

  def compute(self, ctx: CalculatorContext) -> CalculatorOutput:
    observations = _observation_prices(ctx)
    if len(observations) < 2:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INSUFFICIENT_INPUT,
        "Need at least two price observations",
      )
    prices = [row[1] for row in observations]
    vol = _sample_std_log_returns(prices)
    if vol is None:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.UNDEFINED_STATISTIC,
        "Could not compute log-return volatility",
      )
    if not math.isfinite(vol):
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INVALID_NUMERIC_INPUT,
        "Non-finite volatility",
      )
    source_events = tuple({row[2] for row in observations[:1] + observations[-1:]})
    return CalculatorOutput(
      signal=build_signal(
        ctx=ctx,
        signal_type=self.signal_type,
        calculator_id=self.calculator_id,
        calculator_version=self.calculator_version,
        value=vol,
        unit="log_return_std",
        raw_value=vol,
        normalized_value=vol,
        source_events=source_events,
        metadata={
          "return_type": "log",
          "annualized": "false",
          "sample_count": str(len(prices)),
        },
      )
    )


__all__ = ["RealizedVolCalculator", "SIGNAL_REALIZED_VOL"]
