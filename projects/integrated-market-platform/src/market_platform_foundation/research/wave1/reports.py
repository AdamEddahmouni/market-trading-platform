"""Wave1ExperimentReport schema (JSON-serializable)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

WAVE1_REPORT_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class Wave1FamilyResult:
    family_id: str
    hypothesis_ref: str
    adapter_kind: str
    oos_mode: str
    status: str
    primary_metric: str
    metrics: dict[str, Any]
    statistical_assessment: dict[str, Any] | None
    negative_control_deltas: dict[str, float | None]
    sample_count: int
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Wave1RunReport:
    schema_version: str
    run_id: str
    run_fingerprint: str
    registry_fingerprint: str
    export_fingerprint: str | None
    oos_mode: str
    pit_status: str
    evidence_class: str | None
    family_results: tuple[Wave1FamilyResult, ...]
    execution_authority: str = "NONE"
    auto_strategy_promotion: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def wave1_family_result_to_dict(result: Wave1FamilyResult) -> dict[str, Any]:
    return {
        "adapter_kind": result.adapter_kind,
        "family_id": result.family_id,
        "hypothesis_ref": result.hypothesis_ref,
        "limitations": list(result.limitations),
        "metrics": dict(result.metrics),
        "negative_control_deltas": dict(result.negative_control_deltas),
        "oos_mode": result.oos_mode,
        "primary_metric": result.primary_metric,
        "sample_count": result.sample_count,
        "statistical_assessment": result.statistical_assessment,
        "status": result.status,
    }


def wave1_run_report_to_dict(report: Wave1RunReport) -> dict[str, Any]:
    return {
        "auto_strategy_promotion": report.auto_strategy_promotion,
        "evidence_class": report.evidence_class,
        "execution_authority": report.execution_authority,
        "export_fingerprint": report.export_fingerprint,
        "family_results": [wave1_family_result_to_dict(r) for r in report.family_results],
        "metadata": dict(report.metadata),
        "oos_mode": report.oos_mode,
        "pit_status": report.pit_status,
        "registry_fingerprint": report.registry_fingerprint,
        "run_fingerprint": report.run_fingerprint,
        "run_id": report.run_id,
        "schema_version": report.schema_version,
    }
