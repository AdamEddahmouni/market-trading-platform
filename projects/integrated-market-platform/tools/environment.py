"""Portable IMP developer environment discovery and bootstrap helpers."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from market_platform_foundation.git_ref import repo_root as _git_repo_root
except ModuleNotFoundError:  # pragma: no cover - direct script execution.
    _git_repo_root = None  # type: ignore[assignment]

HARD_PYTHON_VERSION = (3, 11)
VENV_DIRNAME = ".venv"
IMP_PYTHON_ENV = "IMP_PYTHON"
IMP_PROJECT_RELATIVE = Path("projects") / "integrated-market-platform"


@dataclass(frozen=True, slots=True)
class WorktreeInfo:
    worktree_root: Path
    git_metadata_dir: Path
    is_linked_worktree: bool
    branch: str


@dataclass(frozen=True, slots=True)
class PythonResolution:
    executable: Path
    source: str
    supported: bool
    environment_root: Path | None


def _python_version_tuple(version: str) -> tuple[int, int]:
    try:
        major, minor = (int(part) for part in version.split(".")[:2])
    except (TypeError, ValueError):
        return (0, 0)
    return major, minor


def python_supported(version: str | None = None) -> bool:
    value = version or platform.python_version()
    return _python_version_tuple(value) >= HARD_PYTHON_VERSION


def _venv_python(environment_root: Path) -> Path | None:
    if os.name == "nt":
        candidate = environment_root / "Scripts" / "python.exe"
    else:
        candidate = environment_root / "bin" / "python"
    return candidate if candidate.is_file() else None


def _read_gitdir_pointer(git_file: Path) -> Path | None:
    try:
        raw = git_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw.startswith("gitdir:"):
        return None
    target = raw[len("gitdir:") :].strip()
    if not target:
        return None
    git_dir = Path(target)
    if not git_dir.is_absolute():
        git_dir = (git_file.parent / git_dir).resolve()
    return git_dir if git_dir.is_dir() else None


def _locate_git(start: Path) -> tuple[Path, Path, bool] | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for parent in [current, *current.parents]:
        marker = parent / ".git"
        if marker.is_dir():
            return parent, marker, False
        if marker.is_file():
            git_dir = _read_gitdir_pointer(marker)
            if git_dir is not None:
                return parent, git_dir, True
            return None
    return None


def _branch_name(worktree_root: Path, git_metadata_dir: Path) -> str:
    head_path = git_metadata_dir / "HEAD"
    try:
        head = head_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    if head.startswith("ref: "):
        return head[5:].strip().removeprefix("refs/heads/") or "unknown"
    return head[:12] if head else "unknown"


def detect_worktree(start: Path | None = None) -> WorktreeInfo | None:
    located = _locate_git(start or Path(__file__).resolve())
    if located is None:
        return None
    worktree_root, git_metadata_dir, is_linked = located
    return WorktreeInfo(
        worktree_root=worktree_root.resolve(),
        git_metadata_dir=git_metadata_dir.resolve(),
        is_linked_worktree=is_linked,
        branch=_branch_name(worktree_root, git_metadata_dir),
    )


def imp_project_root(start: Path | None = None) -> Path:
    anchor = Path(__file__).resolve().parent.parent
    start_path = (start or anchor).resolve()
    if start_path.is_file():
        start_path = start_path.parent
    if (start_path / "phase0-dependency-lock.json").is_file() and (start_path / "src").is_dir():
        return start_path
    if _git_repo_root is not None:
        try:
            git_root = _git_repo_root(start_path)
        except FileNotFoundError:
            git_root = None
        if git_root is not None:
            embedded = git_root / IMP_PROJECT_RELATIVE
            if (embedded / "phase0-dependency-lock.json").is_file():
                return embedded.resolve()
            return git_root
    located = _locate_git(start_path)
    if located is not None:
        worktree_root, _, _ = located
        embedded = worktree_root / IMP_PROJECT_RELATIVE
        if (embedded / "phase0-dependency-lock.json").is_file():
            return embedded.resolve()
        return worktree_root.resolve()
    return anchor.resolve()


def _configured_python() -> Path | None:
    configured = os.environ.get(IMP_PYTHON_ENV, "").strip()
    if not configured:
        return None
    candidate = Path(configured)
    return candidate if candidate.is_file() else None


def _local_environment_root(project_root: Path) -> Path | None:
    local = project_root / VENV_DIRNAME
    if _venv_python(local) is not None:
        return local.resolve()
    return None


def _git_worktree_roots(monorepo_root: Path) -> tuple[Path, ...]:
    completed = subprocess.run(
        ["git", "-C", str(monorepo_root), "worktree", "list", "--porcelain"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ()
    roots: list[Path] = []
    for line in completed.stdout.splitlines():
        if line.startswith("worktree "):
            roots.append(Path(line[len("worktree ") :].strip()).resolve())
    return tuple(roots)


def _shared_environment_candidates(project_root: Path) -> tuple[Path, ...]:
    candidates: list[Path] = []
    local_root = project_root / VENV_DIRNAME
    if local_root.exists():
        candidates.append(local_root.resolve())

    worktree = detect_worktree(project_root)
    if worktree is not None:
        for root in _git_worktree_roots(worktree.worktree_root):
            candidate_root = root / IMP_PROJECT_RELATIVE / VENV_DIRNAME
            if candidate_root.exists():
                resolved = candidate_root.resolve()
                if resolved not in candidates:
                    candidates.append(resolved)

    return tuple(candidates)


def resolve_python(project_root: Path | None = None) -> PythonResolution:
    requested = Path(project_root).resolve() if project_root is not None else None
    root = requested if requested is not None else imp_project_root()
    configured = _configured_python()
    if configured is not None:
        return PythonResolution(
            executable=configured.resolve(),
            source=f"{IMP_PYTHON_ENV}",
            supported=python_supported(_python_version_from_executable(configured)),
            environment_root=_environment_root_for_executable(configured),
        )

    local_root = _local_environment_root(root)
    if local_root is not None:
        executable = _venv_python(local_root)
        assert executable is not None
        return PythonResolution(
            executable=executable.resolve(),
            source="local_venv",
            supported=python_supported(_python_version_from_executable(executable)),
            environment_root=local_root,
        )

    for environment_root in _shared_environment_candidates(root):
        if environment_root.resolve() == (root / VENV_DIRNAME).resolve():
            continue
        executable = _venv_python(environment_root)
        if executable is None:
            continue
        return PythonResolution(
            executable=executable.resolve(),
            source="shared_worktree_venv",
            supported=python_supported(_python_version_from_executable(executable)),
            environment_root=environment_root,
        )

    current = Path(sys.executable).resolve()
    return PythonResolution(
        executable=current,
        source="current_interpreter",
        supported=python_supported(platform.python_version()),
        environment_root=None,
    )


def _python_version_from_executable(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "-c", "import platform; print(platform.python_version())"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return platform.python_version()
    return completed.stdout.strip() or platform.python_version()


def _environment_root_for_executable(executable: Path) -> Path | None:
    resolved = executable.resolve()
    if resolved.parent.name == "Scripts" and resolved.parent.parent.name == VENV_DIRNAME:
        return resolved.parent.parent
    if resolved.parent.name == "bin" and resolved.parent.parent.name == VENV_DIRNAME:
        return resolved.parent.parent
    return None


def timezone_ready(python_executable: Path | None = None) -> tuple[bool, str]:
    executable = python_executable or Path(sys.executable)
    completed = subprocess.run(
        [
            str(executable),
            "-c",
            "from zoneinfo import ZoneInfo; ZoneInfo('America/New_York'); print('ok')",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "timezone data unavailable").strip()
        return False, detail
    return True, "America/New_York available"


def _is_reparse_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name != "nt" or not path.exists():
        return False
    import stat

    return bool(getattr(os.lstat(path), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def link_local_venv(project_root: Path | None = None, *, force: bool = False) -> dict[str, Any]:
    requested = Path(project_root).resolve() if project_root is not None else None
    root = requested if requested is not None else imp_project_root()
    target_link = root / VENV_DIRNAME
    resolution = resolve_python(root)
    if resolution.environment_root is None:
        raise RuntimeError(
            "no canonical IMP virtual environment found; create one in the primary checkout "
            f"under {IMP_PROJECT_RELATIVE / VENV_DIRNAME} or set {IMP_PYTHON_ENV}"
        )
    target = resolution.environment_root.resolve()
    if target_link.exists() or target_link.is_symlink():
        if target_link.is_dir() and not _is_reparse_link(target_link):
            raise RuntimeError(f"{target_link} is a real directory; remove it manually")
        if not force:
            if target_link.resolve() == target:
                return {
                    "status": "unchanged",
                    "link": str(target_link),
                    "target": str(target),
                }
            raise RuntimeError(
                f"{target_link} already exists and does not match the canonical environment"
            )
        if target_link.is_symlink() or target_link.is_file():
            target_link.unlink()
        elif target_link.is_dir() and _is_reparse_link(target_link):
            target_link.rmdir()

    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target_link), str(target)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "failed to create junction")
    else:
        os.symlink(target, target_link, target_is_directory=True)

    return {
        "status": "linked",
        "link": str(target_link),
        "target": str(target),
        "mechanism": "junction" if os.name == "nt" else "symlink",
    }


def build_environment_report(project_root: Path | None = None) -> dict[str, Any]:
    requested = Path(project_root).resolve() if project_root is not None else None
    root = requested if requested is not None else imp_project_root()
    worktree = detect_worktree(root)
    resolution = resolve_python(root)
    tz_ok, tz_detail = timezone_ready(resolution.executable)
    local_exists = (root / VENV_DIRNAME).exists()
    shared_candidates = [
        str(path)
        for path in _shared_environment_candidates(root)
        if path.resolve() != (root / VENV_DIRNAME).resolve()
    ]
    node = shutil.which("node")
    npm = shutil.which("npm")
    return {
        "imp_project_root": str(root),
        "worktree": None
        if worktree is None
        else {
            "root": str(worktree.worktree_root),
            "git_metadata_dir": str(worktree.git_metadata_dir),
            "is_linked_worktree": worktree.is_linked_worktree,
            "branch": worktree.branch,
        },
        "python": {
            "current_executable": sys.executable,
            "current_version": platform.python_version(),
            "resolved_executable": str(resolution.executable),
            "resolved_version": _python_version_from_executable(resolution.executable),
            "resolution_source": resolution.source,
            "supported": resolution.supported,
        },
        "environment": {
            "local_venv_present": local_exists,
            "environment_root": None
            if resolution.environment_root is None
            else str(resolution.environment_root),
            "shared_candidates": shared_candidates,
        },
        "timezone": {"ready": tz_ok, "detail": tz_detail},
        "tools": {
            "git_available": shutil.which("git") is not None,
            "node_available": node is not None,
            "npm_available": npm is not None,
        },
        "next_commands": _next_commands(root, resolution, tz_ok, local_exists),
    }


def _next_commands(
    root: Path,
    resolution: PythonResolution,
    tz_ok: bool,
    local_exists: bool,
) -> list[str]:
    commands: list[str] = []
    if not local_exists and resolution.source == "shared_worktree_venv":
        commands.append(f"python tools/imp.py env bootstrap --link-venv")
    if not resolution.supported:
        commands.append(
            f"{resolution.executable} tools/imp.py validate fast"
            if resolution.source != "current_interpreter"
            else f"set {IMP_PYTHON_ENV}=<path-to-python311> (or run env bootstrap --link-venv)"
        )
    elif resolution.executable.resolve() != Path(sys.executable).resolve():
        commands.append(f"{resolution.executable} tools/imp.py validate fast")
    else:
        commands.append("python tools/imp.py validate fast")
    if not tz_ok:
        commands.append("install tzdata in the resolved virtual environment")
    if not (root / "ui" / "node_modules").is_dir():
        commands.append("cd ui && npm ci")
    return commands


def effective_python_executable(project_root: Path | None = None) -> Path:
    resolution = resolve_python(project_root)
    if not resolution.supported:
        raise RuntimeError(
            "unsupported Python interpreter for IMP validation; run "
            "`python tools/imp.py env` and follow next_commands"
        )
    return resolution.executable


__all__ = [
    "HARD_PYTHON_VERSION",
    "IMP_PYTHON_ENV",
    "PythonResolution",
    "WorktreeInfo",
    "build_environment_report",
    "detect_worktree",
    "effective_python_executable",
    "imp_project_root",
    "link_local_venv",
    "python_supported",
    "resolve_python",
    "timezone_ready",
]
