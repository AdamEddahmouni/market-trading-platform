"""Deterministic conflict-summary aggregation (docs/phase-2d-design.md Section 8). A
thin grouping over squeeze_core.evidence.EvidenceConflict, which already excludes
revisions/corrections/cancellations -- no new conflict-detection logic is implemented
here, and no conflict is ever resolved. TEMPORAL_DIFFERENCE-classified entries are
retained in bundle.conflicts by Phase 1 for audit purposes but are explicitly not
real conflicts ("compatible field, different comparison_period"), so this module
excludes them from every count, exactly as squeeze_core.evidence's own coverage-state
computation does."""

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.evidence import ConflictClassification, CoverageDomain, PointInTimeEvidenceBundle

from .diagnostics import ReadinessDiagnostic, ReadinessDiagnosticCode, sort_diagnostics
from .models import DomainConflictEntry, EvidenceConflictSummary


def build_conflict_summary(
    bundle: PointInTimeEvidenceBundle,
    domains: tuple[CoverageDomain, ...],
) -> EvidenceConflictSummary:
    domain_observation_ids: dict[CoverageDomain, set[str]] = {}
    for domain in domains:
        coverage_entry = next((c for c in bundle.source_coverage if c.domain is domain), None)
        domain_observation_ids[domain] = (
            set(coverage_entry.observation_ids) if coverage_entry else set()
        )

    conflicts_by_domain: list[DomainConflictEntry] = []
    all_conflict_ids: set[str] = set()
    affected_observation_ids: set[str] = set()
    categories: set = set()

    for domain in domains:
        domain_ids = domain_observation_ids[domain]
        matching = [
            conflict
            for conflict in bundle.conflicts
            if conflict.classification is not ConflictClassification.TEMPORAL_DIFFERENCE
            and set(conflict.observation_ids) & domain_ids
        ]
        if not matching:
            continue
        conflict_ids = tuple(conflict.conflict_id for conflict in matching)
        conflicts_by_domain.append(DomainConflictEntry(domain=domain, conflict_ids=conflict_ids))
        all_conflict_ids.update(conflict_ids)
        for conflict in matching:
            affected_observation_ids.update(conflict.observation_ids)
            categories.add(conflict.classification)

    diagnostics: list[ReadinessDiagnostic] = []
    if not all_conflict_ids:
        diagnostics.append(
            ReadinessDiagnostic(
                code=ReadinessDiagnosticCode.CONFLICT_SUMMARY_NO_CONFLICTS,
                severity=DiagnosticSeverity.INFO,
                message="No unresolved conflicts found in the requested domains.",
            )
        )
    else:
        diagnostics.append(
            ReadinessDiagnostic(
                code=ReadinessDiagnosticCode.CONFLICT_SUMMARY_UNRESOLVED_CONFLICT,
                severity=DiagnosticSeverity.WARNING,
                message=f"{len(all_conflict_ids)} unresolved conflict(s) found.",
            )
        )

    asset_class = bundle.observations[0].asset_class if bundle.observations else AssetClass.UNKNOWN

    return EvidenceConflictSummary(
        symbol=bundle.symbol,
        asset_class=asset_class,
        as_of=bundle.as_of,
        conflict_count=len(all_conflict_ids),
        conflicts_by_domain=tuple(conflicts_by_domain),
        conflict_ids=tuple(sorted(all_conflict_ids)),
        affected_observation_ids=tuple(sorted(affected_observation_ids)),
        affected_metric_ids=(),
        conflict_categories=tuple(categories),
        input_observation_ids=tuple(sorted(affected_observation_ids)),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=sort_diagnostics(diagnostics),
    )


__all__ = ["build_conflict_summary"]
