"""PineTS research runtime adapter (RESEARCH / REPLAY / PARITY only)."""

from __future__ import annotations

from typing import Any, Mapping

from ...canonical import canonical_bytes, sha256_bytes
from .pinets_engine_probe import pinets_license_audit, probe_pinets_engine, run_pinets_fixture_via_bridge
from .pinets_parity import ParityFailureCode, compare_parity, parity_side_from_reference_payload
from .pinets_reference import bars_from_dataset_events, reference_statistics, run_reference_fixture
from .pinets_registry import DEFAULT_PINETS_REGISTRY, PineScriptRegistry
from .protocol import StrategyRuntimeError
from .python_runtime import _assert_research_context
from .types import (
    STRATEGY_RUNTIME_PINETS_LICENSE_BOUNDARY,
    STRATEGY_RUNTIME_PINETS_RESEARCH_READY,
    PineRuntimeCompatibilityStatus,
    StrategyDatasetRef,
    StrategyExecutionContext,
    StrategyExecutionMode,
    StrategyParameterRef,
    StrategySourceRef,
    StrategySourceRuntimeResult,
    compute_result_identity,
)

PINETS_RUNTIME_ID = "imp.pinets_strategy_runtime"
PINETS_RUNTIME_VERSION = "0.1.0-lane-e"

_SUPPORTED_SOURCE_KINDS = frozenset({"pinets_fixture", "pine_script"})
_FORBIDDEN_MODES = frozenset(
    {
        "PAPER",
        "LIVE",
        "paper",
        "live",
    }
)


class PineTSRuntime:
    """Isolated Pine compatibility surface — Python reference is not canonical truth."""

    runtime_id = PINETS_RUNTIME_ID
    runtime_version = PINETS_RUNTIME_VERSION

    def __init__(self, registry: PineScriptRegistry | None = None) -> None:
        self._registry = registry or DEFAULT_PINETS_REGISTRY

    def execute(
        self,
        source: StrategySourceRef,
        dataset: StrategyDatasetRef,
        parameters: StrategyParameterRef,
        context: StrategyExecutionContext,
    ) -> StrategySourceRuntimeResult:
        _assert_research_context(context)
        mode_token = str(context.mode)
        if mode_token in _FORBIDDEN_MODES:
            raise StrategyRuntimeError("EXECUTION_AUTHORITY_FORBIDDEN")
        if mode_token not in {m.value for m in StrategyExecutionMode}:
            raise StrategyRuntimeError(f"UNSUPPORTED_EXECUTION_MODE:{mode_token}")

        if source.kind not in _SUPPORTED_SOURCE_KINDS:
            raise StrategyRuntimeError(f"UNSUPPORTED_SOURCE_KIND:{source.kind}")

        body = dict(source.body)
        script_id = str(body.get("script_id") or body.get("fixture_id") or "")
        if not script_id:
            raise StrategyRuntimeError("PINETS_SCRIPT_ID_REQUIRED")

        try:
            record = self._registry.require(script_id)
        except KeyError as exc:
            raise StrategyRuntimeError(str(exc)) from exc

        param_body = dict(parameters.body)
        merged_params: dict[str, Any] = dict(record.reference_parameters)
        merged_params.update(param_body.get("reference_parameters") or {})
        merged_params.update(param_body.get("parameters") or {})

        bars = bars_from_dataset_events(dataset.events)
        if not bars:
            raise StrategyRuntimeError("PINETS_DATASET_EMPTY")

        reference_payload = run_reference_fixture(script_id, bars, merged_params)
        ref_stats = reference_statistics(reference_payload)

        warnings: list[str] = []
        errors: list[str] = []
        foundation_gate = STRATEGY_RUNTIME_PINETS_RESEARCH_READY
        pine_status = record.status
        prefer_pinets = bool(param_body.get("prefer_pinets_engine", False))
        parity_ok = True
        parity_details: list[str] = []
        engine_probe = probe_pinets_engine()

        if prefer_pinets:
            bridge_result = run_pinets_fixture_via_bridge(
                script_id=script_id,
                pine_source=record.pine_source,
                bars=bars,
                parameters=merged_params,
            )
            if bridge_result.get("status") == "UNAVAILABLE":
                foundation_gate = STRATEGY_RUNTIME_PINETS_LICENSE_BOUNDARY
                reason = str(bridge_result.get("reason") or bridge_result.get("probe", {}).get("reason"))
                errors.append(reason or "PINETS_AGPL_LICENSE_BOUNDARY")
                warnings.append("PINETS_ENGINE_NOT_IN_PRODUCTION_GRAPH")
            elif bridge_result.get("status") != "OK":
                errors.append(str(bridge_result.get("reason", ParityFailureCode.RUNTIME_ERROR)))
                if bridge_result.get("reason") == ParityFailureCode.UNSUPPORTED_PINE_FEATURE:
                    warnings.append("PINETS_BRIDGE_PARTIAL_IMPLEMENTATION")
                parity_ok = False
            else:
                challenger_side = parity_side_from_reference_payload(bridge_result)
                reference_side = parity_side_from_reference_payload(reference_payload)
                parity = compare_parity(reference_side, challenger_side)
                parity_ok = parity.ok
                parity_details = list(parity.details)
                if not parity.ok:
                    errors.extend(parity.failure_codes)
                    errors.extend(parity.details)

        payload_root_hash = sha256_bytes(
            canonical_bytes(
                {
                    "reference": reference_payload,
                    "parity_ok": parity_ok,
                    "script_id": script_id,
                    "stats": ref_stats,
                }
            )
        )

        source_hash = source.content_hash()
        dataset_hash = dataset.content_hash()
        parameter_hash = parameters.content_hash()
        context_hash = context.content_hash()
        result_identity = compute_result_identity(
            runtime_id=self.runtime_id,
            runtime_version=self.runtime_version,
            source_hash=source_hash,
            dataset_hash=dataset_hash,
            parameter_hash=parameter_hash,
            context_hash=context_hash,
            payload_root_hash=payload_root_hash,
        )

        signal_rows = tuple(dict(row) for row in reference_payload.get("signals") or [])
        metrics: dict[str, Any] = {
            "bar_count": ref_stats["bar_count"],
            "license_audit": pinets_license_audit(),
            "parity_details": parity_details,
            "parity_ok": parity_ok,
            "pinets_engine_probe": engine_probe,
            "reference_statistics": ref_stats,
            "script_id": script_id,
            "script_registry_status": str(record.status),
            "warmup_bars": ref_stats["warmup_bars"],
        }

        return StrategySourceRuntimeResult(
            runtime_id=self.runtime_id,
            runtime_version=self.runtime_version,
            source_hash=source_hash,
            dataset_hash=dataset_hash,
            parameter_hash=parameter_hash,
            context_hash=context_hash,
            result_identity=result_identity,
            execution_context=context,
            signals=signal_rows,
            metrics=metrics,
            warnings=tuple(warnings),
            errors=tuple(errors),
            generated_at=context.generated_at,
            pine_compatibility_status=pine_status,
            foundation_gate=foundation_gate,
        )


__all__ = [
    "PINETS_RUNTIME_ID",
    "PINETS_RUNTIME_VERSION",
    "PineTSRuntime",
]
