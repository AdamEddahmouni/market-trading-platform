"""InferenceJobV1 — BUILD 10 immutable scheduler work specification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ComponentLineage,
    ContractKind,
    ContractReference,
    component_lineage_from_dict,
    component_lineage_to_dict,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    reject_unknown_keys,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)
from .routing_decision import ExpertDomain, RoutingPriority


def _normalized_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value).strip()}))


@dataclass(frozen=True, slots=True)
class InferenceJobV1:
    """Immutable inference work specification derived from a routing decision."""

    job_id: str
    schema_version: str
    routing_decision_ref: ContractReference
    detection_ref: ContractReference
    source_snapshot_ref: ContractReference | None
    expert_domain: ExpertDomain
    priority: RoutingPriority
    decision_time_ns: int
    submitted_at_ns: int
    deadline_time_ns: int
    expires_at_ns: int
    required_capabilities: tuple[str, ...]
    execution_profile_id: str
    batch_key: str
    residency_key: str
    adapter_key: str | None
    scheduler_policy_identity: str
    scheduler_lineage: ComponentLineage
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.job_id, field_name="job_id")
        validate_schema_version(self.schema_version)
        if self.routing_decision_ref.kind != ContractKind.ROUTING_DECISION.value:
            raise ValueError("JOB_ROUTING_REF_KIND_INVALID")
        if self.detection_ref.kind != ContractKind.DETECTION.value:
            raise ValueError("JOB_DETECTION_REF_KIND_INVALID")
        if self.source_snapshot_ref is not None and self.source_snapshot_ref.kind != ContractKind.SNAPSHOT.value:
            raise ValueError("JOB_SNAPSHOT_REF_KIND_INVALID")
        if not isinstance(self.expert_domain, ExpertDomain):
            object.__setattr__(self, "expert_domain", ExpertDomain(str(self.expert_domain)))
        if not isinstance(self.priority, RoutingPriority):
            object.__setattr__(self, "priority", RoutingPriority(str(self.priority)))
        validate_timestamp_ns(self.decision_time_ns, field_name="decision_time_ns")
        validate_timestamp_ns(self.submitted_at_ns, field_name="submitted_at_ns")
        validate_timestamp_ns(self.deadline_time_ns, field_name="deadline_time_ns")
        validate_timestamp_ns(self.expires_at_ns, field_name="expires_at_ns")
        if self.deadline_time_ns <= self.decision_time_ns:
            raise ValueError("JOB_DEADLINE_NOT_FUTURE")
        if self.deadline_time_ns > self.expires_at_ns:
            raise ValueError("JOB_DEADLINE_AFTER_EXPIRATION")
        if not self.execution_profile_id:
            raise ValueError("JOB_EXECUTION_PROFILE_REQUIRED")
        if not self.batch_key:
            raise ValueError("JOB_BATCH_KEY_REQUIRED")
        if not self.residency_key:
            raise ValueError("JOB_RESIDENCY_KEY_REQUIRED")
        if not self.scheduler_policy_identity:
            raise ValueError("JOB_SCHEDULER_POLICY_IDENTITY_REQUIRED")
        if not self.scheduler_lineage.component_id or not self.scheduler_lineage.component_version:
            raise ValueError("JOB_SCHEDULER_LINEAGE_IDENTITY_REQUIRED")
        object.__setattr__(self, "required_capabilities", _normalized_strings(self.required_capabilities))
        if not isinstance(self.metadata, dict):
            raise ValueError("JOB_METADATA_INVALID")


_INFERENCE_JOB_ALLOWED = dataclass_field_names(InferenceJobV1)


def inference_job_v1_to_dict(record: InferenceJobV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "job_id": record.job_id,
        "schema_version": record.schema_version,
        "routing_decision_ref": contract_reference_to_dict(record.routing_decision_ref),
        "detection_ref": contract_reference_to_dict(record.detection_ref),
        "expert_domain": record.expert_domain.value,
        "priority": record.priority.value,
        "decision_time_ns": record.decision_time_ns,
        "submitted_at_ns": record.submitted_at_ns,
        "deadline_time_ns": record.deadline_time_ns,
        "expires_at_ns": record.expires_at_ns,
        "required_capabilities": list(record.required_capabilities),
        "execution_profile_id": record.execution_profile_id,
        "batch_key": record.batch_key,
        "residency_key": record.residency_key,
        "scheduler_policy_identity": record.scheduler_policy_identity,
        "scheduler_lineage": component_lineage_to_dict(record.scheduler_lineage),
    }
    if record.source_snapshot_ref is not None:
        body["source_snapshot_ref"] = contract_reference_to_dict(record.source_snapshot_ref)
    if record.adapter_key is not None:
        body["adapter_key"] = record.adapter_key
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def inference_job_v1_from_dict(payload: dict[str, Any]) -> InferenceJobV1:
    reject_unknown_keys(payload, _INFERENCE_JOB_ALLOWED)
    for field_name in ("required_capabilities",):
        value = payload.get(field_name, ())
        if value is not None and not isinstance(value, (list, tuple)):
            raise ValueError("JOB_STRING_LIST_INVALID")
    lineage = component_lineage_from_dict(payload.get("scheduler_lineage"))
    if lineage is None:
        raise ValueError("JOB_SCHEDULER_LINEAGE_REQUIRED")
    snapshot_ref = payload.get("source_snapshot_ref")
    return InferenceJobV1(
        job_id=str(payload["job_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        routing_decision_ref=contract_reference_from_dict(payload["routing_decision_ref"]),
        detection_ref=contract_reference_from_dict(payload["detection_ref"]),
        source_snapshot_ref=contract_reference_from_dict(snapshot_ref) if snapshot_ref else None,
        expert_domain=ExpertDomain(str(payload["expert_domain"])),
        priority=RoutingPriority(str(payload["priority"])),
        decision_time_ns=int(payload["decision_time_ns"]),
        submitted_at_ns=int(payload["submitted_at_ns"]),
        deadline_time_ns=int(payload["deadline_time_ns"]),
        expires_at_ns=int(payload["expires_at_ns"]),
        required_capabilities=tuple(payload.get("required_capabilities") or ()),
        execution_profile_id=str(payload["execution_profile_id"]),
        batch_key=str(payload["batch_key"]),
        residency_key=str(payload["residency_key"]),
        adapter_key=payload.get("adapter_key"),
        scheduler_policy_identity=str(payload["scheduler_policy_identity"]),
        scheduler_lineage=lineage,
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "InferenceJobV1",
    "inference_job_v1_from_dict",
    "inference_job_v1_to_dict",
]
