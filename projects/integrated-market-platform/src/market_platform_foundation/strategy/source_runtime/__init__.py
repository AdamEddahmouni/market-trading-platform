"""Governed strategy source execution runtime (research/replay/parity)."""

from .matlab_runtime import MATLABRuntime
from .protocol import (
    PineTSRuntime,
    StrategyRuntime,
    StrategyRuntimeError,
    TypeScriptRuntime,
    WasmStrategyRuntime,
)
from .python_runtime import PYTHON_RUNTIME_ID, PYTHON_RUNTIME_VERSION, PythonRuntime
from .types import (
    FOUNDATION_SCHEMA_VERSION,
    HOLD_LABEL_LIVE_OFF,
    HOLD_LABEL_SIMULATOR,
    MATLAB_RUNTIME_UNAVAILABLE,
    MATLAB_STRATEGY_RUNTIME_READY,
    PineRuntimeCompatibilityStatus,
    STRATEGY_RUNTIME_FOUNDATION_READY,
    STRATEGY_RUNTIME_STUB_UNAVAILABLE,
    StrategyDatasetRef,
    StrategyExecutionContext,
    StrategyExecutionMode,
    StrategyParameterRef,
    StrategySourceRef,
    StrategySourceRuntimeResult,
    compute_result_identity,
)

__all__ = [
    "FOUNDATION_SCHEMA_VERSION",
    "HOLD_LABEL_LIVE_OFF",
    "HOLD_LABEL_SIMULATOR",
    "MATLAB_RUNTIME_UNAVAILABLE",
    "MATLAB_STRATEGY_RUNTIME_READY",
    "MATLABRuntime",
    "PineRuntimeCompatibilityStatus",
    "PineTSRuntime",
    "PYTHON_RUNTIME_ID",
    "PYTHON_RUNTIME_VERSION",
    "PythonRuntime",
    "STRATEGY_RUNTIME_FOUNDATION_READY",
    "STRATEGY_RUNTIME_STUB_UNAVAILABLE",
    "StrategyDatasetRef",
    "StrategyExecutionContext",
    "StrategyExecutionMode",
    "StrategyParameterRef",
    "StrategyRuntime",
    "StrategyRuntimeError",
    "StrategySourceRef",
    "StrategySourceRuntimeResult",
    "TypeScriptRuntime",
    "WasmStrategyRuntime",
    "compute_result_identity",
]
