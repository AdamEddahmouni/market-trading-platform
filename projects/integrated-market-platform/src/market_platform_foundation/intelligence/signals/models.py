"""Signal computation request/result models (BUILD 06)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.signal import SignalV1


class ComputationDiagnosticCode(StrEnum):
  """Calculation feasibility codes — not provider-quality codes."""

  INSUFFICIENT_INPUT = "INSUFFICIENT_INPUT"
  MISSING_REQUIRED_EVENT_TYPE = "MISSING_REQUIRED_EVENT_TYPE"
  ZERO_DENOMINATOR = "ZERO_DENOMINATOR"
  UNDEFINED_STATISTIC = "UNDEFINED_STATISTIC"
  UNSUPPORTED_SCOPE = "UNSUPPORTED_SCOPE"
  INPUT_QUALITY_REJECTED = "INPUT_QUALITY_REJECTED"
  INVALID_NUMERIC_INPUT = "INVALID_NUMERIC_INPUT"
  UNSUPPORTED_SIGNAL = "UNSUPPORTED_SIGNAL"
  SNAPSHOT_QUALITY_REJECTED = "SNAPSHOT_QUALITY_REJECTED"


@dataclass(frozen=True, slots=True)
class ComputationDiagnostic:
  signal_type: str
  code: ComputationDiagnosticCode
  message: str
  details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SignalComputationRequest:
  """Immutable computation request."""

  window_ns: int = 300 * 1_000_000_000
  signal_types: frozenset[str] | None = None
  depth_levels: int = 5
  require_all: bool = False
  persist: bool = False
  parameters: dict[str, str] = field(default_factory=dict)

  def __post_init__(self) -> None:
    if self.window_ns <= 0:
      raise ValueError("WINDOW_NS_MUST_BE_POSITIVE")
    if self.depth_levels <= 0:
      raise ValueError("DEPTH_LEVELS_MUST_BE_POSITIVE")


@dataclass(frozen=True, slots=True)
class SignalComputationResult:
  signals: tuple[SignalV1, ...]
  diagnostics: tuple[ComputationDiagnostic, ...] = ()
  skipped_signal_types: tuple[str, ...] = ()
  persisted: tuple[str, ...] = ()

  @property
  def success(self) -> bool:
    return bool(self.signals) or not self.skipped_signal_types


__all__ = [
  "ComputationDiagnostic",
  "ComputationDiagnosticCode",
  "SignalComputationRequest",
  "SignalComputationResult",
]
