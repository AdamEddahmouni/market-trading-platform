"""Cross-domain evidence-age alignment (docs/phase-2d-design.md Section 6). Reuses
squeeze_core.metrics.source_age.build_source_age directly rather than reimplementing
age arithmetic."""

from decimal import Decimal

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.evidence import CoverageDomain, PointInTimeEvidenceBundle
from squeeze_core.metrics.source_age import build_source_age
from squeeze_core.metrics.statistics import decimal_mean

from .diagnostics import ReadinessDiagnostic, ReadinessDiagnosticCode, sort_diagnostics
from .models import AgeDimension, DomainAgeEntry, EvidenceAgeAlignment


def _representative_availability_age(
    bundle: PointInTimeEvidenceBundle, domain: CoverageDomain
) -> tuple[int | None, str | None]:
    """The representative age for a domain is the MINIMUM (freshest) availability age
    among its point-in-time-eligible observations -- see docs/phase-2d-design.md
    Section 6 for the rationale (answers "how current can this domain be treated as
    of as_of", not "how old is the oldest thing we still have")."""

    coverage_entry = next((c for c in bundle.source_coverage if c.domain is domain), None)
    if coverage_entry is None or not coverage_entry.observation_ids:
        return None, None
    observation_ids = set(coverage_entry.observation_ids)
    candidates = [o for o in bundle.observations if o.observation_id in observation_ids]
    if not candidates:
        return None, None

    best_observation_id: str | None = None
    best_age: int | None = None
    for observation in candidates:
        age = build_source_age(observation, bundle.as_of).availability_age_seconds
        if best_age is None or age < best_age:
            best_age = age
            best_observation_id = observation.observation_id
    return best_age, best_observation_id


def build_evidence_age_alignment(
    bundle: PointInTimeEvidenceBundle,
    domains: tuple[CoverageDomain, ...],
    *,
    age_dimension: AgeDimension = AgeDimension.AVAILABILITY_AGE,
) -> EvidenceAgeAlignment:
    if age_dimension is not AgeDimension.AVAILABILITY_AGE:
        raise ValueError(
            "build_evidence_age_alignment only computes AVAILABILITY_AGE; use "
            "build_reporting_period_alignment for REPORTING_PERIOD_AGE"
        )

    entries: list[DomainAgeEntry] = []
    missing_age_domains: list[CoverageDomain] = []
    observation_ids: set[str] = set()
    comparable_ages: list[int] = []

    for domain in domains:
        age, observation_id = _representative_availability_age(bundle, domain)
        entries.append(DomainAgeEntry(domain=domain, age_seconds=age, observation_id=observation_id))
        if age is None:
            missing_age_domains.append(domain)
        else:
            comparable_ages.append(age)
            if observation_id is not None:
                observation_ids.add(observation_id)

    diagnostics: list[ReadinessDiagnostic] = []
    if not comparable_ages:
        diagnostics.append(
            ReadinessDiagnostic(
                code=ReadinessDiagnosticCode.AGE_ALIGNMENT_NO_COMPARABLE_DOMAINS,
                severity=DiagnosticSeverity.INFO,
                message="No domain in the requested set has a comparable availability age.",
            )
        )
    elif len(comparable_ages) == 1:
        diagnostics.append(
            ReadinessDiagnostic(
                code=ReadinessDiagnosticCode.AGE_ALIGNMENT_SINGLE_DOMAIN_ONLY,
                severity=DiagnosticSeverity.INFO,
                message="Only one domain has a comparable availability age; spread is zero by definition.",
            )
        )

    asset_class = bundle.observations[0].asset_class if bundle.observations else AssetClass.UNKNOWN
    youngest = min(comparable_ages) if comparable_ages else None
    oldest = max(comparable_ages) if comparable_ages else None
    spread = (oldest - youngest) if comparable_ages else None
    mean = decimal_mean([Decimal(age) for age in comparable_ages]) if comparable_ages else None

    return EvidenceAgeAlignment(
        symbol=bundle.symbol,
        asset_class=asset_class,
        as_of=bundle.as_of,
        age_dimension=age_dimension,
        domain_ages=tuple(entries),
        youngest_age_seconds=youngest,
        oldest_age_seconds=oldest,
        age_spread_seconds=spread,
        mean_age_seconds=mean,
        domain_count=len(comparable_ages),
        missing_age_domains=tuple(missing_age_domains),
        input_observation_ids=tuple(sorted(observation_ids)),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=sort_diagnostics(diagnostics),
    )


__all__ = ["build_evidence_age_alignment"]
