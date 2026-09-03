"""Aggregate operation-scoped readiness snapshot (docs/phase-2d-design.md Section 12).
References its component results by their deterministic ID rather than embedding
them, so each component stays small and independently anchorable/testable."""

from typing import Any

from squeeze_core.contracts import AssetClass, Quality, QualityState
from squeeze_core.evidence import PointInTimeEvidenceBundle

from .age_alignment import build_evidence_age_alignment
from .conflicts import build_conflict_summary
from .coverage import build_domain_coverage_snapshot
from .missingness import build_missingness_summary
from .models import EvidenceReadinessSnapshot
from .policies import lookup_policy
from .reporting_alignment import REPORTING_PERIOD_FIELDS, build_reporting_period_alignment
from .sufficiency import build_input_sufficiency_result


def build_evidence_readiness_snapshot(
    bundle: PointInTimeEvidenceBundle,
    operation: str,
    *,
    policy_version: str | None = None,
    metric_results: tuple[Any, ...] = (),
) -> EvidenceReadinessSnapshot:
    policy = lookup_policy(operation, policy_version)

    coverage_snapshot = build_domain_coverage_snapshot(bundle, policy.required_domains)
    sufficiency = build_input_sufficiency_result(
        bundle, operation, policy_version=policy_version, metric_results=metric_results
    )
    conflict_summary = build_conflict_summary(bundle, policy.required_domains)
    missingness_summary = build_missingness_summary(
        bundle, coverage_snapshot, policy=policy, metric_results=metric_results
    )

    age_alignment = build_evidence_age_alignment(bundle, policy.required_domains)

    reporting_domains = tuple(
        domain for domain in policy.required_domains if domain in REPORTING_PERIOD_FIELDS
    )
    reporting_alignment = (
        build_reporting_period_alignment(bundle, reporting_domains) if reporting_domains else None
    )

    observation_ids = set(sufficiency.input_observation_ids) | set(
        coverage_snapshot.input_observation_ids
    )

    asset_class = bundle.observations[0].asset_class if bundle.observations else AssetClass.UNKNOWN

    return EvidenceReadinessSnapshot(
        operation=policy.operation,
        policy_version=policy.policy_version,
        symbol=bundle.symbol,
        asset_class=asset_class,
        as_of=bundle.as_of,
        structural_state=sufficiency.structural_state,
        required_domains=policy.required_domains,
        required_metrics=policy.required_metric_names,
        coverage_snapshot_id=coverage_snapshot.deterministic_id,
        age_alignment_id=age_alignment.deterministic_id,
        reporting_alignment_id=(
            reporting_alignment.deterministic_id if reporting_alignment is not None else None
        ),
        conflict_summary_id=conflict_summary.deterministic_id,
        missingness_summary_id=missingness_summary.deterministic_id,
        sufficiency_result_id=sufficiency.deterministic_id,
        missing_inputs=sufficiency.missing_inputs,
        conflicted_inputs=sufficiency.conflicted_inputs,
        incompatible_inputs=sufficiency.incompatible_inputs,
        insufficient_history_inputs=sufficiency.insufficient_history_inputs,
        input_observation_ids=tuple(sorted(observation_ids)),
        input_metric_ids=sufficiency.input_metric_ids,
        quality=Quality(state=QualityState.KNOWN_VALUE),
        diagnostics=(),
    )


__all__ = ["build_evidence_readiness_snapshot"]
