"""Strict as-of replay for a validation case.

This module implements **no** point-in-time filtering of its own. Eligibility,
no-look-ahead, lifecycle handling (corrections, cancellations, revisions), and
freshness all come from `squeeze_core.evidence.build_point_in_time_evidence`; every
structural diagnostic comes from `squeeze_core.readiness`. What is added here is
orchestration: run those existing engines at a given `as_of` and record what they
returned, with a deterministic identity.

If this module ever grows a timestamp comparison against `as_of`, that is a bug -- it
means a second point-in-time engine has started to appear.
"""

from collections.abc import Sequence
from datetime import datetime

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import Observation, Quality
from squeeze_core.contracts.enums import QualityState
from squeeze_core.evidence import PointInTimeEvidencePolicy, build_point_in_time_evidence
from squeeze_core.readiness import (
    StructuralState,
    build_conflict_summary,
    build_domain_coverage_snapshot,
    build_evidence_age_alignment,
    build_evidence_readiness_snapshot,
    build_input_sufficiency_result,
    build_missingness_summary,
    build_reporting_period_alignment,
    lookup_policy,
)
from squeeze_core.readiness.reporting_alignment import REPORTING_PERIOD_FIELDS

from .diagnostics import ValidationDiagnostic, ValidationDiagnosticCode, sort_diagnostics
from .identifiers import deterministic_validation_id, replay_identity
from .models import RebuiltAsOfSnapshot


def _default_policy(as_of: datetime) -> PointInTimeEvidencePolicy:
    """Every optional domain enabled, so a genuinely absent domain resolves MISSING
    rather than UNKNOWN -- the same choice the readiness CLI makes, for the same
    reason: a validation replay must not silently under-evaluate coverage."""

    return PointInTimeEvidencePolicy(
        as_of=as_of,
        allow_stale=True,
        allow_delayed=True,
        allow_unknown_freshness=True,
        include_published_short_interest_domain=True,
        include_sec_filings_domain=True,
        include_trading_halts_domain=True,
        include_news_domain=True,
        include_market_bars_domain=True,
        include_trades_domain=True,
        include_quotes_domain=True,
    )


def build_rebuilt_as_of_snapshot(
    label: str,
    symbol: str,
    observations: Sequence[Observation],
    as_of: datetime,
    *,
    operation: str | None = None,
    policy_version: str | None = None,
    evidence_policy: PointInTimeEvidencePolicy | None = None,
    metric_results: Sequence[object] = (),
) -> RebuiltAsOfSnapshot:
    """Replay `symbol` strictly as of `as_of`.

    `operation` names an already-implemented Phase 2A/2B/2C operation whose input
    contract should be checked. When omitted, coverage/age/conflict diagnostics are
    still produced but no sufficiency verdict is claimed.
    """

    policy = evidence_policy or _default_policy(as_of)
    bundle = build_point_in_time_evidence(symbol, observations, policy)

    diagnostics: list[ValidationDiagnostic] = []

    if operation is None:
        requirement = None
        required_domains: tuple = ()
    else:
        requirement = lookup_policy(operation, policy_version)
        required_domains = requirement.required_domains

    coverage = build_domain_coverage_snapshot(bundle, required_domains)
    conflicts = build_conflict_summary(bundle, required_domains)
    age = build_evidence_age_alignment(bundle, required_domains)
    reporting_domains = tuple(
        domain for domain in required_domains if domain in REPORTING_PERIOD_FIELDS
    )
    reporting = (
        build_reporting_period_alignment(bundle, reporting_domains) if reporting_domains else None
    )

    if requirement is None:
        missingness = None
        sufficiency = None
        readiness = None
        structural_state = None
    else:
        missingness = build_missingness_summary(bundle, coverage, policy=requirement)
        sufficiency = build_input_sufficiency_result(
            bundle, operation, policy_version=policy_version, metric_results=tuple(metric_results)
        )
        readiness = build_evidence_readiness_snapshot(
            bundle, operation, policy_version=policy_version
        )
        structural_state = readiness.structural_state

        if structural_state == StructuralState.INSUFFICIENT:
            diagnostics.append(
                ValidationDiagnostic(
                    code=ValidationDiagnosticCode.VALIDATION_REBUILT_INPUT_INSUFFICIENT,
                    severity=DiagnosticSeverity.WARNING,
                    message=(
                        f"inputs for {operation} are structurally insufficient at this as-of; "
                        "the metric is absent rather than defaulted"
                    ),
                )
            )
        elif structural_state == StructuralState.CONFLICTED:
            diagnostics.append(
                ValidationDiagnostic(
                    code=ValidationDiagnosticCode.VALIDATION_REBUILT_INPUT_CONFLICTED,
                    severity=DiagnosticSeverity.WARNING,
                    message=f"inputs for {operation} conflict at this as-of",
                )
            )

    metric_ids = tuple(
        getattr(result, "deterministic_id", "") for result in metric_results
    )
    metric_ids = tuple(item for item in metric_ids if item)
    if operation is not None and not metric_ids:
        diagnostics.append(
            ValidationDiagnostic(
                code=ValidationDiagnosticCode.VALIDATION_REBUILT_METRIC_UNAVAILABLE,
                severity=DiagnosticSeverity.INFO,
                message=(
                    "no metric result was supplied for this replay; unavailable metrics are "
                    "omitted, never computed as zero"
                ),
            )
        )

    draft = RebuiltAsOfSnapshot(
        label=label,
        symbol=symbol.strip().upper(),
        as_of=as_of,
        # Taken from the bundle, not from the coverage snapshot: coverage is scoped to
        # the operation's required domains, so deriving eligibility from it would report
        # nothing whenever no operation was named.
        eligible_observation_ids=tuple(item.observation_id for item in bundle.observations),
        eligible_metric_ids=metric_ids,
        coverage_snapshot_id=coverage.deterministic_id,
        age_alignment_id=age.deterministic_id,
        reporting_alignment_id=None if reporting is None else reporting.deterministic_id,
        conflict_summary_id=conflicts.deterministic_id,
        missingness_summary_id=None if missingness is None else missingness.deterministic_id,
        sufficiency_result_id=None if sufficiency is None else sufficiency.deterministic_id,
        operation=operation,
        structural_state=structural_state,
        present_domains=tuple(item.value for item in coverage.present_domains),
        missing_domains=tuple(item.value for item in coverage.missing_domains),
        conflicted_domains=tuple(item.value for item in coverage.conflicted_domains),
        metric_results=metric_ids,
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=sort_diagnostics(diagnostics),
        deterministic_id="",
    )
    return draft.model_copy(
        update={"deterministic_id": deterministic_validation_id(replay_identity(draft))}
    )


def build_boundary_replays(
    symbol: str,
    observations: Sequence[Observation],
    boundaries: Sequence[tuple[str, datetime]],
    *,
    operation: str | None = None,
    policy_version: str | None = None,
) -> tuple[RebuiltAsOfSnapshot, ...]:
    """One replay per detection-time boundary, in chronological order.

    Every boundary is replayed and every result returned. Nothing here filters for the
    most favourable outcome; divergence between boundaries is a finding to report.
    """

    return tuple(
        sorted(
            (
                build_rebuilt_as_of_snapshot(
                    label,
                    symbol,
                    observations,
                    as_of,
                    operation=operation,
                    policy_version=policy_version,
                )
                for label, as_of in boundaries
            ),
            key=lambda item: (item.as_of, item.label),
        )
    )


__all__ = ["build_boundary_replays", "build_rebuilt_as_of_snapshot"]
