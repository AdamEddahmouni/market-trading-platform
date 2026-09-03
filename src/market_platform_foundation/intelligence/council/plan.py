"""Frozen council plan for BUILD 12."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts import ContractReference
from .errors import CouncilConfigurationError
from .identity import derive_council_id
from .models import CouncilParticipant
from .policy import CouncilPolicy


def canonicalize_participants(
    participants: tuple[CouncilParticipant, ...],
) -> tuple[CouncilParticipant, ...]:
    if not participants:
        raise CouncilConfigurationError("COUNCIL_PARTICIPANTS_REQUIRED")
    unique: dict[tuple[str, str], CouncilParticipant] = {}
    for participant in participants:
        key = (participant.expert_domain.value, participant.job_id)
        if key in unique:
            raise CouncilConfigurationError("COUNCIL_DUPLICATE_PARTICIPANT")
        unique[key] = participant
    return tuple(sorted(unique.values(), key=lambda row: (row.expert_domain.value, row.job_id)))


@dataclass(frozen=True, slots=True)
class CouncilPlan:
    council_id: str
    source_snapshot_id: str
    participants: tuple[CouncilParticipant, ...]
    policy: CouncilPolicy
    decision_time_ns: int
    blind_pass_version: str = "1"
    source_snapshot_ref: ContractReference | None = None

    @classmethod
    def create(
        cls,
        *,
        source_snapshot_id: str,
        participants: tuple[CouncilParticipant, ...],
        policy: CouncilPolicy,
        decision_time_ns: int,
        blind_pass_version: str = "1",
        source_snapshot_ref: ContractReference | None = None,
    ) -> CouncilPlan:
        frozen_participants = canonicalize_participants(participants)
        council_id = derive_council_id(
            source_snapshot_id=source_snapshot_id,
            participants=frozen_participants,
            policy=policy,
            decision_time_ns=decision_time_ns,
            blind_pass_version=blind_pass_version,
        )
        return cls(
            council_id=council_id,
            source_snapshot_id=source_snapshot_id,
            participants=frozen_participants,
            policy=policy,
            decision_time_ns=decision_time_ns,
            blind_pass_version=blind_pass_version,
            source_snapshot_ref=source_snapshot_ref,
        )


__all__ = ["CouncilPlan", "canonicalize_participants"]
