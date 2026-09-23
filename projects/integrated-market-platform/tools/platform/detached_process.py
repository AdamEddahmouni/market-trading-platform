"""IMP-owned process spawn helper for campaign supervision.

Default Windows flags (tested): ``CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW``.
``CREATE_BREAKAWAY_FROM_JOB`` is an explicit opt-in and remains **unproven** for
job/terminal-kill survival on this host. ``DETACHED_PROCESS`` is **not** used
(aborted child Python processes in testing). This helper does **not** claim that
``Start-Process -WindowStyle Hidden`` is durable.
"""

from __future__ import annotations

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
    allow_breakaway: bool = False,
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
        process = subprocess.Popen(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            **popen_kwargs,
        )
        process._imp_log_handle = handle  # type: ignore[attr-defined]
        note = path.parent / "detach-flags-used.txt"
        try:
            note.write_text(
                f"{'breakaway_opt_in' if allow_breakaway else 'no_breakaway_default'}:{creationflags}\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        return int(process.pid)

    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        **popen_kwargs,
    )
    return int(process.pid)


def mechanism_description(*, allow_breakaway: bool = False) -> dict[str, object]:
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
        "job_or_terminal_kill_survival_proven": False,
        "parent_process_exit_survival_proven_without_breakaway": True,
        "notes": (
            "Default/tested mechanism is CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW "
            f"({SELECTED_MECHANISM_DEFAULT}). CREATE_BREAKAWAY_FROM_JOB is an explicit "
            "opt-in and remains UNPROVEN for Windows job-kill / terminal-independent "
            "durability on this host. DETACHED_PROCESS is not used. "
            "Start-Process -WindowStyle Hidden is not treated as durable. "
            "Product guarantee is fail-visible detection when supervisor/heartbeat is "
            "dead or stale — not a proven detached OS service."
        ),
    }


__all__ = [
    "SELECTED_MECHANISM_BREAKAWAY_OPT_IN",
    "SELECTED_MECHANISM_DEFAULT",
    "mechanism_description",
    "spawn_detached",
    "windows_detached_creationflags",
]
