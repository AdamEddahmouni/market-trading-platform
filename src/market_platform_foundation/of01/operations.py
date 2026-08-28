"""Structured OF-01 operator capabilities and result envelopes."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping

from .authorization import AuthorizationVerifier
from .backup import BackupService
from .errors import OF01Error, OF01ErrorCode
from .health import HealthService
from .ids import new_uuid
from .integrity import IntegrityChecker, IntegrityMode
from .sqlite_store import SQLiteAuthorityStore

JsonValue = str | int | float | bool | None | list[Any] | dict[str, Any]

CAPABILITY_IDS: frozenset[str] = frozenset(
    {
        "OF01.OP.STATUS",
        "OF01.OP.LEDGER_METADATA",
        "OF01.OP.COMMAND_RESOLVE",
        "OF01.OP.WRITE_DISABLE",
        "OF01.OP.INTEGRITY_QUICK",
        "OF01.OP.INTEGRITY_FULL",
        "OF01.OP.INTEGRITY_FORENSIC",
        "OF01.OP.BACKUP_CREATE",
        "OF01.OP.BACKUP_VERIFY",
        "OF01.OP.BACKUP_ATTEST_RESTORE_TEST",
        "OF01.OP.RESTORE_VALIDATE",
        "OF01.OP.RESTORE_ACTIVATE",
        "OF01.OP.MAINTENANCE_ENTER",
        "OF01.OP.MAINTENANCE_EXIT",
        "OF01.OP.CAS_VERIFY",
        "OF01.OP.CAS_ORPHAN_SCAN",
        "OF01.OP.CAS_GC_DRY_RUN",
        "OF01.OP.CAS_GC_EXECUTE",
        "OF01.OP.PROJECTION_STATUS",
        "OF01.OP.PROJECTION_START",
        "OF01.OP.PROJECTION_PAUSE",
        "OF01.OP.PROJECTION_RESUME",
        "OF01.OP.PROJECTION_REBUILD",
        "OF01.OP.PROJECTION_UPGRADE",
        "OF01.OP.MIGRATION_STATUS",
        "OF01.OP.MIGRATION_APPLY",
        "OF01.OP.AUTHORITY_CLONE_VALIDATE",
        "OF01.OP.AUTHORITY_REIDENTIFY",
        "OF01.OP.SHUTDOWN",
    }
)


@dataclass(frozen=True, slots=True)
class OperationResult:
    operation_id: str
    capability_id: str
    ledger_authority_id: str
    outcome_code: str
    started_at_ns: int
    completed_at_ns: int
    verification: Mapping[str, JsonValue]
    evidence_ref: str | None


class OperationsService:
    def __init__(
        self,
        *,
        store: SQLiteAuthorityStore,
        health: HealthService | None = None,
        verifier: AuthorizationVerifier | None = None,
    ) -> None:
        self._store = store
        self._health = health or HealthService(store)
        self._verifier = verifier

    def execute(
        self,
        capability_id: str,
        *,
        input_identities: Mapping[str, JsonValue] | None = None,
        authorization_ref: str | None = None,
    ) -> OperationResult:
        if capability_id not in CAPABILITY_IDS:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "unknown capability",
                {"capability_id": capability_id},
            )
        started = time.time_ns()
        verification: dict[str, JsonValue] = {}
        outcome = "OK"
        try:
            if capability_id == "OF01.OP.STATUS":
                status = self._health.get_status()
                verification["status"] = {
                    "mode": status.mode.value,
                    "liveness": status.liveness,
                    "ready_for_authoritative_writes": status.ready_for_authoritative_writes,
                    "ledger_authority_id": status.ledger_authority_id,
                    "database_schema_version": status.database_schema_version,
                    "readiness_reason_codes": list(status.readiness_reason_codes),
                }
            elif capability_id == "OF01.OP.LEDGER_METADATA":
                row = self._store.connection.execute(
                    """
                    SELECT ledger_authority_id, database_schema_version, hash_profile,
                           command_profile, record_profile, commit_profile
                    FROM ledger_metadata WHERE singleton = 1
                    """
                ).fetchone()
                verification["metadata"] = dict(row) if row else {}
            elif capability_id == "OF01.OP.INTEGRITY_QUICK":
                report = IntegrityChecker(self._store).check(IntegrityMode.QUICK)
                verification["integrity"] = {
                    "has_fatal": report.has_fatal,
                    "finding_count": len(report.findings),
                    "high_water_sequence": report.high_water_sequence,
                }
            elif capability_id == "OF01.OP.SHUTDOWN":
                status = self._health.shutdown()
                verification["status"] = {"mode": status.mode.value}
            else:
                verification["note"] = "capability stub"
        except OF01Error as exc:
            outcome = exc.code.value
            verification["error"] = exc.message
        completed = time.time_ns()
        return OperationResult(
            operation_id=new_uuid(),
            capability_id=capability_id,
            ledger_authority_id=self._store.ledger_authority_id,
            outcome_code=outcome,
            started_at_ns=started,
            completed_at_ns=completed,
            verification=verification,
            evidence_ref=None,
        )
