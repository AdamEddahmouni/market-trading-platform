"""OF-01 runtime health, startup gates, and shutdown."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .cas import LocalCAS
from .errors import OF01Error, OF01ErrorCode
from .integrity import IntegrityChecker, IntegrityMode
from .migrations import current_database_schema_version, verify_schema_objects
from .sqlite_schema import SCHEMA_VERSION
from .sqlite_store import SQLiteAuthorityStore


class RuntimeMode(StrEnum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    MAINTENANCE = "MAINTENANCE"
    WRITE_DISABLED = "WRITE_DISABLED"
    INTEGRITY_BLOCKED = "INTEGRITY_BLOCKED"
    SHUTTING_DOWN = "SHUTTING_DOWN"


@dataclass(frozen=True, slots=True)
class StatusV1:
    observed_at_ns: int
    runtime_revision: int
    process_instance_id: str
    mode: RuntimeMode
    liveness: bool
    ready_for_authoritative_writes: bool
    readiness_reason_codes: tuple[str, ...]
    ledger_authority_id: str
    database_schema_version: int

    @property
    def integrity_ok(self) -> bool:
        return "INTEGRITY_FATAL" not in self.readiness_reason_codes


class HealthService:
    def __init__(
        self,
        store: SQLiteAuthorityStore,
        *,
        cas: LocalCAS | None = None,
    ) -> None:
        self._store = store
        self._cas = cas
        self._process_instance_id = str(uuid.uuid4())

    def _read_runtime(self) -> tuple[RuntimeMode, int]:
        row = self._store.connection.execute(
            "SELECT mode, revision FROM runtime_control WHERE singleton = 1"
        ).fetchone()
        if row is None:
            return RuntimeMode.STOPPED, 0
        return RuntimeMode(str(row["mode"])), int(row["revision"])

    def _write_runtime(self, mode: RuntimeMode, *, reason_code: str) -> int:
        current_mode, revision = self._read_runtime()
        del current_mode
        new_revision = revision + 1
        now = time.time_ns()
        self._store.connection.execute(
            """
            UPDATE runtime_control
            SET mode = ?, revision = ?, changed_at_ns = ?, reason_code = ?
            WHERE singleton = 1
            """,
            (mode.value, new_revision, now, reason_code),
        )
        return new_revision

    def startup_checks(
        self,
        *,
        db_path: Path,
        cas_root: Path | None = None,
    ) -> StatusV1:
        reasons: list[str] = []
        self._write_runtime(RuntimeMode.STARTING, reason_code="STARTUP")
        if not db_path.exists():
            reasons.append("DB_MISSING")
        version = current_database_schema_version(self._store.connection)
        if version != SCHEMA_VERSION:
            reasons.append("SCHEMA_UNSUPPORTED")
        else:
            try:
                verify_schema_objects(self._store.connection)
            except OF01Error:
                reasons.append("SCHEMA_UNSUPPORTED")
        if not self._store.integrity_ok():
            reasons.append("INTEGRITY_FATAL")
        if not self._store.foreign_keys_ok():
            reasons.append("FOREIGN_KEY_MISMATCH")
        checker = IntegrityChecker(self._store, cas=self._cas)
        report = checker.check(IntegrityMode.QUICK)
        if report.has_fatal:
            reasons.append("INTEGRITY_FATAL")
        if cas_root is not None:
            if not cas_root.exists():
                reasons.append("CAS_ROOT_MISSING")
            elif self._cas is not None:
                try:
                    self._cas.probe_write()
                except OF01Error:
                    reasons.append("CAS_UNWRITABLE")
        mode = RuntimeMode.READY if not reasons else RuntimeMode.DEGRADED
        revision = self._write_runtime(mode, reason_code="STARTUP_COMPLETE")
        ready = mode == RuntimeMode.READY and mode not in {
            RuntimeMode.MAINTENANCE,
            RuntimeMode.WRITE_DISABLED,
            RuntimeMode.INTEGRITY_BLOCKED,
        }
        return StatusV1(
            observed_at_ns=time.time_ns(),
            runtime_revision=revision,
            process_instance_id=self._process_instance_id,
            mode=mode,
            liveness=True,
            ready_for_authoritative_writes=ready,
            readiness_reason_codes=tuple(sorted(set(reasons))),
            ledger_authority_id=self._store.ledger_authority_id,
            database_schema_version=version or SCHEMA_VERSION,
        )

    def shutdown(self) -> StatusV1:
        revision = self._write_runtime(RuntimeMode.SHUTTING_DOWN, reason_code="SHUTDOWN")
        revision = self._write_runtime(RuntimeMode.STOPPED, reason_code="SHUTDOWN_COMPLETE")
        return StatusV1(
            observed_at_ns=time.time_ns(),
            runtime_revision=revision,
            process_instance_id=self._process_instance_id,
            mode=RuntimeMode.STOPPED,
            liveness=True,
            ready_for_authoritative_writes=False,
            readiness_reason_codes=("STOPPED",),
            ledger_authority_id=self._store.ledger_authority_id,
            database_schema_version=current_database_schema_version(self._store.connection) or SCHEMA_VERSION,
        )

    def get_status(self) -> StatusV1:
        mode, revision = self._read_runtime()
        version = current_database_schema_version(self._store.connection) or SCHEMA_VERSION
        ready = mode in {RuntimeMode.READY, RuntimeMode.DEGRADED}
        reasons: list[str] = []
        if mode == RuntimeMode.STOPPED:
            reasons.append("STOPPED")
        if mode == RuntimeMode.MAINTENANCE:
            reasons.append("MAINTENANCE")
        if mode == RuntimeMode.INTEGRITY_BLOCKED:
            reasons.append("INTEGRITY_FATAL")
        return StatusV1(
            observed_at_ns=time.time_ns(),
            runtime_revision=revision,
            process_instance_id=self._process_instance_id,
            mode=mode,
            liveness=True,
            ready_for_authoritative_writes=ready,
            readiness_reason_codes=tuple(sorted(reasons)),
            ledger_authority_id=self._store.ledger_authority_id,
            database_schema_version=version,
        )
