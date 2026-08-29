"""OF-01 writer gateway. Adapters never touch SQLite or CAS internals."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from market_platform_foundation.of01.canonical import COMMAND_PROFILE
from market_platform_foundation.of01.cas import LocalCAS
from market_platform_foundation.of01.commands import (
    CommandEnvelope,
    CommitReceipt,
    LedgerCommand,
    PreparedArtifactToken,
    compute_command_hash,
)
from market_platform_foundation.of01.errors import OF01Error, OF01ErrorCode

from .errors import OF02Error, OF02ErrorCode


class LedgerWriter(Protocol):
    def submit(
        self,
        envelope: CommandEnvelope,
        prepared_artifacts: Mapping[str, PreparedArtifactToken] | None = None,
    ) -> CommitReceipt: ...

    def resolve_command(self, command_id: str) -> CommitReceipt | None: ...


def envelope_for(command: LedgerCommand, command_id: str) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=command_id,
        command_type=type(command).__name__,
        command_schema_version=1,
        command_canonicalization_profile=COMMAND_PROFILE,
        command_hash=compute_command_hash(command),
        command=command,
    )


def submit(
    writer: LedgerWriter,
    command: LedgerCommand,
    command_id: str,
    prepared_artifacts: Mapping[str, PreparedArtifactToken] | None = None,
) -> CommitReceipt:
    existing = writer.resolve_command(command_id)
    envelope = envelope_for(command, command_id)
    if existing is not None:
        if existing.command_hash != envelope.command_hash:
            raise OF01Error(
                OF01ErrorCode.COMMAND_ID_CONFLICT,
                "command identity reused with different semantic hash",
                {"command_id": command_id},
            )
        return existing
    return writer.submit(envelope, prepared_artifacts)


def token_from_cas(cas: LocalCAS, artifact_id: str, payload: bytes) -> PreparedArtifactToken:
    from io import BytesIO

    prepared = cas.prepare(BytesIO(payload))
    return PreparedArtifactToken(
        artifact_id=artifact_id,
        temp_path=str(prepared.temp_path),
        content_hash=prepared.content_hash,
        byte_size=prepared.byte_size,
        operation_id=prepared.operation_id,
    )


def require_writer(writer: LedgerWriter | None) -> LedgerWriter:
    if writer is None:
        raise OF02Error(OF02ErrorCode.WRITER_UNAVAILABLE, "OF writer is not ready", {})
    return writer
