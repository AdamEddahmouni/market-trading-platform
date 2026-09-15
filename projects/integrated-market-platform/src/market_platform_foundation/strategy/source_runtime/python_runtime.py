"""Python native strategy evaluation adapter (walk-forward + interpret_strategy)."""

from __future__ import annotations

from typing import Any, Mapping

from ..evaluation import run_strategy_evaluation, strategy_evaluation_root_hash
from ..evaluation import DEFAULT_REGISTERED_AT
from ..strategy_spec import coerce_strategy_spec
from .protocol import StrategyRuntimeError
from .types import (
    STRATEGY_RUNTIME_FOUNDATION_READY,
    PineRuntimeCompatibilityStatus,
    StrategyDatasetRef,
    StrategyExecutionContext,
    StrategyExecutionMode,
    StrategyParameterRef,
    StrategySourceRef,
    StrategySourceRuntimeResult,
    compute_result_identity,
)

PYTHON_RUNTIME_ID = "imp.python_strategy_evaluation"
PYTHON_RUNTIME_VERSION = "1.0.0"

_FORBIDDEN_CONTEXT_MODES = frozenset({"PAPER", "LIVE", "paper", "live"})


class PythonRuntime:
    """Executes preregistered Python strategy evaluation (Phase 6 walk-forward path)."""

    runtime_id = PYTHON_RUNTIME_ID
    runtime_version = PYTHON_RUNTIME_VERSION

    def execute(
        self,
        source: StrategySourceRef,
        dataset: StrategyDatasetRef,
        parameters: StrategyParameterRef,
        context: StrategyExecutionContext,
    ) -> StrategySourceRuntimeResult:
        _assert_research_context(context)
        if source.kind not in {"strategy_spec", "python_strategy_spec"}:
            raise StrategyRuntimeError(f"UNSUPPORTED_SOURCE_KIND:{source.kind}")

        spec_body = dict(source.body)
        strategy_spec = coerce_strategy_spec(spec_body)
        param_body = dict(parameters.body)
        preregistration = param_body.get("preregistration")
        registered_at = str(param_body.get("registered_at", DEFAULT_REGISTERED_AT))
        events = [dict(row) for row in dataset.events]

        evaluation = run_strategy_evaluation(
            events,
            strategy_spec=strategy_spec,
            preregistration=preregistration if isinstance(preregistration, dict) else None,
            registered_at=registered_at,
        )
        payload_root_hash = strategy_evaluation_root_hash(evaluation)
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

        interpretations = evaluation.get("interpretations", [])
        event_rows: list[Mapping[str, Any]] = []
        signal_rows: list[Mapping[str, Any]] = []
        for row in interpretations:
            if not isinstance(row, dict):
                continue
            event_rows.append(row)
            if row.get("outcome") == "signal":
                signal_rows.append(row)

        warnings: list[str] = []
        prereg_status = str(evaluation.get("preregistration_status", ""))
        if prereg_status != "PASS":
            warnings.append(f"PREREGISTRATION_STATUS_{prereg_status}")

        metrics = {
            "abstention_count": int(evaluation.get("abstention_count", 0)),
            "evaluation_root_hash": payload_root_hash,
            "signal_count": int(evaluation.get("signal_count", 0)),
            "strategy_identity_hash": strategy_spec["strategy_identity_hash"],
            "walk_forward_fold_count": int(evaluation.get("walk_forward_fold_count", 0)),
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
            events=tuple(event_rows),
            signals=tuple(signal_rows),
            trades=(),
            metrics=metrics,
            warnings=tuple(warnings),
            errors=(),
            generated_at=context.generated_at,
            pine_compatibility_status=PineRuntimeCompatibilityStatus.UNTESTED,
            foundation_gate=STRATEGY_RUNTIME_FOUNDATION_READY,
        )


def _assert_research_context(context: StrategyExecutionContext) -> None:
    mode_token = str(context.mode)
    if mode_token in _FORBIDDEN_CONTEXT_MODES:
        raise StrategyRuntimeError("EXECUTION_AUTHORITY_FORBIDDEN")
    if mode_token not in {m.value for m in StrategyExecutionMode}:
        raise StrategyRuntimeError(f"UNSUPPORTED_EXECUTION_MODE:{mode_token}")
    if "LIVE_ON" in context.hold_labels:
        raise StrategyRuntimeError("LIVE_AUTHORITY_FORBIDDEN")
