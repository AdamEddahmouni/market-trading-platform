"""System acceptance serialization (BUILD 25)."""

from __future__ import annotations

from typing import Any

from .types import (
    AcceptanceDisposition,
    InvariantResultV1,
    InvariantStatus,
    ScenarioResultV1,
    ScenarioStatus,
    SystemAcceptanceReportV1,
    SystemAcceptanceSpecV1,
)


def system_acceptance_spec_v1_to_dict(spec: SystemAcceptanceSpecV1) -> dict[str, Any]:
    return {
        "acceptance_spec_id": spec.acceptance_spec_id,
        "schema_version": spec.schema_version,
        "source_build_head": spec.source_build_head,
        "required_build_range": list(spec.required_build_range),
        "required_suites": list(spec.required_suites),
        "required_lifecycle_scenarios": list(spec.required_lifecycle_scenarios),
        "required_adversarial_scenarios": list(spec.required_adversarial_scenarios),
        "required_invariants": list(spec.required_invariants),
        "required_persistence_checks": list(spec.required_persistence_checks),
        "required_replay_checks": list(spec.required_replay_checks),
        "required_determinism_checks": list(spec.required_determinism_checks),
        "required_security_checks": list(spec.required_security_checks),
        "allowed_known_limitations": list(spec.allowed_known_limitations),
        "blocking_failure_classes": [c.value for c in spec.blocking_failure_classes],
        "implementation_version": spec.implementation_version,
        "metadata": dict(spec.metadata),
    }


def invariant_result_v1_to_dict(result: InvariantResultV1) -> dict[str, Any]:
    return {
        "invariant_id": result.invariant_id,
        "status": result.status.value,
        "evidence": result.evidence,
        "details": dict(result.details),
    }


def scenario_result_v1_to_dict(result: ScenarioResultV1) -> dict[str, Any]:
    return {
        "scenario_id": result.scenario_id,
        "status": result.status.value,
        "expected": result.expected,
        "observed": result.observed,
        "details": dict(result.details),
    }


def system_acceptance_report_v1_to_dict(report: SystemAcceptanceReportV1) -> dict[str, Any]:
    return {
        "acceptance_report_id": report.acceptance_report_id,
        "schema_version": report.schema_version,
        "acceptance_spec_ref": report.acceptance_spec_ref,
        "source_head": report.source_head,
        "candidate_head": report.candidate_head,
        "scenario_results": [scenario_result_v1_to_dict(row) for row in report.scenario_results],
        "invariant_results": [invariant_result_v1_to_dict(row) for row in report.invariant_results],
        "test_suite_results": dict(report.test_suite_results),
        "determinism_results": dict(report.determinism_results),
        "replay_parity_results": dict(report.replay_parity_results),
        "persistence_results": dict(report.persistence_results),
        "security_results": dict(report.security_results),
        "blocking_failures": list(report.blocking_failures),
        "nonblocking_limitations": list(report.nonblocking_limitations),
        "overall_disposition": report.overall_disposition.value,
        "implementation_version": report.implementation_version,
        "metadata": dict(report.metadata),
    }
