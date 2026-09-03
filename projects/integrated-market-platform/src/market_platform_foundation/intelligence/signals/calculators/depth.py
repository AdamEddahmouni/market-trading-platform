"""Depth imbalance calculator (BUILD 06)."""

from __future__ import annotations

from ..models import ComputationDiagnosticCode
from .base import CalculatorContext, CalculatorOutput, build_signal, skip_diagnostic

CALCULATOR_ID = "depth-imbalance-calculator"
CALCULATOR_VERSION = "1"
SIGNAL_DEPTH_IMBALANCE = "depth_imbalance"


class DepthImbalanceCalculator:
  signal_type = SIGNAL_DEPTH_IMBALANCE
  calculator_id = CALCULATOR_ID
  calculator_version = CALCULATOR_VERSION

  def compute(self, ctx: CalculatorContext) -> CalculatorOutput:
    book = ctx.prepared.latest_book()
    if book is None:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.MISSING_REQUIRED_EVENT_TYPE,
        "No BOOK event in snapshot",
      )
    levels = ctx.request.depth_levels
    bids = book.payload.get("bids") or []
    asks = book.payload.get("asks") or []
    if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.INSUFFICIENT_INPUT,
        "Incomplete book payload",
        event_id=book.event_id,
      )
    bid_depth = sum(float(row.get("size") or 0) for row in bids[:levels])
    ask_depth = sum(float(row.get("size") or 0) for row in asks[:levels])
    total = bid_depth + ask_depth
    if total <= 0:
      return skip_diagnostic(
        self.signal_type,
        ComputationDiagnosticCode.ZERO_DENOMINATOR,
        "Zero total depth",
        event_id=book.event_id,
      )
    imbalance = (bid_depth - ask_depth) / total
    params = {"depth_levels": str(levels)}
    return CalculatorOutput(
      signal=build_signal(
        ctx=ctx,
        signal_type=self.signal_type,
        calculator_id=self.calculator_id,
        calculator_version=self.calculator_version,
        value=imbalance,
        unit="dimensionless",
        raw_value=bid_depth - ask_depth,
        normalized_value=imbalance,
        source_events=(book.event_id,),
        parameters=params,
        metadata={
          "bid_depth": str(bid_depth),
          "ask_depth": str(ask_depth),
          "level_count": str(levels),
        },
        windowed=False,
      )
    )


__all__ = ["DepthImbalanceCalculator", "SIGNAL_DEPTH_IMBALANCE"]
