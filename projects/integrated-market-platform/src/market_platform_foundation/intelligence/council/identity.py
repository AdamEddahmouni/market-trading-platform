"""Deterministic council identities for BUILD 12."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from .models import CouncilExecutionPhase, ParticipantOutcome
from .policy import CouncilPolicy


COUNCIL_IDENTITY_VERSION = "expert-council-sha256-v1"
BLACKBOARD_IDENTITY_VERSION = "evidence-blackboard-sha256-v1"
RELATION_REPORT_IDENTITY_VERSION = "evidence-relation-sha256-v1"
DELIBERATION_REQUEST_IDENTITY_VERSION = "council-deliberation-request-sha256-v1"
SOURCE_SIGNATURE_IDENTITY_VERSION = "source-signature-sha256-v1"


def _participant_payload(participants: tuple[Any, ...]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for participant in participants:
        rows.append(
            {
                "expert_domain": participant.expert_domain.value,
                "job_id": participant.job_id,
            }
        )
    return sorted(rows, key=lambda row: (row["expert_domain"], row["job_id"]))


def derive_council_id(
    *,
    source_snapshot_id: str,
    participants: tuple[Any, ...],
    policy: CouncilPolicy,
    decision_time_ns: int,
    blind_pass_version: str = "1",
) -> str:
    payload = {
        "identity_version": COUNCIL_IDENTITY_VERSION,
        "schema_version": "1",
        "source_snapshot_id": source_snapshot_id,
        "participants": _participant_payload(participants),
        "policy_identity": policy.policy_identity,
        "decision_time_ns": decision_time_ns,
        "blind_pass_version": blind_pass_version,
    }
    return f"COUNCIL-{sha256_bytes(canonical_bytes(payload))}"


def derive_source_signature_id(*, terminal_source_ids: tuple[str, ...]) -> str:
    payload = {
        "identity_version": SOURCE_SIGNATURE_IDENTITY_VERSION,
        "schema_version": "1",
        "terminal_source_ids": sorted(set(terminal_source_ids)),
    }
    return f"SRCSIG-{sha256_bytes(canonical_bytes(payload))}"


def derive_blackboard_id(
    *,
    council_id: str,
    evidence_ids: tuple[str, ...],
    participant_outcomes: tuple[ParticipantOutcome, ...],
    phase: str,
    revision: int,
) -> str:
    outcome_payload = [
        {
            "expert_domain": outcome.expert_domain.value,
            "job_id": outcome.job_id,
            "status": outcome.status.value,
            "evidence_refs": list(outcome.evidence_refs),
            "execution_phase": outcome.execution_phase.value,
        }
        for outcome in sorted(
            participant_outcomes,
            key=lambda row: (row.expert_domain.value, row.job_id),
        )
    ]
    payload = {
        "identity_version": BLACKBOARD_IDENTITY_VERSION,
        "schema_version": "1",
        "council_id": council_id,
        "evidence_ids": sorted(set(evidence_ids)),
        "participant_outcomes": outcome_payload,
        "phase": phase,
        "revision": revision,
    }
    return f"BB-{sha256_bytes(canonical_bytes(payload))}"


def derive_relation_report_id(
    *,
    blackboard_id: str,
    policy_identity: str,
    comparison_adapter_version: str,
) -> str:
    payload = {
        "identity_version": RELATION_REPORT_IDENTITY_VERSION,
        "schema_version": "1",
        "blackboard_id": blackboard_id,
        "policy_identity": policy_identity,
        "comparison_adapter_version": comparison_adapter_version,
    }
    return f"REL-{sha256_bytes(canonical_bytes(payload))}"


def derive_deliberation_request_id(
    *,
    council_id: str,
    blackboard_id: str,
    conflicting_evidence_refs: tuple[str, ...],
    invited_participant_domains: tuple[str, ...],
    round_number: int,
    policy_identity: str,
) -> str:
    payload = {
        "identity_version": DELIBERATION_REQUEST_IDENTITY_VERSION,
        "schema_version": "1",
        "council_id": council_id,
        "blackboard_id": blackboard_id,
        "conflicting_evidence_refs": sorted(set(conflicting_evidence_refs)),
        "invited_participant_domains": sorted(invited_participant_domains),
        "round_number": round_number,
        "policy_identity": policy_identity,
    }
    return f"DELIB-{sha256_bytes(canonical_bytes(payload))}"


__all__ = [
    "BLACKBOARD_IDENTITY_VERSION",
    "COUNCIL_IDENTITY_VERSION",
    "DELIBERATION_REQUEST_IDENTITY_VERSION",
    "RELATION_REPORT_IDENTITY_VERSION",
    "SOURCE_SIGNATURE_IDENTITY_VERSION",
    "derive_blackboard_id",
    "derive_council_id",
    "derive_deliberation_request_id",
    "derive_relation_report_id",
    "derive_source_signature_id",
]
