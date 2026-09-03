"""Relative volume calculator — snapshot-internal baseline only (BUILD 06)."""

from __future__ import annotations

from ..models import ComputationDiagnosticCode
from ..trade_direction import TradeSide, classify_trades_in_window
from .base import CalculatorContext, CalculatorOutput, build_signal, skip_diagnostic

CALCULATOR_ID = "relative-volume-calculator"
CALCULATOR_VERSION = "1"
SIGNAL_RELATIVE_VOLUME = "relative_volume"


def _window_volume(ctx: CalculatorContext, *, start_offset_ns: int, end_offset_ns: int) -> float:
  start_ns = ctx.decision_time_ns - start_offset_ns
  end_ns = ctx.decision_time_ns - end_offset_ns
  total = 0.0
  for trade in ctx.prepared.trades:
    if trade.available_time_ns > ctx.decision_time_ns:
      continue
    if trade.event_time_ns <= start_ns or trade.event_time_ns > end_ns:
      continue
    try:
      total += float(trade.payload.get("quantity") or 0)
    except (TypeError, ValueError):
      continue
  return total


class RelativeVolumeCalculator:
  signal_type = SIGNAL_RELATIVE_VOLUME
  calculator_id = CALCULATOR_ID
  calculator_version = CALCULATOR_VERSION

  def compute(self, ctx: CalculatorContext) -> CalculatorOutput:
    window = ctx.window_ns
    current_volume = _window_volume(ctx, start_offset_ns=window, end_offset_ns=0)
    classified, _, _ = classify_trades_in_window(ctx.prepared, window_ns=window)
    if not classified and current_volume <= 0:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INSUFFICIENT_INPUT,
        "No trades in current window",
      )
    baseline_volume = _window_volume(ctx, start_offset_ns=2 * window, end_offset_ns=window)
    if baseline_volume <= 0:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.ZERO_DENOMINATOR,
        "Baseline window volume is zero",
        current_volume=current_volume,
      )
    ratio = current_volume / baseline_volume
    event_ids = tuple(trade.event_id for trade, _, _, _ in classified)
    return CalculatorOutput(
      signal=build_signal(
        ctx=ctx,
        signal_type=self.signal_type,
        calculator_id=self.calculator_id,
        calculator_version=self.calculator_version,
        value=ratio,
        unit="ratio",
        raw_value=current_volume,
        normalized_value=ratio,
        source_events=event_ids,
        metadata={
          "baseline_volume": str(baseline_volume),
          "current_volume": str(current_volume),
          "baseline_source": "snapshot_prior_window",
        },
      )
    )


__all__ = ["RelativeVolumeCalculator", "SIGNAL_RELATIVE_VOLUME"]
