"""Source provenance and reproducibility (BUILD 34)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]


@dataclass(frozen=True)
class SourceProvenanceV1:
    repository_root: str
    commit_sha: str
    branch: str
    is_clean: bool
    dirty_paths: tuple[str, ...]
    source_tree_hash: str
    dependency_lock_hash: str


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _run_git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=cwd or ROOT,
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def get_repository_root() -> Path:
    return Path(_run_git("rev-parse", "--show-toplevel"))


def get_commit_sha(root: Path | None = None) -> str:
    return _run_git("rev-parse", "HEAD", cwd=root)


def get_branch(root: Path | None = None) -> str:
    branch = _run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=root)
    return branch


def get_dirty_paths(root: Path | None = None) -> tuple[str, ...]:
    root = root or get_repository_root()
    output = subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=root,
        text=True,
    )
    dirty: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        dirty.append(path)
    return tuple(sorted(dirty))


def is_source_tree_clean(root: Path | None = None) -> bool:
    return len(get_dirty_paths(root)) == 0


def hash_tracked_source_tree(root: Path | None = None) -> str:
    """Hash of tracked file contents at HEAD (git ls-tree + blob hashes)."""
    root = root or get_repository_root()
    tree_sha = _run_git("rev-parse", "HEAD^{tree}", cwd=root)
    entries: list[tuple[str, str]] = []
    output = subprocess.check_output(
        ["git", "ls-tree", "-r", tree_sha],
        cwd=root,
        text=True,
    )
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        meta, path = parts
        blob_sha = meta.split()[2]
        entries.append((path, blob_sha))
    entries.sort()
    payload = {"entries": entries}
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def hash_dependency_lock(root: Path | None = None) -> str:
    root = root or get_repository_root()
    lock_path = root / "phase0-dependency-lock.json"
    if not lock_path.exists():
        raise FileNotFoundError("phase0-dependency-lock.json not found")
    content = lock_path.read_bytes()
    return hashlib.sha256(content).hexdigest()


def verify_dependency_lock_consistent(root: Path | None = None) -> tuple[bool, str]:
    root = root or get_repository_root()
    lock_path = root / "phase0-dependency-lock.json"
    if not lock_path.exists():
        return False, "dependency lock file missing"
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"dependency lock invalid JSON: {exc}"
    required = {"schema_version", "implementation", "major_minor", "tested_patch", "third_party"}
    missing = required - set(data.keys())
    if missing:
        return False, f"dependency lock missing keys: {sorted(missing)}"
    return True, "OK"


def collect_source_provenance(root: Path | None = None) -> SourceProvenanceV1:
    root = root or get_repository_root()
    dirty = get_dirty_paths(root)
    return SourceProvenanceV1(
        repository_root=str(root),
        commit_sha=get_commit_sha(root),
        branch=get_branch(root),
        is_clean=len(dirty) == 0,
        dirty_paths=dirty,
        source_tree_hash=hash_tracked_source_tree(root),
        dependency_lock_hash=hash_dependency_lock(root),
    )


def dirty_tree_blocks_release(root: Path | None = None) -> tuple[bool, str]:
    """Return (blocked, reason). Blocked=True means release packaging must fail."""
    prov = collect_source_provenance(root)
    if not prov.is_clean:
        return True, f"dirty source tree: {list(prov.dirty_paths)}"
    ok, msg = verify_dependency_lock_consistent(root)
    if not ok:
        return True, msg
    return False, "OK"
