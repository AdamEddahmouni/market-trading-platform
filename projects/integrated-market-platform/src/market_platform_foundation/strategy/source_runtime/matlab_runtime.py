"""MATLAB governed Research Export v1 round-trip strategy adapter (research/parity only)."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

from ...research.export_v1 import (
    PROFILE_MARKET_TECHNICAL,
    ResearchExportV1Package,
    build_research_export_v1,
    load_research_export_v1_package,
)
from ...research.export_v1_matlab_result import (
    MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY,
    build_parity_matlab_research_result,
    matlab_research_result_content_sha256,
)
from ...research.export_v1_matlab_roundtrip import (
    MATLAB_RESULT_FILENAME,
    execute_governed_roundtrip,
)
from .protocol import StrategyRuntimeError
from .python_runtime import _assert_research_context
from .types import (
    MATLAB_RUNTIME_UNAVAILABLE,
    MATLAB_STRATEGY_RUNTIME_READY,
    PineRuntimeCompatibilityStatus,
    StrategyDatasetRef,
    StrategyExecutionContext,
    StrategyParameterRef,
    StrategySourceRef,
    StrategySourceRuntimeResult,
    compute_result_identity,
)

MATLAB_RUNTIME_ID = "imp.matlab_strategy_runtime"
MATLAB_RUNTIME_VERSION = "1.0.0"

_SUPPORTED_SOURCE_KINDS = frozenset({"research_export_v1"})
_NUMERIC_TOLERANCE = 1e-9
_IMP_ROOT = Path(__file__).resolve().parents[4]


def _ensure_tools_import_path() -> None:
    root = str(_IMP_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _resolve_export_package(
    source: StrategySourceRef,
    parameters: StrategyParameterRef,
) -> ResearchExportV1Package:
    body = dict(source.body)
    param_body = dict(parameters.body)
    export_path = body.get("export_package_path")
    if export_path:
        return load_research_export_v1_package(Path(str(export_path)))
    profile = str(
        body.get("profile")
        or param_body.get("export_profile")
        or param_body.get("profile")
        or PROFILE_MARKET_TECHNICAL
    )
    return build_research_export_v1(profile=profile)


def _compare_reference_statistics(
    *,
    python_stats: dict[str, Any],
    challenger_stats: dict[str, Any],
) -> tuple[bool, tuple[str, ...]]:
    mismatches: list[str] = []
    for key in sorted(set(python_stats) | set(challenger_stats)):
        left = python_stats.get(key)
        right = challenger_stats.get(key)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            if abs(float(left) - float(right)) > _NUMERIC_TOLERANCE:
                mismatches.append(f"STAT_NUMERIC_MISMATCH:{key}")
        elif left != right:
            mismatches.append(f"STAT_VALUE_MISMATCH:{key}")
    return (not mismatches, tuple(mismatches))


class MATLABRuntime:
    """Governed export round-trip — MATLAB is research/challenger, not trading authority."""

    runtime_id = MATLAB_RUNTIME_ID
    runtime_version = MATLAB_RUNTIME_VERSION

    def execute(
        self,
        source: StrategySourceRef,
        dataset: StrategyDatasetRef,
        parameters: StrategyParameterRef,
        context: StrategyExecutionContext,
    ) -> StrategySourceRuntimeResult:
        _assert_research_context(context)
        if source.kind not in _SUPPORTED_SOURCE_KINDS:
            raise StrategyRuntimeError(f"UNSUPPORTED_SOURCE_KIND:{source.kind}")

        package = _resolve_export_package(source, parameters)
        param_body = dict(parameters.body)
        prefer_matlab = bool(param_body.get("prefer_matlab", True))
        if str(context.mode) == "PARITY":
            prefer_matlab = True

        source_hash = source.content_hash()
        dataset_hash = dataset.content_hash()
        parameter_hash = parameters.content_hash()
        context_hash = context.content_hash()

        warnings: list[str] = []
        errors: list[str] = []
        parity_match = False
        parity_mismatch_reasons: tuple[str, ...] = ()
        analysis_source = "python_reference"
        matlab_release = "UNAVAILABLE"
        readiness = MATLAB_RUNTIME_UNAVAILABLE
        foundation_gate = MATLAB_RUNTIME_UNAVAILABLE
        export_id = ""
        manifest_hash = ""
        result_content_sha256 = ""
        evidence_sha256 = ""

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            python_reference = build_parity_matlab_research_result(
                package,
                analysis_source="python_reference",
                code_identity="strategy/source_runtime/matlab_runtime",
                generated_at=context.generated_at,
            )
            ref_stats = (python_reference.get("result_values") or {}).get("reference_statistics") or {}

            probe: dict[str, Any] = {"status": "UNPROBED"}
            matlab_used = False
            result_payload: dict[str, Any] = python_reference

            if prefer_matlab:
                _ensure_tools_import_path()
                from tools.research.matlab_governed_roundtrip import (  # noqa: PLC0415
                    execute_governed_roundtrip_with_matlab,
                )
                from tools.research.matlab_runtime import probe_matlab_runtime  # noqa: PLC0415

                probe = probe_matlab_runtime()
                if probe.get("status") == "AVAILABLE":
                    matlab_release = str(probe.get("matlab_release") or "UNKNOWN")
                    try:
                        report = execute_governed_roundtrip_with_matlab(
                            package,
                            work_dir=work_dir,
                            prefer_matlab=True,
                        )
                    except (OSError, ValueError, json.JSONDecodeError) as exc:
                        errors.append(f"MATLAB_ROUNDTRIP_FAILED:{type(exc).__name__}")
                        report = execute_governed_roundtrip(
                            package,
                            work_dir=work_dir,
                            matlab_runtime_available=False,
                        )
                    else:
                        result_path = work_dir / MATLAB_RESULT_FILENAME
                        if result_path.is_file():
                            loaded = json.loads(result_path.read_text(encoding="utf-8"))
                            if isinstance(loaded, dict):
                                result_payload = loaded
                        analysis_source = report.analysis_source
                        export_id = report.export_id
                        manifest_hash = report.manifest_hash
                        result_content_sha256 = report.result_content_sha256
                        evidence_sha256 = report.evidence_artifact_content_sha256
                        readiness = report.readiness
                        matlab_used = report.matlab_runtime_available
                        if readiness == MATLAB_GOVERNED_RESEARCH_ROUNDTRIP_READY:
                            foundation_gate = MATLAB_STRATEGY_RUNTIME_READY
                        else:
                            warnings.append(f"MATLAB_READINESS:{readiness}")
                else:
                    warnings.append("MATLAB_RUNTIME_NOT_AVAILABLE")
                    report = execute_governed_roundtrip(
                        package,
                        work_dir=work_dir,
                        matlab_runtime_available=False,
                    )
                    analysis_source = report.analysis_source
                    export_id = report.export_id
                    manifest_hash = report.manifest_hash
                    result_content_sha256 = report.result_content_sha256
                    evidence_sha256 = report.evidence_artifact_content_sha256
                    readiness = report.readiness
            else:
                report = execute_governed_roundtrip(
                    package,
                    work_dir=work_dir,
                    matlab_runtime_available=False,
                )
                analysis_source = report.analysis_source
                export_id = report.export_id
                manifest_hash = report.manifest_hash
                result_content_sha256 = report.result_content_sha256
                evidence_sha256 = report.evidence_artifact_content_sha256
                readiness = report.readiness

            challenger_stats = (result_payload.get("result_values") or {}).get("reference_statistics") or {}
            parity_match, parity_mismatch_reasons = _compare_reference_statistics(
                python_stats=ref_stats if isinstance(ref_stats, dict) else {},
                challenger_stats=challenger_stats if isinstance(challenger_stats, dict) else {},
            )
            if not result_content_sha256:
                result_content_sha256 = matlab_research_result_content_sha256(result_payload)

        if not matlab_used and foundation_gate != MATLAB_STRATEGY_RUNTIME_READY:
            foundation_gate = MATLAB_RUNTIME_UNAVAILABLE

        payload_root_hash = result_content_sha256
        result_identity = compute_result_identity(
            runtime_id=self.runtime_id,
            runtime_version=self.runtime_version,
            source_hash=source_hash,
            dataset_hash=dataset_hash,
            parameter_hash=parameter_hash,
            context_hash=context_hash,
            payload_root_hash=payload_root_hash,
        )

        metrics: dict[str, Any] = {
            "analysis_source": analysis_source,
            "dataset_lineage_export_id": export_id or package.manifest.get("export_id"),
            "dataset_lineage_manifest_hash": manifest_hash or package.manifest.get("manifest_hash"),
            "evidence_artifact_content_sha256": evidence_sha256,
            "matlab_release": matlab_release,
            "matlab_runtime_probe_status": probe.get("status"),
            "matlab_runtime_used": matlab_used,
            "numerical_tolerance": _NUMERIC_TOLERANCE,
            "parity_mismatch_reasons": list(parity_mismatch_reasons),
            "parity_reference_statistics_match": parity_match,
            "python_reference_result_sha256": matlab_research_result_content_sha256(python_reference),
            "readiness": readiness,
            "result_content_sha256": result_content_sha256,
            "source_sha256": package.manifest.get("source_sha256"),
        }

        if parity_mismatch_reasons:
            warnings.extend(parity_mismatch_reasons)

        return StrategySourceRuntimeResult(
            runtime_id=self.runtime_id,
            runtime_version=self.runtime_version,
            source_hash=source_hash,
            dataset_hash=dataset_hash,
            parameter_hash=parameter_hash,
            context_hash=context_hash,
            result_identity=result_identity,
            execution_context=context,
            metrics=metrics,
            warnings=tuple(warnings),
            errors=tuple(errors),
            generated_at=context.generated_at,
            pine_compatibility_status=PineRuntimeCompatibilityStatus.UNTESTED,
            foundation_gate=foundation_gate,
        )


__all__ = [
    "MATLAB_RUNTIME_ID",
    "MATLAB_RUNTIME_VERSION",
    "MATLABRuntime",
]
