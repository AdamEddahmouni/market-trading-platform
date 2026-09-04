"""CVD and net signed share calculators (BUILD 06)."""

from __future__ import annotations

from ..models import ComputationDiagnosticCode
from ..trade_direction import TradeSide, classify_trades_in_window
from .base import CalculatorContext, CalculatorOutput, build_signal, skip_diagnostic

CALCULATOR_ID = "cvd-calculator"
CALCULATOR_VERSION = "1"
SIGNAL_CVD = "cvd"
SIGNAL_NET_SIGNED_SHARE = "net_signed_share"


class CvdCalculator:
  signal_type = SIGNAL_CVD
  calculator_id = CALCULATOR_ID
  calculator_version = CALCULATOR_VERSION

  def compute(self, ctx: CalculatorContext) -> CalculatorOutput:
    classified, _, _ = classify_trades_in_window(ctx.prepared, window_ns=ctx.window_ns)
    if not classified:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INSUFFICIENT_INPUT,
        "No trades in calculation window",
      )
    cvd = 0.0
    event_ids: list[str] = []
    for trade, side, signed, _ in classified:
      event_ids.append(trade.event_id)
      if side != TradeSide.UNKNOWN:
        cvd += signed
    if not any(row[1] != TradeSide.UNKNOWN for row in classified):
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INSUFFICIENT_INPUT,
        "No classified trades in window",
      )
    return CalculatorOutput(
      signal=build_signal(
        ctx=ctx,
        signal_type=self.signal_type,
        calculator_id=self.calculator_id,
        calculator_version=self.calculator_version,
        value=cvd,
        unit="shares",
        raw_value=cvd,
        source_events=tuple(event_ids),
        metadata={"unknown_excluded": "true"},
      )
    )


class NetSignedShareCalculator:
  signal_type = SIGNAL_NET_SIGNED_SHARE
  calculator_id = CALCULATOR_ID
  calculator_version = CALCULATOR_VERSION

  def compute(self, ctx: CalculatorContext) -> CalculatorOutput:
    classified, _, _ = classify_trades_in_window(ctx.prepared, window_ns=ctx.window_ns)
    if not classified:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INSUFFICIENT_INPUT,
        "No trades in calculation window",
      )
    buyer_volume = 0.0
    seller_volume = 0.0
    event_ids: list[str] = []
    unknown_count = 0
    for trade, side, signed, _ in classified:
      event_ids.append(trade.event_id)
      if side == TradeSide.BUY:
        buyer_volume += abs(signed)
      elif side == TradeSide.SELL:
        seller_volume += abs(signed)
      else:
        unknown_count += 1
    classified_volume = buyer_volume + seller_volume
    if classified_volume <= 0:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.ZERO_DENOMINATOR,
        "Zero classified volume in window",
        unknown_count=unknown_count,
      )
    nss = (buyer_volume - seller_volume) / classified_volume
    cvd = buyer_volume - seller_volume
    return CalculatorOutput(
      signal=build_signal(
        ctx=ctx,
        signal_type=self.signal_type,
        calculator_id=self.calculator_id,
        calculator_version=self.calculator_version,
        value=nss,
        unit="dimensionless",
        raw_value=cvd,
        normalized_value=nss,
        source_events=tuple(event_ids),
        metadata={
          "buyer_volume": str(buyer_volume),
          "seller_volume": str(seller_volume),
          "unknown_count": str(unknown_count),
        },
      )
    )


__all__ = [
  "CvdCalculator",
  "NetSignedShareCalculator",
  "SIGNAL_CVD",
  "SIGNAL_NET_SIGNED_SHARE",
]
