"""Deterministic domain-coverage classification (docs/phase-2d-design.md Section 5).
Consumes an already-built squeeze_core.evidence.PointInTimeEvidenceBundle -- no new
point-in-time eligibility logic is implemented here; no-look-ahead is inherited from
the bundle."""

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.contracts.observation import Observation
from squeeze_core.evidence import (
    ConflictClassification,
    CoverageDomain,
    CoverageState,
    PointInTimeEvidenceBundle,
)

from .diagnostics import ReadinessDiagnostic, ReadinessDiagnosticCode, sort_diagnostics
from .models import DomainCoverageEntry, DomainCoverageSnapshot, DomainCoverageState

# Per-domain lifecycle metadata field used to detect cancellation, mirroring the exact
# fields squeeze_core.evidence.builder uses to link revisions (docs/phase-2d-design.md
# Section 5 table). An unmapped domain, or a missing metadata key, is defensively
# treated as "not cancelled" -- it never raises and never promotes a domain to
# CANCELLED on absent data.
_CANCELLATION_METADATA: dict[CoverageDomain, tuple[str, frozenset[str]]] = {
    CoverageDomain.PUBLISHED_SHORT_INTEREST: ("revision_status", frozenset({"CANCELLED"})),
    CoverageDomain.SEC_FILINGS: ("filing_status", frozenset({"CANCELLED"})),
    CoverageDomain.TRADING_HALTS: ("revision_status", frozenset({"CANCELLED"})),
    CoverageDomain.NEWS: ("status", frozenset({"WITHDRAWN", "DELETED"})),
    CoverageDomain.MARKET_BARS: ("status", frozenset({"CANCELLED"})),
    CoverageDomain.TRADES: ("status", frozenset({"CANCELLED", "DELETED"})),
    CoverageDomain.QUOTES: ("status", frozenset({"CANCELLED", "DELETED"})),
}

# Diagnostic-code substrings that mean "evidence existed but was point-in-time
# ineligible" as opposed to "no evidence exists at all" -- used to distinguish
# UNAVAILABLE from MISSING (docs/phase-2d-design.md Section 5, step 5).
_EXCLUDED_DIAGNOSTIC_MARKERS = (
    "NOT_YET_PUBLISHED",
    "NOT_YET_RECEIVED",
    "NOT_YET_ACCEPTED",
    "NOT_YET_AVAILABLE",
    "EXCLUDED_AFTER_AS_OF",
    "EXCLUDED_RECEIVED_AFTER_AS_OF",
    "FUTURE_EVENT",
)


def _is_cancelled(observation: Observation, domain: CoverageDomain) -> bool:
    mapping = _CANCELLATION_METADATA.get(domain)
    if mapping is None:
        return False
    key, cancelled_values = mapping
    value = observation.provenance.provider_metadata.get(key)
    return isinstance(value, str) and value in cancelled_values


def classify_domain_coverage(
    bundle: PointInTimeEvidenceBundle, domain: CoverageDomain
) -> tuple[DomainCoverageState, list[str]]:
    """Returns the domain's DomainCoverageState plus the diagnostic codes (as plain
    strings) that justify it, following the precedence in docs/phase-2d-design.md
    Section 5: UNKNOWN > CANCELLED > CONFLICTED > PARTIAL > UNAVAILABLE > MISSING >
    PRESENT."""

    coverage_entry = next((c for c in bundle.source_coverage if c.domain is domain), None)
    if coverage_entry is None:
        return DomainCoverageState.UNKNOWN, ["COVERAGE_DOMAIN_UNKNOWN"]

    observation_ids = set(coverage_entry.observation_ids)
    domain_observations = [o for o in bundle.observations if o.observation_id in observation_ids]

    if domain_observations and all(_is_cancelled(o, domain) for o in domain_observations):
        return DomainCoverageState.CANCELLED, ["COVERAGE_DOMAIN_CANCELLED"]

    # TEMPORAL_DIFFERENCE conflicts are explicitly not real conflicts (docs/phase-2d-
    # design.md Section 8, mirroring squeeze_core.evidence.conflicts' own
    # "compatible field, different comparison_period -- not a real conflict" rule).
    domain_conflicted = coverage_entry.state is CoverageState.CONFLICTED or any(
        conflict.classification is not ConflictClassification.TEMPORAL_DIFFERENCE
        and set(conflict.observation_ids) & observation_ids
        for conflict in bundle.conflicts
    )
    if domain_conflicted:
        return DomainCoverageState.CONFLICTED, ["COVERAGE_DOMAIN_CONFLICTED"]

    if coverage_entry.state is CoverageState.PARTIAL:
        return DomainCoverageState.PARTIAL, ["COVERAGE_DOMAIN_PARTIAL"]

    if coverage_entry.state is CoverageState.MISSING:
        domain_diagnostics = [d for d in bundle.diagnostics if d.domain is domain]
        if any(
            marker in diagnostic.code.value
            for diagnostic in domain_diagnostics
            for marker in _EXCLUDED_DIAGNOSTIC_MARKERS
        ):
            return DomainCoverageState.UNAVAILABLE, ["COVERAGE_DOMAIN_UNAVAILABLE"]
        return DomainCoverageState.MISSING, ["COVERAGE_DOMAIN_MISSING"]

    if domain_observations and all(
        o.quality.state in (QualityState.UNAVAILABLE, QualityState.INVALID)
        for o in domain_observations
    ):
        return DomainCoverageState.UNAVAILABLE, ["COVERAGE_DOMAIN_UNAVAILABLE"]

    return DomainCoverageState.PRESENT, ["COVERAGE_DOMAIN_PRESENT"]


