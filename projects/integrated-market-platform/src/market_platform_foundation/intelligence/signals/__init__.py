"""Feature and fast signal layer (BUILD 06)."""

from .engine import FastSignalEngine, compute_fast_signals, compute_from_snapshot
from .errors import (
  SignalComputationError,
  SignalDeterminismError,
  SignalInputError,
  UnsupportedSignalError,
)
from .identity import IDENTITY_VERSION, SIGNAL_ID_PREFIX, derive_signal_id
from .models import (
  ComputationDiagnostic,
  ComputationDiagnosticCode,
  SignalComputationRequest,
  SignalComputationResult,
)
from .prepared import PreparedSnapshotState
from .calculators import ALL_SIGNAL_TYPES

__all__ = [
  "ALL_SIGNAL_TYPES",
  "ComputationDiagnostic",
  "ComputationDiagnosticCode",
  "FastSignalEngine",
  "IDENTITY_VERSION",
  "PreparedSnapshotState",
  "SIGNAL_ID_PREFIX",
  "SignalComputationError",
  "SignalComputationRequest",
  "SignalComputationResult",
  "SignalDeterminismError",
  "SignalInputError",
  "UnsupportedSignalError",
  "compute_fast_signals",
  "compute_from_snapshot",
  "derive_signal_id",
]
