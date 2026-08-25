"""Spread and midpoint calculators (BUILD 06)."""

from __future__ import annotations

from ..models import ComputationDiagnosticCode
from ..trade_direction import _payload_bid_ask, quote_is_operational
from .base import CalculatorContext, CalculatorOutput, build_signal, skip_diagnostic

CALCULATOR_ID = "spread-calculator"
CALCULATOR_VERSION = "1"
SIGNAL_SPREAD_ABS = "spread_abs"
SIGNAL_SPREAD_BPS = "spread_bps"


class SpreadAbsCalculator:
  signal_type = SIGNAL_SPREAD_ABS
  calculator_id = CALCULATOR_ID
  calculator_version = CALCULATOR_VERSION

  def compute(self, ctx: CalculatorContext) -> CalculatorOutput:
    quote = ctx.prepared.latest_quote()
    if quote is None:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.MISSING_REQUIRED_EVENT_TYPE,
        "No QUOTE event in snapshot",
      )
    if not quote_is_operational(quote.payload):
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INPUT_QUALITY_REJECTED,
        "Quote failed operational quality checks",
        event_id=quote.event_id,
      )
    bid, ask = _payload_bid_ask(quote.payload)
    if bid is None or ask is None or bid <= 0 or ask <= 0:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INVALID_NUMERIC_INPUT,
        "Invalid bid/ask on quote",
        event_id=quote.event_id,
      )
    spread_abs = ask - bid
    return CalculatorOutput(
      signal=build_signal(
        ctx=ctx,
        signal_type=self.signal_type,
        calculator_id=self.calculator_id,
        calculator_version=self.calculator_version,
        value=spread_abs,
        unit="USD/share",
        raw_value=spread_abs,
        source_events=(quote.event_id,),
        metadata={"price_source": "quote"},
        windowed=False,
      )
    )


class SpreadBpsCalculator:
  signal_type = SIGNAL_SPREAD_BPS
  calculator_id = CALCULATOR_ID
  calculator_version = CALCULATOR_VERSION

  def compute(self, ctx: CalculatorContext) -> CalculatorOutput:
    quote = ctx.prepared.latest_quote()
    if quote is None:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.MISSING_REQUIRED_EVENT_TYPE,
        "No QUOTE event in snapshot",
      )
    if not quote_is_operational(quote.payload):
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INPUT_QUALITY_REJECTED,
        "Quote failed operational quality checks",
        event_id=quote.event_id,
      )
    bid, ask = _payload_bid_ask(quote.payload)
    if bid is None or ask is None or bid <= 0 or ask <= 0:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INVALID_NUMERIC_INPUT,
        "Invalid bid/ask on quote",
        event_id=quote.event_id,
      )
    mid = (bid + ask) / 2.0
    if mid <= 0:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.ZERO_DENOMINATOR,
        "Midpoint is zero",
      )
    spread_bps = (ask - bid) / mid * 10_000.0
    return CalculatorOutput(
      signal=build_signal(
        ctx=ctx,
        signal_type=self.signal_type,
        calculator_id=self.calculator_id,
        calculator_version=self.calculator_version,
        value=spread_bps,
        unit="basis_points",
        raw_value=ask - bid,
        normalized_value=spread_bps,
        source_events=(quote.event_id,),
        metadata={"price_source": "quote_mid"},
        windowed=False,
      )
    )


__all__ = [
  "SpreadAbsCalculator",
  "SpreadBpsCalculator",
  "SIGNAL_SPREAD_ABS",
  "SIGNAL_SPREAD_BPS",
]
