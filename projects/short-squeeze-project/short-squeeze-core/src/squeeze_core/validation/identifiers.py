from typing import TYPE_CHECKING, Any

from squeeze_core.metrics.identifiers import METRIC_NAMESPACE, deterministic_metric_id

if TYPE_CHECKING:
    from .models import (
        CandidateOutcomeObservation,
        DetectionTimeEvidence,
        FieldComparisonEntry,
        OriginalCandidateSnapshot,
        PublicValidationCase,
        RebuiltAsOfSnapshot,
        RuleValidationEntry,
        ValidationCase,
        ValidationCaseConclusion,
    )

# Reuses squeeze_core.metrics.identifiers.METRIC_NAMESPACE directly -- no new UUID
# namespace is minted, matching the Phase 2D rationale (docs/phase-2d-design.md
# Section 3) and Phase 2B/2C before it. Every identity dict below starts with a literal
# "result_type" unique to its model, so a Phase 2V result can never collide with a
# Phase 1/2A/2B/2C/2D result even if every other field coincided, and no identity dict
# here shares its full key set with any prior phase's identity builder.


def deterministic_validation_id(identity: dict[str, Any]) -> str:
    return deterministic_metric_id(identity)


def detection_time_identity(result: "DetectionTimeEvidence") -> dict[str, Any]:
    return {
        "result_type": "DETECTION_TIME_EVIDENCE",
        "symbol": result.symbol,
        "state": result.state,
        "exact_timestamp": result.exact_timestamp,
        "window_start": result.window_start,
        "window_end": result.window_end,
        "timezone": result.timezone,
        "source_artifact_ids": sorted(result.source_artifact_ids),
        "quality_state": result.quality.state,
    }


def original_snapshot_identity(result: "OriginalCandidateSnapshot") -> dict[str, Any]:
    return {
        "result_type": "ORIGINAL_CANDIDATE_SNAPSHOT",
        "symbol": result.symbol,
        "detection_time_evidence_id": result.detection_time_evidence_id,
        "field_values": sorted(
            (
                {
                    "field_id": entry.field_id,
                    "state": entry.state.value,
                    "value": None if entry.value is None else str(entry.value),
                    "unit": entry.unit,
                    "provider": entry.provider,
                }
                for entry in result.original_field_values
            ),
            key=lambda item: item["field_id"],
        ),
        "rule_results": sorted(
            (
                {"rule_id": entry.rule_id, "state": entry.state.value, "outcome": entry.outcome}
                for entry in result.original_rule_results
            ),
            key=lambda item: item["rule_id"],
        ),
        "original_score_if_any": result.original_score_if_any,
        "original_label_if_any": result.original_label_if_any,
        "source_artifact_ids": sorted(result.source_artifact_ids),
        "quality_state": result.quality.state,
    }


def replay_identity(result: "RebuiltAsOfSnapshot") -> dict[str, Any]:
    return {
        "result_type": "REBUILT_AS_OF_SNAPSHOT",
        "label": result.label,
        "symbol": result.symbol,
        "as_of": result.as_of,
        "operation": result.operation,
        "structural_state": result.structural_state,
        "eligible_observation_ids": sorted(result.eligible_observation_ids),
        "eligible_metric_ids": sorted(result.eligible_metric_ids),
        "coverage_snapshot_id": result.coverage_snapshot_id,
        "age_alignment_id": result.age_alignment_id,
        "reporting_alignment_id": result.reporting_alignment_id,
        "conflict_summary_id": result.conflict_summary_id,
        "missingness_summary_id": result.missingness_summary_id,
        "sufficiency_result_id": result.sufficiency_result_id,
        "quality_state": result.quality.state,
    }


