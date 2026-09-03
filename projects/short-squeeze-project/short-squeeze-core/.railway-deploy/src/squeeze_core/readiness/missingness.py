"""Deterministic missingness-summary aggregation (docs/phase-2d-design.md Section 9).
Distinguishes MISSING_DOMAIN, UNKNOWN_AVAILABILITY, MISSING_REQUIRED_METRIC, and
INSUFFICIENT_HISTORY using only facts already visible on the coverage snapshot and
supplied metric results -- zero-valued evidence is never counted as missing."""

from typing import Any

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.evidence import CoverageDomain, PointInTimeEvidenceBundle

from .diagnostics import ReadinessDiagnostic, ReadinessDiagnosticCode, sort_diagnostics
from .models import (
    DomainCoverageSnapshot,
    DomainCoverageState,
    DomainMissingnessEntry,
    EvidenceMissingnessSummary,
    MissingnessCategory,
    OperationRequirementPolicy,
)


def _metric_name_of(result: Any) -> str | None:
    metric_name = getattr(result, "metric_name", None)
    return metric_name.value if metric_name is not None else None


def build_missingness_summary(
    bundle: PointInTimeEvidenceBundle,
    coverage_snapshot: DomainCoverageSnapshot,
    *,
    policy: OperationRequirementPolicy | None = None,
    metric_results: tuple[Any, ...] = (),
) -> EvidenceMissingnessSummary:
    required_domains = set(policy.required_domains) if policy is not None else set(
        coverage_snapshot.requested_domains
    )

    by_domain: dict[str, set[MissingnessCategory]] = {}
    unknown_domains: list[str] = []
    for entry in coverage_snapshot.coverage_by_domain:
        if entry.domain not in required_domains:
            continue
        if entry.state is DomainCoverageState.MISSING:
            by_domain.setdefault(entry.domain.value, set()).add(MissingnessCategory.MISSING_DOMAIN)
        elif entry.state is DomainCoverageState.UNKNOWN:
            by_domain.setdefault(entry.domain.value, set()).add(
                MissingnessCategory.UNKNOWN_AVAILABILITY
            )
            unknown_domains.append(entry.domain.value)

    supplied_metric_names = {
        name for name in (_metric_name_of(result) for result in metric_results) if name is not None
    }
    missing_required_inputs: list[str] = []
    insufficient_history: list[str] = []

    if policy is not None:
        for metric_name in policy.required_metric_names:
            if metric_name not in supplied_metric_names:
                missing_required_inputs.append(metric_name)
                by_domain.setdefault(f"metric:{metric_name}", set()).add(
                    MissingnessCategory.MISSING_REQUIRED_METRIC
                )

        if policy.requires_trailing_window:
            for result in metric_results:
                name = _metric_name_of(result)
                if name is None or name not in policy.required_metric_names | {policy.operation}:
                    continue
                sample_counts = getattr(result, "sample_counts", None)
                if sample_counts is not None and sample_counts.used < sample_counts.requested:
                    insufficient_history.append(name)
                    by_domain.setdefault(f"metric:{name}", set()).add(
                        MissingnessCategory.INSUFFICIENT_HISTORY
                    )

    missing_by_domain = tuple(
        DomainMissingnessEntry(domain=CoverageDomain(key), categories=tuple(categories))
        for key, categories in by_domain.items()
        if not key.startswith("metric:")
    )

    missing_domain_count = sum(
        1 for categories in by_domain.values() if MissingnessCategory.MISSING_DOMAIN in categories
    )
    missing_field_count = 0

    diagnostics: list[ReadinessDiagnostic] = []
    for domain_value, categories in by_domain.items():
        if MissingnessCategory.MISSING_DOMAIN in categories:
            diagnostics.append(
                ReadinessDiagnostic(
                    code=ReadinessDiagnosticCode.MISSINGNESS_REQUIRED_DOMAIN,
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Required domain missing: {domain_value}.",
                    domain=None if domain_value.startswith("metric:") else domain_value,
                )
            )
        if MissingnessCategory.UNKNOWN_AVAILABILITY in categories:
            diagnostics.append(
                ReadinessDiagnostic(
                    code=ReadinessDiagnosticCode.MISSINGNESS_UNKNOWN_AVAILABILITY,
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Availability unknown for domain: {domain_value}.",
                    domain=None if domain_value.startswith("metric:") else domain_value,
                )
            )
        if MissingnessCategory.MISSING_REQUIRED_METRIC in categories:
            diagnostics.append(
                ReadinessDiagnostic(
                    code=ReadinessDiagnosticCode.MISSINGNESS_REQUIRED_METRIC,
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Required metric result missing: {domain_value}.",
                )
            )
        if MissingnessCategory.INSUFFICIENT_HISTORY in categories:
            diagnostics.append(
                ReadinessDiagnostic(
                    code=ReadinessDiagnosticCode.MISSINGNESS_INSUFFICIENT_HISTORY,
                    severity=DiagnosticSeverity.WARNING,
                    message=f"Insufficient history for: {domain_value}.",
                )
            )

    asset_class = bundle.observations[0].asset_class if bundle.observations else AssetClass.UNKNOWN

    return EvidenceMissingnessSummary(
        symbol=bundle.symbol,
        asset_class=asset_class,
        as_of=bundle.as_of,
        operation=policy.operation if policy is not None else None,
        missing_domain_count=missing_domain_count,
        missing_field_count=missing_field_count,
        missing_by_domain=missing_by_domain,
        missing_required_inputs=tuple(missing_required_inputs),
        unknown_by_domain=tuple(CoverageDomain(value) for value in unknown_domains),
        input_observation_ids=coverage_snapshot.input_observation_ids,
        input_metric_ids=tuple(
            sorted(
                getattr(result, "deterministic_id", None)
                for result in metric_results
                if getattr(result, "deterministic_id", None) is not None
            )
        ),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=sort_diagnostics(diagnostics),
    )


__all__ = ["build_missingness_summary"]
