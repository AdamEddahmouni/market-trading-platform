"""Verified OF-01 backup creation and manifest publication."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from .canonical import HASH_PROFILE, sha256_upper
from .cas import LocalCAS
from .errors import OF01Error, OF01ErrorCode
from .ids import new_uuid, validate_hash
from .integrity import IntegrityChecker, IntegrityMode
from .sqlite_store import SQLiteAuthorityStore


class BackupState(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    RESTORE_TESTED = "RESTORE_TESTED"


@dataclass(frozen=True, slots=True)
class BackupCASEntry:
    content_hash: str
    byte_size: int
    coverage_type: str
    coverage_ref: str


@dataclass(frozen=True, slots=True)
class BackupManifestV1:
    backup_id: str
    state: BackupState
    source_authority_id: str
    database_schema_version: int
    hash_profile: str
    tool_identity: str
    source_revision: str
    created_at_ns: int
    snapshot_hash: str
    snapshot_byte_size: int
    high_water_sequence: int
    high_water_commit_id: str | None
    high_water_commit_hash: str | None
    cas_entries: tuple[BackupCASEntry, ...]
    destination_identity: str
    limitations: str | None
    verification_operation_id: str | None
    manifest_hash: str


def _hash_file(path: Path) -> tuple[str, int]:
    hasher = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest().upper(), size


def _manifest_body(manifest: BackupManifestV1) -> dict:
    return {
        "backup_id": manifest.backup_id,
        "state": manifest.state.value,
        "source_authority_id": manifest.source_authority_id,
        "database_schema_version": manifest.database_schema_version,
        "hash_profile": manifest.hash_profile,
        "tool_identity": manifest.tool_identity,
        "source_revision": manifest.source_revision,
        "created_at_ns": manifest.created_at_ns,
        "snapshot_hash": manifest.snapshot_hash,
        "snapshot_byte_size": manifest.snapshot_byte_size,
        "high_water_sequence": manifest.high_water_sequence,
        "high_water_commit_id": manifest.high_water_commit_id,
        "high_water_commit_hash": manifest.high_water_commit_hash,
        "cas_entries": [
            {
                "byte_size": e.byte_size,
                "content_hash": e.content_hash,
                "coverage_ref": e.coverage_ref,
                "coverage_type": e.coverage_type,
            }
            for e in sorted(manifest.cas_entries, key=lambda x: x.content_hash)
        ],
        "destination_identity": manifest.destination_identity,
        "limitations": manifest.limitations,
        "verification_operation_id": manifest.verification_operation_id,
    }


def manifest_hash(manifest: BackupManifestV1) -> str:
    body = json.dumps(_manifest_body(manifest), sort_keys=True, separators=(",", ":"))
    return sha256_upper(body.encode("utf-8"))


class BackupService:
    TOOL_IDENTITY = "imp-of01-backup-v1"

    def __init__(
        self,
        store: SQLiteAuthorityStore,
        *,
        cas: LocalCAS | None = None,
        db_path: Path,
        destination_root: Path,
    ) -> None:
        self._store = store
        self._cas = cas
        self._db_path = db_path
        self._destination_root = destination_root

    def create_backup(self) -> BackupManifestV1:
        backup_id = new_uuid()
        dest = self._destination_root / backup_id
        dest.mkdir(parents=True, exist_ok=True)
        snapshot_path = dest / "authority.sqlite3"
        cas_dest = dest / "cas"
        cas_dest.mkdir(exist_ok=True)

        snapshot_conn = sqlite3.connect(str(snapshot_path))
        try:
            self._store.connection.backup(snapshot_conn)
        finally:
            snapshot_conn.close()

        snapshot_hash, snapshot_size = _hash_file(snapshot_path)
        snap_conn = sqlite3.connect(str(snapshot_path))
        snap_conn.row_factory = sqlite3.Row
        try:
            high_row = snap_conn.execute(
                "SELECT commit_sequence, commit_id, commit_hash FROM ledger_commits ORDER BY commit_sequence DESC LIMIT 1"
            ).fetchone()
            schema_row = snap_conn.execute(
                "SELECT database_schema_version FROM ledger_metadata WHERE singleton = 1"
            ).fetchone()
            artifact_rows = snap_conn.execute(
                "SELECT content_hash, byte_size FROM artifacts"
            ).fetchall()
        finally:
            snap_conn.close()

        cas_entries: list[BackupCASEntry] = []
        if self._cas is not None:
            for row in artifact_rows:
                content_hash = str(row["content_hash"])
                byte_size = int(row["byte_size"])
                src = self._cas._object_path(content_hash)
                if not src.exists():
                    raise OF01Error(
                        OF01ErrorCode.BACKUP_INCOMPLETE,
                        "referenced CAS object missing during backup",
                        {"content_hash": content_hash},
                    )
                rel = content_hash[:2]
                target_dir = cas_dest / rel
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / content_hash
                shutil.copy2(src, target)
                cas_entries.append(
                    BackupCASEntry(
                        content_hash=content_hash,
                        byte_size=byte_size,
                        coverage_type="COPIED_OBJECT",
                        coverage_ref=str(target.relative_to(dest)),
                    )
                )

        manifest = BackupManifestV1(
            backup_id=backup_id,
            state=BackupState.UNVERIFIED,
            source_authority_id=self._store.ledger_authority_id,
            database_schema_version=int(schema_row[0]) if schema_row else 1,
            hash_profile=HASH_PROFILE,
            tool_identity=self.TOOL_IDENTITY,
            source_revision="local",
            created_at_ns=time.time_ns(),
            snapshot_hash=snapshot_hash,
            snapshot_byte_size=snapshot_size,
            high_water_sequence=int(high_row["commit_sequence"]) if high_row else 0,
            high_water_commit_id=str(high_row["commit_id"]) if high_row else None,
            high_water_commit_hash=str(high_row["commit_hash"]) if high_row else None,
            cas_entries=tuple(cas_entries),
            destination_identity=str(dest),
            limitations=None,
            verification_operation_id=None,
            manifest_hash="",
        )
        final_hash = manifest_hash(manifest)
        verified = replace(manifest, manifest_hash=final_hash)
        manifest_path = dest / "backup_manifest.json"
        manifest_path.write_text(
            json.dumps({**_manifest_body(verified), "manifest_hash": final_hash}, indent=2),
            encoding="utf-8",
        )
        return verified

    def verify_backup(self, manifest: BackupManifestV1) -> BackupManifestV1:
        if manifest_hash(manifest) != manifest.manifest_hash:
            raise OF01Error(
                OF01ErrorCode.BACKUP_VERIFY_FAILED,
                "manifest hash mismatch",
                {"backup_id": manifest.backup_id},
            )
        dest = Path(manifest.destination_identity)
        snapshot_path = dest / "authority.sqlite3"
        actual_hash, actual_size = _hash_file(snapshot_path)
        if actual_hash != manifest.snapshot_hash or actual_size != manifest.snapshot_byte_size:
            raise OF01Error(
                OF01ErrorCode.BACKUP_VERIFY_FAILED,
                "snapshot hash or size mismatch",
                {"backup_id": manifest.backup_id},
            )
        for entry in manifest.cas_entries:
            path = dest / entry.coverage_ref
            if not path.exists():
                raise OF01Error(
                    OF01ErrorCode.BACKUP_VERIFY_FAILED,
                    "CAS coverage object missing",
                    {"content_hash": entry.content_hash},
                )
            file_hash, file_size = _hash_file(path)
            validate_hash(entry.content_hash, field="content_hash")
            if file_hash != entry.content_hash or file_size != entry.byte_size:
                raise OF01Error(
                    OF01ErrorCode.BACKUP_VERIFY_FAILED,
                    "CAS coverage object mismatch",
                    {"content_hash": entry.content_hash},
                )
        return replace(
            manifest,
            state=BackupState.VERIFIED,
            verification_operation_id=new_uuid(),
        )
