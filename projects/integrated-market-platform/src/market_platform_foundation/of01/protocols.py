"""Backend-independent OF-01 protocol definitions."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import BinaryIO, Protocol

from .cas import CASObjectInfo, PreparedObject, PublishedObject
from .commands import CommandEnvelope, CommitReceipt
from .records import AuthoritativeRecord


@dataclass(frozen=True, slots=True)
class CommitBundle:
    commit_sequence: int
    commit_id: str
    commit_hash: str
    command_id: str
    command_hash: str
    command_type: str
    recorded_at_ns: int
    records: tuple[AuthoritativeRecord, ...]


class DispositionScope(StrEnum):
    RUN = "RUN"
    OUTCOME = "OUTCOME"


@dataclass(frozen=True, slots=True)
class DispositionSelectionPolicyV1:
    scope: str
    allowed_authority_types: frozenset[str]
    allowed_action_categories: frozenset[str]


@dataclass(frozen=True, slots=True)
class RunView:
    run_id: str
    as_of_commit_sequence: int
    current_state: str | None
    disposition_policy: DispositionSelectionPolicyV1
    current_disposition_id: str | None


@dataclass(frozen=True, slots=True)
class AttemptView:
    attempt_id: str
    run_id: str
    current_phase: str | None
    as_of_commit_sequence: int


@dataclass(frozen=True, slots=True)
class LedgerCommit:
    commit_sequence: int
    commit_id: str
    commit_hash: str
    command_id: str
    command_hash: str
    command_type: str
    recorded_at_ns: int
    record_count: int


class PreparedArtifactToken(Protocol):
    artifact_id: str


class AuthoritativeLedgerWriter(Protocol):
    def submit(
        self,
        envelope: CommandEnvelope,
        prepared_artifacts: Mapping[str, PreparedArtifactToken] = {},
    ) -> CommitReceipt: ...

    def resolve_command(self, command_id: str) -> CommitReceipt | None: ...


class LedgerReader(Protocol):
    def get_record(self, record_type: str, record_id: str) -> AuthoritativeRecord | None: ...

    def get_run(
        self, run_id: str, disposition_policy: DispositionSelectionPolicyV1
    ) -> RunView | None: ...

    def get_attempt(self, attempt_id: str) -> AttemptView | None: ...

    def get_commit(self, commit_sequence: int) -> LedgerCommit | None: ...


class CommitStreamReader(Protocol):
    def stream_commits(
        self, after_sequence: int, through_sequence: int | None = None
    ) -> Iterator[CommitBundle]: ...


class CASStore(Protocol):
    def prepare(self, source: BinaryIO, expected_hash: str | None = None) -> PreparedObject: ...

    def publish(self, prepared: PreparedObject) -> PublishedObject: ...

    def open_verified(self, content_hash: str) -> BinaryIO: ...

    def inventory(self) -> Iterator[CASObjectInfo]: ...
