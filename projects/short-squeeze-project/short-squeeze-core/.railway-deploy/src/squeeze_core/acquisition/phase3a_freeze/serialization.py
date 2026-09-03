"""Canonical serialization and deterministic identity for the Batch 08 freeze.

Reuses the project's existing ``canonical_json_bytes`` (UTF-8, sorted keys, exact Decimal
strings, explicit nulls, no NaN/infinity) and ``deterministic_acquisition_id`` (UUIDv5
over canonical JSON). Nothing is reimplemented.

Identity inputs are frozen pre-outcome facts only: no wall clock, no retrieval time, no
absolute local path, no random id, no credential, no outcome, no forward artifact.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel

from squeeze_core.evaluation.models import (
    CandidateEvaluationResult,
    RuleEvaluationRequest,
)
from squeeze_core.serialization import canonical_json_bytes

from ..identifiers import deterministic_acquisition_id
from ..operation_readiness.models import (
    OPERATION_READINESS_POLICY_VERSION,
    SEMANTIC_RESOLUTION_POLICY_VERSION,
)
from .models import (
    FREEZE_POLICY_VERSION,
    GLOBAL_PREFLIGHT_VERDICT,
    EvidenceAssociation,
    FrozenArtifactRef,
    ReceiptModelingPolicy,
    RuleOutcomeRecord,
    TemporalSelection,
)


def serialize(value: BaseModel) -> bytes:
    """Canonical bytes for any frozen model or evaluation object."""
    return canonical_json_bytes(value)


def artifact_ref(kind: str, payload: bytes) -> FrozenArtifactRef:
    return FrozenArtifactRef(
        artifact_kind=kind,
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_length=len(payload),
    )


def request_identity(
    *,
    association: EvidenceAssociation,
    temporal: TemporalSelection,
    receipt_policy: ReceiptModelingPolicy,
    phase3a_policy_version: str,
    phase3a_evaluation_version: str,
    enabled_rule_ids: tuple[str, ...],
    admissible_evidence_ids: tuple[str, ...],
    metric_ids: tuple[str, ...],
    readiness_ids: tuple[str, ...],
) -> dict[str, object]:
    """Frozen pre-outcome identity inputs for a Phase 3A request."""
    return {
        "result_type": "BATCH08_PHASE3A_REQUEST",
        "freeze_policy_version": FREEZE_POLICY_VERSION,
        "phase3a_policy_version": phase3a_policy_version,
        "phase3a_evaluation_version": phase3a_evaluation_version,
        "operation_readiness_policy_version": OPERATION_READINESS_POLICY_VERSION,
        "semantic_resolution_policy_version": SEMANTIC_RESOLUTION_POLICY_VERSION,
        "receipt_modeling_policy": receipt_policy.value,
        "global_preflight_status": GLOBAL_PREFLIGHT_VERDICT,
        "case_id": association.case_id,
        "symbol": association.symbol,
        "boundary_id": association.boundary_id,
        "boundary_time": association.boundary_time,
        "detection_context_artifact_sha256": (
            association.detection_context_artifact_sha256
        ),
        "detection_context_artifact_byte_length": (
            association.detection_context_artifact_byte_length
        ),
        "batch07_readiness_record_id": association.batch07_readiness_record_id,
        "evidence_association_id": str(association.deterministic_id),
        "temporal_selection_id": str(temporal.deterministic_id),
        "enabled_rule_ids": sorted(enabled_rule_ids),
        "admissible_evidence_ids": sorted(admissible_evidence_ids),
        "metric_ids": sorted(metric_ids),
        "readiness_ids": sorted(readiness_ids),
    }


def result_identity(
    *,
    request_id: str,
    candidate_evaluation_id: str,
    rule_outcomes: tuple[RuleOutcomeRecord, ...],
) -> dict[str, object]:
    """Result identity: the frozen request plus the evaluator's exact rule outcomes."""
    return {
        "result_type": "BATCH08_PHASE3A_RESULT",
        "freeze_policy_version": FREEZE_POLICY_VERSION,
        "phase3a_request_id": request_id,
        "candidate_evaluation_id": candidate_evaluation_id,
        "rule_outcomes": [
            {
                "rule_id": item.rule_id,
                "rule_version": item.rule_version,
                "category": item.category,
                "outcome": item.outcome,
                "explanation_code": item.explanation_code,
                "rule_result_id": item.rule_result_id,
                "supporting_observation_ids": sorted(item.supporting_observation_ids),
                "supporting_metric_ids": sorted(item.supporting_metric_ids),
                "supporting_readiness_ids": sorted(item.supporting_readiness_ids),
            }
            for item in sorted(rule_outcomes, key=lambda item: item.rule_id)
        ],
    }


def freeze_id(identity: dict[str, object]) -> str:
    return deterministic_acquisition_id(identity)


def serialize_phase3a_request(request: RuleEvaluationRequest) -> bytes:
    return canonical_json_bytes(request)


def serialize_phase3a_result(evaluation: CandidateEvaluationResult) -> bytes:
    return canonical_json_bytes(evaluation)


__all__ = [
    "artifact_ref",
    "freeze_id",
    "request_identity",
    "result_identity",
    "serialize",
    "serialize_phase3a_request",
    "serialize_phase3a_result",
]
