"""StrategyRuntime protocol and non-Python runtime stubs (interfaces only)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .types import (
    PineRuntimeCompatibilityStatus,
    StrategyDatasetRef,
    StrategyExecutionContext,
    StrategyParameterRef,
    StrategySourceRef,
    StrategySourceRuntimeResult,
)


class StrategyRuntimeError(ValueError):
    """Strategy source runtime rejected the request."""


@runtime_checkable
class StrategyRuntime(Protocol):
    """Generic strategy/research execution surface (not Paper/Live authority)."""

    runtime_id: str
    runtime_version: str

    def execute(
        self,
        source: StrategySourceRef,
        dataset: StrategyDatasetRef,
        parameters: StrategyParameterRef,
        context: StrategyExecutionContext,
    ) -> StrategySourceRuntimeResult:
        ...


class _UnavailableRuntime:
    """Shared stub body for adapters that are not wired in Lane H."""

    def __init__(
        self,
        *,
        runtime_id: str,
        runtime_version: str,
        pine_status: PineRuntimeCompatibilityStatus,
        reason_code: str,
    ) -> None:
        self.runtime_id = runtime_id
        self.runtime_version = runtime_version
        self._pine_status = pine_status
        self._reason_code = reason_code

    def execute(
        self,
        source: StrategySourceRef,
        dataset: StrategyDatasetRef,
        parameters: StrategyParameterRef,
        context: StrategyExecutionContext,
    ) -> StrategySourceRuntimeResult:
        from .types import STRATEGY_RUNTIME_STUB_UNAVAILABLE, compute_result_identity

        source_hash = source.content_hash()
        dataset_hash = dataset.content_hash()
        parameter_hash = parameters.content_hash()
        context_hash = context.content_hash()
        payload_root_hash = "unavailable"
        result_identity = compute_result_identity(
            runtime_id=self.runtime_id,
            runtime_version=self.runtime_version,
            source_hash=source_hash,
            dataset_hash=dataset_hash,
            parameter_hash=parameter_hash,
            context_hash=context_hash,
            payload_root_hash=payload_root_hash,
        )
        return StrategySourceRuntimeResult(
            runtime_id=self.runtime_id,
            runtime_version=self.runtime_version,
            source_hash=source_hash,
            dataset_hash=dataset_hash,
            parameter_hash=parameter_hash,
            context_hash=context_hash,
            result_identity=result_identity,
            execution_context=context,
            errors=(self._reason_code,),
            generated_at=context.generated_at,
            pine_compatibility_status=self._pine_status,
            foundation_gate=STRATEGY_RUNTIME_STUB_UNAVAILABLE,
        )


class TypeScriptRuntime(_UnavailableRuntime):
    def __init__(self) -> None:
        super().__init__(
            runtime_id="imp.typescript_strategy_runtime",
            runtime_version="0.0.0-stub",
            pine_status=PineRuntimeCompatibilityStatus.UNTESTED,
            reason_code="TYPESCRIPT_RUNTIME_NOT_IMPLEMENTED",
        )


class WasmStrategyRuntime(_UnavailableRuntime):
    def __init__(self) -> None:
        super().__init__(
            runtime_id="imp.wasm_strategy_runtime",
            runtime_version="0.0.0-stub",
            pine_status=PineRuntimeCompatibilityStatus.UNTESTED,
            reason_code="WASM_RUNTIME_NOT_IMPLEMENTED",
        )
