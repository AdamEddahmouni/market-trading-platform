"""OF-01 offline restore validation and activation."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .backup import BackupCASEntry, BackupManifestV1, BackupState, manifest_hash
from .cas import LocalCAS
from .errors import OF01Error, OF01ErrorCode
from .integrity import IntegrityChecker, IntegrityMode
from .sqlite_store import SQLiteAuthorityStore, configure_connection, open_connection


@dataclass(frozen=True, slots=True)
class RestoreCandidate:
    backup_dir: Path
    manifest: BackupManifestV1


@dataclass(frozen=True, slots=True)
class RestoreValidationResult:
    authority_id: str
    integrity_ok: bool
    high_water_sequence: int
    manifest_state: BackupState


class RestoreService:
    def __init__(self, *, expected_authority_id: str) -> None:
        self._expected_authority_id = expected_authority_id

    def load_candidate(self, backup_dir: Path) -> RestoreCandidate:
        manifest_path = backup_dir / "backup_manifest.json"
        if not manifest_path.exists():
            raise OF01Error(
                OF01ErrorCode.RESTORE_VERIFY_FAILED,
                "backup manifest missing",
                {"path": str(manifest_path)},
            )
        body = json.loads(manifest_path.read_text(encoding="utf-8"))
        cas_entries = tuple(
            {
                "content_hash": entry["content_hash"],
                "byte_size": entry["byte_size"],
                "coverage_type": entry["coverage_type"],
                "coverage_ref": entry["coverage_ref"],
            }
            for entry in body.get("cas_entries", [])
        )
        manifest = BackupManifestV1(
            backup_id=str(body["backup_id"]),
            state=BackupState(str(body["state"])),
            source_authority_id=str(body["source_authority_id"]),
            database_schema_version=int(body["database_schema_version"]),
            hash_profile=str(body["hash_profile"]),
            tool_identity=str(body["tool_identity"]),
            source_revision=str(body["source_revision"]),
            created_at_ns=int(body["created_at_ns"]),
            snapshot_hash=str(body["snapshot_hash"]),
            snapshot_byte_size=int(body["snapshot_byte_size"]),
            high_water_sequence=int(body["high_water_sequence"]),
            high_water_commit_id=body.get("high_water_commit_id"),
            high_water_commit_hash=body.get("high_water_commit_hash"),
            cas_entries=tuple(
                BackupCASEntry(
                    content_hash=str(e["content_hash"]),
                    byte_size=int(e["byte_size"]),
                    coverage_type=str(e["coverage_type"]),
                    coverage_ref=str(e["coverage_ref"]),
                )
                for e in sorted(cas_entries, key=lambda x: x["content_hash"])
            ),
            destination_identity=str(body["destination_identity"]),
            limitations=body.get("limitations"),
            verification_operation_id=body.get("verification_operation_id"),
            manifest_hash=str(body["manifest_hash"]),
        )
        if manifest_hash(manifest) != manifest.manifest_hash:
            raise OF01Error(
                OF01ErrorCode.RESTORE_VERIFY_FAILED,
                "manifest hash mismatch",
                {"backup_id": manifest.backup_id},
            )
        return RestoreCandidate(backup_dir=backup_dir, manifest=manifest)

    def validate(self, candidate: RestoreCandidate) -> RestoreValidationResult:
        manifest = candidate.manifest
        if manifest.source_authority_id != self._expected_authority_id:
            raise OF01Error(
                OF01ErrorCode.AUTHORITY_IDENTITY_MISMATCH,
                "restore authority identity mismatch",
                {
                    "expected": self._expected_authority_id,
                    "actual": manifest.source_authority_id,
                },
            )
        snapshot_path = candidate.backup_dir / "authority.sqlite3"
        if not snapshot_path.exists():
            raise OF01Error(
                OF01ErrorCode.RESTORE_VERIFY_FAILED,
                "snapshot database missing",
                {"path": str(snapshot_path)},
            )
        conn = open_connection(snapshot_path)
        try:
            row = conn.execute(
                "SELECT ledger_authority_id FROM ledger_metadata WHERE singleton = 1"
            ).fetchone()
            if row is None or str(row[0]) != self._expected_authority_id:
                raise OF01Error(
                    OF01ErrorCode.AUTHORITY_IDENTITY_MISMATCH,
                    "snapshot authority mismatch",
                    {},
                )
            store = SQLiteAuthorityStore(conn, ledger_authority_id=self._expected_authority_id)
            cas_root = candidate.backup_dir / "cas"
            cas = LocalCAS(cas_root) if cas_root.exists() else None
            checker = IntegrityChecker(store, cas=cas)
            report = checker.check(IntegrityMode.RESTORE_VERIFY)
            return RestoreValidationResult(
                authority_id=self._expected_authority_id,
                integrity_ok=not report.has_fatal,
                high_water_sequence=manifest.high_water_sequence,
                manifest_state=manifest.state,
            )
        finally:
            conn.close()
