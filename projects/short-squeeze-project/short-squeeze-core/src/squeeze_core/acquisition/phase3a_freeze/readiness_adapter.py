"""Build the canonical readiness records the Phase 3A request contract accepts.

Nothing is reimplemented: the three records come from the existing Phase 2D builders. The
requested domain set is *derived from the committed Phase 3A policy file* (the union of
``required_domains`` across the 25 rules) rather than hand-picked, so a policy change
propagates automatically and no domain list is invented here.
"""

from __future__ import annotations

from datetime import datetime

from squeeze_core.contracts import Observation
from squeeze_core.evaluation.models import CandidateEvaluationPolicy
from squeeze_core.evidence import (
    CoverageDomain,
    PointInTimeEvidencePolicy,
    PointInTimeEvidenceBundle,
    build_point_in_time_evidence,
)
from squeeze_core.metrics.models import MetricResult
from squeeze_core.readiness import (
    DomainCoverageSnapshot,
    EvidenceConflictSummary,
    InputSufficiencyResult,
)
from squeeze_core.readiness.conflicts import build_conflict_summary
from squeeze_core.readiness.coverage import build_domain_coverage_snapshot
from squeeze_core.readiness.sufficiency import build_input_sufficiency_result

from .models import ADMISSIBLE_METRIC_NAME

#: The one Phase 2 operation Batch 07 admitted, and the only metric the request supplies.
SUFFICIENCY_OPERATION = ADMISSIBLE_METRIC_NAME


def requested_domains(policy: CandidateEvaluationPolicy) -> tuple[CoverageDomain, ...]:
    """Union of ``required_domains`` across the enabled rules, in enum order."""
    required = {domain for rule in policy.rules for domain in rule.required_domains}
    return tuple(domain for domain in CoverageDomain if domain in required)


def point_in_time_policy(as_of: datetime) -> PointInTimeEvidencePolicy:
    """The point-in-time policy used for every case. No new eligibility logic."""
    return PointInTimeEvidencePolicy(
        as_of=as_of,
        include_market_bars_domain=True,
        include_published_short_interest_domain=True,
        include_sec_filings_domain=True,
        include_trading_halts_domain=True,
        include_news_domain=True,
    )


def build_bundle(
    symbol: str, observations: tuple[Observation, ...], as_of: datetime
) -> PointInTimeEvidenceBundle:
    return build_point_in_time_evidence(symbol, observations, point_in_time_policy(as_of))


def build_readiness_records(
    bundle: PointInTimeEvidenceBundle,
    policy: CandidateEvaluationPolicy,
    metric: MetricResult | None,
) -> tuple[DomainCoverageSnapshot, EvidenceConflictSummary, InputSufficiencyResult]:
    """The three canonical readiness records, in stable order."""
    domains = requested_domains(policy)
    coverage = build_domain_coverage_snapshot(bundle, domains)
    conflicts = build_conflict_summary(bundle, domains)
    sufficiency = build_input_sufficiency_result(
        bundle,
        SUFFICIENCY_OPERATION,
        metric_results=() if metric is None else (metric,),
    )
    return coverage, conflicts, sufficiency


__all__ = [
    "SUFFICIENCY_OPERATION",
    "build_bundle",
    "build_readiness_records",
    "point_in_time_policy",
    "requested_domains",
]