def field_comparison_identity(result: "FieldComparisonEntry") -> dict[str, Any]:
    return {
        "result_type": "FIELD_COMPARISON_ENTRY",
        "field_id": result.field_id,
        "original_value": None if result.original_value is None else str(result.original_value),
        "original_unit": result.original_unit,
        "original_provider": result.original_provider,
        "rebuilt_value": None if result.rebuilt_value is None else str(result.rebuilt_value),
        "rebuilt_unit": result.rebuilt_unit,
        "rebuilt_provider": result.rebuilt_provider,
        "available_at_detection": result.available_at_detection,
        "comparison_state": result.comparison_state,
        "supporting_artifact_ids": sorted(result.supporting_artifact_ids),
        "supporting_observation_ids": sorted(result.supporting_observation_ids),
        "supporting_metric_ids": sorted(result.supporting_metric_ids),
    }


def rule_validation_identity(result: "RuleValidationEntry") -> dict[str, Any]:
    """`state` is part of the identity: the same rule assessed under different evidence
    must produce a different id, so a reclassification is never mistaken for the
    earlier judgement."""

    return {
        "result_type": "RULE_VALIDATION_ENTRY",
        "rule_id": result.rule_id,
        "state": result.state,
        "corrections_required": sorted(result.corrections_required),
        "supporting_artifact_ids": sorted(result.supporting_artifact_ids),
        "supporting_field_ids": sorted(result.supporting_field_ids),
    }


def outcome_observation_identity(result: "CandidateOutcomeObservation") -> dict[str, Any]:
    return {
        "result_type": "CANDIDATE_OUTCOME_OBSERVATION",
        "symbol": result.symbol,
        "detection_time_evidence_id": result.detection_time_evidence_id,
        "reference_price": None if result.reference_price is None else str(result.reference_price),
        "reference_price_time": result.reference_price_time,
        "windows": sorted(
            (
                {
                    "window": entry.window.value,
                    "observed": entry.observed,
                    "close_price": None if entry.close_price is None else str(entry.close_price),
                }
                for entry in result.subsequent_windows
            ),
            key=lambda item: item["window"],
        ),
        "data_sources": sorted(result.data_sources),
        "quality_state": result.quality.state,
    }


def case_conclusion_identity(result: "ValidationCaseConclusion") -> dict[str, Any]:
    return {
        "result_type": "VALIDATION_CASE_CONCLUSION",
        "symbol": result.symbol,
        "conclusion": result.conclusion,
        "supporting_findings": sorted(result.supporting_findings),
        "quality_state": result.quality.state,
    }


def validation_case_identity(result: "ValidationCase") -> dict[str, Any]:
    return {
        "result_type": "VALIDATION_CASE",
        "case_id": result.case_id,
        "symbol": result.symbol,
        "case_status": result.case_status,
        "artifact_ids": sorted(item.artifact_id for item in result.artifacts),
        "detection_time_evidence_id": (
            None if result.detection_time_evidence is None else result.detection_time_evidence.deterministic_id
        ),
        "original_snapshot_id": (
            None if result.original_snapshot is None else result.original_snapshot.deterministic_id
        ),
        "replay_ids": sorted(item.deterministic_id for item in result.replays),
        "field_comparison_ids": sorted(item.deterministic_id for item in result.field_comparisons),
        "rule_validation_ids": sorted(item.deterministic_id for item in result.rule_validations),
        "outcome_observation_id": (
            None if result.outcome_observation is None else result.outcome_observation.deterministic_id
        ),
        "conclusion_id": None if result.conclusion is None else result.conclusion.deterministic_id,
        "quality_state": result.quality.state,
    }


def public_case_identity(result: "PublicValidationCase") -> dict[str, Any]:
    return {
        "result_type": "PUBLIC_VALIDATION_CASE",
        "case_id": result.case_id,
        "symbol": result.symbol,
        "case_status": result.case_status,
        "schema_version": result.schema_version,
        "detection_time_state": result.detection_time_state,
        "detection_window_start": result.detection_window_start,
        "detection_window_end": result.detection_window_end,
        "conclusion": result.conclusion,
        "replay_labels": sorted(result.replay_labels),
    }


__all__ = [
    "METRIC_NAMESPACE",
    "case_conclusion_identity",
    "detection_time_identity",
    "deterministic_validation_id",
    "field_comparison_identity",
    "original_snapshot_identity",
    "outcome_observation_identity",
    "public_case_identity",
    "replay_identity",
    "rule_validation_identity",
    "validation_case_identity",
]
