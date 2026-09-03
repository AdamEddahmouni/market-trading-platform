"""Cross-domain reporting-period alignment (docs/phase-2d-design.md Section 7).
Applies only to domains with a genuine reporting-period concept in the existing
payload models -- PUBLISHED_SHORT_INTEREST (settlement_date) and SEC_FILINGS
(period_of_report). Publication time and receipt time are never substituted for a
reporting period."""

from datetime import date

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.contracts.observation import Observation
from squeeze_core.evidence import CoverageDomain, PointInTimeEvidenceBundle
from squeeze_core.metrics.source_age import build_source_age

from .diagnostics import ReadinessDiagnostic, ReadinessDiagnosticCode, sort_diagnostics
from .models import ReportingPeriodAlignment, ReportingPeriodEntry

# Only these two domains have a genuine reporting-period field on their canonical
# payload model. No other domain is ever eligible for this alignment.
REPORTING_PERIOD_FIELDS: dict[CoverageDomain, str] = {
    CoverageDomain.PUBLISHED_SHORT_INTEREST: "settlement_date",
    CoverageDomain.SEC_FILINGS: "period_of_report",
}


def _period_end(observation: Observation, domain: CoverageDomain) -> date | None:
    field = REPORTING_PERIOD_FIELDS.get(domain)
    if field is None:
        return None
    return getattr(observation.payload, field, None)


def _representative_period(
    bundle: PointInTimeEvidenceBundle, domain: CoverageDomain
) -> tuple[date | None, str | None]:
    """Selects the most-current (latest effective_timestamp) eligible observation
    with a non-null reporting period, consistent with age_alignment's "freshest
    record represents the domain" rationale."""

    if domain not in REPORTING_PERIOD_FIELDS:
        return None, None
    coverage_entry = next((c for c in bundle.source_coverage if c.domain is domain), None)
    if coverage_entry is None or not coverage_entry.observation_ids:
        return None, None
    observation_ids = set(coverage_entry.observation_ids)
    candidates = [
        o
        for o in bundle.observations
        if o.observation_id in observation_ids and _period_end(o, domain) is not None
    ]
    if not candidates:
        return None, None
    best = max(candidates, key=lambda o: o.effective_timestamp)
    return _period_end(best, domain), best.observation_id


def build_reporting_period_alignment(
    bundle: PointInTimeEvidenceBundle,
    domains: tuple[CoverageDomain, ...],
) -> ReportingPeriodAlignment:
    entries: list[ReportingPeriodEntry] = []
    missing_domains: list[CoverageDomain] = []
    observation_ids: set[str] = set()
    period_ends: list[date] = []

    for domain in domains:
        period_end, observation_id = _representative_period(bundle, domain)
        age_seconds: int | None = None
        if period_end is not None and observation_id is not None:
            observation = next(
                o for o in bundle.observations if o.observation_id == observation_id
            )
            age_seconds = (
                build_source_age(
                    observation, bundle.as_of, reporting_period_end=period_end
                ).reporting_period_age_days
                * 86400
            )
            period_ends.append(period_end)
            observation_ids.add(observation_id)
        else:
            missing_domains.append(domain)
        entries.append(
            ReportingPeriodEntry(
                domain=domain,
                reporting_period_end=period_end,
                reporting_period_age_seconds=age_seconds,
                observation_id=observation_id,
            )
        )

    diagnostics: list[ReadinessDiagnostic] = []
    for domain in domains:
        if domain not in REPORTING_PERIOD_FIELDS:
            diagnostics.append(
                ReadinessDiagnostic(
                    code=ReadinessDiagnosticCode.AGE_ALIGNMENT_REPORTING_PERIOD_NOT_APPLICABLE,
                    severity=DiagnosticSeverity.INFO,
                    message=f"Domain {domain.value} has no reporting-period concept.",
                    domain=domain.value,
                )
            )

    asset_class = bundle.observations[0].asset_class if bundle.observations else AssetClass.UNKNOWN
    earliest = min(period_ends) if period_ends else None
    latest = max(period_ends) if period_ends else None
    spread = (latest - earliest).days * 86400 if period_ends else None

    return ReportingPeriodAlignment(
        symbol=bundle.symbol,
        asset_class=asset_class,
        as_of=bundle.as_of,
        reporting_period_by_domain=tuple(entries),
        earliest_reporting_period_end=earliest,
        latest_reporting_period_end=latest,
        reporting_period_spread_seconds=spread,
        missing_reporting_period_domains=tuple(missing_domains),
        input_observation_ids=tuple(sorted(observation_ids)),
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=sort_diagnostics(diagnostics),
    )


__all__ = ["build_reporting_period_alignment"]
