"""Signal calculator registry (BUILD 06)."""

from __future__ import annotations

from .base import SignalCalculator
from .depth import DepthImbalanceCalculator, SIGNAL_DEPTH_IMBALANCE
from .momentum import MomentumSimpleCalculator, SIGNAL_MOMENTUM_SIMPLE
from .order_flow import CvdCalculator, NetSignedShareCalculator, SIGNAL_CVD, SIGNAL_NET_SIGNED_SHARE
from .spread import SpreadAbsCalculator, SpreadBpsCalculator, SIGNAL_SPREAD_ABS, SIGNAL_SPREAD_BPS
from .volatility import RealizedVolCalculator, SIGNAL_REALIZED_VOL
from .volume import RelativeVolumeCalculator, SIGNAL_RELATIVE_VOLUME

DEFAULT_CALCULATORS: tuple[SignalCalculator, ...] = (
  SpreadAbsCalculator(),
  SpreadBpsCalculator(),
  CvdCalculator(),
  NetSignedShareCalculator(),
  DepthImbalanceCalculator(),
  MomentumSimpleCalculator(),
  RealizedVolCalculator(),
  RelativeVolumeCalculator(),
)

ALL_SIGNAL_TYPES: frozenset[str] = frozenset(
  {
    SIGNAL_SPREAD_ABS,
    SIGNAL_SPREAD_BPS,
    SIGNAL_CVD,
    SIGNAL_NET_SIGNED_SHARE,
    SIGNAL_DEPTH_IMBALANCE,
    SIGNAL_MOMENTUM_SIMPLE,
    SIGNAL_REALIZED_VOL,
    SIGNAL_RELATIVE_VOLUME,
  }
)


def build_default_registry() -> dict[str, SignalCalculator]:
  return {calc.signal_type: calc for calc in DEFAULT_CALCULATORS}


__all__ = [
  "ALL_SIGNAL_TYPES",
  "DEFAULT_CALCULATORS",
  "build_default_registry",
]
