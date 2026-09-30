"""User-level IMP cache outside any checkout: local models, runtimes, public registries.

Large or shared artifacts (model weights, a local inference runtime, public datasets)
must never live in Git and should not be duplicated per worktree. They live under
``IMP_CACHE_DIR`` or, by default, ``%LOCALAPPDATA%\\IMP`` (``~/.cache/imp`` elsewhere).
Each artifact is described by a small JSON manifest written by an explicit setup
step; runtime code only reads manifests and never downloads.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

CACHE_ENV = "IMP_CACHE_DIR"


def imp_cache_dir(env: Mapping[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    override = str(values.get(CACHE_ENV) or "").strip()
    if override:
        return Path(override).expanduser()
    local = str(values.get("LOCALAPPDATA") or "").strip()
    return Path(local) / "IMP" if local else Path.home() / ".cache" / "imp"


def read_manifest(path: Path) -> dict[str, Any] | None:
    """A manifest dict, or None when absent or unreadable (never raises)."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


__all__ = ["CACHE_ENV", "imp_cache_dir", "read_manifest", "write_json_atomic"]
