from __future__ import annotations

from importlib import metadata
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence

from src.ticker_metadata.models import CollectorProvenance


GitRunner = Callable[[Sequence[str], Path], str]


def _run_git(arguments: Sequence[str], cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout


def collect_provenance(
    repository_root: Path,
    *,
    git_runner: GitRunner = _run_git,
) -> CollectorProvenance:
    try:
        revision = git_runner(("rev-parse", "HEAD"), repository_root).strip()
        if not revision:
            revision = "unknown"
        dirty = bool(git_runner(("status", "--porcelain"), repository_root).strip())
    except Exception:
        revision = "unknown"
        dirty = True
    try:
        provider_version = metadata.version("yfinance")
    except Exception:
        provider_version = "unknown"
    return CollectorProvenance(
        collector_git_revision=revision,
        collector_dirty=dirty,
        python_version=".".join(str(part) for part in sys.version_info[:3]),
        provider_library_name="yfinance",
        provider_library_version=provider_version,
    )
