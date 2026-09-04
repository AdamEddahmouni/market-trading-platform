"""OF-01 local immutable content-addressed store."""

from __future__ import annotations

import hashlib
import os
import secrets
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from .canonical import CAS_LOCATOR_PROFILE, HASH_PROFILE, sha256_upper
from .errors import OF01Error, OF01ErrorCode
from .ids import validate_hash


@dataclass(frozen=True, slots=True)
class PreparedObject:
    temp_path: Path
    content_hash: str
    byte_size: int
    operation_id: str


@dataclass(frozen=True, slots=True)
class PublishedObject:
    content_hash: str
    byte_size: int
    final_path: Path


@dataclass(frozen=True, slots=True)
class CASObjectInfo:
    content_hash: str
    byte_size: int
    path: Path


class LocalCAS:
    HASH_PROFILE = HASH_PROFILE
    LOCATOR_PROFILE = CAS_LOCATOR_PROFILE

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._content_locks: dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()
        for sub in ("objects", "temporary", "quarantine", "locks"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def _object_path(self, content_hash: str) -> Path:
        validate_hash(content_hash, field="content_hash")
        prefix = content_hash[:2]
        return (
            self.root
            / "objects"
            / self.HASH_PROFILE
            / prefix
            / content_hash
        )

    def _lock_path(self, content_hash: str) -> Path:
        prefix = content_hash[:2]
        return self.root / "locks" / prefix / f"{content_hash}.lock"

    def _content_lock(self, content_hash: str) -> threading.Lock:
        with self._meta_lock:
            lock = self._content_locks.get(content_hash)
            if lock is None:
                lock = threading.Lock()
                self._content_locks[content_hash] = lock
            return lock

    def _hash_stream(self, source: BinaryIO) -> tuple[str, int, bytes]:
        hasher = hashlib.sha256()
        size = 0
        chunks: list[bytes] = []
        while True:
            chunk = source.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
            size += len(chunk)
            chunks.append(chunk)
        content_hash = hasher.hexdigest().upper()
        return content_hash, size, b"".join(chunks)

    def prepare(
        self,
        source: BinaryIO,
        expected_hash: str | None = None,
    ) -> PreparedObject:
        operation_id = secrets.token_hex(16)
        temp_path = self.root / "temporary" / f"{operation_id}.tmp"
        try:
            content_hash, byte_size, _ = self._hash_stream(source)
            if expected_hash is not None:
                validate_hash(expected_hash, field="expected_hash")
                if content_hash != expected_hash:
                    raise OF01Error(
                        OF01ErrorCode.CAS_HASH_MISMATCH,
                        "expected hash mismatch during prepare",
                        {"expected": expected_hash, "actual": content_hash},
                    )
            source.seek(0)
            with open(temp_path, "xb") as dest:
                while True:
                    chunk = source.read(65536)
                    if not chunk:
                        break
                    dest.write(chunk)
                dest.flush()
                os.fsync(dest.fileno())
        except OF01Error:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise
        except OSError as exc:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise OF01Error(
                OF01ErrorCode.CAS_PREPARE_FAILED,
                "failed to prepare CAS object",
                {"error": str(exc)},
            ) from exc
        return PreparedObject(
            temp_path=temp_path,
            content_hash=content_hash,
            byte_size=byte_size,
            operation_id=operation_id,
        )

    def publish(self, prepared: PreparedObject) -> PublishedObject:
        final_path = self._object_path(prepared.content_hash)
        lock_path = self._lock_path(prepared.content_hash)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        content_lock = self._content_lock(prepared.content_hash)
        with content_lock:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                raise OF01Error(
                    OF01ErrorCode.CAS_PREPARE_FAILED,
                    "publisher lock already held",
                    {"content_hash": prepared.content_hash},
                )
            try:
                os.write(fd, prepared.operation_id.encode("ascii"))
            finally:
                os.close(fd)
            try:
                if final_path.exists():
                    self._verify_file(final_path, prepared.content_hash, prepared.byte_size)
                    prepared.temp_path.unlink(missing_ok=True)
                    return PublishedObject(
                        content_hash=prepared.content_hash,
                        byte_size=prepared.byte_size,
                        final_path=final_path,
                    )
                final_path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(prepared.temp_path, final_path)
                self._verify_file(final_path, prepared.content_hash, prepared.byte_size)
                return PublishedObject(
                    content_hash=prepared.content_hash,
                    byte_size=prepared.byte_size,
                    final_path=final_path,
                )
            finally:
                lock_path.unlink(missing_ok=True)

    def _verify_file(self, path: Path, content_hash: str, byte_size: int) -> None:
        if not path.exists():
            raise OF01Error(
                OF01ErrorCode.CAS_REFERENCED_OBJECT_MISSING,
                "CAS object missing",
                {"content_hash": content_hash},
            )
        actual_size = path.stat().st_size
        if actual_size != byte_size:
            raise OF01Error(
                OF01ErrorCode.CAS_HASH_MISMATCH,
                "CAS byte size mismatch",
                {"expected": byte_size, "actual": actual_size},
            )
        with open(path, "rb") as handle:
            actual_hash, _, _ = self._hash_stream(handle)
        if actual_hash != content_hash:
            raise OF01Error(
                OF01ErrorCode.CAS_HASH_MISMATCH,
                "CAS content hash mismatch",
                {"expected": content_hash, "actual": actual_hash},
            )

    def open_verified(self, content_hash: str) -> BinaryIO:
        path = self._object_path(content_hash)
        if not path.exists():
            raise OF01Error(
                OF01ErrorCode.CAS_REFERENCED_OBJECT_MISSING,
                "referenced CAS object missing",
                {"content_hash": content_hash},
            )
        data = path.read_bytes()
        actual_hash = sha256_upper(data)
        if actual_hash != content_hash:
            raise OF01Error(
                OF01ErrorCode.CAS_HASH_MISMATCH,
                "referenced CAS object hash mismatch",
                {"expected": content_hash, "actual": actual_hash},
            )
        return BytesIO(data)

    def inventory(self) -> Iterator[CASObjectInfo]:
        base = self.root / "objects" / self.HASH_PROFILE
        if not base.exists():
            return
        for prefix_dir in sorted(base.iterdir()):
            if not prefix_dir.is_dir():
                continue
            for path in sorted(prefix_dir.iterdir()):
                if not path.is_file():
                    continue
                content_hash = path.name
                yield CASObjectInfo(
                    content_hash=content_hash,
                    byte_size=path.stat().st_size,
                    path=path,
                )

    def cleanup_temp(self, prepared: PreparedObject) -> None:
        prepared.temp_path.unlink(missing_ok=True)

    def probe_write(self) -> None:
        """Write, fsync, and remove a dedicated startup probe object."""
        operation_id = secrets.token_hex(16)
        probe_path = self.root / "temporary" / f"probe-{operation_id}.tmp"
        try:
            with open(probe_path, "xb") as handle:
                handle.write(b"probe")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise OF01Error(
                OF01ErrorCode.STORAGE_UNWRITABLE,
                "CAS probe write failed",
                {"error": str(exc)},
            ) from exc
        finally:
            probe_path.unlink(missing_ok=True)
