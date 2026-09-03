"""Operation-specific input sufficiency (docs/phase-2d-design.md Section 11). Never
recomputes the downstream metric -- only validates presence/compatibility of what the
metric would need, optionally cross-checking an already-computed result's own
quality/SampleCounts when one is supplied."""

from typing import Any

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.evidence import PointInTimeEvidenceBundle

from .coverage import build_domain_coverage_snapshot
from .diagnostics import ReadinessDiagnostic, ReadinessDiagnosticCode, sort_diagnostics
from .models import DomainCoverageState, InputSufficiencyResult, StructuralState
from .policies import OperationRequirementPolicy, lookup_policy

_UNAVAILABLE_LIKE_STATES = (
    DomainCoverageState.MISSING,
    DomainCoverageState.UNAVAILABLE,
    DomainCoverageState.CANCELLED,
    DomainCoverageState.PARTIAL,
)


def _metric_name_of(result: Any) -> str | None:
    metric_name = getattr(result, "metric_name", None)
    return metric_name.value if metric_name is not None else None


def _find_referenced_metric(metric_results: tuple[Any, ...], metric_name: str) -> Any | None:
    for result in metric_results:
        if _metric_name_of(result) == metric_name:
            return result
    return None


def build_input_sufficiency_result(
    bundle: PointInTimeEvidenceBundle,
    operation: str,
    *,
    policy_version: str | None = None,
    metric_results: tuple[Any, ...] = (),
) -> InputSufficiencyResult:
    policy: OperationRequirementPolicy = lookup_policy(operation, policy_version)

    coverage_snapshot = build_domain_coverage_snapshot(bundle, policy.required_domains)
    entries_by_domain = {entry.domain: entry for entry in coverage_snapshot.coverage_by_domain}

    missing_inputs: list[str] = []
    conflicted_inputs: list[str] = []
    incompatible_inputs: list[str] = []
    insufficient_history_inputs: list[str] = []
    unknown_domains: list[str] = []
    observation_ids: set[str] = set()
    diagnostics: list[ReadinessDiagnostic] = []

    for domain in policy.required_domains:
        entry = entries_by_domain[domain]
        observation_ids.update(entry.observation_ids)
        if entry.state is DomainCoverageState.CONFLICTED:
            conflicted_inputs.append(f"domain:{domain.value}")
            diagnostics.append(
                ReadinessDiagnostic(
                    code=ReadinessDiagnosticCode.READINESS_REQUIRED_DOMAIN_CONFLICTED,
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Required domain conflicted: {domain.value}.",
                    domain=domain.value,
                )
            )
        elif entry.state is DomainCoverageState.UNKNOWN:
            unknown_domains.append(domain.value)
            missing_inputs.append(f"domain:{domain.value}")
            diagnostics.append(
                ReadinessDiagnostic(
                    code=ReadinessDiagnosticCode.READINESS_UNKNOWN_AVAILABILITY,
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Availability of required domain unknown: {domain.value}.",
                    domain=domain.value,
                )
            )
        elif entry.state in _UNAVAILABLE_LIKE_STATES:
            missing_inputs.append(f"domain:{domain.value}")
            code = {
                DomainCoverageState.MISSING: ReadinessDiagnosticCode.READINESS_REQUIRED_DOMAIN_MISSING,
                DomainCoverageState.UNAVAILABLE: ReadinessDiagnosticCode.READINESS_REQUIRED_DOMAIN_UNAVAILABLE,
                DomainCoverageState.CANCELLED: ReadinessDiagnosticCode.READINESS_REQUIRED_DOMAIN_CANCELLED,
                DomainCoverageState.PARTIAL: ReadinessDiagnosticCode.READINESS_REQUIRED_DOMAIN_PARTIAL,
            }[entry.state]
            diagnostics.append(
                ReadinessDiagnostic(
                    code=code,
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Required domain {entry.state.value.lower()}: {domain.value}.",
                    domain=domain.value,
                )
            )

    referenced_metric_ids: list[str] = []
    for metric_name in policy.required_metric_names:
        result = _find_referenced_metric(metric_results, metric_name)
        if result is None:
            missing_inputs.append(f"metric:{metric_name}")
            diagnostics.append(
                ReadinessDiagnostic(
                    code=ReadinessDiagnosticCode.READINESS_REQUIRED_METRIC_MISSING,
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Required metric result not supplied: {metric_name}.",
                )
            )
            continue

        deterministic_id = getattr(result, "deterministic_id", None)
        if deterministic_id is not None:
            referenced_metric_ids.append(deterministic_id)
        observation_ids.update(getattr(result, "input_observation_ids", ()) or ())

        quality: Quality = result.quality
        if quality.state is QualityState.CONFLICTED:
            conflicted_inputs.append(f"metric:{metric_name}")
        elif quality.state in (QualityState.MISSING, QualityState.UNAVAILABLE):
            missing_inputs.append(f"metric:{metric_name}")
        elif quality.state is QualityState.INVALID:
            missing_inputs.append(f"metric:{metric_name}")

        if policy.required_units and getattr(result, "unit", None) is not None:
            if result.unit.value not in policy.required_units:
                incompatible_inputs.append(f"metric:{metric_name}:unit")
                diagnostics.append(
                    ReadinessDiagnostic(
                        code=ReadinessDiagnosticCode.READINESS_REQUIRED_UNIT_INCOMPATIBLE,
                        severity=DiagnosticSeverity.WARNING,
                        message=f"Metric {metric_name} unit {result.unit.value} is not in the required set.",
                    )
                )

        if policy.requires_trailing_window:
            sample_counts = getattr(result, "sample_counts", None)
            if sample_counts is not None and sample_counts.used < sample_counts.requested:
                insufficient_history_inputs.append(f"metric:{metric_name}")
                diagnostics.append(
                    ReadinessDiagnostic(
                        code=ReadinessDiagnosticCode.READINESS_INSUFFICIENT_HISTORY,
                        severity=DiagnosticSeverity.WARNING,
                        message=f"Insufficient history for {metric_name}: "
                        f"{sample_counts.used} of {sample_counts.requested} used.",
                    )
                )

    if conflicted_inputs and not policy.allow_conflicts:
        structural_state = StructuralState.CONFLICTED
    elif unknown_domains and not policy.allow_unknown_availability:
        structural_state = StructuralState.UNKNOWN
    elif missing_inputs or incompatible_inputs or insufficient_history_inputs:
        structural_state = StructuralState.INSUFFICIENT
    else:
        structural_state = StructuralState.SUFFICIENT

    asset_class = bundle.observations[0].asset_class if bundle.observations else AssetClass.UNKNOWN

    return InputSufficiencyResult(
        operation=policy.operation,
        policy_version=policy.policy_version,
        symbol=bundle.symbol,
        asset_class=asset_class,
        as_of=bundle.as_of,
        required_domains=policy.required_domains,
        required_metrics=policy.required_metric_names,
        missing_inputs=tuple(missing_inputs),
        invalid_inputs=(),
        conflicted_inputs=tuple(conflicted_inputs),
        incompatible_inputs=tuple(incompatible_inputs),
        insufficient_history_inputs=tuple(insufficient_history_inputs),
        point_in_time_failures=(),
        structural_state=structural_state,
        referenced_metric_ids=tuple(referenced_metric_ids),
        input_observation_ids=tuple(sorted(observation_ids)),
        input_metric_ids=tuple(sorted(referenced_metric_ids)),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=sort_diagnostics(diagnostics),
    )


__all__ = ["build_input_sufficiency_result"]
