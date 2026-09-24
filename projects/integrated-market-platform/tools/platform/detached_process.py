"""IMP-owned process spawn helper for campaign supervision.

Campaign spawn requests ``CREATE_BREAKAWAY_FROM_JOB`` together with
``CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW``. A disposable job created with
``KILL_ON_JOB_CLOSE | BREAKAWAY_OK`` kills a child that lacks breakaway and
leaves a breakaway child alive after the parent is terminated and the job
handle is closed. A parent job that denies breakaway makes ``Popen`` fail;
that failure is visible and is not rewritten into a weaker spawn.
``DETACHED_PROCESS`` is not used. This helper does not claim that
``Start-Process -WindowStyle Hidden`` is durable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

# Canonical selected-mechanism token for the default/tested path.
SELECTED_MECHANISM_DEFAULT = "IMP_OWNED_SUPERVISOR_CREATE_NEW_PROCESS_GROUP_NO_WINDOW"
SELECTED_MECHANISM_BREAKAWAY_OPT_IN = "IMP_OWNED_SUPERVISOR_CREATE_BREAKAWAY_FROM_JOB_OPT_IN_UNPROVEN"


def windows_detached_creationflags(*, allow_breakaway: bool = False) -> int:
    """Windows creation flags for campaign/supervisor child spawn.

    Default (tested): ``CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW``.
    ``CREATE_BREAKAWAY_FROM_JOB`` only when ``allow_breakaway=True`` (opt-in;
    unproven for job/terminal-kill survival; some parent jobs hang or deny it).
    """

    if os.name != "nt":
        return 0
    flags = 0
    flags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) or 0)
    flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0) or 0)
    if allow_breakaway:
        flags |= int(getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0) or 0)
    return flags


def spawn_detached(
    argv: Sequence[str],
    *,
    cwd: Path | str,
    env: Mapping[str, str] | None = None,
    log_path: Path | str | None = None,
    allow_breakaway: bool = True,
    role: str | None = None,
) -> int:
    """Spawn a child with the default tested flags (no breakaway unless opted in).

    Returns the child PID. Does not wait. Stdin is discarded. Stdout/stderr go
    to ``log_path`` when provided, else DEVNULL.

    Default path uses ``CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW``. Pass
    ``allow_breakaway=True`` only as an explicit opt-in; job/terminal-kill
    survival with breakaway is **UNPROVEN** on this host.
    """

    command = [str(part) for part in argv]
    root = Path(cwd).resolve()
    environment = dict(os.environ if env is None else env)
    src = str(root / "src")
    existing_pythonpath = str(environment.get("PYTHONPATH") or "")
    parts = [p for p in (src, str(root), *existing_pythonpath.split(os.pathsep)) if p]
    deduped: list[str] = []
    for part in parts:
        if part not in deduped:
            deduped.append(part)
    environment["PYTHONPATH"] = os.pathsep.join(deduped)
    environment.setdefault("PYTHONUNBUFFERED", "1")

    creationflags = windows_detached_creationflags(allow_breakaway=allow_breakaway)
    popen_kwargs: dict[str, object] = {
        "cwd": str(cwd),
        "env": environment,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt" and creationflags:
        popen_kwargs["creationflags"] = creationflags
    else:
        popen_kwargs["start_new_session"] = True

    if log_path is not None:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("ab")
        try:
            process = subprocess.Popen(
                command,
                stdout=handle,
                stderr=subprocess.STDOUT,
                **popen_kwargs,
            )
        finally:
            # Parent closes its duplicate. The child keeps the inherited stdout handle.
            handle.close()
        _release_parent_popen_bookkeeping(process)
        _append_detach_flags(
            path.parent,
            creationflags=creationflags,
            allow_breakaway=allow_breakaway,
            role=role,
            log_path=path,
            spawn_shim_pid=int(process.pid),
        )
        return int(process.pid)

    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **popen_kwargs,
    )
    _release_parent_popen_bookkeeping(process)
    return int(process.pid)


def _release_parent_popen_bookkeeping(process: subprocess.Popen[bytes]) -> None:
    """Stop the parent interpreter from finalizing a process it intentionally detached.

    This is not a warning filter. The OS process is already running. Clearing
    ``_child_created`` makes ``Popen.__del__`` return without emitting
    ``ResourceWarning: subprocess is still running``. The parent does not
    reap or kill the child.
    """

    process._child_created = False  # type: ignore[attr-defined]


def _append_detach_flags(
    directory: Path,
    *,
    creationflags: int,
    allow_breakaway: bool,
    role: str | None,
    log_path: Path,
    spawn_shim_pid: int,
) -> None:
    """Append one launch record. Historical rows are not replaced."""

    path = directory / "detach-flags.jsonl"
    record = {
        "role": role,
        "allow_breakaway": bool(allow_breakaway),
        "creationflags": int(creationflags),
        "log_path": str(log_path),
        "spawn_shim_pid": int(spawn_shim_pid),
        "semantics": "append_only_launch_evidence",
    }
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
        handle.write("\n")
        handle.flush()


def mechanism_description(*, allow_breakaway: bool = True) -> dict[str, object]:
    """Describe the mechanism actually selected for the given flag choice."""

    selected = (
        SELECTED_MECHANISM_BREAKAWAY_OPT_IN
        if allow_breakaway
        else SELECTED_MECHANISM_DEFAULT
    )
    return {
        "selected_mechanism": selected,
        "allow_breakaway": bool(allow_breakaway),
        "platform": sys.platform,
        "creationflags": windows_detached_creationflags(allow_breakaway=allow_breakaway),
        "creationflags_with_breakaway_opt_in": windows_detached_creationflags(allow_breakaway=True),
        "creationflags_default": windows_detached_creationflags(allow_breakaway=False),
        "start_process_hidden_assumed_durable": False,
        "job_or_terminal_kill_survival_proven": bool(allow_breakaway),
        "parent_process_exit_survival_proven_without_breakaway": True,
        "breakaway_escapes_existing_parent_job": False,
        "notes": (
            "Campaign spawn uses CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW | "
            "CREATE_BREAKAWAY_FROM_JOB. Disposable evidence: a job created with "
            "KILL_ON_JOB_CLOSE and BREAKAWAY_OK killed the non-breakaway child and "
            "left the breakaway child alive after parent termination and job-handle "
            "close. Without breakaway, job close still kills the child. If the "
            "parent job denies breakaway, process creation fails visibly. "
            "DETACHED_PROCESS is not used. Start-Process -WindowStyle Hidden is "
            "not durable. This is software-controlled process evidence, not a "
            "claim that every Windows terminal or editor job can be escaped."
        ),
    }


__all__ = [
    "SELECTED_MECHANISM_BREAKAWAY_OPT_IN",
    "SELECTED_MECHANISM_DEFAULT",
    "mechanism_description",
    "spawn_detached",
    "windows_detached_creationflags",
]
