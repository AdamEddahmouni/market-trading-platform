"""Operator diagnostics for IMP durable state directory resolution.

Linked Git worktrees default `IMP_STATE_DIR` to `<worktree>/.local`, which is
empty for feature worktrees. Canonical FTEP empirical state lives on the primary
checkout's IMP tree unless `IMP_STATE_DIR` overrides it. This module surfaces
that distinction without opening persistence for writes.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

IMP_ROOT = Path(__file__).resolve().parents[1]
DB_FILENAME = "imp-state.sqlite3"
CANONICAL_STATE_ENV = "IMP_CANONICAL_STATE_DIR"


def _monorepo_root(imp_root: Path) -> Path | None:
    parent = imp_root.parent
    if parent.name == "projects" and imp_root.name == "integrated-market-platform":
        return parent.parent
    return None


def _git_worktree_roots(imp_root: Path) -> list[tuple[Path, str | None]]:
    try:
        completed = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(imp_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    if completed.returncode != 0:
        return []
    entries: list[tuple[Path, str | None]] = []
    current_path: Path | None = None
    current_branch: str | None = None
    for line in completed.stdout.splitlines():
        if line.startswith("worktree "):
            if current_path is not None:
                entries.append((current_path, current_branch))
            current_path = Path(line[len("worktree ") :].strip()).resolve()
            current_branch = None
        elif line.startswith("branch "):
            current_branch = line[len("branch ") :].strip()
    if current_path is not None:
        entries.append((current_path, current_branch))
    return entries


def _primary_monorepo_root(imp_root: Path) -> Path | None:
    for worktree_root, branch in _git_worktree_roots(imp_root):
        normalized = str(worktree_root).replace("\\", "/")
        if "/.worktrees/" in normalized or normalized.endswith("/.worktrees"):
            continue
        if branch in {"refs/heads/main", "main"}:
            return worktree_root
    for worktree_root, _branch in _git_worktree_roots(imp_root):
        normalized = str(worktree_root).replace("\\", "/")
        if "/.worktrees/" in normalized or normalized.endswith("/.worktrees"):
            continue
        return worktree_root
    return _monorepo_root(imp_root)


def default_canonical_state_dir(imp_root: Path) -> Path:
    override = os.environ.get(CANONICAL_STATE_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    mono = _primary_monorepo_root(imp_root)
    if mono is not None:
        return (mono / "projects" / "integrated-market-platform" / ".local").resolve()
    return (imp_root / ".local").resolve()


def effective_state_dir(imp_root: Path) -> Path:
    override = os.environ.get("IMP_STATE_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (imp_root / ".local").resolve()


def persistence_configured() -> bool:
    if os.environ.get("IMP_STATE_DIR"):
        return True
    return os.environ.get("IMP_PERSIST_STATE") == "1"


def _read_session_count(db_path: Path) -> int | None:
    if not db_path.is_file():
        return None
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = connection.execute("SELECT COUNT(*) FROM forward_test_sessions").fetchone()
        return int(row[0]) if row is not None else 0
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def _detect_linked_worktree(imp_root: Path) -> bool:
    normalized = str(imp_root.resolve()).replace("\\", "/")
    if "/.worktrees/" in normalized:
        return True
    git_path = imp_root / ".git"
    if not git_path.is_file():
        return False
    try:
        raw = git_path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    return raw.startswith("gitdir:")


def collect_state_path_report(imp_root: Path | None = None) -> dict[str, Any]:
    root = (imp_root or IMP_ROOT).resolve()
    effective = effective_state_dir(root)
    canonical = default_canonical_state_dir(root)
    effective_db = effective / DB_FILENAME
    canonical_db = canonical / DB_FILENAME
    effective_sessions = _read_session_count(effective_db)
    canonical_sessions = _read_session_count(canonical_db)

    warnings: list[str] = []
    effective_count = 0 if effective_sessions is None else effective_sessions
    canonical_count = 0 if canonical_sessions is None else canonical_sessions
    if effective.resolve() != canonical.resolve():
        if effective_count == 0 and canonical_count > 0:
            warnings.append("WORKTREE_STATE_MISMATCH")
        if not persistence_configured() and canonical_count > 0:
            warnings.append("PERSIST_OFF_ZERO_SESSIONS_NOT_ABSENCE")

    return {
        "schema_version": "1.0.0",
        "artifact_kind": "imp_state_path_diagnostic",
        "imp_project_root": str(root),
        "is_linked_worktree": _detect_linked_worktree(root),
        "persistence_configured": persistence_configured(),
        "effective_state_dir": str(effective),
        "effective_database_path": str(effective_db),
        "effective_database_present": effective_db.is_file(),
        "effective_forward_test_session_count": effective_sessions,
        "canonical_state_dir": str(canonical),
        "canonical_database_path": str(canonical_db),
        "canonical_database_present": canonical_db.is_file(),
        "canonical_forward_test_session_count": canonical_sessions,
        "canonical_state_env_override": CANONICAL_STATE_ENV,
        "warnings": warnings,
        "operator_commands": {
            "state_path_diagnostic": "python tools/imp.py state-path",
            "ftep_campaign_status_canonical": (
                "set IMP_STATE_DIR=<canonical_state_dir> && "
                "python tools/imp.py ftep campaign-status FTEP-V1-002"
            ),
            "ftep_integrity_canonical": (
                "set IMP_STATE_DIR=<canonical_state_dir> && "
                "python tools/imp.py ftep integrity-check FTEP-V1-002"
            ),
        },
        "documentation": "docs/engineering/STATE_PATH_OPERATOR_CONVENTION.md",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_path", type=Path)
    args = parser.parse_args(argv)
    report = collect_state_path_report()
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["warnings"] else 0


if __name__ == "__main__":
    sys.exit(main())
