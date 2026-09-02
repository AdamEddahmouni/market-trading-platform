"""OF-01 maintenance lease and revision-bound operational mode."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

from .errors import OF01Error, OF01ErrorCode
from .health import RuntimeMode
from .ids import new_uuid
from .sqlite_store import SQLiteAuthorityStore


class MaintenancePurpose(StrEnum):
    BACKUP = "BACKUP"
    GENERAL = "GENERAL"
    MIGRATION = "MIGRATION"
    RESTORE = "RESTORE"
    CAS_GC = "CAS_GC"
    INTEGRITY_FULL = "INTEGRITY_FULL"


@dataclass(frozen=True, slots=True)
class MaintenanceLease:
    lease_id: str
    ledger_authority_id: str
    purpose: MaintenancePurpose
    authorization_ref: str
    owner_ref: str
    issued_at_ns: int
    expires_at_ns: int
    runtime_revision: int


@dataclass(frozen=True, slots=True)
class MaintenanceEnterResult:
    lease: MaintenanceLease | None
    runtime_revision: int
    mode: RuntimeMode


@dataclass(frozen=True, slots=True)
class MaintenanceExitResult:
    runtime_revision: int
    mode: RuntimeMode


class MaintenanceService:
    LEASE_TTL_NS = 3_600_000_000_000

    def __init__(self, store: SQLiteAuthorityStore) -> None:
        self._store = store
        self._active_lease: MaintenanceLease | None = None

    def _read_revision(self) -> tuple[RuntimeMode, int]:
        row = self._store.connection.execute(
            "SELECT mode, revision FROM runtime_control WHERE singleton = 1"
        ).fetchone()
        if row is None:
            return RuntimeMode.STOPPED, 0
        return RuntimeMode(str(row["mode"])), int(row["revision"])

    def enter(
        self,
        *,
        purpose: MaintenancePurpose,
        authorization_ref: str,
        owner_ref: str,
        expected_revision: int,
    ) -> MaintenanceEnterResult:
        _mode, revision = self._read_revision()
        if revision != expected_revision:
            raise OF01Error(
                OF01ErrorCode.PRECONDITION_CHANGED,
                "runtime revision mismatch",
                {"expected": expected_revision, "actual": revision},
            )
        now = time.time_ns()
        new_revision = revision + 1
        self._store.connection.execute(
            """
            UPDATE runtime_control
            SET mode = ?, revision = ?, changed_at_ns = ?, reason_code = ?, authorization_ref = ?
            WHERE singleton = 1
            """,
            (
                RuntimeMode.MAINTENANCE.value,
                new_revision,
                now,
                f"MAINTENANCE_{purpose.value}",
                authorization_ref,
            ),
        )
        lease = MaintenanceLease(
            lease_id=new_uuid(),
            ledger_authority_id=self._store.ledger_authority_id,
            purpose=purpose,
            authorization_ref=authorization_ref,
            owner_ref=owner_ref,
            issued_at_ns=now,
            expires_at_ns=now + self.LEASE_TTL_NS,
            runtime_revision=new_revision,
        )
        self._active_lease = lease
        return MaintenanceEnterResult(
            lease=lease,
            runtime_revision=new_revision,
            mode=RuntimeMode.MAINTENANCE,
        )

    def exit(
        self,
        *,
        lease_id: str,
        expected_revision: int,
    ) -> MaintenanceExitResult:
        if self._active_lease is None or self._active_lease.lease_id != lease_id:
            raise OF01Error(
                OF01ErrorCode.INVALID_COMMAND,
                "maintenance lease not found",
                {"lease_id": lease_id},
            )
        _mode, revision = self._read_revision()
        if revision != expected_revision:
            raise OF01Error(
                OF01ErrorCode.PRECONDITION_CHANGED,
                "runtime revision mismatch on exit",
                {"expected": expected_revision, "actual": revision},
            )
        now = time.time_ns()
        new_revision = revision + 1
        self._store.connection.execute(
            """
            UPDATE runtime_control
            SET mode = ?, revision = ?, changed_at_ns = ?, reason_code = ?, authorization_ref = NULL
            WHERE singleton = 1
            """,
            (RuntimeMode.READY.value, new_revision, now, "MAINTENANCE_EXIT"),
        )
        self._active_lease = None
        return MaintenanceExitResult(
            runtime_revision=new_revision,
            mode=RuntimeMode.READY,
        )
