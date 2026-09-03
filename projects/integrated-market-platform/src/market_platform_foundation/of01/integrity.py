"""Read-only OF-01 integrity verification."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from .canonical import RECORD_PROFILE, commit_hash_from_obj, record_hash_from_obj
from .cas import LocalCAS
from .errors import OF01Error, OF01ErrorCode
from .ids import new_uuid
from .records import record_hash
from .sqlite_store import SQLiteAuthorityStore


class IntegrityMode(StrEnum):
    QUICK = "QUICK"
    FULL = "FULL"
    FORENSIC = "FORENSIC"
    BACKUP_VERIFY = "BACKUP_VERIFY"
    RESTORE_VERIFY = "RESTORE_VERIFY"


class FindingClass(StrEnum):
    AUTHORITATIVE_FATAL = "AUTHORITATIVE_FATAL"
    OPERATIONAL_DEGRADED = "OPERATIONAL_DEGRADED"
    REBUILDABLE = "REBUILDABLE"
    HOUSEKEEPING = "HOUSEKEEPING"


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    code: str
    finding_class: FindingClass
    message: str
    details: dict[str, str | int]


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    report_id: str
    mode: IntegrityMode
    authority_id: str
    high_water_sequence: int
    findings: tuple[IntegrityFinding, ...]
    completed_at_ns: int

    @property
    def has_fatal(self) -> bool:
        return any(f.finding_class == FindingClass.AUTHORITATIVE_FATAL for f in self.findings)


class IntegrityChecker:
    def __init__(
        self,
        store: SQLiteAuthorityStore,
        *,
        cas: LocalCAS | None = None,
        on_fatal: Callable[[IntegrityReport], None] | None = None,
    ) -> None:
        self._store = store
        self._cas = cas
        self._on_fatal = on_fatal

    def check(self, mode: IntegrityMode = IntegrityMode.QUICK) -> IntegrityReport:
        findings: list[IntegrityFinding] = []
        conn = self._store.connection
        high_row = conn.execute("SELECT MAX(commit_sequence) FROM ledger_commits").fetchone()
        high_water = int(high_row[0]) if high_row and high_row[0] is not None else 0

        if not self._store.integrity_ok():
            findings.append(
                IntegrityFinding(
                    code=OF01ErrorCode.INTEGRITY_FATAL.value,
                    finding_class=FindingClass.AUTHORITATIVE_FATAL,
                    message="quick_check failed",
                    details={},
                )
            )
        if not self._store.foreign_keys_ok():
            findings.append(
                IntegrityFinding(
                    code=OF01ErrorCode.FOREIGN_KEY_MISMATCH.value,
                    finding_class=FindingClass.AUTHORITATIVE_FATAL,
                    message="foreign key check failed",
                    details={},
                )
            )

        if mode in {IntegrityMode.FULL, IntegrityMode.FORENSIC, IntegrityMode.BACKUP_VERIFY, IntegrityMode.RESTORE_VERIFY}:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            if row is None or str(row[0]) != "ok":
                findings.append(
                    IntegrityFinding(
                        code=OF01ErrorCode.INTEGRITY_FATAL.value,
                        finding_class=FindingClass.AUTHORITATIVE_FATAL,
                        message="integrity_check failed",
                        details={"status": str(row[0]) if row else "missing"},
                    )
                )
            findings.extend(self._check_record_hashes(conn))
            findings.extend(self._check_commit_hashes(conn))
            if self._cas is not None:
                findings.extend(self._check_referenced_cas(conn))

        report = IntegrityReport(
            report_id=new_uuid(),
            mode=mode,
            authority_id=self._store.ledger_authority_id,
            high_water_sequence=high_water,
            findings=tuple(findings),
            completed_at_ns=time.time_ns(),
        )
        if report.has_fatal and self._on_fatal is not None:
            self._on_fatal(report)
        return report

    def _check_record_hashes(self, conn: sqlite3.Connection) -> list[IntegrityFinding]:
        findings: list[IntegrityFinding] = []
        items = conn.execute(
            """
            SELECT record_type, record_id, record_hash
            FROM ledger_commit_items
            """
        ).fetchall()
        from .readers import _load_record

        for item in items:
            rec = _load_record(conn, str(item["record_type"]), str(item["record_id"]))
            if rec is None:
                findings.append(
                    IntegrityFinding(
                        code=OF01ErrorCode.MEMBERSHIP_MISMATCH.value,
                        finding_class=FindingClass.AUTHORITATIVE_FATAL,
                        message="commit item missing typed row",
                        details={
                            "record_type": str(item["record_type"]),
                            "record_id": str(item["record_id"]),
                        },
                    )
                )
                continue
            expected = record_hash(rec)
            if expected != str(item["record_hash"]):
                findings.append(
                    IntegrityFinding(
                        code=OF01ErrorCode.RECORD_HASH_MISMATCH.value,
                        finding_class=FindingClass.AUTHORITATIVE_FATAL,
                        message="stored record hash mismatch",
                        details={
                            "record_type": str(item["record_type"]),
                            "record_id": str(item["record_id"]),
                        },
                    )
                )
        return findings

    def _check_commit_hashes(self, conn: sqlite3.Connection) -> list[IntegrityFinding]:
        findings: list[IntegrityFinding] = []
        commits = conn.execute(
            """
            SELECT commit_sequence, commit_id, commit_hash, command_id, command_hash,
                   command_type, recorded_at_ns, record_count, ledger_authority_id,
                   commit_schema_version, commit_canonicalization_profile, hash_profile,
                   command_schema_version, command_canonicalization_profile
            FROM ledger_commits
            """
        ).fetchall()
        for commit in commits:
            items = conn.execute(
                """
                SELECT item_ordinal, record_type, record_id, record_schema_version,
                       record_canonicalization_profile, record_hash
                FROM ledger_commit_items
                WHERE commit_sequence = ?
                ORDER BY item_ordinal
                """,
                (int(commit["commit_sequence"]),),
            ).fetchall()
            commit_obj = {
                "command_canonicalization_profile": str(commit["command_canonicalization_profile"]),
                "command_hash": str(commit["command_hash"]),
                "command_id": str(commit["command_id"]),
                "command_schema_version": int(commit["command_schema_version"]),
                "command_type": str(commit["command_type"]),
                "commit_canonicalization_profile": str(commit["commit_canonicalization_profile"]),
                "commit_id": str(commit["commit_id"]),
                "commit_schema_version": int(commit["commit_schema_version"]),
                "commit_sequence": int(commit["commit_sequence"]),
                "hash_profile": str(commit["hash_profile"]),
                "items": [
                    {
                        "item_ordinal": int(i["item_ordinal"]),
                        "record_canonicalization_profile": str(i["record_canonicalization_profile"]),
                        "record_hash": str(i["record_hash"]),
                        "record_id": str(i["record_id"]),
                        "record_schema_version": int(i["record_schema_version"]),
                        "record_type": str(i["record_type"]),
                    }
                    for i in items
                ],
                "ledger_authority_id": str(commit["ledger_authority_id"]),
                "record_count": int(commit["record_count"]),
                "recorded_at_ns": int(commit["recorded_at_ns"]),
            }
            expected = commit_hash_from_obj(commit_obj)
            if expected != str(commit["commit_hash"]):
                findings.append(
                    IntegrityFinding(
                        code=OF01ErrorCode.COMMIT_HASH_MISMATCH.value,
                        finding_class=FindingClass.AUTHORITATIVE_FATAL,
                        message="stored commit hash mismatch",
                        details={"commit_sequence": int(commit["commit_sequence"])},
                    )
                )
        return findings

    def _check_referenced_cas(self, conn: sqlite3.Connection) -> list[IntegrityFinding]:
        findings: list[IntegrityFinding] = []
        rows = conn.execute("SELECT content_hash, byte_size FROM artifacts").fetchall()
        referenced = {str(r["content_hash"]): int(r["byte_size"]) for r in rows}
        inventory = {obj.content_hash: obj.byte_size for obj in self._cas.inventory()}
        for content_hash, byte_size in referenced.items():
            if content_hash not in inventory:
                findings.append(
                    IntegrityFinding(
                        code=OF01ErrorCode.CAS_REFERENCED_OBJECT_MISSING.value,
                        finding_class=FindingClass.AUTHORITATIVE_FATAL,
                        message="referenced CAS object missing",
                        details={"content_hash": content_hash},
                    )
                )
            elif inventory[content_hash] != byte_size:
                findings.append(
                    IntegrityFinding(
                        code=OF01ErrorCode.CAS_HASH_MISMATCH.value,
                        finding_class=FindingClass.AUTHORITATIVE_FATAL,
                        message="referenced CAS byte size mismatch",
                        details={"content_hash": content_hash},
                    )
                )
        for content_hash in inventory:
            if content_hash not in referenced:
                findings.append(
                    IntegrityFinding(
                        code=OF01ErrorCode.CAS_ORPHAN_FOUND.value,
                        finding_class=FindingClass.HOUSEKEEPING,
                        message="unreferenced CAS object",
                        details={"content_hash": content_hash},
                    )
                )
        return findings
