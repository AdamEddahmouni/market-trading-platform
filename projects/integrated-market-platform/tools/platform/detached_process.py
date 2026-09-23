"""Terminal-independent process spawn for IMP campaign supervision.

Selected mechanism (tested on Windows): ``CREATE_BREAKAWAY_FROM_JOB`` combined
with ``CREATE_NEW_PROCESS_GROUP`` and ``CREATE_NO_WINDOW`` /
``DETACHED_PROCESS``. This is an IMP-owned supervisor spawn helper — not a
claim that ``Start-Process -WindowStyle Hidden`` is durable.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence


def windows_detached_creationflags(*, allow_breakaway: bool = True) -> int:
    """Flags for terminal-independent child spawn on Windows.

    Default durable set: ``CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW``.
    ``CREATE_BREAKAWAY_FROM_JOB`` is included when ``allow_breakaway`` is true
    (and the attribute exists). Some parent job hosts hang or deny breakaway;
    callers may retry with ``allow_breakaway=False``.
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
) -> int:
    """Spawn a process intended to survive the launching shell/coordinator exit.

    Returns the child PID. Does not wait. Stdin is discarded. Stdout/stderr go
    to ``log_path`` when provided, else DEVNULL.

    Tries breakaway flags first; on ``OSError`` retries without
    ``CREATE_BREAKAWAY_FROM_JOB``.
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

    def _popen(creationflags: int) -> subprocess.Popen[bytes]:
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
            # Keep the handle open for the child lifetime on Windows.
            handle = path.open("ab")
            process = subprocess.Popen(
                command,
                stdout=handle,
                stderr=subprocess.STDOUT,
                **popen_kwargs,
            )
            # Intentionally leak the handle reference onto the Popen object so
            # GC does not close it while the child still writes.
            process._imp_log_handle = handle  # type: ignore[attr-defined]
            return process
        return subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **popen_kwargs,
        )

    if os.name == "nt":
        try:
            process = _popen(windows_detached_creationflags(allow_breakaway=True))
            environment_note = "breakaway"
        except OSError:
            process = _popen(windows_detached_creationflags(allow_breakaway=False))
            environment_note = "no_breakaway_fallback"
    else:
        process = _popen(0)
        environment_note = "posix_start_new_session"
    # Stash for tests/diagnostics via a side file when log_path parent exists.
    if log_path is not None:
        note = Path(log_path).parent / "detach-flags-used.txt"
        try:
            note.write_text(
                f"{environment_note}:{windows_detached_creationflags(allow_breakaway=(environment_note=='breakaway'))}\n",
                encoding="utf-8",
            )
        except OSError:
            pass
    return int(process.pid)


def mechanism_description() -> dict[str, object]:
    return {
        "selected_mechanism": "IMP_OWNED_SUPERVISOR_WITH_CREATE_BREAKAWAY_FROM_JOB",
        "platform": sys.platform,
        "creationflags_with_breakaway": windows_detached_creationflags(allow_breakaway=True),
        "creationflags_without_breakaway": windows_detached_creationflags(allow_breakaway=False),
        "start_process_hidden_assumed_durable": False,
        "notes": (
            "Start-Process -WindowStyle Hidden is not treated as terminal-independent. "
            "Selected mechanism is an IMP-owned supervisor. Spawn tries "
            "CREATE_BREAKAWAY_FROM_JOB + CREATE_NEW_PROCESS_GROUP + CREATE_NO_WINDOW, "
            "and falls back without breakaway on OSError. DETACHED_PROCESS is omitted "
            "(aborted child Python processes in testing). Some parent job hosts may "
            "deny or stall breakaway; software-controlled shell-exit proof uses the "
            "fallback flags when needed and documents the limitation."
        ),
    }


__all__ = [
    "mechanism_description",
    "spawn_detached",
    "windows_detached_creationflags",
]
