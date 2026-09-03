"""Production release registry (BUILD 35)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .identity import derive_history_event_id
from .types import (
    RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    RELEASE_GOVERNANCE_SCHEMA_VERSION,
    ProductionReleaseApprovalV1,
    ProductionReleaseCandidateV1,
    ReleaseApprovalStatus,
    ReleaseHistoryEventType,
    ReleaseHistoryEventV1,
)


@dataclass
class ProductionReleaseRegistry:
    """Append-only release registry — current state is derived from history."""

    events: list[ReleaseHistoryEventV1] = field(default_factory=list)
    candidates: dict[str, ProductionReleaseCandidateV1] = field(default_factory=dict)
    approvals: dict[str, ProductionReleaseApprovalV1] = field(default_factory=dict)

    def append_event(self, event: ReleaseHistoryEventV1) -> None:
        self.events.append(event)

    def register_candidate(self, candidate: ProductionReleaseCandidateV1) -> ReleaseHistoryEventV1:
        self.candidates[candidate.production_release_candidate_id] = candidate
        event = ReleaseHistoryEventV1(
            event_id="",
            schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
            event_type=ReleaseHistoryEventType.CANDIDATE_ASSEMBLED.value,
            event_time_ns=0,
            release_candidate_ref=candidate.production_release_candidate_id,
            release_approval_ref=None,
            environment_kind=None,
            details={"status": candidate.candidate_status},
            implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
        )
        event = ReleaseHistoryEventV1(
            event_id=derive_history_event_id(event),
            schema_version=event.schema_version,
            event_type=event.event_type,
            event_time_ns=event.event_time_ns,
            release_candidate_ref=event.release_candidate_ref,
            release_approval_ref=event.release_approval_ref,
            environment_kind=event.environment_kind,
            details=event.details,
            implementation_version=event.implementation_version,
        )
        self.append_event(event)
        return event

    def register_approval(
        self,
        approval: ProductionReleaseApprovalV1,
        *,
        event_time_ns: int,
    ) -> ReleaseHistoryEventV1:
        self.approvals[approval.release_approval_id] = approval
        event_type = (
            ReleaseHistoryEventType.APPROVED.value
            if approval.approval_status == ReleaseApprovalStatus.APPROVED_SUPERVISED_OPERATION.value
            else ReleaseHistoryEventType.REJECTED.value
        )
        event = ReleaseHistoryEventV1(
            event_id="",
            schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
            event_type=event_type,
            event_time_ns=event_time_ns,
            release_candidate_ref=approval.candidate_ref,
            release_approval_ref=approval.release_approval_id,
            environment_kind=None,
            details={
                "status": approval.approval_status,
                "scope": list(approval.approved_environment_scope),
            },
            implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
        )
        event = ReleaseHistoryEventV1(
            event_id=derive_history_event_id(event),
            schema_version=event.schema_version,
            event_type=event.event_type,
            event_time_ns=event.event_time_ns,
            release_candidate_ref=event.release_candidate_ref,
            release_approval_ref=event.release_approval_ref,
            environment_kind=event.environment_kind,
            details=event.details,
            implementation_version=event.implementation_version,
        )
        self.append_event(event)
        return event

    def register_revocation(
        self,
        approval: ProductionReleaseApprovalV1,
        *,
        event_time_ns: int,
        reason: str,
    ) -> ReleaseHistoryEventV1:
        event = ReleaseHistoryEventV1(
            event_id="",
            schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
            event_type=ReleaseHistoryEventType.REVOKED.value,
            event_time_ns=event_time_ns,
            release_candidate_ref=approval.candidate_ref,
            release_approval_ref=approval.release_approval_id,
            environment_kind=None,
            details={"reason": reason, "status": approval.approval_status},
            implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
        )
        event = ReleaseHistoryEventV1(
            event_id=derive_history_event_id(event),
            schema_version=event.schema_version,
            event_type=event.event_type,
            event_time_ns=event.event_time_ns,
            release_candidate_ref=event.release_candidate_ref,
            release_approval_ref=event.release_approval_ref,
            environment_kind=event.environment_kind,
            details=event.details,
            implementation_version=event.implementation_version,
        )
        self.append_event(event)
        return event

    def current_approved_release(self) -> ProductionReleaseApprovalV1 | None:
        """Derive current approved release from history — revoked/superseded excluded."""
        approved: dict[str, ProductionReleaseApprovalV1] = {}
        revoked: set[str] = set()
        superseded: set[str] = set()
        for event in self.events:
            if event.event_type == ReleaseHistoryEventType.APPROVED.value and event.release_approval_ref:
                approval = self.approvals.get(event.release_approval_ref)
                if approval:
                    approved[approval.release_approval_id] = approval
            elif event.event_type == ReleaseHistoryEventType.REVOKED.value and event.release_approval_ref:
                revoked.add(event.release_approval_ref)
            elif event.event_type == ReleaseHistoryEventType.SUPERSEDED.value and event.release_approval_ref:
                superseded.add(event.release_approval_ref)
        for aid in revoked | superseded:
            approved.pop(aid, None)
        if not approved:
            return None
        return max(approved.values(), key=lambda a: a.approval_time_ns)

    def is_revoked(self, approval_id: str) -> bool:
        for event in self.events:
            if (
                event.event_type == ReleaseHistoryEventType.REVOKED.value
                and event.release_approval_ref == approval_id
            ):
                return True
        return False

    def event_count(self) -> int:
        return len(self.events)
