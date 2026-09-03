"""Fast signal engine orchestration (BUILD 06)."""

from __future__ import annotations

from ..contracts.common import QualityState
from ..contracts.signal import SignalV1
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from ..snapshots.resolver import SnapshotResolvedState, resolve_snapshot
from .errors import SignalComputationError, SignalInputError, UnsupportedSignalError
from .models import (
  ComputationDiagnostic,
  ComputationDiagnosticCode,
  SignalComputationRequest,
  SignalComputationResult,
)
from .prepared import PreparedSnapshotState
from .calculators import ALL_SIGNAL_TYPES, build_default_registry
from .calculators.base import CalculatorContext, SignalCalculator


class FastSignalEngine:
  """Deterministic snapshot-bound signal computation."""

  def __init__(self, calculators: dict[str, SignalCalculator] | None = None) -> None:
    self._calculators = calculators or build_default_registry()

  def compute(
    self,
    resolved: SnapshotResolvedState,
    request: SignalComputationRequest,
  ) -> SignalComputationResult:
    return compute_fast_signals(resolved, request, calculators=self._calculators)

  def compute_and_persist(
    self,
    resolved: SnapshotResolvedState,
    repository: IntelligenceRepository,
    request: SignalComputationRequest,
  ) -> SignalComputationResult:
    persist_request = SignalComputationRequest(
      window_ns=request.window_ns,
      signal_types=request.signal_types,
      depth_levels=request.depth_levels,
      require_all=request.require_all,
      persist=True,
      parameters=dict(request.parameters),
    )
    return compute_fast_signals(
      resolved,
      persist_request,
      calculators=self._calculators,
      repository=repository,
    )


def compute_fast_signals(
  resolved: SnapshotResolvedState,
  request: SignalComputationRequest,
  *,
  calculators: dict[str, SignalCalculator] | None = None,
  repository: IntelligenceRepository | None = None,
) -> SignalComputationResult:
  """Pure computation from resolved snapshot; optional persistence at boundary."""
  registry = calculators or build_default_registry()
  snapshot = resolved.snapshot
  if snapshot.quality.state == QualityState.INVALID:
    diagnostic = ComputationDiagnostic(
      signal_type="*",
      code=ComputationDiagnosticCode.SNAPSHOT_QUALITY_REJECTED,
      message="Snapshot quality INVALID — operational signals prohibited",
    )
    if request.require_all:
      raise SignalInputError("SNAPSHOT_QUALITY_REJECTED", details={"quality": snapshot.quality.state.value})
    return SignalComputationResult(signals=(), diagnostics=(diagnostic,), skipped_signal_types=())

  requested = request.signal_types or ALL_SIGNAL_TYPES
  unknown = sorted(signal_type for signal_type in requested if signal_type not in registry)
  diagnostics_list: list[ComputationDiagnostic] = []
  if unknown:
    diagnostics_list.extend(
      ComputationDiagnostic(
        signal_type=signal_type,
        code=ComputationDiagnosticCode.UNSUPPORTED_SIGNAL,
        message=f"Signal type not registered: {signal_type}",
      )
      for signal_type in unknown
    )
    if request.require_all:
      raise UnsupportedSignalError(f"UNSUPPORTED_SIGNAL:{','.join(unknown)}")
    requested = frozenset(signal_type for signal_type in requested if signal_type in registry)

  prepared = PreparedSnapshotState.from_resolved(resolved)
  ctx = CalculatorContext(prepared=prepared, request=request)
  signals: list[SignalV1] = []
  skipped: list[str] = []
  failures: list[ComputationDiagnostic] = []

  for signal_type in sorted(requested):
    calculator = registry[signal_type]
    output = calculator.compute(ctx)
    if output.signal is not None:
      signals.append(output.signal)
    elif output.diagnostic is not None:
      diagnostics_list.append(output.diagnostic)
      skipped.append(signal_type)
      if request.require_all:
        failures.append(output.diagnostic)

  if failures:
    raise SignalComputationError(
      "REQUIRE_ALL_FAILED",
      details={"failures": [row.code.value for row in failures]},
    )

  persisted: list[str] = []
  if request.persist and repository is not None:
    for signal in signals:
      result = repository.put_signal(signal)
      if result in {RepositoryPutResult.INSERTED, RepositoryPutResult.ALREADY_PRESENT}:
        persisted.append(signal.signal_id)

  return SignalComputationResult(
    signals=tuple(signals),
    diagnostics=tuple(diagnostics_list),
    skipped_signal_types=tuple(skipped),
    persisted=tuple(persisted),
  )


def compute_from_snapshot(
  snapshot,
  repository: IntelligenceRepository,
  request: SignalComputationRequest,
  *,
  calculators: dict[str, SignalCalculator] | None = None,
  strict_resolve: bool = True,
) -> SignalComputationResult:
  """Resolve snapshot then compute signals."""
  resolved = resolve_snapshot(snapshot, repository, strict=strict_resolve)
  return compute_fast_signals(
    resolved,
    request,
    calculators=calculators,
    repository=repository if request.persist else None,
  )


__all__ = [
  "FastSignalEngine",
  "compute_fast_signals",
  "compute_from_snapshot",
]
