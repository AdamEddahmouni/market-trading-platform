from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import BinaryIO

from src.ticker_metadata.storage import MetadataBoundaryError


class MetadataRefreshLock:
    def __init__(self, database_path: str | Path):
        resolved = Path(database_path).resolve(strict=False)
        identity = hashlib.sha256(os.path.normcase(str(resolved)).encode("utf-8")).hexdigest()
        self.path = resolved.parent / f".{identity}.metadata-refresh.lock"
        self._handle: BinaryIO | None = None

    def __enter__(self) -> "MetadataRefreshLock":
        handle = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            handle.seek(0)
            handle.write(b"\x00")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise MetadataBoundaryError(
                "metadata_refresh_locked",
                "Another metadata refresh holds the selected database lock",
            ) from exc
        self._handle = handle
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
