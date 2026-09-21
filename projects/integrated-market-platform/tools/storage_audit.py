"""Read-only IMP repository storage observability.

Default command path: ``python tools/imp.py storage audit``.

This tool measures disk, Git object, worktree, dependency, cache, artifact,
and optional project-scoped Cursor storage. It never deletes files, never
prunes worktrees or branches, never runs destructive Git maintenance, and
never mutates collector/runtime/evidence state.

storage audit output is advisory and is not deletion authority.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from heapq import heappush, heapreplace, nlargest
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Callable, Sequence


SCHEMA_VERSION = "1.0"
REPORT_TYPE = "imp_storage_audit"
ADVISORY_NOTICE = "storage audit output is advisory and is not deletion authority"

# Conservative warning thresholds (bytes / counts). Documented in the SOP.
WORKTREE_COUNT_HIGH = 50
REVIEW_TEMP_HIGH_BYTES = 1 * 1024 * 1024 * 1024
CURSOR_PROJECT_HIGH_BYTES = 2 * 1024 * 1024 * 1024
GIT_OBJECT_HIGH_BYTES = 5 * 1024 * 1024 * 1024
PROTECTED_EVIDENCE_HIGH_BYTES = 1 * 1024 * 1024 * 1024
UNKNOWN_LARGE_PATH_BYTES = 512 * 1024 * 1024

FILE_ATTRIBUTE_REPARSE_POINT = 0x400

ALLOWED_GIT_VERBS = frozenset(
    {
        "worktree",
        "count-objects",
        "rev-parse",
        "status",
        "rev-list",
        "merge-base",
        "show-ref",
    }
)
ALLOWED_WORKTREE_SUBCOMMANDS = frozenset({"list"})
FORBIDDEN_GIT_VERBS = frozenset(
    {
        "gc",
        "prune",
        "clean",
        "reset",
        "checkout",
        "switch",
        "merge",
        "rebase",
        "push",
        "commit",
        "add",
        "rm",
        "mv",
        "stash",
        "reflog",
        "repack",
        "fetch",
        "pull",
        "clone",
        "init",
        "config",
        "filter-branch",
        "replace",
        "update-ref",
        "notes",
        "tag",
        "branch",
        "remote",
        "worktree-add",
        "worktree-remove",
        "worktree-move",
        "worktree-prune",
    }
)

DEPENDENCY_DIR_NAMES = frozenset({".venv", "venv", "node_modules"})
VENV_MARKER_FILES = frozenset({"pyvenv.cfg"})
CACHE_DIR_NAMES = {
    "__pycache__": "pycache",
    ".pytest_cache": "pytest",
    ".mypy_cache": "mypy",
    ".ruff_cache": "ruff",
    ".tox": "test_cache",
    ".nox": "test_cache",
    ".hypothesis": "test_cache",
    ".vite": "frontend_build",
    ".turbo": "frontend_build",
    ".next": "frontend_build",
    ".nuxt": "frontend_build",
    ".parcel-cache": "frontend_build",
    ".eslintcache": "eslint",
    "htmlcov": "coverage",
    "coverage": "coverage",
    "dist": "build_dist",
    "build": "build_dist",
    ".cache": "generic_cache",
}
CACHE_FILE_NAMES = {
    ".coverage": "coverage",
    ".eslintcache": "eslint",
    "coverage.xml": "coverage",
}
CACHE_SUFFIXES = {
    ".pyc": "pycache",
    ".pyo": "pycache",
    ".tsbuildinfo": "frontend_build",
}

PROTECTED_PATH_TOKENS = (
    "artifacts",
    "evidence",
    "receipts",
    "historical-development",
    "historical_development",
    "historical-rth",
    "historical_rth",
    "item9-prospective-proof-receipts",
    "forward-test",
    "forward_test",
    "prospective",
    "corpora",
    "operator-artifacts",
    "benchmarks",
    "run-manifests",
    "research-datasets",
    ".imp-actual-01-phase-d",
)

TEMPORARY_PREFIXES = (".review-", ".agent-", ".rth-")
TEMPORARY_DIR_NAMES = frozenset(
    {
        ".review",
        "ci-scratch",
        "tmp",
        "temp",
        ".tmp",
        ".temp",
    }
)

CURSOR_CATEGORY_NAMES = {
    "agent-transcripts": "agent_transcripts",
    "agent-tools": "agent_tools",
    "terminals": "logs",
    "logs": "logs",
    "snapshots": "checkpoints_snapshots",
    "checkpoints": "checkpoints_snapshots",
    "mcps": "indexes_cache",
    "indexes": "indexes_cache",
    "cache": "indexes_cache",
    "canvases": "temporary_project_state",
}

ProgressFn = Callable[[str], None]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def format_bytes(value: int) -> str:
    amount = float(max(0, int(value)))
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if amount < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(amount)} {unit}"
            return f"{amount:.2f} {unit}"
        amount /= 1024.0
    return f"{int(value)} B"


def _posix(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def _strip_win_extended_prefix(text: str) -> str:
    if text.startswith("\\\\?\\UNC\\"):
        return "\\\\" + text[8:]
    if text.startswith("\\\\?\\"):
        return text[4:]
    if text.startswith("//?/UNC/") or text.startswith("//?/UNC\\"):
        return "//" + text[8:]
    if text.startswith("//?/"):
        return text[4:]
    return text


def classify_path_syntax(text: str) -> str:
    """Classify a path by the syntax it represents, not by the host OS.

    Returns ``windows-drive``, ``posix``, or ``unsupported``.
    """
    raw = _strip_win_extended_prefix(text)
    if not raw:
        return "unsupported"
    if raw.startswith("\\\\") or raw.startswith("//"):
        return "unsupported"
    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha() and (len(raw) == 2 or raw[2] in "\\/"):
        return "windows-drive"
    if raw.startswith("/"):
        return "posix"
    return "unsupported"


def _represented_path_text(repo_root: Path | str) -> str:
    raw = os.fspath(repo_root)
    kind = classify_path_syntax(raw)
    native = (os.name == "nt" and kind == "windows-drive") or (os.name != "nt" and kind == "posix")
    if native:
        try:
            return os.fspath(Path(raw).resolve())
        except OSError:
            return raw
    return raw


def _slug_from_parts(parts: Sequence[str], *, drive_letter: str | None) -> str:
    remainder = [part for part in parts if part not in {"", "/", "\\"}]
    if any(part in {".", ".."} for part in remainder):
        return ""
    if drive_letter is not None:
        if len(drive_letter) != 1 or not drive_letter.isalpha() or not remainder:
            return ""
        slug = "-".join((drive_letter.lower(), *remainder))
    else:
        if not remainder:
            return ""
        slug = "-".join(remainder)
    if not slug or "/" in slug or "\\" in slug:
        return ""
    return slug


def location_compare_key(path: Path | str) -> str:
    """Canonical compare key so ``\\\\?\\C:\\`` and ``C:\\`` are the same location."""
    text = _strip_win_extended_prefix(os.fspath(path))
    kind = classify_path_syntax(text)
    if kind == "windows-drive":
        parsed = PureWindowsPath(text)
        drive = parsed.drive.lower().rstrip("\\/")
        rest = [part.lower() for part in parsed.parts[1:] if part not in {"", "/", "\\"}]
        return drive + "\\" + "\\".join(rest)
    if kind == "posix":
        parsed = PurePosixPath(text)
        key = parsed.as_posix()
        if key != "/":
            key = key.rstrip("/")
        return key
    return "\x00" + text


def path_is_within_root(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        pass
    try:
        child_text = os.fspath(candidate.resolve())
        root_text = os.fspath(root.resolve())
    except OSError:
        child_text = os.fspath(candidate)
        root_text = os.fspath(root)
    child = location_compare_key(child_text)
    base = location_compare_key(root_text)
    if child.startswith("\x00") or base.startswith("\x00"):
        return False
    if child == base:
        return True
    sep = "\\" if classify_path_syntax(_strip_win_extended_prefix(root_text)) == "windows-drive" else "/"
    if base.endswith(sep):
        return child.startswith(base)
    return child.startswith(base + sep)


def git_command_verb(args: Sequence[str]) -> tuple[str, tuple[str, ...]]:
    tokens = list(args)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "-C":
            index += 2
            continue
        if token.startswith("--git-dir=") or token.startswith("--work-tree="):
            index += 1
            continue
        if token in {"--git-dir", "--work-tree"}:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        verb = token
        remainder = tuple(tokens[index + 1 :])
        if verb == "worktree" and remainder:
            sub = remainder[0]
            if sub in {"remove", "prune", "move", "add", "lock", "unlock", "repair"}:
                return f"worktree-{sub}", remainder[1:]
        return verb, remainder
    return "", ()


def git_argv_is_allowed(args: Sequence[str]) -> bool:
    verb, remainder = git_command_verb(args)
    if not verb or verb in FORBIDDEN_GIT_VERBS:
        return False
    if verb not in ALLOWED_GIT_VERBS:
        return False
    if verb == "worktree":
        if not remainder or remainder[0] not in ALLOWED_WORKTREE_SUBCOMMANDS:
            return False
    return True


class ReadOnlyGit:
    """Git subprocess wrapper that refuses destructive commands."""

    def __init__(self) -> None:
        self.history: list[tuple[str, tuple[str, ...]]] = []

    def run(self, args: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
        argv = tuple(str(item) for item in args)
        if not git_argv_is_allowed(argv):
            raise RuntimeError(f"blocked non-read-only git command: {' '.join(argv)}")
        self.history.append((str(cwd), argv))
        return subprocess.run(
            ["git", *argv],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )

    def text(self, args: Sequence[str], *, cwd: Path) -> tuple[int, str, str]:
        completed = self.run(args, cwd=cwd)
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


@dataclass(frozen=True)
class WorktreePorcelain:
    path: str
    head: str | None
    branch: str | None
    detached: bool
    prunable: bool
    locked: bool
    bare: bool


def parse_worktree_porcelain(text: str) -> list[WorktreePorcelain]:
    records: list[WorktreePorcelain] = []
    current: dict[str, Any] = {}

    def flush() -> None:
        path = current.get("path")
        if not path:
            return
        records.append(
            WorktreePorcelain(
                path=str(path),
                head=current.get("head"),
                branch=current.get("branch"),
                detached=bool(current.get("detached")),
                prunable=bool(current.get("prunable")),
                locked=bool(current.get("locked")),
                bare=bool(current.get("bare")),
            )
        )

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            current = {}
            continue
        if line.startswith("worktree "):
            flush()
            current = {"path": line[len("worktree ") :].strip()}
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD ") :].strip() or None
        elif line.startswith("branch "):
            current["branch"] = line[len("branch ") :].strip() or None
        elif line == "detached":
            current["detached"] = True
        elif line == "bare":
            current["bare"] = True
        elif line == "prunable" or line.startswith("prunable "):
            current["prunable"] = True
        elif line == "locked" or line.startswith("locked "):
            current["locked"] = True
    flush()
    return records


def classify_link_kind(path: Path, st: os.stat_result | None = None) -> str:
    try:
        info = st if st is not None else os.lstat(path)
    except OSError:
        return "UNREADABLE"
    try:
        if path.is_symlink():
            return "SYMLINK"
    except OSError:
        pass
    if stat.S_ISLNK(info.st_mode):
        return "SYMLINK"
    attributes = int(getattr(info, "st_file_attributes", 0) or 0)
    if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
        return "JUNCTION" if os.name == "nt" else "REPARSE"
    return "PHYSICAL"


def read_link_target(path: Path) -> str | None:
    try:
        return os.readlink(path)
    except OSError:
        return None


def is_venv_directory(path: Path) -> bool:
    name = path.name.lower()
    if name in {".venv", "venv"}:
        return True
    if name == "env" and (path / "pyvenv.cfg").is_file():
        return True
    try:
        return (path / "pyvenv.cfg").is_file()
    except OSError:
        return False


def is_protected_relpath(relpath: str) -> bool:
    normalized = relpath.replace("\\", "/").lower()
    parts = [part for part in normalized.split("/") if part]
    if any(part in PROTECTED_PATH_TOKENS for part in parts):
        return True
    return any(token in normalized for token in ("item9-prospective", "ftep-v1-", "evidence-ledgers"))


def is_temporary_relpath(relpath: str) -> bool:
    normalized = relpath.replace("\\", "/").lower()
    name = Path(normalized).name
    if any(name.startswith(prefix) for prefix in TEMPORARY_PREFIXES):
        return True
    return name in TEMPORARY_DIR_NAMES


def _rel_parts(relpath: str) -> list[str]:
    return [part for part in relpath.replace("\\", "/").split("/") if part]


def _rel_inside_named_cache_dir(relpath: str) -> bool:
    parts = _rel_parts(relpath)
    return any(part in CACHE_DIR_NAMES for part in parts[:-1])


def _rel_inside_protected_parent(relpath: str) -> bool:
    parts = _rel_parts(relpath)
    if len(parts) <= 1:
        return False
    parent = "/".join(parts[:-1])
    return is_protected_relpath(parent)


DEPENDENCY_TREE_NAMES = frozenset({".venv", "venv", "node_modules"})


def _rel_inside_dependency_tree(relpath: str) -> bool:
    return any(part in DEPENDENCY_TREE_NAMES for part in _rel_parts(relpath))


def cache_counts_toward_reclaimable(relpath: str) -> bool:
    """Caches inside venvs, node_modules, or protected evidence are observed, not reclaimable."""
    if is_protected_relpath(relpath) or _rel_inside_protected_parent(relpath):
        return False
    if _rel_inside_dependency_tree(relpath):
        return False
    return True


def _largest_path_class(relpath: str, is_dir: bool) -> str:
    if is_protected_relpath(relpath):
        return "PROTECTED_OR_REVIEW_REQUIRED"
    if is_temporary_relpath(relpath) or relpath.replace("\\", "/").startswith(".review-"):
        return "REVIEW_TEMP"
    first = _rel_parts(relpath)[:1]
    if first and first[0] == ".worktrees":
        return "WORKTREE_STORAGE"
    if cache_category_for(Path(relpath).name, is_dir=is_dir) or _rel_inside_named_cache_dir(relpath):
        return "CACHE"
    return "UNKNOWN"


def cache_category_for(name: str, *, is_dir: bool) -> str | None:
    if is_dir:
        return CACHE_DIR_NAMES.get(name)
    if name in CACHE_FILE_NAMES:
        return CACHE_FILE_NAMES[name]
    suffix = Path(name).suffix.lower()
    return CACHE_SUFFIXES.get(suffix)


def classify_worktree_hints(
    *,
    dirty: bool,
    detached: bool,
    upstream_status: str,
    ancestor_of_main: bool | None,
    unique_commits_possible: bool,
) -> list[str]:
    hints: list[str] = []
    if dirty:
        hints.append("DIRTY")
        hints.append("ACTIVE")
    if detached:
        hints.append("DETACHED")
    if upstream_status == "GONE":
        hints.append("UPSTREAM_GONE")
    if ancestor_of_main is True:
        hints.append("MERGED_OR_ANCESTOR")
    if unique_commits_possible:
        hints.append("UNIQUE_COMMITS_POSSIBLE")
        if "ACTIVE" not in hints:
            hints.append("ACTIVE")
    hints.append("REVIEW_REQUIRED")
    # Preserve order while uniquing.
    seen: set[str] = set()
    ordered: list[str] = []
    for hint in hints:
        if hint not in seen:
            seen.add(hint)
            ordered.append(hint)
    return ordered


def cursor_project_slug(repo_root: Path | str) -> str:
    """Derive Cursor's project directory slug from the path being represented.

    Windows-form input is parsed with ``PureWindowsPath`` even on POSIX hosts.
    POSIX-form input is parsed with ``PurePosixPath`` even on Windows hosts.
    Ambiguous forms (UNC, relative, mixed) return an empty slug so discovery
    fails closed instead of guessing a Cursor directory.
    """
    text = _represented_path_text(repo_root)
    kind = classify_path_syntax(text)
    if kind == "windows-drive":
        parsed = PureWindowsPath(_strip_win_extended_prefix(text))
        parts = parsed.parts
        if not parts:
            return ""
        drive = parts[0].rstrip("\\/")
        if len(drive) < 2 or drive[1] != ":" or not drive[0].isalpha():
            return ""
        return _slug_from_parts(parts[1:], drive_letter=drive[0])
    if kind == "posix":
        parsed = PurePosixPath(text)
        return _slug_from_parts(parsed.parts, drive_letter=None)
    return ""


def discover_cursor_project_dir(repo_root: Path) -> tuple[Path | None, str]:
    override = os.environ.get("IMP_CURSOR_PROJECT_DIR", "").strip()
    home_projects = Path.home() / ".cursor" / "projects"
    if override:
        candidate = Path(override).expanduser()
        try:
            resolved = candidate.resolve()
            resolved.relative_to(home_projects.resolve())
        except (OSError, ValueError):
            return None, "UNSUPPORTED_UNSAFE_PATH"
        if resolved.is_dir():
            return resolved, "OK"
        return None, "UNAVAILABLE"
    slug = cursor_project_slug(repo_root)
    if not slug or slug in {".", ".."} or "/" in slug or "\\" in slug:
        return None, "UNSUPPORTED"
    candidate = home_projects / slug
    try:
        candidate.relative_to(home_projects)
    except ValueError:
        return None, "UNSUPPORTED"
    try:
        if candidate.is_dir():
            return candidate, "OK"
    except OSError:
        return None, "UNAVAILABLE"
    return None, "UNAVAILABLE"


@dataclass
class ScanAccumulator:
    file_count: int = 0
    dir_count: int = 0
    physical_bytes: int = 0
    git_physical_bytes: int = 0
    unreadable: list[dict[str, str]] = field(default_factory=list)
    dir_sizes: dict[str, int] = field(default_factory=dict)
    file_sizes: list[tuple[int, str]] = field(default_factory=list)
    file_heap_limit: int = 50
    caches: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts_bytes: int = 0
    artifacts_paths: list[dict[str, Any]] = field(default_factory=list)
    temporary: list[dict[str, Any]] = field(default_factory=list)
    temporary_bytes: int = 0
    dependencies: list[dict[str, Any]] = field(default_factory=list)
    worktree_bytes: dict[str, int] = field(default_factory=dict)
    escaped_links: list[str] = field(default_factory=list)
    reclaimable_cache_bytes: int = 0

    def add_cache(self, category: str, relpath: str, size: int) -> None:
        row = self.caches.setdefault(category, {"category": category, "bytes": 0, "count": 0, "examples": []})
        row["bytes"] += size
        row["count"] += 1
        examples = row["examples"]
        if len(examples) < 8:
            examples.append(relpath)
        if cache_counts_toward_reclaimable(relpath):
            self.reclaimable_cache_bytes += size

    def consider_file(self, size: int, relpath: str) -> None:
        item = (size, relpath)
        if len(self.file_sizes) < self.file_heap_limit:
            heappush(self.file_sizes, item)
        elif size > self.file_sizes[0][0]:
            heapreplace(self.file_sizes, item)


class StorageAuditor:
    def __init__(
        self,
        *,
        git: ReadOnlyGit | None = None,
        progress: ProgressFn | None = None,
        top: int = 25,
        include_cursor: bool = False,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.git = git or ReadOnlyGit()
        self.progress = progress or (lambda _message: None)
        self.top = max(1, int(top))
        self.include_cursor = include_cursor
        self._now = now or time.monotonic
        self._last_progress = 0.0

    def _emit(self, message: str, *, force: bool = False) -> None:
        current = self._now()
        if force or current - self._last_progress >= 2.0:
            self.progress(message)
            self._last_progress = current

    def audit(self, start: Path, *, scan_root: Path | None = None) -> dict[str, Any]:
        start_path = Path(start).resolve()
        warnings: list[dict[str, Any]] = []
        git_root = self._git_toplevel(start_path)
        primary_root = self._primary_working_tree(git_root or start_path)
        root = Path(scan_root).resolve() if scan_root is not None else (primary_root or git_root or start_path)
        self._emit(f"resolved scan root {root}", force=True)

        repo = self._repository_summary(root, git_root=git_root or root, primary_root=primary_root)
        git_info = self._git_object_storage(root)
        porcelain = self._list_worktrees(root)
        worktree_rows = self._inspect_worktrees(porcelain, origin_main=repo.get("origin_main"))
        self._emit("scanning filesystem (read-only, no link follow)", force=True)
        scan = self._scan_filesystem(root, worktrees=worktree_rows)
        self._scan_external_worktrees(root, worktree_rows, scan)
        cursor = self._cursor_storage(primary_root or root) if self.include_cursor else {
            "status": "SKIPPED",
            "included": False,
            "reason": "pass --include-cursor to inspect this repository's Cursor project directory",
        }

        worktrees_payload = self._worktrees_payload(worktree_rows, scan)
        dependencies = self._dependencies_payload(scan)
        caches = self._caches_payload(scan)
        artifacts = self._artifacts_payload(scan)
        temporary = self._temporary_payload(scan, worktree_rows)
        largest = self._largest_paths(scan, root)
        repo["physical_bytes"] = scan.physical_bytes
        repo["file_count"] = scan.file_count
        repo["directory_count"] = scan.dir_count
        git_info["physical_bytes"] = scan.git_physical_bytes or git_info.get("physical_bytes", 0)

        warnings.extend(self._build_warnings(
            worktrees=worktrees_payload,
            dependencies=dependencies,
            caches=caches,
            artifacts=artifacts,
            temporary=temporary,
            cursor=cursor,
            git_info=git_info,
            largest=largest,
            unreadable=scan.unreadable,
        ))
        summary = self._summary(
            repo=repo,
            git_info=git_info,
            worktrees=worktrees_payload,
            dependencies=dependencies,
            caches=caches,
            artifacts=artifacts,
            temporary=temporary,
            cursor=cursor,
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "report_type": REPORT_TYPE,
            "generated_at": utc_now(),
            "advisory_notice": ADVISORY_NOTICE,
            "safety": {
                "read_only": True,
                "deletion_authority": False,
                "destructive_git_commands_run": False,
                "network_used": False,
                "hint_is_not_deletion_authority": True,
            },
            "repo": repo,
            "git": git_info,
            "worktrees": worktrees_payload,
            "dependencies": dependencies,
            "caches": caches,
            "artifacts": artifacts,
            "temporary": temporary,
            "cursor": cursor,
            "largest_paths": largest,
            "unreadable_paths": scan.unreadable,
            "warnings": warnings,
            "summary": summary,
        }

    def _git_toplevel(self, start: Path) -> Path | None:
        code, stdout, _stderr = self.git.text(["rev-parse", "--show-toplevel"], cwd=start)
        if code != 0 or not stdout:
            return None
        return Path(stdout).resolve()

    def _primary_working_tree(self, start: Path) -> Path | None:
        code, stdout, _stderr = self.git.text(["rev-parse", "--git-common-dir"], cwd=start)
        if code != 0 or not stdout:
            return start if start.is_dir() else None
        common = Path(stdout)
        if not common.is_absolute():
            common = (start / common)
        try:
            common = common.resolve()
        except OSError:
            return start
        if common.name == ".git":
            return common.parent
        return start

    def _repository_summary(self, root: Path, *, git_root: Path, primary_root: Path | None) -> dict[str, Any]:
        head_code, head, _ = self.git.text(["rev-parse", "HEAD"], cwd=git_root)
        branch_code, branch, _ = self.git.text(["rev-parse", "--abbrev-ref", "HEAD"], cwd=git_root)
        main_code, origin_main, _ = self.git.text(["rev-parse", "origin/main"], cwd=git_root)
        detached = branch_code == 0 and branch == "HEAD"
        return {
            "scan_root": str(root),
            "git_toplevel": str(git_root),
            "primary_working_tree": str(primary_root) if primary_root is not None else None,
            "head": head if head_code == 0 else None,
            "origin_main": origin_main if main_code == 0 else None,
            "branch": None if detached else (branch if branch_code == 0 else None),
            "detached": detached,
            "physical_bytes": 0,
            "file_count": 0,
            "directory_count": 0,
        }

    def _git_object_storage(self, root: Path) -> dict[str, Any]:
        code, stdout, stderr = self.git.text(["count-objects", "-v"], cwd=root)
        parsed = {
            "count": None,
            "size_kib": None,
            "in_pack": None,
            "packs": None,
            "size_pack_kib": None,
            "prune_packable": None,
            "garbage": None,
            "size_garbage_kib": None,
        }
        if code == 0:
            for line in stdout.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                key = key.strip()
                raw = value.strip().split()[0] if value.strip() else ""
                try:
                    number = int(raw)
                except ValueError:
                    continue
                if key == "count":
                    parsed["count"] = number
                elif key == "size":
                    parsed["size_kib"] = number
                elif key == "in-pack":
                    parsed["in_pack"] = number
                elif key == "packs":
                    parsed["packs"] = number
                elif key == "size-pack":
                    parsed["size_pack_kib"] = number
                elif key == "prune-packable":
                    parsed["prune_packable"] = number
                elif key == "garbage":
                    parsed["garbage"] = number
                elif key == "size-garbage":
                    parsed["size_garbage_kib"] = number
        loose_bytes = (parsed["size_kib"] or 0) * 1024
        packed_bytes = (parsed["size_pack_kib"] or 0) * 1024
        garbage_bytes = (parsed["size_garbage_kib"] or 0) * 1024
        return {
            "count_objects_ok": code == 0,
            "count_objects_error": None if code == 0 else (stderr or "count-objects failed"),
            "loose_object_count": parsed["count"],
            "loose_object_bytes": loose_bytes,
            "packed_object_count": parsed["in_pack"],
            "packed_object_bytes": packed_bytes,
            "pack_count": parsed["packs"],
            "garbage_count": parsed["garbage"],
            "garbage_bytes": garbage_bytes,
            "prune_packable": parsed["prune_packable"],
            "physical_bytes": 0,
            "destructive_maintenance": False,
        }

    def _list_worktrees(self, root: Path) -> list[WorktreePorcelain]:
        code, stdout, _stderr = self.git.text(["worktree", "list", "--porcelain"], cwd=root)
        if code != 0:
            return []
        return parse_worktree_porcelain(stdout)

    def _inspect_worktrees(
        self,
        porcelain: Sequence[WorktreePorcelain],
        *,
        origin_main: str | None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        total = len(porcelain)
        for index, record in enumerate(porcelain, start=1):
            path = Path(record.path)
            self._emit(f"inspecting worktree {index}/{total}: {_posix(path)}")
            rows.append(self._inspect_one_worktree(record, origin_main=origin_main))
        return rows

    def _inspect_one_worktree(self, record: WorktreePorcelain, *, origin_main: str | None) -> dict[str, Any]:
        path = Path(record.path)
        dirty = False
        tracked_modifications = 0
        untracked = 0
        status_error = None
        if path.is_dir():
            code, stdout, stderr = self.git.text(["status", "--porcelain=v1", "-unormal"], cwd=path)
            if code == 0:
                for line in stdout.splitlines():
                    if not line:
                        continue
                    if line.startswith("??"):
                        untracked += 1
                    else:
                        tracked_modifications += 1
                dirty = tracked_modifications > 0 or untracked > 0
            else:
                status_error = stderr or "git status failed"
        else:
            status_error = "worktree path missing"
        upstream_name, upstream_status = self._upstream_status(path)
        ahead = None
        behind = None
        ancestor = None
        unique_commits_possible = False
        if origin_main:
            code, stdout, _ = self.git.text(
                ["rev-list", "--left-right", "--count", f"{origin_main}...HEAD"],
                cwd=path,
            )
            if code == 0 and stdout:
                parts = stdout.split()
                if len(parts) >= 2:
                    try:
                        behind = int(parts[0])
                        ahead = int(parts[1])
                    except ValueError:
                        ahead = None
                        behind = None
            ancestor_code, _stdout, _stderr = self.git.text(
                ["merge-base", "--is-ancestor", "HEAD", origin_main],
                cwd=path,
            )
            if ancestor_code == 0:
                ancestor = True
            elif ancestor_code == 1:
                ancestor = False
                unique_commits_possible = True
        hints = classify_worktree_hints(
            dirty=dirty,
            detached=record.detached or record.branch is None,
            upstream_status=upstream_status,
            ancestor_of_main=ancestor,
            unique_commits_possible=unique_commits_possible,
        )
        return {
            "path": str(path),
            "head": record.head,
            "branch": None if record.detached else record.branch,
            "detached": bool(record.detached or record.branch is None),
            "upstream": upstream_name,
            "upstream_status": upstream_status,
            "dirty": dirty,
            "tracked_modifications": tracked_modifications,
            "untracked": untracked,
            "ahead_of_origin_main": ahead,
            "behind_origin_main": behind,
            "head_is_ancestor_of_origin_main": ancestor,
            "associated_pr": None,
            "pr_lookup": "skipped_no_network",
            "physical_bytes": 0,
            "has_venv": False,
            "has_node_modules": False,
            "has_caches_or_build": False,
            "hints": hints,
            "hint_is_not_deletion_authority": True,
            "status_error": status_error,
            "prunable_flag": record.prunable,
            "locked": record.locked,
        }

    def _upstream_status(self, worktree: Path) -> tuple[str | None, str]:
        if not worktree.is_dir():
            return None, "NONE"
        status_code, status_out, _ = self.git.text(
            ["status", "-sb", "--untracked-files=no"],
            cwd=worktree,
        )
        if status_code == 0 and status_out:
            header = status_out.splitlines()[0]
            if "[gone]" in header.lower():
                name = None
                if "..." in header:
                    name = header.split("...", 1)[1].split()[0]
                return name, "GONE"
            if "..." in header:
                name = header.split("...", 1)[1].split()[0]
                return name, "EXISTS"
        code, stdout, _ = self.git.text(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
            cwd=worktree,
        )
        if code != 0 or not stdout:
            return None, "NONE"
        name = stdout
        verify_code, _, _ = self.git.text(["rev-parse", "--verify", "--quiet", name], cwd=worktree)
        if verify_code != 0:
            alt = name if name.startswith("refs/") else f"refs/remotes/{name}"
            alt_code, _, _ = self.git.text(["show-ref", "--verify", "--quiet", alt], cwd=worktree)
            if alt_code != 0:
                return name, "GONE"
        return name, "EXISTS"

    def _scan_filesystem(self, root: Path, *, worktrees: Sequence[dict[str, Any]]) -> ScanAccumulator:
        acc = ScanAccumulator(file_heap_limit=max(50, self.top * 2))
        prefixes = self._worktree_prefixes(root, worktrees)
        self._walk(root, relative="", acc=acc, scan_root=root, prefixes=prefixes, inside_git=False)
        acc.git_physical_bytes = int(acc.dir_sizes.get(".git") or acc.git_physical_bytes)
        return acc

    def _worktree_prefixes(self, root: Path, worktrees: Sequence[dict[str, Any]]) -> list[tuple[str, str]]:
        items: list[tuple[str, str]] = []
        root_resolved = root.resolve()
        for row in worktrees:
            try:
                wt = Path(row["path"]).resolve()
                rel = str(wt.relative_to(root_resolved)).replace("\\", "/")
            except (OSError, ValueError):
                continue
            if rel == ".":
                rel = ""
            items.append((rel, str(wt)))
        items.sort(key=lambda item: len(item[0]), reverse=True)
        return items

    def _attribute_worktree(self, relpath: str, prefixes: Sequence[tuple[str, str]]) -> str | None:
        normalized = relpath.replace("\\", "/")
        for rel, identity in prefixes:
            if rel == "":
                return identity
            if normalized == rel or normalized.startswith(rel + "/"):
                return identity
        return None

    def _walk(
        self,
        path: Path,
        *,
        relative: str,
        acc: ScanAccumulator,
        scan_root: Path,
        prefixes: Sequence[tuple[str, str]],
        inside_git: bool,
    ) -> int:
        self._emit(f"scanning {_posix(relative or path.name or '.')}")
        total = 0
        try:
            iterator = os.scandir(path)
        except OSError as exc:
            acc.unreadable.append({"path": str(path), "error": exc.__class__.__name__})
            return 0
        try:
            entries = list(iterator)
        except OSError as exc:
            acc.unreadable.append({"path": str(path), "error": exc.__class__.__name__})
            return 0
        finally:
            iterator.close()

        acc.dir_count += 1
        for entry in entries:
            child_rel = entry.name if not relative else f"{relative}/{entry.name}"
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError as exc:
                acc.unreadable.append({"path": str(entry.path), "error": exc.__class__.__name__})
                continue
            kind = classify_link_kind(Path(entry.path), st)
            if kind != "PHYSICAL":
                self._record_link(entry, relative=child_rel, kind=kind, acc=acc, scan_root=scan_root)
                continue
            child_inside_git = inside_git or entry.name == ".git"
            if stat.S_ISDIR(st.st_mode):
                child_bytes = self._walk(
                    Path(entry.path),
                    relative=child_rel,
                    acc=acc,
                    scan_root=scan_root,
                    prefixes=prefixes,
                    inside_git=child_inside_git,
                )
                total += child_bytes
                acc.dir_sizes[child_rel] = child_bytes
                self._classify_directory(entry.name, child_rel, child_bytes, acc, path=Path(entry.path))
            elif stat.S_ISREG(st.st_mode):
                size = int(st.st_size)
                total += size
                acc.file_count += 1
                acc.consider_file(size, child_rel)
                if not child_inside_git:
                    owner = self._attribute_worktree(child_rel, prefixes)
                    if owner is not None:
                        acc.worktree_bytes[owner] = acc.worktree_bytes.get(owner, 0) + size
                if not _rel_inside_named_cache_dir(child_rel):
                    category = cache_category_for(entry.name, is_dir=False)
                    if category:
                        acc.add_cache(category, child_rel, size)
                if is_protected_relpath(child_rel) and not _rel_inside_protected_parent(child_rel):
                    acc.artifacts_bytes += size
            # Ignore sockets, FIFOs, and other non-regular entries.
        if relative == "":
            acc.physical_bytes = total
        return total

    def _record_link(
        self,
        entry: os.DirEntry[str],
        *,
        relative: str,
        kind: str,
        acc: ScanAccumulator,
        scan_root: Path,
    ) -> None:
        target = read_link_target(Path(entry.path))
        escaped = False
        if target:
            try:
                resolved = (Path(entry.path).parent / target).resolve()
                escaped = not path_is_within_root(resolved, scan_root)
            except OSError:
                escaped = True
            if escaped:
                acc.escaped_links.append(relative)
        record = {
            "path": relative,
            "kind": kind,
            "target": target,
            "physical_bytes": 0,
            "escaped_scan_root": escaped,
        }
        name = entry.name
        if name in {".venv", "venv"} or name == "node_modules" or is_venv_directory(Path(entry.path)):
            record["type"] = "node_modules" if name == "node_modules" else "venv"
            acc.dependencies.append(record)
        if is_temporary_relpath(relative):
            acc.temporary.append({**record, "bytes": 0, "is_git_worktree": False, "safe_review_hint": "REVIEW_REQUIRED"})

    def _classify_directory(
        self,
        name: str,
        relative: str,
        size: int,
        acc: ScanAccumulator,
        *,
        path: Path,
    ) -> None:
        if name in {".venv", "venv"} or is_venv_directory(path) or name == "node_modules":
            acc.dependencies.append(
                {
                    "path": relative,
                    "kind": "PHYSICAL",
                    "type": "node_modules" if name == "node_modules" else "venv",
                    "target": None,
                    "physical_bytes": size,
                    "escaped_scan_root": False,
                }
            )
        category = cache_category_for(name, is_dir=True)
        if category and not _rel_inside_named_cache_dir(relative):
            acc.add_cache(category, relative, size)
        if is_protected_relpath(relative) and not _rel_inside_protected_parent(relative):
            acc.artifacts_bytes += size
            acc.artifacts_paths.append(
                {
                    "path": relative,
                    "bytes": size,
                    "classification": "PROTECTED_OR_REVIEW_REQUIRED",
                }
            )
        if is_temporary_relpath(relative):
            acc.temporary_bytes += size
            acc.temporary.append(
                {
                    "path": relative,
                    "bytes": size,
                    "kind": "PHYSICAL",
                    "is_git_worktree": False,
                    "safe_review_hint": "REVIEW_REQUIRED",
                    "classification": "REPORT_ONLY",
                }
            )

    def _scan_external_worktrees(
        self,
        root: Path,
        worktrees: Sequence[dict[str, Any]],
        acc: ScanAccumulator,
    ) -> None:
        root_resolved = root.resolve()
        for row in worktrees:
            path = Path(row["path"])
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if path_is_within_root(resolved, root_resolved):
                continue
            if not path.is_dir():
                continue
            self._emit(f"scanning external worktree {_posix(path)}", force=True)
            nested = ScanAccumulator()
            self._walk(
                path,
                relative="",
                acc=nested,
                scan_root=path,
                prefixes=[("", str(resolved if path.exists() else path))],
                inside_git=False,
            )
            acc.worktree_bytes[str(path)] = nested.physical_bytes
            acc.caches = _merge_cache_maps(acc.caches, nested.caches)
            acc.reclaimable_cache_bytes += nested.reclaimable_cache_bytes
            acc.dependencies.extend(nested.dependencies)
            acc.temporary.extend(nested.temporary)
            acc.unreadable.extend(nested.unreadable)

    def _worktrees_payload(
        self,
        rows: Sequence[dict[str, Any]],
        acc: ScanAccumulator,
    ) -> dict[str, Any]:
        enriched: list[dict[str, Any]] = []
        gone = 0
        dirty = 0
        ancestor = 0
        detached = 0
        total_bytes = 0
        for row in rows:
            item = dict(row)
            identity = str(Path(row["path"]))
            # Match scan attribution keys which use resolved paths when possible.
            size = acc.worktree_bytes.get(identity)
            if size is None:
                try:
                    size = acc.worktree_bytes.get(str(Path(identity).resolve()), 0)
                except OSError:
                    size = 0
            item["physical_bytes"] = int(size or 0)
            item["physical_bytes_human"] = format_bytes(item["physical_bytes"])
            rel_markers = self._worktree_markers(Path(row["path"]))
            item.update(rel_markers)
            if item["upstream_status"] == "GONE":
                gone += 1
            if item["dirty"]:
                dirty += 1
            if item.get("head_is_ancestor_of_origin_main") is True:
                ancestor += 1
            if item["detached"]:
                detached += 1
            total_bytes += item["physical_bytes"]
            enriched.append(item)
        return {
            "count": len(enriched),
            "gone_upstream_count": gone,
            "dirty_count": dirty,
            "ancestor_of_main_count": ancestor,
            "detached_count": detached,
            "total_physical_bytes": total_bytes,
            "hint_is_not_deletion_authority": True,
            "items": enriched,
        }

    def _worktree_markers(self, path: Path) -> dict[str, bool]:
        has_venv = False
        has_node = False
        has_caches = False
        candidates = [
            path / ".venv",
            path / "venv",
            path / "projects" / "integrated-market-platform" / ".venv",
            path / "node_modules",
            path / "projects" / "integrated-market-platform" / "ui" / "node_modules",
            path / "projects" / "integrated-market-platform" / ".pytest_cache",
            path / "projects" / "integrated-market-platform" / ".mypy_cache",
            path / "projects" / "integrated-market-platform" / ".ruff_cache",
        ]
        for candidate in candidates:
            try:
                exists = candidate.exists() or candidate.is_symlink()
            except OSError:
                continue
            if not exists:
                continue
            name = candidate.name
            if name in {".venv", "venv"}:
                has_venv = True
            elif name == "node_modules":
                has_node = True
            else:
                has_caches = True
        return {
            "has_venv": has_venv,
            "has_node_modules": has_node,
            "has_caches_or_build": has_caches,
        }

    def _dependencies_payload(self, acc: ScanAccumulator) -> dict[str, Any]:
        physical_venv = 0
        linked_venv = 0
        physical_venv_bytes = 0
        physical_node = 0
        linked_node = 0
        physical_node_bytes = 0
        physical_targets: set[str] = set()
        items: list[dict[str, Any]] = []
        for row in acc.dependencies:
            item = dict(row)
            kind = item.get("kind")
            dtype = item.get("type")
            if dtype == "venv":
                if kind == "PHYSICAL":
                    identity = item.get("path") or ""
                    if identity not in physical_targets:
                        physical_targets.add(identity)
                        physical_venv += 1
                        physical_venv_bytes += int(item.get("physical_bytes") or 0)
                else:
                    linked_venv += 1
            elif dtype == "node_modules":
                if kind == "PHYSICAL":
                    physical_node += 1
                    physical_node_bytes += int(item.get("physical_bytes") or 0)
                else:
                    linked_node += 1
            items.append(item)
        return {
            "physical_venv_count": physical_venv,
            "linked_venv_count": linked_venv,
            "physical_venv_bytes": physical_venv_bytes,
            "physical_node_modules_count": physical_node,
            "linked_node_modules_count": linked_node,
            "physical_node_modules_bytes": physical_node_bytes,
            "note": "Linked .venv/node_modules paths are not counted as physical copies.",
            "items": items,
        }

    def _caches_payload(self, acc: ScanAccumulator) -> dict[str, Any]:
        categories = sorted(acc.caches.values(), key=lambda row: int(row.get("bytes") or 0), reverse=True)
        total = sum(int(row.get("bytes") or 0) for row in categories)
        return {
            "total_bytes": total,
            "reclaimable_bytes": int(acc.reclaimable_cache_bytes),
            "categories": categories,
            "note": "Caches inside .venv/venv/node_modules or protected evidence are observed but excluded from conservative reclaimable estimates.",
        }

    def _artifacts_payload(self, acc: ScanAccumulator) -> dict[str, Any]:
        return {
            "total_bytes": acc.artifacts_bytes,
            "classification": "PROTECTED_OR_REVIEW_REQUIRED",
            "deletion_authority": False,
            "items": acc.artifacts_paths[:50],
            "note": "Evidence, receipts, corpora, and historical artifacts are measured only. Large does not mean disposable.",
        }

    def _temporary_payload(
        self,
        acc: ScanAccumulator,
        worktrees: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        worktree_names = {
            Path(row["path"]).name.lower()
            for row in worktrees
            if row.get("path")
        }
        items = []
        for row in acc.temporary:
            item = dict(row)
            name = Path(str(item.get("path") or "")).name.lower()
            item["is_git_worktree"] = name in worktree_names
            item["associated_with_current_branch"] = False
            items.append(item)
        return {
            "total_bytes": acc.temporary_bytes,
            "count": len(items),
            "items": items,
            "note": "Review/temp paths are reported only. Presence is not deletion authority.",
        }

    def _largest_paths(self, acc: ScanAccumulator, root: Path) -> list[dict[str, Any]]:
        directories = [
            {"path": path, "kind": "directory", "bytes": size}
            for path, size in acc.dir_sizes.items()
        ]
        files = [
            {"path": path, "kind": "file", "bytes": size}
            for size, path in acc.file_sizes
        ]
        top_dirs = nlargest(self.top, directories, key=lambda row: int(row["bytes"]))
        top_files = nlargest(self.top, files, key=lambda row: int(row["bytes"]))
        combined = nlargest(self.top, directories + files, key=lambda row: int(row["bytes"]))
        for row in (*top_dirs, *top_files, *combined):
            row["bytes_human"] = format_bytes(int(row["bytes"]))
            row["classification"] = _largest_path_class(str(row["path"]), row["kind"] == "directory")
        return combined

    def _cursor_storage(self, repo_root: Path) -> dict[str, Any]:
        path, status = discover_cursor_project_dir(repo_root)
        if path is None:
            return {
                "status": status,
                "included": True,
                "path": None,
                "total_bytes": 0,
                "categories": [],
                "note": "Project-scoped Cursor storage was not inspected because it could not be located safely.",
            }
        acc = ScanAccumulator()
        self._walk(
            path,
            relative="",
            acc=acc,
            scan_root=path,
            prefixes=[("", str(path))],
            inside_git=False,
        )
        categories: dict[str, dict[str, Any]] = {}
        for rel, size in acc.dir_sizes.items():
            top = rel.split("/", 1)[0]
            bucket = CURSOR_CATEGORY_NAMES.get(top, "temporary_project_state")
            row = categories.setdefault(bucket, {"category": bucket, "bytes": 0, "paths": []})
            if "/" not in rel.replace("\\", "/"):
                row["bytes"] += size
                row["paths"].append(rel)
        return {
            "status": "OK",
            "included": True,
            "path": str(path),
            "total_bytes": acc.physical_bytes,
            "file_count": acc.file_count,
            "categories": sorted(categories.values(), key=lambda row: int(row["bytes"]), reverse=True),
            "note": "Sizes and path classifications only. Transcript contents are not printed.",
        }

    def _build_warnings(
        self,
        *,
        worktrees: dict[str, Any],
        dependencies: dict[str, Any],
        caches: dict[str, Any],
        artifacts: dict[str, Any],
        temporary: dict[str, Any],
        cursor: dict[str, Any],
        git_info: dict[str, Any],
        largest: Sequence[dict[str, Any]],
        unreadable: Sequence[dict[str, str]],
    ) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        count = int(worktrees.get("count") or 0)
        if count >= WORKTREE_COUNT_HIGH:
            warnings.append(
                {
                    "code": "WORKTREE_COUNT_HIGH",
                    "message": f"{count} Git worktrees are registered (threshold {WORKTREE_COUNT_HIGH}).",
                    "count": count,
                }
            )
        gone = int(worktrees.get("gone_upstream_count") or 0)
        if gone:
            warnings.append(
                {
                    "code": "GONE_UPSTREAM_WORKTREES_PRESENT",
                    "message": f"{gone} worktree(s) have a configured upstream that is gone. This is not deletion authority.",
                    "count": gone,
                }
            )
        dirty = int(worktrees.get("dirty_count") or 0)
        ancestor = int(worktrees.get("ancestor_of_main_count") or 0)
        if dirty:
            warnings.append(
                {
                    "code": "DIRTY_STALE_WORKTREES_PRESENT",
                    "message": (
                        f"{dirty} dirty worktree(s) exist; {ancestor} HEAD(s) are already ancestors of origin/main. "
                        "Dirty trees are never classified as removable."
                    ),
                    "count": dirty,
                }
            )
        physical_venv = int(dependencies.get("physical_venv_count") or 0)
        if physical_venv > 1:
            warnings.append(
                {
                    "code": "PHYSICAL_VENV_DUPLICATES",
                    "message": f"{physical_venv} physically stored virtualenvs were found.",
                    "count": physical_venv,
                }
            )
        physical_node = int(dependencies.get("physical_node_modules_count") or 0)
        if physical_node > 1:
            warnings.append(
                {
                    "code": "PHYSICAL_NODE_MODULES_DUPLICATES",
                    "message": f"{physical_node} physically stored node_modules directories were found.",
                    "count": physical_node,
                }
            )
        temp_bytes = int(temporary.get("total_bytes") or 0)
        if temp_bytes >= REVIEW_TEMP_HIGH_BYTES:
            warnings.append(
                {
                    "code": "REVIEW_TEMP_STORAGE_HIGH",
                    "message": f"Review/temp storage is {format_bytes(temp_bytes)}.",
                    "bytes": temp_bytes,
                }
            )
        cursor_bytes = int(cursor.get("total_bytes") or 0)
        if cursor.get("status") == "OK" and cursor_bytes >= CURSOR_PROJECT_HIGH_BYTES:
            warnings.append(
                {
                    "code": "CURSOR_PROJECT_STORAGE_HIGH",
                    "message": f"Cursor project storage is {format_bytes(cursor_bytes)}.",
                    "bytes": cursor_bytes,
                }
            )
        git_bytes = int(git_info.get("physical_bytes") or 0)
        packed = int(git_info.get("packed_object_bytes") or 0)
        if max(git_bytes, packed) >= GIT_OBJECT_HIGH_BYTES:
            warnings.append(
                {
                    "code": "GIT_OBJECT_STORAGE_HIGH",
                    "message": f"Git object storage is {format_bytes(max(git_bytes, packed))}.",
                    "bytes": max(git_bytes, packed),
                }
            )
        artifact_bytes = int(artifacts.get("total_bytes") or 0)
        if artifact_bytes >= PROTECTED_EVIDENCE_HIGH_BYTES:
            warnings.append(
                {
                    "code": "PROTECTED_EVIDENCE_LARGE",
                    "message": (
                        f"Protected artifact/evidence storage is {format_bytes(artifact_bytes)}. "
                        "Large evidence is not reclaimable."
                    ),
                    "bytes": artifact_bytes,
                }
            )
        for row in largest[:5]:
            if row.get("classification") == "UNKNOWN" and int(row.get("bytes") or 0) >= UNKNOWN_LARGE_PATH_BYTES:
                warnings.append(
                    {
                        "code": "UNKNOWN_LARGE_PATH",
                        "message": f"{row['path']} is {row.get('bytes_human')} and is not a known cache/evidence class.",
                        "path": row["path"],
                        "bytes": row["bytes"],
                    }
                )
                break
        if unreadable:
            warnings.append(
                {
                    "code": "UNREADABLE_PATHS_PRESENT",
                    "message": f"{len(unreadable)} path(s) could not be read (permission or filesystem errors).",
                    "count": len(unreadable),
                }
            )
        return warnings

    def _summary(
        self,
        *,
        repo: dict[str, Any],
        git_info: dict[str, Any],
        worktrees: dict[str, Any],
        dependencies: dict[str, Any],
        caches: dict[str, Any],
        artifacts: dict[str, Any],
        temporary: dict[str, Any],
        cursor: dict[str, Any],
    ) -> dict[str, Any]:
        cache_bytes = int(caches.get("total_bytes") or 0)
        reclaimable = int(caches.get("reclaimable_bytes") if caches.get("reclaimable_bytes") is not None else cache_bytes)
        return {
            "total_project_physical_bytes": int(repo.get("physical_bytes") or 0),
            "git_physical_bytes": int(git_info.get("physical_bytes") or 0),
            "worktree_count": int(worktrees.get("count") or 0),
            "total_worktree_physical_bytes": int(worktrees.get("total_physical_bytes") or 0),
            "worktrees_with_gone_upstream": int(worktrees.get("gone_upstream_count") or 0),
            "dirty_worktrees": int(worktrees.get("dirty_count") or 0),
            "worktrees_head_on_main": int(worktrees.get("ancestor_of_main_count") or 0),
            "physical_venv_count": int(dependencies.get("physical_venv_count") or 0),
            "physical_venv_bytes": int(dependencies.get("physical_venv_bytes") or 0),
            "linked_venv_count": int(dependencies.get("linked_venv_count") or 0),
            "physical_node_modules_count": int(dependencies.get("physical_node_modules_count") or 0),
            "physical_node_modules_bytes": int(dependencies.get("physical_node_modules_bytes") or 0),
            "cache_total_bytes": cache_bytes,
            "review_temp_total_bytes": int(temporary.get("total_bytes") or 0),
            "protected_artifact_evidence_bytes": int(artifacts.get("total_bytes") or 0),
            "cursor_project_total_bytes": int(cursor.get("total_bytes") or 0) if cursor.get("status") == "OK" else None,
            "estimated_reviewable_reclaimable_bytes": reclaimable,
            "reclaimable_basis": "CONSERVATIVE_CACHES_ONLY",
            "reclaimable_exclusions": [
                "worktrees",
                "dirty trees",
                "gone upstream",
                "merged/ancestor HEAD",
                "unique commits uncertain",
                "protected evidence",
                "review/temp directories",
                "physical venvs",
                "node_modules",
                "caches inside venv/node_modules/protected trees",
            ],
            "totals_overlap": True,
            "totals_overlap_note": (
                "Project, .worktrees, caches, dependencies, and protected evidence "
                "may overlap; do not arithmetically sum section totals."
            ),
            "advisory_notice": ADVISORY_NOTICE,
        }


def _merge_cache_maps(
    left: dict[str, dict[str, Any]],
    right: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged = {key: dict(value) for key, value in left.items()}
    for key, value in right.items():
        row = merged.setdefault(key, {"category": key, "bytes": 0, "count": 0, "examples": []})
        row["bytes"] += int(value.get("bytes") or 0)
        row["count"] += int(value.get("count") or 0)
        examples = list(row.get("examples") or [])
        for example in value.get("examples") or []:
            if len(examples) >= 8:
                break
            examples.append(example)
        row["examples"] = examples
    return merged


def render_text_report(report: dict[str, Any]) -> str:
    repo = report.get("repo", {})
    git_info = report.get("git", {})
    worktrees = report.get("worktrees", {})
    dependencies = report.get("dependencies", {})
    caches = report.get("caches", {})
    artifacts = report.get("artifacts", {})
    temporary = report.get("temporary", {})
    cursor = report.get("cursor", {})
    largest = report.get("largest_paths", [])
    warnings = report.get("warnings", [])
    summary = report.get("summary", {})
    lines = [
        "IMP STORAGE AUDIT",
        "-----------------",
        ADVISORY_NOTICE,
        "",
        "Repo",
        f"  scan_root: {repo.get('scan_root')}",
        f"  HEAD: {repo.get('head')}",
        f"  origin/main: {repo.get('origin_main')}",
        f"  branch: {repo.get('branch') or ('detached' if repo.get('detached') else 'unknown')}",
        f"  physical: {format_bytes(int(repo.get('physical_bytes') or 0))}  files={repo.get('file_count')}  dirs={repo.get('directory_count')}",
        "",
        "Git",
        f"  .git physical: {format_bytes(int(git_info.get('physical_bytes') or 0))}",
        f"  loose: count={git_info.get('loose_object_count')} size={format_bytes(int(git_info.get('loose_object_bytes') or 0))}",
        f"  packed: count={git_info.get('packed_object_count')} size={format_bytes(int(git_info.get('packed_object_bytes') or 0))} packs={git_info.get('pack_count')}",
        f"  garbage: count={git_info.get('garbage_count')} size={format_bytes(int(git_info.get('garbage_bytes') or 0))} prune-packable={git_info.get('prune_packable')}",
        "",
        "Worktrees",
        (
            f"  count={worktrees.get('count')}  dirty={worktrees.get('dirty_count')}  "
            f"gone_upstream={worktrees.get('gone_upstream_count')}  "
            f"ancestor_of_main={worktrees.get('ancestor_of_main_count')}  "
            f"physical={format_bytes(int(worktrees.get('total_physical_bytes') or 0))}"
        ),
        "  A hint is not deletion authority. Dirty worktrees are never removable.",
    ]
    for item in (worktrees.get("items") or [])[:15]:
        hints = ",".join(item.get("hints") or [])
        lines.append(
            f"  - {item.get('path')} head={(item.get('head') or '')[:12]} "
            f"{'dirty' if item.get('dirty') else 'clean'} "
            f"upstream={item.get('upstream_status')} "
            f"{format_bytes(int(item.get('physical_bytes') or 0))} [{hints}]"
        )
    if int(worktrees.get("count") or 0) > 15:
        lines.append(f"  ... {int(worktrees['count']) - 15} more worktrees (see --json)")
    lines.extend(
        [
            "",
            "Dependencies",
            (
                f"  physical .venv: {dependencies.get('physical_venv_count')} "
                f"({format_bytes(int(dependencies.get('physical_venv_bytes') or 0))})  "
                f"linked .venv: {dependencies.get('linked_venv_count')}"
            ),
            (
                f"  physical node_modules: {dependencies.get('physical_node_modules_count')} "
                f"({format_bytes(int(dependencies.get('physical_node_modules_bytes') or 0))})  "
                f"linked node_modules: {dependencies.get('linked_node_modules_count')}"
            ),
            "",
            "Caches",
            f"  total: {format_bytes(int(caches.get('total_bytes') or 0))}",
        ]
    )
    for row in (caches.get("categories") or [])[:8]:
        lines.append(f"  - {row.get('category')}: {format_bytes(int(row.get('bytes') or 0))} (n={row.get('count')})")
    lines.extend(
        [
            "",
            "Artifacts/evidence",
            (
                f"  {format_bytes(int(artifacts.get('total_bytes') or 0))}  "
                f"classification={artifacts.get('classification')}  (not reclaimable)"
            ),
            "",
            "Review/temp",
            f"  {format_bytes(int(temporary.get('total_bytes') or 0))}  count={temporary.get('count')}  (report only)",
            "",
            "Cursor project storage",
        ]
    )
    if cursor.get("status") == "OK":
        lines.append(f"  {cursor.get('path')}  {format_bytes(int(cursor.get('total_bytes') or 0))}")
    else:
        lines.append(f"  status={cursor.get('status')}  {cursor.get('reason') or cursor.get('note') or ''}")
    lines.extend(["", "Largest consumers"])
    for row in largest[:10]:
        lines.append(f"  {format_bytes(int(row.get('bytes') or 0)):>12}  {row.get('kind')}  {row.get('path')}  ({row.get('classification')})")
    lines.extend(["", "Warnings"])
    if not warnings:
        lines.append("  none")
    for warning in warnings:
        lines.append(f"  {warning.get('code')}: {warning.get('message')}")
    lines.extend(
        [
            "",
            "Summary",
            f"  project: {format_bytes(int(summary.get('total_project_physical_bytes') or 0))}",
            f"  .git: {format_bytes(int(summary.get('git_physical_bytes') or 0))}",
            f"  worktrees: {summary.get('worktree_count')} / {format_bytes(int(summary.get('total_worktree_physical_bytes') or 0))}",
            f"  caches: {format_bytes(int(summary.get('cache_total_bytes') or 0))}",
            f"  conservative reclaimable (caches only): {format_bytes(int(summary.get('estimated_reviewable_reclaimable_bytes') or 0))}",
            "  Section totals may overlap (project / .worktrees / caches / dependencies / protected evidence); do not arithmetically sum them.",
            f"  {ADVISORY_NOTICE}",
        ]
    )
    return "\n".join(lines) + "\n"


def default_progress(message: str) -> None:
    print(f"[storage-audit] {message}", file=sys.stderr, flush=True)


def run_audit(
    *,
    start: Path,
    scan_root: Path | None = None,
    top: int = 25,
    include_cursor: bool = False,
    git: ReadOnlyGit | None = None,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    auditor = StorageAuditor(
        git=git,
        progress=progress,
        top=top,
        include_cursor=include_cursor,
    )
    return auditor.audit(start, scan_root=scan_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only IMP storage audit. Output is advisory and is not deletion authority."
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON on stdout")
    parser.add_argument("--top", type=int, default=25, help="Largest-path rank count (default 25)")
    parser.add_argument(
        "--include-cursor",
        action="store_true",
        help="Optionally inspect this repository's project-scoped Cursor storage (sizes only)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Override scan/git root (tests and explicit local roots only)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress on stderr")
    return parser


def run_cli(argv: Sequence[str] | None = None, *, repository_root: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    start = Path(args.root).resolve() if args.root is not None else (
        Path(repository_root).resolve() if repository_root is not None else Path(__file__).resolve().parents[1]
    )
    if args.top < 1:
        print("--top must be >= 1", file=sys.stderr)
        return 2
    progress = (lambda _message: None) if args.quiet else default_progress
    try:
        report = run_audit(
            start=start,
            scan_root=Path(args.root).resolve() if args.root is not None else None,
            top=args.top,
            include_cursor=args.include_cursor,
            progress=progress,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_text_report(report))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main())