_STATE_BUCKETS: dict[DomainCoverageState, str] = {
    DomainCoverageState.PRESENT: "present_domains",
    DomainCoverageState.MISSING: "missing_domains",
    DomainCoverageState.UNAVAILABLE: "unavailable_domains",
    DomainCoverageState.CONFLICTED: "conflicted_domains",
    DomainCoverageState.CANCELLED: "cancelled_domains",
    DomainCoverageState.PARTIAL: "partial_domains",
    DomainCoverageState.UNKNOWN: "unknown_domains",
}


def build_domain_coverage_snapshot(
    bundle: PointInTimeEvidenceBundle,
    requested_domains: tuple[CoverageDomain, ...],
) -> DomainCoverageSnapshot:
    buckets: dict[str, list[CoverageDomain]] = {name: [] for name in _STATE_BUCKETS.values()}
    entries: list[DomainCoverageEntry] = []
    diagnostics: list[ReadinessDiagnostic] = []
    all_observation_ids: set[str] = set()

    for domain in requested_domains:
        state, codes = classify_domain_coverage(bundle, domain)
        buckets[_STATE_BUCKETS[state]].append(domain)

        coverage_entry = next((c for c in bundle.source_coverage if c.domain is domain), None)
        observation_ids = tuple(coverage_entry.observation_ids) if coverage_entry else ()
        all_observation_ids.update(observation_ids)

        conflict_ids = tuple(
            conflict.conflict_id
            for conflict in bundle.conflicts
            if conflict.classification is not ConflictClassification.TEMPORAL_DIFFERENCE
            and set(conflict.observation_ids) & set(observation_ids)
        )

        entries.append(
            DomainCoverageEntry(
                domain=domain,
                state=state,
                observation_ids=observation_ids,
                conflict_ids=conflict_ids,
                diagnostic_codes=tuple(codes),
            )
        )
        for code in codes:
            diagnostics.append(
                ReadinessDiagnostic(
                    code=ReadinessDiagnosticCode(code),
                    severity=DiagnosticSeverity.INFO,
                    message=f"Domain {domain.value} classified as {state.value}.",
                    domain=domain.value,
                )
            )

    return DomainCoverageSnapshot(
        symbol=bundle.symbol,
        asset_class=domain_observations_asset_class(bundle),
        as_of=bundle.as_of,
        requested_domains=requested_domains,
        present_domains=tuple(buckets["present_domains"]),
        missing_domains=tuple(buckets["missing_domains"]),
        unavailable_domains=tuple(buckets["unavailable_domains"]),
        conflicted_domains=tuple(buckets["conflicted_domains"]),
        cancelled_domains=tuple(buckets["cancelled_domains"]),
        partial_domains=tuple(buckets["partial_domains"]),
        unknown_domains=tuple(buckets["unknown_domains"]),
        coverage_by_domain=tuple(entries),
        input_observation_ids=tuple(sorted(all_observation_ids)),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=sort_diagnostics(diagnostics),
    )


def domain_observations_asset_class(bundle: PointInTimeEvidenceBundle) -> AssetClass:
    if bundle.observations:
        return bundle.observations[0].asset_class
    return AssetClass.UNKNOWN


__all__ = ["build_domain_coverage_snapshot", "classify_domain_coverage"]
