from typing import TYPE_CHECKING, Any

from squeeze_core.metrics.identifiers import METRIC_NAMESPACE, deterministic_metric_id

if TYPE_CHECKING:
    from .models import (
        DomainCoverageSnapshot,
        EvidenceAgeAlignment,
        EvidenceConflictSummary,
        EvidenceMissingnessSummary,
        EvidenceReadinessSnapshot,
        InputSufficiencyResult,
        ReportingPeriodAlignment,
    )

# Reuses squeeze_core.metrics.identifiers.METRIC_NAMESPACE and deterministic_metric_id
# directly -- no new UUID namespace is minted (docs/phase-2d-design.md Section 13).
# Every identity dict below starts with a literal "result_type" string unique to its
# model, so two different Phase 2D result types can never collide even if every other
# field happened to coincide, and no identity dict here shares its full key set with
# any Phase 2A/2B/2C identity builder.


def deterministic_readiness_id(identity: dict[str, Any]) -> str:
    return deterministic_metric_id(identity)


def coverage_snapshot_identity(result: "DomainCoverageSnapshot") -> dict[str, Any]:
    return {
        "result_type": "DOMAIN_COVERAGE_SNAPSHOT",
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "requested_domains": sorted(item.value for item in result.requested_domains),
        "input_observation_ids": sorted(result.input_observation_ids),
        "quality_state": result.quality.state,
    }


def age_alignment_identity(result: "EvidenceAgeAlignment") -> dict[str, Any]:
    return {
        "result_type": "EVIDENCE_AGE_ALIGNMENT",
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "age_dimension": result.age_dimension,
        "domain_ages": sorted(
            (
                {
                    "domain": entry.domain.value,
                    "age_seconds": entry.age_seconds,
                    "observation_id": entry.observation_id,
                }
                for entry in result.domain_ages
            ),
            key=lambda item: item["domain"],
        ),
        "input_observation_ids": sorted(result.input_observation_ids),
        "quality_state": result.quality.state,
    }


def reporting_alignment_identity(result: "ReportingPeriodAlignment") -> dict[str, Any]:
    return {
        "result_type": "REPORTING_PERIOD_ALIGNMENT",
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "reporting_period_by_domain": sorted(
            (
                {
                    "domain": entry.domain.value,
                    "reporting_period_end": entry.reporting_period_end,
                    "observation_id": entry.observation_id,
                }
                for entry in result.reporting_period_by_domain
            ),
            key=lambda item: item["domain"],
        ),
        "input_observation_ids": sorted(result.input_observation_ids),
        "quality_state": result.quality.state,
    }


def conflict_summary_identity(result: "EvidenceConflictSummary") -> dict[str, Any]:
    return {
        "result_type": "EVIDENCE_CONFLICT_SUMMARY",
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "conflict_ids": sorted(result.conflict_ids),
        "input_observation_ids": sorted(result.input_observation_ids),
        "quality_state": result.quality.state,
    }


def missingness_summary_identity(result: "EvidenceMissingnessSummary") -> dict[str, Any]:
    return {
        "result_type": "EVIDENCE_MISSINGNESS_SUMMARY",
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "operation": result.operation,
        "missing_by_domain": sorted(
            (
                {
                    "domain": entry.domain.value,
                    "categories": sorted(item.value for item in entry.categories),
                }
                for entry in result.missing_by_domain
            ),
            key=lambda item: item["domain"],
        ),
        "missing_required_inputs": sorted(result.missing_required_inputs),
        "input_observation_ids": sorted(result.input_observation_ids),
        "input_metric_ids": sorted(result.input_metric_ids),
        "quality_state": result.quality.state,
    }


def sufficiency_result_identity(result: "InputSufficiencyResult") -> dict[str, Any]:
    return {
        "result_type": "INPUT_SUFFICIENCY",
        "operation": result.operation,
        "policy_version": result.policy_version,
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "structural_state": result.structural_state,
        "missing_inputs": sorted(result.missing_inputs),
        "invalid_inputs": sorted(result.invalid_inputs),
        "conflicted_inputs": sorted(result.conflicted_inputs),
        "incompatible_inputs": sorted(result.incompatible_inputs),
        "insufficient_history_inputs": sorted(result.insufficient_history_inputs),
        "point_in_time_failures": sorted(result.point_in_time_failures),
        "input_observation_ids": sorted(result.input_observation_ids),
        "input_metric_ids": sorted(result.input_metric_ids),
        "quality_state": result.quality.state,
    }


def readiness_snapshot_identity(result: "EvidenceReadinessSnapshot") -> dict[str, Any]:
    return {
        "result_type": "EVIDENCE_READINESS_SNAPSHOT",
        "operation": result.operation,
        "policy_version": result.policy_version,
        "symbol": result.symbol,
        "asset_class": result.asset_class,
        "as_of": result.as_of,
        "structural_state": result.structural_state,
        "coverage_snapshot_id": result.coverage_snapshot_id,
        "age_alignment_id": result.age_alignment_id,
        "reporting_alignment_id": result.reporting_alignment_id,
        "conflict_summary_id": result.conflict_summary_id,
        "missingness_summary_id": result.missingness_summary_id,
        "sufficiency_result_id": result.sufficiency_result_id,
        "input_observation_ids": sorted(result.input_observation_ids),
        "input_metric_ids": sorted(result.input_metric_ids),
        "quality_state": result.quality.state,
    }


__all__ = [
    "METRIC_NAMESPACE",
    "age_alignment_identity",
    "conflict_summary_identity",
    "coverage_snapshot_identity",
    "deterministic_readiness_id",
    "missingness_summary_identity",
    "readiness_snapshot_identity",
    "reporting_alignment_identity",
    "sufficiency_result_identity",
]
