"""Signal calculator protocol and shared helpers (BUILD 06)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ...contracts.common import (
  ContractKind,
  ContractReference,
  INTELLIGENCE_SCHEMA_VERSION,
  QualityState,
  QualitySummary,
  TimeHorizonNs,
)
from ...contracts.signal import SignalV1
from ..identity import derive_signal_id
from ..models import ComputationDiagnostic, ComputationDiagnosticCode, SignalComputationRequest
from ..prepared import PreparedSnapshotState


@dataclass(frozen=True, slots=True)
class CalculatorOutput:
  signal: SignalV1 | None = None
  diagnostic: ComputationDiagnostic | None = None


@dataclass(frozen=True, slots=True)
class CalculatorContext:
  prepared: PreparedSnapshotState
  request: SignalComputationRequest

  @property
  def snapshot(self):
    return self.prepared.snapshot

  @property
  def decision_time_ns(self) -> int:
    return self.prepared.decision_time_ns

  @property
  def window_ns(self) -> int:
    return self.request.window_ns


class SignalCalculator(Protocol):
  signal_type: str
  calculator_id: str
  calculator_version: str

  def compute(self, ctx: CalculatorContext) -> CalculatorOutput: ...


def signal_quality_from_snapshot(snapshot_quality: QualitySummary) -> QualitySummary:
  if snapshot_quality.state == QualityState.INVALID:
    return QualitySummary(state=QualityState.INVALID, flags=snapshot_quality.flags)
  if snapshot_quality.state == QualityState.DEGRADED:
    return QualitySummary(state=QualityState.DEGRADED, flags=snapshot_quality.flags)
  return QualitySummary(state=QualityState.GOOD, flags=())


def build_signal(
  *,
  ctx: CalculatorContext,
  signal_type: str,
  calculator_id: str,
  calculator_version: str,
  value: float,
  unit: str,
  raw_value: float | None = None,
  normalized_value: float | None = None,
  source_events: tuple[str, ...] = (),
  parameters: dict[str, str] | None = None,
  metadata: dict[str, str] | None = None,
  windowed: bool = True,
) -> SignalV1:
  snapshot = ctx.snapshot
  window_ns = ctx.window_ns if windowed else None
  signal_id = derive_signal_id(
    source_snapshot_id=snapshot.snapshot_id,
    signal_type=signal_type,
    scope=snapshot.scope,
    window_ns=window_ns,
    calculator_id=calculator_id,
    calculator_version=calculator_version,
    parameters=parameters,
  )
  lineage = {
    "calculator_id": calculator_id,
    "calculator_version": calculator_version,
  }
  if parameters:
    for key, val in sorted(parameters.items()):
      lineage[f"param_{key}"] = val
  calculation_window = TimeHorizonNs(duration_ns=ctx.window_ns) if windowed else None
  return SignalV1(
    signal_id=signal_id,
    schema_version=INTELLIGENCE_SCHEMA_VERSION,
    signal_type=signal_type,
    scope=snapshot.scope,
    as_of_time_ns=snapshot.decision_time_ns,
    value=value,
    quality=signal_quality_from_snapshot(snapshot.quality),
    source_snapshot_ref=ContractReference(
      kind=ContractKind.SNAPSHOT.value,
      id=snapshot.snapshot_id,
    ),
    source_event_refs=tuple(
      ContractReference(kind=ContractKind.EVENT.value, id=event_id) for event_id in source_events
    ),
    raw_value=raw_value,
    normalized_value=normalized_value,
    unit=unit,
    calculation_window=calculation_window,
    calculation_lineage=lineage,
    metadata=dict(metadata or {}),
  )


def skip_diagnostic(
  signal_type: str,
  code: ComputationDiagnosticCode,
  message: str,
  **details: object,
) -> CalculatorOutput:
  return CalculatorOutput(
    diagnostic=ComputationDiagnostic(
      signal_type=signal_type,
      code=code,
      message=message,
      details=dict(details),
    )
  )


__all__ = [
  "CalculatorContext",
  "CalculatorOutput",
  "SignalCalculator",
  "build_signal",
  "signal_quality_from_snapshot",
  "skip_diagnostic",
]
