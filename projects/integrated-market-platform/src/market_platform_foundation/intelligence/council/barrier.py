"""Blind execution barrier for BUILD 12."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..specialists.models import SpecialistExecutionStatus
from .errors import CouncilStateError
from .models import CouncilParticipant, ParticipantOutcome


_TERMINAL_STATUSES = frozenset(
    {
        SpecialistExecutionStatus.COMPLETED,
        SpecialistExecutionStatus.ABSTAINED,
        SpecialistExecutionStatus.FAILED,
        SpecialistExecutionStatus.STALE,
    }
)


@dataclass
class BlindExecutionBarrier:
    participants: tuple[CouncilParticipant, ...]
    outcomes: dict[str, ParticipantOutcome] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._participant_by_job = {participant.job_id: participant for participant in self.participants}
        if len(self._participant_by_job) != len(self.participants):
            raise CouncilStateError("COUNCIL_DUPLICATE_JOB_ID")

    @property
    def participant_count(self) -> int:
        return len(self.participants)

    @property
    def terminal_count(self) -> int:
        return len(self.outcomes)

    def record_terminal(self, outcome: ParticipantOutcome) -> None:
        participant = self._participant_by_job.get(outcome.job_id)
        if participant is None:
            raise CouncilStateError("COUNCIL_UNKNOWN_PARTICIPANT_JOB")
        if outcome.job_id in self.outcomes:
            raise CouncilStateError("COUNCIL_PARTICIPANT_ALREADY_TERMINAL")
        if outcome.status not in _TERMINAL_STATUSES:
            raise CouncilStateError("COUNCIL_PARTICIPANT_NOT_TERMINAL")
        self.outcomes[outcome.job_id] = outcome

    def all_terminal(self) -> bool:
        return len(self.outcomes) == len(self.participants)

    def can_publish_blackboard(self) -> bool:
        return self.all_terminal()

    def participant_outcomes(self) -> tuple[ParticipantOutcome, ...]:
        return tuple(
            self.outcomes[job_id]
            for job_id in sorted(
                self.outcomes,
                key=lambda job: (
                    self._participant_by_job[job].expert_domain.value,
                    job,
                ),
            )
        )

    def pending_job_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                job_id
                for job_id in self._participant_by_job
                if job_id not in self.outcomes
            )
        )


__all__ = ["BlindExecutionBarrier"]
