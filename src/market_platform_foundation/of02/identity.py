"""Stable native and retrospective identity allocation."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from market_platform_foundation.of01.ids import new_uuid, validate_imported_uuid5
from market_platform_foundation.of01.records import ProvenanceQualifier

from .errors import OF02Error, OF02ErrorCode

# UUIDv4 namespace reserved for OF-02 import derivation.
OF02_IMPORT_NAMESPACE = "8f3c1a2e-4b7d-4e91-8c2a-0d5f6a7b8c9d"


def imported_uuid(name: str, *, qualifier: str) -> str:
    value = str(uuid.uuid5(uuid.UUID(OF02_IMPORT_NAMESPACE), name))
    return validate_imported_uuid5(
        value,
        field="imported_id",
        namespace_id=OF02_IMPORT_NAMESPACE,
        provenance_qualifier=qualifier,
    )


@dataclass(frozen=True, slots=True)
class IdentityPlan:
    run_id: str
    register_run_command_id: str
    activate_command_id: str
    register_transition_id: str
    activate_transition_id: str
    close_command_id: str
    close_transition_id: str
    outcome_id: str
    outcome_command_id: str
    disposition_id: str
    attempt_ids: tuple[str, ...]
    attempt_register_command_ids: tuple[str, ...]
    attempt_running_command_ids: tuple[str, ...]
    attempt_terminal_command_ids: tuple[str, ...]
    attempt_pending_transition_ids: tuple[str, ...]
    attempt_running_transition_ids: tuple[str, ...]
    attempt_terminal_transition_ids: tuple[str, ...]
    artifact_id: str | None
    artifact_command_id: str | None
    attach_artifact_command_id: str | None
    attach_artifact_relationship_id: str | None
    domain_ref_id: str
    domain_ref_command_id: str
    environment_ref_id: str
    environment_ref_command_id: str
    source_attribution_id: str
    source_attribution_command_id: str
    registered_at_ns: int

    def require_preserved(self, previous: "IdentityPlan") -> None:
        if self != previous:
            raise OF02Error(
                OF02ErrorCode.RETRY_IDENTITY_REGENERATION,
                "retry must preserve command and domain identities",
                {},
            )


def allocate_native(*, attempt_count: int, capture_artifact: bool) -> IdentityPlan:
    if attempt_count < 1:
        raise OF02Error(OF02ErrorCode.ATTRIBUTION_FAILED, "attempt_count must be >= 1", {})
    attempt_ids = tuple(new_uuid() for _ in range(attempt_count))
    return IdentityPlan(
        run_id=new_uuid(),
        register_run_command_id=new_uuid(),
        activate_command_id=new_uuid(),
        register_transition_id=new_uuid(),
        activate_transition_id=new_uuid(),
        close_command_id=new_uuid(),
        close_transition_id=new_uuid(),
        outcome_id=new_uuid(),
        outcome_command_id=new_uuid(),
        disposition_id=new_uuid(),
        attempt_ids=attempt_ids,
        attempt_register_command_ids=tuple(new_uuid() for _ in attempt_ids),
        attempt_running_command_ids=tuple(new_uuid() for _ in attempt_ids),
        attempt_terminal_command_ids=tuple(new_uuid() for _ in attempt_ids),
        attempt_pending_transition_ids=tuple(new_uuid() for _ in attempt_ids),
        attempt_running_transition_ids=tuple(new_uuid() for _ in attempt_ids),
        attempt_terminal_transition_ids=tuple(new_uuid() for _ in attempt_ids),
        artifact_id=new_uuid() if capture_artifact else None,
        artifact_command_id=new_uuid() if capture_artifact else None,
        attach_artifact_command_id=new_uuid() if capture_artifact else None,
        attach_artifact_relationship_id=new_uuid() if capture_artifact else None,
        domain_ref_id=new_uuid(),
        domain_ref_command_id=new_uuid(),
        environment_ref_id=new_uuid(),
        environment_ref_command_id=new_uuid(),
        source_attribution_id=new_uuid(),
        source_attribution_command_id=new_uuid(),
        registered_at_ns=time.time_ns(),
    )


def derive_retrospective(
    *,
    source_type: str,
    source_identity: str,
    content_hash: str,
    attempt_count: int,
    capture_artifact: bool,
    qualifier: str,
) -> IdentityPlan:
    if qualifier not in {
        ProvenanceQualifier.RETROSPECTIVE_INDEX.value,
        ProvenanceQualifier.LEGACY_PARTIAL.value,
    }:
        raise OF02Error(
            OF02ErrorCode.FABRICATION_PROHIBITED,
            "retrospective identities require import provenance qualifier",
            {"qualifier": qualifier},
        )
    prefix = f"{source_type}|{source_identity}|{content_hash}"

    def _id(role: str) -> str:
        return imported_uuid(f"{prefix}|{role}", qualifier=qualifier)

    attempt_ids = tuple(_id(f"attempt|{i+1}") for i in range(attempt_count))
    return IdentityPlan(
        run_id=_id("run"),
        register_run_command_id=_id("cmd|RegisterRun"),
        activate_command_id=_id("cmd|Activate"),
        register_transition_id=_id("tr|register"),
        activate_transition_id=_id("tr|activate"),
        close_command_id=_id("cmd|CloseRun"),
        close_transition_id=_id("tr|close"),
        outcome_id=_id("outcome"),
        outcome_command_id=_id("cmd|RecordOutcome"),
        disposition_id=_id("disposition"),
        attempt_ids=attempt_ids,
        attempt_register_command_ids=tuple(_id(f"cmd|RegisterAttempt|{i+1}") for i in range(attempt_count)),
        attempt_running_command_ids=tuple(_id(f"cmd|AttemptRunning|{i+1}") for i in range(attempt_count)),
        attempt_terminal_command_ids=tuple(_id(f"cmd|AttemptTerminal|{i+1}") for i in range(attempt_count)),
        attempt_pending_transition_ids=tuple(_id(f"tr|pending|{i+1}") for i in range(attempt_count)),
        attempt_running_transition_ids=tuple(_id(f"tr|running|{i+1}") for i in range(attempt_count)),
        attempt_terminal_transition_ids=tuple(_id(f"tr|terminal|{i+1}") for i in range(attempt_count)),
        artifact_id=_id("artifact") if capture_artifact else None,
        artifact_command_id=_id("cmd|RegisterArtifact") if capture_artifact else None,
        attach_artifact_command_id=_id("cmd|AttachArtifact") if capture_artifact else None,
        attach_artifact_relationship_id=_id("rel|artifact") if capture_artifact else None,
        domain_ref_id=_id("prov|domain"),
        domain_ref_command_id=_id("cmd|AttachProvenance"),
        environment_ref_id=_id("prov|environment"),
        environment_ref_command_id=_id("cmd|AttachEnv"),
        source_attribution_id=_id("source"),
        source_attribution_command_id=_id("cmd|AttachSource"),
        registered_at_ns=0,
    )
